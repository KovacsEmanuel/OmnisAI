"""Fixed DB-only Stop reconciliation job. Host attestation remains the host's job.

Input is one JSON document on stdin, terminated by EOF, at most 16 KiB. No
Docker access, arbitrary SQL, input paths or command arguments are supported.
"""

import asyncio
import json
import os
import re
import select
import signal
import sys
import time
from types import FrameType
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError

from omnis.core.db import database_engine
from omnis.modules.instance.domain import ControlConflict
from omnis.modules.instance.service import InstanceService
from omnis.modules.instance.stop_contract import StopReconciliation
from omnis.transport.local_control import unique_object

MAX_INPUT_BYTES = 16 * 1024
INPUT_SECONDS = 3.0
JOB_SECONDS = 15


def read_request(fd: int = 0) -> StopReconciliation:
    deadline = time.monotonic() + INPUT_SECONDS
    data = bytearray()
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
            raise TimeoutError("Reconciliation input deadline")
        chunk = os.read(fd, min(4096, MAX_INPUT_BYTES + 1 - len(data)))
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > MAX_INPUT_BYTES:
            raise ValueError("Reconciliation input too large")
    return StopReconciliation.model_validate(
        json.loads(data.decode("utf-8"), object_pairs_hook=unique_object)
    )


async def execute(request: StopReconciliation) -> dict[str, object]:
    expected = os.environ.get("OMNIS_EXPECTED_SYSTEM_ID", "")
    database_url = os.environ.get("OMNIS_DATABASE_URL", "")
    if not re.fullmatch(r"[0-9]{1,20}", expected) or expected != request.system_identifier:
        raise ValueError("Reconciliation cluster identity required")
    # Same URL validation and ambient PG* rejection as the migrator. Configuration
    # stays in the protected process environment, never argv/stdout/errors.
    engine = database_engine(database_url)
    try:
        async with asyncio.timeout(10):
            return await InstanceService(engine).reconcile_stop(request)
    finally:
        async with asyncio.timeout(2):
            await engine.dispose()


def main() -> int:
    correlation = str(uuid4())

    def deadline(_signum: int, _frame: FrameType | None) -> None:
        # Hard backstop includes blocked stdin, cancellation/disposal and output.
        # No traceback or configuration escapes even if an async client stalls.
        message = json.dumps(
            {"ok": False, "correlation_id": correlation, "error": "RECONCILIATION_TIMEOUT"}
        )
        try:
            os.set_blocking(1, False)
            os.write(1, message.encode() + b"\n")
        finally:
            os._exit(4)

    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(JOB_SECONDS)
    try:
        if len(sys.argv) != 1:
            raise ValueError("Arguments forbidden")
        request = read_request()
        correlation = str(request.reconciliation_id)
        receipt = asyncio.run(execute(request))
        response: dict[str, object] = {
            "ok": True,
            "correlation_id": correlation,
            "receipt": receipt,
        }
        result = 0
    except TimeoutError:
        response = {"ok": False, "correlation_id": correlation, "error": "RECONCILIATION_TIMEOUT"}
        result = 4
    except (ValueError, RecursionError, OSError):
        response = {"ok": False, "correlation_id": correlation, "error": "INVALID_RECONCILIATION"}
        result = 4
    except ControlConflict:
        response = {"ok": False, "correlation_id": correlation, "error": "RECONCILIATION_REFUSED"}
        result = 4
    except SQLAlchemyError:
        response = {
            "ok": False,
            "correlation_id": correlation,
            "error": "RECONCILIATION_UNAVAILABLE",
        }
        result = 4
    try:
        sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
        sys.stdout.flush()
    except (OSError, ValueError):
        return 4
    finally:
        signal.alarm(0)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
