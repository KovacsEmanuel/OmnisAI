"""Operator-facing console script."""

import argparse
import json
import os
import sys
from pathlib import Path

from .browser import open_verified
from .compose import ImageInstallError, install_control_image
from .config import load_config
from .instance import state_dir
from .lifecycle import StartError
from .pairing import interactive_tty, pair
from .release import ReleaseError, install_release
from .start import start, start_result
from .status import status
from .stop import stop


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omnis")
    commands = parser.add_subparsers(dest="command")
    status_parser = commands.add_parser("status", help="Read private local instance status")
    status_parser.add_argument(
        "--json", action="store_true", help="Sanitized machine-readable status"
    )
    install_parser = commands.add_parser("install", help="Install an explicit local release bundle")
    install_parser.add_argument(
        "--bundle", type=Path, required=True, help="Absolute bundle directory"
    )
    start_parser = commands.add_parser(
        "start", help="Start and verify the installed inert control plane"
    )
    start_parser.add_argument(
        "--no-open",
        action="store_true",
        required=True,
        help="Headless startup; use omnis pair/open separately",
    )
    start_parser.add_argument(
        "--port", type=int, help="Explicit loopback port for a new, stopped instance"
    )
    start_parser.add_argument("--json", action="store_true", help="Sanitized startup result")
    start_parser.add_argument("--startup-timeout", type=int, help="Startup budget, 30–300 seconds")
    pair_parser = commands.add_parser("pair", help="Emit a one-use code on a private TTY")
    pair_parser.add_argument("--json", action="store_true", help="Refused: pairing is TTY-only")
    commands.add_parser("open", help="Open the verified, ready installed dashboard")
    stop_parser = commands.add_parser("stop", help="Stop this installed instance and keep its data")
    stop_parser.add_argument("--json", action="store_true", help="Sanitized shutdown result")
    commands.add_parser("install-image", help="Explicitly build the pinned local control image")
    args = parser.parse_args(argv)
    try:
        config = load_config()
        if args.command in {None, "start", "stop", "status", "pair", "open"}:
            config.check_instance(state_dir(), getattr(args, "port", None))
    except StartError as exc:
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "state": "REFUSED",
                        "reason": exc.reason,
                        "dashboard_ready": False,
                        "assessment_ready": False,
                        "browser_opened": False,
                    },
                    sort_keys=True,
                )
            )
        else:
            print(f"{exc.reason}: verificați configurația non-secretă privată.", file=sys.stderr)
        return exc.code
    if args.command is None:
        code, result = start_result(None)
        if code:
            print(f"{result['reason']}: browserul nu a fost invocat.", file=sys.stderr)
            return code
        if result.get("reused") is False and interactive_tty():
            issuance = pair()
            if issuance:
                return issuance  # Services remain READY; never open after uncertain disclosure.
        return open_verified(expected=result)
    if args.command == "start":
        return start(port=args.port, as_json=args.json, startup_timeout=args.startup_timeout)
    if args.command == "status":
        return status(as_json=args.json)
    if args.command == "pair":
        return pair(as_json=args.json)
    if args.command == "open":
        return open_verified()
    if args.command == "stop":
        return stop(as_json=args.json)
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
        print(
            "Release Omnis 0.1.0 instalat; pregătiți explicit imaginea, apoi omnis start --no-open."
        )
        return 0
    if args.command == "install-image":
        data_home = os.environ.get("XDG_DATA_HOME")
        root = Path(data_home) if data_home else Path.home() / ".local/share"
        try:
            receipt = install_control_image(root)
        except ImageInstallError:
            print("IMAGE_INSTALL_REFUSED: verificați releaseul și Docker local.", file=sys.stderr)
            return 2
        print(f"Control image instalată: {receipt.image_id}; serviciile nu au fost pornite.")
        return 0
    return 2


def entrypoint() -> None:
    raise SystemExit(main())
