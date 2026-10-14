"""Private, owner-locked immutable RUN input commands. Never assigns a task."""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

from sqlalchemy import text as sql
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.core.db import database_engine
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.candidate_catalog import uuid_string
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical, load_json
from omnis.modules.tasks import managed_contract as contract
from omnis.modules.tasks import managed_store as store
from omnis.modules.tasks.managed_contract import exact, mapping, ref

if TYPE_CHECKING:
    from omnis.modules.runs.managed_admission import BuildSource


def validate_request(operation: str, value: object) -> dict[str, object]:
    fields = {"schema_version", "owner_id", "command_id"}
    if operation in {"create-context", "create-method-context"}:
        fields |= {"selection_ref", "preparation_command_id"}
    elif operation == "create-input":
        fields |= {"context_ref", "input"}
    elif operation == "append-mission":
        fields |= {"context_ref", "mission_ref", "criterion_id"}
    elif operation == "create-denominator":
        fields |= {"context_ref", "mission_ref", "input_ref"}
    elif operation not in {
        "read-context",
        "read-method-context",
        "read-input",
        "read-mission",
        "read-denominator",
    }:
        raise CatalogError("INVALID_REQUEST")
    if operation == "create-method-context" and "criterion_ids" in mapping(value):
        fields.add("criterion_ids")
    result = exact(value, fields)
    if "criterion_ids" in result:
        from omnis.modules.tasks.criterion_checks import allocation

        allocation(result["criterion_ids"])
    contract.integer(result["schema_version"], 1, 2 if operation.startswith("create-") else 1)
    uuid_string(result["owner_id"])
    uuid_string(result["command_id"])
    if operation in {"create-context", "create-method-context"}:
        ref(result["selection_ref"], "execution-selection")
        uuid_string(result["preparation_command_id"])
    elif operation == "create-input":
        ref(result["context_ref"], "contract-input-context")
        mapping(result["input"])
    elif operation == "append-mission":
        ref(result["context_ref"], "contract-input-context")
        mission = ref(result["mission_ref"], "mission")
        contract.integer(mission["revision"], 1, 1)
        uuid_string(result["criterion_id"])
    elif operation == "create-denominator":
        contract.integer(result["schema_version"], 1, 1)
        ref(result["context_ref"], "contract-input-context")
        ref(result["mission_ref"], "mission")
        ref(result["input_ref"], "contract-case-records")
    return result


