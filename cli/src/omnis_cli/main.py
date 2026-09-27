"""Operator-facing console script."""

import argparse
import os
import sys
from pathlib import Path

from .release import ReleaseError, install_release
from .status import status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omnis")
    commands = parser.add_subparsers(dest="command", required=True)
    status_parser = commands.add_parser("status", help="Read private local instance status")
    status_parser.add_argument(
        "--json", action="store_true", help="Sanitized machine-readable status"
    )
    install_parser = commands.add_parser("install", help="Install an explicit local release bundle")
    install_parser.add_argument(
        "--bundle", type=Path, required=True, help="Absolute bundle directory"
    )
    args = parser.parse_args(argv)
    if args.command == "status":
        return status(as_json=args.json)
    if args.command == "install":
        data_home = os.environ.get("XDG_DATA_HOME")
        root = Path(data_home) if data_home else Path.home() / ".local/share"
        try:
            install_release(args.bundle, root)
        except ReleaseError:
            print(
                "RELEASE_INSTALL_REFUSED: verificați bundleul și directorul XDG privat.",
                file=sys.stderr,
            )
            return 2
        print("Release Omnis 0.1.0 instalat; pornirea serviciilor nu este încă implementată.")
        return 0
    return 2


def entrypoint() -> None:
    raise SystemExit(main())
