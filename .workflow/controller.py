#!/usr/bin/env python3
"""Plan deterministic repository-workflow transitions from observed GitHub state."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"invalid {label}: expected a JSON object")
    return value


def is_active(candidate: dict[str, Any]) -> bool:
    return (
        candidate.get("draft") is False
        and candidate.get("closed") is not True
        and candidate.get("merged") is not True
    )


def is_eligible(candidate: dict[str, Any]) -> bool:
    return candidate.get("draft") is True and can_hold_landing_slot(candidate)


def can_hold_landing_slot(candidate: dict[str, Any]) -> bool:
    sequence = candidate.get("queue_sequence")
    owner = candidate.get("owner")
    dependencies = candidate.get("open_dependencies", [])
    return (
        isinstance(sequence, int)
        and not isinstance(sequence, bool)
        and sequence > 0
        and candidate.get("lifecycle") in {"Waiting to land", "In PR"}
        and isinstance(owner, str)
        and bool(owner)
        and dependencies == []
        and candidate.get("hold") is not True
        and candidate.get("material_rework") is not True
        and candidate.get("closed") is not True
        and candidate.get("merged") is not True
    )


def has_current_promotion(candidate: dict[str, Any]) -> bool:
    promotion = candidate.get("promotion")
    return (
        isinstance(promotion, dict)
        and promotion.get("head_sha") == candidate.get("head_sha")
        and promotion.get("base_sha") == candidate.get("base_sha")
        and promotion.get("local_gates_passed") is True
        and promotion.get("review_passed") is True
    )


def has_current_local_completion(candidate: dict[str, Any]) -> bool:
    completion = candidate.get("local_completion")
    return (
        isinstance(completion, dict)
        and isinstance(completion.get("id"), str)
        and bool(completion["id"])
        and completion.get("candidate_commit") == candidate.get("head_sha")
    )


def config_errors(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if config.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    mode = config.get("mode")
    if mode not in {"audit", "enforcement"}:
        errors.append("mode must be audit or enforcement")
    enforcement_enabled = config.get("enforcement_enabled")
    if not isinstance(enforcement_enabled, bool):
        errors.append("enforcement_enabled must be boolean")
    elif mode == "enforcement" and not enforcement_enabled:
        errors.append("enforcement mode requires enforcement_enabled true")
    elif mode == "enforcement":
        errors.append("this controller build supports audit mode only")
    interval = config.get("reconciliation_minutes")
    if interval != 15 or isinstance(interval, bool):
        errors.append("reconciliation_minutes must be 15 for this workflow build")
    checks = config.get("required_status_checks")
    if not isinstance(checks, list) or not all(
        isinstance(check, str) and bool(check) for check in checks
    ):
        errors.append("required_status_checks must be a list of names")
    elif config.get("repository") != "Pending GitHub setup" and not checks:
        errors.append("connected audit configuration requires required_status_checks")
    if config.get("landing_record_location") != "pull_request_comments":
        errors.append("landing_record_location must be pull_request_comments")
    project_fields = config.get("project_fields")
    if not isinstance(project_fields, dict) or not all(
        isinstance(project_fields.get(key), str) and bool(project_fields[key])
        for key in ("lifecycle", "queue_sequence")
    ):
        errors.append("project_fields must name lifecycle and queue_sequence")
    coordinators = config.get("authorized_coordinators")
    if not isinstance(coordinators, list) or not coordinators or not all(
        isinstance(login, str) and bool(login) for login in coordinators
    ):
        errors.append("authorized_coordinators must be a non-empty list of logins")
    required_strings = (
        "repository",
        "base_branch",
        "project_id",
        "merge_method",
        "app_client_id_variable",
        "app_private_key_secret",
    )
    for field in required_strings:
        if not isinstance(config.get(field), str) or not config[field]:
            errors.append(f"{field} must be a non-empty string")
    if config.get("app_client_id_variable") != "WORKFLOW_APP_CLIENT_ID":
        errors.append("app_client_id_variable must be WORKFLOW_APP_CLIENT_ID")
    if config.get("app_private_key_secret") != "WORKFLOW_APP_PRIVATE_KEY":
        errors.append("app_private_key_secret must be WORKFLOW_APP_PRIVATE_KEY")
    if mode == "enforcement":
        for field in ("repository", "base_branch", "project_id", "merge_method"):
            if config.get(field) == "Pending GitHub setup":
                errors.append(f"enforcement requires configured {field}")
        if checks == []:
            errors.append("enforcement requires required_status_checks")
        if coordinators == ["Pending GitHub setup"]:
            errors.append("enforcement requires configured authorized_coordinators")
    return errors


def plan(snapshot: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    event_id = event.get("id")
    mode = snapshot.get("mode")
    highest = snapshot.get("highest_queue_sequence")
    candidates = snapshot.get("candidates")
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("invalid event: id must be a non-empty string")
    if mode not in {"audit", "enforcement"}:
        raise ValueError("invalid snapshot: mode must be audit or enforcement")
    if not isinstance(highest, int) or isinstance(highest, bool) or highest < 0:
        raise ValueError(
            "invalid snapshot: highest_queue_sequence must be a non-negative integer"
        )
    if not isinstance(candidates, list):
        raise ValueError("invalid snapshot: candidates must be a list")

    mutations: list[dict[str, Any]] = []
    violations: list[str] = []
    next_sequence = highest + 1

    seen_sequences: set[int] = set()
    duplicate_sequences: set[int] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("invalid snapshot: each candidate must be an object")
        sequence = candidate.get("queue_sequence")
        if isinstance(sequence, int) and not isinstance(sequence, bool) and sequence > 0:
            if sequence in seen_sequences:
                duplicate_sequences.add(sequence)
            seen_sequences.add(sequence)
    violations.extend(
        f"Queue sequence {sequence} is duplicated"
        for sequence in sorted(duplicate_sequences)
    )

    if event.get("type") == "converted_to_draft":
        event_pull_request = event.get("pull_request")
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise ValueError("invalid snapshot: each candidate must be an object")
            if candidate.get("pull_request") != event_pull_request:
                continue
            sequence = candidate.get("queue_sequence")
            if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
                raise ValueError(
                    "invalid converted candidate: queue_sequence must be positive"
                )
            if candidate.get("auto_merge") is True:
                mutations.append(
                    {
                        "kind": "disable_auto_merge",
                        "pull_request": event_pull_request,
                    }
                )
            mutations.extend(
                (
                    {
                        "kind": "set_lifecycle",
                        "pull_request": event_pull_request,
                        "value": "Waiting to land",
                    },
                    {
                        "kind": "post_candidate_returned_to_draft",
                        "pull_request": event_pull_request,
                        "queue_sequence": sequence,
                    },
                )
            )
            break

    if event.get("type") == "closed":
        event_pull_request = event.get("pull_request")
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise ValueError("invalid snapshot: each candidate must be an object")
            if (
                candidate.get("pull_request") != event_pull_request
                or candidate.get("merged") is True
            ):
                continue
            sequence = candidate.get("queue_sequence")
            if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
                raise ValueError(
                    "invalid closed candidate: queue_sequence must be positive"
                )
            if candidate.get("auto_merge") is True:
                mutations.append(
                    {
                        "kind": "disable_auto_merge",
                        "pull_request": event_pull_request,
                    }
                )
            mutations.extend(
                (
                    {
                        "kind": "set_lifecycle",
                        "pull_request": event_pull_request,
                        "value": "Waiting to land",
                    },
                    {
                        "kind": "post_candidate_attention",
                        "pull_request": event_pull_request,
                        "queue_sequence": sequence,
                        "reason": "pull request closed without merging",
                    },
                )
            )
            break

    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("invalid snapshot: each candidate must be an object")
        if (
            candidate.get("merged") is not True
            or candidate.get("lifecycle") == "Landed"
        ):
            continue
        pull_request = candidate.get("pull_request")
        batch = candidate.get("batch")
        merge_commit = candidate.get("merge_commit")
        branch = candidate.get("branch")
        delivered_tickets = candidate.get("delivered_tickets", [])
        dependants = candidate.get("dependants", [])
        if not isinstance(pull_request, int) or isinstance(pull_request, bool):
            raise ValueError("invalid candidate: pull_request must be an integer")
        if not isinstance(merge_commit, str) or not merge_commit:
            raise ValueError("invalid merged candidate: merge_commit is required")
        if not isinstance(batch, int) or isinstance(batch, bool) or batch < 1:
            raise ValueError("invalid merged candidate: batch must be an issue number")
        if not isinstance(branch, str) or not branch:
            raise ValueError("invalid merged candidate: branch is required")
        if not isinstance(delivered_tickets, list) or not all(
            isinstance(issue, int) and not isinstance(issue, bool)
            for issue in delivered_tickets
        ):
            raise ValueError(
                "invalid merged candidate: delivered_tickets must be issue numbers"
            )
        if not isinstance(dependants, list) or not all(
            isinstance(issue, int) and not isinstance(issue, bool)
            for issue in dependants
        ):
            raise ValueError("invalid merged candidate: dependants must be issue numbers")
        mutations.extend(
            (
                {
                    "kind": "set_lifecycle",
                    "pull_request": pull_request,
                    "value": "Landed",
                },
                {
                    "kind": "post_candidate_landed",
                    "merge_commit": merge_commit,
                    "pull_request": pull_request,
                },
                {
                    "issue": batch,
                    "kind": "close_landing_batch",
                    "pull_request": pull_request,
                },
            )
        )
        mutations.extend(
            {
                "issue": issue,
                "kind": "close_delivered_ticket",
                "pull_request": pull_request,
            }
            for issue in delivered_tickets
        )
        mutations.append(
            {
                "branch": branch,
                "kind": "delete_remote_branch",
                "pull_request": pull_request,
            }
        )
        mutations.extend(
            {
                "issue": issue,
                "kind": "post_dependant_unblocked",
                "pull_request": pull_request,
            }
            for issue in dependants
        )

    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("invalid snapshot: each candidate must be an object")
        if candidate.get("material_rework") is not True:
            continue
        pull_request = candidate.get("pull_request")
        sequence = candidate.get("queue_sequence")
        reason = candidate.get("rework_reason")
        if not isinstance(pull_request, int) or isinstance(pull_request, bool):
            raise ValueError("invalid candidate: pull_request must be an integer")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            raise ValueError(
                "invalid material rework: queue_sequence must be a positive integer"
            )
        if not isinstance(reason, str) or not reason:
            raise ValueError("invalid material rework: rework_reason is required")
        if candidate.get("auto_merge") is True:
            mutations.append(
                {"kind": "disable_auto_merge", "pull_request": pull_request}
            )
        if candidate.get("draft") is False:
            mutations.append({"kind": "mark_draft", "pull_request": pull_request})
        mutations.extend(
            (
                {
                    "kind": "clear_queue_sequence",
                    "pull_request": pull_request,
                    "retired_value": sequence,
                },
                {
                    "kind": "set_lifecycle",
                    "pull_request": pull_request,
                    "value": "Building",
                },
                {
                    "kind": "post_candidate_rework",
                    "pull_request": pull_request,
                    "reason": reason,
                    "retired_queue_sequence": sequence,
                },
            )
        )

    invalid_local_completions: set[int] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("invalid snapshot: each candidate must be an object")
        completion = candidate.get("local_completion")
        lifecycle = candidate.get("lifecycle")
        if lifecycle not in {"Building", "Locally complete"}:
            continue
        if (
            candidate.get("material_rework") is True
            or candidate.get("closed") is True
            or candidate.get("merged") is True
        ):
            continue
        pull_request = candidate.get("pull_request")
        head_sha = candidate.get("head_sha")
        if not isinstance(pull_request, int) or isinstance(pull_request, bool):
            raise ValueError("invalid candidate: pull_request must be an integer")
        if not isinstance(head_sha, str) or not head_sha:
            raise ValueError("invalid candidate: head_sha is required")
        partial_queue_sequence = None
        for repair_name in ("queue_repair", "receipt_repair"):
            repair = candidate.get(repair_name)
            if isinstance(repair, dict):
                sequence = repair.get("queue_sequence")
                if isinstance(sequence, int) and not isinstance(sequence, bool):
                    partial_queue_sequence = sequence
        if completion is None:
            if lifecycle == "Locally complete":
                invalid_local_completions.add(pull_request)
                if candidate.get("local_completion_retired") is not True:
                    missing_mutation = {
                        "kind": "post_local_completion_missing",
                        "pull_request": pull_request,
                        "reason": "current local-complete evidence is missing",
                    }
                    if partial_queue_sequence is not None:
                        missing_mutation["retired_queue_sequence"] = (
                            partial_queue_sequence
                        )
                    mutations.append(missing_mutation)
                mutations.append(
                    {
                        "kind": "set_lifecycle",
                        "pull_request": pull_request,
                        "value": "Building",
                    }
                )
            continue
        if not isinstance(completion, dict):
            raise ValueError("invalid local completion: expected an object")
        candidate_commit = completion.get("candidate_commit")
        completion_id = completion.get("id")
        if not isinstance(candidate_commit, str) or not candidate_commit:
            raise ValueError("invalid local completion: candidate_commit is required")
        if not isinstance(completion_id, str) or not completion_id:
            raise ValueError("invalid local completion: id is required")
        if lifecycle == "Building" and candidate_commit == head_sha:
            mutations.append(
                {
                    "kind": "set_lifecycle",
                    "pull_request": pull_request,
                    "value": "Locally complete",
                }
            )
        elif lifecycle == "Locally complete" and candidate_commit != head_sha:
            invalid_local_completions.add(pull_request)
            mutations.extend(
                (
                    {
                        "candidate_commit": candidate_commit,
                        "current_head": head_sha,
                        "kind": "post_local_completion_invalidated",
                        "local_completion": completion_id,
                        "pull_request": pull_request,
                        "reason": "candidate commit does not match current PR head",
                        **(
                            {"retired_queue_sequence": partial_queue_sequence}
                            if partial_queue_sequence is not None
                            else {}
                        ),
                    },
                    {
                        "kind": "set_lifecycle",
                        "pull_request": pull_request,
                        "value": "Building",
                    },
                )
            )

    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("invalid snapshot: each candidate must be an object")
        pull_request = candidate.get("pull_request")
        queue_repair = candidate.get("queue_repair")
        receipt_repair = candidate.get("receipt_repair")
        queue_cleanup = candidate.get("queue_cleanup")
        if queue_cleanup is not None:
            if not isinstance(pull_request, int) or isinstance(pull_request, bool):
                raise ValueError("invalid candidate: pull_request must be an integer")
            if not isinstance(queue_cleanup, dict):
                raise ValueError("invalid queue cleanup: expected an object")
            retired_value = queue_cleanup.get("retired_value")
            if (
                not isinstance(retired_value, int)
                or isinstance(retired_value, bool)
                or retired_value < 1
            ):
                raise ValueError("invalid queue cleanup: retired_value must be positive")
            mutations.append(
                {
                    "kind": "clear_queue_sequence",
                    "pull_request": pull_request,
                    "retired_value": retired_value,
                }
            )
        if (queue_repair is not None or receipt_repair is not None) and not (
            has_current_local_completion(candidate)
            and pull_request not in invalid_local_completions
        ):
            if isinstance(candidate.get("queue_sequence"), int):
                mutations.append(
                    {
                        "kind": "clear_queue_sequence",
                        "pull_request": pull_request,
                        "retired_value": candidate["queue_sequence"],
                    }
                )
            continue
        if queue_repair is not None:
            if not isinstance(pull_request, int) or isinstance(pull_request, bool):
                raise ValueError("invalid candidate: pull_request must be an integer")
            if not isinstance(queue_repair, dict):
                raise ValueError("invalid queue repair: expected an object")
            sequence = queue_repair.get("queue_sequence")
            if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
                raise ValueError("invalid queue repair: queue_sequence must be positive")
            mutations.extend(
                (
                    {
                        "kind": "set_queue_sequence",
                        "pull_request": pull_request,
                        "value": sequence,
                    },
                    {
                        "kind": "set_lifecycle",
                        "pull_request": pull_request,
                        "value": "Waiting to land",
                    },
                )
            )
        if receipt_repair is not None:
            if not isinstance(pull_request, int) or isinstance(pull_request, bool):
                raise ValueError("invalid candidate: pull_request must be an integer")
            if not isinstance(receipt_repair, dict):
                raise ValueError("invalid receipt repair: expected an object")
            sequence = receipt_repair.get("queue_sequence")
            request_id = receipt_repair.get("id")
            if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
                raise ValueError("invalid receipt repair: queue_sequence must be positive")
            if not isinstance(request_id, str) or not request_id:
                raise ValueError("invalid receipt repair: id is required")
            mutations.append(
                {
                    "accepted": True,
                    "kind": "post_queue_receipt",
                    "pull_request": pull_request,
                    "queue_request": request_id,
                    "queue_sequence": sequence,
                }
            )

    queueable: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("invalid snapshot: each candidate must be an object")
        request = candidate.get("queue_request")
        if (
            candidate.get("lifecycle") != "Locally complete"
            or candidate.get("queue_sequence") is not None
            or not isinstance(request, dict)
            or candidate.get("pull_request") in invalid_local_completions
            or not has_current_local_completion(candidate)
        ):
            continue
        requested_at = request.get("requested_at")
        if not isinstance(requested_at, str) or not requested_at:
            raise ValueError("invalid queue request: requested_at is required")
        pull_request = candidate.get("pull_request")
        if not isinstance(pull_request, int) or isinstance(pull_request, bool):
            raise ValueError("invalid candidate: pull_request must be an integer")
        queueable.append(candidate)

    queueable.sort(
        key=lambda candidate: (
            candidate["queue_request"]["requested_at"],
            candidate.get("pull_request", 0),
        )
    )
    for candidate in queueable:
        request = candidate["queue_request"]
        pull_request = candidate.get("pull_request")
        request_id = request.get("id")
        if not isinstance(pull_request, int) or isinstance(pull_request, bool):
            raise ValueError("invalid candidate: pull_request must be an integer")
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("invalid queue request: id must be a non-empty string")
        if request.get("candidate_commit") != candidate.get("head_sha"):
            mutations.append(
                {
                    "accepted": False,
                    "kind": "post_queue_receipt",
                    "pull_request": pull_request,
                    "queue_request": request_id,
                    "queue_sequence": None,
                    "reason": "candidate commit does not match current PR head",
                }
            )
            continue
        mutations.extend(
            (
                {
                    "kind": "set_queue_sequence",
                    "pull_request": pull_request,
                    "value": next_sequence,
                },
                {
                    "kind": "set_lifecycle",
                    "pull_request": pull_request,
                    "value": "Waiting to land",
                },
                {
                    "accepted": True,
                    "kind": "post_queue_receipt",
                    "pull_request": pull_request,
                    "queue_request": request_id,
                    "queue_sequence": next_sequence,
                },
            )
        )
        next_sequence += 1

    active = [
        candidate
        for candidate in candidates
        if is_active(candidate) and candidate.get("material_rework") is not True
    ]
    if len(active) > 1:
        violations.append("more than one non-draft landing candidate is active")
    invalid_active: set[int] = set()
    if len(active) == 1:
        current = active[0]
        sequence = current.get("queue_sequence")
        pull_request = current.get("pull_request")
        if not isinstance(pull_request, int) or isinstance(pull_request, bool):
            raise ValueError("invalid active candidate: pull_request must be an integer")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            raise ValueError(
                "invalid active candidate: queue_sequence must be a positive integer"
            )
        slot_candidates = sorted(
            (
                candidate
                for candidate in candidates
                if isinstance(candidate, dict) and can_hold_landing_slot(candidate)
            ),
            key=lambda candidate: (
                candidate["queue_sequence"],
                candidate["pull_request"],
            ),
        )
        reason = None
        if not has_current_promotion(current):
            reason = "promotion evidence no longer matches the active candidate"
        elif not can_hold_landing_slot(current):
            reason = "active candidate is no longer eligible"
        elif slot_candidates and slot_candidates[0].get("pull_request") != pull_request:
            reason = "active candidate is not the lowest-sequence eligible candidate"
        if reason is not None:
            if current.get("auto_merge") is True:
                mutations.append(
                    {"kind": "disable_auto_merge", "pull_request": pull_request}
                )
            mutations.extend(
                (
                    {"kind": "mark_draft", "pull_request": pull_request},
                    {
                        "kind": "set_lifecycle",
                        "pull_request": pull_request,
                        "value": "Waiting to land",
                    },
                    {
                        "kind": "post_candidate_attention",
                        "pull_request": pull_request,
                        "queue_sequence": sequence,
                        "reason": reason,
                    },
                )
            )
            invalid_active.add(pull_request)

    effective_active = [
        candidate
        for candidate in active
        if candidate.get("pull_request") not in invalid_active
    ]
    if not effective_active and len(active) <= 1:
        eligible = sorted(
            (
                candidate
                for candidate in candidates
                if isinstance(candidate, dict) and is_eligible(candidate)
            ),
            key=lambda candidate: (
                candidate["queue_sequence"],
                candidate["pull_request"],
            ),
        )
        selected = eligible[0] if eligible else None
        if selected is not None and has_current_promotion(selected):
            repository = snapshot.get("repository")
            if not isinstance(repository, dict):
                raise ValueError("invalid snapshot: repository must be an object")
            if repository.get("auto_merge_allowed") is not True:
                violations.append("repository auto-merge is not enabled")
            else:
                merge_method = repository.get("merge_method")
                if not isinstance(merge_method, str) or not merge_method:
                    raise ValueError(
                        "invalid repository: merge_method must be a non-empty string"
                    )
                pull_request = selected["pull_request"]
                mutations.extend(
                    (
                        {"kind": "mark_ready", "pull_request": pull_request},
                        {
                            "kind": "set_lifecycle",
                            "pull_request": pull_request,
                            "value": "In PR",
                        },
                        {
                            "kind": "enable_auto_merge",
                            "merge_method": merge_method,
                            "pull_request": pull_request,
                        },
                        {
                            "candidate_commit": selected["head_sha"],
                            "kind": "post_candidate_activation",
                            "pull_request": pull_request,
                            "queue_sequence": selected["queue_sequence"],
                        },
                    )
                )

    if mode == "enforcement" and violations:
        mutations = []

    return {
        "event_id": event_id,
        "mode": mode,
        "mutations": mutations,
        "violations": violations,
    }


def authorize_landing_ci(snapshot: dict[str, Any], pull_request: int) -> str | None:
    candidates = snapshot.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("invalid snapshot: candidates must be a list")
    active = [
        candidate
        for candidate in candidates
        if isinstance(candidate, dict) and is_active(candidate)
    ]
    if len(active) != 1:
        return "exactly one active landing candidate is required"
    candidate = active[0]
    if candidate.get("pull_request") != pull_request:
        return "pull request is not the active landing candidate"
    if candidate.get("auto_merge") is not True:
        return "active landing candidate does not have auto-merge enabled"
    if not can_hold_landing_slot(candidate):
        return "active landing candidate is no longer eligible"
    if not has_current_promotion(candidate):
        return "active landing candidate promotion evidence is stale"
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--snapshot", type=Path, required=True)
    plan_parser.add_argument("--event", type=Path, required=True)
    config_parser = subparsers.add_parser("validate-config")
    config_parser.add_argument("--config", type=Path, required=True)
    authorize_parser = subparsers.add_parser("authorize-ci")
    authorize_parser.add_argument("--snapshot", type=Path, required=True)
    authorize_parser.add_argument("--pull-request", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "validate-config":
            config = read_object(args.config, "controller config")
            errors = config_errors(config)
            if errors:
                print("\n".join(errors), file=sys.stderr)
                return 2
            print(f"CONTROLLER CONFIG VALID: {config['mode']}")
            return 0
        if args.command == "authorize-ci":
            snapshot = read_object(args.snapshot, "snapshot")
            reason = authorize_landing_ci(snapshot, args.pull_request)
            if reason is not None:
                print(f"LANDING CI REFUSED: {reason}", file=sys.stderr)
                return 1
            print(f"LANDING CI AUTHORIZED: pull request {args.pull_request}")
            return 0
        snapshot = read_object(args.snapshot, "snapshot")
        event = read_object(args.event, "event")
        result = plan(snapshot, event)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["mode"] == "enforcement" and result["violations"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
