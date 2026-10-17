"""Qualified preparation DATA over retained cold material; never model authority."""

import json
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import text as sql
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.instance.schemas import NativeTaskCommand
from omnis.modules.runs.managed_admission import ManagedAdmission
from omnis.modules.runs.pure_probe import PureProbe
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.candidate_catalog import uuid_string
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks import managed_store as store
from omnis.modules.tasks.managed_contract import exact, mapping, record, ref, sequence

REQUESTED = {"provider": "openai-codex", "model": "gpt-6.1-sol", "effort": "xhigh"}
PURPOSE = "MODEL_TEST_PREPARE"


def qualify(value: object) -> dict[str, object]:
    """Recheck exact retained refs and real encoded bounds; no adapter dependency in API."""
    payload = exact(value, {"protocol", "mode", "context", "records", "material"})
    c = mapping(record(payload["context"], "model-test-context")["payload"])
    if c["purpose"] != PURPOSE or c["requested"] != REQUESTED or c["effective"] is not None:
        raise CatalogError("MODEL_TEST_REJECTED")
    for field, kind in (
        ("managed_run_ref", "managed-run"),
        ("snapshot_ref", "run-snapshot"),
        ("selection_ref", "execution-selection"),
        ("provider_config_ref", "provider-config"),
        ("brief_ref", "task-brief"),
        ("composition_ref", "prompt-composition"),
        ("manifest_ref", "launch-manifest"),
    ):
        matches = [
            record(r, kind) for r in sequence(payload["records"]) if mapping(r)["kind"] == kind
        ]
        if len(matches) != 1 or records.reference(matches[0]) != ref(c[field], kind):
            raise CatalogError("MODEL_TEST_REJECTED")
    if len(canonical(payload)) > 32768:
        raise CatalogError("MODEL_TEST_LIMIT")
    frames = [
        {
            "jsonrpc": "2.0",
            "id": "f" * 36,
            "method": "omnis.managed.model_initialize",
            "params": payload,
        },
        {
            "version": 1,
            "id": "f" * 36,
            "boot": "f" * 36,
            "capability": "f" * 64,
            "generation": 2**63 - 1,
            "epoch": 2**63 - 1,
            "deadline_ns": 2**63 - 1,
            "op": "task_model_initialize",
            "payload": payload,
        },
    ]
    if any(
        len(json.dumps(f, separators=(",", ":"), allow_nan=False).encode()) + 1 > 65536
        for f in frames
    ):
        raise CatalogError("MODEL_TEST_LIMIT")
    return payload


def accept(result: object, payload: dict[str, object]) -> dict[str, object]:
    from omnis.modules.tasks.managed_contract import authority, exact, integer, text

    qualify(payload)
    context = record(payload["context"], "model-test-context")
    c = mapping(context["payload"])
    v = exact(
        result,
        {
            "protocol",
            "context_ref",
            "runtime_boot",
            "authority",
            "status",
            "native_root_id",
            "native_child_id",
            "native_session_id",
            "native_turn",
            "observed_configuration_ref",
            "client_status",
            "model_calls",
            "inference_status",
            "account_status",
        },
    )
    authority(v["authority"])
    integer(v["model_calls"], 0, 0)
    if (
        v["protocol"] != payload["protocol"]
        or ref(v["context_ref"], "model-test-context") != records.reference(context)
        or canonical(v["authority"]) != canonical(c["authority"])
        or v["runtime_boot"] != c["runtime_boot"]
        or v["observed_configuration_ref"] != c["provider_config_ref"]
        or v["client_status"] != "DEFERRED_NO_CREDENTIAL"
        or v["inference_status"] != "HOLD"
        or v["account_status"] != "NOT_VERIFIED"
    ):
        raise CatalogError("MODEL_TEST_REJECTED")
    if v["status"] == "UNKNOWN":
        raise CatalogError("TASK_INDETERMINATE")
    if v["status"] != "TURN_BOUND_PRE_CLIENT_HOLD":
        raise CatalogError("MODEL_TEST_REJECTED")
    uuid_string(v["native_root_id"])
    uuid_string(v["native_child_id"])
    text(v["native_session_id"], 128)
    turn = exact(v["native_turn"], {"task_id", "turn_id"})
    if uuid_string(turn["task_id"]) != c["task_id"]:
        raise CatalogError("MODEL_TEST_REJECTED")
    text(turn["turn_id"], 256)
    return v


