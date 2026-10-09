"""DB-only managed admission. Supervisor owns authenticated native IPC and fences.

prepare commits before native dispatch; reserve_dispatch commits uncertainty before
IPC. commit_binding MUST run inside InstanceService.native_preparation_commit.
Ingest is historical receive-only and never dispatches or completes a Brain turn.
"""

import argparse
import asyncio
import base64
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

from sqlalchemy import text as sql
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.core.db import database_engine
from omnis.modules.settings import candidate_store as catalog
from omnis.modules.settings.candidate_catalog import uuid_string
from omnis.modules.settings.candidate_material import digest
from omnis.modules.settings.catalog_models import CatalogError, Manifest, Procedure, ReleaseRef
from omnis.modules.settings.catalog_schema import canonical, dto, load_json
from omnis.modules.tasks import managed_contract as contract
from omnis.modules.tasks import managed_store as store
from omnis.modules.tasks.managed_contract import mapping, record, ref, sequence, text


def validate_request(operation: str, value: object) -> dict[str, object]:
    fields = {"schema_version", "owner_id", "command_id"}
    if operation in {"prepare", "prepare-composed"}:
        fields |= {"selection_ref", "preparation_command_id", "task_count"}
    elif operation not in {"readback", "reconcile"}:
        raise CatalogError("INVALID_REQUEST")
    result = contract.exact(value, fields)
    contract.integer(result["schema_version"], 1, 1)
    uuid_string(result["owner_id"])
    uuid_string(result["command_id"])
    if operation in {"prepare", "prepare-composed"}:
        ref(result["selection_ref"], "execution-selection")
        uuid_string(result["preparation_command_id"])
        contract.integer(result["task_count"], 1, 2)
    return result


