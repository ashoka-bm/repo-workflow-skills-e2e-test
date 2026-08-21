#!/usr/bin/env python3
"""Read GitHub state and normalize it for the repository workflow controller."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


API_VERSION = "2026-03-10"
RECORD_LINE = re.compile(r"(?m)^([a-z][a-z0-9_]*):\s*(.*?)\s*$")
LANDING_BATCH = re.compile(
    r"(?mi)^\s*-?\s*Landing batch:\s*(?:https://github\.com/[^/]+/[^/]+/issues/)?#?(\d+)\s*$"
)
DELIVERED_TICKET = re.compile(
    r"(?mi)^\s*(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)\s*$"
)
LOCAL_AFTER = re.compile(r"(?mi)^\s*-\s*Local after:\s*(.+?)\s*$")
ISSUE_REFERENCE = re.compile(r"(?:/issues/|#)(\d+)")


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"invalid {label}: expected a JSON object")
    return value


def scalar(value: str) -> Any:
    value = value.strip().strip("`\"'")
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "none" or value == "null":
        return None
    if re.fullmatch(r"[1-9]\d*|0", value):
        return int(value)
    return value


def record(comment: dict[str, Any]) -> dict[str, Any] | None:
    body = comment.get("body")
    if not isinstance(body, str):
        return None
    fields = {key: scalar(value) for key, value in RECORD_LINE.findall(body)}
    event = fields.get("event")
    if not isinstance(event, str):
        return None
    comment_id = comment.get("id")
    if not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id < 1:
        raise ValueError("invalid GitHub data: comment id must be a positive integer")
    fields["_comment_id"] = comment_id
    fields["_created_at"] = str(comment.get("created_at", ""))
    fields["_updated_at"] = str(comment.get("updated_at", ""))
    author = comment.get("author")
    if not isinstance(author, str):
        user = comment.get("user")
        author = user.get("login") if isinstance(user, dict) else None
    fields["_author"] = author
    return fields


def records(comments: Any) -> list[dict[str, Any]]:
    if not isinstance(comments, list):
        raise ValueError("invalid GitHub data: comments must be a list")
    parsed = [record(comment) for comment in comments if isinstance(comment, dict)]
    return sorted(
        (entry for entry in parsed if entry is not None),
        key=lambda entry: (entry["_created_at"], entry["_comment_id"]),
    )


def latest(entries: list[dict[str, Any]], event: str) -> dict[str, Any] | None:
    matches = [entry for entry in entries if entry.get("event") == event]
    return matches[-1] if matches else None


def newest(
    entries: list[dict[str, Any]], event_names: set[str]
) -> dict[str, Any] | None:
    matches = [entry for entry in entries if entry.get("event") in event_names]
    return matches[-1] if matches else None


def positive_integer(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def referenced_comment_id(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    if not isinstance(value, str):
        return None
    match = re.search(r"(?:issuecomment-|^)(\d+)$", value)
    return int(match.group(1)) if match else None


def referenced_issue_number(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    if not isinstance(value, str):
        return None
    match = ISSUE_REFERENCE.search(value)
    return int(match.group(1)) if match else None


def local_prerequisite_graph(value: Any) -> dict[int, list[int]] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError("child_tickets must be a list")
    graph: dict[int, list[int]] = {}
    for child in value:
        if not isinstance(child, dict):
            raise ValueError("child ticket must be an object")
        number = positive_integer(child.get("number"))
        body = child.get("body")
        if number is None or not isinstance(body, str):
            raise ValueError("child ticket requires a number and body")
        match = LOCAL_AFTER.search(body)
        if match is None:
            raise ValueError(f"child ticket #{number} is missing Local after")
        text = match.group(1).strip()
        prerequisites = (
            []
            if text.lower() == "none"
            else [int(candidate) for candidate in ISSUE_REFERENCE.findall(text)]
        )
        if text.lower() != "none" and not prerequisites:
            raise ValueError(f"child ticket #{number} has invalid Local after")
        if len(prerequisites) != len(set(prerequisites)):
            raise ValueError(f"child ticket #{number} repeats a local prerequisite")
        graph[number] = prerequisites
    visiting: set[int] = set()
    visited: set[int] = set()

    def visit(ticket: int) -> bool:
        if ticket in visiting:
            return True
        if ticket in visited:
            return False
        visiting.add(ticket)
        if any(
            visit(prerequisite)
            for prerequisite in graph[ticket]
            if prerequisite in graph
        ):
            return True
        visiting.remove(ticket)
        visited.add(ticket)
        return False

    if any(visit(ticket) for ticket in graph):
        raise ValueError("child ticket local prerequisite graph contains a cycle")
    return graph


def local_slice_state(
    *,
    batch: int,
    graph: dict[int, list[int]],
    item: dict[str, Any],
    entries: list[dict[str, Any]],
    entries_by_id: dict[int, dict[str, Any]],
    owner: Any,
    authorized_coordinators: list[Any],
    commit_shas: Any,
    commit_parents: Any,
) -> dict[str, Any]:
    checkpoints = [
        entry for entry in entries if entry.get("event") == "slice-checkpoint"
    ]
    if commit_shas is None and not checkpoints:
        commit_shas = []
    if not isinstance(commit_shas, list) or not all(
        isinstance(commit, str) and bool(commit) for commit in commit_shas
    ):
        raise ValueError("slice checkpoints require pull-request commit SHAs")
    if checkpoints and (
        not isinstance(commit_parents, dict)
        or set(commit_shas) - set(commit_parents)
        or not all(
            isinstance(commit, str)
            and isinstance(parents, list)
            and all(isinstance(parent, str) and parent for parent in parents)
            for commit, parents in commit_parents.items()
        )
    ):
        raise ValueError("slice checkpoints require pull-request commit ancestry")

    def is_ancestor(ancestor: str, descendant: str) -> bool:
        pending = [descendant]
        seen: set[str] = set()
        while pending:
            commit = pending.pop()
            if commit == ancestor:
                return True
            if commit in seen:
                continue
            seen.add(commit)
            pending.extend(commit_parents.get(commit, []))
        return False

    current_by_ticket: dict[int, dict[str, Any]] = {}
    slice_events = [
        entry
        for entry in entries
        if entry.get("event")
        in {"slice-checkpoint", "slice-checkpoint-invalidated"}
    ]
    if slice_events:
        claim_receipt, claim_request = current_claim_receipt(
            item, owner, authorized_coordinators
        )
        claim_position = (
            claim_receipt["_created_at"],
            claim_receipt["_comment_id"],
        )
        descendants: dict[int, set[int]] = {ticket: set() for ticket in graph}
        for possible_descendant, prerequisites in graph.items():
            pending = list(prerequisites)
            seen: set[int] = set()
            while pending:
                prerequisite = pending.pop()
                if prerequisite in seen:
                    continue
                seen.add(prerequisite)
                if prerequisite not in graph:
                    continue
                descendants[prerequisite].add(possible_descendant)
                pending.extend(graph[prerequisite])

        for entry in slice_events:
            entry_position = (entry["_created_at"], entry["_comment_id"])
            if entry_position <= claim_position:
                continue
            if entry.get("event") == "slice-checkpoint-invalidated":
                require_unedited(entry, "slice-checkpoint-invalidated")
                if entry.get("_author") not in {owner, *authorized_coordinators}:
                    raise ValueError(
                        "slice-checkpoint-invalidated must be authored by the owner or coordinator"
                    )
                checkpoint_id = referenced_comment_id(entry.get("checkpoint"))
                checkpoint = entries_by_id.get(checkpoint_id)
                if checkpoint is None or checkpoint.get("event") != "slice-checkpoint":
                    raise ValueError(
                        "slice-checkpoint-invalidated must reference its slice-checkpoint"
                    )
                if not isinstance(entry.get("reason"), str) or not entry["reason"]:
                    raise ValueError("slice-checkpoint-invalidated reason is required")
                if entry_position <= (
                    checkpoint["_created_at"],
                    checkpoint["_comment_id"],
                ):
                    raise ValueError(
                        "slice checkpoint invalidation must follow its checkpoint"
                    )
                checkpoint_ticket = referenced_issue_number(checkpoint.get("ticket"))
                current = current_by_ticket.get(checkpoint_ticket)
                if current is None or current["_comment_id"] != checkpoint_id:
                    raise ValueError(
                        "slice-checkpoint-invalidated must reference the current slice-checkpoint"
                    )
                current_by_ticket.pop(checkpoint_ticket)
                for dependant in descendants[checkpoint_ticket]:
                    current_by_ticket.pop(dependant, None)
                continue

            checkpoint = entry
            require_unedited(checkpoint, "slice-checkpoint")
            if checkpoint.get("_author") != owner:
                raise ValueError(
                    f"slice-checkpoint must be authored by landing batch owner {owner}"
                )
            if referenced_issue_number(checkpoint.get("batch")) != batch:
                raise ValueError("slice-checkpoint batch does not match landing batch")
            ticket = referenced_issue_number(checkpoint.get("ticket"))
            if ticket not in graph:
                raise ValueError("slice-checkpoint ticket is not a child of the batch")
            if referenced_comment_id(checkpoint.get("claim_receipt")) != claim_receipt[
                "_comment_id"
            ]:
                raise ValueError(
                    "slice-checkpoint must reference the current accepted claim receipt"
                )
            for field in ("worker", "session"):
                if checkpoint.get(field) != claim_request[field]:
                    raise ValueError(
                        f"slice-checkpoint {field} must match the current claim-request"
                    )
            if checkpoint.get("focused_gates_passed") is not True:
                raise ValueError("slice-checkpoint requires focused_gates_passed: true")
            starting_commit = checkpoint.get("starting_commit")
            slice_commit = checkpoint.get("slice_commit")
            if not isinstance(starting_commit, str) or not starting_commit:
                raise ValueError("slice-checkpoint starting_commit is required")
            if slice_commit not in commit_shas:
                raise ValueError("slice-checkpoint commit is not in the pull request")
            if starting_commit == slice_commit:
                raise ValueError("slice-checkpoint must contain a non-empty slice diff")
            if not is_ancestor(starting_commit, slice_commit):
                raise ValueError(
                    "slice-checkpoint commit must descend from its starting_commit"
                )
            review_id = referenced_comment_id(checkpoint.get("review"))
            review = entries_by_id.get(review_id)
            if review is None or review.get("event") != "slice-review":
                raise ValueError("slice-checkpoint must reference its slice-review")
            require_unedited(review, "slice-review")
            review_author = review.get("_author")
            if not isinstance(review_author, str) or not review_author:
                raise ValueError("slice-review author must be a GitHub actor")
            if review_author == owner:
                raise ValueError("slice-review must be authored by another actor")
            if review.get("verdict") != "passed":
                raise ValueError("slice-review verdict must be passed")
            if referenced_issue_number(review.get("ticket")) != ticket:
                raise ValueError("slice-review ticket must match slice-checkpoint")
            for field in ("starting_commit", "slice_commit"):
                if review.get(field) != checkpoint.get(field):
                    raise ValueError(f"slice-review {field} must match slice-checkpoint")
            review_position = (review["_created_at"], review["_comment_id"])
            checkpoint_position = (
                checkpoint["_created_at"],
                checkpoint["_comment_id"],
            )
            if review_position <= claim_position:
                raise ValueError("slice-review must follow the current claim receipt")
            if review_position >= checkpoint_position:
                raise ValueError("slice-review must precede slice-checkpoint")
            if ticket in current_by_ticket:
                raise ValueError(
                    "a current slice-checkpoint must be invalidated before replacement"
                )
            internal_prerequisites = set(graph[ticket]) & set(graph)
            if not internal_prerequisites <= set(current_by_ticket):
                raise ValueError(
                    "slice-checkpoint local prerequisites are not current"
                )
            for prerequisite in internal_prerequisites:
                prerequisite_commit = current_by_ticket[prerequisite]["slice_commit"]
                if not is_ancestor(prerequisite_commit, starting_commit):
                    raise ValueError(
                        "slice-checkpoint starting_commit does not contain current "
                        "local prerequisite commits"
                    )
            current_by_ticket[ticket] = checkpoint

    completed = set(current_by_ticket)
    frontier = sorted(
        ticket
        for ticket, prerequisites in graph.items()
        if ticket not in completed and (set(prerequisites) & set(graph)) <= completed
    )
    blocked = {
        str(ticket): sorted((set(prerequisites) & set(graph)) - completed)
        for ticket, prerequisites in graph.items()
        if ticket not in completed and ticket not in frontier
    }
    return {
        "local_frontier": frontier,
        "locally_blocked": blocked,
        "slice_checkpoints": [
            {
                "comment_id": current_by_ticket[ticket]["_comment_id"],
                "slice_commit": current_by_ticket[ticket]["slice_commit"],
                "ticket": ticket,
            }
            for ticket in sorted(completed)
        ],
    }


def require_unedited(entry: dict[str, Any], event: str) -> None:
    created_at = entry.get("_created_at")
    updated_at = entry.get("_updated_at")
    if (
        not isinstance(created_at, str)
        or not created_at
        or not isinstance(updated_at, str)
        or updated_at != created_at
    ):
        raise ValueError(f"{event} must be an unedited GitHub comment")


def current_claim_receipt(
    item: dict[str, Any], owner: Any, authorized_coordinators: list[Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(owner, str) or not owner:
        raise ValueError("local-complete requires a current landing batch owner")
    entries = records(item.get("comments", []))
    entries_by_id = {entry["_comment_id"]: entry for entry in entries}
    accepted = [
        entry
        for entry in entries
        if entry.get("event") == "claim-receipt" and entry.get("accepted") is True
    ]
    if not accepted:
        raise ValueError("local-complete requires a current accepted claim receipt")
    receipt = accepted[-1]
    require_unedited(receipt, "claim-receipt")
    if receipt.get("_author") not in authorized_coordinators:
        raise ValueError(
            "accepted claim receipt must be authored by an authorized coordinator"
        )
    request_id = referenced_comment_id(receipt.get("request"))
    request = entries_by_id.get(request_id)
    if request is None or request.get("event") != "claim-request":
        raise ValueError("accepted claim receipt must reference its claim-request")
    require_unedited(request, "claim-request")
    request_author = request.get("_author")
    if not isinstance(request_author, str) or not request_author:
        raise ValueError("claim-request author must be a GitHub actor")
    if request_author != owner or request.get("actor") != owner:
        raise ValueError("current accepted claim receipt does not match batch owner")
    for field in ("worker", "session"):
        if not isinstance(request.get(field), str) or not request[field]:
            raise ValueError(f"claim-request {field} is required")
    if (
        receipt["_created_at"],
        receipt["_comment_id"],
    ) <= (request["_created_at"], request["_comment_id"]):
        raise ValueError("accepted claim receipt must follow its claim-request")
    reason = receipt.get("reason")
    if not isinstance(reason, str) or not reason:
        raise ValueError("accepted claim receipt reason is required")
    receipt_position = (receipt["_created_at"], receipt["_comment_id"])
    claim_barrier = newest(entries, {"release", "handoff"})
    if claim_barrier is not None and (
        claim_barrier["_created_at"],
        claim_barrier["_comment_id"],
    ) > receipt_position:
        raise ValueError("local-complete requires a claim after release or handoff")
    recovery = latest(entries, "recovery-result")
    if (
        recovery is not None
        and (recovery["_created_at"], recovery["_comment_id"]) > receipt_position
        and recovery.get("outcome") == "released"
    ):
        raise ValueError("local-complete cannot use a released claim")
    return receipt, request


def normalize(config: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    repository = raw.get("repository")
    project_items = raw.get("project_items")
    pull_requests = raw.get("pull_requests")
    if not isinstance(repository, dict):
        raise ValueError("invalid GitHub data: repository must be an object")
    if not isinstance(project_items, list):
        raise ValueError("invalid GitHub data: project_items must be a list")
    if not isinstance(pull_requests, list):
        raise ValueError("invalid GitHub data: pull_requests must be a list")

    items_by_issue: dict[int, dict[str, Any]] = {}
    highest = 0
    for item in project_items:
        if not isinstance(item, dict):
            raise ValueError("invalid GitHub data: project item must be an object")
        issue_number = positive_integer(item.get("issue_number"))
        if issue_number is None:
            continue
        items_by_issue[issue_number] = item
        owners = item.get("owners")
        if isinstance(owners, list) and len(owners) > 1:
            raise ValueError(f"landing batch #{issue_number} has more than one owner")
        sequence = positive_integer(item.get("queue_sequence"))
        if sequence is not None:
            highest = max(highest, sequence)

    candidates: list[dict[str, Any]] = []
    candidate_graphs: dict[int, dict[int, list[int]]] = {}
    authorized_coordinators = config.get("authorized_coordinators", [])
    if not isinstance(authorized_coordinators, list):
        raise ValueError("invalid controller config: authorized_coordinators must be a list")
    for pull_request in pull_requests:
        if not isinstance(pull_request, dict):
            raise ValueError("invalid GitHub data: pull request must be an object")
        body = pull_request.get("body") or ""
        if not isinstance(body, str):
            raise ValueError("invalid GitHub data: pull request body must be text")
        match = LANDING_BATCH.search(body)
        if match is None:
            continue
        batch = int(match.group(1))
        item = items_by_issue.get(batch)
        if item is None:
            raise ValueError(f"landing batch #{batch} is missing from the configured Project")

        entries = records(pull_request.get("comments", []))
        entries_by_id = {entry["_comment_id"]: entry for entry in entries}
        owner = item.get("owner")
        if isinstance(owner, str) and owner in authorized_coordinators:
            raise ValueError(
                f"landing batch #{batch} owner must not be an authorized coordinator"
            )
        for entry in entries:
            event = entry.get("event")
            if event in {
                "queue-receipt",
                "candidate-rework",
                "local-completion-invalidated",
                "local-completion-missing",
            } and entry.get("_author") not in authorized_coordinators:
                raise ValueError(
                    f"{event} must be authored by an authorized coordinator"
                )
        for entry in entries:
            if entry.get("event") == "queue-receipt" and entry.get("accepted") is True:
                request_id = referenced_comment_id(entry.get("request"))
                request_record = entries_by_id.get(request_id)
                if request_record is None or request_record.get("event") != "queue-request":
                    raise ValueError(
                        "accepted queue receipt must reference its queue-request"
                    )
                if not isinstance(entry.get("reason"), str) or not entry["reason"]:
                    raise ValueError("accepted queue receipt reason is required")
                sequence = positive_integer(entry.get("queue_sequence"))
                if sequence is not None:
                    highest = max(highest, sequence)
            if entry.get("event") == "candidate-rework":
                sequence = positive_integer(entry.get("retired_queue_sequence"))
                if sequence is not None:
                    highest = max(highest, sequence)
            if entry.get("event") in {
                "local-completion-invalidated",
                "local-completion-missing",
            }:
                sequence = positive_integer(entry.get("retired_queue_sequence"))
                if sequence is not None:
                    highest = max(highest, sequence)

        number = positive_integer(pull_request.get("number"))
        if number is None:
            raise ValueError("invalid GitHub data: pull request number must be positive")
        state = pull_request.get("state")
        merged = bool(pull_request.get("merged") or pull_request.get("merged_at"))
        delivered_tickets = sorted(
            {int(issue) for issue in DELIVERED_TICKET.findall(body)}
        )
        child_issues = item.get("child_issues")
        if isinstance(child_issues, list):
            undeclared = sorted(set(delivered_tickets) - set(child_issues))
            if undeclared:
                raise ValueError(
                    "delivered tickets are not native children of the landing batch: "
                    + ", ".join(str(issue) for issue in undeclared)
                )
        candidate: dict[str, Any] = {
            "auto_merge": pull_request.get("auto_merge") is True,
            "base_sha": pull_request.get("base_sha"),
            "batch": batch,
            "branch": pull_request.get("head_ref"),
            "closed": state == "closed",
            "delivered_tickets": delivered_tickets,
            "dependants": item.get("dependants", []),
            "draft": pull_request.get("draft"),
            "head_sha": pull_request.get("head_sha"),
            "hold": item.get("hold") is True,
            "lifecycle": item.get("lifecycle"),
            "merged": merged,
            "open_dependencies": item.get("open_dependencies", []),
            "owner": owner,
            "pull_request": number,
            "queue_sequence": item.get("queue_sequence"),
        }
        local_graph = local_prerequisite_graph(item.get("child_tickets"))
        if local_graph is not None:
            candidate_graphs[batch] = local_graph
            candidate.update(
                local_slice_state(
                    batch=batch,
                    graph=local_graph,
                    item=item,
                    entries=entries,
                    entries_by_id=entries_by_id,
                    owner=owner,
                    authorized_coordinators=authorized_coordinators,
                    commit_shas=pull_request.get("commit_shas"),
                    commit_parents=pull_request.get("commit_parents"),
                )
            )
        blocker = newest(entries, {"candidate-blocked", "candidate-unblocked"})
        if blocker is not None:
            if blocker.get("_author") not in authorized_coordinators:
                raise ValueError(
                    f"{blocker.get('event')} must be authored by an authorized coordinator"
                )
            candidate["hold"] = blocker.get("event") == "candidate-blocked"

        rework_request = latest(entries, "rework-request")
        applied_rework = latest(entries, "candidate-rework")
        completion_invalidation = latest(entries, "local-completion-invalidated")
        if completion_invalidation is not None:
            require_unedited(
                completion_invalidation, "local-completion-invalidated"
            )
            invalidated_id = referenced_comment_id(
                completion_invalidation.get("completion")
            )
            invalidated = entries_by_id.get(invalidated_id)
            if invalidated is None or invalidated.get("event") != "local-complete":
                raise ValueError(
                    "local-completion-invalidated must reference its local-complete record"
                )
            reason = completion_invalidation.get("reason")
            if not isinstance(reason, str) or not reason:
                raise ValueError("local-completion-invalidated reason is required")
        completion_missing = latest(entries, "local-completion-missing")
        if completion_missing is not None:
            require_unedited(completion_missing, "local-completion-missing")
            reason = completion_missing.get("reason")
            if not isinstance(reason, str) or not reason:
                raise ValueError("local-completion-missing reason is required")
        completion_barrier = newest(
            entries,
            {
                "candidate-rework",
                "local-completion-invalidated",
                "local-completion-missing",
            },
        )
        local_completion = latest(entries, "local-complete")
        if local_completion is not None and (
            completion_barrier is None
            or (
                local_completion["_created_at"],
                local_completion["_comment_id"],
            )
            > (
                completion_barrier["_created_at"],
                completion_barrier["_comment_id"],
            )
        ):
            completion_author = local_completion.get("_author")
            if not isinstance(completion_author, str) or not completion_author:
                raise ValueError("local-complete author must be a GitHub actor")
            if completion_author != owner:
                raise ValueError(
                    f"local-complete must be authored by landing batch owner {owner}"
                )
            require_unedited(local_completion, "local-complete")
            claim_receipt, claim_request = current_claim_receipt(
                item, owner, authorized_coordinators
            )
            claim_receipt_id = referenced_comment_id(
                local_completion.get("claim_receipt")
            )
            if claim_receipt_id != claim_receipt["_comment_id"]:
                raise ValueError(
                    "local-complete must reference the current accepted claim receipt"
                )
            if (
                local_completion["_created_at"],
                local_completion["_comment_id"],
            ) <= (
                claim_receipt["_created_at"],
                claim_receipt["_comment_id"],
            ):
                raise ValueError("local-complete must follow its accepted claim receipt")
            candidate_commit = local_completion.get("candidate_commit")
            if not isinstance(candidate_commit, str) or not candidate_commit:
                raise ValueError("local-complete candidate_commit is required")
            if local_completion.get("local_gates_passed") is not True:
                raise ValueError("local-complete requires local_gates_passed: true")
            for field in ("worker", "session"):
                if local_completion.get(field) != claim_request[field]:
                    raise ValueError(
                        f"local-complete {field} must match the current claim-request"
                    )
            review_id = referenced_comment_id(local_completion.get("review"))
            review = entries_by_id.get(review_id)
            if review is None or review.get("event") != "local-review":
                raise ValueError("local-complete must reference its local-review")
            require_unedited(review, "local-review")
            review_author = review.get("_author")
            if not isinstance(review_author, str) or not review_author:
                raise ValueError("local-review author must be a GitHub actor")
            if review_author == owner:
                raise ValueError("local-review must be authored by another actor")
            if review.get("reviewed_by") != review_author:
                raise ValueError("local-review reviewed_by must match its author")
            if review.get("verdict") != "passed":
                raise ValueError("local-review verdict must be passed")
            if review.get("candidate_commit") != candidate_commit:
                raise ValueError(
                    "local-review candidate commit must match local-complete"
                )
            review_position = (review["_created_at"], review["_comment_id"])
            claim_position = (
                claim_receipt["_created_at"],
                claim_receipt["_comment_id"],
            )
            completion_position = (
                local_completion["_created_at"],
                local_completion["_comment_id"],
            )
            if review_position <= claim_position:
                raise ValueError("local-review must follow the current claim receipt")
            if completion_barrier is not None and review_position <= (
                completion_barrier["_created_at"],
                completion_barrier["_comment_id"],
            ):
                raise ValueError("local-review must follow completion invalidation")
            if review_position >= completion_position:
                raise ValueError("local-review must precede local-complete")
            candidate["local_completion"] = {
                "candidate_commit": candidate_commit,
                "completed_at": local_completion["_created_at"],
                "id": str(local_completion["_comment_id"]),
            }
        elif completion_barrier is not None:
            candidate["local_completion_retired"] = True

        if rework_request is not None and (
            applied_rework is None
            or (
                rework_request["_created_at"],
                rework_request["_comment_id"],
            )
            > (applied_rework["_created_at"], applied_rework["_comment_id"])
        ):
            if rework_request.get("_author") != owner:
                raise ValueError(
                    f"rework-request must be authored by landing batch owner {owner}"
                )
            if rework_request.get("candidate_commit") != candidate["head_sha"]:
                raise ValueError("rework-request candidate commit does not match PR head")
            reason = rework_request.get("reason")
            if not isinstance(reason, str) or not reason:
                raise ValueError("rework-request reason is required")
            candidate["material_rework"] = True
            candidate["rework_reason"] = reason
        if merged:
            candidate["merge_commit"] = pull_request.get("merge_commit")

        queue_request = latest(entries, "queue-request")
        if queue_request is not None and completion_barrier is not None and (
            queue_request["_created_at"],
            queue_request["_comment_id"],
        ) <= (
            completion_barrier["_created_at"],
            completion_barrier["_comment_id"],
        ):
            queue_request = None
        accepted_receipts = [
            entry
            for entry in entries
            if entry.get("event") == "queue-receipt"
            and entry.get("accepted") is True
            and positive_integer(entry.get("queue_sequence")) is not None
            and (
                completion_barrier is None
                or (entry["_created_at"], entry["_comment_id"])
                > (
                    completion_barrier["_created_at"],
                    completion_barrier["_comment_id"],
                )
            )
        ]
        accepted_receipt = accepted_receipts[-1] if accepted_receipts else None
        project_sequence = positive_integer(candidate["queue_sequence"])
        if accepted_receipt is not None:
            accepted_sequence = positive_integer(accepted_receipt["queue_sequence"])
            request_id = referenced_comment_id(accepted_receipt.get("request"))
            accepted_request = entries_by_id.get(request_id)
            if completion_barrier is not None and accepted_request is not None and (
                accepted_request["_created_at"],
                accepted_request["_comment_id"],
            ) <= (
                completion_barrier["_created_at"],
                completion_barrier["_comment_id"],
            ):
                reason = (
                    "rework"
                    if completion_barrier.get("event") == "candidate-rework"
                    else "local-completion invalidation"
                )
                raise ValueError(
                    f"accepted receipt references a queue-request retired by {reason}"
                )
            if project_sequence is None:
                if accepted_request is None or accepted_request.get(
                    "candidate_commit"
                ) != candidate["head_sha"]:
                    raise ValueError(
                        "accepted queue-request candidate commit does not match PR head"
                    )
                if candidate["lifecycle"] not in {
                    "Locally complete",
                    "Waiting to land",
                    "In PR",
                }:
                    raise ValueError(
                        "accepted Queue sequence has an incompatible lifecycle"
                    )
                candidate["queue_repair"] = {
                    "queue_sequence": accepted_sequence,
                }
            elif project_sequence != accepted_sequence:
                raise ValueError(
                    "accepted queue receipt and Project Queue sequence disagree"
                )
        elif project_sequence is not None and queue_request is not None:
            if queue_request.get("_author") != owner:
                raise ValueError(
                    f"queue-request must be authored by landing batch owner {owner}"
                )
            if completion_barrier is not None and (
                queue_request["_created_at"],
                queue_request["_comment_id"],
            ) <= (
                completion_barrier["_created_at"],
                completion_barrier["_comment_id"],
            ):
                raise ValueError("Project Queue sequence remains after completion reset")
            if queue_request.get("candidate_commit") != candidate["head_sha"]:
                raise ValueError("queue-request candidate commit does not match PR head")
            if candidate["lifecycle"] not in {
                "Locally complete",
                "Waiting to land",
                "In PR",
            }:
                raise ValueError(
                    "Project Queue sequence has an incompatible lifecycle"
                )
            candidate["receipt_repair"] = {
                "id": str(queue_request["_comment_id"]),
                "queue_sequence": project_sequence,
            }
        elif project_sequence is not None and completion_barrier is not None:
            retired_sequence = positive_integer(
                completion_barrier.get("retired_queue_sequence")
            )
            if retired_sequence != project_sequence:
                raise ValueError(
                    "completion reset does not preserve the Project Queue sequence"
                )
            candidate["queue_cleanup"] = {"retired_value": project_sequence}
        elif project_sequence is not None:
            raise ValueError(
                "Project Queue sequence has no accepted receipt or queue request"
            )
        elif candidate["queue_sequence"] is None and queue_request is not None:
            if queue_request.get("_author") != owner:
                raise ValueError(
                    f"queue-request must be authored by landing batch owner {owner}"
                )
            candidate["queue_request"] = {
                "candidate_commit": queue_request.get("candidate_commit"),
                "id": str(queue_request["_comment_id"]),
                "requested_at": queue_request["_created_at"],
            }

        promotion = latest(entries, "promote-request")
        if promotion is not None and candidate["lifecycle"] in {
            "Waiting to land",
            "In PR",
        }:
            if promotion.get("_author") != owner:
                raise ValueError(
                    f"promote-request must be authored by landing batch owner {owner}"
                )
            candidate["promotion"] = {
                "base_sha": promotion.get("base_commit"),
                "head_sha": promotion.get("candidate_commit"),
                "local_gates_passed": promotion.get("local_gates_passed") is True,
                "review_passed": (
                    promotion.get("another_agent_review_passed") is True
                ),
            }
        candidates.append(candidate)

    candidates.sort(key=lambda candidate: candidate["pull_request"])
    checkpoint_tickets = {
        checkpoint["ticket"]
        for candidate in candidates
        for checkpoint in candidate.get("slice_checkpoints", [])
    }
    for candidate in candidates:
        graph = candidate_graphs.get(candidate["batch"])
        if graph is None:
            continue
        completed = {
            checkpoint["ticket"]
            for checkpoint in candidate.get("slice_checkpoints", [])
        }
        candidate["local_frontier"] = sorted(
            ticket
            for ticket, prerequisites in graph.items()
            if ticket not in completed and set(prerequisites) <= checkpoint_tickets
        )
        candidate["locally_blocked"] = {
            str(ticket): sorted(set(prerequisites) - checkpoint_tickets)
            for ticket, prerequisites in graph.items()
            if ticket not in completed and ticket not in candidate["local_frontier"]
        }
    return {
        "candidates": candidates,
        "highest_queue_sequence": highest,
        "mode": config.get("mode"),
        "repository": {
            "auto_merge_allowed": repository.get("auto_merge_allowed") is True,
            "merge_method": config.get("merge_method"),
        },
    }


def request_json(
    token: str,
    url: str,
    *,
    data: dict[str, Any] | None = None,
) -> Any:
    payload = None if data is None else json.dumps(data).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": API_VERSION,
        },
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError) as error:
        raise ValueError(f"GitHub API request failed for {url}: {error}") from error


def rest_pages(token: str, api: str, path: str) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    page = 1
    separator = "&" if "?" in path else "?"
    while True:
        result = request_json(token, f"{api}{path}{separator}per_page=100&page={page}")
        if not isinstance(result, list) or not all(isinstance(item, dict) for item in result):
            raise ValueError(f"GitHub API returned an invalid list for {path}")
        values.extend(result)
        if len(result) < 100:
            return values
        page += 1


PROJECT_QUERY = """
query($id: ID!, $cursor: String) {
  node(id: $id) {
    ... on ProjectV2 {
      items(first: 100, after: $cursor) {
        nodes {
          content {
            ... on Issue {
              number
              assignees(first: 10) { nodes { login } }
            }
          }
          fieldValues(first: 50) {
            nodes {
              ... on ProjectV2ItemFieldNumberValue {
                number
                field { ... on ProjectV2FieldCommon { name } }
              }
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field { ... on ProjectV2FieldCommon { name } }
              }
            }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
"""


def project_items(
    token: str,
    api: str,
    project_id: str,
    field_names: dict[str, str],
) -> list[dict[str, Any]]:
    cursor: str | None = None
    items: list[dict[str, Any]] = []
    while True:
        result = request_json(
            token,
            f"{api}/graphql",
            data={"query": PROJECT_QUERY, "variables": {"id": project_id, "cursor": cursor}},
        )
        if not isinstance(result, dict) or result.get("errors"):
            raise ValueError(f"GitHub Project query failed: {result}")
        try:
            connection = result["data"]["node"]["items"]
        except (KeyError, TypeError) as error:
            raise ValueError("GitHub Project query returned incomplete data") from error
        for node in connection.get("nodes", []):
            content = node.get("content") or {}
            issue_number = positive_integer(content.get("number"))
            if issue_number is None:
                continue
            fields: dict[str, Any] = {}
            for value in (node.get("fieldValues") or {}).get("nodes", []):
                field = value.get("field") or {}
                name = field.get("name")
                if isinstance(name, str):
                    fields[name] = value.get("number", value.get("name"))
            assignees = (content.get("assignees") or {}).get("nodes", [])
            if len(assignees) > 1:
                raise ValueError(
                    f"landing batch #{issue_number} has more than one owner"
                )
            owner = assignees[0].get("login") if assignees else None
            queue_sequence = fields.get(field_names["queue_sequence"])
            if isinstance(queue_sequence, float) and queue_sequence.is_integer():
                queue_sequence = int(queue_sequence)
            items.append(
                {
                    "issue_number": issue_number,
                    "lifecycle": fields.get(field_names["lifecycle"]),
                    "owner": owner,
                    "owners": [assignee.get("login") for assignee in assignees],
                    "queue_sequence": queue_sequence,
                }
            )
        page_info = connection.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            return items
        cursor = page_info.get("endCursor")
        if not isinstance(cursor, str) or not cursor:
            raise ValueError("GitHub Project pagination cursor is missing")


def collect(config: dict[str, Any], token: str) -> dict[str, Any]:
    repository_name = config.get("repository")
    project_id = config.get("project_id")
    base_branch = config.get("base_branch")
    if not all(
        isinstance(value, str) and value and value != "Pending GitHub setup"
        for value in (repository_name, project_id, base_branch)
    ):
        raise ValueError("controller GitHub identity is still Pending GitHub setup")
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    repository = request_json(token, f"{api}/repos/{repository_name}")
    if not isinstance(repository, dict):
        raise ValueError("GitHub repository response must be an object")
    pulls = rest_pages(
        token,
        api,
        f"/repos/{repository_name}/pulls?state=all&base={urllib.parse.quote(base_branch)}",
    )
    field_names = config.get("project_fields")
    if not isinstance(field_names, dict) or not all(
        isinstance(field_names.get(key), str) for key in ("lifecycle", "queue_sequence")
    ):
        raise ValueError("controller project_fields are not configured")
    items = project_items(token, api, project_id, field_names)
    items_by_issue = {item["issue_number"]: item for item in items}
    normalized_pulls: list[dict[str, Any]] = []
    for pull in pulls:
        body = pull.get("body") or ""
        match = LANDING_BATCH.search(body) if isinstance(body, str) else None
        if match is None:
            continue
        number = positive_integer(pull.get("number"))
        if number is None:
            raise ValueError("GitHub pull request number must be positive")
        batch = int(match.group(1))
        comments = rest_pages(
            token, api, f"/repos/{repository_name}/issues/{number}/comments?"
        )
        batch_comments = rest_pages(
            token, api, f"/repos/{repository_name}/issues/{batch}/comments?"
        )
        dependencies = rest_pages(
            token,
            api,
            f"/repos/{repository_name}/issues/{batch}/dependencies/blocked_by?",
        )
        dependants = rest_pages(
            token,
            api,
            f"/repos/{repository_name}/issues/{batch}/dependencies/blocking?",
        )
        child_issues = rest_pages(
            token,
            api,
            f"/repos/{repository_name}/issues/{batch}/sub_issues?",
        )
        pull_commits = rest_pages(
            token,
            api,
            f"/repos/{repository_name}/pulls/{number}/commits?",
        )
        item = items_by_issue.get(batch)
        if item is not None:
            item["comments"] = batch_comments
            item["open_dependencies"] = sorted(
                dependency["number"]
                for dependency in dependencies
                if dependency.get("state") == "open"
                and positive_integer(dependency.get("number")) is not None
            )
            item["dependants"] = sorted(
                issue["number"]
                for issue in dependants
                if issue.get("state") == "open"
                and positive_integer(issue.get("number")) is not None
            )
            item["child_issues"] = sorted(
                issue["number"]
                for issue in child_issues
                if positive_integer(issue.get("number")) is not None
            )
            item["child_tickets"] = [
                {"body": issue.get("body") or "", "number": issue["number"]}
                for issue in child_issues
                if positive_integer(issue.get("number")) is not None
            ]
        normalized_pulls.append(
            {
                "auto_merge": pull.get("auto_merge") is not None,
                "base_sha": (pull.get("base") or {}).get("sha"),
                "body": body,
                "comments": comments,
                "commit_shas": [
                    commit["sha"]
                    for commit in pull_commits
                    if isinstance(commit.get("sha"), str) and commit["sha"]
                ],
                "commit_parents": {
                    commit["sha"]: [
                        parent["sha"]
                        for parent in commit.get("parents", [])
                        if isinstance(parent, dict)
                        and isinstance(parent.get("sha"), str)
                        and parent["sha"]
                    ]
                    for commit in pull_commits
                    if isinstance(commit.get("sha"), str) and commit["sha"]
                },
                "draft": pull.get("draft"),
                "head_ref": (pull.get("head") or {}).get("ref"),
                "head_sha": (pull.get("head") or {}).get("sha"),
                "merge_commit": pull.get("merge_commit_sha"),
                "merged_at": pull.get("merged_at"),
                "number": number,
                "state": pull.get("state"),
            }
        )
    return {
        "project_items": items,
        "pull_requests": normalized_pulls,
        "repository": {"auto_merge_allowed": repository.get("allow_auto_merge") is True},
    }


def event_payload(event_name: str, event_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    action = payload.get("action")
    event_type = action if action in {"closed", "converted_to_draft"} else "reconcile"
    result: dict[str, Any] = {"id": event_id, "type": event_type}
    pull_request = payload.get("pull_request")
    if event_name == "pull_request_target" and isinstance(pull_request, dict):
        number = positive_integer(pull_request.get("number"))
        if number is not None:
            result["pull_request"] = number
    return result


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    normalize_parser = subparsers.add_parser("normalize")
    normalize_parser.add_argument("--config", type=Path, required=True)
    normalize_parser.add_argument("--github-data", type=Path, required=True)
    normalize_parser.add_argument("--output", type=Path, required=True)
    collect_parser = subparsers.add_parser("collect")
    collect_parser.add_argument("--config", type=Path, required=True)
    collect_parser.add_argument("--output", type=Path, required=True)
    event_parser = subparsers.add_parser("event")
    event_parser.add_argument("--event-name", required=True)
    event_parser.add_argument("--event-id", required=True)
    event_parser.add_argument("--github-event", type=Path, required=True)
    event_parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "event":
            payload = read_object(args.github_event, "GitHub event")
            write_json(
                args.output,
                event_payload(args.event_name, args.event_id, payload),
            )
            return 0
        config = read_object(args.config, "controller config")
        if args.command == "normalize":
            raw = read_object(args.github_data, "GitHub data")
        else:
            token = os.environ.get("GH_TOKEN")
            if not token:
                raise ValueError("GH_TOKEN is required to collect GitHub state")
            raw = collect(config, token)
        write_json(args.output, normalize(config, raw))
        return 0
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
