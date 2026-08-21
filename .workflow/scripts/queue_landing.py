#!/usr/bin/env python3
"""Classify one landing PR, then ask Mergify to queue it."""

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


REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
LANDING_BATCH_PATTERN = re.compile(r"(?mi)^\s*-?\s*Landing batch:\s*(\S+)\s*$")
STARTS_AFTER_LINE_PATTERN = re.compile(r"(?mi)^\s*-?\s*Starts after:\s*(.*)$")
ISSUE_URL_PATTERN = re.compile(
    r"https://github\.com/(?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"
    r"/issues/(?P<number>\d+)"
)
LOCAL_ISSUE_PATTERN = re.compile(r"#(\d+)")
PULL_URL_PATTERN = re.compile(
    r"https://github\.com/(?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"
    r"/pull/(?P<number>\d+)"
)
DEPENDS_ON_PATTERN = re.compile(r"(?mi)^\s*Depends-On:\s*(\S+)\s*$")
PRIORITY_LABEL = "workflow:unlocks-work"
HOLD_LABEL = "workflow:needs-human-review"
VALIDATED_LABEL = "workflow:landing-validated"
BATCH_LABEL = "BATCH"
QUEUE_COMMENT = "@mergifyio queue"
RECORD_LINE_PATTERN = re.compile(r"(?m)^([a-z][a-z0-9_]*):\s*(.*?)\s*$")
COMMENT_REFERENCE_PATTERN = re.compile(r"(?:issuecomment-)?(\d+)$")


class QueueLandingError(RuntimeError):
    pass


def validated_api_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    is_loopback = parsed.hostname in {"127.0.0.1", "::1", "localhost"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and is_loopback):
        raise QueueLandingError("GitHub API URL must use HTTPS")
    if not parsed.netloc or parsed.query or parsed.fragment:
        raise QueueLandingError("GitHub API URL is invalid")
    return value.rstrip("/")


