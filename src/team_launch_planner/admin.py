import argparse
from collections.abc import Sequence


COMMANDS = {
    "migrate": "apply or inspect database migrations",
    "tokens": "manage local access tokens",
    "export": "export versioned launch data",
    "backup": "back up or restore the service database",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="team-launch-admin",
        description="Administrative shell for Team Launch Planner.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in COMMANDS.items():
        commands.add_parser(name, help=help_text, description=help_text)
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    parser = build_parser()
    parsed = parser.parse_args(arguments)
    parser.error(f"{parsed.command} is reserved but not implemented yet")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
