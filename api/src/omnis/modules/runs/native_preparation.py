"""Private published-document preparation; no agent, model, or runtime ownership.

T1 reserves once. Only its creator dispatches. A missing T2 receipt is indeterminate,
never a retry instruction. T2 holds the instance fence through its post-write check.
"""

import argparse
import asyncio
import os
import socket
import stat
import struct
import sys
from contextlib import suppress
from pathlib import Path
from typing import NoReturn
from uuid import UUID, uuid5

from pydantic import ValidationError
from sqlalchemy import text as sql
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.core.db import database_engine
from omnis.core.paths import check_private_file, private_directory
from omnis.modules.instance.domain import ControlConflict
from omnis.modules.instance.schemas import NativePrepareCommand
from omnis.modules.instance.service import InstanceService
from omnis.modules.runs.native_preparation_models import (
    LIMITS,
    mapping,
    prepare_packages,
    sequence,
    text,
    validate_bundle,
    validate_worker,
)
from omnis.modules.settings import candidate_store as store
from omnis.modules.settings.candidate_catalog import payload, uuid_string, valid_ref
from omnis.modules.settings.candidate_index import index_source, resolved_index
from omnis.modules.settings.candidate_material import digest, read_material
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_publication import PublicationCatalog
from omnis.modules.settings.catalog_schema import bounded, canonical, load_json
from omnis.modules.settings.publication_models import clean_text
from omnis.modules.settings.skill_catalog import read_file
from omnis.modules.tasks.execution_selection import selection_payload
from omnis.supervisor.runtime_client import RuntimeClient, RuntimeUnavailable

OPERATION = "native-prepare"


def validate_request(operation: str, value: object) -> dict[str, object]:
    bounded(value)
    clean_text(value)
    result = mapping(value)
    if len(canonical(result)) > 4096:
        raise CatalogError("INVALID_REQUEST")
    if operation == "prepare":
        if "op" in result:
            raise CatalogError("INVALID_REQUEST")
        try:
            command = NativePrepareCommand.model_validate({"op": "native_prepare", **result})
        except ValidationError:
            raise CatalogError("INVALID_REQUEST") from None
        return command.model_dump(mode="json", exclude={"op"})
    if (
        operation != "readback"
        or set(result) != {"schema_version", "owner_id", "command_id"}
        or type(result["schema_version"]) is not int
        or result["schema_version"] != 1
    ):
        raise CatalogError("INVALID_REQUEST")
    uuid_string(result["owner_id"])
    uuid_string(result["command_id"])
    return mapping(load_json(canonical(result)))


def existing_private_root(root: Path) -> Path:
    if not root.is_absolute() or root != root.resolve(strict=True):
        raise CatalogError("PREPARATION_UNAVAILABLE")
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise CatalogError("PREPARATION_UNAVAILABLE")
    private_directory(root)
    return root


def receipt_id(bundle: dict[str, object]) -> str:
    return str(uuid5(UUID(uuid_string(bundle["id"])), "native-preparation-receipt-v1"))


