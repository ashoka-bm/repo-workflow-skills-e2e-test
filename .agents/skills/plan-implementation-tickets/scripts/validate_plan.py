#!/usr/bin/env python3
"""Validate a planning or implementation GitHub publication preview."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from workflow_plan_validation import publication_preview_validation_errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    args = parser.parse_args()
    try:
        value = json.loads(args.plan.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"cannot read plan: {error}", file=sys.stderr)
        return 1
    if not isinstance(value, dict):
        print("plan must contain one JSON object", file=sys.stderr)
        return 1
    errors = publication_preview_validation_errors(value)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
