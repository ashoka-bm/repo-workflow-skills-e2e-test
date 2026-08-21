#!/usr/bin/env python3
"""Fail unless a pull request's current commit has valid evidence and independent review."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from queue_landing import (
    GitHub,
    QueueLandingError,
    REPOSITORY_PATTERN,
    authorized_maintainers,
    configured_base_branch,
    enforce_landing_order,
    github_state_config,
    landing_pulls,
    merged_batches,
    one_landing_batch,
    stack_dependencies,
    validate_landing_evidence,
)


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
        pull = github.get_pull(args.pull_request)
        if pull.get("state") != "open":
            raise QueueLandingError("pull request must be open")
        config = github_state_config(args.config)
        validate_landing_evidence(
            github,
            args.pull_request,
            pull,
            authorized_maintainers(args.config),
        )
        pull_values = github.all_pulls()
        pulls = landing_pulls(pull_values, github.repository_name)
        if args.pull_request not in pulls:
            raise QueueLandingError(
                "pull request is missing from the open landing PR listing"
            )
        stack = stack_dependencies(
            pulls, {args.pull_request}, github.repository_name
        )
        direct_predecessor_batches = {
            one_landing_batch(pulls[predecessor], github.repository_name)
            for predecessor in stack[args.pull_request]
        }
        landed = merged_batches(
            pull_values,
            github.repository_name,
            configured_base_branch(config),
        )
        enforce_landing_order(
            github,
            one_landing_batch(pull, github.repository_name),
            landed,
            direct_predecessor_batches,
        )
    except QueueLandingError as error:
        print(f"LANDING EVIDENCE INVALID: {error}", file=sys.stderr)
        return 1
    print(f"LANDING EVIDENCE VALID: pull_request={args.pull_request}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
