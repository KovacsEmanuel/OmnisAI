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
from omnis.supervisor.runtime_client import RuntimeClient
from omnis.transport.local_control import LocalControl


async def run() -> None:
    raw_url = os.environ.get("OMNIS_DATABASE_URL")
    raw_directory = os.environ.get("OMNIS_CONTROL_DIR")
    if not raw_url or not raw_directory:
        raise ValueError("Explicit database and control directory required")
    raw_runtime = os.environ.get("OMNIS_RUNTIME_DIR")
    probe = os.environ.get("OMNIS_RUNTIME_INERT_PROBE")
    if probe not in {None, "1"} or (probe is not None and not raw_runtime):
        raise ValueError("Invalid explicit runtime opt-in")
    if raw_runtime is not None and (not raw_runtime or Path(raw_runtime) == Path(raw_directory)):
        raise ValueError("Runtime requires a distinct private directory")
    runtime: RuntimeClient | None = None
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
        if raw_runtime is not None:
            status = await service.owned_status(owner, epoch)
            runtime = RuntimeClient(Path(raw_runtime), generation=status.generation, epoch=epoch)
            await runtime.connect()
            service.runtime_drain = runtime.drain
            if probe == "1":
                await runtime.launch_inert(service, owner)
                # Startup consumed the initial grant; refresh CURRENT authority
                # before entering the ordinary heartbeat interval.
                await service.heartbeat(owner, epoch)
                await runtime.renew(service, owner)
            else:
                await runtime.status()
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
                    if runtime is not None:
                        runtime_state = (await runtime.status())["state"]
                        if runtime_state == "READY":
                            await runtime.renew(service, owner)
                        elif probe == "1":
                            observed = await service.owned_status(owner, epoch)
                            if (
                                runtime_state != "STOPPED"
                                or observed.shutdown_command_id is None
                                or observed.quiesced_generation != observed.generation
                            ):
                                raise ValueError("Runtime unavailable") from None
    finally:
        try:
            if runtime is not None:
                try:
                    if not await runtime.drain():
                        raise ValueError("Runtime drain uncertain")
                finally:
                    await runtime.close()
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
