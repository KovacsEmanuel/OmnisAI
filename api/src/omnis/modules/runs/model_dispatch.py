"""Qualified data consumer for the authenticated private native-task owner.

Explicit local-control decisions classify exact synthetic texts. They are not
model grants; no classification is inferred from composition content. This owner
uses the existing transaction, immutable managed records and B06c reader.
"""

import re

from sqlalchemy import text as sql
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.runs.managed_admission import ManagedAdmission
from omnis.modules.runs.model_projection import ModelProjections
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.candidate_catalog import uuid_string
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks import managed_contract as contract
from omnis.modules.tasks import managed_store as store
from omnis.modules.tasks.managed_contract import exact, mapping, record, ref, sequence
from omnis.policy import budgets
from omnis.policy.model_projection import POLICY_DIGEST, SyntheticApproval

DECISION_FIELDS = {"decision_id", "composition_ref", "approved_text_digests"}
APPROVAL_FIELDS = DECISION_FIELDS | {
    "version",
    "owner_id",
    "run_id",
    "binding_ref",
    "policy_digest",
    "provenance",
}
PROVENANCE = "PRIVATE_CONTROL_EXACT_SYNTHETIC_TEXT_DECISION_V1"


def data_decision(value: object) -> dict[str, object]:
    result = exact(value, DECISION_FIELDS)
    uuid_string(result["decision_id"])
    ref(result["composition_ref"], "prompt-composition")
    digests = sequence(result["approved_text_digests"])
    if not 1 <= len(digests) <= 32 or any(
        type(d) is not str or re.fullmatch(r"[0-9a-f]{64}", d) is None for d in digests
    ):
        raise CatalogError("MODEL_DATA_DECISION_REJECTED")
    if len(set(digests)) != len(digests):
        raise CatalogError("MODEL_DATA_DECISION_REJECTED")
    return result


class ModelDispatch:
    def __init__(self, managed: ManagedAdmission, *, known_secrets: tuple[str, ...] = ()) -> None:
        self.projections = ModelProjections(managed)
        self.known_secrets = known_secrets

    @staticmethod
    def accept_preflight(result: object, prepared: dict[str, object]) -> dict[str, object]:
        payload = mapping(prepared["payload"])
        body = mapping(mapping(payload["projection"])["payload"])
        expected: dict[str, object] = {
            "protocol": payload["protocol"],
            "status": "BLOCKED",
            "reason": "NO_MODEL",
            "manifest_ref": payload["manifest_ref"],
            "binding_ref": records.reference(mapping(payload["binding"])),
            "projection_ref": payload["projection_ref"],
            "projection_digest": body["projection_digest"],
            "native_turn": None,
            "model_calls": 0,
        }
        if canonical(exact(result, set(expected))) != canonical(expected):
            raise CatalogError("MODEL_PREFLIGHT_REJECTED")
        return {**expected, "data_approval_ref": prepared["approval_ref"]}

    def _approval(
        self, item: object, owner: str, run: str, binding_ref: object
    ) -> SyntheticApproval:
        body = exact(record(item, "model-data-approval")["payload"], APPROVAL_FIELDS)
        decision = data_decision({key: body[key] for key in DECISION_FIELDS})
        if (
            type(body["version"]) is not int
            or body["version"] != 1
            or body["owner_id"] != uuid_string(owner)
            or body["run_id"] != uuid_string(run)
            or ref(body["binding_ref"], "runtime-binding") != ref(binding_ref, "runtime-binding")
            or body["policy_digest"] != POLICY_DIGEST
            or body["provenance"] != PROVENANCE
        ):
            raise CatalogError("MODEL_DATA_DECISION_REJECTED")
        return SyntheticApproval(
            owner,
            run,
            canonical(decision["composition_ref"]),
            frozenset(str(d) for d in sequence(decision["approved_text_digests"])),
            self.known_secrets,
        )

    async def prepare(
        self,
        connection: AsyncConnection,
        owner: str,
        manifest_ref: object,
        binding_ref: object,
        decision: object,
    ) -> dict[str, object]:
        """Caller holds Instance→lease→Stop; it owns commit/rollback, not this class."""
        supplied = data_decision(decision)
        await budgets._transaction(connection, owner)
        state = await store.state(connection, owner, manifest=manifest_ref)
        run = uuid_string(state["run_id"])
        manifest = contract.validate_manifest(await store.get(connection, owner, run, manifest_ref))
        binding = contract.validate_binding(
            await store.get(connection, owner, run, binding_ref), manifest
        )
        if state["binding_id"] != binding["id"]:
            raise CatalogError("MODEL_DATA_DECISION_REJECTED")
        payload: dict[str, object] = {
            **supplied,
            "version": 1,
            "owner_id": owner,
            "run_id": run,
            "binding_ref": records.reference(binding),
            "policy_digest": POLICY_DIGEST,
            "provenance": PROVENANCE,
        }
        prior = (
            (
                await connection.execute(
                    sql(
                        "SELECT envelope FROM managed_record WHERE owner_id=:owner "
                        "AND envelope->>'kind'='model-data-approval' "
                        "AND envelope->'payload'->>'decision_id'=:decision"
                    ),
                    {"owner": owner, "decision": supplied["decision_id"]},
                )
            )
            .scalars()
            .all()
        )
        if prior:
            if len(prior) != 1 or canonical(record(prior[0])["payload"]) != canonical(payload):
                raise CatalogError("MODEL_DATA_DECISION_CONFLICT")
            approved = record(prior[0], "model-data-approval")
        else:
            approved = records.envelope("model-data-approval", payload)
        approval = self._approval(approved, owner, run, binding_ref)
        projection = await self.projections.prepare(
            connection, owner, manifest_ref, binding_ref, supplied["composition_ref"], approval
        )
        if not prior:
            await store.put(connection, owner, run, approved)
        return await self.read(
            connection,
            owner,
            run,
            records.reference(binding),
            records.reference(approved),
            records.reference(projection),
        )

    async def read(
        self,
        connection: AsyncConnection,
        owner: str,
        run: str,
        binding_ref: object,
        approval_ref: object,
        projection_ref: object,
    ) -> dict[str, object]:
        await budgets._transaction(connection, owner)
        approved = await store.get(connection, owner, run, ref(approval_ref, "model-data-approval"))
        approval = self._approval(approved, owner, run, binding_ref)
        projection = await self.projections.read(connection, owner, run, projection_ref, approval)
        body = mapping(projection["payload"])
        binding = await store.get(connection, owner, run, binding_ref)
        manifest = await store.get(connection, owner, run, body["manifest_ref"])
        contract.validate_binding(binding, manifest)
        return {
            "approval_ref": records.reference(approved),
            "payload": {
                "protocol": contract.manifest_protocol(manifest),
                "ticket": mapping(binding["payload"])["ticket"],
                "manifest_ref": records.reference(manifest),
                "binding": binding,
                "owner_id": owner,
                "run_id": run,
                "projection": projection,
                "projection_ref": records.reference(projection),
                "policy_digest": POLICY_DIGEST,
            },
        }