class ManagedAdmission:
    def __init__(self, engine: AsyncEngine, catalog_root: Path | None = None) -> None:
        self.engine, self.root = engine, catalog_root

    async def _build(
        self, connection: AsyncConnection, owner: str, request: dict[str, object]
    ) -> list[dict[str, object]]:
        # Optional material/producer imports occur only on prepare, not API startup/readback.
        from omnis.modules.runs.native_preparation import read_receipt, reservation
        from omnis.modules.runs.pure_probe import PureProbe

        if self.root is None:
            raise CatalogError("CATALOG_REQUIRED")
        probe = PureProbe(self.engine, self.root)
        group, selection, compiled = await probe._selection(
            connection, owner, ref(request["selection_ref"])
        )
        snapshot_ref = ref(mapping(selection["payload"])["snapshot_ref"])
        _, _, profile, _ = await probe.publications.load_probe(connection, owner, snapshot_ref)
        if compiled.dependency_artifact_refs or compiled.dependency_closure_refs:
            raise CatalogError("UNSUPPORTED_DEPENDENCY")
        prepared = await read_receipt(
            connection,
            owner,
            await reservation(connection, owner, uuid_string(request["preparation_command_id"])),
        )
        bundle = mapping(mapping(prepared["bundle"])["payload"])
        if canonical(bundle["selection_ref"]) != canonical(request["selection_ref"]):
            raise CatalogError("PREPARATION_MISMATCH")
        recipe = profile.agent_recipes[0]
        source = recipe.procedure_refs[0]
        if (
            isinstance(source, ReleaseRef)
            or recipe.overlay_refs
            or recipe.role in {"BRAIN", "REVIEWER"}
        ):
            raise CatalogError("UNSUPPORTED_RECIPE")
        matches = [
            b
            for b in compiled.catalog_bindings
            if b["package_key"] == source.package_key
            and b["entity_kind"] == "procedure"
            and b["key"] == source.key
        ]
        if len(matches) != 1:
            raise CatalogError("UNRESOLVED_PROCEDURE_REF")
        packages = [
            mapping(p)
            for p in sequence(bundle["packages"])
            if mapping(p)["package_key"] == source.package_key
        ]
        if len(packages) != 1:
            raise CatalogError("UNRESOLVED_PROCEDURE_REF")
        files = {
            text(mapping(f)["path"]): base64.b64decode(
                text(mapping(f)["content_b64"], 16384), validate=True
            )
            for f in sequence(packages[0]["files"])
        }
        manifest = dto(files["omnis.yaml"], Manifest)
        procedures = [dto(files[path], Procedure) for path in manifest.procedures]
        selected = [p for p in procedures if p.key == source.key]
        if len(selected) != 1:
            raise CatalogError("UNRESOLVED_PROCEDURE_REF")
        # Both recipe and procedure ceilings constrain the brief, without removing requirements.
        procedure = selected[0]
        if request.get("composition_version") == 1:
            from omnis.modules.tasks.managed_composition import require_recipe

            require_recipe(recipe, procedure, source.package_key)
        graph = contract.build_records(
            selection,
            ref(prepared["receipt_ref"]),
            ref(matches[0]["ref"]),
            procedure,
            list(compiled.catalog_bindings),
            source.package_key,
            recipe.role,
            contract.integer(request["task_count"], 1, 2),
            datetime.now(UTC),
            recipe.limits,
            composition_packages=(
                [mapping(p) for p in sequence(bundle["packages"])]
                if request.get("composition_version") == 1
                else None
            ),
        )
        if len(canonical(graph)) + len(canonical(prepared["bundle"])) > 65536:
            raise CatalogError("CONTEXT_OVERFLOW")
        return graph

    async def prepare(self, request: object) -> dict[str, object]:
        value = validate_request("prepare", request)
        return await self._prepare(value)

    async def prepare_composed(self, request: object) -> dict[str, object]:
        value = validate_request("prepare-composed", request)
        return await self._prepare({**value, "composition_version": 1})

    async def _prepare(self, value: dict[str, object]) -> dict[str, object]:
        owner, command = uuid_string(value["owner_id"]), uuid_string(value["command_id"])
        created = False
        async with asyncio.timeout(15), self.engine.begin() as conn:
            await store.lock(conn, owner)
            prior = (
                await conn.execute(
                    sql(
                        "SELECT request_digest FROM managed_run WHERE owner_id=:owner AND command_id=:command"
                    ),
                    {"owner": owner, "command": command},
                )
            ).scalar_one_or_none()
            if prior is not None:
                if prior != digest(canonical(value)):
                    raise CatalogError("COMMAND_CONFLICT")
            else:
                graph = await self._build(conn, owner, value)
                manifest = contract.validate_manifest(graph[-1])
                run = uuid_string(mapping(manifest["payload"])["run_id"])
                await self._verify_graph(conn, owner, run, graph)
                # The scoped cursor is inserted only after its owning run row.
                initial_ids = {run, uuid_string(manifest["id"])}
                for item in graph:
                    if item["id"] in initial_ids:
                        await store.put(conn, owner, run, item)
                await conn.execute(
                    sql(
                        "INSERT INTO managed_run(run_id,owner_id,command_id,request_digest,manifest_id) VALUES (:run,:owner,:command,:digest,:manifest)"
                    ),
                    {
                        "run": run,
                        "owner": owner,
                        "command": command,
                        "digest": digest(canonical(value)),
                        "manifest": manifest["id"],
                    },
                )
                for item in graph:
                    if item["id"] not in initial_ids:
                        await store.put(conn, owner, run, item)
                for raw in sequence(mapping(manifest["payload"])["entries"]):
                    e = mapping(raw)
                    await conn.execute(
                        sql(
                            "INSERT INTO managed_task(task_id,attempt_id,run_id,batch_index,brief_id,state) VALUES (:task,:attempt,:run,:idx,:brief,'QUEUED')"
                        ),
                        {
                            "task": e["task_id"],
                            "attempt": e["attempt_id"],
                            "run": run,
                            "idx": e["batch_index"],
                            "brief": ref(e["brief_ref"])["id"],
                        },
                    )
                created = True
        back = await self.readback(
            {k: value[k] for k in ("schema_version", "owner_id", "command_id")}
        )
        return {**back, "created": created}

    async def load_manifest(
        self, connection: AsyncConnection, owner_id: str, manifest_ref: object
    ) -> dict[str, object]:
        owner = uuid_string(owner_id)
        state = await store.state(connection, owner, manifest=ref(manifest_ref, "launch-manifest"))
        return contract.validate_manifest(
            await store.get(connection, owner, uuid_string(state["run_id"]), manifest_ref)
        )

    async def reserve_dispatch(
        self, connection: AsyncConnection, owner_id: str, manifest_ref: object, operation: str
    ) -> dict[str, object]:
        """Commit this under supervisor fence BEFORE IPC. Never retry lost stage/release."""
        owner = uuid_string(owner_id)
        ref(manifest_ref, "launch-manifest")
        if operation not in {"stage", "release"}:
            raise CatalogError("INVALID_REQUEST")
        await store.lock(connection, owner)
        state = await store.state(connection, owner, manifest=manifest_ref)
        if state[operation + "_started"] is not False:
            raise CatalogError("NEEDS_RECONCILIATION")
        if operation == "release" and state["binding_id"] is None:
            raise CatalogError("BINDING_REQUIRED")
        manifest = await self.load_manifest(connection, owner, manifest_ref)
        run = uuid_string(state["run_id"])
        # Validate exact retained material before recording uncertain dispatch.
        await self.stage_payload(connection, owner, manifest_ref)
        briefs = [
            await store.get(connection, owner, run, mapping(raw)["brief_ref"])
            for raw in sequence(mapping(manifest["payload"])["entries"])
        ]
        # clock_timestamp(), not transaction-start now(): prior reads can wait.
        now = (await connection.execute(sql("SELECT clock_timestamp()"))).scalar_one()
        if not isinstance(now, datetime):
            raise CatalogError("STORAGE_INCOMPATIBLE")
        for brief in briefs:
            contract.require_unexpired(brief, now)
        await connection.execute(
            sql(f"UPDATE managed_run SET {operation}_started=true WHERE run_id=:run"),
            {"run": state["run_id"]},
        )
        return manifest

    async def stage_payload(
        self, connection: AsyncConnection, owner_id: str, manifest_ref: object
    ) -> dict[str, object]:
        from omnis.modules.tasks import managed_composition

        owner = uuid_string(owner_id)
        manifest = await self.load_manifest(connection, owner, manifest_ref)
        run = uuid_string(mapping(manifest["payload"])["run_id"])
        rows = (
            (
                await connection.execute(
                    sql(
                        "SELECT envelope FROM managed_record WHERE owner_id=:owner AND run_id=:run ORDER BY id"
                    ),
                    {"owner": owner, "run": run},
                )
            )
            .scalars()
            .all()
        )
        graph = [record(r) for r in rows]
        await self._verify_graph(connection, owner, run, graph)
        return managed_composition.stage_payload(manifest, graph)

    async def commit_binding(
        self,
        connection: AsyncConnection,
        owner_id: str,
        manifest_ref: object,
        stage: object,
        runtime_boot: object,
        authority: object,
    ) -> dict[str, object]:
        owner = uuid_string(owner_id)
        checked_fence = contract.authority(authority)
        boot = uuid_string(runtime_boot)
        ref(manifest_ref, "launch-manifest")
        await store.lock(connection, owner)
        manifest = await self.load_manifest(connection, owner, manifest_ref)
        candidate = contract.binding_record(manifest, stage, boot, checked_fence)
        state = await store.state(connection, owner, manifest=manifest_ref)
        run = uuid_string(state["run_id"])
        if state["stage_started"] is not True:
            raise CatalogError("STAGE_NOT_RESERVED")
        if state["binding_id"] is not None:
            prior = await store.by_id(connection, owner, run, state["binding_id"])
            contract.validate_binding(prior, manifest)
            if canonical(prior["payload"]) != canonical(candidate["payload"]):
                raise CatalogError("BINDING_CONFLICT")
            return prior
        await store.put(connection, owner, run, candidate)
        body = mapping(candidate["payload"])
        await connection.execute(
            sql(
                "UPDATE managed_run SET binding_id=:id,runtime_boot=:boot,ticket=:ticket,native_root_id=:root WHERE run_id=:run"
            ),
            {
                "id": candidate["id"],
                "boot": boot,
                "ticket": body["ticket"],
                "root": body["native_root_id"],
                "run": run,
            },
        )
        for raw in sequence(body["entries"]):
            e = mapping(raw)
            await connection.execute(
                sql(
                    "UPDATE managed_task SET state='BOUND',runtime_boot=:boot,native_child_id=:child,native_session_id=:session WHERE task_id=:task AND run_id=:run"
                ),
                {
                    "boot": boot,
                    "child": e["native_child_id"],
                    "session": e["native_session_id"],
                    "task": e["task_id"],
                    "run": run,
                },
            )
        return candidate

    async def ingest_result(
        self,
        owner_id: str,
        manifest_ref: object,
        final: object,
        runtime_boot: object,
        authority: object,
        *,
        held: bool,
    ) -> dict[str, object]:
        """Only supervisor-authenticated final may enter. Caller supplies no task body.

        Historical boot/authority identify the committed binding. Current control
        classifies disposition only, under Stop's lock order; never grants work.
        """
        owner = uuid_string(owner_id)
        checked_fence = contract.authority(authority)
        boot = uuid_string(runtime_boot)
        ref(manifest_ref, "launch-manifest")
        if type(held) is not bool:
            raise CatalogError("INVALID_REQUEST")
        async with asyncio.timeout(4), self.engine.begin() as conn:
            instance = (
                (await conn.execute(sql("SELECT * FROM instance_control WHERE id=1 FOR UPDATE")))
                .mappings()
                .one_or_none()
            )
            lease = (
                (await conn.execute(sql("SELECT * FROM supervisor_lease WHERE id=1 FOR UPDATE")))
                .mappings()
                .one_or_none()
            )
            await store.lock(conn, owner)
            state = await store.state(conn, owner, manifest=manifest_ref)
            run = uuid_string(state["run_id"])
            manifest = await self.load_manifest(conn, owner, manifest_ref)
            if state["binding_id"] is None or state["release_started"] is not True:
                raise CatalogError("BINDING_REQUIRED")
            binding = await store.by_id(conn, owner, run, state["binding_id"])
            bound = mapping(binding["payload"])
            if boot != bound["runtime_boot"] or canonical(checked_fence) != canonical(
                bound["authority"]
            ):
                raise CatalogError("LINEAGE_MISMATCH")
            checked = contract.validate_final(final, manifest, binding)
            if state["final_id"] is not None:
                prior = await store.by_id(conn, owner, run, state["final_id"])
                if canonical(prior["payload"]) != canonical(checked):
                    raise CatalogError("RESULT_CONFLICT")
            else:
                receipt = catalog.envelope("native-task-receipt", checked)
                now = (await conn.execute(sql("SELECT clock_timestamp()"))).scalar_one()
                if not isinstance(now, datetime):
                    raise CatalogError("STORAGE_INCOMPATIBLE")
                disposition = contract.receive_disposition(
                    {} if instance is None else dict(instance),
                    {} if lease is None else dict(lease),
                    bound["authority"],
                    now,
                    held=held,
                )
                await store.put(conn, owner, run, receipt)
                await conn.execute(
                    sql("UPDATE managed_run SET final_id=:id WHERE run_id=:run"),
                    {"id": receipt["id"], "run": run},
                )
                for raw in sequence(mapping(manifest["payload"])["entries"]):
                    e = mapping(raw)
                    brief = await store.get(conn, owner, run, e["brief_ref"])
                    result = contract.blocked_result(brief)
                    await store.put(conn, owner, run, result)
                    await conn.execute(
                        sql(
                            "UPDATE managed_task SET result_id=:id,state='BLOCKED' WHERE task_id=:task AND run_id=:run"
                        ),
                        {"id": result["id"], "task": e["task_id"], "run": run},
                    )
                    await conn.execute(
                        sql(
                            "INSERT INTO managed_inbox(result_id,task_id,delivered,admitted,turn_completed,domain_result_consumed,disposition) VALUES (:result,:task,true,false,false,false,:disposition)"
                        ),
                        {
                            "result": result["id"],
                            "task": e["task_id"],
                            "disposition": disposition,
                        },
                    )
            command = uuid_string(state["command_id"])
        # Separate committed phase: an exception in check cannot erase raw results.
        return await self.readback({"schema_version": 1, "owner_id": owner, "command_id": command})

    async def check(self, owner_id: str, command_id: str) -> dict[str, object]:
        return await self._check(
            {"schema_version": 1, "owner_id": owner_id, "command_id": command_id}, consume=False
        )

    async def reconcile(self, request: object) -> dict[str, object]:
        return await self._check(request, consume=True)

    async def _check(self, request: object, *, consume: bool) -> dict[str, object]:
        value = validate_request("reconcile", request)
        owner, command = uuid_string(value["owner_id"]), uuid_string(value["command_id"])
        async with asyncio.timeout(4), self.engine.begin() as conn:
            await store.lock(conn, owner)
            state = await store.state(conn, owner, command=command)
            run = uuid_string(state["run_id"])
            if state["final_id"] is None:
                raise CatalogError("NEEDS_RECONCILIATION")
            run_record = await store.by_id(conn, owner, run, run)
            checker_ref = ref(mapping(run_record["payload"])["method_check_ref"], "method-checker")
            await store.get(conn, owner, run, checker_ref)
            rows = (
                (
                    await conn.execute(
                        sql("SELECT * FROM managed_task WHERE run_id=:run ORDER BY batch_index"),
                        {"run": run},
                    )
                )
                .mappings()
                .all()
            )
            for row in rows:
                brief = await store.by_id(conn, owner, run, row["brief_id"])
                result = await store.by_id(conn, owner, run, row["result_id"])
                checked = contract.method_check(brief, result, checker_ref)
                if row["check_id"] is None:
                    await store.put(conn, owner, run, checked)
                    await conn.execute(
                        sql("UPDATE managed_task SET check_id=:id WHERE task_id=:task"),
                        {"id": checked["id"], "task": row["task_id"]},
                    )
                else:
                    prior = await store.by_id(conn, owner, run, row["check_id"])
                    if canonical(prior["payload"]) != canonical(checked["payload"]):
                        raise CatalogError("RESULT_CONFLICT")
                if consume:
                    await conn.execute(
                        sql(
                            "UPDATE managed_inbox SET domain_result_consumed=true WHERE result_id=:id AND domain_result_consumed=false"
                        ),
                        {"id": result["id"]},
                    )
        return await self.readback(value)

    async def _verify_graph(
        self, conn: AsyncConnection, owner: str, run: str, graph: list[dict[str, object]]
    ) -> None:
        refs: dict[bytes, dict[str, object]] = {}

        def collect(value: object) -> None:
            if isinstance(value, dict):
                if (
                    set(value) == {"kind", "id", "revision", "digest"}
                    and type(value["kind"]) is str
                ):
                    checked = ref(value)
                    refs[canonical(checked)] = checked
                else:
                    for child in value.values():
                        collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)

        for item in graph:
            collect(item["payload"])
        local = {text(item["id"]): item for item in graph}
        for reference in refs.values():
            identity = uuid_string(reference["id"])
            if identity in local:
                if canonical(catalog.reference(local[identity])) != canonical(reference):
                    raise CatalogError("REF_MISMATCH")
            elif reference["kind"] in {
                "package",
                "technique",
                "procedure",
                "schema",
                "profile",
                "overlay",
                "method",
                "asset",
                "prompt",
                "template",
            }:
                found = (
                    await conn.execute(
                        sql(
                            "SELECT i.entity_kind FROM catalog_reservation r JOIN catalog_identity i ON i.id=r.id WHERE r.id=:id AND r.revision=:revision AND r.digest=:digest AND i.owner_id=:owner AND i.entity_kind=:kind"
                        ),
                        {**reference, "owner": owner},
                    )
                ).scalar_one_or_none()
                if found is None:
                    raise CatalogError("REF_UNAVAILABLE")
            else:
                await catalog.get(conn, owner, reference)
        for brief in (r for r in graph if r["kind"] == "task-brief"):
            body = mapping(brief["payload"])
            header = mapping(body["header"])
            cursor = local.get(uuid_string(header["through_cursor"]))
            if cursor is None or run not in local:
                raise CatalogError("CURSOR_UNAVAILABLE")
            contract.validate_cursor(header, cursor, local[run])
            bound_ref = ref(mapping(sequence(body["procedure_bindings"])[0])["bound_procedure_ref"])
            contract.validate_assignment(brief, local[uuid_string(bound_ref["id"])])
        for manifest in (r for r in graph if r["kind"] == "launch-manifest"):
            if contract.manifest_protocol(manifest) != contract.PROTOCOL:
                await self._verify_compositions(conn, owner, run, graph, manifest)
        from jsonschema import Draft202012Validator, ValidationError

        for result in (r for r in graph if r["kind"] == "task-result"):
            header = mapping(mapping(result["payload"])["header"])
            matches = [
                b
                for b in graph
                if b["kind"] == "task-brief"
                and canonical(mapping(b["payload"])["header"]) == canonical(header)
            ]
            if len(matches) != 1:
                raise CatalogError("ASSIGNMENT_MISMATCH")
            schema = local[uuid_string(ref(header["result_schema_ref"], "schema")["id"])]
            try:
                Draft202012Validator(mapping(schema["payload"])).validate(result["payload"])
            except ValidationError:
                raise CatalogError("RESULT_SCHEMA_MISMATCH") from None
            checker = ref(mapping(local[run]["payload"])["method_check_ref"], "method-checker")
            expected = contract.method_check(matches[0], result, checker)
            for check in (
                c
                for c in graph
                if c["kind"] == "method-check"
                and mapping(c["payload"]).get("task_result_ref") == catalog.reference(result)
            ):
                if canonical(check["payload"]) != canonical(expected["payload"]):
                    raise CatalogError("RESULT_CONFLICT")

    async def _verify_compositions(
        self,
        conn: AsyncConnection,
        owner: str,
        run: str,
        graph: list[dict[str, object]],
        manifest: dict[str, object],
    ) -> None:
        from omnis.modules.runs.native_preparation import read_receipt
        from omnis.modules.tasks import managed_composition

        payload = managed_composition.stage_payload(manifest, graph)
        local = {text(r["id"]): r for r in graph}
        run_body = mapping(local[run]["payload"])
        preparation_ref = ref(run_body["preparation_receipt_ref"], "native-preparation-receipt")
        _, receipt = await catalog.get(conn, owner, preparation_ref)
        prepared = await read_receipt(conn, owner, ref(mapping(receipt["payload"])["bundle_ref"]))
        bundle = mapping(mapping(prepared["bundle"])["payload"])
        if (
            prepared["receipt_ref"] != preparation_ref
            or bundle["selection_ref"] != mapping(manifest["payload"])["selection_ref"]
        ):
            raise CatalogError("PREPARATION_MISMATCH")
        for raw in sequence(payload["compositions"]):
            body = mapping(mapping(raw)["payload"])
            sections = sequence(load_json(text(body["text"], 65536)))
            brief = mapping(mapping(mapping(sections[2])["record"])["payload"])
            technique = ref(sequence(brief["technique_refs"])[0], "technique")
            row = (
                (
                    await conn.execute(
                        sql(
                            "SELECT package_key,entity_key FROM catalog_identity WHERE id=:id AND owner_id=:owner AND entity_kind='technique'"
                        ),
                        {"id": technique["id"], "owner": owner},
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None or body["preparation_receipt_ref"] != preparation_ref:
                raise CatalogError("COMPOSITION_REJECTED")
            expected = managed_composition.selected_skills(
                [mapping(p) for p in sequence(bundle["packages"])],
                brief["package_refs"],
                technique,
                [
                    {
                        "package_key": row["package_key"],
                        "key": row["entity_key"],
                        "entity_kind": "technique",
                        "ref": technique,
                    }
                ],
            )
            if sections[4:] != expected:
                raise CatalogError("COMPOSITION_REJECTED")

    async def readback_manifest(self, owner_id: str, manifest_ref: object) -> dict[str, object]:
        owner = uuid_string(owner_id)
        reference = ref(manifest_ref, "launch-manifest")
        async with asyncio.timeout(4), self.engine.begin() as conn:
            await store.lock(conn, owner)
            state = await store.state(conn, owner, manifest=reference)
            command = uuid_string(state["command_id"])
        return await self.readback({"schema_version": 1, "owner_id": owner, "command_id": command})

    async def readback(self, request: object) -> dict[str, object]:
        value = validate_request("readback", request)
        owner, command = uuid_string(value["owner_id"]), uuid_string(value["command_id"])
        async with asyncio.timeout(4), self.engine.begin() as conn:
            await store.lock(conn, owner)
            state = await store.state(conn, owner, command=command)
            run = uuid_string(state["run_id"])
            rows = (
                (
                    await conn.execute(
                        sql(
                            "SELECT envelope FROM managed_record WHERE owner_id=:owner AND run_id=:run ORDER BY id"
                        ),
                        {"owner": owner, "run": run},
                    )
                )
                .scalars()
                .all()
            )
            graph = [record(r) for r in rows]
            await self._verify_graph(conn, owner, run, graph)
            by_id = {text(r["id"]): r for r in graph}
            manifest = contract.validate_manifest(by_id[uuid_string(state["manifest_id"])])
            binding = (
                None
                if state["binding_id"] is None
                else contract.validate_binding(by_id[uuid_string(state["binding_id"])], manifest)
            )
            if state["final_id"] is not None:
                if binding is None:
                    raise CatalogError("STORAGE_INCOMPATIBLE")
                contract.validate_final(
                    by_id[uuid_string(state["final_id"])]["payload"], manifest, binding
                )
            briefs = [contract.validate_brief(r) for r in graph if r["kind"] == "task-brief"]
            results = [r for r in graph if r["kind"] == "task-result"]
            checks = [r for r in graph if r["kind"] == "method-check"]
            task_rows = (
                (
                    await conn.execute(
                        sql("SELECT * FROM managed_task WHERE run_id=:run ORDER BY batch_index"),
                        {"run": run},
                    )
                )
                .mappings()
                .all()
            )
            # One task/one attempt in this cold slice: expose the actual row.
            tasks = []
            for row in task_rows:
                item = dict(row)
                for key in (
                    "task_id",
                    "attempt_id",
                    "run_id",
                    "brief_id",
                    "result_id",
                    "check_id",
                    "runtime_boot",
                ):
                    if item[key] is not None:
                        item[key] = str(item[key])
                if item["state"] not in {"QUEUED", "BOUND", "BLOCKED"}:
                    raise CatalogError("STORAGE_INCOMPATIBLE")
                tasks.append(item)
            inbox = (
                (
                    await conn.execute(
                        sql(
                            "SELECT i.* FROM managed_inbox i JOIN managed_task t ON t.task_id=i.task_id WHERE t.run_id=:run ORDER BY t.batch_index"
                        ),
                        {"run": run},
                    )
                )
                .mappings()
                .all()
            )
            return {
                "manifest_ref": catalog.reference(manifest),
                "manifest": manifest,
                "binding": binding,
                "binding_ref": None if binding is None else catalog.reference(binding),
                "run_id": run,
                "status": "BLOCKED"
                if state["final_id"] is not None
                else "NEEDS_RECONCILIATION"
                if state["stage_started"]
                else "PREPARED",
                "stage_started": state["stage_started"],
                "release_started": state["release_started"],
                "briefs": briefs,
                "tasks": tasks,
                "results": results,
                "checks": checks,
                "records": graph,
                "inbox": [
                    {**dict(i), "result_id": str(i["result_id"]), "task_id": str(i["task_id"])}
                    for i in inbox
                ],
            }


def main(argv: list[str] | None = None) -> int:
    class Parser(argparse.ArgumentParser):
        def error(self, message: str) -> NoReturn:
            raise CatalogError("INVALID_ARGUMENTS")

    parser = Parser()
    parser.add_argument(
        "operation", choices=("prepare", "prepare-composed", "readback", "reconcile")
    )
    parser.add_argument("--request", required=True)
    parser.add_argument("--catalog-root")
    try:
        args = parser.parse_args(argv)
        from omnis.modules.settings.skill_catalog import read_file

        value = validate_request(args.operation, load_json(read_file(Path(args.request), 8192)))
        url = os.environ.get("OMNIS_DATABASE_URL")
        if not url:
            raise CatalogError("DATABASE_UNAVAILABLE")

        async def run() -> dict[str, object]:
            engine = database_engine(url)
            try:
                consumer = ManagedAdmission(
                    engine, Path(args.catalog_root) if args.catalog_root else None
                )
                if args.operation == "prepare":
                    return await consumer.prepare(value)
                if args.operation == "prepare-composed":
                    return await consumer.prepare_composed(value)
                if args.operation == "reconcile":
                    return await consumer.reconcile(value)
                return await consumer.readback(value)
            finally:
                await engine.dispose()

        print(canonical(asyncio.run(run())).decode())
        return 0
    except CatalogError as error:
        reason = error.reason
    except (SQLAlchemyError, TimeoutError):
        reason = "DATABASE_UNAVAILABLE"
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        reason = "MANAGED_REJECTED"
    print(canonical({"status": "BLOCKED", "reason": reason}).decode(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
