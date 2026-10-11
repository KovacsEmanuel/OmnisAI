"""Terminal inference denial for the existing Omnis inert runtime.

This is not a warm permission mechanism. A future authorized warm consumer
must supply authentic turn/config/admission/SENT and the physical Stop barrier;
neither a projection, a ledger dict nor the development model supplies them.
"""

import os
from typing import NoReturn


class ManagedModelTerminal(Exception):
    """Sanitized protocol outcome; explicitly propagated by native callers."""

    def __init__(self) -> None:
        super().__init__("Omnis model admission: NO_MODEL")
        self.cleanup_uncertain = False


def is_inert_model_context(agent: object = None) -> bool:
    attributes = getattr(agent, "__dict__", {})
    return os.environ.get("HERMES_OMNIS_INERT") == "1" or (
        isinstance(attributes, dict)
        and (
            attributes.get("_cold_state") is not None
            or attributes.get("_owned_initialization") is not None
            or attributes.get("_owned_core") is not None
        )
    )


def terminal_result(error: ManagedModelTerminal | None = None) -> dict[str, object]:
    # Never return inherited messages, errors, request bodies, token estimates,
    # model output, successful completion or permission to retry.
    return {
        "completed": False,
        "failed": True,
        "failure_retryable": False,
        "failure_reason": "omnis_model_admission",
        "model_admission_reason": "NO_MODEL",
        "final_response": "",
        "messages": [],
        "api_calls": 0,
        "error": "Omnis model admission: NO_MODEL",
        "cleanup_uncertain": error.cleanup_uncertain if error is not None else False,
    }


def deny_model() -> NoReturn:
    raise ManagedModelTerminal()


def require_model_authority(agent: object = None, *, final_request: object = None) -> None:
    # Explicit Omnis DATA never selects the stock warm route. There is no
    # authenticated turn/config admission producer yet; neither dropping the
    # inert env flag nor supplying native-turn-shaped refs provides one.
    if final_request is not None or is_inert_model_context(agent):
        deny_model()
