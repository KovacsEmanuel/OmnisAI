"""Dedicated migration command for an explicitly configured PostgreSQL database."""

import argparse
import json
import os
import re
import signal
import sys
from importlib.resources import files
from types import FrameType

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.core.db import schema0016_reason_on
from omnis.core.persistence import read_record
from omnis.modules.instance.domain import ControlConflict
from omnis.modules.instance.records import InstanceRecord, LeaseRecord
from omnis.modules.instance.service import InstanceService
from omnis.modules.instance.stop_contract import StopReconciliation


async def admit_t1_upgrade(
    connection: AsyncConnection, engine: AsyncEngine, request: StopReconciliation
) -> None:
    """Hold the existing authority rows through DDL; do not retire the Stop grant."""
    if await schema0016_reason_on(connection) is not None:
        raise ValueError("Physical0016 required")
    instance = (
        (await connection.execute(text("SELECT * FROM instance_control WHERE id=1 FOR UPDATE")))
        .mappings()
        .one()
    )
    lease = (
        (await connection.execute(text("SELECT * FROM supervisor_lease WHERE id=1 FOR UPDATE")))
        .mappings()
        .one()
    )
    service = InstanceService(engine)
    stored = await service._grant(connection)
    if request.grant.state != "STOP_PENDING" or stored != request.grant:
        raise ValueError("Exact stopped grant required")
    await service._closed_stop(
        connection,
        read_record(InstanceRecord, instance),
        read_record(LeaseRecord, lease),
        request.grant,
    )
    if (
        await connection.execute(
            text("SELECT EXISTS(SELECT 1 FROM system_operation WHERE state <> 'FINISHED')")
        )
    ).scalar_one():
        raise ValueError("Unsettled operations")


def upgrade_t1(request: StopReconciliation) -> None:
    """Finite explicit0016→0017 migration; the host must attest stopped resources."""
    expected = os.environ.get("OMNIS_EXPECTED_SYSTEM_ID", "")
    if not re.fullmatch(r"[0-9]{1,20}", expected) or request.system_identifier != expected:
        raise ValueError("Expected cluster identity required")
    config = Config()
    config.attributes["t1_upgrade"] = request
    config.attributes["upgrade_system_id"] = expected
    config.set_main_option("script_location", str(files("omnis.migrations")))
    command.upgrade(config, "0017_model_removal")


def upgrade_job() -> int:
    from omnis.stop_reconcile import read_request

    def expired(_signum: int, _frame: FrameType | None) -> None:
        try:
            os.set_blocking(1, False)
            os.write(1, b'{"ok":false,"error":"UPGRADE_UNCERTAIN"}\n')
        finally:
            os._exit(4)

    signal.signal(signal.SIGALRM, expired)
    signal.alarm(25)
    try:
        request = read_request()
        upgrade_t1(request)
        response: dict[str, object] = {
            "ok": True,
            "schema": "0017_model_removal",
            "request": request.model_dump(mode="json"),
        }
        code = 0
    except (
        OSError,
        ValueError,
        RuntimeError,
        TimeoutError,
        ControlConflict,
        SQLAlchemyError,
        KeyboardInterrupt,
    ):
        response = {"ok": False, "error": "UPGRADE_UNCERTAIN"}
        code = 4
    try:
        sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
        sys.stdout.flush()
        return code
    finally:
        signal.alarm(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Explicit PostgreSQL migration")
    parser.add_argument(
        "--initialize", action="store_true", help="Only an empty, attested database; never upgrade"
    )
    parser.add_argument("--upgrade-t1", action="store_true", help="Finite stopped0016→0017 only")
    args = parser.parse_args()
    if args.upgrade_t1:
        if args.initialize:
            parser.error("Initialize and upgrade are mutually exclusive")
        raise SystemExit(upgrade_job())
    config = Config()
    if args.initialize:
        identity = os.environ.get("OMNIS_EXPECTED_SYSTEM_ID", "")
        if not re.fullmatch(r"[0-9]{1,20}", identity):
            raise RuntimeError("Expected PostgreSQL cluster identity required")
        config.attributes["initialize_system_id"] = identity
    config.set_main_option("script_location", str(files("omnis.migrations")))
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()
