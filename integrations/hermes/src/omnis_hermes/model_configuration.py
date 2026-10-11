"""Strict read of a native cold configuration observation, never a READY grant."""

from . import managed_admission_contract as managed
from .native_preparation_contract import obj, text
from .prompt_bundle import integer, mapping

FIELDS = {
    "version",
    "source",
    "mode",
    "provider",
    "model_id",
    "native_child_id",
    "native_session_id",
    "native_parent_session_id",
}


def validate_configuration(value: object, payload: dict[str, object]) -> dict[str, object]:
    result = obj(value, FIELDS)
    integer(result["version"], 1, 1)
    context = mapping(payload["model_context"])
    body = mapping(mapping(payload["binding"])["payload"])
    rows = managed.entries(body["entries"], native=True, composed=True)
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
        raise ValueError("Invalid native configuration observation")
    text(result["native_child_id"])
    text(result["native_session_id"])
    text(result["native_parent_session_id"])
    return result
