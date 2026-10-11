"""Cold model context from the existing qualified catalog/assignment source.

This is SUPPORT preflight, not a model dispatch purpose or permission. It never
creates configuration, native turns, reservations/SENT, or provider responses.
"""

from omnis.modules.runs.managed_admission import BuildSource
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.candidate_catalog import uuid_string
from omnis.modules.settings.catalog_models import CatalogError, ReleaseRef
from omnis.modules.tasks import managed_contract as contract
from omnis.modules.tasks.managed_contract import exact, mapping, record, ref, sequence

CONTEXT_FIELDS = set(
    "version owner_id run_id managed_run_ref manifest_ref binding_ref projection_ref composition_ref brief_ref task_id attempt_id selection_ref selection snapshot_ref recipe_key recipe_role technique_ref source_work_kind procedure_ref verification_kind preparation_receipt_ref execution_kind purpose requested effective resolution".split()
)


def validate_context_readback(value: object) -> dict[str, object]:
    """Strict private reply data, not a replacement for qualified catalog readback."""
    context = exact(value, CONTEXT_FIELDS)
    contract.integer(context["version"], 1, 1)
    for key in ("owner_id", "run_id", "task_id", "attempt_id"):
        uuid_string(context[key])
    for key, kind in (
        ("managed_run_ref", "managed-run"),
        ("manifest_ref", "launch-manifest"),
        ("binding_ref", "runtime-binding"),
        ("projection_ref", "model-projection"),
        ("composition_ref", "prompt-composition"),
        ("brief_ref", "task-brief"),
        ("selection_ref", "execution-selection"),
        ("snapshot_ref", "run-snapshot"),
        ("technique_ref", "technique"),
        ("procedure_ref", "procedure"),
        ("preparation_receipt_ref", "native-preparation-receipt"),
    ):
        ref(context[key], kind)
    selection = record(context["selection"], "execution-selection")
    selected = exact(
        selection["payload"],
        set(
            "snapshot_ref recipe_key selected_package_refs requested effective resolution reason compatibility_receipt_refs".split()
        ),
    )
    requested = exact(
        selected["requested"], {"model_key", "effort", "requirement", "on_unavailable"}
    )
    if (
        context["purpose"] != "SUPPORT"
        or context["execution_kind"] != "CONTRACT_PROBE"
        or context["verification_kind"] != "CONTRACT"
        or context["effective"] is not None
        or context["resolution"] != "NO_MODEL"
        or selected["effective"] is not None
        or selected["resolution"] != "NO_MODEL"
        or selected["reason"] != "CONTRACT_PROBE_PURE"
        or context["requested"] != requested
        or requested
        != {
            "model_key": None,
            "effort": None,
            "requirement": "PREFERRED",
            "on_unavailable": "BLOCK",
        }
        or context["selection_ref"] != records.reference(selection)
        or context["snapshot_ref"] != ref(selected["snapshot_ref"], "run-snapshot")
        or context["recipe_key"] != selected["recipe_key"]
        or type(context["recipe_key"]) is not str
        or not context["recipe_key"]
        or context["recipe_role"] not in ("RECON", "INVESTIGATOR", "VALIDATOR", "RESEARCH")
        or context["source_work_kind"]
        not in ("RECON", "ANALYSIS", "INVESTIGATION", "VALIDATION", "SUPPORT", "REVIEW")
        or selected["compatibility_receipt_refs"] != []
        or mapping(context["managed_run_ref"])["id"] != context["run_id"]
    ):
        raise CatalogError("MODEL_CONTEXT_REJECTED")
    for package in sequence(selected["selected_package_refs"]):
        ref(package, "package")
    if not 1 <= len(sequence(selected["selected_package_refs"])) <= 4:
        raise CatalogError("MODEL_CONTEXT_REJECTED")
    return context