class GitHub:
    def __init__(self, api_url: str, repository: str, token: str) -> None:
        self.api_url = validated_api_url(api_url)
        self.repository_name = repository
        self.repository = urllib.parse.quote(repository, safe="/")
        self.token = token

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        body = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(
            f"{self.api_url}/repos/{self.repository}{path}",
            data=body,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                response_body = response.read()
        except urllib.error.HTTPError as error:
            raise QueueLandingError(
                f"GitHub API {method} {path} failed with HTTP {error.code}"
            ) from error
        except urllib.error.URLError as error:
            raise QueueLandingError(
                f"GitHub API {method} {path} failed: {error.reason}"
            ) from error
        if not response_body:
            return None
        try:
            return json.loads(response_body)
        except json.JSONDecodeError as error:
            raise QueueLandingError("GitHub API returned invalid JSON") from error

    def get_pull(self, number: int) -> dict[str, Any]:
        value = self.request("GET", f"/pulls/{number}")
        if not isinstance(value, dict):
            raise QueueLandingError("GitHub returned an invalid pull request")
        return value

    def get_issue(self, number: int) -> dict[str, Any]:
        value = self.request("GET", f"/issues/{number}")
        if not isinstance(value, dict):
            raise QueueLandingError("GitHub returned an invalid issue")
        return value

    def list_pages(self, path: str) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        separator = "&" if "?" in path else "?"
        page = 1
        while True:
            value = self.request(
                "GET", f"{path}{separator}per_page=100&page={page}"
            )
            if not isinstance(value, list) or not all(
                isinstance(item, dict) for item in value
            ):
                raise QueueLandingError("GitHub returned an invalid paginated list")
            values.extend(value)
            if len(value) < 100:
                return values
            page += 1

    def open_issues(self) -> list[dict[str, Any]]:
        return self.list_pages("/issues?state=open")

    def all_pulls(self) -> list[dict[str, Any]]:
        return self.list_pages("/pulls?state=all")

    def comments(self, number: int) -> list[dict[str, Any]]:
        return self.list_pages(f"/issues/{number}/comments")

    def blocking_issues(self, number: int) -> list[dict[str, Any]]:
        return self.list_pages(f"/issues/{number}/dependencies/blocking")

    def blocked_by_issues(self, number: int) -> list[dict[str, Any]]:
        return self.list_pages(f"/issues/{number}/dependencies/blocked_by")

    def add_label(self, number: int, label: str) -> None:
        self.request("POST", f"/issues/{number}/labels", {"labels": [label]})

    def remove_label(self, number: int, label: str) -> None:
        encoded = urllib.parse.quote(label, safe="")
        self.request("DELETE", f"/issues/{number}/labels/{encoded}")

    def queue(self, number: int) -> None:
        self.request("POST", f"/issues/{number}/comments", {"body": QUEUE_COMMENT})


def label_names(value: dict[str, Any]) -> set[str]:
    labels = value.get("labels", [])
    if not isinstance(labels, list):
        raise QueueLandingError("GitHub returned invalid labels")
    names: set[str] = set()
    for label in labels:
        if isinstance(label, dict) and isinstance(label.get("name"), str):
            names.add(label["name"])
    return names


def body(value: dict[str, Any]) -> str:
    text = value.get("body")
    return text if isinstance(text, str) else ""


def local_issue_references(value: str, repository: str) -> set[int]:
    references: set[int] = set()
    without_urls = value
    for match in ISSUE_URL_PATTERN.finditer(value):
        if match.group("repository").lower() != repository.lower():
            raise QueueLandingError(
                f"issue references must belong to {repository}"
            )
        references.add(int(match.group("number")))
    without_urls = ISSUE_URL_PATTERN.sub("", without_urls)
    references.update(int(number) for number in LOCAL_ISSUE_PATTERN.findall(without_urls))
    return references


def one_landing_batch(pull: dict[str, Any], repository: str) -> int:
    matches = LANDING_BATCH_PATTERN.findall(body(pull))
    if len(matches) != 1:
        raise QueueLandingError("pull request must declare exactly one Landing batch")
    value = matches[0].strip("`")
    if value.isdigit():
        return int(value)
    references = local_issue_references(value, repository)
    if len(references) != 1:
        raise QueueLandingError("pull request Landing batch reference is ambiguous")
    return next(iter(references))


def starts_after(issue: dict[str, Any], repository: str) -> set[int]:
    issue_body = issue.get("body")
    number = issue.get("number")
    if not isinstance(issue_body, str):
        raise QueueLandingError(f"landing batch #{number} body is missing")
    lines = STARTS_AFTER_LINE_PATTERN.findall(issue_body)
    if len(lines) != 1:
        raise QueueLandingError(
            f"landing batch #{number} must declare exactly one Starts after field"
        )
    value = lines[0].strip().strip("`")
    if value.lower() == "none":
        return set()
    references = local_issue_references(value, repository)
    if not references:
        raise QueueLandingError(f"landing batch #{number} Starts after is ambiguous")
    return references


def is_open_batch(issue: dict[str, Any]) -> bool:
    return issue.get("state") == "open" and BATCH_LABEL in label_names(issue)


def issue_number(value: dict[str, Any], context: str) -> int:
    number = value.get("number")
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        raise QueueLandingError(f"GitHub returned an invalid {context} number")
    return number


def unlocking_batches(github: GitHub, landed_batches: set[int]) -> set[int]:
    open_issues = github.open_issues()
    batches = {
        issue_number(issue, "landing batch"): issue
        for issue in open_issues
        if is_open_batch(issue)
    }
    if not batches:
        raise QueueLandingError("GitHub returned no open landing batches")
    blocking_cache: dict[int, set[int]] = {}
    for upstream in batches:
        dependants = github.blocking_issues(upstream)
        blocking_cache[upstream] = {
            issue_number(value, "blocking issue") for value in dependants
        }
        for dependant in dependants:
            if (
                STARTS_AFTER_LINE_PATTERN.search(body(dependant))
                and upstream in starts_after(dependant, github.repository_name)
                and BATCH_LABEL not in label_names(dependant)
            ):
                number = issue_number(dependant, "landing batch")
                raise QueueLandingError(
                    f"landing batch #{number} is missing its {BATCH_LABEL} label"
                )
    unlockers: set[int] = set()
    for downstream, issue in batches.items():
        for upstream in starts_after(issue, github.repository_name):
            upstream_issue = batches.get(upstream)
            if upstream_issue is None:
                upstream_issue = github.get_issue(upstream)
                if BATCH_LABEL not in label_names(upstream_issue):
                    raise QueueLandingError(
                        f"Starts after #{upstream} does not identify a landing batch"
                    )
                if upstream_issue.get("state") == "closed":
                    if upstream in landed_batches:
                        continue
                    raise QueueLandingError(
                        f"Starts after batch #{upstream} has not merged in a pull request"
                    )
                raise QueueLandingError(
                    f"open Starts after batch #{upstream} is missing from batch listing"
                )
            if downstream not in blocking_cache[upstream]:
                raise QueueLandingError(
                    f"landing batch #{downstream} is missing native lands_after #{upstream}"
                )
            unlockers.add(upstream)
    return unlockers


def enforce_landing_order(
    github: GitHub,
    batch: int,
    landed_batches: set[int],
    open_stack_predecessors: set[int] | None = None,
) -> None:
    allowed_open = open_stack_predecessors or set()
    observed: set[int] = set()
    for prerequisite in github.blocked_by_issues(batch):
        number = issue_number(prerequisite, "landing prerequisite")
        observed.add(number)
        if BATCH_LABEL not in label_names(prerequisite):
            raise QueueLandingError(
                f"lands_after #{number} does not identify a landing batch"
            )
        if number not in landed_batches and number not in allowed_open:
            raise QueueLandingError(
                f"landing batch #{batch} has unresolved lands_after #{number}"
            )
    missing = allowed_open - observed
    if missing:
        predecessor = min(missing)
        raise QueueLandingError(
            f"stack predecessor batch #{predecessor} is missing native lands_after"
        )


def scalar(value: str) -> str | bool:
    stripped = value.strip().strip("`\"'")
    if stripped == "true":
        return True
    if stripped == "false":
        return False
    return stripped


def comment_record(comment: dict[str, Any]) -> dict[str, Any] | None:
    text = comment.get("body")
    if not isinstance(text, str):
        return None
    fields = {
        key: scalar(value) for key, value in RECORD_LINE_PATTERN.findall(text)
    }
    if not isinstance(fields.get("event"), str):
        return None
    comment_id = comment.get("id")
    created_at = comment.get("created_at")
    updated_at = comment.get("updated_at")
    user = comment.get("user")
    author = user.get("login") if isinstance(user, dict) else None
    if (
        not isinstance(comment_id, int)
        or isinstance(comment_id, bool)
        or comment_id < 1
        or not isinstance(created_at, str)
        or not isinstance(updated_at, str)
        or not isinstance(author, str)
        or not author
    ):
        raise QueueLandingError("GitHub returned invalid landing evidence metadata")
    fields["_id"] = comment_id
    fields["_created_at"] = created_at
    fields["_updated_at"] = updated_at
    fields["_author"] = author
    return fields


def record_position(record: dict[str, Any]) -> tuple[str, int]:
    return record["_created_at"], record["_id"]


def require_unedited(record: dict[str, Any], event: str) -> None:
    if record.get("_created_at") != record.get("_updated_at"):
        raise QueueLandingError(f"{event} evidence was edited")


def reference_id(value: Any) -> int | None:
    match = COMMENT_REFERENCE_PATTERN.search(value) if isinstance(value, str) else None
    return int(match.group(1)) if match else None


def validated_completion_barriers(
    records: list[dict[str, Any]],
    owner: str,
    maintainers: set[str],
    head_sha: str,
    current_completion_id: int | None = None,
) -> list[dict[str, Any]]:
    """Return authenticated records that retire completion evidence."""
    barriers: list[dict[str, Any]] = []
    completion_ids = {
        record.get("_id")
        for record in records
        if record.get("event") == "local-complete"
    }
    for record in records:
        event = record.get("event")
        author = record.get("_author")
        if event in {"local-completion-invalidated", "local-completion-missing"}:
            if author not in maintainers:
                continue
            require_unedited(record, str(event))
            if record.get("maintainer") != author:
                raise QueueLandingError(
                    f"{event} maintainer must match its GitHub author"
                )
            if event == "local-completion-invalidated":
                completion_id = reference_id(record.get("completion"))
                if completion_id not in completion_ids:
                    raise QueueLandingError(
                        "local-completion-invalidated must reference local-complete evidence"
                    )
                if (
                    current_completion_id is not None
                    and completion_id != current_completion_id
                ):
                    continue
        elif event == "rework-request":
            if author != owner:
                continue
            require_unedited(record, "rework-request")
            if record.get("requested_by") != author:
                raise QueueLandingError(
                    "rework-request requested_by must match its GitHub author"
                )
            if record.get("candidate_commit") != head_sha:
                raise QueueLandingError(
                    "rework-request candidate commit does not match PR head"
                )
        else:
            continue
        if not isinstance(record.get("reason"), str) or not record["reason"]:
            raise QueueLandingError(f"{event} reason is missing")
        barriers.append(record)
    barriers.sort(key=record_position)
    return barriers


def authorized_maintainers(config_path: Path) -> set[str]:
    value = github_state_config(config_path)
    maintainers = value.get("authorized_maintainers")
    if not isinstance(maintainers, list) or not maintainers or not all(
        isinstance(maintainer, str)
        and maintainer
        and maintainer != "Pending GitHub setup"
        for maintainer in maintainers
    ):
        raise QueueLandingError("authorized workflow maintainers are not configured")
    return set(maintainers)


def github_state_config(config_path: Path) -> dict[str, Any]:
    try:
        value = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise QueueLandingError(f"cannot read GitHub state config: {error}") from error
    if not isinstance(value, dict):
        raise QueueLandingError("GitHub state config must be an object")
    return value


def configured_base_branch(config: dict[str, Any]) -> str:
    value = config.get("base_branch")
    if (
        not isinstance(value, str)
        or not value
        or value == "Pending GitHub setup"
    ):
        raise QueueLandingError("base branch is not configured")
    return value


def validate_assignment(batch_issue: dict[str, Any]) -> str:
    """Return the sole owner when assignment is a valid current claim."""
    if batch_issue.get("state") != "open":
        raise QueueLandingError("landing batch must be open")
    assignees = batch_issue.get("assignees")
    if not isinstance(assignees, list) or len(assignees) != 1:
        raise QueueLandingError("landing batch must have exactly one owner")
    owner = assignees[0].get("login") if isinstance(assignees[0], dict) else None
    if not isinstance(owner, str) or not owner:
        raise QueueLandingError("landing batch owner is invalid")
    return owner


def validate_landing_evidence(
    github: GitHub,
    pull_request: int,
    pull: dict[str, Any],
    maintainers: set[str],
) -> None:
    head = pull.get("head")
    head_sha = head.get("sha") if isinstance(head, dict) else None
    if not isinstance(head_sha, str) or not head_sha:
        raise QueueLandingError("pull request's current commit is missing")
    batch = one_landing_batch(pull, github.repository_name)
    batch_issue = github.get_issue(batch)
    if HOLD_LABEL in label_names(batch_issue):
        raise QueueLandingError(f"landing batch #{batch} needs human review")
    owner = validate_assignment(batch_issue)

    records = [
        record
        for comment in github.comments(pull_request)
        if (record := comment_record(comment)) is not None
    ]
    records.sort(key=record_position)
    completions = [record for record in records if record.get("event") == "local-complete"]
    if not completions:
        raise QueueLandingError("current local-complete evidence is missing")
    completion = completions[-1]
    if completion.get("candidate_commit") != head_sha:
        raise QueueLandingError("local-complete does not match the pull request's current commit")
    if completion.get("local_gates_passed") is not True:
        raise QueueLandingError("local-complete does not prove passing local gates")
    require_unedited(completion, "local-complete")
    if completion.get("_author") != owner:
        raise QueueLandingError("local-complete must be authored by the batch owner")
    for field in ("worker", "session"):
        if not isinstance(completion.get(field), str) or not completion[field]:
            raise QueueLandingError(f"local-complete {field} is missing")
    review_id = reference_id(completion.get("review"))
    review = next((record for record in records if record.get("_id") == review_id), None)
    if (
        review is None
        or review.get("event") != "local-review"
        or review.get("candidate_commit") != head_sha
        or review.get("verdict") != "passed"
        or review.get("reviewed_by") != review.get("_author")
    ):
        raise QueueLandingError("local-complete does not reference a passing review of the current commit")
    require_unedited(review, "local-review")
    if not review.get("_author") or review.get("_author") == completion.get("_author"):
        raise QueueLandingError("local-review must be authored by another GitHub actor")
    completion_position = record_position(completion)
    review_position = record_position(review)
    barriers = validated_completion_barriers(
        records, owner, maintainers, head_sha, completion["_id"]
    )
    barrier_position = record_position(barriers[-1]) if barriers else None
    if barrier_position is not None and completion_position <= barrier_position:
        raise QueueLandingError("local-complete evidence was retired")
    if barrier_position is not None and review_position <= barrier_position:
        raise QueueLandingError("local-review must follow completion invalidation")
    if review_position >= completion_position:
        raise QueueLandingError("local-review must precede local-complete")


def landing_pulls(
    pull_values: list[dict[str, Any]], repository: str
) -> dict[int, dict[str, Any]]:
    pulls: dict[int, dict[str, Any]] = {}
    batches: set[int] = set()
    for pull in pull_values:
        if pull.get("state") != "open":
            continue
        if LANDING_BATCH_PATTERN.search(body(pull)) is None:
            continue
        number = issue_number(pull, "pull request")
        batch = one_landing_batch(pull, repository)
        if batch in batches:
            raise QueueLandingError(f"landing batch #{batch} has multiple open pull requests")
        batches.add(batch)
        pulls[number] = pull
    return pulls


def merged_batches(
    pull_values: list[dict[str, Any]], repository: str, base_branch: str
) -> set[int]:
    return {
        one_landing_batch(pull, repository)
        for pull in pull_values
        if pull.get("merged_at")
        and isinstance(pull.get("base"), dict)
        and pull["base"].get("ref") == base_branch
        and LANDING_BATCH_PATTERN.search(body(pull)) is not None
    }


def pull_reference(reference: str, repository: str) -> int:
    url = PULL_URL_PATTERN.fullmatch(reference)
    if url is not None:
        if url.group("repository").lower() != repository.lower():
            raise QueueLandingError(
                f"pull request references must belong to {repository}"
            )
        return int(url.group("number"))
    if reference.startswith("#") and reference[1:].isdigit():
        return int(reference[1:])
    raise QueueLandingError("Depends-On pull request reference is ambiguous")


def stack_dependencies(
    pulls: dict[int, dict[str, Any]], roots: set[int], repository: str
) -> dict[int, set[int]]:
    dependencies: dict[int, set[int]] = {}
    visiting: set[int] = set()

    def visit(number: int) -> None:
        if number in dependencies:
            return
        if number in visiting:
            raise QueueLandingError("Depends-On stack contains a cycle")
        if number not in pulls:
            raise QueueLandingError(f"open stack predecessor PR #{number} is missing")
        visiting.add(number)
        references = DEPENDS_ON_PATTERN.findall(body(pulls[number]))
        predecessors = {
            pull_reference(reference, repository) for reference in references
        }
        for predecessor in predecessors:
            if predecessor not in pulls:
                raise QueueLandingError(
                    f"open stack predecessor PR #{predecessor} is missing"
                )
            successor_base = pulls[number].get("base")
            predecessor_head = pulls[predecessor].get("head")
            if (
                not isinstance(successor_base, dict)
                or not isinstance(predecessor_head, dict)
                or not isinstance(successor_base.get("ref"), str)
                or successor_base.get("ref") != predecessor_head.get("ref")
            ):
                raise QueueLandingError(
                    f"PR #{number} is not physically stacked on predecessor PR #{predecessor}"
                )
            visit(predecessor)
        visiting.remove(number)
        dependencies[number] = predecessors
        if len(dependencies) > 20:
            raise QueueLandingError("Mergify stack depth exceeds 20 pull requests")

    for root in roots:
        visit(root)
    return dependencies


def prioritized_pulls(
    pulls: dict[int, dict[str, Any]], unlocker_batches: set[int], repository: str
) -> set[int]:
    roots = {
        number
        for number, pull in pulls.items()
        if one_landing_batch(pull, repository) in unlocker_batches
    }
    return set(stack_dependencies(pulls, roots, repository))


def classify_and_queue(
    github: GitHub,
    pull_request: int,
    maintainers: set[str],
    base_branch: str,
) -> bool:
    pull = github.get_pull(pull_request)
    if pull.get("state") != "open":
        raise QueueLandingError("pull request must be open")
    if pull.get("draft") is not False:
        raise QueueLandingError("pull request must be ready for review")
    one_landing_batch(pull, github.repository_name)
    pull_values = github.all_pulls()
    landed = merged_batches(
        pull_values,
        github.repository_name,
        base_branch,
    )
    unlockers = unlocking_batches(github, landed)
    pulls = landing_pulls(pull_values, github.repository_name)
    if pull_request not in pulls:
        raise QueueLandingError("pull request is missing from the open landing PR listing")
    queued_stack = stack_dependencies(
        pulls, {pull_request}, github.repository_name
    )
    for number in sorted(queued_stack):
        candidate = pulls[number]
        if candidate.get("draft") is not False:
            raise QueueLandingError(
                f"stack pull request #{number} must be ready for review"
            )
        candidate_batch = one_landing_batch(candidate, github.repository_name)
        validate_landing_evidence(github, number, candidate, maintainers)
        direct_predecessor_batches = {
            one_landing_batch(pulls[predecessor], github.repository_name)
            for predecessor in queued_stack[number]
        }
        enforce_landing_order(
            github,
            candidate_batch,
            landed,
            direct_predecessor_batches,
        )
        batch_issue = github.get_issue(candidate_batch)
        if not is_open_batch(batch_issue):
            raise QueueLandingError(
                f"Landing batch #{candidate_batch} is not an open BATCH issue"
            )
    priority_set = prioritized_pulls(pulls, unlockers, github.repository_name)
    high_priority = pull_request in priority_set

    for number, candidate in pulls.items():
        has_priority = PRIORITY_LABEL in label_names(candidate)
        if number in priority_set and not has_priority:
            github.add_label(number, PRIORITY_LABEL)
        elif number not in priority_set and has_priority:
            github.remove_label(number, PRIORITY_LABEL)

    for number in sorted(queued_stack):
        if VALIDATED_LABEL not in label_names(pulls[number]):
            github.add_label(number, VALIDATED_LABEL)
    github.queue(pull_request)
    return high_priority


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-repository", required=True)
    parser.add_argument("--pull-request", required=True, type=int)
    parser.add_argument("--api-url", default="https://api.github.com")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "github-state-config.json",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    try:
        if REPOSITORY_PATTERN.fullmatch(args.github_repository) is None:
            raise QueueLandingError("GitHub repository must be owner/name")
        if args.pull_request < 1:
            raise QueueLandingError("pull request number must be positive")
        if not token:
            raise QueueLandingError("GH_TOKEN or GITHUB_TOKEN is required")
        github = GitHub(args.api_url, args.github_repository, token)
        config = github_state_config(args.config)
        maintainers = authorized_maintainers(args.config)
        high_priority = classify_and_queue(
            github,
            args.pull_request,
            maintainers,
            configured_base_branch(config),
        )
    except QueueLandingError as error:
        print(f"QUEUE LANDING FAILED: {error}", file=sys.stderr)
        return 1
    priority = "high" if high_priority else "normal"
    print(f"LANDING PR QUEUED: pull_request={args.pull_request} priority={priority}")
    print(
        "NEXT: wait for Mergify to confirm this commit is queued and for the "
        "Lifecycle workflow to report In PR"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
