"""Trusted opt-in cold AIAgent state. No routing, client, tools or conversation.

This mode has its own complete finite state, NOT a partially initialized warm
agent. All warm surfaces (including lineage, wake, persistence and tools) refuse.
It cannot be upgraded to warm. The caller must create a new authorized agent.
"""
from dataclasses import dataclass
import inspect
from uuid import uuid4


class ColdAdmissionDenied(ValueError):
    pass


@dataclass(frozen=True)
class ColdAdmission:
    resolution: str = "NO_MODEL"
    parent_session_id: str | None = None


@dataclass
class ColdState:
    session_id: str
    native_id: str
    parent_session_id: str | None
    closed: bool = False
    binding: bytes | None = None
    terminal: str | None = None

    def block(self, binding: bytes) -> str:
        if self.closed or not binding:
            raise ColdAdmissionDenied("Cold agent unavailable")
        if self.binding is not None and self.binding != binding:
            raise ColdAdmissionDenied("Cold binding conflict")
        self.binding = binding
        self.terminal = "BLOCKED"
        return self.terminal


COLD_READABLE = frozenset({
    "_cold_state", "session_id", "_subagent_id", "_parent_session_id",
    "_delegate_role", "_delegate_depth", "provider", "model", "enabled_toolsets",
    "tools", "close", "__class__", "__dict__", "__weakref__",
})


def initialize_cold(agent, admission, kwargs):
    if type(admission) is not ColdAdmission or admission.resolution != "NO_MODEL":
        raise ColdAdmissionDenied("Unrecognized cold admission")
    if admission.parent_session_id is not None and (
        type(admission.parent_session_id) is not str or not 0 < len(admission.parent_session_id) <= 128
    ):
        raise ColdAdmissionDenied("Invalid cold parent")
    defaults = inspect.signature(type(agent).__init__).parameters
    if any(value != defaults[key].default for key, value in kwargs.items()):
        raise ColdAdmissionDenied("Cold admission cannot carry warm options")
    state = ColdState(str(uuid4()), str(uuid4()), admission.parent_session_id)
    agent.__dict__.update(
        _cold_state=state, session_id=state.session_id, _subagent_id=state.native_id,
        _parent_session_id=state.parent_session_id, _delegate_role="leaf" if state.parent_session_id else "orchestrator",
        _delegate_depth=1 if state.parent_session_id else 0, provider=None, model=None,
        enabled_toolsets=(), tools=(),
    )


def require_warm_parent(parent):
    if getattr(parent, "_cold_state", None) is not None:
        raise ColdAdmissionDenied("Cold lineage/stock launch unsupported")
