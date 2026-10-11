"""Native validation of backend-qualified cold context, not catalog/model authority."""

from .managed_admission_contract import envelope, ref
from .native_preparation_contract import loads, obj, reference, uuid
from .prompt_bundle import integer, mapping, sequence, validate_composition

FIELDS = {
    "version",
    "owner_id",
    "run_id",
    "managed_run_ref",
    "manifest_ref",
    "binding_ref",
    "projection_ref",
    "composition_ref",
    "brief_ref",
    "task_id",
    "attempt_id",
    "selection_ref",
    "selection",
    "snapshot_ref",
    "recipe_key",
    "recipe_role",
    "technique_ref",
    "source_work_kind",
    "procedure_ref",
    "verification_kind",
    "preparation_receipt_ref",
    "execution_kind",
    "purpose",
    "requested",
    "effective",
    "resolution",
}


def validate_context(
    value: object,
    payload: dict[str, object],
    *,
    staged_manifest: object = None,
    staged_material: tuple[bytes, ...] | None = None,
) -> dict[str, object]:
    context = obj(value, FIELDS)
    integer(context["version"], 1, 1)
    for key in ("owner_id", "run_id", "task_id", "attempt_id"):
        uuid(context[key])
    kinds = {
        "managed_run_ref": "managed-run",
        "manifest_ref": "launch-manifest",
        "binding_ref": "runtime-binding",
        "projection_ref": "model-projection",
        "composition_ref": "prompt-composition",
        "brief_ref": "task-brief",
        "selection_ref": "execution-selection",
        "snapshot_ref": "run-snapshot",
        "technique_ref": "technique",
        "procedure_ref": "procedure",
        "preparation_receipt_ref": "native-preparation-receipt",
    }
    for key, kind in kinds.items():
        reference(context[key], kind)
    selection = envelope(context["selection"], "execution-selection")
    selected = obj(
        selection["payload"],
        {
            "snapshot_ref",
            "recipe_key",
            "selected_package_refs",
            "requested",
            "effective",
            "resolution",
            "reason",
            "compatibility_receipt_refs",
        },
    )
    requested = obj(selected["requested"], {"model_key", "effort", "requirement", "on_unavailable"})
    if (
        context["purpose"] != "SUPPORT"
        or context["execution_kind"] != "CONTRACT_PROBE"
        or context["verification_kind"] != "CONTRACT"
        or context["resolution"] != "NO_MODEL"
        or context["effective"] is not None
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
        or context["requested"] != requested
        or context["selection_ref"] != ref(selection)
        or context["snapshot_ref"] != selected["snapshot_ref"]
        or context["recipe_key"] != selected["recipe_key"]
        or type(context["recipe_key"]) is not str
        or not context["recipe_key"]
        or context["recipe_role"] not in ("RECON", "INVESTIGATOR", "VALIDATOR", "RESEARCH")
        or context["source_work_kind"]
        not in ("RECON", "ANALYSIS", "INVESTIGATION", "VALIDATION", "SUPPORT", "REVIEW")
        or selected["compatibility_receipt_refs"] != []
    ):
        raise ValueError("Invalid qualified model context")
    for package in sequence(selected["selected_package_refs"], 1, 4):
        reference(package, "package")
    projection = mapping(mapping(payload["projection"])["payload"])
    binding = envelope(payload["binding"], "runtime-binding")
    pins = {
        "owner_id": payload["owner_id"],
        "run_id": payload["run_id"],
        "manifest_ref": payload["manifest_ref"],
        "binding_ref": ref(binding),
        "projection_ref": payload["projection_ref"],
        "composition_ref": projection["composition_ref"],
        "brief_ref": projection["brief_ref"],
        "selection_ref": projection["selection_ref"],
        "snapshot_ref": projection["snapshot_ref"],
    }
    if (
        any(context[k] != v for k, v in pins.items())
        or mapping(context["managed_run_ref"])["id"] != context["run_id"]
    ):
        raise ValueError("Invalid qualified context pins")
    user = mapping(
        loads(
            str(
                mapping(sequence(mapping(projection["model_input"])["messages"], 2, 2)[1])[
                    "content"
                ]
            ).encode(),
            32768,
        )
    )
    header = mapping(user["header"])
    if (
        any(context[k] != header[k] for k in ("task_id", "attempt_id"))
        or context["recipe_role"] != user["role"]
    ):
        raise ValueError("Invalid qualified context assignment")
    if staged_manifest is not None:
        if staged_material is None:
            raise ValueError("Missing staged context material")
        manifest = envelope(staged_manifest, "launch-manifest")
        if (
            ref(manifest) != context["manifest_ref"]
            or mapping(manifest["payload"])["selection_ref"] != context["selection_ref"]
        ):
            raise ValueError("Invalid staged context manifest")
        entries = sequence(mapping(manifest["payload"])["entries"], 1, 2)
        matched = [
            mapping(e)
            for e in entries
            if mapping(e)["composition_ref"] == context["composition_ref"]
        ]
        materials = [mapping(loads(raw, 32768)) for raw in staged_material]
        compositions = [c for c in materials if ref(c) == context["composition_ref"]]
        if len(matched) != 1 or len(compositions) != 1:
            raise ValueError("Invalid staged context composition")
        raw = validate_composition(compositions[0], manifest, matched[0])
        sections = sequence(loads(raw, 32768))
        brief = envelope(mapping(sections[2])["record"], "task-brief")
        body = mapping(brief["payload"])
        bound = mapping(mapping(sections[3])["record"])
        if (
            ref(brief) != context["brief_ref"]
            or body["role"] != context["recipe_role"]
            or body["validation_reserve"] != {"actions": 0, "seconds": 0}
            or any(type(v) is not int for v in mapping(body["validation_reserve"]).values())
            or body["criterion_bindings"] != []
            or body["allowed_capability_ids"] != []
            or body["operation_refs"] != []
            or body["review_request"] is not None
            or body["technique_refs"] != [context["technique_ref"]]
            or mapping(bound["payload"])["procedure_ref"] != context["procedure_ref"]
            or mapping(compositions[0]["payload"])["preparation_receipt_ref"]
            != context["preparation_receipt_ref"]
        ):
            raise ValueError("Invalid staged context source")
    return context
