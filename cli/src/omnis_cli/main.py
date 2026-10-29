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
        help="Headless startup; use omnis pair/open separately",
    )
    start_parser.add_argument(
        "--port", type=int, help="Explicit loopback port for a new, stopped instance"
    )
    start_parser.add_argument("--json", action="store_true", help="Sanitized startup result")
    start_parser.add_argument("--startup-timeout", type=int, help="Startup budget, 30–300 seconds")
    start_parser.add_argument(
        "--cleanup-timeout", type=int, help="Separate cleanup budget, 30–180 seconds"
    )
    pair_parser = commands.add_parser("pair", help="Emit a one-use code on a private TTY")
    pair_parser.add_argument("--json", action="store_true", help="Refused: pairing is TTY-only")
    commands.add_parser("open", help="Open the verified, ready installed dashboard")
    stop_parser = commands.add_parser("stop", help="Stop this installed instance and keep its data")
    stop_parser.add_argument("--json", action="store_true", help="Sanitized shutdown result")
    stop_parser.add_argument("--shutdown-timeout", type=int, help="Shutdown budget, 15–180 seconds")
    recover_parser = commands.add_parser("recover", help="Recover a dead T1 supervisor to STOPPED")
    recover_parser.add_argument("--json", action="store_true", help="Sanitized recovery result")
    backup_parser = commands.add_parser("backup", help="Cold STOPPED snapshot (T1: at most 1 GiB)")
    backup_parser.add_argument("--output", type=Path, required=True)
    restore_parser = commands.add_parser(
        "restore", help="Restore into a new XDG state root; leave STOPPED"
    )
    restore_parser.add_argument("--backup", type=Path, required=True)
    restore_parser.add_argument("--master-key-file", type=Path)
    image_parser = commands.add_parser(
        "install-image", help="Explicitly build the pinned local images"
    )
    image_parser.add_argument(
        "--runtime-context", type=Path, help="Prepared native input for p4a-settings-offline only"
    )
    upgrade_parser = commands.add_parser(
        "upgrade", help="Explicit stopped T1 0016 to 0017 transition"
    )
    upgrade_parser.add_argument("--bundle", type=Path, required=True)
    upgrade_parser.add_argument("--backup", type=Path, required=True)
    upgrade_parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "upgrade":
        from .upgrade import upgrade_command

        return upgrade_command(args.bundle, args.backup, as_json=args.json)
    try:
        config = load_config()
        if args.command in {
            None,
            "start",
            "stop",
            "recover",
            "status",
            "pair",
            "open",
            "backup",
            "restore",
        }:
            config.check_instance(state_dir(), getattr(args, "port", None))
    except StartError as exc:
        if getattr(args, "json", False):
            result: dict[str, object] = {
                "state": "REFUSED",
                "reason": exc.reason,
                "dashboard_ready": False,
                "assessment_ready": False,
                "browser_opened": False,
            }
            if args.command == "start" and not args.no_open:
                result["browser_outcome"] = "BROWSER_NOT_INVOKED"
            print(json.dumps(result, sort_keys=True))
        else:
            print(f"{exc.reason}: verificați configurația non-secretă privată.", file=sys.stderr)
        return exc.code
    if args.command is None or (args.command == "start" and not args.no_open):
        as_json = getattr(args, "json", False)
        code, result = (
            start_result(None)
            if args.command is None
            else start_result(
                args.port,
                startup_timeout=args.startup_timeout,
                cleanup_timeout=args.cleanup_timeout,
            )
        )
        if code:
            if as_json:
                print(
                    json.dumps({**result, "browser_outcome": "BROWSER_NOT_INVOKED"}, sort_keys=True)
                )
            else:
                print(f"{result['reason']}: browserul nu a fost invocat.", file=sys.stderr)
            return code
        if not as_json and result.get("reused") is False and interactive_tty():
            issuance = pair()
            if issuance:
                return issuance  # Services remain READY; never open after uncertain disclosure.
        if as_json:
            return open_verified(expected=result, as_json=True)
        return open_verified(expected=result)
    if args.command == "start":
        return start(
            port=args.port,
            as_json=args.json,
            startup_timeout=args.startup_timeout,
            cleanup_timeout=args.cleanup_timeout,
        )
    if args.command == "backup":
        from .backup import cold_command

        return cold_command("backup", args.output)
    if args.command == "restore":
        from .backup import cold_command

        return cold_command("restore", args.backup, args.master_key_file)
    if args.command == "status":
        return status(as_json=args.json)
    if args.command == "pair":
        return pair(as_json=args.json)
    if args.command == "open":
        return open_verified()
    if args.command == "stop":
        return stop(as_json=args.json, shutdown_timeout=args.shutdown_timeout)
    if args.command == "recover":
        return stop(as_json=args.json, recover=True)
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
        print("Release Omnis instalat; pregătiți explicit imaginea, apoi omnis start --no-open.")
        return 0
    if args.command == "install-image":
        data_home = os.environ.get("XDG_DATA_HOME")
        root = Path(data_home) if data_home else Path.home() / ".local/share"
        try:
            receipt = install_control_image(root, runtime_context=args.runtime_context)
        except ImageInstallError:
            print("IMAGE_INSTALL_REFUSED: verificați releaseul și Docker local.", file=sys.stderr)
            return 2
        print(f"Control image instalată: {receipt.image_id}; serviciile nu au fost pornite.")
        return 0
    return 2


def entrypoint() -> None:
    raise SystemExit(main())
