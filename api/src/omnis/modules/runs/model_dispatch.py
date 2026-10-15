"""Qualified data consumer for the authenticated private native-task owner.

Explicit local-control decisions classify exact synthetic texts. They are not
model grants; no classification is inferred from composition content. This owner
uses the existing transaction, immutable managed records and B06c reader.
"""

import re
from hashlib import sha256

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

    async def prepare_ready_configuration(
        self,
        connection: AsyncConnection,
        owner: str,
        manifest_ref: object,
        configuration: object,
        authority: dict[str, object],
    ) -> dict[str, object]:
        """Private owner decision; compute readiness of DATA, never execution permission."""
        from omnis.policy.ready_model_configuration import PROVENANCE, validate_ready_source

        config = validate_ready_source(configuration)
        await budgets._transaction(connection, owner)
        state = await store.state(connection, owner, manifest=manifest_ref)
        run = uuid_string(state["run_id"])
        manifest = await store.get(connection, owner, run, manifest_ref)
        contract.validate_manifest(manifest)
        if (
            state["binding_id"] is not None
            or state["stage_started"] is not False
            or state["release_started"] is not False
            or state["final_id"] is not None
        ):
            raise CatalogError("MODEL_CONFIGURATION_REJECTED")
        request = {
            "manifest_ref": records.reference(manifest),
            "configuration": config,
            "authority": authority,
        }
        prior = await store.command_replay(
            connection, owner, str(config["decision_id"]), "model_configuration", request
        )
        if prior is not None:
            return await store.get(connection, owner, run, prior["provider_config_ref"])
        item = records.envelope(
            "provider-config",
            {
                "version": 1,
                "owner_id": owner,
                "run_id": run,
                "manifest_ref": records.reference(manifest),
                "authority": authority,
                "configuration": config,
                "provenance": PROVENANCE,
                "status": "READY",
                "inference_authorized": False,
            },
        )
        await store.put(connection, owner, run, item)
        checked = await store.get(connection, owner, run, records.reference(item))
        if canonical(checked) != canonical(item):
            raise CatalogError("MODEL_CONFIGURATION_REJECTED")
        await store.command_complete(
            connection,
            owner,
            run,
            str(config["decision_id"]),
            "model_configuration",
            request,
            {"provider_config_ref": records.reference(checked)},
        )
        return checked

    async def read_ready_initialization(
        self,
        connection: AsyncConnection,
        owner: str,
        manifest_ref: object,
        provider_config_ref: object,
        authority: dict[str, object],
    ) -> bytes:
        """First initialization reader: only exact owned source, not a request alias."""
        from omnis.policy.ready_model_configuration import initialization_data

        await budgets._transaction(connection, owner)
        state = await store.state(connection, owner, manifest=manifest_ref)
        run = uuid_string(state["run_id"])
        manifest = await store.get(connection, owner, run, manifest_ref)
        contract.validate_manifest(manifest)
        if (
            state["binding_id"] is not None
            or state["stage_started"] is not False
            or state["release_started"] is not False
            or state["final_id"] is not None
        ):
            raise CatalogError("MODEL_CONFIGURATION_REJECTED")
        return initialization_data(
            await self.read_configuration(
                connection, owner, manifest_ref, provider_config_ref, authority
            )
        )

    async def read_configuration(
        self,
        connection: AsyncConnection,
        owner: str,
        manifest_ref: object,
        provider_config_ref: object,
        authority: dict[str, object],
    ) -> dict[str, object]:
        """Qualified immutable DATA, also usable post-binding; never a warm grant."""
        from omnis.policy.ready_model_configuration import PROVENANCE

        await budgets._transaction(connection, owner)
        state = await store.state(connection, owner, manifest=manifest_ref)
        run = uuid_string(state["run_id"])
        manifest = await store.get(connection, owner, run, manifest_ref)
        contract.validate_manifest(manifest)
        item = record(
            await store.get(connection, owner, run, ref(provider_config_ref, "provider-config")),
            "provider-config",
        )
        body = exact(
            item["payload"],
            {
                "version",
                "owner_id",
                "run_id",
                "manifest_ref",
                "authority",
                "configuration",
                "provenance",
                "status",
                "inference_authorized",
            },
        )
        if (
            type(body["version"]) is not int
            or body["version"] != 1
            or body["owner_id"] != owner
            or body["run_id"] != run
            or body["manifest_ref"] != records.reference(manifest)
            or canonical(body["authority"]) != canonical(authority)
            or body["provenance"] != PROVENANCE
            or body["status"] != "READY"
            or body["inference_authorized"] is not False
        ):
            raise CatalogError("MODEL_CONFIGURATION_REJECTED")
        # Qualification includes the committed decision receipt, not only a
        # well-shaped record bearing a caller-forged READY/provenance label.
        from omnis.policy.ready_model_configuration import validate_ready_source

        config = validate_ready_source(body["configuration"])
        request = {
            "manifest_ref": records.reference(manifest),
            "configuration": config,
            "authority": authority,
        }
        produced = await store.command_replay(
            connection, owner, str(config["decision_id"]), "model_configuration", request
        )
        if produced is None or produced != {"provider_config_ref": records.reference(item)}:
            raise CatalogError("MODEL_CONFIGURATION_REJECTED")
        return config

    async def prepare_initialization(
        self,
        connection: AsyncConnection,
        owner: str,
        manifest_ref: object,
        provider_config_ref: object,
        initialization_id: object,
        authority: dict[str, object],
        runtime_boot: object,
    ) -> tuple[dict[str, object], dict[str, object] | None]:
        """Commit caller owns fences; new intent precedes IPC, pending replay is STATUS-only."""
        from omnis.modules.settings.catalog_schema import load_json

        identity, boot = uuid_string(initialization_id), uuid_string(runtime_boot)
        data = await self.read_ready_initialization(
            connection, owner, manifest_ref, provider_config_ref, authority
        )
        state = await store.state(connection, owner, manifest=manifest_ref)
        run = uuid_string(state["run_id"])
        source = record(
            await store.get(connection, owner, run, ref(provider_config_ref, "provider-config")),
            "provider-config",
        )
        config = mapping(mapping(source["payload"])["configuration"])
        producer = await store.command_receipt(
            connection, owner, uuid_string(config["decision_id"])
        )
        request: dict[str, object] = {
            "manifest_ref": ref(manifest_ref, "launch-manifest"),
            "provider_config_ref": records.reference(source),
            "initialization_id": identity,
            "authority": authority,
            "runtime_boot": boot,
        }
        body: dict[str, object] = {
            "version": 1,
            "initialization_id": identity,
            "owner_id": owner,
            "run_id": run,
            "manifest_ref": request["manifest_ref"],
            "authority": authority,
            "runtime_boot": boot,
            "provider_config_ref": records.reference(source),
            "producer_receipt_ref": records.reference(producer),
            "source_byte_digest": sha256(canonical(source)).hexdigest(),
            "initialization_data_digest": sha256(data).hexdigest(),
            "state": "RESERVED",
        }
        prior = await store.command_replay(
            connection, owner, identity, "model_initialization", request
        )
        if prior is None:
            intent = records.envelope("native-initialization-intent", body)
            await store.put(connection, owner, run, intent)
            checked = await store.get(connection, owner, run, records.reference(intent))
            if canonical(checked) != canonical(intent):
                raise CatalogError("MODEL_INITIALIZATION_REJECTED")
            await store.command_complete(
                connection,
                owner,
                run,
                identity,
                "model_initialization",
                request,
                {"intent_ref": records.reference(intent)},
            )
        else:
            exact(prior, {"intent_ref"})
            intent = record(
                await store.get(connection, owner, run, prior["intent_ref"]),
                "native-initialization-intent",
            )
            if canonical(intent["payload"]) != canonical(body):
                raise CatalogError("MODEL_INITIALIZATION_REJECTED")
        payload: dict[str, object] = {
            "protocol": "omnis-managed-admission-v3",
            **{
                k: body[k]
                for k in body
                if k not in {"provider_config_ref", "producer_receipt_ref", "state"}
            },
            "mode": "CREATE" if prior is None else "STATUS",
            "intent_ref": records.reference(intent),
            "provider_config": source,
            "producer_receipt": producer,
            "initialization_data": data.decode(),
        }
        if len(canonical(payload)) > 32768:
            raise CatalogError("MODEL_INITIALIZATION_REJECTED")
        # Detach storage/request aliases before leaving the transaction.
        payload = mapping(load_json(canonical(payload)))
        observations = [
            r
            for r in await store.graph(connection, owner, run)
            if r["kind"] == "native-initialization-observation"
            and canonical(mapping(r["payload"]).get("intent_ref"))
            == canonical(payload["intent_ref"])
        ]
        if len(observations) > 1:
            raise CatalogError("STORAGE_INCOMPATIBLE")
        if observations:
            observed = record(observations[0], "native-initialization-observation")
            self.accept_initialization(observed["payload"], payload)
            return payload, observed
        return payload, None

    @staticmethod
    def accept_initialization(result: object, payload: dict[str, object]) -> dict[str, object]:
        """Strict observation DATA; no client, turn or inference authority issued here."""
        from omnis.modules.runs.native_preparation_models import sha
        from omnis.modules.settings.catalog_schema import load_json
        from omnis.policy.ready_model_configuration import exact_configuration_types

        exact_configuration_types(result)
        common = {
            **{
                k: payload[k]
                for k in (
                    "protocol",
                    "version",
                    "initialization_id",
                    "intent_ref",
                    "owner_id",
                    "run_id",
                    "manifest_ref",
                    "runtime_boot",
                    "authority",
                    "source_byte_digest",
                    "initialization_data_digest",
                )
            },
            "provider_config_ref": records.reference(
                record(payload["provider_config"], "provider-config")
            ),
            "producer_receipt_ref": records.reference(
                record(payload["producer_receipt"], "contract-input-command")
            ),
            "client_status": "DEFERRED_NO_CREDENTIAL",
            "native_turn": None,
            "inference_status": "HOLD",
            "model_calls": 0,
        }
        observed = exact(
            result,
            set(common)
            | {
                "status",
                "native_session_id",
                "native_instance_id",
                "observed_configuration",
                "observed_configuration_digest",
            },
        )
        if canonical({k: observed[k] for k in common}) != canonical(common):
            raise CatalogError("MODEL_INITIALIZATION_REJECTED")
        for key, kind in (
            ("intent_ref", "native-initialization-intent"),
            ("manifest_ref", "launch-manifest"),
            ("provider_config_ref", "provider-config"),
            ("producer_receipt_ref", "contract-input-command"),
        ):
            ref(observed[key], kind)
        if observed["status"] == "UNKNOWN":
            if any(
                observed[k] is not None
                for k in (
                    "native_session_id",
                    "native_instance_id",
                    "observed_configuration",
                    "observed_configuration_digest",
                )
            ):
                raise CatalogError("MODEL_INITIALIZATION_REJECTED")
            raise CatalogError("TASK_INDETERMINATE")
        if observed["status"] != "CONFIG_INITIALIZED_AT_PRE_CLIENT_SEAM":
            raise CatalogError("MODEL_INITIALIZATION_REJECTED")
        contract.text(observed["native_session_id"], 128)
        uuid_string(observed["native_instance_id"])
        config = mapping(load_json(contract.text(payload["initialization_data"], 2048)))
        if (
            canonical(observed["observed_configuration"]) != canonical(config)
            or sha(observed["observed_configuration_digest"])
            != sha256(canonical(config)).hexdigest()
        ):
            raise CatalogError("MODEL_INITIALIZATION_REJECTED")
        return observed

    async def persist_initialization(
        self,
        connection: AsyncConnection,
        owner: str,
        payload: dict[str, object],
        result: object,
    ) -> dict[str, object]:
        """Requalify source/intent/fences after IPC; success only after caller commits."""
        current, prior = await self.prepare_initialization(
            connection,
            owner,
            payload["manifest_ref"],
            records.reference(record(payload["provider_config"], "provider-config")),
            payload["initialization_id"],
            mapping(payload["authority"]),
            payload["runtime_boot"],
        )
        if canonical({k: v for k, v in current.items() if k != "mode"}) != canonical(
            {k: v for k, v in payload.items() if k != "mode"}
        ):
            raise CatalogError("MODEL_INITIALIZATION_REJECTED")
        checked = self.accept_initialization(result, current)
        if prior is not None:
            if canonical(prior["payload"]) != canonical(checked):
                raise CatalogError("MODEL_INITIALIZATION_REJECTED")
            return prior
        item = records.envelope("native-initialization-observation", checked)
        await store.put(connection, owner, uuid_string(payload["run_id"]), item)
        back = await store.get(
            connection, owner, uuid_string(payload["run_id"]), records.reference(item)
        )
        if canonical(back) != canonical(item):
            raise CatalogError("MODEL_INITIALIZATION_REJECTED")
        return back

    @staticmethod
    def accept_preflight(result: object, prepared: dict[str, object]) -> dict[str, object]:
        from omnis.policy.model_configuration import validate_source

        payload = mapping(prepared["payload"])
        native = mapping(result)
        configuration = validate_source(native.get("source_configuration"), payload)
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
            "model_context": payload["model_context"],
            "model_context_digest": payload["model_context_digest"],
            "source_configuration": configuration,
        }
        if canonical(exact(result, set(expected))) != canonical(expected):
            raise CatalogError("MODEL_PREFLIGHT_REJECTED")
        return {**expected, "data_approval_ref": prepared["approval_ref"]}

    async def persist_configuration(
        self,
        connection: AsyncConnection,
        owner: str,
        prepared: dict[str, object],
        result: object,
    ) -> dict[str, object]:
        """Private owner holds Instance→lease→Stop; commit/read actual RPC observation."""
        from omnis.policy.model_configuration import configuration_payload

        payload = mapping(prepared["payload"])
        run = uuid_string(payload["run_id"])
        current = await self.read(
            connection,
            owner,
            run,
            records.reference(mapping(payload["binding"])),
            prepared["approval_ref"],
            payload["projection_ref"],
        )
        if canonical(current) != canonical(prepared):
            raise CatalogError("MODEL_CONFIGURATION_REJECTED")
        accepted = self.accept_preflight(result, current)
        expected = configuration_payload(
            mapping(current["payload"]), accepted["source_configuration"]
        )
        graph = await store.graph(connection, owner, run)
        matches = [
            r
            for r in graph
            if r["kind"] == "model-configuration-receipt"
            and mapping(r["payload"]).get("projection_ref") == payload["projection_ref"]
        ]
        if matches:
            if len(matches) != 1 or canonical(matches[0]["payload"]) != canonical(expected):
                raise CatalogError("MODEL_CONFIGURATION_REJECTED")
            receipt = matches[0]
        else:
            receipt = records.envelope("model-configuration-receipt", expected)
            await store.put(connection, owner, run, receipt)
        # Read the exact owned immutable record, never return a hand-built Ref.
        checked = await store.get(connection, owner, run, records.reference(receipt))
        if canonical(checked["payload"]) != canonical(expected):
            raise CatalogError("MODEL_CONFIGURATION_REJECTED")
        return {**accepted, "configuration_receipt_ref": records.reference(checked)}

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
        context = await self._context(connection, owner, run, binding, manifest, projection)
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
                "model_context": context,
                "model_context_digest": sha256(canonical(context)).hexdigest(),
            },
        }

    async def _context(
        self,
        connection: AsyncConnection,
        owner: str,
        run: str,
        binding: dict[str, object],
        manifest: dict[str, object],
        projection: dict[str, object],
    ) -> dict[str, object]:
        """Qualified source read in the current owner transaction, never authority from a Ref."""
        from omnis.policy.model_context import derive_model_context

        graph = await store.graph(connection, owner, run)
        matches = [r for r in graph if r["kind"] == "managed-run" and r["id"] == run]
        if len(matches) != 1:
            raise CatalogError("MODEL_CONTEXT_REJECTED")
        run_record = matches[0]
        run_body = mapping(run_record["payload"])
        projection_body = mapping(projection["payload"])
        source = await self.projections.managed._source(
            connection,
            owner,
            {
                "selection_ref": mapping(manifest["payload"])["selection_ref"],
                "composition_version": mapping(manifest["payload"])["composition_version"],
            },
            preparation_ref=ref(run_body["preparation_receipt_ref"], "native-preparation-receipt"),
        )
        brief = await store.get(connection, owner, run, projection_body["brief_ref"])
        brief_body = mapping(brief["payload"])
        bindings = sequence(brief_body["procedure_bindings"])
        if len(bindings) != 1:
            raise CatalogError("MODEL_CONTEXT_REJECTED")
        bound = await store.get(connection, owner, run, mapping(bindings[0])["bound_procedure_ref"])
        policy = await store.get(connection, owner, run, run_body["policy_ref"])
        return derive_model_context(
            source,
            owner=owner,
            run_record=run_record,
            policy=policy,
            manifest=manifest,
            binding=binding,
            brief=brief,
            bound=bound,
            projection=projection,
        )