class ModelTest:
    def __init__(self, domain: ManagedAdmission) -> None:
        self.domain = domain

    async def completed(
        self, connection: AsyncConnection, command: NativeTaskCommand
    ) -> tuple[dict[str, object], dict[str, object]] | None:
        command = NativeTaskCommand.model_validate(
            command.model_dump(mode="python", warnings=False)
        )
        try:
            receipt = await store.command_receipt(
                connection, command.owner_id, str(command.initialization_id)
            )
        except CatalogError as error:
            if error.reason == "REF_UNAVAILABLE":
                return None
            raise
        body = mapping(record(receipt, "contract-input-command")["payload"])
        if (
            body["owner_id"] != command.owner_id
            or body["command_id"] != command.initialization_id
            or body["operation"] != "model_test_prepare"
        ):
            raise CatalogError("COMMAND_CONFLICT")
        references = exact(body["result_refs"], {"context_ref"})
        _, context = await store.owned(
            connection, command.owner_id, ref(references["context_ref"], "model-test-context")
        )
        c = mapping(record(context, "model-test-context")["payload"])
        request = {
            "manifest_ref": command.manifest_ref,
            "settings_operation_id": command.settings_operation_id,
            "authority": c["authority"],
            "runtime_boot": c["runtime_boot"],
            "command": command.model_dump(mode="json"),
        }
        if (
            c["owner_id"] != command.owner_id
            or c["preparation_id"] != command.initialization_id
            or c["source_manifest_ref"] != command.manifest_ref
            or c["settings_operation_id"] != command.settings_operation_id
        ):
            raise CatalogError("COMMAND_CONFLICT")
        await store.command_replay(
            connection,
            command.owner_id,
            str(command.initialization_id),
            "model_test_prepare",
            request,
        )
        _, observation = await self.dispatch(connection, command.owner_id, context, False)
        return None if observation is None else (context, observation)

    async def prepare(
        self,
        connection: AsyncConnection,
        owner: str,
        manifest_ref: object,
        identity: str,
        settings_operation_id: str,
        settings: object,
        authority: dict[str, object],
        runtime_boot: str,
        command: NativeTaskCommand,
    ) -> tuple[dict[str, object], bool]:
        await store.lock(connection, owner)
        identity, runtime_boot = uuid_string(identity), uuid_string(runtime_boot)
        state = await store.state(connection, owner, manifest=manifest_ref)
        run = uuid_string(state["run_id"])
        if any(state[k] is not None for k in ("binding_id", "final_id")) or any(
            state[k] is not False for k in ("stage_started", "release_started")
        ):
            raise CatalogError("MODEL_TEST_REJECTED")
        request = {
            "manifest_ref": ref(manifest_ref, "launch-manifest"),
            "settings_operation_id": uuid_string(settings_operation_id),
            "authority": authority,
            "runtime_boot": runtime_boot,
            "command": command.model_dump(mode="json"),
        }
        prior = await store.command_replay(
            connection, owner, identity, "model_test_prepare", request
        )
        if prior is not None:
            _, context = await store.owned(connection, owner, prior["context_ref"])
            return context, False
        if settings is None:
            raise CatalogError("MODEL_TEST_SETTINGS_REQUIRED")
        saved = mapping(settings)
        if saved.get("status") != "CONFIRMED" or saved.get("selection") != REQUESTED:
            raise CatalogError("MODEL_TEST_SETTINGS_REQUIRED")
        graph = await store.graph(connection, owner, run)
        runs = [record(r, "managed-run") for r in graph if r["kind"] == "managed-run"]
        if len(runs) != 1 or runs[0]["id"] != run:
            raise CatalogError("MODEL_TEST_REJECTED")
        original = mapping(runs[0]["payload"])
        # The old reader sees ONLY its original selection and receipt, never v5 DATA.
        source = await self.domain._source(
            connection,
            owner,
            {"selection_ref": original["selection_ref"], "composition_version": 4},
            preparation_ref=ref(original["preparation_receipt_ref"], "native-preparation-receipt"),
        )
        selected = mapping(source.selection["payload"])
        if selected["resolution"] != "NO_MODEL" or selected["effective"] is not None:
            raise CatalogError("MODEL_TEST_REJECTED")
        if self.domain.root is None:
            raise CatalogError("CATALOG_REQUIRED")
        probe = PureProbe(self.domain.engine, self.domain.root)
        _, snapshot, _, compiled = await probe.publications.load_probe(
            connection, owner, ref(selected["snapshot_ref"], "run-snapshot")
        )
        material = mapping(snapshot["payload"])
        ref(material["profile_ref"], "profile")
        if material["dependency_closure_refs"] != [] or material["dependency_artifact_refs"] != []:
            raise CatalogError("UNSUPPORTED_DEPENDENCY")
        if compiled.dependency_artifact_refs or compiled.dependency_closure_refs:
            raise CatalogError("UNSUPPORTED_DEPENDENCY")
        fresh_snapshot = records.envelope(
            "run-snapshot",
            {
                **material,
                "execution_purpose": PURPOSE,
                "original_snapshot_ref": records.reference(snapshot),
                "original_selection_ref": records.reference(source.selection),
                "preparation_receipt_ref": source.preparation_ref,
                "resolution": "PREPARATION_ONLY",
                "effective": None,
                "assessment_selectable": False,
            },
        )
        selection = records.envelope(
            "execution-selection",
            {
                **selected,
                "snapshot_ref": records.reference(fresh_snapshot),
                "purpose": PURPOSE,
                "requested": REQUESTED,
                "effective": None,
                "resolution": "PREPARATION_ONLY",
                "reason": "ACCOUNT_NOT_VERIFIED",
            },
        )
        fresh_run = records.envelope(
            "managed-run",
            {
                "purpose": PURPOSE,
                "owner_id": owner,
                "snapshot_ref": records.reference(fresh_snapshot),
                "selection_ref": records.reference(selection),
                "source_manifest_ref": request["manifest_ref"],
            },
        )
        run = str(fresh_run["id"])
        task_id, attempt_id = str(uuid4()), str(uuid4())
        brief = records.envelope(
            "task-brief",
            {
                "purpose": PURPOSE,
                "run_id": run,
                "task_id": task_id,
                "attempt_id": attempt_id,
                "batch_index": 0,
                "selection_ref": records.reference(selection),
                "procedure_ref": source.procedure_ref,
                "objective": source.procedure.objective,
                "allowed_capability_ids": [],
            },
        )
        composition = records.envelope(
            "prompt-composition",
            {
                "purpose": PURPOSE,
                "brief_ref": records.reference(brief),
                "preparation_receipt_ref": source.preparation_ref,
                "package_refs": selected["selected_package_refs"],
                "text": source.procedure.objective,
                "text_digest": sha256(source.procedure.objective.encode()).hexdigest(),
            },
        )
        manifest = records.envelope(
            "launch-manifest",
            {
                "purpose": PURPOSE,
                "run_id": run,
                "selection_ref": records.reference(selection),
                "entries": [
                    {
                        "batch_index": 0,
                        "task_id": task_id,
                        "attempt_id": attempt_id,
                        "brief_ref": records.reference(brief),
                        "composition_ref": records.reference(composition),
                    }
                ],
            },
        )
        configuration = records.envelope(
            "provider-config",
            {
                "version": 2,
                "owner_id": owner,
                "run_id": run,
                "settings_operation_id": request["settings_operation_id"],
                "provenance": "NATIVE_SETTINGS_SAVED_SELECTION_READBACK_V2",
                "requested": REQUESTED,
                "api_mode": "codex_responses",
                "reasoning_config": {"enabled": True, "effort": "xhigh"},
                "fallback": None,
                "auxiliary": False,
                "fast": False,
                "account_status": "NOT_VERIFIED",
                "inference_status": "HOLD",
            },
        )
        context = records.envelope(
            "model-test-context",
            {
                "version": 5,
                "purpose": PURPOSE,
                "owner_id": owner,
                "run_id": run,
                **{k: v for k, v in request.items() if k != "command"},
                "preparation_id": identity,
                "manifest_ref": records.reference(manifest),
                "managed_run_ref": records.reference(fresh_run),
                "task_id": task_id,
                "attempt_id": attempt_id,
                "batch_index": 0,
                "brief_ref": records.reference(brief),
                "composition_ref": records.reference(composition),
                "source_manifest_ref": ref(manifest_ref, "launch-manifest"),
                "preparation_receipt_ref": source.preparation_ref,
                "original_selection_ref": records.reference(source.selection),
                "snapshot_ref": records.reference(fresh_snapshot),
                "selection_ref": records.reference(selection),
                "provider_config_ref": records.reference(configuration),
                "procedure_ref": source.procedure_ref,
                "package_refs": selected["selected_package_refs"],
                "material_digest": material["material_digest"],
                "resolved_index_digest": material["resolved_index_digest"],
                "requested": REQUESTED,
                "effective": None,
                "account_status": "NOT_VERIFIED",
                "inference_status": "HOLD",
            },
        )
        produced = [
            fresh_run,
            fresh_snapshot,
            selection,
            configuration,
            brief,
            composition,
            manifest,
            context,
        ]
        material_bundle = record(source.preparation_bundle, "native-preparation-bundle")
        payload: dict[str, object] = {
            "protocol": "omnis-managed-admission-v5",
            "mode": "CREATE",
            "context": context,
            "records": produced[:-1],
            "material": {
                "bundle_ref": records.reference(material_bundle),
                "bundle": material_bundle,
            },
        }
        qualify(payload)
        if len(canonical(produced)) > 32768:
            raise CatalogError("MODEL_TEST_LIMIT")
        # Size the actual producer before any persistence, not one legacy sample.
        await store.put(connection, owner, run, fresh_run)
        await store.put(connection, owner, run, manifest)
        await connection.execute(
            sql(
                "INSERT INTO managed_run(run_id,owner_id,command_id,request_digest,manifest_id) "
                "VALUES (:run,:owner,:command,:digest,:manifest)"
            ),
            {
                "run": run,
                "owner": owner,
                "command": identity,
                "digest": sha256(canonical(request)).hexdigest(),
                "manifest": manifest["id"],
            },
        )
        for item in produced:
            if item not in (fresh_run, manifest):
                await store.put(connection, owner, run, item)
            back = await store.get(connection, owner, run, records.reference(item))
            if canonical(back) != canonical(item):
                raise CatalogError("MODEL_TEST_REJECTED")
        await connection.execute(
            sql(
                "INSERT INTO managed_task(task_id,attempt_id,run_id,batch_index,brief_id,state) "
                "VALUES (:task,:attempt,:run,0,:brief,'QUEUED')"
            ),
            {"task": task_id, "attempt": attempt_id, "run": run, "brief": brief["id"]},
        )
        material = records.envelope(
            "model-test-material",
            {"context_ref": records.reference(context), "material": payload["material"]},
        )
        await store.put(connection, owner, run, material)
        await store.command_complete(
            connection,
            owner,
            run,
            identity,
            "model_test_prepare",
            request,
            {"context_ref": records.reference(context)},
        )
        return context, True

    async def dispatch(
        self, connection: AsyncConnection, owner: str, context: dict[str, object], created: bool
    ) -> tuple[dict[str, object], dict[str, object] | None]:
        c = mapping(context["payload"])
        run = str(c["run_id"])
        rows = await store.graph(connection, owner, run)
        selected = []
        for field in (
            "managed_run_ref",
            "snapshot_ref",
            "selection_ref",
            "provider_config_ref",
            "brief_ref",
            "composition_ref",
            "manifest_ref",
        ):
            selected.append(await store.get(connection, owner, run, c[field]))
        materials = [
            r
            for r in rows
            if r["kind"] == "model-test-material"
            and mapping(r["payload"]).get("context_ref") == records.reference(context)
        ]
        if len(materials) != 1:
            raise CatalogError("MODEL_TEST_REJECTED")
        payload: dict[str, object] = {
            "protocol": "omnis-managed-admission-v5",
            "mode": "CREATE" if created else "STATUS",
            "context": context,
            "records": selected,
            "material": mapping(materials[0]["payload"])["material"],
        }
        qualify(payload)
        observed = [
            r
            for r in rows
            if r["kind"] == "native-turn"
            and mapping(r["payload"]).get("context_ref") == records.reference(context)
        ]
        if len(observed) > 1:
            raise CatalogError("STORAGE_INCOMPATIBLE")
        if observed:
            accept(observed[0]["payload"], payload)
        return payload, observed[0] if observed else None

    async def persist(
        self, connection: AsyncConnection, owner: str, payload: dict[str, object], result: object
    ) -> dict[str, object]:
        context = record(payload["context"], "model-test-context")
        _, checked = await store.owned(connection, owner, records.reference(context))
        current, prior = await self.dispatch(connection, owner, checked, False)
        if canonical({k: v for k, v in current.items() if k != "mode"}) != canonical(
            {k: v for k, v in payload.items() if k != "mode"}
        ):
            raise CatalogError("MODEL_TEST_REJECTED")
        observation = accept(result, current)
        if observation["status"] != "TURN_BOUND_PRE_CLIENT_HOLD":
            raise CatalogError("TASK_INDETERMINATE")
        if prior is not None:
            if canonical(prior["payload"]) != canonical(observation):
                raise CatalogError("MODEL_TEST_REJECTED")
            return prior
        item = records.envelope("native-turn", observation)
        run = str(mapping(context["payload"])["run_id"])
        await store.put(connection, owner, run, item)
        return await store.get(connection, owner, run, records.reference(item))