async def reservation(connection: AsyncConnection, owner: str, command: str) -> dict[str, object]:
    row = (
        (
            await connection.execute(
                sql(
                    "SELECT operation, result FROM catalog_command WHERE owner_id=:owner AND command_id=:command"
                ),
                {"owner": owner, "command": command},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None or row["operation"] != OPERATION:
        raise CatalogError("REF_UNAVAILABLE")
    result = mapping(row["result"])
    if set(result) != {"bundle_ref"}:
        raise CatalogError("PREPARATION_REJECTED")
    return valid_ref(result["bundle_ref"])


async def retained(
    connection: AsyncConnection, owner: str, ref: dict[str, object]
) -> tuple[str, dict[str, object]]:
    group, raw = await store.get(connection, owner, ref)
    bundle = validate_bundle(ref, raw)
    body = payload(bundle)
    if body["owner_id"] != owner:
        raise CatalogError("PREPARATION_REJECTED")
    records: dict[str, dict[str, object]] = {}
    for field in ("selection_ref", "snapshot_ref", "publication_ref", "candidate_snapshot_ref"):
        source_group, record = await store.get(connection, owner, valid_ref(body[field]))
        if source_group != group:
            raise CatalogError("PREPARATION_REJECTED")
        records[field] = payload(record)
    selection = records["selection_ref"]
    snapshot = records["snapshot_ref"]
    package_refs = [mapping(p)["package_ref"] for p in sequence(body["packages"])]
    if (
        selection.get("snapshot_ref") != body["snapshot_ref"]
        or selection.get("recipe_key") != body["recipe_key"]
        or sorted(sequence(selection.get("selected_package_refs")), key=canonical)
        != sorted(package_refs, key=canonical)
        or selection.get("resolution") != "NO_MODEL"
        or selection.get("effective") is not None
        or snapshot.get("publication_ref") != body["publication_ref"]
        or snapshot.get("snapshot_ref") != body["candidate_snapshot_ref"]
        or snapshot.get("material_digest") != body["material_digest"]
        or snapshot.get("resolved_index_digest") != body["resolved_index_digest"]
        or snapshot.get("dependency_artifact_refs") != []
    ):
        raise CatalogError("PREPARATION_REJECTED")
    return group, bundle


async def read_receipt(
    connection: AsyncConnection, owner: str, ref: dict[str, object]
) -> dict[str, object]:
    group, bundle = await retained(connection, owner, ref)
    identity = receipt_id(bundle)
    row = (
        (
            await connection.execute(
                sql("SELECT owner_id, group_id, envelope FROM catalog_record WHERE id=:id"),
                {"id": identity},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise CatalogError("PREPARATION_INDETERMINATE")
    if str(row["owner_id"]) != owner or str(row["group_id"]) != group:
        raise CatalogError("PREPARATION_REJECTED")
    receipt = store.checked(row["envelope"])
    valid_ref(store.reference(receipt))
    if (
        receipt["id"] != identity
        or receipt["kind"] != "native-preparation-receipt"
        or type(receipt["revision"]) is not int
        or receipt["revision"] != 1
        or type(receipt["schema_version"]) is not int
        or receipt["schema_version"] != 1
    ):
        raise CatalogError("PREPARATION_REJECTED")
    body = payload(receipt)
    if (
        set(body) != {"bundle_ref", "selection_ref", "status", "loader_result", "authority"}
        or body["bundle_ref"] != ref
        or body["selection_ref"] != payload(bundle)["selection_ref"]
        or body["status"] != "PREPARED"
    ):
        raise CatalogError("PREPARATION_REJECTED")
    validate_worker(body["loader_result"], ref, bundle)
    fence = mapping(body["authority"])
    if set(fence) != {"instance_id", "supervisor_owner", "epoch", "generation", "runtime_boot"}:
        raise CatalogError("PREPARATION_REJECTED")
    for key in ("instance_id", "supervisor_owner", "runtime_boot"):
        uuid_string(fence[key])
    for key, minimum in (("epoch", 1), ("generation", 0)):
        value = fence[key]
        if type(value) is not int or not minimum <= value < 2**63:
            raise CatalogError("PREPARATION_REJECTED")
    return {
        "bundle_ref": ref,
        "bundle": bundle,
        "receipt_ref": store.reference(receipt),
        "receipt": receipt,
        "preparation_status": "PREPARED",
    }


async def readback(engine: AsyncEngine, request: object) -> dict[str, object]:
    value = validate_request("readback", request)
    owner, command = uuid_string(value["owner_id"]), uuid_string(value["command_id"])
    async with asyncio.timeout(4):
        async with engine.begin() as connection:
            await store.lock(connection, "owner:" + owner)
            return await read_receipt(
                connection, owner, await reservation(connection, owner, command)
            )


def success(back: dict[str, object]) -> dict[str, object]:
    return {
        "ok": True,
        "bundle_ref": back["bundle_ref"],
        "receipt_ref": back["receipt_ref"],
        "preparation_status": "PREPARED",
    }


class NativePreparation:
    def __init__(
        self,
        engine: AsyncEngine,
        catalog_root: Path,
        service: InstanceService,
        supervisor_owner: UUID,
        epoch: int,
        runtime: RuntimeClient,
    ) -> None:
        self.engine, self.service, self.owner, self.epoch, self.runtime = (
            engine,
            service,
            supervisor_owner,
            epoch,
            runtime,
        )
        self.root = existing_private_root(catalog_root)
        self.publications = PublicationCatalog(engine, self.root)

    async def build(
        self, connection: AsyncConnection, command: NativePrepareCommand
    ) -> tuple[str, dict[str, object]]:
        group, selection = await store.get(connection, command.owner_id, command.selection_ref)
        selected = payload(selection)
        snapshot_ref = valid_ref(selected.get("snapshot_ref"))
        source_group, snapshot, profile, compiled = await self.publications.load_probe(
            connection, command.owner_id, snapshot_ref
        )
        expected = selection_payload(
            snapshot_ref, text(selected.get("recipe_key")), profile, compiled
        )
        if group != source_group or selected != expected:
            raise CatalogError("PREPARATION_REJECTED")
        snapshot_body = payload(snapshot)
        candidate_ref = valid_ref(snapshot_body["snapshot_ref"])
        candidate_group, candidate = await store.get(connection, command.owner_id, candidate_ref)
        if candidate_group != group:
            raise CatalogError("PREPARATION_REJECTED")
        _, records = await self.publications.candidates.sources(
            connection, command.owner_id, payload(candidate)
        )
        sources = [payload(record) for record in records]
        material = read_material(
            self.root,
            "candidates",
            uuid_string(candidate["id"]),
            [*sources, index_source(resolved_index(compiled))],
        )
        pairs: list[tuple[dict[str, object], dict[str, object]]] = []
        for item in sequence(selected["selected_package_refs"]):
            ref = valid_ref(item)
            bindings = [
                b
                for b in compiled.catalog_bindings
                if b.get("ref") == ref
                and b.get("entity_kind") == "package"
                and b.get("key") == b.get("package_key")
            ]
            if len(bindings) != 1:
                raise CatalogError("PREPARATION_REJECTED")
            matches = [
                s
                for s in sources
                if s.get("source_kind") == "package"
                and s.get("package_key") == bindings[0]["package_key"]
            ]
            if len(matches) != 1:
                raise CatalogError("PREPARATION_REJECTED")
            pairs.append((ref, matches[0]))
        bundle = store.envelope(
            "native-preparation-bundle",
            {
                "protocol": "omnis-native-preparation-v1",
                "owner_id": command.owner_id,
                "selection_ref": command.selection_ref,
                "snapshot_ref": snapshot_ref,
                "publication_ref": snapshot_body["publication_ref"],
                "candidate_snapshot_ref": candidate_ref,
                "recipe_key": selected["recipe_key"],
                "material_digest": snapshot_body["material_digest"],
                "resolved_index_digest": snapshot_body["resolved_index_digest"],
                "resolution": "NO_MODEL",
                "effective": None,
                "preprocess": False,
                "limits": LIMITS,
                "packages": prepare_packages(material, pairs),
            },
        )
        return group, validate_bundle(store.reference(bundle), bundle)

    async def _instance(self, connection: AsyncConnection, command: NativePrepareCommand) -> None:
        identity = (
            await connection.execute(sql("SELECT instance_id FROM instance_control WHERE id=1"))
        ).scalar_one()
        if str(identity) != command.instance_id or command.expected_epoch != self.epoch:
            raise CatalogError("PREPARATION_REJECTED")

    async def prepare(self, command: NativePrepareCommand) -> dict[str, object]:
        # Revalidate even model_construct or caller mutation before all replay and I/O.
        value = validate_request("prepare", command.model_dump(mode="json", exclude={"op"}))
        command = NativePrepareCommand.model_validate({"op": "native_prepare", **value})
        async with asyncio.timeout(4):
            return await self._prepare(command, value)

    async def _prepare(
        self, command: NativePrepareCommand, value: dict[str, object]
    ) -> dict[str, object]:
        owner, identity = command.owner_id, command.command_id
        # Historical replay needs no live runtime. Never acquire instance locks under catalog lock.
        async with self.engine.begin() as connection:
            await store.lock(connection, "owner:" + owner)
            prior = await store.replay(connection, owner, identity, OPERATION, value)
            if prior is not None:
                return success(
                    await read_receipt(
                        connection, owner, await reservation(connection, owner, identity)
                    )
                )
        async with self.service.native_preparation_commit(
            self.owner, self.epoch, command.expected_generation
        ) as connection:
            await self._instance(connection, command)
            await store.lock(connection, "owner:" + owner)
            prior = await store.replay(connection, owner, identity, OPERATION, value)
            if prior is not None:
                return success(
                    await read_receipt(
                        connection, owner, await reservation(connection, owner, identity)
                    )
                )
            group, bundle = await self.build(connection, command)
            ref = store.reference(bundle)
            await store.put(connection, owner, group, bundle)
            await store.complete(connection, owner, identity, OPERATION, value, {"bundle_ref": ref})
        # Committed T1. Only the invocation which reached here may dispatch.
        try:
            response = await self.runtime.prepare(self.service, self.owner, ref, bundle)
        except RuntimeUnavailable:
            raise CatalogError("PREPARATION_INDETERMINATE") from None
        result = validate_worker(response.get("preparation"), ref, bundle)
        boot = uuid_string(self.runtime.boot)
        async with self.service.native_preparation_commit(
            self.owner, self.epoch, command.expected_generation
        ) as connection:
            await self._instance(connection, command)
            await store.lock(connection, "owner:" + owner)
            if await store.replay(connection, owner, identity, OPERATION, value) != {
                "bundle_ref": ref
            }:
                raise CatalogError("PREPARATION_REJECTED")
            retained_group, retained_bundle = await retained(connection, owner, ref)
            if retained_group != group or retained_bundle != bundle:
                raise CatalogError("PREPARATION_REJECTED")
            validate_worker(result, ref, retained_bundle)
            receipt = store.envelope(
                "native-preparation-receipt",
                {
                    "bundle_ref": ref,
                    "selection_ref": command.selection_ref,
                    "status": "PREPARED",
                    "loader_result": result,
                    "authority": {
                        "instance_id": command.instance_id,
                        "supervisor_owner": str(self.owner),
                        "epoch": self.epoch,
                        "generation": command.expected_generation,
                        "runtime_boot": boot,
                    },
                },
            )
            receipt["id"] = receipt_id(bundle)
            receipt["digest"] = digest(
                canonical({k: v for k, v in receipt.items() if k != "digest"})
            )
            await store.put(connection, owner, group, receipt)
        return success(
            await readback(
                self.engine, {"schema_version": 1, "owner_id": owner, "command_id": identity}
            )
        )


async def control_prepare(directory: Path, value: dict[str, object]) -> dict[str, object]:
    value = validate_request("prepare", value)
    existing_private_root(directory)
    fd = os.open(directory / "control.cap", os.O_RDONLY | os.O_NOFOLLOW)
    try:
        check_private_file(os.fstat(fd))
        capability = os.read(fd, 65).decode("ascii")
    finally:
        os.close(fd)
    if len(capability) != 64 or any(c not in "0123456789abcdef" for c in capability):
        raise CatalogError("PREPARATION_UNAVAILABLE")
    info = (directory / "control.sock").lstat()
    if (
        not stat.S_ISSOCK(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        raise CatalogError("PREPARATION_UNAVAILABLE")
    async with asyncio.timeout(4):
        reader, writer = await asyncio.open_unix_connection(
            str(directory / "control.sock"), limit=4096
        )
        try:
            peer = writer.get_extra_info("socket").getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, 12
            )
            if struct.unpack("3i", peer)[1] != os.getuid():
                raise CatalogError("PREPARATION_UNAVAILABLE")
            frame = (
                canonical(
                    {
                        "version": 1,
                        "capability": capability,
                        "command": {"op": "native_prepare", **value},
                    }
                )
                + b"\n"
            )
            if len(frame) > 4096:
                raise CatalogError("INVALID_REQUEST")
            writer.write(frame)
            await writer.drain()
            response = mapping(load_json(await reader.readuntil(b"\n")))
            uuid_string(response.get("correlation_id"))
            if response.get("ok") is not True:
                reason = response.get("error")
                allowed = {
                    "PREPARATION_REJECTED",
                    "PREPARATION_INDETERMINATE",
                    "PREPARATION_UNAVAILABLE",
                    "PREPARATION_BUSY",
                    "COMMAND_CONFLICT",
                    "CONTROL_TIMEOUT",
                    "CONTROL_UNAVAILABLE",
                    "LEASE_LOST",
                }
                raise CatalogError(
                    reason
                    if isinstance(reason, str) and reason in allowed
                    else "PREPARATION_UNAVAILABLE"
                )
            if (
                set(response)
                != {"ok", "correlation_id", "bundle_ref", "receipt_ref", "preparation_status"}
                or response["preparation_status"] != "PREPARED"
                or valid_ref(response["bundle_ref"])["kind"] != "native-preparation-bundle"
                or valid_ref(response["receipt_ref"])["kind"] != "native-preparation-receipt"
            ):
                raise CatalogError("PREPARATION_REJECTED")
            return response
        finally:
            writer.close()
            with suppress(ConnectionError, TimeoutError):
                await asyncio.wait_for(writer.wait_closed(), 0.5)


def main(argv: list[str] | None = None) -> int:
    class SafeParser(argparse.ArgumentParser):
        def error(self, message: str) -> NoReturn:
            raise CatalogError("INVALID_ARGUMENTS")

    parser = SafeParser()
    commands = parser.add_subparsers(dest="operation", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--request", required=True)
    prepare.add_argument("--control-dir", required=True)
    read = commands.add_parser("readback")
    read.add_argument("--request", required=True)
    try:
        args = parser.parse_args(argv)
        request = validate_request(args.operation, load_json(read_file(Path(args.request), 4096)))

        async def run() -> dict[str, object]:
            if args.operation == "prepare":
                return await control_prepare(Path(args.control_dir), request)
            url = os.environ.get("OMNIS_DATABASE_URL")
            if not url:
                raise CatalogError("DATABASE_UNAVAILABLE")
            engine = database_engine(url)
            try:
                return await readback(engine, request)
            finally:
                await engine.dispose()

        print(canonical(asyncio.run(run())).decode())
        return 0
    except CatalogError as error:
        reason = error.reason
    except (SQLAlchemyError, ControlConflict, TimeoutError):
        reason = "PREPARATION_UNAVAILABLE"
    except (
        OSError,
        ValueError,
        RecursionError,
        KeyError,
        TypeError,
        asyncio.IncompleteReadError,
        asyncio.LimitOverrunError,
    ):
        reason = "INVALID_REQUEST"
    print(canonical({"status": "BLOCKED", "reason": reason}).decode(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
