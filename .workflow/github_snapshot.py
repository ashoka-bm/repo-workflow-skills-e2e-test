#!/usr/bin/env python3
"""Read GitHub state and derive repository workflow evidence."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
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
STARTS_AFTER = re.compile(r"(?mi)^\s*-\s*Starts after:\s*(.+?)\s*$")
MUST_NOT_OVERLAP = re.compile(r"(?mi)^\s*-\s*Must not overlap:\s*(.+?)\s*$")
ISSUE_REFERENCE = re.compile(r"(?:/issues/|#)(\d+)")
CHECKPOINT_BINDING = re.compile(
    r"\s*(?:https://github\.com/[^/]+/[^/]+/issues/)?#?(\d+)\s*=\s*"
    r"(?:https://github\.com/[^/]+/[^/]+/issues/\d+#issuecomment-|issuecomment-)?"
    r"(\d+)\s*"
)


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


def issue_relation_numbers(body: Any, pattern: re.Pattern[str]) -> list[int]:
    if not isinstance(body, str):
        return []
    match = pattern.search(body)
    if match is None or match.group(1).strip().lower() == "none":
        return []
    numbers = sorted(
        {int(number) for number in ISSUE_REFERENCE.findall(match.group(1))}
    )
    if not numbers:
        raise ValueError(
            "Must not overlap must be none or reference a landing batch"
        )
    return numbers


def conflict_surface_labels(labels: Any) -> list[str]:
    if not isinstance(labels, list):
        return []
    names = [
        label.get("name") if isinstance(label, dict) else label
        for label in labels
    ]
    return sorted(
        name
        for name in names
        if isinstance(name, str) and name.startswith("surface:")
    )


def prerequisite_checkpoint_bindings(value: Any) -> dict[int, int]:
    if value is None:
        return {}
    if not isinstance(value, str) or not value.strip():
        raise ValueError("prerequisite_checkpoints must be a non-empty binding list")
    bindings: dict[int, int] = {}
    for part in value.split(","):
        match = CHECKPOINT_BINDING.fullmatch(part)
        if match is None:
            raise ValueError("prerequisite_checkpoints contains an invalid binding")
        ticket, checkpoint = (int(candidate) for candidate in match.groups())
        if ticket in bindings:
            raise ValueError(
                f"prerequisite_checkpoints repeats prerequisite ticket #{ticket}"
            )
        bindings[ticket] = checkpoint
    return bindings


def commit_is_ancestor(
    ancestor: str, descendant: str, commit_parents: dict[str, list[str]]
) -> bool:
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
    entries: list[dict[str, Any]],
    entries_by_id: dict[int, dict[str, Any]],
    owner: Any,
    ticket_owners: dict[int, str | None],
    authorized_maintainers: list[Any],
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
        raise ValueError("slice checkpoints require pull request commit SHAs")
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
        raise ValueError("slice checkpoints require pull request commit ancestry")

    current_by_ticket: dict[int, dict[str, Any]] = {}
    validated_checkpoints: dict[int, dict[str, Any]] = {}
    slice_events = [
        entry
        for entry in entries
        if entry.get("event")
        in {"slice-checkpoint", "slice-checkpoint-invalidated"}
    ]
    if slice_events:
        if not isinstance(owner, str) or not owner:
            raise ValueError("slice checkpoints require a current landing batch owner")
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
            if entry.get("event") == "slice-checkpoint-invalidated":
                require_unedited(entry, "slice-checkpoint-invalidated")
                if entry.get("_author") not in {owner, *authorized_maintainers}:
                    raise ValueError(
                        "slice-checkpoint-invalidated must be authored by the owner or workflow maintainer"
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
            ticket_owner = ticket_owners.get(ticket)
            if not isinstance(ticket_owner, str) or not ticket_owner:
                raise ValueError(
                    f"slice-checkpoint requires child ticket #{ticket} to have one assignee"
                )
            for field in ("worker", "session"):
                if not isinstance(checkpoint.get(field), str) or not checkpoint[field]:
                    raise ValueError(f"slice-checkpoint delegated {field} is required")
            delegated = checkpoint.get("delivery") is not None
            if checkpoint.get("focused_gates_passed") is not True:
                raise ValueError("slice-checkpoint requires focused_gates_passed: true")
            starting_commit = checkpoint.get("starting_commit")
            slice_commit = checkpoint.get("slice_commit")
            if not isinstance(starting_commit, str) or not starting_commit:
                raise ValueError("slice-checkpoint starting_commit is required")
            if starting_commit == slice_commit:
                raise ValueError("slice-checkpoint must contain a non-empty slice diff")
            delivery = None
            if delegated:
                delivery_id = referenced_comment_id(checkpoint.get("delivery"))
                delivery = entries_by_id.get(delivery_id)
                if delivery is None or delivery.get("event") != "slice-delivery":
                    raise ValueError(
                        "delegated slice-checkpoint must reference its slice-delivery"
                    )
                require_unedited(delivery, "slice-delivery")
                delivery_author = delivery.get("_author")
                if not isinstance(delivery_author, str) or not delivery_author:
                    raise ValueError("slice-delivery author must be a GitHub actor")
                if delivery_author != ticket_owner:
                    raise ValueError(
                        "slice-delivery must be authored by child ticket assignee "
                        f"{ticket_owner}"
                    )
                if referenced_issue_number(delivery.get("ticket")) != ticket:
                    raise ValueError("slice-delivery ticket must match slice-checkpoint")
                for field in (
                    "starting_commit",
                    "slice_commit",
                    "worker",
                    "session",
                ):
                    if delivery.get(field) != checkpoint.get(field):
                        raise ValueError(
                            f"slice-delivery {field} must match slice-checkpoint"
                        )
            elif ticket_owner != owner:
                raise ValueError(
                    "non-delegated slice-checkpoint requires the batch owner to be "
                    "the child ticket assignee"
                )
            review_id = referenced_comment_id(checkpoint.get("review"))
            review = entries_by_id.get(review_id)
            if review is None or review.get("event") != "slice-review":
                raise ValueError("slice-checkpoint must reference its slice-review")
            require_unedited(review, "slice-review")
            review_author = review.get("_author")
            if not isinstance(review_author, str) or not review_author:
                raise ValueError("slice-review author must be a GitHub actor")
            for field in ("reviewer_worker", "reviewer_session"):
                if not isinstance(review.get(field), str) or not review[field]:
                    raise ValueError(f"slice-review {field} is required")
            if review["reviewer_worker"] == checkpoint["worker"]:
                raise ValueError("slice-review must use an independent worker")
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
            if review_position >= checkpoint_position:
                raise ValueError("slice-review must precede slice-checkpoint")
            if delivery is not None:
                delivery_position = (
                    delivery["_created_at"],
                    delivery["_comment_id"],
                )
                if delivery_position >= review_position:
                    raise ValueError("slice-delivery must precede slice-review")
            if ticket in current_by_ticket:
                raise ValueError(
                    "a current slice-checkpoint must be invalidated before replacement"
                )
            internal_prerequisites = set(graph[ticket]) & set(graph)
            external_prerequisites = set(graph[ticket]) - set(graph)
            prerequisite_checkpoints = prerequisite_checkpoint_bindings(
                checkpoint.get("prerequisite_checkpoints")
            )
            if set(prerequisite_checkpoints) != external_prerequisites:
                raise ValueError(
                    "slice-checkpoint prerequisite_checkpoints must bind every "
                    "cross-batch local prerequisite"
                )
            if not internal_prerequisites <= set(current_by_ticket):
                raise ValueError(
                    "slice-checkpoint local prerequisites are not current"
                )
            detail = {
                "batch": batch,
                "checkpoint_position": checkpoint_position,
                "comment_id": checkpoint["_comment_id"],
                "commit_parents": commit_parents,
                "prerequisite_checkpoints": prerequisite_checkpoints,
                "review_position": review_position,
                "slice_commit": slice_commit,
                "starting_commit": starting_commit,
                "ticket": ticket,
            }
            validated_checkpoints[checkpoint["_comment_id"]] = detail
            current_by_ticket[ticket] = checkpoint

        for ticket, checkpoint in current_by_ticket.items():
            starting_commit = checkpoint["starting_commit"]
            slice_commit = checkpoint["slice_commit"]
            if slice_commit not in commit_shas:
                raise ValueError("slice-checkpoint commit is not in the pull request")
            if not commit_is_ancestor(starting_commit, slice_commit, commit_parents):
                raise ValueError(
                    "slice-checkpoint commit must descend from its starting_commit"
                )
            internal_prerequisites = set(graph[ticket]) & set(graph)
            for prerequisite in internal_prerequisites:
                prerequisite_commit = current_by_ticket[prerequisite]["slice_commit"]
                if not commit_is_ancestor(
                    prerequisite_commit, starting_commit, commit_parents
                ):
                    raise ValueError(
                        "slice-checkpoint starting_commit does not contain current "
                        "local prerequisite commits"
                    )

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
        "_validated_slice_checkpoints": list(validated_checkpoints.values()),
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
    for item in project_items:
        if not isinstance(item, dict):
            raise ValueError("invalid GitHub data: project item must be an object")
        if item.get("workflow_batch", True) is False:
            continue
        issue_number = positive_integer(item.get("issue_number"))
        if issue_number is None:
            continue
        item_body = item.get("body")
        if item_body is not None and not isinstance(item_body, str):
            raise ValueError("invalid GitHub data: landing batch body must be text")
        if item_body is not None:
            start_lines = STARTS_AFTER.findall(item_body)
            if len(start_lines) != 1:
                raise ValueError(
                    f"landing batch #{issue_number} must declare exactly one Starts after field"
                )
            start_value = start_lines[0].strip().strip("`")
            starts_after = {
                int(reference) for reference in ISSUE_REFERENCE.findall(start_value)
            }
            if start_value.lower() != "none" and not starts_after:
                raise ValueError(
                    f"landing batch #{issue_number} Starts after is ambiguous"
                )
            item["starts_after"] = sorted(starts_after)
        else:
            item["starts_after"] = sorted(item.get("starts_after", []))
        items_by_issue[issue_number] = item
        owners = item.get("owners")
        if isinstance(owners, list) and len(owners) > 1:
            raise ValueError(f"landing batch #{issue_number} has more than one owner")

    item_graphs: dict[int, dict[int, list[int]]] = {}
    ticket_batches: dict[int, int] = {}
    for batch, item in items_by_issue.items():
        graph = local_prerequisite_graph(item.get("child_tickets"))
        if not graph:
            continue
        item_graphs[batch] = graph
        for ticket in graph:
            if ticket in ticket_batches:
                raise ValueError(f"child ticket #{ticket} belongs to multiple batches")
            ticket_batches[ticket] = batch

    ticket_owners: dict[int, str | None] = {}
    for batch, graph in item_graphs.items():
        children = {
            child.get("number"): child
            for child in items_by_issue[batch].get("child_tickets", [])
            if isinstance(child, dict)
        }
        for ticket in graph:
            child = children.get(ticket, {})
            owner = child.get("owner")
            owners = child.get("owners")
            if owners is not None:
                if (
                    not isinstance(owners, list)
                    or len(owners) > 1
                    or not all(isinstance(value, str) and value for value in owners)
                ):
                    raise ValueError(
                        f"child ticket #{ticket} must have at most one assignee"
                    )
                observed_owner = owners[0] if owners else None
                if owner not in {None, observed_owner}:
                    raise ValueError(
                        f"child ticket #{ticket} owner does not match its assignees"
                    )
                owner = observed_owner
            if owner is not None and (not isinstance(owner, str) or not owner):
                raise ValueError(f"child ticket #{ticket} assignee is invalid")
            ticket_owners[ticket] = owner

    for batch, graph in item_graphs.items():
        open_dependencies = set(items_by_issue[batch].get("open_dependencies", []))
        for prerequisites in graph.values():
            for prerequisite in prerequisites:
                upstream_batch = ticket_batches.get(prerequisite)
                if upstream_batch is None:
                    raise ValueError(
                        f"local prerequisite ticket #{prerequisite} is not in a landing batch"
                    )
                if upstream_batch == batch:
                    continue
                upstream = items_by_issue[upstream_batch]
                if (
                    upstream_batch not in open_dependencies
                    and upstream.get("lifecycle") != "Landed"
                ):
                    raise ValueError(
                        "cross-batch local prerequisite requires landing dependency "
                        f"#{batch} lands_after #{upstream_batch}"
                    )

    for batch, item in items_by_issue.items():
        open_dependencies = set(item.get("open_dependencies", []))
        for upstream_batch in item.get("starts_after", []):
            upstream = items_by_issue.get(upstream_batch)
            if upstream is None:
                raise ValueError(
                    f"landing batch #{batch} Starts after unknown batch #{upstream_batch}"
                )
            if upstream.get("lifecycle") == "Landed":
                continue
            if upstream_batch not in open_dependencies:
                raise ValueError(
                    f"landing batch #{batch} Starts after #{upstream_batch} "
                    "is missing its native lands_after dependency"
                )

    candidates: list[dict[str, Any]] = []
    candidate_graphs: dict[int, dict[int, list[int]]] = {}
    validated_checkpoints: dict[int, dict[str, Any]] = {}
    authorized_maintainers = config.get("authorized_maintainers", [])
    if not isinstance(authorized_maintainers, list):
        raise ValueError("invalid GitHub state config: authorized_maintainers must be a list")
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
        for entry in entries:
            event = entry.get("event")
            if event in {
                "local-completion-invalidated",
                "local-completion-missing",
            } and entry.get("_author") not in authorized_maintainers:
                raise ValueError(
                    f"{event} must be authored by an authorized workflow maintainer"
                )
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
            "base_sha": pull_request.get("base_sha"),
            "batch": batch,
            "branch": pull_request.get("head_ref"),
            "closed": state == "closed",
            "delivered_tickets": delivered_tickets,
            "dependants": item.get("dependants", []),
            "draft": pull_request.get("draft"),
            "head_sha": pull_request.get("head_sha"),
            "lifecycle": item.get("lifecycle"),
            "merged": merged,
            "open_dependencies": item.get("open_dependencies", []),
            "owner": owner,
            "pull_request": number,
        }
        local_graph = item_graphs.get(batch)
        if local_graph is not None:
            candidate_graphs[batch] = local_graph
            local_state = local_slice_state(
                batch=batch,
                graph=local_graph,
                entries=entries,
                entries_by_id=entries_by_id,
                owner=owner,
                ticket_owners=ticket_owners,
                authorized_maintainers=authorized_maintainers,
                commit_shas=pull_request.get("commit_shas"),
                commit_parents=pull_request.get("commit_parents"),
            )
            for checkpoint in local_state.pop("_validated_slice_checkpoints"):
                checkpoint_id = checkpoint["comment_id"]
                if checkpoint_id in validated_checkpoints:
                    raise ValueError("slice-checkpoint comment ids must be unique")
                validated_checkpoints[checkpoint_id] = checkpoint
            candidate.update(local_state)
        rework_request = latest(entries, "rework-request")
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
                "local-completion-invalidated",
                "local-completion-missing",
                "rework-request",
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
            candidate_commit = local_completion.get("candidate_commit")
            if not isinstance(candidate_commit, str) or not candidate_commit:
                raise ValueError("local-complete candidate_commit is required")
            if local_completion.get("local_gates_passed") is not True:
                raise ValueError("local-complete requires local_gates_passed: true")
            for field in ("worker", "session"):
                if not isinstance(local_completion.get(field), str) or not local_completion[field]:
                    raise ValueError(f"local-complete {field} is required")
            review_id = referenced_comment_id(local_completion.get("review"))
            review = entries_by_id.get(review_id)
            if review is None or review.get("event") != "local-review":
                raise ValueError("local-complete must reference its local-review")
            require_unedited(review, "local-review")
            review_author = review.get("_author")
            if not isinstance(review_author, str) or not review_author:
                raise ValueError("local-review author must be a GitHub actor")
            if review.get("reviewed_by") != review_author:
                raise ValueError("local-review reviewed_by must match its author")
            for field in ("reviewer_worker", "reviewer_session"):
                if not isinstance(review.get(field), str) or not review[field]:
                    raise ValueError(f"local-review {field} is required")
            if review["reviewer_worker"] == local_completion["worker"]:
                raise ValueError("local-review must use an independent worker")
            if review.get("verdict") != "passed":
                raise ValueError("local-review verdict must be passed")
            if review.get("base_commit") != candidate.get("base_sha"):
                raise ValueError("local-review base commit does not match PR base")
            if review.get("candidate_commit") != candidate_commit:
                raise ValueError(
                    "local-review candidate commit must match local-complete"
                )
            review_position = (review["_created_at"], review["_comment_id"])
            completion_position = (
                local_completion["_created_at"],
                local_completion["_comment_id"],
            )
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

        if rework_request is not None:
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

        candidates.append(candidate)

    for candidate in candidates:
        graph = candidate_graphs.get(candidate["batch"])
        if candidate.get("local_completion") is None:
            continue
        child_tickets = items_by_issue[candidate["batch"]].get("child_tickets")
        if isinstance(child_tickets, list) and not child_tickets:
            raise ValueError("local-complete requires at least one child slice")
        if graph is None:
            continue
        candidate_completed = {
            checkpoint["ticket"]
            for checkpoint in candidate.get("slice_checkpoints", [])
        }
        if set(graph) != candidate_completed:
            raise ValueError(
                "local-complete requires a current checkpoint for every child slice"
            )

    candidates.sort(key=lambda candidate: candidate["pull_request"])
    active_checkpoints = {
        checkpoint["ticket"]: validated_checkpoints[checkpoint["comment_id"]]
        for candidate in candidates
        if not candidate["closed"] or candidate["merged"]
        for checkpoint in candidate.get("slice_checkpoints", [])
    }
    while True:
        invalid = {
            ticket
            for ticket, checkpoint in active_checkpoints.items()
            if any(
                prerequisite not in active_checkpoints
                or (
                    prerequisite in checkpoint["prerequisite_checkpoints"]
                    and checkpoint["prerequisite_checkpoints"][prerequisite]
                    != active_checkpoints[prerequisite]["comment_id"]
                )
                for prerequisite in candidate_graphs[checkpoint["batch"]][ticket]
            )
        }
        if not invalid:
            break
        for ticket in invalid:
            active_checkpoints.pop(ticket)
    for checkpoint in active_checkpoints.values():
        for prerequisite, checkpoint_id in checkpoint[
            "prerequisite_checkpoints"
        ].items():
            referenced = active_checkpoints.get(prerequisite)
            if (
                referenced is None
                or referenced["comment_id"] != checkpoint_id
            ):
                raise ValueError(
                    "prerequisite_checkpoints must reference the prerequisite "
                    "ticket's current slice-checkpoint"
                )
            if referenced["checkpoint_position"] >= checkpoint["review_position"]:
                raise ValueError(
                    "cross-batch prerequisite checkpoint must precede slice review"
                )
            if not commit_is_ancestor(
                referenced["slice_commit"],
                checkpoint["starting_commit"],
                checkpoint["commit_parents"],
            ):
                raise ValueError(
                    "stacked slice starting_commit does not contain its cross-batch "
                    "prerequisite checkpoint"
                )
    checkpoint_tickets = set(active_checkpoints)
    for candidate in candidates:
        graph = candidate_graphs.get(candidate["batch"])
        if graph is None:
            continue
        completed = {
            ticket
            for ticket, checkpoint in active_checkpoints.items()
            if checkpoint["batch"] == candidate["batch"]
        }
        candidate["slice_checkpoints"] = [
            {
                "comment_id": active_checkpoints[ticket]["comment_id"],
                "slice_commit": active_checkpoints[ticket]["slice_commit"],
                "ticket": ticket,
            }
            for ticket in sorted(completed)
        ]
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
        if (
            candidate.get("local_completion") is not None
            and not candidate["closed"]
            and not candidate["merged"]
            and set(graph) != completed
        ):
            candidate["local_completion_invalid_reason"] = (
                "one or more child slice checkpoints are no longer current"
            )
    candidate_batches = {candidate["batch"] for candidate in candidates}
    active_batches = {
        batch
        for batch, item in items_by_issue.items()
        if item.get("workflow_batch", True) is not False
        and isinstance(item.get("owner"), str)
        and item.get("lifecycle") != "Landed"
    }
    ticket_surfaces: dict[int, set[str]] = {}
    for batch, graph in item_graphs.items():
        item = items_by_issue[batch]
        children = {
            child.get("number"): child
            for child in item.get("child_tickets", [])
            if isinstance(child, dict)
        }
        batch_surfaces = set(item.get("conflict_surfaces", []))
        for ticket in graph:
            child = children.get(ticket, {})
            surfaces = child.get("conflict_surfaces", [])
            ticket_surfaces[ticket] = set(surfaces) or batch_surfaces

    def must_not_overlap(first: int, second: int) -> bool:
        return (
            second in items_by_issue[first].get("must_not_overlap", [])
            or first in items_by_issue[second].get("must_not_overlap", [])
        )

    candidates_by_batch = {
        candidate["batch"]: candidate
        for candidate in candidates
        if not candidate["closed"] and not candidate["merged"]
    }

    def active_work_surfaces(batch: int) -> set[str]:
        candidate = candidates_by_batch.get(batch)
        frontier = candidate.get("local_frontier", []) if candidate else []
        if frontier:
            return {
                surface
                for ticket in frontier
                for surface in ticket_surfaces.get(ticket, set())
            }
        return set(items_by_issue[batch].get("conflict_surfaces", []))

    def conflicting_batches(batch: int, ticket: int) -> list[int]:
        surfaces = ticket_surfaces.get(
            ticket, set(items_by_issue[batch].get("conflict_surfaces", []))
        )
        return sorted(
            other
            for other in active_batches
            if other != batch
            and (
                must_not_overlap(batch, other)
                or surfaces
                & active_work_surfaces(other)
            )
        )

    ready_batches: list[dict[str, Any]] = []
    blocked_batches: list[dict[str, Any]] = []
    ready_slices: list[dict[str, Any]] = []
    for candidate in candidates:
        if (
            candidate["closed"]
            or candidate["merged"]
            or candidate.get("hold", False)
            or not isinstance(candidate.get("owner"), str)
            or candidate.get("lifecycle")
            in {"Locally complete", "In PR", "Landed"}
        ):
            continue
        frontier = candidate.get("local_frontier", [])
        available_tickets = [
            ticket for ticket in frontier if ticket_owners.get(ticket) is None
        ]
        safe_tickets = [
            ticket
            for ticket in available_tickets
            if not conflicting_batches(candidate["batch"], ticket)
        ]
        ready_slices.extend(
            {
                "batch": candidate["batch"],
                "pull_request": candidate["pull_request"],
                "ticket": ticket,
            }
            for ticket in safe_tickets
        )
        if available_tickets and not safe_tickets:
            blocked_batches.append(
                {
                    "batch": candidate["batch"],
                    "conflicting_batches": sorted(
                        {
                            conflict
                            for ticket in frontier
                            for conflict in conflicting_batches(
                                candidate["batch"], ticket
                            )
                        }
                    ),
                    "missing_checkpoints": [],
                }
            )
    for batch, graph in sorted(item_graphs.items()):
        item = items_by_issue[batch]
        if (
            batch in candidate_batches
            or item.get("owner") is not None
            or item.get("lifecycle") != "Planned"
        ):
            continue
        starting_slices = sorted(
            ticket
            for ticket, prerequisites in graph.items()
            if set(prerequisites) <= checkpoint_tickets
        )
        safe_starting_slices = [
            ticket
            for ticket in starting_slices
            if not conflicting_batches(batch, ticket)
        ]
        conflicts = sorted(
            {
                conflict
                for ticket in starting_slices
                for conflict in conflicting_batches(batch, ticket)
            }
        )
        unresolved_start_dependencies = sorted(
            set(item.get("starts_after", []))
            & set(item.get("open_dependencies", []))
        )
        if safe_starting_slices and not unresolved_start_dependencies:
            ready_batches.append(
                {"batch": batch, "starting_slices": safe_starting_slices}
            )
            continue
        blocked = {
            "batch": batch,
            "conflicting_batches": conflicts,
            "missing_checkpoints": sorted(
                {
                    prerequisite
                    for prerequisites in graph.values()
                    for prerequisite in prerequisites
                    if prerequisite not in checkpoint_tickets
                }
            ),
        }
        if unresolved_start_dependencies:
            blocked["start_dependencies"] = unresolved_start_dependencies
        blocked_batches.append(blocked)
    blocked_batches.sort(key=lambda blocked: blocked["batch"])
    return {
        "candidates": candidates,
        "execution_frontier": {
            "blocked_batches": blocked_batches,
            "ready_batches": ready_batches,
            "ready_slices": ready_slices,
        },
        "repository": {"name": config.get("repository")},
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
              body
              assignees(first: 10) { nodes { login } }
              labels(first: 50) {
                nodes { name }
                pageInfo { hasNextPage }
              }
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
            label_connection = content.get("labels") or {}
            if (label_connection.get("pageInfo") or {}).get("hasNextPage"):
                raise ValueError(
                    f"landing batch #{issue_number} label pagination is truncated"
                )
            labels = label_connection.get("nodes", [])
            workflow_batch = any(
                isinstance(label, dict)
                and label.get("name") == "BATCH"
                for label in labels
            )
            conflict_surfaces = conflict_surface_labels(labels)
            issue_body = content.get("body")
            if (
                workflow_batch
                and (
                    not isinstance(issue_body, str)
                    or MUST_NOT_OVERLAP.search(issue_body) is None
                )
            ):
                raise ValueError(
                    f"landing batch #{issue_number} is missing Must not overlap"
                )
            items.append(
                {
                    "issue_number": issue_number,
                    "body": content.get("body") or "",
                    "conflict_surfaces": conflict_surfaces,
                    "lifecycle": fields.get(field_names["lifecycle"]),
                    "must_not_overlap": (
                        issue_relation_numbers(issue_body, MUST_NOT_OVERLAP)
                        if workflow_batch
                        else []
                    ),
                    "owner": owner,
                    "owners": [assignee.get("login") for assignee in assignees],
                    "workflow_batch": workflow_batch,
                }
            )
        page_info = connection.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            workflow_batches = {
                item["issue_number"]
                for item in items
                if item["workflow_batch"]
            }
            for item in items:
                if not item["workflow_batch"]:
                    continue
                for target in item["must_not_overlap"]:
                    if target == item["issue_number"]:
                        raise ValueError(
                            f"landing batch #{target} cannot reference itself in "
                            "Must not overlap"
                        )
                    if target not in workflow_batches:
                        raise ValueError(
                            f"Must not overlap references unknown landing batch #{target}"
                        )
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
        raise ValueError("GitHub state identity is still Pending GitHub setup")
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    repository = request_json(token, f"{api}/repos/{repository_name}")
    if not isinstance(repository, dict):
        raise ValueError("GitHub repository response must be an object")
    pulls = rest_pages(
        token,
        api,
        f"/repos/{repository_name}/pulls?state=all",
    )
    field_names = config.get("project_fields")
    if not isinstance(field_names, dict) or not isinstance(
        field_names.get("lifecycle"), str
    ):
        raise ValueError("GitHub state project_fields are not configured")
    items = project_items(token, api, project_id, field_names)
    for item in items:
        batch = item["issue_number"]
        item["comments"] = rest_pages(
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
            {
                "body": issue.get("body") or "",
                "conflict_surfaces": conflict_surface_labels(issue.get("labels")),
                "number": issue["number"],
                "owner": (
                    issue["assignees"][0].get("login")
                    if isinstance(issue.get("assignees"), list)
                    and len(issue["assignees"]) == 1
                    and isinstance(issue["assignees"][0], dict)
                    else None
                ),
                "owners": [
                    assignee.get("login")
                    for assignee in issue.get("assignees", [])
                    if isinstance(assignee, dict)
                ],
            }
            for issue in child_issues
            if positive_integer(issue.get("number")) is not None
        ]
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
        pull_commits = rest_pages(
            token,
            api,
            f"/repos/{repository_name}/pulls/{number}/commits?",
        )
        normalized_pulls.append(
            {
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
        "repository": {"name": repository.get("full_name")},
    }


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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = read_object(args.config, "GitHub state config")
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