def derive_model_context(
    source: BuildSource,
    *,
    owner: str,
    run_record: dict[str, object],
    policy: dict[str, object],
    manifest: dict[str, object],
    binding: dict[str, object],
    brief: dict[str, object],
    bound: dict[str, object],
    projection: dict[str, object],
) -> dict[str, object]:
    """Caller resolves source with _source/_selection; no caller-supplied purpose/config."""
    selection = record(source.selection, "execution-selection")
    selected = mapping(selection["payload"])
    run = record(run_record, "managed-run")
    run_body = mapping(run["payload"])
    body = mapping(contract.validate_brief(brief)["payload"])
    bound_body = mapping(record(bound, "bound-procedure")["payload"])
    projection_body = mapping(record(projection, "model-projection")["payload"])
    header = mapping(body["header"])
    policy_body = exact(
        record(policy, "probe-policy")["payload"],
        {"purpose", "target_actions", "model_calls", "allowed_capability_ids"},
    )
    requested = exact(
        selected["requested"], {"model_key", "effort", "requirement", "on_unavailable"}
    )
    if (
        run_body["purpose"] != "CONTRACT_PROBE"
        or policy_body
        != {
            "purpose": "CONTRACT_PROBE",
            "target_actions": 0,
            "model_calls": 0,
            "allowed_capability_ids": [],
        }
        or type(policy_body["target_actions"]) is not int
        or type(policy_body["model_calls"]) is not int
        or selected["resolution"] != "NO_MODEL"
        or selected["effective"] is not None
        or selected["reason"] != "CONTRACT_PROBE_PURE"
        or requested
        != {
            "model_key": None,
            "effort": None,
            "requirement": "PREFERRED",
            "on_unavailable": "BLOCK",
        }
        or body["role"] != source.role
        or body["execution_selection_ref"] != records.reference(selection)
        or run_body["selection_ref"] != records.reference(selection)
        or selected["snapshot_ref"] != header["snapshot_ref"]
        or header["run_id"] != run["id"]
        or run_body["snapshot_ref"] != selected["snapshot_ref"]
        or body["review_request"] is not None
        or sequence(body["criterion_bindings"]) != []
        or sequence(body["operation_refs"]) != []
        or sequence(body["allowed_capability_ids"]) != []
        or body["validation_reserve"] != {"actions": 0, "seconds": 0}
        or any(type(v) is not int for v in mapping(body["validation_reserve"]).values())
        or source.procedure.verification_kind != "CONTRACT"
        or bound_body["procedure_ref"] != source.procedure_ref
        or ref(run_body["policy_ref"], "probe-policy") != records.reference(policy)
        or projection_body["brief_ref"] != records.reference(brief)
        or projection_body["selection_ref"] != records.reference(selection)
    ):
        raise CatalogError("MODEL_CONTEXT_REJECTED")
    contract.validate_assignment(brief, bound)
    if isinstance(source.procedure.technique_ref, ReleaseRef):
        raise CatalogError("MODEL_CONTEXT_REJECTED")
    matches = [t for t in source.manifest.techniques if t.key == source.procedure.technique_ref.key]
    bindings = [
        b
        for b in source.bindings
        if b["entity_kind"] == "technique"
        and b["package_key"] == source.package
        and b["key"] == source.procedure.technique_ref.key
    ]
    if len(matches) != 1 or len(bindings) != 1 or body["technique_refs"] != [bindings[0]["ref"]]:
        raise CatalogError("MODEL_CONTEXT_REJECTED")
    return {
        "version": 1,
        "owner_id": owner,
        "run_id": run["id"],
        "managed_run_ref": records.reference(run),
        "manifest_ref": records.reference(manifest),
        "binding_ref": records.reference(binding),
        "projection_ref": records.reference(projection),
        "composition_ref": projection_body["composition_ref"],
        "brief_ref": records.reference(brief),
        "task_id": header["task_id"],
        "attempt_id": header["attempt_id"],
        "selection_ref": records.reference(selection),
        "selection": selection,
        "snapshot_ref": selected["snapshot_ref"],
        "recipe_key": selected["recipe_key"],
        "recipe_role": source.role,
        "technique_ref": bindings[0]["ref"],
        "source_work_kind": matches[0].work_kind,
        "procedure_ref": source.procedure_ref,
        "verification_kind": "CONTRACT",
        "preparation_receipt_ref": source.preparation_ref,
        "execution_kind": "CONTRACT_PROBE",
        "purpose": "SUPPORT",
        "requested": requested,
        "effective": None,
        "resolution": "NO_MODEL",
    }
