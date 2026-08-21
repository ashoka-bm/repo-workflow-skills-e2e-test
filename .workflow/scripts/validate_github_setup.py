#!/usr/bin/env python3
"""Validate an observed GitHub repository snapshot against the workflow contract."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_CONTRACT = Path(__file__).resolve().parents[1] / "github-setup-contract.json"
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "github-state-config.json"
REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


def read_object(path: Path, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.is_file():
        return None, [f"MISSING {label}: {path}"]
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return None, [f"INVALID {label}: {error}"]
    if not isinstance(value, dict):
        return None, [f"INVALID {label}: root must be an object"]
    return value, []


def configured_value(agents_text: str, prefix: str) -> str | None:
    matching = [line for line in agents_text.splitlines() if line.startswith(prefix)]
    if len(matching) != 1:
        return None
    return matching[0][len(prefix) :].strip().strip("`").strip()


def validation_errors(
    snapshot: dict[str, Any],
    contract: dict[str, Any],
    agents_text: str | None = None,
) -> list[str]:
    errors: list[str] = []
    repository_identity = snapshot.get("repository_identity")
    if contract.get("repository_identity_required") is True:
        name_with_owner = (
            repository_identity.get("name_with_owner")
            if isinstance(repository_identity, dict)
            else None
        )
        if (
            not isinstance(name_with_owner, str)
            or REPOSITORY_PATTERN.fullmatch(name_with_owner) is None
        ):
            errors.append("MISSING REPOSITORY IDENTITY: name_with_owner")
    identity = snapshot.get("project_identity")
    if contract.get("project_identity_required") is True:
        if not isinstance(identity, dict):
            errors.append("MISSING PROJECT IDENTITY")
        else:
            project_id = identity.get("id")
            project_url = identity.get("url")
            if not isinstance(project_id, str) or not project_id.strip():
                errors.append("MISSING PROJECT IDENTITY: id")
            if (
                not isinstance(project_url, str)
                or not project_url.startswith("https://github.com/")
            ):
                errors.append("MISSING PROJECT IDENTITY: url")
    actual_labels = snapshot.get("labels")
    if not isinstance(actual_labels, list) or not all(
        isinstance(label, str) for label in actual_labels
    ):
        errors.append("INVALID SNAPSHOT: labels must be a list of strings")
        actual_label_names: set[str] = set()
    else:
        actual_label_names = set(actual_labels)
    required_labels = contract.get("labels")
    if not isinstance(required_labels, list):
        errors.append("INVALID CONTRACT: labels must be a list")
    else:
        for label in required_labels:
            if not isinstance(label, dict) or not isinstance(label.get("name"), str):
                errors.append("INVALID CONTRACT: every label requires a name")
                continue
            if label["name"] not in actual_label_names:
                errors.append(f"MISSING LABEL: {label['name']}")
    deprecated_labels = contract.get("deprecated_labels", {})
    if not isinstance(deprecated_labels, dict) or not all(
        isinstance(name, str) and isinstance(replacement, str)
        for name, replacement in deprecated_labels.items()
    ):
        errors.append("INVALID CONTRACT: deprecated_labels must map strings to strings")
    else:
        for name, replacement in deprecated_labels.items():
            if name in actual_label_names:
                errors.append(f"DEPRECATED LABEL: {name} -> {replacement}")

    actual_fields = snapshot.get("project_fields")
    if not isinstance(actual_fields, dict):
        errors.append("INVALID SNAPSHOT: project_fields must be an object")
        actual_fields = {}
    required_fields = contract.get("project_fields")
    if not isinstance(required_fields, dict):
        errors.append("INVALID CONTRACT: project_fields must be an object")
        required_fields = {}
    for name, required in required_fields.items():
        actual = actual_fields.get(name)
        if not isinstance(actual, dict):
            errors.append(f"MISSING PROJECT FIELD: {name}")
            continue
        if not isinstance(required, dict):
            errors.append(f"INVALID CONTRACT PROJECT FIELD: {name}")
            continue
        if actual.get("type") != required.get("type"):
            errors.append(f"WRONG PROJECT FIELD TYPE: {name}")
        required_options = required.get("options", [])
        actual_options = actual.get("options", [])
        if not isinstance(actual_options, list):
            actual_options = []
        for option in required_options if isinstance(required_options, list) else []:
            if option not in actual_options:
                errors.append(f"MISSING PROJECT OPTION: {name} -> {option}")
        if isinstance(required_options, list):
            for option in actual_options:
                if option not in required_options:
                    errors.append(f"UNEXPECTED PROJECT OPTION: {name} -> {option}")

    actual_repository = snapshot.get("repository")
    if not isinstance(actual_repository, dict):
        errors.append("INVALID SNAPSHOT: repository must be an object")
        actual_repository = {}
    required_repository = contract.get("repository")
    if not isinstance(required_repository, dict):
        errors.append("INVALID CONTRACT: repository must be an object")
        required_repository = {}
    for setting, expected in required_repository.items():
        if actual_repository.get(setting) is not expected:
            errors.append(f"REPOSITORY SETTING MISMATCH: {setting}")
    required_lists = contract.get("required_non_empty_repository_lists")
    if not isinstance(required_lists, list):
        errors.append("INVALID CONTRACT: required repository lists must be a list")
    else:
        for setting in required_lists:
            value = actual_repository.get(setting)
            if not isinstance(value, list) or not value or not all(
                isinstance(item, str) and item.strip() for item in value
            ):
                errors.append(
                    f"REPOSITORY SETTING must be a non-empty list: {setting}"
                )
    required_members = contract.get("required_repository_list_members", {})
    if not isinstance(required_members, dict):
        errors.append("INVALID CONTRACT: required repository list members must be an object")
    else:
        for setting, members in required_members.items():
            actual_members = actual_repository.get(setting, [])
            if not isinstance(members, list) or not all(
                isinstance(member, str) and member for member in members
            ):
                errors.append(
                    f"INVALID CONTRACT: required members for {setting} must be strings"
                )
                continue
            for member in members:
                if member not in actual_members:
                    errors.append(
                        f"MISSING REPOSITORY LIST MEMBER: {setting} -> {member}"
                    )
    if agents_text is not None:
        project = configured_value(agents_text, "- Workflow Project:")
        if not isinstance(identity, dict) or project not in {
            identity.get("id"),
            identity.get("url"),
        }:
            errors.append("PROJECT IDENTITY does not match AGENTS.md")
        checks = configured_value(agents_text, "- Required status checks:")
        expected_checks = {
            check.strip() for check in (checks or "").split(",") if check.strip()
        }
        observed_checks = actual_repository.get("required_status_checks", [])
        if not expected_checks or not expected_checks.issubset(set(observed_checks)):
            errors.append("REQUIRED STATUS CHECKS do not match AGENTS.md")
        expected_commands = {
            value
            for prefix in (
                "- Full local test gate:",
                "- Build or type-check:",
                "- Lint or static checks:",
            )
            if (value := configured_value(agents_text, prefix))
            and value.casefold() != "none"
        }
        observed_commands = set(actual_repository.get("full_gate_commands", []))
        if not expected_commands.issubset(observed_commands):
            errors.append("FULL GATE COMMANDS do not match AGENTS.md")
    return errors


def runtime_config_errors(
    config: dict[str, Any],
    snapshot: dict[str, Any],
    agents_text: str,
) -> list[str]:
    errors: list[str] = []
    repository = config.get("repository")
    if (
        not isinstance(repository, str)
        or REPOSITORY_PATTERN.fullmatch(repository) is None
    ):
        errors.append("UNCONFIGURED GITHUB STATE: repository")
    repository_identity = snapshot.get("repository_identity")
    observed_repository = (
        repository_identity.get("name_with_owner")
        if isinstance(repository_identity, dict)
        else None
    )
    if repository != observed_repository:
        errors.append("GITHUB STATE repository does not match observed repository")
    identity = snapshot.get("project_identity")
    observed_project = identity.get("id") if isinstance(identity, dict) else None
    if config.get("project_id") != observed_project:
        errors.append("GITHUB STATE project_id does not match observed Project")
    base = configured_value(agents_text, "- Base branch:")
    if config.get("base_branch") != base:
        errors.append("GITHUB STATE base_branch does not match AGENTS.md")
    fields = config.get("project_fields")
    lifecycle = fields.get("lifecycle") if isinstance(fields, dict) else None
    observed_fields = snapshot.get("project_fields")
    if lifecycle != "Lifecycle" or not isinstance(observed_fields, dict) or lifecycle not in observed_fields:
        errors.append("GITHUB STATE Lifecycle field does not match observed Project")
    maintainers = config.get("authorized_maintainers")
    expected_maintainer = configured_value(agents_text, "- Workflow maintainers:")
    if (
        not isinstance(maintainers, list)
        or not maintainers
        or not all(
            isinstance(value, str)
            and value
            and value != "Pending GitHub setup"
            for value in maintainers
        )
        or expected_maintainer not in maintainers
    ):
        errors.append("GITHUB STATE maintainers do not match AGENTS.md")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--agents", type=Path)
    parser.add_argument(
        "--contract-only",
        action="store_true",
        help="check contract shape before AGENTS.md can be bound; not a final setup gate",
    )
    args = parser.parse_args()
    snapshot, snapshot_errors = read_object(args.snapshot, "SNAPSHOT")
    contract, contract_errors = read_object(args.contract, "CONTRACT")
    errors = [*snapshot_errors, *contract_errors]
    agents_text: str | None = None
    if args.contract_only and args.agents is not None:
        errors.append("--contract-only and --agents cannot be used together")
    elif not args.contract_only and args.agents is None:
        errors.append("FINAL VALIDATION REQUIRES: --agents AGENTS.md")
    if args.agents is not None:
        if not args.agents.is_file():
            errors.append(f"MISSING AGENTS: {args.agents}")
        else:
            agents_text = args.agents.read_text(encoding="utf-8")
    if snapshot is not None and contract is not None:
        errors.extend(validation_errors(snapshot, contract, agents_text))
    if not args.contract_only and snapshot is not None and agents_text is not None:
        config, config_errors = read_object(args.config, "GITHUB STATE CONFIG")
        errors.extend(config_errors)
        if config is not None:
            errors.extend(runtime_config_errors(config, snapshot, agents_text))
    success = "GITHUB CONTRACT VERIFIED" if args.contract_only else "GITHUB SETUP VERIFIED"
    print("\n".join(errors or [success]))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