class ContractInputs:
    def __init__(self, engine: AsyncEngine, catalog_root: Path | None = None) -> None:
        self.engine, self.root = engine, catalog_root

    async def create_method_context(self, request: object) -> dict[str, object]:
        return await self.create_context(request, method_execution=True)

    async def create_context(
        self, request: object, *, method_execution: bool = False
    ) -> dict[str, object]:
        from omnis.modules.runs.managed_admission import ManagedAdmission
        from omnis.modules.tasks.contract_case_input import require_slots

        if type(method_execution) is not bool:
            raise CatalogError("INVALID_REQUEST")
        operation = "create-method-context" if method_execution else "create-context"
        value = validate_request(operation, request)
        version = contract.integer(value["schema_version"], 1, 2)
        owner, command = uuid_string(value["owner_id"]), uuid_string(value["command_id"])
        async with asyncio.timeout(15), self.engine.begin() as conn:
            await store.lock(conn, owner)
            prior = await store.command_replay(conn, owner, command, operation, value)
            if prior is not None:
                return {**prior, "created": False}
            managed = ManagedAdmission(self.engine, self.root)
            source = await managed._source(
                conn, owner, {**value, "composition_version": version + 1}
            )
            require_slots(source.procedure.model_dump(mode="json")["slots"], version=version)
            schema_ref, _, _ = source.input_schema()
            graph = source.build(
                context_only=True,
                method_execution=method_execution,
                criterion_ids=value.get("criterion_ids"),
            )
            run = next(r for r in graph if r["kind"] == "managed-run")
            body = mapping(run["payload"])
            context = records.envelope(
                "contract-input-context",
                {
                    "version": version,
                    "namespace": "RUN",
                    "owner_id": owner,
                    "basis_ref": records.reference(run),
                    "snapshot_ref": body["snapshot_ref"],
                    "procedure_ref": source.procedure_ref,
                    "schema_ref": schema_ref,
                    "selection_ref": body["selection_ref"],
                    "mission_ref": body["mission_ref"],
                    "focus_ref": body["focus_ref"],
                },
            )
            graph.append(context)
            if len(canonical(graph)) + source.preparation_bytes > 65536:
                raise CatalogError("CONTEXT_OVERFLOW")
            await managed._verify_graph(conn, owner, uuid_string(run["id"]), graph)
            for item in graph:
                await store.put(conn, owner, uuid_string(run["id"]), item)
            result_refs: dict[str, object] = {
                "context_ref": records.reference(context),
                "run_ref": records.reference(run),
            }
            await store.command_complete(
                conn, owner, uuid_string(run["id"]), command, operation, value, result_refs
            )
            return {**result_refs, "created": True}

    async def create_input(self, request: object) -> dict[str, object]:
        from omnis.modules.tasks.contract_case_input import produce_input

        value = validate_request("create-input", request)
        owner, command = uuid_string(value["owner_id"]), uuid_string(value["command_id"])
        async with asyncio.timeout(15), self.engine.begin() as conn:
            await store.lock(conn, owner)
            prior = await store.command_replay(conn, owner, command, "create-input", value)
            if prior is not None:
                return {**prior, "created": False}
            run, context = await store.owned(
                conn, owner, ref(value["context_ref"], "contract-input-context")
            )
            if mapping(context["payload"])["version"] != value["schema_version"]:
                raise CatalogError("REF_MISMATCH")
            graph = await store.graph(conn, owner, run)
            from omnis.modules.tasks.mission_revisions import require_no_revision

            require_no_revision(graph)
            source = await self.current_source(conn, owner, context, graph)
            schema_ref, raw_schema, _ = source.input_schema()
            if schema_ref != mapping(context["payload"])["schema_ref"]:
                raise CatalogError("REF_MISMATCH")
            item = produce_input(context, value["input"], raw_schema, command)
            await store.put(conn, owner, run, item)
            result_refs: dict[str, object] = {
                "context_ref": records.reference(context),
                "input_ref": records.reference(item),
            }
            await store.command_complete(
                conn, owner, run, command, "create-input", value, result_refs
            )
            return {**result_refs, "created": True}

    async def append_mission(self, request: object) -> dict[str, object]:
        from omnis.modules.tasks import mission_revisions

        value = validate_request("append-mission", request)
        owner, command = uuid_string(value["owner_id"]), uuid_string(value["command_id"])
        async with asyncio.timeout(15), self.engine.begin() as conn:
            await store.lock(conn, owner)
            run, context = await store.owned(conn, owner, value["context_ref"])
            original = await store.get(conn, owner, run, value["mission_ref"])
            graph = await store.graph(conn, owner, run)
            mission_revisions.require_supported(graph, context, original)
            revised = mission_revisions.append(original, value["criterion_id"])
            prior = await store.command_replay(conn, owner, command, "append-mission", value)
            if prior is not None:
                if prior != {
                    "context_ref": value["context_ref"],
                    "predecessor_ref": value["mission_ref"],
                    "mission_ref": records.reference(revised),
                }:
                    raise CatalogError("COMMAND_CONFLICT")
                return {**prior, "created": False}
            if any(r["kind"] == "mission" and r["revision"] == 2 for r in graph):
                raise CatalogError("MISSION_REVISION_CONFLICT")
            await self._require_settled(conn, owner, run, graph)
            source = await self.current_source(conn, owner, context, graph)
            if (
                source.procedure.key != "map-records"
                or source.procedure.verification_kind != "CONTRACT"
            ):
                raise CatalogError("MISSION_REVISION_UNSUPPORTED")
            await store.put(conn, owner, run, revised)
            result_refs = {
                "context_ref": value["context_ref"],
                "predecessor_ref": value["mission_ref"],
                "mission_ref": records.reference(revised),
            }
            await store.command_complete(
                conn, owner, run, command, "append-mission", value, result_refs
            )
            return {**result_refs, "created": True}

    async def create_denominator(self, request: object) -> dict[str, object]:
        from omnis.modules.coverage import denominator

        value = validate_request("create-denominator", request)
        owner, command = uuid_string(value["owner_id"]), uuid_string(value["command_id"])
        async with asyncio.timeout(15), self.engine.begin() as conn:
            # Existing generic writer resolves public ahead of temp shadows.
            await conn.execute(sql("SET LOCAL search_path = pg_catalog, public, pg_temp"))
            await store.lock(conn, owner)
            run, _ = await store.owned(conn, owner, value["context_ref"])
            await store.get(conn, owner, run, value["mission_ref"])
            await store.get(conn, owner, run, value["input_ref"])
            graph = await store.graph(conn, owner, run)
            await denominator.validate_graph(conn, owner, run, graph)
            prior = await store.command_replay(conn, owner, command, "create-denominator", value)
            if prior is not None:
                item = await store.get(
                    conn, owner, run, ref(prior.get("denominator_ref"), denominator.KIND)
                )
                denominator.validate_receipt(
                    await store.command_receipt(conn, owner, command), item, command=command
                )
                return {**prior, "created": False}
            body = await denominator.derive(
                conn, owner, graph, value["context_ref"], value["mission_ref"], value["input_ref"]
            )
            retained = [r for r in graph if r["kind"] == denominator.KIND]
            matches = [
                r
                for r in retained
                if canonical(denominator.material(denominator.payload(r["payload"])))
                == canonical(body)
            ]
            if matches:
                item = matches[0]
                created = False
            else:
                revision = contract.integer(len(retained) + 1, 1, denominator.REVISION_LIMIT)
                body.update(
                    denominator_revision=revision,
                    provenance={
                        "producer_key": denominator.KIND,
                        "producer_revision": denominator.KIND + "-v1",
                        "command_id": command,
                    },
                )
                denominator.payload(body)
                item = records.envelope(denominator.KIND, body)
                await store.put(conn, owner, run, item)
                created = True
            result = denominator.result_refs(denominator.payload(item["payload"]), item)
            await store.command_complete(
                conn, owner, run, command, "create-denominator", value, result
            )
            return {**result, "created": created}

    async def _require_settled(
        self, conn: AsyncConnection, owner: str, run: str, graph: list[dict[str, object]]
    ) -> None:
        """Owner lock spans this check and M2 commit, not the later native send.

        A committed dispatch intent therefore fences cutover until authentic
        final/result/check settlement. Replay does not pass through this guard.
        All authority reads are public-bound; temp shadows cannot grant no-work.
        """
        state = (
            (
                await conn.execute(
                    sql("SELECT * FROM public.managed_run WHERE owner_id=:owner AND run_id=:run"),
                    {"owner": owner, "run": run},
                )
            )
            .mappings()
            .one_or_none()
        )
        tasks = (
            (
                await conn.execute(
                    sql("SELECT * FROM public.managed_task WHERE run_id=:run ORDER BY batch_index"),
                    {"run": run},
                )
            )
            .mappings()
            .all()
        )
        inbox = (
            (
                await conn.execute(
                    sql(
                        "SELECT i.* FROM public.managed_inbox i JOIN public.managed_task t ON t.task_id=i.task_id WHERE t.run_id=:run ORDER BY t.batch_index"
                    ),
                    {"run": run},
                )
            )
            .mappings()
            .all()
        )
        work_kinds = {"runtime-binding", "native-task-receipt", "task-result", "method-check"}
        if state is None or (
            state["stage_started"] is False
            and state["release_started"] is False
            and state["binding_id"] is None
            and state["final_id"] is None
        ):
            if (
                inbox
                or any(r["kind"] in work_kinds for r in graph)
                or (state is None and tasks)
                or any(
                    t["state"] != "QUEUED"
                    or any(
                        t[k] is not None
                        for k in (
                            "result_id",
                            "check_id",
                            "runtime_boot",
                            "native_child_id",
                            "native_session_id",
                        )
                    )
                    for t in tasks
                )
            ):
                raise CatalogError("NEEDS_RECONCILIATION")
            return
        if (
            state["stage_started"] is not True
            or state["release_started"] is not True
            or state["binding_id"] is None
            or state["final_id"] is None
            or not tasks
        ):
            raise CatalogError("NEEDS_RECONCILIATION")
        manifest = contract.validate_manifest(
            await store.by_id(conn, owner, run, state["manifest_id"])
        )
        binding = contract.validate_binding(
            await store.by_id(conn, owner, run, state["binding_id"]), manifest
        )
        final = contract.record(
            await store.by_id(conn, owner, run, state["final_id"]), "native-task-receipt"
        )
        contract.validate_final(final["payload"], manifest, binding)
        entries = [mapping(e) for e in contract.sequence(mapping(manifest["payload"])["entries"])]
        if len(tasks) != len(entries) or len(inbox) != len(tasks):
            raise CatalogError("NEEDS_RECONCILIATION")
        for task, entry, received in zip(tasks, entries, inbox, strict=True):
            if (
                str(task["task_id"]) != entry["task_id"]
                or str(task["brief_id"]) != ref(entry["brief_ref"])["id"]
                or task["result_id"] is None
                or task["check_id"] is None
                or task["state"] not in {"BLOCKED", "SUCCEEDED"}
                or str(received["task_id"]) != str(task["task_id"])
                or str(received["result_id"]) != str(task["result_id"])
                or received["delivered"] is not True
                or received["admitted"] is not False
                or received["turn_completed"] is not False
                or type(received["domain_result_consumed"]) is not bool
                or received["disposition"] not in {"RECEIVED", "HELD_FOR_RECONCILIATION"}
            ):
                raise CatalogError("NEEDS_RECONCILIATION")
            result = contract.record(
                await store.by_id(conn, owner, run, task["result_id"]), "task-result"
            )
            check = contract.record(
                await store.by_id(conn, owner, run, task["check_id"]), "method-check"
            )
            body = mapping(check["payload"])
            if (
                body.get("task_result_ref") != records.reference(result)
                or body.get("brief_ref") != entry["brief_ref"]
                or body.get("status") not in {"COMPLETE", "INCOMPLETE", "UNKNOWN"}
                or task["state"] != ("SUCCEEDED" if body["status"] == "COMPLETE" else "BLOCKED")
            ):
                raise CatalogError("NEEDS_RECONCILIATION")
        # Reuse receive-only receipt/check/outcome validation in this transaction;
        # opening readback's second owner-locked transaction would deadlock.
        from omnis.modules.runs.managed_admission import ManagedAdmission

        await ManagedAdmission(self.engine, self.root)._verify_graph(conn, owner, run, graph)

    async def current_source(
        self, conn: AsyncConnection, owner: str, context: object, graph: list[dict[str, object]]
    ) -> "BuildSource":
        from omnis.modules.runs.managed_admission import ManagedAdmission
        from omnis.modules.tasks.contract_case_input import require_slots

        checked = contract.record(context, "contract-input-context")
        body = exact(
            checked["payload"],
            set(
                "version namespace owner_id basis_ref snapshot_ref procedure_ref schema_ref selection_ref mission_ref focus_ref".split()
            ),
        )
        version = contract.integer(body["version"], 1, 2)
        if body["namespace"] != "RUN" or body["owner_id"] != owner:
            raise CatalogError("REF_UNAVAILABLE")
        basis = ref(body["basis_ref"], "managed-run")
        matches = [r for r in graph if records.reference(r) == basis]
        if len(matches) != 1:
            raise CatalogError("REF_UNAVAILABLE")
        run = mapping(matches[0]["payload"])
        for key, kind in (
            ("snapshot_ref", "run-snapshot"),
            ("selection_ref", "execution-selection"),
            ("mission_ref", "mission"),
            ("focus_ref", "focus"),
        ):
            if ref(body[key], kind) != run[key]:
                raise CatalogError("REF_MISMATCH")
        source = await ManagedAdmission(self.engine, self.root)._source(
            conn,
            owner,
            {"selection_ref": body["selection_ref"], "composition_version": version + 1},
            preparation_ref=ref(run["preparation_receipt_ref"], "native-preparation-receipt"),
        )
        require_slots(source.procedure.model_dump(mode="json")["slots"], version=version)
        if (
            ref(body["procedure_ref"], "procedure") != source.procedure_ref
            or ref(body["schema_ref"], "schema") != source.input_schema()[0]
        ):
            raise CatalogError("REF_MISMATCH")
        return source

    async def read(self, operation: str, request: object) -> dict[str, object]:
        value = validate_request(operation, request)
        owner, command = uuid_string(value["owner_id"]), uuid_string(value["command_id"])
        async with asyncio.timeout(4), self.engine.begin() as conn:
            if operation == "read-denominator":
                await conn.execute(sql("SET LOCAL search_path = pg_catalog, public, pg_temp"))
            await store.lock(conn, owner)
            receipt = await store.command_receipt(conn, owner, command)
            body = mapping(receipt["payload"])
            expected_operation = (
                "append-mission"
                if operation == "read-mission"
                else operation.replace("read-", "create-")
            )
            if body["operation"] != expected_operation:
                raise CatalogError("COMMAND_CONFLICT")
            result = mapping(body["result_refs"])
            if operation == "read-denominator":
                from omnis.modules.coverage import denominator

                run, item = await store.owned(
                    conn, owner, ref(result.get("denominator_ref"), denominator.KIND)
                )
                await denominator.validate_graph(
                    conn, owner, run, await store.graph(conn, owner, run)
                )
                denominator.validate_receipt(receipt, item, command=command)
            values = {
                key.replace("_ref", ""): (await store.owned(conn, owner, ref(value)))[1]
                for key, value in result.items()
            }
            return {**result, **values}


