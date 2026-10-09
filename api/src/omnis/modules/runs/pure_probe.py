"""Explicit deterministic probe, not a Task or a catalog qualification.

Committed command replay revalidates pins/outputs, never reruns the executor.
A crash before commit may recompute PURE; this is not exactly-once execution.
"""

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path
from typing import NoReturn

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.core.db import database_engine
from omnis.modules.settings import candidate_store as store
from omnis.modules.settings.candidate_catalog import (
    EVALUATOR_REVISION,
    payload,
    uuid_string,
    valid_ref,
)
from omnis.modules.settings.candidate_material import digest
from omnis.modules.settings.catalog_models import CatalogError, CompiledCatalog
from omnis.modules.settings.catalog_publication import PublicationCatalog
from omnis.modules.settings.catalog_schema import bounded, canonical, load_json, validate
from omnis.modules.settings.publication_models import clean_text, load_request
from omnis.modules.settings.skill_catalog import evaluate_pure, read_file
from omnis.modules.tasks.execution_selection import selection_payload

EXECUTOR_FILES = (
    "runs/pure_probe.py",
    "runs/plan_snapshot.py",
    "tasks/execution_selection.py",
    "settings/catalog_publication.py",
    "settings/publication_models.py",
    "settings/publication_store.py",
)


def executor_revision() -> str:
    root = Path(__file__).parent.parent
    return "sha256:" + digest(
        canonical(
            {
                "domain": "omnis-contract-probe-pure-v1",
                "evaluator_revision": EVALUATOR_REVISION,
                "files": {name: digest(read_file(root / name)) for name in EXECUTOR_FILES},
            }
        )
    )


EXECUTOR_REVISION = executor_revision()


def validate_request(operation: str, value: object) -> dict[str, object]:
    fields = {
        "select": {"snapshot_ref", "recipe_key"},
        "execute": {"selection_ref", "input"},
        "readback": {"receipt_ref"},
    }
    if operation not in fields or not isinstance(value, dict):
        raise CatalogError("INVALID_REQUEST")
    common = {"schema_version", "owner_id"}
    if operation != "readback":
        common.add("command_id")
    if set(value) != common | fields[operation]:
        raise CatalogError("INVALID_REQUEST")
    try:
        bounded(value)
        clean_text(value)
        if len(canonical(value)) > 1048576:
            raise CatalogError("INVALID_REQUEST")
    except (CatalogError, ValueError, TypeError, RecursionError):
        raise CatalogError("INVALID_REQUEST") from None
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise CatalogError("INVALID_REQUEST")
    uuid_string(value["owner_id"])
    if "command_id" in common:
        uuid_string(value["command_id"])
    for field, kind in (
        ("snapshot_ref", "run-snapshot"),
        ("selection_ref", "execution-selection"),
        ("receipt_ref", "pure-probe-receipt"),
    ):
        if field in value and valid_ref(value[field])["kind"] != kind:
            raise CatalogError("INVALID_REQUEST")
    if operation == "select":
        key = value["recipe_key"]
        if type(key) is not str or re.fullmatch(r"[a-z][a-z0-9_.-]{0,127}", key) is None:
            raise CatalogError("INVALID_REQUEST")
    if operation == "execute" and not isinstance(value["input"], dict):
        raise CatalogError("INVALID_REQUEST")
    # Isolate caller-owned mutable objects before the first await/replay lookup.
    checked = load_json(canonical(value))
    if not isinstance(checked, dict):
        raise CatalogError("INVALID_REQUEST")
    return checked


def execute_outputs(compiled: CompiledCatalog, input_object: object) -> list[dict[str, object]]:
    result = evaluate_pure(compiled, input_object)
    return [
        {"step_id": step.id, "output": load_json(raw), "digest": digest(raw)}
        for step, raw in zip(compiled.steps, result.outputs_json, strict=True)
    ]


