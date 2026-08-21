#!/usr/bin/env python3
"""Delete one merged batch branch and its exact clean local worktree."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
SHA_PATTERN = re.compile(r"[0-9a-fA-F]{40}")


class CleanupError(RuntimeError):
    pass


class PartialCleanupError(RuntimeError):
    pass


def git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise CleanupError(detail or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def git_with_status(repository: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def common_git_directory(repository: Path) -> Path:
    value = Path(git(repository, "rev-parse", "--git-common-dir"))
    if not value.is_absolute():
        value = repository / value
    return value.resolve()


def registered_worktrees(repository: Path) -> dict[Path, str | None]:
    registrations: dict[Path, str | None] = {}
    current_worktree: Path | None = None
    for line in git(repository, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            current_worktree = Path(line.removeprefix("worktree ")).resolve()
            registrations[current_worktree] = None
        elif line.startswith("branch ") and current_worktree is not None:
            registrations[current_worktree] = line.removeprefix("branch refs/heads/")
    return registrations


def validated_api_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    is_loopback = parsed.hostname in {"127.0.0.1", "::1", "localhost"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and is_loopback):
        raise CleanupError("GitHub API URL must use HTTPS")
    if not parsed.netloc or parsed.query or parsed.fragment:
        raise CleanupError("GitHub API URL is invalid")
    return value.rstrip("/")


def github_host(api_url: str) -> str:
    hostname = urllib.parse.urlparse(api_url).hostname
    return "github.com" if hostname == "api.github.com" else str(hostname)


def remote_repository(
    repository: Path,
    remote: str,
    expected_host: str,
) -> tuple[str, str]:
    rewrites = git_with_status(
        repository,
        "config",
        "--get-regexp",
        r"^url\..*\.(insteadOf|pushInsteadOf)$",
    )
    if rewrites.returncode == 0:
        raise CleanupError("Git URL rewriting must be disabled for safe cleanup")
    if rewrites.returncode != 1:
        raise CleanupError("could not inspect Git URL rewrite configuration")
    values = git(repository, "remote", "get-url", "--push", "--all", remote).splitlines()
    if len(values) != 1:
        raise CleanupError("Git remote must have exactly one effective push URL")
    value = values[0]
    if value.startswith("git@") and ":" in value:
        host, path = value.removeprefix("git@").split(":", 1)
    else:
        parsed = urllib.parse.urlparse(value)
        host = parsed.hostname or ""
        path = parsed.path.lstrip("/")
    if host.lower() != expected_host.lower():
        raise CleanupError("local Git remote is not hosted by the GitHub API host")
    path = path.removesuffix(".git").strip("/")
    if REPOSITORY_PATTERN.fullmatch(path) is None:
        raise CleanupError("local Git remote does not identify one GitHub repository")
    return path, value


def github_json(
    api_url: str,
    token: str,
    path: str,
) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{api_url}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        raise CleanupError(f"GitHub API request failed with HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise CleanupError(f"GitHub API request failed: {error.reason}") from error
    if not body:
        return {}
    try:
        value = json.loads(body)
    except json.JSONDecodeError as error:
        raise CleanupError("GitHub API returned invalid JSON") from error
    if not isinstance(value, dict):
        raise CleanupError("GitHub API returned an unexpected response")
    return value


def require_merged_pr(
    api_url: str,
    token: str,
    github_repository: str,
    pull_request: int,
    branch: str,
    local_head: str,
) -> None:
    repository_path = urllib.parse.quote(github_repository, safe="/")
    value = github_json(
        api_url,
        token,
        f"/repos/{repository_path}/pulls/{pull_request}",
    )
    head = value.get("head")
    head_repository = head.get("repo") if isinstance(head, dict) else None
    if value.get("merged_at") is None or value.get("state") != "closed":
        raise CleanupError("pull request is not merged; preserve the branch and worktree")
    if (
        not isinstance(head, dict)
        or head.get("ref") != branch
        or head.get("sha") != local_head
        or not isinstance(head_repository, dict)
        or head_repository.get("full_name") != github_repository
    ):
        raise CleanupError(
            "local branch does not match the merged pull request head; preserve it"
        )


def delete_remote_branch(
    repository: Path,
    remote_url: str,
    branch: str,
    merged_head: str,
) -> None:
    full_ref = f"refs/heads/{branch}"
    observed = git_with_status(
        repository,
        "ls-remote",
        "--exit-code",
        "--heads",
        remote_url,
        full_ref,
    )
    if observed.returncode == 2:
        return
    if observed.returncode != 0:
        detail = observed.stderr.strip() or observed.stdout.strip()
        raise CleanupError(detail or "could not read remote batch branch")
    fields = observed.stdout.split()
    if len(fields) != 2 or fields != [merged_head, full_ref]:
        raise CleanupError("remote batch branch advanced after merge; preserve it")
    deletion = git_with_status(
        repository,
        "push",
        f"--force-with-lease={full_ref}:{merged_head}",
        remote_url,
        f":{full_ref}",
    )
    if deletion.returncode != 0:
        raise CleanupError(
            "remote batch branch changed during cleanup; preserve local work"
        )


def cleanup(
    repository: Path,
    worktree: Path,
    branch: str,
    github_repository: str,
    pull_request: int,
    remote: str,
    api_url: str,
    github_host_name: str | None,
    token: str,
) -> None:
    repository = repository.resolve()
    worktree = worktree.resolve()
    if not repository.is_dir():
        raise CleanupError(f"repository does not exist: {repository}")
    if not worktree.is_dir():
        raise CleanupError(f"worktree does not exist: {worktree}")
    if repository == worktree:
        raise CleanupError("refusing to remove the repository worktree")
    if REPOSITORY_PATTERN.fullmatch(github_repository) is None:
        raise CleanupError("GitHub repository must be owner/name")
    if pull_request < 1:
        raise CleanupError("pull request number must be positive")
    if not token:
        raise CleanupError("GH_TOKEN or GITHUB_TOKEN is required")

    api_url = validated_api_url(api_url)
    expected_host = github_host_name or github_host(api_url)
    if not expected_host or "/" in expected_host or ":" in expected_host:
        raise CleanupError("GitHub host is invalid")
    git(repository, "check-ref-format", "--branch", branch)
    remote_name, remote_url = remote_repository(repository, remote, expected_host)
    if remote_name.lower() != github_repository.lower():
        raise CleanupError("local Git remote and GitHub repository do not match")
    if common_git_directory(repository) != common_git_directory(worktree):
        raise CleanupError("worktree belongs to a different repository")
    registrations = registered_worktrees(repository)
    if registrations.get(worktree) != branch:
        raise CleanupError("worktree is not registered to the requested branch")
    if [path for path, registered in registrations.items() if registered == branch] != [
        worktree
    ]:
        raise CleanupError("branch is registered to another worktree")

    status = git(worktree, "status", "--porcelain", "--ignored=matching")
    if status:
        raise CleanupError(
            "worktree has modified, untracked, or ignored files; preserve it for recovery"
        )
    local_head = git(worktree, "rev-parse", "HEAD")
    if SHA_PATTERN.fullmatch(local_head) is None:
        raise CleanupError("local branch head is invalid")
    if git(repository, "rev-parse", f"refs/heads/{branch}") != local_head:
        raise CleanupError("local branch ref does not match the worktree head")

    require_merged_pr(
        api_url,
        token,
        github_repository,
        pull_request,
        branch,
        local_head,
    )
    delete_remote_branch(repository, remote_url, branch, local_head)
    try:
        git(repository, "worktree", "remove", "--", str(worktree))
        git(
            repository,
            "update-ref",
            "-d",
            f"refs/heads/{branch}",
            local_head,
        )
    except CleanupError as error:
        raise PartialCleanupError(
            f"remote branch removed; local cleanup remains incomplete: {error}"
        ) from error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--github-repository", required=True)
    parser.add_argument("--pull-request", type=int, required=True)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--api-url", default="https://api.github.com")
    parser.add_argument("--github-host")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    try:
        cleanup(
            args.repository,
            args.worktree,
            args.branch,
            args.github_repository,
            args.pull_request,
            args.remote,
            args.api_url,
            args.github_host,
            token,
        )
    except PartialCleanupError as error:
        print(f"CLEANUP PARTIAL: {error}", file=sys.stderr)
        return 2
    except CleanupError as error:
        print(f"CLEANUP REFUSED: {error}", file=sys.stderr)
        return 1
    print(f"LANDED BATCH CLEANED: {args.branch} ({args.worktree.resolve()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
