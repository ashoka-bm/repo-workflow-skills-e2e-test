#!/usr/bin/env python3
"""Validate durable human approval for one exact workflow artifact."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


FIELDS = {
    "artifact_sha256",
    "approved",
    "approved_by",
    "approved_at",
    "approval_source_url",
    "approval_event_id",
}
OBSERVATION_FIELDS = {
    "source_url",
    "event_id",
    "actor",
    "occurred_at",
    "decision",
    "artifact_sha256",
}
UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
GITHUB_EVENT_URL = re.compile(
    r"https://github\.com/[^/]+/[^/]+/(?:issues|pull)/\d+#issuecomment-\d+"
)


def read_json_object(path: Path, label: str) -> tuple[dict[str, object] | None, list[str]]:
    if not path.is_file():
        return None, [f"{label} does not exist: {path}"]
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return None, [f"{label} is not valid JSON: {error}"]
    if not isinstance(value, dict):
        return None, [f"{label} must be one JSON object"]
    return value, []


def valid_utc_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not UTC_TIMESTAMP.fullmatch(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def github_event_errors(
    approval: dict[str, object],
    digest: object,
    artifact_bytes: bytes,
    *,
    token: str | None,
    request_json: Callable[[str, dict[str, str]], object] | None = None,
) -> list[str]:
    if not token:
        return ["GitHub approval verification requires GH_TOKEN or GITHUB_TOKEN"]
    source_url = approval.get("approval_source_url")
    if not isinstance(source_url, str) or not GITHUB_EVENT_URL.fullmatch(source_url):
        return []
    parsed = urlparse(source_url)
    parts = parsed.path.strip("/").split("/")
    owner, repository = parts[0], parts[1]
    comment_id = parsed.fragment.removeprefix("issuecomment-")
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "repository-workflow-approval-validator",
    }

    if request_json is None:
        def request_json(path: str, request_headers: dict[str, str]) -> object:
            request = Request(
                f"https://api.github.com{path}", headers=request_headers
            )
            with urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))

    try:
        comment = request_json(
            f"/repos/{owner}/{repository}/issues/comments/{comment_id}", headers
        )
        reactions = request_json(
            f"/repos/{owner}/{repository}/issues/comments/{comment_id}/reactions"
            "?per_page=100",
            headers,
        )
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        return [f"GitHub approval lookup failed: {error}"]
    if not isinstance(comment, dict) or not isinstance(comment.get("body"), str):
        return ["GitHub approval proposal is not a valid issue comment"]
    try:
        artifact_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return ["approval artifacts must be UTF-8 for exact GitHub presentation"]
    expected_body = (
        "WORKFLOW APPROVAL REQUEST\n"
        f"Artifact byte length: {len(artifact_bytes)}\n"
        "Artifact:\n"
    ).encode("utf-8") + artifact_bytes + (
        f"\nArtifact SHA-256: {digest}"
    ).encode("utf-8")
    if comment["body"].encode("utf-8") != expected_body:
        return ["GitHub approval proposal does not present the exact artifact bytes"]
    if not isinstance(reactions, list):
        return ["GitHub approval reactions response must be a list"]
    event_id = str(approval.get("approval_event_id", ""))
    matching = [
        reaction
        for reaction in reactions
        if isinstance(reaction, dict) and str(reaction.get("id")) == event_id
    ]
    if len(matching) != 1 or not isinstance(matching[0], dict):
        return ["GitHub approval reaction was not found by immutable event ID"]
    reaction = matching[0]
    user = reaction.get("user")
    errors: list[str] = []
    if reaction.get("content") != "+1":
        errors.append("GitHub approval event must be a +1 reaction")
    if not isinstance(user, dict) or user.get("type") != "User":
        errors.append("GitHub approval actor must be a human User")
        login = None
    else:
        login = user.get("login")
    if login != approval.get("approved_by"):
        errors.append("GitHub approval actor does not match approved_by")
    if reaction.get("created_at") != approval.get("approved_at"):
        errors.append("GitHub approval time does not match approved_at")
    comment_updated_at = comment.get("updated_at")
    reaction_created_at = reaction.get("created_at")
    if not valid_utc_timestamp(comment_updated_at):
        errors.append("GitHub approval proposal must expose a valid updated_at")
    elif valid_utc_timestamp(reaction_created_at):
        comment_time = datetime.strptime(comment_updated_at, "%Y-%m-%dT%H:%M:%SZ")
        reaction_time = datetime.strptime(reaction_created_at, "%Y-%m-%dT%H:%M:%SZ")
        if comment_time >= reaction_time:
            errors.append(
                "GitHub approval proposal was edited after or not finalized before "
                "the approving reaction"
            )
    return errors


def validate_record(
    artifact: Path,
    approval_path: Path,
    observation_path: Path,
) -> list[str]:
    errors: list[str] = []
    if not artifact.is_file():
        return [f"artifact does not exist: {artifact}"]
    approval, approval_errors = read_json_object(approval_path, "approval record")
    observation, observation_errors = read_json_object(
        observation_path, "approval observation"
    )
    errors.extend(approval_errors)
    errors.extend(observation_errors)
    if approval is None or observation is None:
        return errors

    for field in sorted(FIELDS - set(approval)):
        errors.append(f"approval record missing {field}")
    for field in sorted(set(approval) - FIELDS):
        errors.append(f"approval record contains unexpected field {field}")

    digest = approval.get("artifact_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        errors.append("artifact_sha256 must be a lowercase SHA-256 digest")
    elif digest != hashlib.sha256(artifact.read_bytes()).hexdigest():
        errors.append("artifact_sha256 does not match the exact artifact")

    if approval.get("approved") is not True:
        errors.append("approved must be true")
    approver = approval.get("approved_by")
    if not isinstance(approver, str) or not approver.strip() or approver.lower().startswith(
        "replace with"
    ):
        errors.append("approved_by must identify the human approver")
    approved_at = approval.get("approved_at")
    if not valid_utc_timestamp(approved_at):
        errors.append("approved_at must be a valid ISO-8601 UTC timestamp")

    source_url = approval.get("approval_source_url")
    if not isinstance(source_url, str) or not GITHUB_EVENT_URL.fullmatch(source_url):
        errors.append("approval_source_url must identify a GitHub issue or pull request event")
    event_id = approval.get("approval_event_id")
    if not isinstance(event_id, str) or not event_id.strip():
        errors.append("approval_event_id must identify the observed GitHub event")

    for field in sorted(OBSERVATION_FIELDS - set(observation)):
        errors.append(f"approval observation missing {field}")
    for field in sorted(set(observation) - OBSERVATION_FIELDS):
        errors.append(f"approval observation contains unexpected field {field}")

    if observation.get("source_url") != source_url:
        errors.append("observation source_url does not match approval_source_url")
    if observation.get("event_id") != event_id:
        errors.append("observation event_id does not match approval_event_id")
    if observation.get("actor") != approver:
        errors.append("observation actor does not match approved_by")
    if observation.get("occurred_at") != approved_at:
        errors.append("observation occurred_at does not match approved_at")
    if not valid_utc_timestamp(observation.get("occurred_at")):
        errors.append("observation occurred_at must be a valid ISO-8601 UTC timestamp")
    if observation.get("decision") != "approved":
        errors.append("observation decision must be approved")
    if observation.get("artifact_sha256") != digest:
        errors.append("observation artifact digest does not match")
    return errors


def validate(
    artifact: Path,
    approval_path: Path,
    observation_path: Path,
    *,
    token: str | None,
    request_json: Callable[[str, dict[str, str]], object] | None = None,
) -> list[str]:
    errors = validate_record(artifact, approval_path, observation_path)
    if errors:
        return errors
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    digest = approval["artifact_sha256"]
    return github_event_errors(
        approval,
        digest,
        artifact.read_bytes(),
        token=token,
        request_json=request_json,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("approval", type=Path)
    parser.add_argument("observation", type=Path)
    args = parser.parse_args()
    errors = validate(
        args.artifact,
        args.approval,
        args.observation,
        token=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"),
    )
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
