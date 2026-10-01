"""TTY-only issuer for the already installed private pairing protocol."""

import hashlib
import secrets
import sys
from uuid import uuid4

from .control import ControlUnavailable, request
from .lifecycle import StartError
from .verified import verified_instance


def pair(*, as_json: bool = False) -> int:
    # No code may exist before the disclosure channel is proven interactive.
    if as_json:
        print("PAIRING_FORMAT_REFUSED: codul nu este disponibil în JSON.", file=sys.stderr)
        return 2
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("PAIRING_TTY_REQUIRED: folosiți un terminal interactiv.", file=sys.stderr)
        return 2
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
            try:
                if sys.stdout.write(message) != len(message):
                    raise OSError("Short TTY write")
                sys.stdout.flush()
            except (OSError, UnicodeError):
                # A partial write may already have disclosed the code; never
                # state that it was not shown or retry issuance automatically.
                print(
                    "PAIRING_DISPLAY_UNCERTAIN: verificați terminalul; nu reutilizați codul.",
                    file=sys.stderr,
                )
                return 4
            return 0
    except StartError as exc:
        print(f"{exc.reason}: codul nu a fost afișat.", file=sys.stderr)
        return exc.code
    except (ControlUnavailable, OSError, ValueError):
        print("PAIRING_UNAVAILABLE: codul nu a fost afișat.", file=sys.stderr)
        return 3
