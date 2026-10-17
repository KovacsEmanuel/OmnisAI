"""Qualified preparation DATA over retained cold material; never model authority."""

import json
from datetime import UTC, datetime, timedelta
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
    execution = payload["protocol"] == "omnis-managed-admission-v6"
    if (
        c["purpose"] != ("SETTINGS_TEST" if execution else PURPOSE)
        or c["requested"] != REQUESTED
        or (not execution and c["effective"] is not None)
    ):
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
        or v["inference_status"]
        != ("AWAITING_SEND" if payload["protocol"] == "omnis-managed-admission-v6" else "HOLD")
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
            or body["operation"] != command.action
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
            command.action,
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
        execution = command.action == "model_test_start"
        purpose = "SETTINGS_TEST" if execution else PURPOSE
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
        prior = await store.command_replay(connection, owner, identity, command.action, request)
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
        fresh_run_id = str(uuid4())
        configuration = records.envelope(
            "provider-config",
            {
                "version": 3 if execution else 2,
                "owner_id": owner,
                "run_id": fresh_run_id,
                "settings_operation_id": request["settings_operation_id"],
                "provenance": "NATIVE_SETTINGS_SAVED_SELECTION_READBACK_V2",
                "requested": REQUESTED,
                "api_mode": "codex_responses",
                "reasoning_config": {"enabled": True, "effort": "xhigh"},
                "fallback": None,
                "auxiliary": False,
                "fast": False,
                **({"output_policy": "MONITOR_SUBSCRIPTION"} if execution else {}),
                "account_status": "NOT_VERIFIED",
                "inference_status": "AWAITING_SEND" if execution else "HOLD",
            },
        )
        effective = (
            {
                "provider_config_ref": records.reference(configuration),
                "model_id": REQUESTED["model"],
                "effort": REQUESTED["effort"],
                "transport_config_ref": records.reference(configuration),
            }
            if execution
            else None
        )
        fresh_snapshot = records.envelope(
            "run-snapshot",
            {
                **material,
                "execution_purpose": purpose,
                "original_snapshot_ref": records.reference(snapshot),
                "original_selection_ref": records.reference(source.selection),
                "preparation_receipt_ref": source.preparation_ref,
                "resolution": "EXACT" if execution else "PREPARATION_ONLY",
                "effective": effective,
                "assessment_selectable": False,
            },
        )
        selection = records.envelope(
            "execution-selection",
            {
                **selected,
                "snapshot_ref": records.reference(fresh_snapshot),
                "purpose": purpose,
                "requested": REQUESTED,
                "effective": effective,
                "resolution": "EXACT" if execution else "PREPARATION_ONLY",
                "reason": "NATIVE_CONFIGURATION_REQUIRED" if execution else "ACCOUNT_NOT_VERIFIED",
            },
        )
        fresh_run = records.envelope(
            "managed-run",
            {
                "purpose": purpose,
                "owner_id": owner,
                "snapshot_ref": records.reference(fresh_snapshot),
                "selection_ref": records.reference(selection),
                "source_manifest_ref": request["manifest_ref"],
            },
        )
        fresh_run = {**fresh_run, "id": fresh_run_id}
        fresh_run["digest"] = sha256(
            canonical({k: v for k, v in fresh_run.items() if k != "digest"})
        ).hexdigest()
        run = fresh_run_id
        task_id, attempt_id = str(uuid4()), str(uuid4())
        brief = records.envelope(
            "task-brief",
            {
                "purpose": purpose,
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
                "purpose": purpose,
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
                "purpose": purpose,
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
        context = records.envelope(
            "model-test-context",
            {
                "version": 6 if execution else 5,
                **(
                    {"campaign_deadline": (datetime.now(UTC) + timedelta(seconds=3600)).isoformat()}
                    if execution
                    else {}
                ),
                "purpose": purpose,
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
                "effective": effective,
                "account_status": "NOT_VERIFIED",
                "inference_status": "AWAITING_SEND" if execution else "HOLD",
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
            "protocol": "omnis-managed-admission-v6" if execution else "omnis-managed-admission-v5",
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
            command.action,
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
        execution = c["version"] == 6
        payload: dict[str, object] = {
            "protocol": "omnis-managed-admission-v6" if execution else "omnis-managed-admission-v5",
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

    async def replay_execution(
        self, connection: AsyncConnection, command: NativeTaskCommand
    ) -> dict[str, object] | None:
        try:
            saved = await store.command_receipt(
                connection, command.owner_id, str(command.protocol_id)
            )
        except CatalogError as error:
            if error.reason == "REF_UNAVAILABLE":
                return None
            raise
        body = mapping(record(saved, "contract-input-command")["payload"])
        if body["operation"] != command.action or body["owner_id"] != command.owner_id:
            raise CatalogError("COMMAND_CONFLICT")
        run, attempt = await store.owned(
            connection, command.owner_id, mapping(body["result_refs"])["attempt_ref"]
        )
        a = mapping(record(attempt, "model-test-attempt")["payload"])
        turn = await store.get(connection, command.owner_id, run, a["turn_ref"])
        authority = mapping(mapping(record(turn, "native-turn")["payload"])["authority"])
        request = command.model_dump(mode="json")
        # The immutable receipt authenticates the original send; reader fences grant no work.
        request.update(
            expected_epoch=authority["epoch"], expected_generation=authority["generation"]
        )
        await store.command_replay(
            connection, command.owner_id, str(command.protocol_id), command.action, request
        )
        return attempt

    async def reserve_execution(
        self,
        connection: AsyncConnection,
        command: NativeTaskCommand,
    ) -> tuple[dict[str, object], bool]:
        from datetime import UTC, datetime, timedelta

        from omnis.modules.runs.model_dispatch import data_decision
        from omnis.policy import budgets
        from omnis.policy.model_projection import SyntheticApproval

        await budgets._transaction(connection, command.owner_id)
        prior = await store.command_replay(
            connection,
            command.owner_id,
            str(command.protocol_id),
            command.action,
            command.model_dump(mode="json"),
        )
        if prior is not None:
            _, attempt = await store.owned(connection, command.owner_id, prior["attempt_ref"])
            return attempt, False
        start = await store.command_receipt(
            connection, command.owner_id, str(command.initialization_id)
        )
        start_body = mapping(record(start, "contract-input-command")["payload"])
        if start_body["operation"] != "model_test_start":
            raise CatalogError("MODEL_TEST_REJECTED")
        _, context = await store.owned(
            connection, command.owner_id, mapping(start_body["result_refs"])["context_ref"]
        )
        payload, turn = await self.dispatch(connection, command.owner_id, context, False)
        c = mapping(context["payload"])
        if c["version"] != 6 or c["source_manifest_ref"] != command.manifest_ref or turn is None:
            raise CatalogError("MODEL_TEST_REJECTED")
        run = str(c["run_id"])
        composition = await store.get(connection, command.owner_id, run, c["composition_ref"])
        decision = data_decision(command.data_approval)
        if decision["composition_ref"] != records.reference(composition):
            raise CatalogError("MODEL_DATA_DECISION_REJECTED")
        approval = SyntheticApproval(
            command.owner_id,
            run,
            canonical(records.reference(composition)),
            frozenset(str(v) for v in sequence(decision["approved_text_digests"])),
            (),
        )
        instruction = approval.classified(
            "Respond briefly to this synthetic model test. Use no tools."
        )
        objective = approval.classified(mapping(composition["payload"])["text"])
        if approval.approved_text_digests != frozenset(
            sha256(v.encode()).hexdigest() for v in (instruction, objective)
        ):
            raise CatalogError("MODEL_DATA_DECISION_REJECTED")
        t = mapping(turn["payload"])
        binding = records.envelope(
            "runtime-binding",
            {
                "version": 6,
                **{
                    k: t[k]
                    for k in (
                        "context_ref",
                        "runtime_boot",
                        "authority",
                        "native_root_id",
                        "native_child_id",
                        "native_session_id",
                        "native_turn",
                    )
                },
            },
        )
        model_input = {
            "messages": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": objective},
            ],
            "tools": [],
        }
        projection = records.envelope(
            "model-projection",
            {
                "version": 2,
                "owner_id": command.owner_id,
                "run_id": run,
                "context_ref": records.reference(context),
                "composition_ref": records.reference(composition),
                "binding_ref": records.reference(binding),
                "selection_ref": c["selection_ref"],
                "model_input": model_input,
                "approved_text_digests": sorted(approval.approved_text_digests),
                "projection_digest": sha256(canonical(model_input)).hexdigest(),
                "output_policy": "MONITOR_SUBSCRIPTION",
            },
        )
        for item in (binding, projection):
            await store.put(connection, command.owner_id, run, item)
        budget = await budgets.create_budget(
            connection,
            command.owner_id,
            c["managed_run_ref"],
            {
                "calls": 1,
                "output_tokens": None,
                "validation_calls": 0,
                "validation_output_tokens": None,
                "cost_limit": None,
                "output_policy": "MONITOR_SUBSCRIPTION",
            },
        )
        campaign = datetime.fromisoformat(str(c["campaign_deadline"]))
        deadline = min(campaign, datetime.now(UTC) + timedelta(seconds=300))
        dispatch = await budgets.reserve(
            connection,
            command.owner_id,
            records.reference(budget),
            {
                "run_or_job_ref": c["managed_run_ref"],
                "dispatch_attempt_id": command.protocol_id,
                "native_turn_ref": records.reference(turn),
                "dispatch_owner_ref": records.reference(binding),
                "purpose": "SETTINGS_TEST",
                "provider_config_ref": c["provider_config_ref"],
                "model_id": "gpt-6.1-sol",
                "execution_selection_ref": c["selection_ref"],
                "projection_ref": records.reference(projection),
                "projection_digest": mapping(projection["payload"])["projection_digest"],
                "fencing_epoch": command.expected_epoch,
                "deadline": deadline.isoformat(),
                "technical_caps": {
                    "calls": 1,
                    "output_tokens": None,
                    "wall_seconds": 300,
                    "output_policy": "MONITOR_SUBSCRIPTION",
                },
            },
            trusted_purpose="SETTINGS_TEST",
            hermes=True,
        )
        attempt = records.envelope(
            "model-test-attempt",
            {
                "context_ref": records.reference(context),
                "binding_ref": records.reference(binding),
                "projection_ref": records.reference(projection),
                "turn_ref": records.reference(turn),
                "dispatch_ref": records.reference(dispatch),
            },
        )
        await store.put(connection, command.owner_id, run, attempt)
        await store.command_complete(
            connection,
            command.owner_id,
            run,
            str(command.protocol_id),
            command.action,
            command.model_dump(mode="json"),
            {"attempt_ref": records.reference(attempt)},
        )
        return attempt, True

    async def execution_packet(
        self,
        connection: AsyncConnection,
        owner: str,
        attempt: dict[str, object],
        *,
        send: bool,
    ) -> dict[str, object] | None:
        from omnis.policy import budgets

        run, stored = await store.owned(connection, owner, records.reference(attempt))
        if canonical(stored) != canonical(attempt):
            raise CatalogError("MODEL_TEST_REJECTED")
        a = mapping(attempt["payload"])
        graph = await store.graph(connection, owner, run)
        packets = [
            r
            for r in graph
            if r["kind"] == "model-test-send"
            and mapping(r["payload"])["attempt_ref"] == records.reference(attempt)
        ]
        if packets:
            if len(packets) != 1 or send:
                raise CatalogError("MODEL_TEST_REJECTED")
            return {**mapping(mapping(packets[0]["payload"])["packet"]), "mode": "RECEIVE"}
        if not send:
            return None
        sent = await budgets.mark_sent(connection, owner, a["dispatch_ref"])
        packet: dict[str, object] = {
            "protocol": "omnis-managed-admission-v6",
            "mode": "SEND",
            "context_ref": a["context_ref"],
            "sent": sent,
        }
        for key, field in (
            ("binding", "binding_ref"),
            ("turn", "turn_ref"),
            ("projection", "projection_ref"),
            ("dispatch", "dispatch_ref"),
        ):
            packet[key] = await store.get(connection, owner, run, a[field])
        if len(canonical(packet)) > 32768:
            raise CatalogError("MODEL_TEST_LIMIT")
        await store.put(
            connection,
            owner,
            run,
            records.envelope(
                "model-test-send", {"attempt_ref": records.reference(attempt), "packet": packet}
            ),
        )
        return packet

    async def execution_receipt(
        self,
        connection: AsyncConnection,
        owner: str,
        attempt: dict[str, object],
        result: object = None,
    ) -> dict[str, object]:
        from omnis.modules.tasks.managed_contract import integer, text
        from omnis.policy import budgets

        run, _ = await store.owned(connection, owner, records.reference(attempt))
        a = mapping(attempt["payload"])
        graph = await store.graph(connection, owner, run)
        found = [
            r
            for r in graph
            if r["kind"] == "provider-receipt"
            and mapping(r["payload"])["attempt_ref"] == records.reference(attempt)
        ]
        if len(found) > 1:
            raise CatalogError("MODEL_RECEIPT_CONFLICT")
        receipt = found[0] if found else None
        if result is not None:
            v = exact(result, {"protocol", "context_ref", "dispatch_ref", "status", "receipt"})
            if (
                v["protocol"] != "omnis-managed-admission-v6"
                or v["context_ref"] != a["context_ref"]
                or v["dispatch_ref"] != a["dispatch_ref"]
                or v["status"] not in ("PENDING", "COMPLETE", "UNKNOWN")
            ):
                raise CatalogError("MODEL_TEST_REJECTED")
            if v["status"] == "COMPLETE":
                observed = exact(
                    v["receipt"],
                    {
                        "provider_response_id",
                        "model",
                        "effort",
                        "input_tokens",
                        "output_tokens",
                        "reasoning_tokens",
                        "status",
                        "output_text",
                        "wire_digest",
                    },
                )
                for key in ("provider_response_id", "model", "status"):
                    text(observed[key], 256)
                if observed["effort"] is not None:
                    text(observed["effort"], 32)
                for key in ("input_tokens", "output_tokens", "reasoning_tokens"):
                    if observed[key] is not None:
                        integer(observed[key], 0)
                if (
                    type(observed["output_text"]) is not str
                    or len(observed["output_text"].encode()) > 8192
                ):
                    raise CatalogError("MODEL_TEST_REJECTED")
                from omnis.modules.runs.native_preparation_models import sha

                sha(observed["wire_digest"])
                body: dict[str, object] = {
                    "attempt_ref": records.reference(attempt),
                    "observed": observed,
                }
                if receipt is not None and canonical(receipt["payload"]) != canonical(body):
                    raise CatalogError("MODEL_RECEIPT_CONFLICT")
                if receipt is None:
                    receipt = records.envelope("provider-receipt", body)
                    await store.put(connection, owner, run, receipt)
                output = observed["output_tokens"]
                usage = (
                    "UNKNOWN"
                    if output is None
                    else "KNOWN"
                    if observed["status"] == "completed"
                    else "PARTIAL"
                )
                await budgets.settle(
                    connection,
                    owner,
                    a["dispatch_ref"],
                    {
                        "receipt_id": mapping(
                            (await store.get(connection, owner, run, a["dispatch_ref"]))["payload"]
                        )["dispatch_attempt_id"],
                        "usage_state": usage,
                        "output_tokens": output,
                        "provider_receipt_ref": records.reference(receipt),
                        "cost_observed": None,
                        "cost_estimate": None,
                    },
                )
            elif v["receipt"] is not None:
                raise CatalogError("MODEL_TEST_REJECTED")
        state = await budgets.readback(connection, owner, a["dispatch_ref"])
        saved_observation = (
            None if receipt is None else mapping(mapping(receipt["payload"])["observed"])
        )
        return validate_execution_readback(
            {
                "ok": True,
                "attempt_ref": records.reference(attempt),
                "dispatch_ref": a["dispatch_ref"],
                "state": state["state"],
                "usage_state": state["usage_state"],
                "output_policy": "MONITOR_SUBSCRIPTION",
                "output_tokens": None
                if saved_observation is None
                else saved_observation["output_tokens"],
                "reasoning_tokens": None
                if saved_observation is None
                else saved_observation["reasoning_tokens"],
                "provider_receipt_ref": None if receipt is None else records.reference(receipt),
                "inference_status": "VERIFIED"
                if saved_observation is not None
                and saved_observation["model"] == "gpt-6.1-sol"
                and saved_observation["effort"] == "xhigh"
                and saved_observation["status"] == "completed"
                else "UNKNOWN",
                "cost_observed": None,
                "cost_estimate": None,
            }
        )


def validate_execution_readback(value: object) -> dict[str, object]:
    from omnis.modules.tasks.managed_contract import integer

    v = exact(
        value,
        {
            "ok",
            "attempt_ref",
            "dispatch_ref",
            "state",
            "usage_state",
            "output_policy",
            "output_tokens",
            "reasoning_tokens",
            "provider_receipt_ref",
            "inference_status",
            "cost_observed",
            "cost_estimate",
        },
    )
    ref(v["attempt_ref"], "model-test-attempt")
    ref(v["dispatch_ref"], "model-dispatch")
    if (
        v["ok"] is not True
        or v["state"] not in ("RESERVED", "SENT", "SETTLED")
        or v["usage_state"] not in ("UNKNOWN", "PARTIAL", "KNOWN")
        or v["output_policy"] != "MONITOR_SUBSCRIPTION"
        or v["inference_status"] not in ("UNKNOWN", "VERIFIED")
        or v["cost_observed"] is not None
        or v["cost_estimate"] is not None
    ):
        raise CatalogError("MODEL_TEST_REJECTED")
    for key in ("output_tokens", "reasoning_tokens"):
        if v[key] is not None:
            integer(v[key], 0)
    if v["provider_receipt_ref"] is not None:
        ref(v["provider_receipt_ref"], "provider-receipt")
    elif v["inference_status"] != "UNKNOWN" or v["usage_state"] != "UNKNOWN":
        raise CatalogError("MODEL_TEST_REJECTED")
    return v