class PureProbe:
    def __init__(self, engine: AsyncEngine, root: Path) -> None:
        self.engine = engine
        self.publications = PublicationCatalog(engine, root)

    async def dispatch(self, operation: str, request: object) -> dict[str, object]:
        value = validate_request(operation, request)
        async with asyncio.timeout(15):
            return await self._dispatch(operation, value)

    async def _selection(
        self, connection: AsyncConnection, owner: str, ref: dict[str, object]
    ) -> tuple[str, dict[str, object], CompiledCatalog]:
        group, record = await store.get(connection, owner, ref)
        if record["kind"] != "execution-selection":
            raise CatalogError("SELECTION_MISMATCH")
        body = payload(record)
        snapshot_ref = valid_ref(body.get("snapshot_ref"))
        key = body.get("recipe_key")
        if type(key) is not str:
            raise CatalogError("SELECTION_MISMATCH")
        source_group, _, profile, compiled = await self.publications.load_probe(
            connection, owner, snapshot_ref
        )
        if group != source_group or body != selection_payload(snapshot_ref, key, profile, compiled):
            raise CatalogError("SELECTION_MISMATCH")
        return group, record, compiled

    async def _readback(
        self, connection: AsyncConnection, owner: str, ref: dict[str, object]
    ) -> dict[str, object]:
        group, receipt = await store.get(connection, owner, ref)
        body = payload(receipt)
        if receipt["kind"] != "pure-probe-receipt" or set(body) != {
            "selection_ref",
            "input_ref",
            "executor_revision",
            "status",
            "outputs",
        }:
            raise CatalogError("RECEIPT_MISMATCH")
        selection_ref = valid_ref(body["selection_ref"])
        selection_group, selection, compiled = await self._selection(
            connection, owner, selection_ref
        )
        input_ref = valid_ref(body["input_ref"])
        input_group, input_record = await store.get(connection, owner, input_ref)
        input_body = payload(input_record)
        if (
            group != selection_group
            or group != input_group
            or input_record["kind"] != "pure-probe-input"
            or set(input_body) != {"selection_ref", "input", "created_by"}
            or input_body["selection_ref"] != selection_ref
            or input_body["created_by"] != owner
            or body["executor_revision"] != EXECUTOR_REVISION
            or body["status"] != "COMPLETED"
        ):
            raise CatalogError("RECEIPT_MISMATCH")
        validate(compiled.input_schema, input_body["input"])
        outputs = body["outputs"]
        if not isinstance(outputs, list) or len(outputs) != len(compiled.steps) or not outputs:
            raise CatalogError("RECEIPT_MISMATCH")
        total = 0
        for step, output in zip(compiled.steps, outputs, strict=True):
            if not isinstance(output, dict) or set(output) != {"step_id", "output", "digest"}:
                raise CatalogError("RECEIPT_MISMATCH")
            raw = canonical(output["output"])
            total += len(raw)
            if output["step_id"] != step.id or output["digest"] != digest(raw):
                raise CatalogError("RECEIPT_MISMATCH")
            validate(step.output_schema, output["output"])
        if total > compiled.max_output_bytes:
            raise CatalogError("OUTPUT_LIMIT")
        validate(compiled.output_schema, outputs[-1]["output"])
        return {
            "receipt_ref": ref,
            "receipt": receipt,
            "selection_ref": selection_ref,
            "selection": selection,
            "input_ref": input_ref,
            "input": input_record,
        }

    async def _revalidate(
        self,
        connection: AsyncConnection,
        owner: str,
        operation: str,
        value: dict[str, object],
        result: dict[str, object],
    ) -> None:
        expected: dict[str, object]
        if operation == "select":
            _, record, _ = await self._selection(
                connection, owner, valid_ref(result.get("selection_ref"))
            )
            body = payload(record)
            if (
                body["snapshot_ref"] != value["snapshot_ref"]
                or body["recipe_key"] != value["recipe_key"]
            ):
                raise CatalogError("SELECTION_MISMATCH")
            expected = {"selection_ref": store.reference(record), "selection": record}
        else:
            back = await self._readback(connection, owner, valid_ref(result.get("receipt_ref")))
            input_record = back["input"]
            if not isinstance(input_record, dict):
                raise CatalogError("STORAGE_INCOMPATIBLE")
            if (
                back["selection_ref"] != value["selection_ref"]
                or payload(input_record)["input"] != value["input"]
            ):
                raise CatalogError("RECEIPT_MISMATCH")
            expected = {"receipt_ref": back["receipt_ref"], "receipt": back["receipt"]}
        if result != expected:
            raise CatalogError("STORAGE_INCOMPATIBLE")

    async def _dispatch(self, operation: str, value: dict[str, object]) -> dict[str, object]:
        owner = uuid_string(value["owner_id"])
        async with self.engine.begin() as connection:
            await store.lock(connection, "owner:" + owner)
            if operation == "readback":
                return await self._readback(connection, owner, valid_ref(value["receipt_ref"]))
            command = uuid_string(value["command_id"])
            prior = await store.replay(connection, owner, command, operation, value)
            if prior is not None:
                await self._revalidate(connection, owner, operation, value, prior)
                return prior
            result: dict[str, object]
            if operation == "select":
                snapshot_ref = valid_ref(value["snapshot_ref"])
                group, _, profile, compiled = await self.publications.load_probe(
                    connection, owner, snapshot_ref
                )
                key = value["recipe_key"]
                if type(key) is not str:
                    raise CatalogError("INVALID_REQUEST")
                record = store.envelope(
                    "execution-selection", selection_payload(snapshot_ref, key, profile, compiled)
                )
                await store.put(connection, owner, group, record)
                result = {"selection_ref": store.reference(record), "selection": record}
            else:
                selection_ref = valid_ref(value["selection_ref"])
                group, _, compiled = await self._selection(connection, owner, selection_ref)
                outputs = execute_outputs(compiled, value["input"])
                input_record = store.envelope(
                    "pure-probe-input",
                    {
                        "selection_ref": selection_ref,
                        "input": value["input"],
                        "created_by": owner,
                    },
                )
                record = store.envelope(
                    "pure-probe-receipt",
                    {
                        "selection_ref": selection_ref,
                        "input_ref": store.reference(input_record),
                        "executor_revision": EXECUTOR_REVISION,
                        "status": "COMPLETED",
                        "outputs": outputs,
                    },
                )
                await store.put(connection, owner, group, input_record)
                await store.put(connection, owner, group, record)
                result = {
                    "receipt_ref": store.reference(record),
                    "receipt": record,
                }
            await store.complete(connection, owner, command, operation, value, result)
        async with self.engine.begin() as connection:
            await store.lock(connection, "owner:" + owner)
            committed = await store.replay(connection, owner, command, operation, value)
            if committed is None:
                raise CatalogError("STORAGE_INCOMPATIBLE")
            await self._revalidate(connection, owner, operation, value, committed)
            return committed


