"""Separate inert supervisor. Startup acquires authority; it never opens admission."""

import asyncio
import os
import signal
import sys
from contextlib import suppress
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError

from omnis.core.db import database_engine, readiness_reason
from omnis.modules.engagements.service import EngagementNotFound, EngagementService
from omnis.modules.instance.domain import ControlConflict
from omnis.modules.instance.service import InstanceService
from omnis.supervisor.case_slot import CaseSlot
from omnis.supervisor.runtime_client import RuntimeClient, RuntimeUnavailable
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
    raw_catalog = os.environ.get("OMNIS_NATIVE_PREPARATION_CATALOG_ROOT")
    managed_opt_in = os.environ.get("OMNIS_MANAGED_TASKS")
    if managed_opt_in not in {None, "1"} or (managed_opt_in == "1" and not raw_catalog):
        raise ValueError("Managed tasks require explicit native preparation opt-in")
    catalog_root = None
    if raw_catalog is not None:
        normal_model_test = (
            os.environ.get("OMNIS_MODEL_TEST_SOURCE_ROOT") == "/opt/omnis/model-test"
        )
        if not raw_catalog or not raw_runtime or (probe != "1" and not normal_model_test):
            raise ValueError("Invalid explicit native preparation opt-in")
        from omnis.modules.runs.native_preparation import existing_private_root

        catalog_root = existing_private_root(Path(raw_catalog))
        if str(catalog_root) != raw_catalog:
            raise ValueError("Invalid explicit native preparation opt-in")
    raw_case = os.environ.get("OMNIS_RUNTIME_CASE_ID")
    raw_state = os.environ.get("OMNIS_RUNTIME_STATE_ROOT")
    case_id = None
    if raw_case is not None or raw_state is not None:
        if not raw_case or not raw_state or probe != "1":
            raise ValueError("Invalid paired case opt-in")
        case_id = UUID(raw_case)
        if (
            str(case_id) != raw_case
            or not Path(raw_state).is_absolute()
            or str(Path(raw_state)) != raw_state
        ):
            raise ValueError("Invalid case identity")
    slot: CaseSlot | None = None
    nominal_close = False
    runtime: RuntimeClient | None = None
    engine = database_engine(raw_url)
    service = InstanceService(engine)
    owner = uuid4()
    epoch = None
    task_owner = None
    provider_owner = None
    startup_generation = None
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    try:
        if await readiness_reason(engine) is not None:
            raise ValueError("Control schema unavailable")
        epoch = await service.acquire(owner)
        raw_vault = os.environ.get("OMNIS_VAULT_DIR")
        raw_keys = os.environ.get("OMNIS_VAULT_KEY_DIR")
        if raw_vault is not None or raw_keys is not None:
            if not raw_vault or not raw_keys or raw_runtime is not None:
                raise ValueError("API-key Settings requires distinct explicit owner-only storage")
            from omnis.modules.settings.provider_key_service import ProviderSettingsOwner
            from omnis.modules.settings.provider_vault import ProviderVault

            identity = str((await service.owned_status(owner, epoch)).instance_id)
            provider_owner = ProviderSettingsOwner(
                service, owner, epoch, ProviderVault(Path(raw_vault), Path(raw_keys), identity)
            )
            service.runtime_drain = provider_owner.drain
        if raw_runtime is not None:
            status = await service.owned_status(owner, epoch)
            startup_generation = status.generation
            runtime = RuntimeClient(Path(raw_runtime), generation=status.generation, epoch=epoch)
            await runtime.connect()
            service.runtime_drain = runtime.drain
            if probe == "1":
                if case_id is not None and raw_state is not None:
                    if (await runtime.status())["state"] != "IDLE":
                        raise ValueError("Fresh runtime boot required")
                    await EngagementService(engine).read(case_id)
                    slot = CaseSlot(
                        Path(raw_state),
                        case_id,
                        status.instance_id,
                        owner,
                        epoch,
                        status.generation,
                        runtime.boot,
                    )
                    await slot.prepare(service)
                launched = await runtime.launch_inert(service, owner)
                # Startup consumed the initial grant; refresh CURRENT authority
                # before entering the ordinary heartbeat interval.
                await service.heartbeat(owner, epoch)
                await runtime.renew(service, owner)
                if slot is not None:
                    await slot.observe(launched)
            else:
                await runtime.status()
        preparation = None

        if catalog_root is not None and runtime is not None:
            from omnis.modules.runs.native_preparation import NativePreparation

            preparation = NativePreparation(engine, catalog_root, service, owner, epoch, runtime)
            if managed_opt_in == "1":
                from omnis.modules.runs.managed_admission import ManagedAdmission
                from omnis.supervisor.native_tasks import NativeTaskOwner

                task_owner = NativeTaskOwner(
                    ManagedAdmission(engine, catalog_root), service, owner, epoch, runtime
                )
        # Drain inherited shutdown before exposing this fresh process owner.
        await service.quiesce(owner, epoch)
        if task_owner is not None and runtime is not None:

            async def drain_model_test() -> bool:
                assert runtime is not None and task_owner is not None
                await task_owner.close_model_test()
                return await runtime.drain()

            service.runtime_drain = drain_model_test
        async with LocalControl(
            Path(raw_directory),
            service,
            owner,
            epoch,
            native_prepare=preparation.prepare if preparation is not None else None,
            native_task=task_owner.handle if task_owner is not None else None,
        ) as control:
            if provider_owner is not None:
                from omnis.modules.settings.provider_key_models import KeySettingsControl

                async def provider_command(command: KeySettingsControl) -> dict[str, object]:
                    assert provider_owner is not None
                    return (await provider_owner.handle(command)).model_dump(mode="json")

                control.provider_settings = provider_command
            if task_owner is not None:
                control.model_test = task_owner.model_test
            if runtime is not None and probe is None:
                from omnis.modules.settings.provider_models import SettingsControl

                settings_runtime = runtime

                async def settings_command(command: SettingsControl) -> dict[str, object]:
                    assert epoch is not None
                    await service.owned_status(owner, epoch)
                    if command.command is None:
                        return await settings_runtime.settings_status(command.operation_id)
                    return await settings_runtime.settings(
                        service, owner, command.command.model_dump(mode="json")
                    )

                control.settings = settings_command
            print("SUPERVISOR_READY", flush=True)
            while not stop.is_set():
                try:
                    await asyncio.wait_for(stop.wait(), timeout=1)
                except TimeoutError:
                    phase = "READINESS"
                    try:
                        if await readiness_reason(engine) is not None:
                            raise ValueError("Control schema unavailable") from None
                        phase = "HEARTBEAT"
                        await service.heartbeat(owner, epoch)
                        phase = "QUIESCE"
                        # The startup generation was already drained without closing this owner.
                        if (
                            task_owner is None
                            or (await service.owned_status(owner, epoch)).generation
                            != startup_generation
                        ):
                            await service.quiesce(owner, epoch)
                        if runtime is not None:
                            phase = "RUNTIME_STATUS"
                            runtime_state = (await runtime.status())["state"]
                            if runtime_state == "READY":
                                phase = "RENEW"
                                await runtime.renew(service, owner)
                            elif runtime_state == "MANAGEMENT":
                                phase = "RENEW"
                                await runtime.renew(service, owner, management=True)
                            elif probe == "1":
                                observed = await service.owned_status(owner, epoch)
                                if (
                                    runtime_state != "STOPPED"
                                    or observed.shutdown_command_id is None
                                    or observed.quiesced_generation != observed.generation
                                ):
                                    raise ValueError("Runtime unavailable") from None
                    except BaseException as error:
                        # Observe before LocalControl exit or drain can mask the first failure.
                        with suppress(BaseException):
                            kind = next(
                                (
                                    label
                                    for cls, label in (
                                        (asyncio.CancelledError, "CANCELLED"),
                                        (TimeoutError, "TIMEOUT"),
                                        (RuntimeUnavailable, "RUNTIME_UNAVAILABLE"),
                                        (ControlConflict, "CONTROL_CONFLICT"),
                                        (SQLAlchemyError, "DB_ERROR"),
                                        (OSError, "OS_ERROR"),
                                        (ValueError, "VALUE_ERROR"),
                                    )
                                    if isinstance(error, cls)
                                ),
                                "OTHER",
                            )
                            sys.stderr.write(f"SUPERVISOR_FAILURE phase={phase} error={kind}\n")
                            sys.stderr.flush()
                        raise
            nominal_close = True
    finally:
        try:
            if provider_owner is not None and not await provider_owner.drain():
                raise ValueError("Credential writer drain uncertain")
            if task_owner is not None:
                await task_owner.close_model_test()
            if runtime is not None:
                try:
                    if not await runtime.drain():
                        raise ValueError("Runtime drain uncertain")
                    if slot is not None and nominal_close and epoch is not None:
                        stopped = await runtime.status()
                        current = await service.owned_status(owner, epoch)
                        await slot.archive(service, current.generation, stopped)
                finally:
                    await runtime.close()
            if epoch is not None:
                await service.release(owner, epoch)
        finally:
            try:
                if slot is not None:
                    await slot.close()
            finally:
                await engine.dispose()
                for sig in (signal.SIGTERM, signal.SIGINT):
                    loop.remove_signal_handler(sig)


def main() -> int:
    try:
        asyncio.run(run())
    except (
        OSError,
        ValueError,
        TimeoutError,
        SQLAlchemyError,
        ControlConflict,
        EngagementNotFound,
    ):
        # Never print DSNs, raw SQL parameters, capabilities or request content.
        print("SUPERVISOR_UNAVAILABLE", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
