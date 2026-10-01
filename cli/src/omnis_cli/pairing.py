"""TTY-only issuer for the already installed private pairing protocol."""

import hashlib
import secrets
import sys
from uuid import uuid4

from .control import ControlUnavailable, request
from .lifecycle import StartError
from .verified import verified_instance


def interactive_tty() -> bool:
    """A failed terminal probe is not permission to create or disclose a code."""
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (OSError, ValueError, AttributeError):
        return False


def _uncertain_disclosure() -> int:
    print(
        "PAIRING_DISPLAY_UNCERTAIN: verificați terminalul; nu reutilizați codul.",
        file=sys.stderr,
    )
    return 4


def pair(*, as_json: bool = False) -> int:
    # No code may exist before the disclosure channel is proven interactive.
    if as_json:
        print("PAIRING_FORMAT_REFUSED: codul nu este disponibil în JSON.", file=sys.stderr)
        return 2
    if not interactive_tty():
        print("PAIRING_TTY_REQUIRED: folosiți un terminal interactiv.", file=sys.stderr)
        return 2
    disclosure_started = False
    try:
        with verified_instance() as (ready, control):
            code = secrets.token_urlsafe(24)
            reply = request(
                control,
                {
                    "op": "pairing",
                    "instance_id": ready["instance_id"],
                    "issuance_id": str(uuid4()),
                    "digest": hashlib.sha256(code.encode()).hexdigest(),
                },
            )
            if (
                reply["instance_id"] != ready["instance_id"]
                or reply["generation"] != ready["generation"]
                or reply["supervisor_epoch"] != ready["supervisor_epoch"]
                or reply["admission_open"] is not True
                or reply["shutdown_command_id"] is not None
            ):
                raise StartError("PAIRING_STATE_CHANGED", 4)
            message = f"Cod pairing Omnis (expiră în 5 minute): {code}\n"
            disclosure_started = True
            if sys.stdout.write(message) != len(message):
                raise OSError("Short TTY write")
            sys.stdout.flush()
            return 0
    except BaseException as exc:
        # Includes a context-manager finalizer or SIGINT after the first byte.
        # Once disclosure starts, no exception may claim the code was unseen.
        if disclosure_started:
            return _uncertain_disclosure()
        if isinstance(exc, StartError):
            print(f"{exc.reason}: codul nu a fost afișat.", file=sys.stderr)
            return exc.code
        if isinstance(exc, (ControlUnavailable, OSError, ValueError)):
            print("PAIRING_UNAVAILABLE: codul nu a fost afișat.", file=sys.stderr)
            return 3
        if isinstance(exc, KeyboardInterrupt):
            print("PAIRING_INTERRUPTED: codul nu a fost afișat.", file=sys.stderr)
            return 3
        raise
