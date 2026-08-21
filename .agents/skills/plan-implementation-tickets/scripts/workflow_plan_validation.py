"""Validate repo workflow planning and implementation publication previews."""

from __future__ import annotations

import re
from typing import Any

MUTABLE_TRACKER_FIELDS = (
    "status",
    "assignee",
    "owner",
    "label",
    "labels",
    "ready_for_agent",
    "queue_position",
    "review_class",
    "review_level",
    "provisional_wave",
)
IMPLEMENTATION_PLAN_FIELDS = {
    "stage",
    "artifact_kind",
    "effort",
    "effort_slug",
    "success_condition",
    "open_decisions",
    "streams",
    "tickets",
    "landing_batches",
}
STREAM_FIELDS = {"id", "name", "scope", "conflict_surfaces"}
IMPLEMENTATION_TICKET_FIELDS = {
    "id",
    "title",
    "problem",
    "desired_outcome",
    "parent_plan",
    "starting_context",
    "local_after",
    "stream",
    "landing_batch",
    "conflict_surfaces",
    "acceptance_criteria",
    "out_of_scope",
    "documentation_impact",
    "operational_impact",
}
ACCEPTANCE_CRITERION_FIELDS = {"criterion", "proving_method"}
LANDING_BATCH_FIELDS = {
    "id",
    "title",
    "problem",
    "desired_outcome",
    "batch_boundary",
    "flow_evidence",
    "split_reason",
    "parent_plan",
    "stream",
    "tickets",
    "lands_after",
    "conflict_surfaces",
    "safe_parallel_with",
    "must_not_overlap",
    "acceptance_criteria",
    "out_of_scope",
    "documentation_impact",
    "operational_impact",
}
PLANNING_PLAN_FIELDS = {
    "stage",
    "artifact_kind",
    "effort",
    "effort_slug",
    "success_condition",
    "notes",
    "planning_tickets",
    "not_yet_specified",
    "out_of_scope",
}
PLANNING_TICKET_FIELDS = {"id", "title", "type", "depends_on", "question"}
def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def string_list(value: Any, *, require_nonempty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (bool(value) or not require_nonempty)
        and all(nonempty_string(item) for item in value)
    )


