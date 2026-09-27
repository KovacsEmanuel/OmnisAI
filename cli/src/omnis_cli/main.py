"""Operator-facing console script."""

import argparse

from .status import status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omnis")
    commands = parser.add_subparsers(dest="command", required=True)
    status_parser = commands.add_parser("status", help="Read private local instance status")
    status_parser.add_argument(
        "--json", action="store_true", help="Sanitized machine-readable status"
    )
    args = parser.parse_args(argv)
    if args.command == "status":
        return status(as_json=args.json)
    return 2


def entrypoint() -> None:
    raise SystemExit(main())
