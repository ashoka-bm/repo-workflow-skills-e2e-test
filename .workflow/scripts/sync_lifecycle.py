#!/usr/bin/env python3
"""Synchronize a landing batch's GitHub Project Lifecycle from trusted events."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from queue_landing import (
    GitHub,
    LANDING_BATCH_PATTERN,
    QueueLandingError,
    VALIDATED_LABEL,
    body,
    comment_record,
    configured_base_branch,
    enforce_landing_order,
    label_names as api_label_names,
    landing_pulls,
    merged_batches,
    one_landing_batch,
    stack_dependencies,
    validate_assignment,
    validated_completion_barriers,
    validate_landing_evidence,
)


REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
BATCH_LABEL = "BATCH"
CLAIM_LABELS = frozenset({"PLAN", BATCH_LABEL, "TICKET"})
QUEUED_LABEL = "workflow:queued"
DEQUEUED_LABEL = "workflow:dequeued"
MERGIFY_ACTOR = "mergify[bot]"
LIFECYCLE_VALUES = (
    "Planned",
    "Building",
    "Locally complete",
    "In PR",
    "Landed",
)


class LifecycleError(RuntimeError):
    pass


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LifecycleError(f"cannot read {label}: {error}") from error
    if not isinstance(value, dict):
        raise LifecycleError(f"{label} must be a JSON object")
    return value


def validated_url(value: str, label: str) -> str:
    parsed = urllib.parse.urlparse(value)
    is_loopback = parsed.hostname in {"127.0.0.1", "::1", "localhost"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and is_loopback):
        raise LifecycleError(f"{label} must use HTTPS")
    if not parsed.netloc or parsed.query or parsed.fragment:
        raise LifecycleError(f"{label} is invalid")
    return value


class GraphQL:
    def __init__(self, url: str, token: str) -> None:
        self.url = validated_url(url, "GitHub GraphQL URL")
        self.token = token

    def execute(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.url,
            data=json.dumps({"query": query, "variables": variables}).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "repository-workflow-lifecycle",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read())
        except urllib.error.HTTPError as error:
            raise LifecycleError(
                f"GitHub GraphQL request failed with HTTP {error.code}"
            ) from error
        except urllib.error.URLError as error:
            raise LifecycleError(
                f"GitHub GraphQL request failed: {error.reason}"
            ) from error
        except json.JSONDecodeError as error:
            raise LifecycleError("GitHub GraphQL returned invalid JSON") from error
        if not isinstance(payload, dict):
            raise LifecycleError("GitHub GraphQL returned an invalid response")
        errors = payload.get("errors")
        if errors:
            raise LifecycleError(f"GitHub GraphQL rejected the request: {errors}")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise LifecycleError("GitHub GraphQL response is missing data")
        return data


@dataclass(frozen=True)
class ProjectIssue:
    content_id: str
    item_id: str | None
    current: str | None
    labels: frozenset[str]


@dataclass(frozen=True)
class Transition:
    number: int
    target: str
    allowed_previous: frozenset[str | None]
    retire_pull: int | None = None


class ProjectLifecycle:
    def __init__(
        self,
        graphql: GraphQL,
        repository: str,
        project_id: str,
        field_name: str,
    ) -> None:
        self.graphql = graphql
        self.owner, self.repository = repository.split("/", 1)
        self.project_id = project_id
        self.field_name = field_name

    def issue(self, number: int) -> ProjectIssue:
        data = self.graphql.execute(
            """
            query WorkflowIssue($owner: String!, $repository: String!, $number: Int!, $field: String!) {
              repository(owner: $owner, name: $repository) {
                issue(number: $number) {
                  id
                  number
                  labels(first: 100) {
                    nodes { name }
                    pageInfo { hasNextPage }
                  }
                  projectItems(first: 100) {
                    nodes {
                      id
                      project { id }
                      fieldValueByName(name: $field) {
                        ... on ProjectV2ItemFieldSingleSelectValue { name }
                      }
                    }
                    pageInfo { hasNextPage }
                  }
                }
              }
            }
            """,
            {
                "owner": self.owner,
                "repository": self.repository,
                "number": number,
                "field": self.field_name,
            },
        )
        repository = data.get("repository")
        issue = repository.get("issue") if isinstance(repository, dict) else None
        if not isinstance(issue, dict) or not isinstance(issue.get("id"), str):
            raise LifecycleError(f"landing batch issue #{number} was not found")
        label_data = issue.get("labels")
        label_nodes = label_data.get("nodes") if isinstance(label_data, dict) else None
        if not isinstance(label_nodes, list):
            raise LifecycleError("GitHub returned invalid issue labels")
        label_page = label_data.get("pageInfo") if isinstance(label_data, dict) else None
        if not isinstance(label_page, dict) or label_page.get("hasNextPage") is not False:
            raise LifecycleError("issue has too many labels to verify safely")
        labels = frozenset(
            node["name"]
            for node in label_nodes
            if isinstance(node, dict) and isinstance(node.get("name"), str)
        )
        items = issue.get("projectItems")
        nodes = items.get("nodes") if isinstance(items, dict) else None
        if not isinstance(nodes, list):
            raise LifecycleError("GitHub returned invalid Project items")
        item_page = items.get("pageInfo") if isinstance(items, dict) else None
        if not isinstance(item_page, dict) or item_page.get("hasNextPage") is not False:
            raise LifecycleError("issue has too many Project items to verify safely")
        matching = [
            node
            for node in nodes
            if isinstance(node, dict)
            and isinstance(node.get("project"), dict)
            and node["project"].get("id") == self.project_id
        ]
        if len(matching) > 1:
            raise LifecycleError("landing batch appears more than once in the Project")
        item = matching[0] if matching else None
        field_value = item.get("fieldValueByName") if item else None
        current = field_value.get("name") if isinstance(field_value, dict) else None
        if current is not None and current not in LIFECYCLE_VALUES:
            raise LifecycleError(f"unexpected Lifecycle value: {current}")
        return ProjectIssue(
            content_id=issue["id"],
            item_id=item.get("id") if isinstance(item, dict) else None,
            current=current,
            labels=labels,
        )

    def field(self) -> tuple[str, dict[str, str]]:
        data = self.graphql.execute(
            """
            query WorkflowProject($project: ID!, $field: String!) {
              node(id: $project) {
                ... on ProjectV2 {
                  field(name: $field) {
                    ... on ProjectV2SingleSelectField {
                      id
                      options { id name }
                    }
                  }
                }
              }
            }
            """,
            {"project": self.project_id, "field": self.field_name},
        )
        node = data.get("node")
        field = node.get("field") if isinstance(node, dict) else None
        if not isinstance(field, dict) or not isinstance(field.get("id"), str):
            raise LifecycleError(f"Project field {self.field_name!r} was not found")
        options = field.get("options")
        if not isinstance(options, list):
            raise LifecycleError("Lifecycle field options are invalid")
        by_name = {
            option["name"]: option["id"]
            for option in options
            if isinstance(option, dict)
            and isinstance(option.get("name"), str)
            and isinstance(option.get("id"), str)
        }
        missing = [value for value in LIFECYCLE_VALUES if value not in by_name]
        if missing:
            raise LifecycleError(f"Lifecycle field is missing options: {', '.join(missing)}")
        return field["id"], by_name

    def add_item(self, content_id: str) -> str:
        data = self.graphql.execute(
            """
            mutation AddLifecycleItem($project: ID!, $content: ID!) {
              addProjectV2ItemById(input: {projectId: $project, contentId: $content}) {
                item { id }
              }
            }
            """,
            {"project": self.project_id, "content": content_id},
        )
        result = data.get("addProjectV2ItemById")
        item = result.get("item") if isinstance(result, dict) else None
        item_id = item.get("id") if isinstance(item, dict) else None
        if not isinstance(item_id, str):
            raise LifecycleError("GitHub did not add the landing batch to the Project")
        return item_id

    def update(self, item_id: str, field_id: str, option_id: str) -> None:
        self.graphql.execute(
            """
            mutation UpdateLifecycle($project: ID!, $item: ID!, $field: ID!, $option: String!) {
              updateProjectV2ItemFieldValue(input: {
                projectId: $project,
                itemId: $item,
                fieldId: $field,
                value: {singleSelectOptionId: $option}
              }) {
                projectV2Item { id }
              }
            }
            """,
            {
                "project": self.project_id,
                "item": item_id,
                "field": field_id,
                "option": option_id,
            },
        )

    def set(self, transition: Transition) -> tuple[str | None, str]:
        number = transition.number
        target = transition.target
        issue = self.issue(number)
        if BATCH_LABEL not in issue.labels:
            raise LifecycleError(f"issue #{number} is not a {BATCH_LABEL} landing batch")
        if issue.current == target:
            return issue.current, target
        if issue.current not in transition.allowed_previous:
            before = issue.current or "unset"
            raise LifecycleError(f"disallowed Lifecycle transition: {before} -> {target}")
        item_id = issue.item_id or self.add_item(issue.content_id)
        field_id, options = self.field()
        self.update(item_id, field_id, options[target])
        observed = self.issue(number).current
        if observed != target:
            raise LifecycleError(
                f"Lifecycle verification failed: expected {target}, observed {observed or 'unset'}"
            )
        return issue.current, target


def label_names(value: dict[str, Any]) -> set[str]:
    labels = value.get("labels", [])
    if not isinstance(labels, list):
        return set()
    return {
        label["name"]
        for label in labels
        if isinstance(label, dict) and isinstance(label.get("name"), str)
    }


def issue_assignees(issue: dict[str, Any]) -> list[str]:
    assignees = issue.get("assignees")
    if not isinstance(assignees, list):
        raise LifecycleError("work issue assignees could not be verified")
    logins = [
        assignee.get("login") if isinstance(assignee, dict) else None
        for assignee in assignees
    ]
    if not all(isinstance(login, str) and login for login in logins):
        raise LifecycleError("work issue assignee is invalid")
    return logins


def replace_assignees(github: GitHub, number: int, assignees: list[str]) -> None:
    try:
        github.request("PATCH", f"/issues/{number}", {"assignees": assignees})
        observed = issue_assignees(github.get_issue(number))
    except QueueLandingError as error:
        raise LifecycleError(str(error)) from error
    if observed != assignees:
        raise LifecycleError("GitHub did not set the expected issue assignees")


def latest_assignment_actor(github: GitHub, number: int, owner: str) -> str:
    try:
        events = github.list_pages(f"/issues/{number}/events")
    except QueueLandingError as error:
        raise LifecycleError(str(error)) from error
    assignments: list[tuple[str, int, str]] = []
    for event in events:
        if event.get("event") != "assigned":
            continue
        assignee = event.get("assignee")
        if not isinstance(assignee, dict) or assignee.get("login") != owner:
            continue
        actor = event.get("actor")
        actor_login = actor.get("login") if isinstance(actor, dict) else None
        created_at = event.get("created_at")
        event_id = event.get("id")
        if (
            not isinstance(actor_login, str)
            or not actor_login
            or not isinstance(created_at, str)
            or not created_at
            or not isinstance(event_id, int)
            or isinstance(event_id, bool)
            or event_id < 1
        ):
            raise LifecycleError("GitHub assignment history is invalid")
        assignments.append((created_at, event_id, actor_login))
    if not assignments:
        raise LifecycleError(
            f"GitHub assignment history does not identify who assigned {owner}"
        )
    return max(assignments, key=lambda assignment: assignment[:2])[2]


def initial_work_issue(
    event_name: str,
    event: dict[str, Any],
    github: GitHub,
    config: dict[str, Any],
) -> Transition | None:
    if event_name != "issues" or event.get("action") not in {"opened", "labeled"}:
        return None
    action = event.get("action")
    event_label_name: str | None = None
    if action == "labeled":
        label = event.get("label")
        event_label_name = label.get("name") if isinstance(label, dict) else None
        if event_label_name not in CLAIM_LABELS:
            return None
    issue = event.get("issue")
    if not isinstance(issue, dict):
        return None
    if action == "opened" and not label_names(issue) & CLAIM_LABELS:
        return None
    number = issue.get("number")
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        raise LifecycleError("GitHub event has an invalid issue number")
    live_issue = github.get_issue(number)
    live_labels = api_label_names(live_issue)
    if action == "labeled" and event_label_name not in live_labels:
        return None
    if action == "opened" and not live_labels & CLAIM_LABELS:
        return None
    if live_issue.get("state") != "open":
        raise LifecycleError("only an open work issue can be claimed")
    assignees = issue_assignees(live_issue)
    if len(assignees) > 1:
        raise LifecycleError("work issue must have at most one assignee")
    if assignees:
        owner = assignees[0]
        actor = latest_assignment_actor(github, number, owner)
        if actor != owner and actor not in maintainers(config):
            replace_assignees(github, number, [])
            raise LifecycleError(
                "existing assignment was not made by the assignee or an "
                "authorized workflow maintainer; "
                "the unauthorized assignment was removed"
            )
    if action == "labeled" and event_label_name != BATCH_LABEL:
        return None
    if BATCH_LABEL not in live_labels:
        return None
    target = "Building" if assignees else "Planned"
    return Transition(number, target, frozenset({None, "Planned", "Building"}))


def event_comment_record(event: dict[str, Any]) -> dict[str, Any] | None:
    comment = event.get("comment")
    if not isinstance(comment, dict):
        raise LifecycleError("issue_comment event is missing its comment")
    try:
        record = comment_record(comment)
    except QueueLandingError as error:
        raise LifecycleError(str(error)) from error
    return record


def maintainers(config: dict[str, Any]) -> set[str]:
    values = config.get("authorized_maintainers")
    if not isinstance(values, list) or not values or not all(
        isinstance(value, str)
        and value
        and value != "Pending GitHub setup"
        for value in values
    ):
        raise LifecycleError("authorized workflow maintainers are not configured")
    return set(values)


def verified_transition(
    event_name: str,
    event: dict[str, Any],
    github: GitHub,
    config: dict[str, Any],
) -> Transition | None:
    initial = initial_work_issue(event_name, event, github, config)
    if initial is not None:
        return initial
    if event_name == "issues" and event.get("action") in {"assigned", "unassigned"}:
        issue_value = event.get("issue")
        number = issue_value.get("number") if isinstance(issue_value, dict) else None
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise LifecycleError("GitHub event has an invalid issue number")
        issue = github.get_issue(number)
        labels = api_label_names(issue)
        if not labels & CLAIM_LABELS:
            return None
        if issue.get("state") != "open":
            raise LifecycleError("only an open work issue can be claimed")
        assignees = issue_assignees(issue)
        event_assignee = event.get("assignee")
        event_login = (
            event_assignee.get("login")
            if isinstance(event_assignee, dict)
            else None
        )
        if not isinstance(event_login, str) or not event_login:
            raise LifecycleError("assignment event assignee is invalid")
        sender = event.get("sender")
        sender_login = sender.get("login") if isinstance(sender, dict) else None
        authorized = maintainers(config)
        if len(assignees) > 1:
            raise LifecycleError(
                "ambiguous assignment race left more than one assignee; "
                "resolve it without guessing which assignment came first"
            )
        if event.get("action") == "assigned":
            if not assignees:
                raise LifecycleError("GitHub did not confirm the new issue assignment")
            owner = assignees[0]
            if event_login != owner:
                raise LifecycleError(
                    f"work issue is already claimed by {owner}; "
                    "refresh GitHub and do not replace its assignee"
                )
            if sender_login != event_login and sender_login not in authorized:
                replace_assignees(github, number, [])
                raise LifecycleError(
                    "ordinary claimants must assign the issue to themselves; "
                    "the unauthorized assignment was removed"
                )
        if event.get("action") == "unassigned":
            if sender_login != event_login and sender_login not in authorized:
                if assignees and assignees != [event_login]:
                    replace_assignees(github, number, [*assignees, event_login])
                    raise LifecycleError(
                        "refused assignment takeover and preserved ambiguous "
                        "ownership without overwriting the newer assignee"
                    )
                replace_assignees(github, number, [event_login])
                raise LifecycleError(
                    f"refused assignment takeover and restored existing owner {event_login}"
                )
        if BATCH_LABEL not in labels:
            return None
        if assignees:
            return Transition(number, "Building", frozenset({"Planned", "Building"}))
        return Transition(number, "Planned", frozenset({"Planned", "Building"}))
    authorized = maintainers(config)
    if event_name == "issue_comment" and event.get("action") == "created":
        record = event_comment_record(event)
        if record is None:
            return None
        issue_value = event.get("issue")
        number = issue_value.get("number") if isinstance(issue_value, dict) else None
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise LifecycleError("GitHub event has an invalid issue number")
        is_pull = isinstance(issue_value.get("pull_request"), dict)
        if not is_pull:
            return None
        pull = github.get_pull(number)
        try:
            batch = one_landing_batch(pull, github.repository_name)
        except QueueLandingError as error:
            raise LifecycleError(str(error)) from error
        if record.get("event") == "local-complete":
            try:
                validate_landing_evidence(github, number, pull, authorized)
            except QueueLandingError as error:
                raise LifecycleError(str(error)) from error
            current_completions = [
                value
                for comment in github.comments(number)
                if (value := comment_record(comment)) is not None
                and value.get("event") == "local-complete"
            ]
            if not current_completions or current_completions[-1].get("_id") != record.get("_id"):
                raise LifecycleError("local-complete is not valid evidence for the pull request's current commit")
            return Transition(
                batch,
                "Locally complete",
                frozenset({"Building", "Locally complete"}),
            )
        if record.get("event") in {
            "local-completion-invalidated",
            "local-completion-missing",
            "rework-request",
        }:
            try:
                owner = validate_assignment(github.get_issue(batch))
                head = pull.get("head")
                head_sha = head.get("sha") if isinstance(head, dict) else None
                if not isinstance(head_sha, str) or not head_sha:
                    raise QueueLandingError("pull request's current commit is missing")
                records = [
                    value
                    for comment in github.comments(number)
                    if (value := comment_record(comment)) is not None
                ]
                records.sort(key=lambda value: (value["_created_at"], value["_id"]))
                completions = [
                    value
                    for value in records
                    if value.get("event") == "local-complete"
                ]
                current_completion_id = (
                    completions[-1]["_id"] if completions else None
                )
                barriers = validated_completion_barriers(
                    records,
                    owner,
                    authorized,
                    head_sha,
                    current_completion_id,
                )
            except QueueLandingError as error:
                raise LifecycleError(str(error)) from error
            if not barriers or barriers[-1].get("_id") != record.get("_id"):
                return None
            return Transition(
                batch,
                "Building",
                frozenset({"Building", "Locally complete", "In PR"}),
                number if VALIDATED_LABEL in api_label_names(pull) else None,
            )
        return None
    if event_name == "pull_request_target":
        action = event.get("action")
        event_label = event.get("label")
        event_label_name = (
            event_label.get("name") if isinstance(event_label, dict) else None
        )
        if action == "labeled" and event_label_name not in {
            QUEUED_LABEL,
            DEQUEUED_LABEL,
        }:
            return None
        pull_event = event.get("pull_request")
        pull_number = pull_event.get("number") if isinstance(pull_event, dict) else None
        if not isinstance(pull_number, int) or isinstance(pull_number, bool) or pull_number < 1:
            raise LifecycleError("pull_request_target event has an invalid pull number")
        pull = github.get_pull(pull_number)
        if LANDING_BATCH_PATTERN.search(body(pull)) is None:
            return None
        try:
            batch = one_landing_batch(pull, github.repository_name)
        except QueueLandingError as error:
            raise LifecycleError(str(error)) from error
        base = pull.get("base")
        if (
            pull.get("merged_at")
            and isinstance(base, dict)
            and base.get("ref") == configured_base_branch(config)
        ):
            return Transition(batch, "Landed", frozenset({"In PR", "Landed"}))
        if action == "synchronize":
            return Transition(
                batch,
                "Building",
                frozenset({"Building", "Locally complete", "In PR"}),
                pull_number if VALIDATED_LABEL in api_label_names(pull) else None,
            )
        if action == "closed":
            return None
        if action != "labeled":
            return None
        label_name = event_label_name
        if label_name not in {QUEUED_LABEL, DEQUEUED_LABEL}:
            return None
        sender = event.get("sender")
        if (
            not isinstance(sender, dict)
            or sender.get("login") != MERGIFY_ACTOR
            or sender.get("type") != "Bot"
        ):
            raise LifecycleError(f"{label_name} was not applied by Mergify")
        current_labels = api_label_names(pull)
        if label_name not in current_labels:
            return None
        opposite = DEQUEUED_LABEL if label_name == QUEUED_LABEL else QUEUED_LABEL
        if opposite in current_labels:
            raise LifecycleError("Mergify queue state labels are ambiguous")
        try:
            validate_landing_evidence(github, pull_number, pull, authorized)
        except QueueLandingError as error:
            raise LifecycleError(str(error)) from error
        if label_name == DEQUEUED_LABEL:
            return Transition(
                batch,
                "Locally complete",
                frozenset({"In PR", "Locally complete"}),
                pull_number if VALIDATED_LABEL in current_labels else None,
            )
        if VALIDATED_LABEL not in api_label_names(pull):
            raise LifecycleError("queued pull request is missing validated landing evidence")
        try:
            pull_values = github.all_pulls()
            landed = merged_batches(
                pull_values,
                github.repository_name,
                configured_base_branch(config),
            )
            pulls = landing_pulls(pull_values, github.repository_name)
            if pull_number not in pulls:
                raise QueueLandingError(
                    "queued pull request is missing from the open landing PR listing"
                )
            dependencies = stack_dependencies(
                pulls, {pull_number}, github.repository_name
            )
            direct_predecessor_batches = {
                one_landing_batch(pulls[predecessor], github.repository_name)
                for predecessor in dependencies[pull_number]
            }
            enforce_landing_order(
                github,
                batch,
                landed,
                direct_predecessor_batches,
            )
        except QueueLandingError as error:
            raise LifecycleError(str(error)) from error
        return Transition(
            batch,
            "In PR",
            frozenset({"Locally complete", "In PR"}),
        )
    return None


def current_queue_transition(
    github: GitHub,
    pull_number: int,
    config: dict[str, Any],
) -> Transition | None:
    """Derive the current Mergify-owned state without trusting an old event label."""
    pull = github.get_pull(pull_number)
    base = pull.get("base")
    if (
        pull.get("merged_at")
        and isinstance(base, dict)
        and base.get("ref") == configured_base_branch(config)
    ):
        synthetic = {"action": "closed", "pull_request": {"number": pull_number}}
        return verified_transition(
            "pull_request_target", synthetic, github, config
        )
    labels = api_label_names(pull)
    states = labels.intersection({QUEUED_LABEL, DEQUEUED_LABEL})
    if not states:
        return None
    if len(states) != 1:
        raise LifecycleError("Mergify queue state labels are ambiguous")
    label = next(iter(states))
    synthetic = {
        "action": "labeled",
        "pull_request": {"number": pull_number},
        "label": {"name": label},
        "sender": {"login": MERGIFY_ACTOR, "type": "Bot"},
    }
    return verified_transition(
        "pull_request_target", synthetic, github, config
    )


def configured_string(config: dict[str, Any], name: str) -> str:
    value = config.get(name)
    if not isinstance(value, str) or not value or value == "Pending GitHub setup":
        raise LifecycleError(f"{name} is not configured")
    return value


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-repository", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--event-path", required=True, type=Path)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "github-state-config.json",
    )
    parser.add_argument("--graphql-url", default="https://api.github.com/graphql")
    parser.add_argument("--api-url", default="https://api.github.com")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if REPOSITORY_PATTERN.fullmatch(args.github_repository) is None:
            raise LifecycleError("GitHub repository must be owner/name")
        token = os.environ.get("PROJECT_TOKEN", "")
        if not token:
            raise LifecycleError("PROJECT_TOKEN is required")
        config = read_object(args.config, "GitHub state config")
        if config.get("repository") != args.github_repository:
            raise LifecycleError("event repository does not match GitHub state config")
        repository_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
        if not repository_token:
            raise LifecycleError("GH_TOKEN or GITHUB_TOKEN is required")
        event = read_object(args.event_path, "GitHub event")
        github = GitHub(args.api_url, args.github_repository, repository_token)
        transition = verified_transition(
            args.event_name,
            event,
            github,
            config,
        )
        if transition is None:
            print("LIFECYCLE IGNORED: event does not change a landing batch")
            return 0
        number, target = transition.number, transition.target
        project_fields = config.get("project_fields")
        field_name = (
            project_fields.get("lifecycle")
            if isinstance(project_fields, dict)
            else None
        )
        if not isinstance(field_name, str) or not field_name:
            raise LifecycleError("Lifecycle Project field is not configured")
        lifecycle = ProjectLifecycle(
            GraphQL(args.graphql_url, token),
            args.github_repository,
            configured_string(config, "project_id"),
            field_name,
        )
        queue_pull_number: int | None = None
        if (
            args.event_name == "pull_request_target"
            and event.get("action") == "labeled"
        ):
            event_pull = event.get("pull_request")
            queue_pull_number = (
                event_pull.get("number") if isinstance(event_pull, dict) else None
            )
            if not isinstance(queue_pull_number, int):
                raise LifecycleError("queue event pull request number is invalid")
            current_transition = current_queue_transition(
                github, queue_pull_number, config
            )
            if current_transition is None:
                print("LIFECYCLE IGNORED: queue event is no longer current")
                return 0
            transition = current_transition
            number, target = transition.number, transition.target
        attempts = 3 if queue_pull_number is not None else 1
        for attempt in range(attempts):
            if transition.target == "Landed" and lifecycle.issue(number).current in {
                "Building",
                "Locally complete",
            }:
                lifecycle.set(
                    Transition(
                        number,
                        "In PR",
                        frozenset({"Building", "Locally complete"}),
                    )
                )
            before, after = lifecycle.set(transition)
            if transition.retire_pull is not None:
                retire = True
                if queue_pull_number is not None:
                    confirmed = current_queue_transition(
                        github, queue_pull_number, config
                    )
                    retire = (
                        confirmed is not None
                        and confirmed.target == transition.target
                        and confirmed.retire_pull == transition.retire_pull
                    )
                if retire:
                    try:
                        github.remove_label(
                            transition.retire_pull, VALIDATED_LABEL
                        )
                        live_pull = github.get_pull(transition.retire_pull)
                        live_labels = api_label_names(live_pull)
                        if (
                            queue_pull_number is not None
                            and QUEUED_LABEL in live_labels
                            and VALIDATED_LABEL not in live_labels
                        ):
                            github.add_label(
                                transition.retire_pull, VALIDATED_LABEL
                            )
                    except QueueLandingError as error:
                        raise LifecycleError(str(error)) from error
            if queue_pull_number is None:
                break
            current_transition = current_queue_transition(
                github, queue_pull_number, config
            )
            if current_transition is None:
                raise LifecycleError("current Mergify queue state is unavailable")
            if (
                current_transition.target == after
                and current_transition.retire_pull is None
            ):
                break
            transition = current_transition
            number, target = transition.number, transition.target
        else:
            raise LifecycleError("Lifecycle did not converge to current Mergify state")
    except LifecycleError as error:
        print(f"LIFECYCLE SYNC FAILED: {error}", file=sys.stderr)
        return 1
    print(f"LIFECYCLE UPDATED: batch={number} from={before or 'unset'} to={after}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
