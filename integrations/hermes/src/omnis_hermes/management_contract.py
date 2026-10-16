"""Private, credential-free Settings protocol, independent of native execution."""

from uuid import UUID

SELECTION = {"provider": "openai-codex", "model": "gpt-6.1-sol", "effort": "xhigh"}
OPS = {"settings", "settings_status"}


def identity(value: object) -> str:
    if type(value) is not str or str(UUID(value)) != value:
        raise ValueError("Invalid settings identity")
    return value


def selection(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    if type(value) is not dict or value != SELECTION:
        raise ValueError("Unsupported requested selection")
    return dict(SELECTION)


def command(value: object) -> dict[str, object]:
    if type(value) is not dict or set(value) != {"operation_id", "action", "selection"}:
        raise ValueError("Invalid settings command")
    identity(value["operation_id"])
    if value["action"] not in ("read", "save"):
        raise ValueError("Invalid settings action")
    selected = selection(value["selection"])
    if (value["action"] == "save") != (selected is not None):
        raise ValueError("Invalid settings selection")
    return value


def view(operation_id: str, status: str, selected: object = None) -> dict[str, object]:
    checked = selection(selected)
    return {
        "operation_id": identity(operation_id),
        "status": status,
        "selection": checked,
        "configured": status == "CONFIRMED" and checked is not None,
        "authenticated": "NOT_VERIFIED",
        "reachable": "NOT_VERIFIED",
        "inference_ready": False,
    }
