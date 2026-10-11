"""Qualified owned receipt of an actual native configuration observation.

This cold observation is not a provider-config or native-turn authority record.
"""

from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.tasks.managed_contract import exact, integer, mapping, sequence, text

SOURCE_FIELDS = {
    "version",
    "source",
    "mode",
    "provider",
    "model_id",
    "native_child_id",
    "native_session_id",
    "native_parent_session_id",
}


def validate_source(value: object, payload: dict[str, object]) -> dict[str, object]:
    result = exact(value, SOURCE_FIELDS)
    integer(result["version"], 1, 1)
    context = mapping(payload["model_context"])
    body = mapping(mapping(payload["binding"])["payload"])
    rows = [mapping(r) for r in sequence(body["entries"])]
    selected = [
        r
        for r in rows
        if r["task_id"] == context["task_id"] and r["attempt_id"] == context["attempt_id"]
    ]
    if (
        len(selected) != 1
        or result["source"] != "NATIVE_COLD_INITIALIZER"
        or result["mode"] != "NO_MODEL"
        or result["provider"] is not None
        or result["model_id"] is not None
        or context["effective"] is not None
        or context["resolution"] != "NO_MODEL"
        or result["native_child_id"] != selected[0]["native_child_id"]
        or result["native_session_id"] != selected[0]["native_session_id"]
    ):
        raise CatalogError("MODEL_CONFIGURATION_REJECTED")
    for key in ("native_child_id", "native_session_id", "native_parent_session_id"):
        text(result[key], 128)
    return result


def configuration_payload(payload: dict[str, object], source: object) -> dict[str, object]:
    context = mapping(payload["model_context"])
    binding = mapping(payload["binding"])
    return {
        "version": 1,
        "owner_id": payload["owner_id"],
        "run_id": payload["run_id"],
        "manifest_ref": payload["manifest_ref"],
        "binding_ref": records.reference(binding),
        "runtime_boot": mapping(binding["payload"])["runtime_boot"],
        "projection_ref": payload["projection_ref"],
        "selection_ref": context["selection_ref"],
        "task_id": context["task_id"],
        "attempt_id": context["attempt_id"],
        "context_digest": payload["model_context_digest"],
        "source_configuration": validate_source(source, payload),
        "inference_authorized": False,
    }