def placeholder_errors(value: Any, path: str = "result") -> list[str]:
    errors: list[str] = []
    if isinstance(value, str) and value.strip().lower().startswith(
        ("replace with", "replace-with", "copy the complete")
    ):
        errors.append(f"placeholder value remains at {path}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(placeholder_errors(item, f"{path}[{index}]"))
    elif isinstance(value, dict):
        for key, item in value.items():
            errors.extend(placeholder_errors(item, f"{path}.{key}"))
    return errors


def schema_errors(value: dict[str, Any], allowed: set[str], context: str) -> list[str]:
    unexpected = sorted(set(value) - allowed)
    return [f"{context} contains unexpected field {field}" for field in unexpected]


def acceptance_criteria_errors(value: Any, context: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, list) or not value:
        return [f"{context} acceptance_criteria must be non-empty"]
    for index, criterion in enumerate(value):
        criterion_context = f"{context} acceptance_criteria[{index}]"
        if not isinstance(criterion, dict):
            errors.append(f"{criterion_context} must be an object")
            continue
        errors.extend(
            schema_errors(
                criterion,
                ACCEPTANCE_CRITERION_FIELDS,
                criterion_context,
            )
        )
        for field in ("criterion", "proving_method"):
            if not nonempty_string(criterion.get(field)):
                errors.append(f"{criterion_context} missing {field}")
    return errors


def relation_targets(
    value: Any,
    *,
    target_field: str,
    explanation_field: str,
    context: str,
    errors: list[str],
) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{context} must be a list")
        return []
    targets: list[str] = []
    for index, relation in enumerate(value):
        if not isinstance(relation, dict):
            errors.append(f"{context}[{index}] must be an object")
            continue
        errors.extend(
            schema_errors(
                relation,
                {target_field, explanation_field},
                f"{context}[{index}]",
            )
        )
        target = relation.get(target_field)
        explanation = relation.get(explanation_field)
        if not nonempty_string(target):
            errors.append(f"{context}[{index}] missing {target_field}")
            continue
        if target in targets:
            errors.append(f"{context} repeats {target_field} {target}")
        else:
            targets.append(target)
        if not nonempty_string(explanation):
            errors.append(f"{context} missing {explanation_field}")
    return targets


def relation_cycle(relations: dict[str, list[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(item_id: str) -> bool:
        if item_id in visiting:
            return True
        if item_id in visited:
            return False
        visiting.add(item_id)
        for dependency in relations.get(item_id, []):
            if dependency in relations and visit(dependency):
                return True
        visiting.remove(item_id)
        visited.add(item_id)
        return False

    return any(visit(item_id) for item_id in relations)


def relation_reachability(relations: dict[str, list[str]]) -> dict[str, set[str]]:
    reachable: dict[str, set[str]] = {}
    for item_id in relations:
        found: set[str] = set()
        pending = list(relations.get(item_id, []))
        while pending:
            dependency = pending.pop()
            if dependency in found or dependency not in relations:
                continue
            found.add(dependency)
            pending.extend(relations.get(dependency, []))
        reachable[item_id] = found
    return reachable


def validation_errors(plan: dict[str, Any]) -> list[str]:
    errors = placeholder_errors(plan)
    errors.extend(schema_errors(plan, IMPLEMENTATION_PLAN_FIELDS, "plan"))
    if plan.get("artifact_kind") != "github-publication-preview":
        errors.append("artifact_kind must be github-publication-preview")
    for field in ("effort", "effort_slug", "success_condition"):
        if not nonempty_string(plan.get(field)):
            errors.append(f"{field} must be a non-empty string")
    effort_slug = plan.get("effort_slug")
    if nonempty_string(effort_slug) and not re.fullmatch(
        r"[a-z0-9][a-z0-9-]*", effort_slug
    ):
        errors.append("effort_slug must contain lowercase letters, digits, or hyphens")

    open_decisions = plan.get("open_decisions")
    if not isinstance(open_decisions, list):
        errors.append("open_decisions must be a list")
    elif open_decisions:
        errors.append("open_decisions must be empty before ticket planning")
    stream_items = plan.get("streams")
    ticket_items = plan.get("tickets")
    batch_items = plan.get("landing_batches")
    if not isinstance(stream_items, list) or not stream_items:
        errors.append("streams must be a non-empty list")
        stream_items = []
    if not isinstance(ticket_items, list) or not ticket_items:
        errors.append("tickets must be a non-empty list")
        ticket_items = []
    if not isinstance(batch_items, list) or not batch_items:
        errors.append("landing_batches must be a non-empty list")
        batch_items = []

    streams: dict[str, dict[str, Any]] = {}
    for index, stream in enumerate(stream_items):
        if not isinstance(stream, dict):
            errors.append(f"streams[{index}] must be an object")
            continue
        stream_id = stream.get("id")
        if not nonempty_string(stream_id):
            errors.append(f"streams[{index}].id must be a non-empty string")
            continue
        if stream_id in streams:
            errors.append(f"duplicate stream id: {stream_id}")
        streams[stream_id] = stream
        errors.extend(schema_errors(stream, STREAM_FIELDS, f"stream {stream_id}"))
        if not nonempty_string(stream.get("name")):
            errors.append(f"stream {stream_id} missing name")
        for field in ("scope", "conflict_surfaces"):
            if not string_list(stream.get(field), require_nonempty=True):
                errors.append(f"stream {stream_id} {field} must be non-empty")

    tickets: dict[str, dict[str, Any]] = {}
    ticket_local_prerequisites: dict[str, list[str]] = {}
    for index, ticket in enumerate(ticket_items):
        if not isinstance(ticket, dict):
            errors.append(f"tickets[{index}] must be an object")
            continue
        ticket_id = ticket.get("id")
        if not nonempty_string(ticket_id):
            errors.append(f"tickets[{index}].id must be a non-empty string")
            continue
        if ticket_id in tickets:
            errors.append(f"duplicate ticket id: {ticket_id}")
        tickets[ticket_id] = ticket
        errors.extend(
            schema_errors(
                ticket, IMPLEMENTATION_TICKET_FIELDS, f"ticket {ticket_id}"
            )
        )
        for field in (
            "title",
            "problem",
            "desired_outcome",
            "parent_plan",
            "stream",
            "landing_batch",
        ):
            if not nonempty_string(ticket.get(field)):
                errors.append(f"ticket {ticket_id} missing {field}")
        for field in ("documentation_impact", "operational_impact"):
            if not nonempty_string(ticket.get(field)):
                errors.append(f"ticket {ticket_id} missing {field}")
        for field in MUTABLE_TRACKER_FIELDS:
            if field in ticket:
                errors.append(
                    f"ticket {ticket_id} must not contain mutable tracker field {field}"
                )
        ticket_local_prerequisites[ticket_id] = relation_targets(
            ticket.get("local_after"),
            target_field="ticket",
            explanation_field="reason",
            context=f"ticket {ticket_id} local prerequisite",
            errors=errors,
        )
        for field in ("starting_context", "conflict_surfaces", "out_of_scope"):
            if not string_list(ticket.get(field), require_nonempty=True):
                errors.append(f"ticket {ticket_id} {field} must be non-empty")
        errors.extend(
            acceptance_criteria_errors(
                ticket.get("acceptance_criteria"), f"ticket {ticket_id}"
            )
        )
        if nonempty_string(ticket.get("stream")) and ticket["stream"] not in streams:
            errors.append(f"ticket {ticket_id} references unknown stream")

    for ticket_id, prerequisites in ticket_local_prerequisites.items():
        for prerequisite in prerequisites:
            if prerequisite not in tickets:
                errors.append(
                    f"ticket {ticket_id} references unknown local prerequisite {prerequisite}"
                )
    if tickets and relation_cycle(ticket_local_prerequisites):
        errors.append("ticket local prerequisite graph contains a cycle")

    batches: dict[str, dict[str, Any]] = {}
    batch_landing_prerequisites: dict[str, list[str]] = {}
    batch_parallel: dict[str, list[str]] = {}
    batch_serial: dict[str, list[str]] = {}
    membership: dict[str, list[str]] = {ticket_id: [] for ticket_id in tickets}
    for index, batch in enumerate(batch_items):
        if not isinstance(batch, dict):
            errors.append(f"landing_batches[{index}] must be an object")
            continue
        batch_id = batch.get("id")
        if not nonempty_string(batch_id):
            errors.append(f"landing_batches[{index}].id must be a non-empty string")
            continue
        if batch_id in batches:
            errors.append(f"duplicate landing batch id: {batch_id}")
        batches[batch_id] = batch
        errors.extend(
            schema_errors(batch, LANDING_BATCH_FIELDS, f"landing batch {batch_id}")
        )
        for field in MUTABLE_TRACKER_FIELDS:
            if field in batch:
                errors.append(
                    f"landing batch {batch_id} must not contain mutable tracker field {field}"
                )
        stream_id = batch.get("stream")
        if not nonempty_string(stream_id) or stream_id not in streams:
            errors.append(f"landing batch {batch_id} references unknown stream")
        for field in (
            "title",
            "problem",
            "desired_outcome",
            "batch_boundary",
            "flow_evidence",
            "parent_plan",
            "documentation_impact",
            "operational_impact",
        ):
            if not nonempty_string(batch.get(field)):
                errors.append(f"landing batch {batch_id} missing {field}")
        if len(batch_items) > 1 and not nonempty_string(batch.get("split_reason")):
            errors.append(f"landing batch {batch_id} missing split_reason")
        elif "split_reason" in batch and not nonempty_string(batch.get("split_reason")):
            errors.append(f"landing batch {batch_id} missing split_reason")
        members = batch.get("tickets")
        if not string_list(members, require_nonempty=True):
            errors.append(f"landing batch {batch_id} tickets must be non-empty")
            members = []
        for field in ("conflict_surfaces", "out_of_scope"):
            if not string_list(batch.get(field), require_nonempty=True):
                errors.append(f"landing batch {batch_id} {field} must be non-empty")
        errors.extend(
            acceptance_criteria_errors(
                batch.get("acceptance_criteria"), f"landing batch {batch_id}"
            )
        )
        batch_landing_prerequisites[batch_id] = relation_targets(
            batch.get("lands_after"),
            target_field="batch",
            explanation_field="reason",
            context=f"landing batch {batch_id} landing prerequisite",
            errors=errors,
        )
        batch_parallel[batch_id] = relation_targets(
            batch.get("safe_parallel_with"),
            target_field="batch",
            explanation_field="evidence",
            context=f"landing batch {batch_id} safe_parallel_with",
            errors=errors,
        )
        batch_serial[batch_id] = relation_targets(
            batch.get("must_not_overlap"),
            target_field="batch",
            explanation_field="reason",
            context=f"landing batch {batch_id} must_not_overlap",
            errors=errors,
        )
        for relation_name, targets in (
            ("lands_after", batch_landing_prerequisites[batch_id]),
            ("safe_parallel_with", batch_parallel[batch_id]),
            ("must_not_overlap", batch_serial[batch_id]),
        ):
            if batch_id in targets:
                errors.append(
                    f"landing batch {batch_id} must not reference itself in {relation_name}"
                )
        for ticket_id in members:
            if ticket_id not in tickets:
                errors.append(
                    f"landing batch {batch_id} references unknown ticket {ticket_id}"
                )
                continue
            membership[ticket_id].append(batch_id)
            if tickets[ticket_id].get("stream") != stream_id:
                errors.append(
                    f"landing batch {batch_id} mixes ticket {ticket_id} from another stream"
                )
            ticket_surfaces = tickets[ticket_id].get("conflict_surfaces")
            batch_surfaces = batch.get("conflict_surfaces")
            if isinstance(ticket_surfaces, list) and isinstance(batch_surfaces, list):
                if set(ticket_surfaces) - set(batch_surfaces):
                    errors.append(
                        f"landing batch {batch_id} omits ticket {ticket_id} conflict surfaces"
                    )

    for ticket_id, ticket in tickets.items():
        planned_batch = ticket.get("landing_batch")
        if nonempty_string(planned_batch) and planned_batch not in batches:
            errors.append(f"ticket {ticket_id} references unknown landing_batch")
        if membership[ticket_id] != [planned_batch]:
            errors.append(
                f"ticket {ticket_id} must appear exactly once in its landing_batch"
            )

    batch_reachability = relation_reachability(batch_landing_prerequisites)
    for batch_id, batch in batches.items():
        for dependency in batch_landing_prerequisites.get(batch_id, []):
            if dependency not in batches:
                errors.append(
                    f"landing batch {batch_id} references unknown landing prerequisite {dependency}"
                )
        for other_id in batch_parallel.get(batch_id, []):
            other = batches.get(other_id)
            if other is None:
                errors.append(
                    f"landing batch {batch_id} references unknown safe_parallel_with {other_id}"
                )
                continue
            if batch_id not in batch_parallel.get(other_id, []):
                errors.append(
                    f"landing batches {batch_id} and {other_id} must declare "
                    "safe parallelism reciprocally"
                )
            overlap = set(batch.get("conflict_surfaces", [])) & set(
                other.get("conflict_surfaces", [])
            )
            if overlap:
                errors.append(
                    f"landing batches {batch_id} and {other_id} claim safe parallelism "
                    "with overlapping conflict surfaces"
                )
            if other_id in batch_reachability.get(
                batch_id, set()
            ) or batch_id in batch_reachability.get(other_id, set()):
                errors.append(
                    f"dependent landing batches {batch_id} and {other_id} "
                    "cannot be safe_parallel_with"
                )
        for other_id in batch_serial.get(batch_id, []):
            if other_id not in batches:
                errors.append(
                    f"landing batch {batch_id} references unknown must_not_overlap {other_id}"
                )
            elif batch_id not in batch_serial.get(other_id, []):
                errors.append(
                    f"landing batches {batch_id} and {other_id} must declare "
                    "must_not_overlap reciprocally"
                )
    if batches and relation_cycle(batch_landing_prerequisites):
        errors.append("landing batch landing-prerequisite graph contains a cycle")

    batch_ids = sorted(batches)
    for index, first_id in enumerate(batch_ids):
        for second_id in batch_ids[index + 1 :]:
            dependent = second_id in batch_reachability.get(
                first_id, set()
            ) or first_id in batch_reachability.get(second_id, set())
            parallel = second_id in batch_parallel.get(
                first_id, []
            ) or first_id in batch_parallel.get(second_id, [])
            serialized = second_id in batch_serial.get(
                first_id, []
            ) or first_id in batch_serial.get(second_id, [])
            classifications = sum((dependent, parallel, serialized))
            if classifications == 0:
                errors.append(
                    f"landing plan must classify {first_id} and {second_id} as "
                    "dependent, safe_parallel_with, or must_not_overlap"
                )
            elif classifications > 1:
                errors.append(
                    f"landing plan gives contradictory classifications for "
                    f"{first_id} and {second_id}"
                )

    for ticket_id, ticket in tickets.items():
        ticket_batch = ticket.get("landing_batch")
        for prerequisite_id in ticket_local_prerequisites.get(ticket_id, []):
            if prerequisite_id not in tickets:
                continue
            prerequisite_batch = tickets[prerequisite_id].get("landing_batch")
            if (
                ticket_batch in batches
                and prerequisite_batch != ticket_batch
                and prerequisite_batch
                not in batch_reachability.get(ticket_batch, set())
            ):
                errors.append(
                    f"ticket {ticket_id} cross-batch local prerequisite "
                    f"{prerequisite_id} requires {ticket_batch} to land after "
                    f"{prerequisite_batch}"
                )
    for batch_id, batch in batches.items():
        members = batch.get("tickets")
        if not isinstance(members, list):
            continue
        if members and not any(
            not any(
                tickets.get(prerequisite_id, {}).get("landing_batch") == batch_id
                for prerequisite_id in ticket_local_prerequisites.get(ticket_id, [])
            )
            for ticket_id in members
            if ticket_id in tickets
        ):
            errors.append(
                f"landing batch {batch_id} has no locally executable starting slice"
            )
    return errors


def planning_validation_errors(plan: dict[str, Any]) -> list[str]:
    errors = placeholder_errors(plan)
    errors.extend(schema_errors(plan, PLANNING_PLAN_FIELDS, "plan"))
    if plan.get("artifact_kind") != "github-publication-preview":
        errors.append("artifact_kind must be github-publication-preview")
    for field in ("effort", "effort_slug", "success_condition"):
        if not nonempty_string(plan.get(field)):
            errors.append(f"{field} must be a non-empty string")
    effort_slug = plan.get("effort_slug")
    if nonempty_string(effort_slug) and not re.fullmatch(
        r"[a-z0-9][a-z0-9-]*", effort_slug
    ):
        errors.append("effort_slug must contain lowercase letters, digits, or hyphens")
    for field in ("notes", "not_yet_specified", "out_of_scope"):
        if not string_list(plan.get(field), require_nonempty=field == "notes"):
            errors.append(f"{field} must contain only non-empty strings")

    items = plan.get("planning_tickets")
    if not isinstance(items, list) or not items:
        return errors + ["planning_tickets must be a non-empty list"]
    tickets: dict[str, dict[str, Any]] = {}
    planning_dependencies: dict[str, list[str]] = {}
    for index, ticket in enumerate(items):
        if not isinstance(ticket, dict):
            errors.append(f"planning_tickets[{index}] must be an object")
            continue
        ticket_id = ticket.get("id")
        if not nonempty_string(ticket_id):
            errors.append(f"planning_tickets[{index}].id must be a non-empty string")
            continue
        if ticket_id in tickets:
            errors.append(f"duplicate planning ticket id: {ticket_id}")
        tickets[ticket_id] = ticket
        errors.extend(
            schema_errors(
                ticket, PLANNING_TICKET_FIELDS, f"planning ticket {ticket_id}"
            )
        )
        for field in ("title", "question"):
            if not nonempty_string(ticket.get(field)):
                errors.append(f"planning ticket {ticket_id} missing {field}")
        if ticket.get("type") not in {"research", "prototype", "grilling", "task"}:
            errors.append(f"planning ticket {ticket_id} has unknown type")
        planning_dependencies[ticket_id] = relation_targets(
            ticket.get("depends_on"),
            target_field="ticket",
            explanation_field="reason",
            context=f"planning ticket {ticket_id} dependency",
            errors=errors,
        )
        for field in MUTABLE_TRACKER_FIELDS:
            if field in ticket:
                errors.append(
                    f"planning ticket {ticket_id} must not contain mutable tracker field {field}"
                )
    for ticket_id, dependencies in planning_dependencies.items():
        for dependency in dependencies:
            if dependency not in tickets:
                errors.append(
                    f"planning ticket {ticket_id} references unknown dependency {dependency}"
                )
    if tickets and relation_cycle(planning_dependencies):
        errors.append("planning ticket graph contains a dependency cycle")
    return errors


def publication_preview_validation_errors(plan: dict[str, Any]) -> list[str]:
    """Validate a publication preview according to its declared stage."""
    stage = plan.get("stage")
    if stage == "implementation":
        return validation_errors(plan)
    if stage == "planning":
        return planning_validation_errors(plan)
    return ["stage must be planning or implementation"]
