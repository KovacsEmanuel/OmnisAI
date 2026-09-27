"""Separate inert supervisor. Startup acquires authority; it never opens admission."""

import asyncio
import os
import signal
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError

from omnis.core.db import database_engine, readiness_reason
from omnis.modules.instance.domain import ControlConflict
from omnis.modules.instance.service import InstanceService
from omnis.transport.local_control import LocalControl


async def run() -> None:
    raw_url = os.environ.get("OMNIS_DATABASE_URL")
    raw_directory = os.environ.get("OMNIS_CONTROL_DIR")
    if not raw_url or not raw_directory:
        raise ValueError("Explicit database and control directory required")
    engine = database_engine(raw_url)
    service = InstanceService(engine)
    owner = uuid4()
    epoch = None
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    try:
        if await readiness_reason(engine) is not None:
            raise ValueError("Control schema unavailable")
        epoch = await service.acquire(owner)
        async with LocalControl(Path(raw_directory), service, owner, epoch):
            await service.quiesce(owner, epoch)
            print("SUPERVISOR_READY", flush=True)
            while not stop.is_set():
                try:
                    await asyncio.wait_for(stop.wait(), timeout=1)
                except TimeoutError:
                    if await readiness_reason(engine) is not None:
                        raise ValueError("Control schema unavailable") from None
                    await service.heartbeat(owner, epoch)
                    await service.quiesce(owner, epoch)
    finally:
        try:
            if epoch is not None:
                await service.release(owner, epoch)
        finally:
            await engine.dispose()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.remove_signal_handler(sig)


def main() -> int:
    try:
        asyncio.run(run())
    except (OSError, ValueError, TimeoutError, SQLAlchemyError, ControlConflict):
        # Never print DSNs, raw SQL parameters, capabilities or request content.
        print("SUPERVISOR_UNAVAILABLE", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
