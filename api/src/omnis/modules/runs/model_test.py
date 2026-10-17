"""Qualified preparation DATA over retained cold material; never model authority."""

from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.runs.managed_admission import ManagedAdmission
from omnis.modules.runs.pure_probe import PureProbe
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.candidate_catalog import uuid_string
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks import managed_store as store
from omnis.modules.tasks.managed_contract import mapping, record, ref

REQUESTED = {"provider": "openai-codex", "model": "gpt-6.1-sol", "effort": "xhigh"}
PURPOSE = "MODEL_TEST_PREPARE"


class ModelTest:
    def __init__(self, domain: ManagedAdmission) -> None:
        self.domain = domain

    async def prepare(
        self, connection: AsyncConnection, owner: str, manifest_ref: object,
        identity: str, settings_operation_id: str, settings: object,
        authority: dict[str, object], runtime_boot: str,
    ) -> dict[str, object]:
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
            "authority": authority, "runtime_boot": runtime_boot,
        }
        prior = await store.command_replay(connection, owner, identity, "model_test_prepare", request)
        if prior is not None:
            return await store.get(connection, owner, run, prior["context_ref"])
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
            connection, owner, {"selection_ref": original["selection_ref"], "composition_version": 4},
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
        if compiled.dependency_artifact_refs or compiled.dependency_closure_refs:
            raise CatalogError("UNSUPPORTED_DEPENDENCY")
        fresh_snapshot = records.envelope("run-snapshot", {
            **material, "execution_purpose": PURPOSE,
            "original_snapshot_ref": records.reference(snapshot),
            "original_selection_ref": records.reference(source.selection),
            "preparation_receipt_ref": source.preparation_ref,
            "resolution": "PREPARATION_ONLY", "effective": None,
            "assessment_selectable": False,
        })
        selection = records.envelope("execution-selection", {
            **selected, "snapshot_ref": records.reference(fresh_snapshot),
            "purpose": PURPOSE, "requested": REQUESTED, "effective": None,
            "resolution": "PREPARATION_ONLY", "reason": "ACCOUNT_NOT_VERIFIED",
        })
        configuration = records.envelope("provider-config", {
            "version": 2, "owner_id": owner, "run_id": run,
            "settings_operation_id": request["settings_operation_id"],
            "provenance": "NATIVE_SETTINGS_SAVED_SELECTION_READBACK_V2",
            "requested": REQUESTED, "api_mode": "codex_responses",
            "reasoning_config": {"enabled": True, "effort": "xhigh"},
            "fallback": None, "auxiliary": False, "fast": False,
            "account_status": "NOT_VERIFIED", "inference_status": "HOLD",
        })
        context = records.envelope("model-test-context", {
            "version": 5, "purpose": PURPOSE, "owner_id": owner, "run_id": run,
            **request, "preparation_id": identity,
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
            "requested": REQUESTED, "effective": None,
            "account_status": "NOT_VERIFIED", "inference_status": "HOLD",
        })
        produced = [fresh_snapshot, selection, configuration, context]
        if len(canonical(produced)) > 32768:
            raise CatalogError("MODEL_TEST_LIMIT")
        # Size the actual producer before any persistence, not one legacy sample.
        for item in produced:
            await store.put(connection, owner, run, item)
            back = await store.get(connection, owner, run, records.reference(item))
            if canonical(back) != canonical(item):
                raise CatalogError("MODEL_TEST_REJECTED")
        await store.command_complete(connection, owner, run, identity, "model_test_prepare", request,
                                     {"context_ref": records.reference(context)})
        return context