def main(argv: list[str] | None = None) -> int:
    class Parser(argparse.ArgumentParser):
        def error(self, message: str) -> NoReturn:
            raise CatalogError("INVALID_ARGUMENTS")

    parser = Parser()
    parser.add_argument(
        "operation",
        choices=(
            "create-context",
            "create-method-context",
            "create-input",
            "append-mission",
            "create-denominator",
            "read-context",
            "read-method-context",
            "read-input",
            "read-mission",
            "read-denominator",
        ),
    )
    parser.add_argument("--request", required=True)
    parser.add_argument("--catalog-root")
    try:
        from omnis.modules.settings.skill_catalog import read_file
        from omnis.modules.tasks.contract_case_input import utf8_json_text

        args = parser.parse_args(argv)
        value = validate_request(
            args.operation, load_json(utf8_json_text(read_file(Path(args.request), 16384)))
        )
        url = os.environ.get("OMNIS_DATABASE_URL")
        if not url:
            raise CatalogError("DATABASE_UNAVAILABLE")

        async def run() -> dict[str, object]:
            engine = database_engine(url)
            try:
                service = ContractInputs(
                    engine, Path(args.catalog_root) if args.catalog_root else None
                )
                if args.operation == "create-context":
                    return await service.create_context(value)
                if args.operation == "create-method-context":
                    return await service.create_method_context(value)
                if args.operation == "create-input":
                    return await service.create_input(value)
                if args.operation == "append-mission":
                    return await service.append_mission(value)
                if args.operation == "create-denominator":
                    return await service.create_denominator(value)
                return await service.read(args.operation, value)
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
