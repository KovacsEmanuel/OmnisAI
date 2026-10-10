"""ModelProjection producer/readback on the existing managed owner transaction.

The caller supplies its trusted approval. This module has no CLI, native calls,
model admission, provider or second ledger. Source/readback errors are sanitized.
"""

from hashlib import sha256

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.runs.managed_admission import ManagedAdmission
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.candidate_catalog import uuid_string
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks import managed_composition, managed_store
from omnis.modules.tasks import managed_contract as contract
from omnis.modules.tasks.managed_contract import mapping, record, ref, sequence
from omnis.policy.model_projection import POLICY_DIGEST, SyntheticApproval, reject


class ModelProjections:
    def __init__(self, managed: ManagedAdmission) -> None:
        self.managed = managed

    async def _produce(
        self,
        connection: AsyncConnection,
        owner_id: str,
        manifest_ref: object,
        binding_ref: object,
        composition_ref: object,
        approval: SyntheticApproval,
    ) -> tuple[str, dict[str, object], list[dict[str, object]]]:
        owner = uuid_string(owner_id)
        if type(approval) is not SyntheticApproval or approval.owner_id != owner:
            raise reject()
        # Validate Ref forms/kinds before performing any lookup.
        manifest_pin = ref(manifest_ref, "launch-manifest")
        binding_pin = ref(binding_ref, "runtime-binding")
        composition_pin = ref(composition_ref, "prompt-composition")
        await managed_store.lock(connection, owner)
        state = await managed_store.state(connection, owner, manifest=manifest_pin)
        run = uuid_string(state["run_id"])
        if run != approval.run_id or state["binding_id"] != binding_pin["id"]:
            raise reject()
        manifest = contract.validate_manifest(
            await managed_store.get(connection, owner, run, manifest_pin)
        )
        binding = contract.validate_binding(
            await managed_store.get(connection, owner, run, binding_pin), manifest
        )
        graph = await managed_store.graph(connection, owner, run)
        # Existing exact catalog/material/preparation/assignment resolver, not an
        # invented preflight or a local dictionary standing in for persistence.
        await self.managed._verify_graph(connection, owner, run, graph)
        stage = managed_composition.stage_payload(manifest, graph)
        entries = [
            mapping(e)
            for e in sequence(mapping(manifest["payload"])["entries"])
            if mapping(e).get("composition_ref") == composition_pin
        ]
        compositions = [
            mapping(c)
            for c in sequence(stage.get("compositions"))
            if records.reference(mapping(c)) == composition_pin
        ]
        if len(entries) != 1 or len(compositions) != 1:
            raise reject()
        composition = managed_composition.validate(compositions[0], entries[0], manifest)
        brief = await managed_store.get(connection, owner, run, entries[0]["brief_ref"])
        body = mapping(brief["payload"])
        header = mapping(body["header"])
        run_record = await managed_store.get(
            connection,
            owner,
            run,
            {
                **records.reference(next(r for r in graph if r["id"] == run)),
                "kind": "managed-run",
            },
        )
        run_body = mapping(run_record["payload"])
        if header["run_id"] != run or run_body["selection_ref"] != body["execution_selection_ref"]:
            raise reject()
        model_input = managed_composition.project_model_input(composition, approval)
        payload: dict[str, object] = {
            "version": 1,
            "owner_id": owner,
            "run_id": run,
            "manifest_ref": manifest_pin,
            "runtime_binding_ref": records.reference(binding),
            "composition_ref": composition_pin,
            "brief_ref": records.reference(brief),
            "snapshot_ref": header["snapshot_ref"],
            "selection_ref": body["execution_selection_ref"],
            "mission_ref": header["mission_revision"],
            "focus_ref": header["focus_ref"],
            "policy_ref": ref(run_body["policy_ref"], "probe-policy"),
            "scope_ref": ref(run_body["scope_ref"], "probe-scope"),
            "policy_digest": POLICY_DIGEST,
            "approval_digest": approval.digest,
            "provenance": {"producer_revision": "model-projection-v1", "source_kind": "SYNTHETIC"},
            "model_input": model_input,
            "projection_digest": sha256(canonical(model_input)).hexdigest(),
        }
        return run, payload, graph

    async def prepare(
        self,
        connection: AsyncConnection,
        owner_id: str,
        manifest_ref: object,
        binding_ref: object,
        composition_ref: object,
        approval: SyntheticApproval,
    ) -> dict[str, object]:
        """Use inside the caller's transaction; no independent connection/commit."""
        try:
            run, payload, graph = await self._produce(
                connection, owner_id, manifest_ref, binding_ref, composition_ref, approval
            )
            matches = [
                r
                for r in graph
                if r["kind"] == "model-projection"
                and mapping(r["payload"]).get("composition_ref") == payload["composition_ref"]
                and mapping(r["payload"]).get("approval_digest") == payload["approval_digest"]
            ]
            if matches:
                if len(matches) != 1 or canonical(matches[0]["payload"]) != canonical(payload):
                    raise reject()
                return record(matches[0], "model-projection")
            result = records.envelope("model-projection", payload)
            await managed_store.put(connection, owner_id, run, result)
            return result
        except (
            CatalogError,
            SQLAlchemyError,
            ValueError,
            TypeError,
            KeyError,
            StopIteration,
            UnicodeError,
            RecursionError,
        ):
            raise reject() from None

    async def read(
        self,
        connection: AsyncConnection,
        owner_id: str,
        run_id: str,
        projection_ref: object,
        approval: SyntheticApproval,
    ) -> dict[str, object]:
        """Re-resolve exact source/owner/assignment and reproduce projected bytes."""
        try:
            owner, run = uuid_string(owner_id), uuid_string(run_id)
            pin = ref(projection_ref, "model-projection")
            if type(approval) is not SyntheticApproval or (owner, run) != (
                approval.owner_id,
                approval.run_id,
            ):
                raise reject()
            await managed_store.lock(connection, owner)
            result = record(
                await managed_store.get(connection, owner, run, pin), "model-projection"
            )
            body = mapping(result["payload"])
            actual_run, expected, _ = await self._produce(
                connection,
                owner,
                body["manifest_ref"],
                body["runtime_binding_ref"],
                body["composition_ref"],
                approval,
            )
            if actual_run != run or canonical(body) != canonical(expected):
                raise reject()
            return result
        except (
            CatalogError,
            SQLAlchemyError,
            ValueError,
            TypeError,
            KeyError,
            StopIteration,
            UnicodeError,
            RecursionError,
        ):
            raise reject() from None
