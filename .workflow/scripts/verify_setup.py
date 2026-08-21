#!/usr/bin/env python3
"""Verify one installed repository workflow without the source package."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


MANIFEST = Path(".workflow/installation.json")
# OS metadata files that file managers drop into working copies; never
# workflow content, so their presence is not an unmanaged-file error.
OS_NOISE_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}
ALLOWED_CUSTOMIZABLE = {
    ".mergify.yml",
    ".github/workflows/landing-ci.yml",
    ".workflow/github-state-config.json",
    "AGENTS.md",
    "docs/agents/domain.md",
}
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
SETUP_PLACEHOLDER = re.compile(r"<[^>\n]+>")
REQUIRED_CONFIGURED_FIELDS = (
    "- **Project:**",
    "- **Purpose:**",
    "- **Primary users or outcomes:**",
    "- Intended product or architecture authority:",
    "- Current implementation and adoption evidence:",
    "- Workflow maintainers:",
    "- Base branch:",
    "- Workflow Project:",
    "- Required status checks:",
    "- Environment setup:",
    "- Focused tests:",
    "- Full local test gate:",
    "- Build or type-check:",
    "- Lint or static checks:",
)
REQUIRED_AGENT_ROUTES = (
    "[`WORKFLOW.md`](WORKFLOW.md)",
    "[`LOCAL-WORK.md`](LOCAL-WORK.md)",
    "[`COORDINATION.md`](COORDINATION.md)",
    "[`GITHUB-WORKFLOW.md`](GITHUB-WORKFLOW.md)",
    "[`docs/agents/review-findings.md`](docs/agents/review-findings.md)",
    "[`docs/agents/domain.md`](docs/agents/domain.md)",
    "[`docs/agents/github-setup.md`](docs/agents/github-setup.md)",
)
REQUIRED_DOMAIN_FIELDS = (
    "- Layout:",
    "- Vocabulary entry point:",
    "- Context documents:",
    "- Architecture authority:",
    "- Architecture decisions:",
    "- Current-state evidence:",
    "- Drift or disagreement record:",
)
DOMAIN_FIELDS_REQUIRING_OWNER = {
    "- Vocabulary entry point:",
    "- Context documents:",
    "- Architecture authority:",
    "- Architecture decisions:",
}
GITHUB_DISCOVERED_FIELDS = {
    "- Workflow Project:",
    "- Required status checks:",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory_digest(files: dict[str, str]) -> str:
    payload = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def safe_relative_path(relative: str) -> bool:
    path = Path(relative)
    return (
        not path.is_absolute()
        and bool(path.parts)
        and all(part not in {"", ".", ".."} for part in path.parts)
        and path.as_posix() == relative
    )


def stays_in_target(target: Path, destination: Path) -> bool:
    try:
        destination.resolve(strict=False).relative_to(target.resolve())
    except ValueError:
        return False
    return True


def read_manifest(target: Path) -> tuple[dict[str, Any] | None, list[str]]:
    path = target / MANIFEST
    if not path.is_file():
        return None, ["MISSING: .workflow/installation.json"]
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, ["DRIFT: invalid .workflow/installation.json"]
    if not isinstance(value, dict):
        return None, ["DRIFT: installation manifest must be an object"]
    return value, []


def installation_errors(target: Path) -> tuple[list[str], set[str]]:
    manifest, errors = read_manifest(target)
    if manifest is None:
        return errors, set()
    files = manifest.get("files")
    if not isinstance(files, dict) or not all(
        isinstance(relative, str) and isinstance(file_digest, str)
        for relative, file_digest in files.items()
    ):
        return [*errors, "DRIFT: installation manifest files must be string hashes"], set()
    if manifest.get("inventory_sha256") != inventory_digest(files):
        errors.append("DRIFT: installation manifest inventory digest does not match")
    customizable = manifest.get("customizable_files")
    if not isinstance(customizable, list) or not all(
        isinstance(relative, str) for relative in customizable
    ):
        errors.append("DRIFT: customizable_files must be a list of paths")
        customizable = []
    customizable_paths = set(customizable)
    if customizable_paths != ALLOWED_CUSTOMIZABLE:
        errors.append(
            "DRIFT: customizable_files do not match this workflow version"
        )
        customizable_paths = ALLOWED_CUSTOMIZABLE
    version_path = target / ".workflow" / "VERSION"
    if version_path.is_file():
        installed_version = version_path.read_text(encoding="utf-8").strip()
        if str(manifest.get("workflow_version")) != installed_version:
            errors.append(
                "DRIFT: manifest workflow version "
                f"{manifest.get('workflow_version')} != installed {installed_version}"
            )
    known_paths = set(files)
    for relative, expected_digest in sorted(files.items()):
        destination = target / relative
        if not safe_relative_path(relative) or not stays_in_target(target, destination):
            errors.append(f"UNSAFE PATH: {relative}")
        elif not destination.is_file():
            errors.append(f"MISSING: {relative}")
        elif relative not in customizable_paths and digest(destination) != expected_digest:
            errors.append(f"DRIFT: {relative}")
    skill_roots = {
        Path(*Path(relative).parts[:3])
        for relative in files
        if len(Path(relative).parts) >= 4
        and Path(relative).parts[:2] == (".agents", "skills")
    }
    for skill_root in skill_roots:
        installed_root = target / skill_root
        if not installed_root.is_dir():
            continue
        for path in installed_root.rglob("*"):
            if (
                path.is_file()
                and path.suffix != ".pyc"
                and "__pycache__" not in path.parts
                and path.name not in OS_NOISE_FILES
                and path.relative_to(target).as_posix() not in known_paths
            ):
                errors.append(f"UNMANAGED FILE: {path.relative_to(target).as_posix()}")
    return errors, known_paths


def field_errors(
    lines: list[str],
    prefixes: tuple[str, ...],
    owner_fields: set[str],
    scope: str,
) -> list[str]:
    errors: list[str] = []
    for prefix in prefixes:
        matching = [line for line in lines if line.startswith(prefix)]
        if not matching:
            if scope == "AGENTS":
                errors.append(f"MISSING REQUIRED AGENTS CONTRACT: {prefix}")
            else:
                errors.append(f"MISSING REQUIRED DOMAIN FIELD: {prefix}")
            continue
        if len(matching) > 1:
            errors.append(f"DUPLICATE {scope} FIELD: {prefix}")
            continue
        value = matching[0][len(prefix) :].strip().strip("`").strip()
        if not value:
            errors.append(f"UNCONFIGURED {scope} FIELD: {prefix}")
        elif value.casefold() == "pending github setup":
            errors.append(f"UNCONFIGURED {scope} FIELD: {prefix}")
        elif prefix in owner_fields and value.casefold() == "none":
            errors.append(f"{scope} FIELD may not be None: {prefix}")
    return errors


def configuration_errors(
    target: Path,
    managed_paths: set[str] | None = None,
    *,
    pre_github: bool = False,
) -> list[str]:
    errors: list[str] = []
    for relative in ("AGENTS.md", "COORDINATION.md", "docs/agents/domain.md"):
        path = target / relative
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            checked_lines = [
                line
                for line in text.splitlines()
                if not (
                    pre_github
                    and relative == "AGENTS.md"
                    and any(line.startswith(prefix) for prefix in GITHUB_DISCOVERED_FIELDS)
                )
            ]
            if SETUP_PLACEHOLDER.search("\n".join(checked_lines)):
                errors.append(f"UNRESOLVED PLACEHOLDER: {relative}")

    orientation = target / "AGENTS.md"
    agent_lines: list[str] = []
    if orientation.is_file():
        text = orientation.read_text(encoding="utf-8")
        agent_lines = text.splitlines()
        required_fields = tuple(
            field
            for field in REQUIRED_CONFIGURED_FIELDS
            if not (pre_github and field in GITHUB_DISCOVERED_FIELDS)
        )
        errors.extend(field_errors(text.splitlines(), required_fields, set(), "AGENTS"))
        for fragment in REQUIRED_AGENT_ROUTES:
            if fragment not in text:
                errors.append(f"MISSING REQUIRED AGENTS CONTRACT: {fragment}")

    state_path = target / ".workflow" / "github-state-config.json"
    if not pre_github:
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"INVALID GITHUB STATE CONFIG: {error}")
            state = None
        if not isinstance(state, dict):
            errors.append("INVALID GITHUB STATE CONFIG: root must be an object")
        else:
            repository = state.get("repository")
            if (
                not isinstance(repository, str)
                or re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
                is None
            ):
                errors.append("UNCONFIGURED GITHUB STATE: repository")
            project_id = state.get("project_id")
            if (
                not isinstance(project_id, str)
                or not project_id
                or project_id == "Pending GitHub setup"
            ):
                errors.append("UNCONFIGURED GITHUB STATE: project_id")
            project_fields = state.get("project_fields")
            if (
                not isinstance(project_fields, dict)
                or project_fields.get("lifecycle") != "Lifecycle"
            ):
                errors.append("UNCONFIGURED GITHUB STATE: project_fields.lifecycle")
            maintainers = state.get("authorized_maintainers")
            if not isinstance(maintainers, list) or not maintainers or not all(
                isinstance(value, str)
                and value
                and value != "Pending GitHub setup"
                for value in maintainers
            ):
                errors.append("UNCONFIGURED GITHUB STATE: authorized_maintainers")
            configured_maintainers = next(
                (
                    line.removeprefix("- Workflow maintainers:").strip().strip("`")
                    for line in agent_lines
                    if line.startswith("- Workflow maintainers:")
                ),
                None,
            )
            if (
                isinstance(maintainers, list)
                and configured_maintainers not in maintainers
            ):
                errors.append(
                    "GITHUB STATE authorized_maintainers do not match AGENTS.md"
                )
            configured_base = next(
                (
                    line.removeprefix("- Base branch:").strip().strip("`")
                    for line in agent_lines
                    if line.startswith("- Base branch:")
                ),
                None,
            )
            if state.get("base_branch") != configured_base:
                errors.append("GITHUB STATE base_branch does not match AGENTS.md")

    domain = target / "docs" / "agents" / "domain.md"
    if domain.is_file():
        lines = domain.read_text(encoding="utf-8").splitlines()
        errors.extend(
            field_errors(
                lines,
                REQUIRED_DOMAIN_FIELDS,
                DOMAIN_FIELDS_REQUIRING_OWNER,
                "DOMAIN",
            )
        )
        layout_lines = [line for line in lines if line.startswith("- Layout:")]
        if len(layout_lines) == 1:
            layout = layout_lines[0].split(":", 1)[1].strip().strip("`")
            if layout not in {"single-context", "multi-context"}:
                errors.append("DOMAIN LAYOUT must be single-context or multi-context")

    if managed_paths is None:
        manifest, _ = read_manifest(target)
        files = manifest.get("files", {}) if manifest else {}
        managed_paths = set(files) if isinstance(files, dict) else set()
    for relative in sorted(path for path in managed_paths if path.endswith(".md")):
        markdown = target / relative
        if not markdown.is_file():
            continue
        for raw_target in MARKDOWN_LINK.findall(markdown.read_text(encoding="utf-8")):
            link = raw_target.strip().strip("<>")
            if not link or link.startswith(("#", "/")) or "://" in link:
                continue
            link_path = link.split("#", 1)[0]
            if link_path and not (markdown.parent / link_path).exists():
                errors.append(f"BROKEN LINK: {relative} -> {link}")
    return errors


def validation_errors(
    target: Path,
    include_installation: bool = True,
    *,
    pre_github: bool = False,
) -> list[str]:
    installation: list[str] = []
    managed_paths: set[str] | None = None
    if include_installation:
        installation, managed_paths = installation_errors(target)
    return [
        *installation,
        *configuration_errors(target, managed_paths, pre_github=pre_github),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument(
        "--pre-github",
        action="store_true",
        help="allow GitHub-discovered Project and status-check fields to remain pending",
    )
    args = parser.parse_args()
    target = args.target.resolve()
    if not target.is_dir():
        print(f"target must be an existing directory: {target}")
        return 1
    errors = validation_errors(target, pre_github=args.pre_github)
    success = "PRE-GITHUB VERIFIED" if args.pre_github else "VERIFIED"
    print("\n".join(errors or [success]))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