def main(argv: list[str] | None = None) -> int:
    class SafeParser(argparse.ArgumentParser):
        def error(self, message: str) -> NoReturn:
            raise CatalogError("INVALID_ARGUMENTS")

    parser = SafeParser()
    parser.add_argument("operation", choices=("select", "execute", "readback"))
    parser.add_argument("--request", required=True)
    parser.add_argument("--catalog-root", required=True)
    try:
        args = parser.parse_args(argv)
        request = load_request(read_file(Path(args.request)))
        validate_request(args.operation, request)
        url = os.environ.get("OMNIS_DATABASE_URL")
        if not url:
            raise CatalogError("DATABASE_UNAVAILABLE")

        async def run() -> dict[str, object]:
            engine = database_engine(url)
            try:
                return await PureProbe(engine, Path(args.catalog_root)).dispatch(
                    args.operation, request
                )
            finally:
                await engine.dispose()

        print(canonical(asyncio.run(run())).decode())
        return 0
    except CatalogError as error:
        reason = error.reason
    except (SQLAlchemyError, TimeoutError):
        reason = "DATABASE_UNAVAILABLE"
    except (OSError, UnicodeError, RecursionError, ValueError, KeyError, TypeError):
        reason = "INPUT_UNAVAILABLE"
    print(canonical({"status": "BLOCKED", "reason": reason}).decode(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
