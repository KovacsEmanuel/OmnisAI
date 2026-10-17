"""Public, plugin-safe lifecycle API for delegated Hermes subagents: immutable contracts, not ``AIAgent``
objects. Plugins obtain it via ``PluginContext.subagent_lifecycle``."""

from __future__ import annotations

import contextvars
import dataclasses
import enum
import hashlib
import hmac
import json
import math
import secrets
import threading
import time
import contextlib
import weakref
from contextlib import contextmanager
from concurrent.futures import Future, TimeoutError
from typing import Any, Callable, Mapping, Optional

from agent.interrupt_compat import request_hard_interrupt

PUBLIC_CONTRACT_VERSION = 1
_MAX_GOAL_CHARS = 16_000
_MAX_CONTEXT_CHARS = 32_000
_MAX_METADATA_BYTES = 8_192
_MAX_RESULT_CHARS = 32_000
_TERMINAL_RETENTION_SECONDS = 3_600


class SubagentLifecycleError(ValueError):
    """A request cannot be safely accepted by the public lifecycle API."""


class SubagentState(str, enum.Enum):
    PENDING = "PENDING"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    INCONCLUSIVE = "INCONCLUSIVE"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


@dataclasses.dataclass(frozen=True)
class SubagentLaunchRequest:
    goal: str
    context: Optional[str] = None
    role: str = "leaf"
    model: Optional[str] = None
    allowed_toolsets: Optional[tuple[str, ...]] = None
    blocked_tools: tuple[str, ...] = ()
    working_directory: Optional[str] = None
    parent_session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Mapping[str, Any] = dataclasses.field(default_factory=dict)
    timeout_seconds: Optional[float] = None


@dataclasses.dataclass(frozen=True)
class SubagentHandle:
    contract_version: int
    subagent_id: str
    parent_session_id: Optional[str]
    correlation_id: Optional[str]
    created_at: float
    provider: Optional[str]
    model: Optional[str]
    role: str
    depth: int
    capability: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SubagentHandle":
        try:
            return cls(**dict(value))
        except (TypeError, ValueError) as exc:
            raise SubagentLifecycleError("Malformed subagent handle.") from exc


@dataclasses.dataclass(frozen=True)
class SubagentStatus:
    handle: SubagentHandle
    state: SubagentState
    updated_at: float
    diagnostic: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class SubagentTerminalState:
    handle: SubagentHandle
    state: SubagentState
    completed: bool
    timed_out: bool = False
    diagnostic: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class SubagentCancelResult:
    accepted: bool
    already_terminal: bool = False
    unknown_handle: bool = False
    unsupported: bool = False
    state: SubagentState = SubagentState.UNKNOWN


@dataclasses.dataclass(frozen=True)
class SubagentResult:
    handle: SubagentHandle
    terminal_state: SubagentState
    ready: bool
    summary: Optional[str] = None
    structured_payload: Optional[Mapping[str, Any]] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error_classification: Optional[str] = None
    error_message: Optional[str] = None
    usage_metadata: Mapping[str, Any] = dataclasses.field(default_factory=dict)
    tool_execution_summary: Mapping[str, Any] = dataclasses.field(default_factory=dict)
    result_hash: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class SubagentReconnectResult:
    connected: bool
    state: SubagentState
    diagnostic: Optional[str] = None


@dataclasses.dataclass
class _Record:
    handle: SubagentHandle
    state: SubagentState
    updated_at: float
    agent: Any = None
    future: Optional[Future] = None
    model_test_submit_started: bool = False
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[SubagentResult] = None


@dataclasses.dataclass
class _Registry:
    """Thread-safe terminal-retention registry; never returns live records."""

    lock: threading.RLock = dataclasses.field(default_factory=threading.RLock)
    records: dict[str, _Record] = dataclasses.field(default_factory=dict)
    correlations: dict[tuple[Optional[str], str], str] = dataclasses.field(default_factory=dict)


_REGISTRY = _Registry()
from tools.daemon_pool import DaemonThreadPoolExecutor as _DaemonExecutor  # daemon: a wedged child never blocks exit
_EXECUTOR = _DaemonExecutor(max_workers=8, thread_name_prefix="hermes-lifecycle")
_SECRET = secrets.token_bytes(32)
_ACTIVE_PARENT_AGENT: contextvars.ContextVar[Any] = contextvars.ContextVar("hermes_subagent_lifecycle_parent", default=None)


@contextmanager
def bind_subagent_parent(parent_agent: Any):
    """Bind the host-owned parent for the current agent turn.

    Stored as a weakref: every asyncio Handle/Future scheduled from the turn
    (LSP reader loops, kernel pipes, ...) snapshots the Context, and those
    snapshots outlive the turn. A strong ref there pinned finished delegate
    children — each of which binds itself here for its own turn — in the
    parent process heap for the life of the background loop.
    """
    try:
        ref = weakref.ref(parent_agent)
    except TypeError:
        ref = lambda: parent_agent  # noqa: E731 — non-weakrefable test doubles
    token = _ACTIVE_PARENT_AGENT.set(ref)
    try:
        yield
    finally:
        _ACTIVE_PARENT_AGENT.reset(token)


def get_active_subagent_parent() -> Any:
    """Return the parent bound to this execution context, if any."""
    ref = _ACTIVE_PARENT_AGENT.get()
    return ref() if ref is not None else None


def _opt_str(value: Any) -> bool:
    return value is None or isinstance(value, str)


def _session_id_of(agent: Any) -> Optional[str]:
    return str(getattr(agent, "session_id", "") or "") or None


def _clip(value: Any) -> Optional[str]:
    return str(value)[:_MAX_RESULT_CHARS] if value is not None else None


# Per-field shape check applied to a (possibly deserialized) handle before trusting it.
_HANDLE_FIELD_CHECKS: tuple[tuple[str, Callable[[Any], bool]], ...] = (
    ("contract_version", lambda v: type(v) is int and v == PUBLIC_CONTRACT_VERSION),
    ("subagent_id", lambda v: isinstance(v, str) and bool(v)),
    ("parent_session_id", _opt_str),
    ("correlation_id", _opt_str),
    ("created_at", lambda v: not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v)),
    ("provider", _opt_str),
    ("model", _opt_str),
    ("role", lambda v: isinstance(v, str)),
    ("depth", lambda v: type(v) is int),
    ("capability", lambda v: isinstance(v, str)),
)

# Launch-request rejections in check order: (predicate, error). The type check leads so later predicates may
# dereference request fields.
_REQUEST_REJECTIONS: tuple[tuple[Callable[[Any], bool], str], ...] = (
    (lambda r: not isinstance(r, SubagentLaunchRequest) or not isinstance(r.goal, str) or not r.goal.strip() or len(r.goal) > _MAX_GOAL_CHARS,
     "goal must be a non-empty string of at most 16000 characters."),
    (lambda r: r.context is not None and (not isinstance(r.context, str) or len(r.context) > _MAX_CONTEXT_CHARS),
     "context must be a string of at most 32000 characters."),
    (lambda r: r.role not in {"leaf", "orchestrator"}, "role must be 'leaf' or 'orchestrator'."),
    (lambda r: r.timeout_seconds is not None, "Per-launch timeout is not supported; configure delegation timeout explicitly."),
    (lambda r: r.working_directory is not None,
     "working_directory is not supported because Hermes delegates use isolated task environments."),
    (lambda r: bool(r.blocked_tools),
     "Per-tool blocking is not supported; use allowed_toolsets. Hermes always blocks unsafe child tools."),
)


def _handle_is_well_formed(handle: Any) -> bool:
    return isinstance(handle, SubagentHandle) and all(check(getattr(handle, field)) for field, check in _HANDLE_FIELD_CHECKS)


class SubagentLifecycleService:
    """Stable public service behind :attr:`PluginContext.subagent_lifecycle`. Children run in-process only;
    completed results stay until process exit; ``reconnect`` reports that a serialized handle cannot
    reconnect after a restart instead of launching work again."""

    def __init__(self, parent_agent_resolver: Callable[[], Any]) -> None:
        self._parent_agent_resolver = parent_agent_resolver
        self._cold_batches = {}
        self._model_test_batches = {}

    def prepare_model_test(self, payload):
        from omnis_hermes.managed_admission_contract import (
            ModelTestPreparation, canonical, preparation_result, validate_model_prepare, ref,
        )
        from agent.agent_init import observe_model_test
        from agent.cold_admission import configuration_snapshot

        p = validate_model_prepare(payload)
        c = p["context"]["payload"]
        key = c["preparation_id"]
        bound = canonical({k:v for k,v in p.items() if k != "mode"})
        with _REGISTRY.lock:
            prior = self._model_test_batches.get(key)
            if prior is not None:
                if prior["bound"] != bound:
                    raise ValueError("Preparation replay conflict")
                if prior["record"] is None:
                    return preparation_result(p)
                child = prior["record"].agent
                if child._model_test_closed.is_set() or child._model_test_failure is not None:
                    return preparation_result(p)
                parent = self._parent_agent_resolver()
                if (parent is not prior["parent"]
                        or (parent._subagent_id, parent.session_id) != prior["root_identity"]):
                    raise ValueError("Preparation root identity changed")
                configuration_snapshot(parent)
                if (child._subagent_id, child.session_id) != prior["child_identity"]:
                    raise ValueError("Preparation child identity changed")
                observe_model_test(child)
                if child._parent_session_id != prior["root_identity"][1]:
                    raise ValueError("Preparation child parent changed")
                if not child._model_test_ready.is_set() or child._model_test_turn is None:
                    return preparation_result(p)
                return preparation_result(p, native_root_id=prior["parent"]._subagent_id,
                    native_child_id=child._subagent_id, native_session_id=child.session_id,
                    native_turn=child._model_test_turn)
            if p["mode"] == "STATUS":
                return preparation_result(p)
            if getattr(self, "_model_test_stopping", False):
                raise ValueError("Native preparation owner stopping")
            parent = self._parent_agent_resolver()
            configuration_snapshot(parent)
            if parent._parent_session_id is not None or len(self._model_test_batches) >= 32:
                raise ValueError("Fresh native preparation root required")
            for batch in self._model_test_batches.values():
                held = batch["record"]
                if (held is None or not held.agent._model_test_closed.is_set()
                        or (held.model_test_submit_started and held.future is None)
                        or (held.future is not None and not held.future.done())):
                    raise ValueError("Native preparation active or drain uncertain")
            prepared = {id(b["record"]) for b in self._model_test_batches.values()}
            for held in _REGISTRY.records.values():
                if id(held) not in prepared and (
                        (held.future is not None and not held.future.done())
                        or held.state in (SubagentState.PENDING, SubagentState.STARTING,
                                          SubagentState.RUNNING, SubagentState.CANCEL_REQUESTED)):
                    raise ValueError("Native child already active")
            # Retain failure before the constructor: uncertain CREATE is never repeated.
            marker = {"bound": bound, "parent": parent, "record": None, "child": None,
                      "context_ref": ref(p["context"]), "protocol": p["protocol"],
                      "root_identity": (parent._subagent_id, parent.session_id)}
            self._model_test_batches[key] = marker
            try:
                from run_agent import AIAgent
                child = AIAgent(model_test_preparation=ModelTestPreparation(canonical(p)))
                marker["child"] = child
                marker["child_identity"] = (child._subagent_id, child.session_id)
                child._parent_session_id = parent.session_id
                created = time.time()
                handle = SubagentHandle(PUBLIC_CONTRACT_VERSION, child._subagent_id, parent.session_id,
                    None, created, None, None, "leaf", 1,
                    self._capability(child._subagent_id, parent.session_id, created))
                record = _Record(handle, SubagentState.PENDING, created, agent=child)
                child._model_test_record = record
                marker["record"] = record
                _REGISTRY.records[handle.subagent_id] = record
                def conversation():
                    try:
                        from agent.conversation_loop import run_conversation
                        composition = next(r for r in p["records"] if r["kind"] == "prompt-composition")
                        run_conversation(child, composition["payload"]["text"], task_id=c["task_id"])
                    except Exception:
                        child._model_test_failure = "PREPARATION_STOPPED_OR_FAILED"
                        child._model_test_ready.set()
                record.model_test_submit_started = True
                record.future = _EXECUTOR.submit(conversation)
                if not child._model_test_ready.wait(2):
                    child.close()
                    raise ValueError("Preparation turn binding timeout")
                if child._model_test_failure is not None:
                    raise ValueError("Preparation turn binding failed")
                if self._parent_agent_resolver() is not parent:
                    child.close()
                    raise ValueError("Preparation root changed")
                configuration_snapshot(parent)
                observe_model_test(child)
                return preparation_result(p, native_root_id=parent._subagent_id,
                    native_child_id=child._subagent_id, native_session_id=child.session_id,
                    native_turn=child._model_test_turn)
            except BaseException:
                if marker["child"] is not None:
                    with contextlib.suppress(BaseException):
                        marker["child"].close()  # cleanup cannot replace the primary failure
                raise

    def execute_model_test(self, payload):
        from omnis_hermes.model_request import execution_packet, CodexFinalRequest
        from omnis_hermes.managed_admission_contract import canonical, ref, validate_execution_result
        p = execution_packet(payload)
        with _REGISTRY.lock:
            batches = [b for b in self._model_test_batches.values() if b["context_ref"] == p["context_ref"]]
            if len(batches) != 1 or getattr(self, "_model_test_stopping", False):
                raise ValueError("Execution owner unavailable")
            batch = batches[0]
            child = batch["child"]
            if child is None or not child._model_test_execution or child._model_test_closed.is_set():
                raise ValueError("Not an execution child")
            parent = self._parent_agent_resolver()
            if parent is not batch["parent"] or (parent._subagent_id, parent.session_id) != batch["root_identity"] or (child._subagent_id, child.session_id) != batch["child_identity"]:
                raise ValueError("Execution lineage changed")
            c = child._model_test_preparation.payload()["context"]["payload"]
            b, t, d, projection = (p[k]["payload"] for k in ("binding", "turn", "dispatch", "projection"))
            if (b["native_root_id"] != parent._subagent_id or b["native_child_id"] != child._subagent_id
                    or b["native_session_id"] != child.session_id or b["native_turn"] != child._model_test_turn
                    or t["context_ref"] != ref(child._model_test_preparation.payload()["context"])
                    or d["provider_config_ref"] != c["provider_config_ref"] or d["execution_selection_ref"] != c["selection_ref"]
                    or d["fencing_epoch"] != c["authority"]["epoch"] or b["authority"] != c["authority"] or b["runtime_boot"] != c["runtime_boot"]
                    or projection["selection_ref"] != c["selection_ref"] or projection["composition_ref"] != c["composition_ref"]
                    or projection["owner_id"] != c["owner_id"] or projection["run_id"] != c["run_id"]):
                raise ValueError("Execution binding changed")
            composition = next(r for r in child._model_test_preparation.payload()["records"] if r["kind"] == "prompt-composition")
            if projection["model_input"]["messages"][1]["content"] != composition["payload"]["text"]:
                raise ValueError("Execution DATA changed")
            bound = canonical({**p, "mode": "SEND"})
            if child._model_test_dispatch is None:
                if p["mode"] == "SEND":
                    child._model_test_lifeline._owner_alive()
                    child._model_test_dispatch = CodexFinalRequest(bound)
                    child._model_test_release.set()
            elif child._model_test_dispatch.raw != bound:
                raise ValueError("Execution replay conflict")
            value = child._model_test_result
            if value is None:
                value = {"protocol": p["protocol"], "context_ref": p["context_ref"],
                    "dispatch_ref": ref(p["dispatch"]), "status": "PENDING" if child._model_test_dispatch is not None else "UNKNOWN", "receipt": None}
            return validate_execution_result(value, p)

    def close_model_tests(self, context_ref=None):
        with _REGISTRY.lock:
            if context_ref is not None and not any(
                    b["context_ref"] == context_ref for b in self._model_test_batches.values()):
                raise ValueError("Unknown native preparation context")
            self._model_test_stopping = True
            children = [b["child"] for b in self._model_test_batches.values() if b["child"] is not None]
            for child in children:
                child._model_test_closed.set()  # revoke every child before the first join
        uncertain = False
        for batch in self._model_test_batches.values():
            try:
                child, record = batch["child"], batch["record"]
                if child is None or record is None:
                    uncertain = True
                if child is not None and (record is None or record.future is None or not record.future.done()):
                    child.close()
                if record is not None and (record.future is None or not record.future.done()):
                    uncertain = True
            except Exception:
                uncertain = True
        if uncertain:
            raise ValueError("Native preparation drain uncertain")
        if context_ref is not None:
            # Receipt follows actual owner revocation and the single record Future.
            return {"protocol": next(b["protocol"] for b in self._model_test_batches.values() if b["context_ref"] == context_ref), "mode": "CLOSE",
                    "context_ref": context_ref, "status": "CLOSED_JOINED"}

    def stage(self, payload):
        """Create cold native identities, with no executor or conversation admission."""
        from omnis_hermes.managed_admission_contract import validate_stage, ref, canonical
        from agent.cold_admission import ColdAdmission, ColdAdmissionDenied
        from uuid import uuid4
        # Freeze caller-owned data, then validate the complete material before identities.
        payload = json.loads(canonical(payload))
        manifest = validate_stage(payload)
        composition_material = tuple(canonical(c) for c in payload.get("compositions", []))
        with _REGISTRY.lock:
            parent = self._parent_agent_resolver()
            state = getattr(parent, "_cold_state", None)
            if state is None or state.closed or state.parent_session_id is not None:
                raise ColdAdmissionDenied("A live cold native root is required")
            prior = self._cold_batches.get(manifest["id"])
            if prior is not None:
                if (prior["manifest"] != manifest or prior["composition_material"] != composition_material
                        or prior["response"]["protocol"] != payload["protocol"]):
                    raise ColdAdmissionDenied("Manifest replay conflict")
                self._require_cold_root(prior, parent)
                if prior.get("indeterminate"):
                    raise ColdAdmissionDenied("CONTRACT execution indeterminate; no retry")
                return json.loads(json.dumps(prior["response"]))
            if len(self._cold_batches) >= 64:
                raise ColdAdmissionDenied("Cold registry full")
            # Branch precedes _resolve_child_runtime and init_agent, not a late observer.
            from run_agent import AIAgent
            rows, records = [], []
            try:
                for entry in manifest["payload"]["entries"]:
                    if payload["protocol"] == "omnis-managed-admission-v4":
                        from agent.contract_execution import ContractAdmission
                        child = AIAgent(contract_admission=ContractAdmission(parent, canonical(payload), entry["batch_index"]))
                    else:
                        child = AIAgent(cold_admission=ColdAdmission(parent_session_id=parent.session_id))
                    created = time.time()
                    handle = SubagentHandle(
                        PUBLIC_CONTRACT_VERSION, child._subagent_id, parent.session_id, None,
                        created, None, None, "leaf", 1,
                        self._capability(child._subagent_id, parent.session_id, created),
                    )
                    records.append(_Record(handle, SubagentState.PENDING, created, agent=child))
                    rows.append({**{k:v for k,v in entry.items() if k != "goal"},
                                 "native_child_id": child._subagent_id, "native_session_id": child.session_id})
            except BaseException:
                for record in records:
                    record.agent.close()
                raise
            response = dict(protocol=payload["protocol"], status="STAGED", ticket=str(uuid4()),
                            manifest_ref=ref(manifest), native_root_id=parent._subagent_id, entries=rows)
            for record in records:
                _REGISTRY.records[record.handle.subagent_id] = record
            self._cold_batches[manifest["id"]] = dict(
                manifest=json.loads(json.dumps(manifest)), response=response, records=records,
                composition_material=composition_material,
                expires=time.monotonic() + 4.5, binding=None,
                parent=parent, parent_session_id=parent.session_id,
            )
            return json.loads(json.dumps(response))

    def _require_cold_root(self, batch, parent):
        """Admission stays with the original root; status readback is historical."""
        from agent.cold_admission import ColdAdmissionDenied
        state = getattr(parent, "_cold_state", None)
        if (parent is not batch["parent"] or state is None or state.closed
                or parent.session_id != batch["parent_session_id"]
                or state.session_id != batch["parent_session_id"]
                or parent._subagent_id != batch["response"]["native_root_id"]
                or state.native_id != batch["response"]["native_root_id"]):
            raise ColdAdmissionDenied("Native root lineage changed or stopped")

    def _cold_batch(self, payload):
        from agent.cold_admission import ColdAdmissionDenied
        batch = self._cold_batches.get(payload["manifest_ref"]["id"])
        if batch is None or any(payload[k] != batch["response"][k] for k in ("protocol", "ticket", "manifest_ref")):
            raise ColdAdmissionDenied("Unknown native stage")
        return batch

    def readback(self, payload):
        from omnis_hermes.managed_admission_contract import validate_status
        validate_status(payload)
        with _REGISTRY.lock:
            batch = self._cold_batch(payload)
            if batch.get("indeterminate"):
                raise ValueError("CONTRACT execution indeterminate; no retry")
            return json.loads(json.dumps(batch["response"]))

    def model_preflight(self, payload):
        """Consume qualified model data without promoting a cold child to a turn."""
        from omnis_hermes.model_admission import validate_preflight, cold_preflight
        from omnis_hermes.native_preparation_contract import canonical
        from agent.cold_admission import ColdAdmissionDenied
        payload = json.loads(canonical(payload))
        validate_preflight(payload)
        with _REGISTRY.lock:
            batch = self._cold_batch(payload)
            if batch["response"]["protocol"] == "omnis-managed-admission-v4":
                raise ColdAdmissionDenied("CONTRACT method has no model preflight")
            parent = self._parent_agent_resolver()
            self._require_cold_root(batch, parent)
            body = payload["binding"]["payload"]
            rows = batch["response"]["entries"]
            if (batch["binding"] is not None or time.monotonic() >= batch["expires"]
                    or body["run_id"] != batch["manifest"]["payload"]["run_id"]
                    or body["entries"] != rows or len(rows) != len(batch["records"])):
                raise ColdAdmissionDenied("Model preflight lifecycle unavailable")
            for row, record in zip(rows, batch["records"], strict=True):
                child = record.agent
                state = getattr(child, "_cold_state", None)
                if (record.state != SubagentState.PENDING or state is None or state.closed
                        or child._subagent_id != row["native_child_id"]
                        or child.session_id != row["native_session_id"]
                        or state.native_id != row["native_child_id"]
                        or state.session_id != row["native_session_id"]
                        or state.parent_session_id != parent.session_id):
                    raise ColdAdmissionDenied("Model preflight native lineage unavailable")
            from omnis_hermes.model_context import validate_context
            validate_context(payload["model_context"], payload,
                staged_manifest=batch["manifest"], staged_material=batch["composition_material"])
            from agent.cold_admission import configuration_snapshot
            context = payload["model_context"]
            selected = [record.agent for row, record in zip(rows, batch["records"], strict=True)
                        if row["task_id"] == context["task_id"] and row["attempt_id"] == context["attempt_id"]]
            if len(selected) != 1:
                raise ColdAdmissionDenied("Native configuration assignment unavailable")
            configuration = configuration_snapshot(selected[0])
            return cold_preflight(payload, native_root_id=parent._subagent_id,
                native_entries=rows, source_configuration=configuration)

    def release(self, payload):
        """Binding barrier; authentic terminal BLOCKED, never a simulated turn."""
        from omnis_hermes.managed_admission_contract import validate_release, ref, canonical, digest
        from agent.cold_admission import ColdAdmissionDenied
        payload = json.loads(canonical(payload))
        validate_release(payload)
        with _REGISTRY.lock:
            batch = self._cold_batch(payload)
            binding = payload["binding"]
            body, response = binding["payload"], batch["response"]
            if (body["run_id"] != batch["manifest"]["payload"]["run_id"]
                    or body["native_root_id"] != response["native_root_id"]
                    or body["entries"] != response["entries"]):
                raise ColdAdmissionDenied("Native binding mismatch")
            if batch["binding"] is not None:
                if canonical(binding) != batch["binding"]:
                    raise ColdAdmissionDenied("Immutable binding conflict")
                if batch.get("indeterminate"):
                    raise ColdAdmissionDenied("CONTRACT execution indeterminate; no retry")
                return json.loads(json.dumps(response))
            parent = self._parent_agent_resolver()
            self._require_cold_root(batch, parent)
            if response["protocol"] == "omnis-managed-admission-v4":
                self._start_contract(batch, payload, parent)
            else:
                if (time.monotonic() >= batch["expires"]
                        or any(r.state != SubagentState.PENDING or r.agent._cold_state.closed
                               for r in batch["records"])):
                    raise ColdAdmissionDenied("Native stage expired or stopped")
                # No observer participates in authority. Validation finishes before mutation.
                committed = canonical(binding)
                for record in batch["records"]:
                    child = record.agent
                    state = child._cold_state.block(committed)
                    completed = time.time()
                    result = SubagentResult(
                        record.handle, SubagentState(state), True, completed_at=completed,
                        error_classification="NO_MODEL", structured_payload={"binding_ref": ref(binding)},
                        usage_metadata={"api_calls": 0}, tool_execution_summary={"tool_calls": 0},
                    )
                    result = dataclasses.replace(result, result_hash=digest(canonical(dataclasses.asdict(result))))
                    record.result, record.state = result, result.terminal_state
                    record.completed_at = record.updated_at = completed
                    child.close()
                    record.agent = None
                batch["binding"] = committed
                batch["response"] = {**response, "status": "BLOCKED", "reason": "NO_MODEL", "binding_ref": ref(binding)}
                return json.loads(json.dumps(batch["response"]))
        # Futures/joins must never run under the registry lock (including this caller).
        return self._release_contract(batch, payload, parent)

    def _contract_guard(self, batch, record, parent, committed):
        from agent.cold_admission import ColdAdmissionDenied
        from agent.contract_execution import ContractState
        with _REGISTRY.lock:
            self._require_cold_root(batch, self._parent_agent_resolver())
            child = record.agent
            state = child._contract_state if child is not None else None
            index = state.batch_index if type(state) is ContractState else None
            if type(index) is not int or not 0 <= index < len(batch["records"]):
                raise ColdAdmissionDenied("CONTRACT trusted index unavailable")
            row = batch["response"]["entries"][index]
            if (batch["records"][index] is not record
                    or _REGISTRY.records.get(record.handle.subagent_id) is not record
                    or type(state) is not ContractState or state.closed or state.parent is not parent
                    or state.parent_session_id != parent.session_id or state.binding != committed
                    or batch.get("failed") or batch["binding"] != committed or record.state != SubagentState.RUNNING
                    or state.native_id != row["native_child_id"] or state.session_id != row["native_session_id"]
                    or child._subagent_id != row["native_child_id"] or child.session_id != row["native_session_id"]
                    or child._parent_session_id != parent.session_id
                    or time.monotonic() >= min(batch["expires"], batch["execution_deadline"])):
                raise ColdAdmissionDenied("CONTRACT live binding unavailable")
            return True

    def _start_contract(self, batch, payload, parent):
        # Caller owns _REGISTRY.lock; validate the entire batch before any mutation.
        from agent.cold_admission import ColdAdmissionDenied
        from agent.contract_execution import ContractState
        from omnis_hermes.managed_admission_contract import canonical
        from datetime import datetime, timezone
        for index, (row, record) in enumerate(zip(batch["response"]["entries"], batch["records"], strict=True)):
            child = record.agent
            state = child._contract_state if child is not None else None
            if (type(state) is not ContractState or state.closed or state.binding is not None or state.started
                    or type(state.batch_index) is not int or state.batch_index != index
                    or _REGISTRY.records.get(record.handle.subagent_id) is not record
                    or record.state != SubagentState.PENDING or state.parent is not parent
                    or state.parent_session_id != parent.session_id
                    or state.native_id != row["native_child_id"] or state.session_id != row["native_session_id"]
                    or child._subagent_id != row["native_child_id"] or child.session_id != row["native_session_id"]
                    or child._parent_session_id != parent.session_id or time.monotonic() >= batch["expires"]):
                raise ColdAdmissionDenied("CONTRACT stage expired or stopped")
            if datetime.now(timezone.utc) >= datetime.fromisoformat(state.deadline):
                raise ColdAdmissionDenied("CONTRACT assignment expired")
        committed = canonical(payload["binding"])
        batch["binding"] = committed
        batch["execution_deadline"] = time.monotonic() + 3.0
        batch["indeterminate"] = True
        for record in batch["records"]:
            record.agent._contract_state.binding = committed
            record.state = SubagentState.RUNNING
            record.started_at = record.updated_at = time.time()

    def _run_contract_record(self, batch, record, parent, committed):
        child = record.agent
        try:
            return child.run_contract(committed, lambda: self._contract_guard(batch, record, parent, committed))
        finally:
            child.close()
            with _REGISTRY.lock:
                record.agent = None

    def _release_contract(self, batch, payload, parent):
        from omnis_hermes.managed_admission_contract import canonical, digest, ref, validate_response
        committed = batch["binding"]
        try:
            # All RUNNING/bindings are latched. Workers cannot pass the guard until
            # every submission has completed or partial submission has been revoked.
            with _REGISTRY.lock:
                try:
                    for record in batch["records"]:
                        record.future = _EXECUTOR.submit(self._run_contract_record, batch, record, parent, committed)
                except BaseException:
                    self._fail_contract_locked(batch)
                    raise
            executions = [record.future.result(timeout=max(0, min(batch["expires"], batch["execution_deadline"]) - time.monotonic()))
                          for record in batch["records"]]
            terminal = SubagentState(executions[0]["records"][0]["payload"]["status"])
            final = {**batch["response"], "status": terminal.value, "reason": "CONTRACT_PURE",
                     "binding_ref": ref(payload["binding"]), "executions": executions}
            validate_response(final)  # ordered homogeneous whole batch, unchanged aggregate cap
            with _REGISTRY.lock:
                previous_response = batch["response"]
                try:
                    results = []
                    for record, execution in zip(batch["records"], executions, strict=True):
                        result = SubagentResult(record.handle, terminal, True,
                            started_at=record.started_at, completed_at=time.time(), structured_payload=execution,
                            usage_metadata={"api_calls": 0}, tool_execution_summary={"tool_calls": sum(r["kind"] == "contract-tool-receipt" for r in execution["records"])})
                        results.append(dataclasses.replace(result, result_hash=digest(canonical(dataclasses.asdict(result)))))
                    response = json.loads(json.dumps(final))
                    # Build/hash the whole set first; rollback any interrupted publication
                    # before releasing the same lock used by result/status/readback.
                    for record, result in zip(batch["records"], results, strict=True):
                        record.result = result
                        record.state = terminal
                        record.completed_at = record.updated_at = result.completed_at
                    batch["response"] = final
                    batch["indeterminate"] = False
                    return response
                except BaseException:
                    batch["response"] = previous_response
                    self._fail_contract_locked(batch)
                    raise
        except BaseException:
            with _REGISTRY.lock:
                self._fail_contract_locked(batch)
            # Keep running futures and the indeterminate latch observable. No retry,
            # invented partial final, or false claim that a timeout drained a worker.
            raise
    def _fail_contract_locked(self, batch):
        # Caller holds the same lock as guards and public result readers. Never join.
        batch["failed"] = True
        batch["indeterminate"] = True
        for record in batch["records"]:
            record.result = None
            record.completed_at = None
            record.state = SubagentState.UNKNOWN
            record.updated_at = time.time()
            if record.agent is not None:
                record.agent.close()  # revocation is not proof of worker drain
            if record.future is None or record.future.cancel():
                record.agent = None

    def launch(self, request: SubagentLaunchRequest) -> SubagentHandle:
        parent = self._parent_agent_resolver()
        from agent.cold_admission import require_warm_parent
        require_warm_parent(parent)
        if parent is None:
            raise SubagentLifecycleError("No active Hermes parent session is available.")
        self._validate_request(request, parent)
        parent_session_id = _session_id_of(parent)
        if request.parent_session_id and request.parent_session_id != parent_session_id:
            raise SubagentLifecycleError("parent_session_id does not match the active session.")
        correlation_key = (parent_session_id, request.correlation_id or "")
        with _REGISTRY.lock:
            self._cleanup_locked()
            if request.correlation_id and correlation_key in _REGISTRY.correlations:
                raise SubagentLifecycleError("Duplicate correlation_id for this parent session.")
        # Lazy: delegate construction stays internal, plugins never import private delegation helpers.
        from tools.delegate_tool import _build_child_preserving_parent_tools, DEFAULT_MAX_ITERATIONS
        child = _build_child_preserving_parent_tools(
            task_index=0, goal=request.goal, context=request.context,
            toolsets=list(request.allowed_toolsets) if request.allowed_toolsets else None,
            model=request.model, max_iterations=DEFAULT_MAX_ITERATIONS, task_count=1, parent_agent=parent, role=request.role,
        )
        subagent_id = str(getattr(child, "_subagent_id", "") or "")
        if not subagent_id:
            raise SubagentLifecycleError("Hermes failed to assign a child identity.")
        created = time.time()
        handle = SubagentHandle(
            PUBLIC_CONTRACT_VERSION, subagent_id, parent_session_id, request.correlation_id, created,
            getattr(child, "provider", None), getattr(child, "model", None), getattr(child, "_delegate_role", request.role),
            int(getattr(child, "_delegate_depth", 1) or 1), self._capability(subagent_id, parent_session_id, created),
        )
        record = _Record(handle, SubagentState.PENDING, created, agent=child)
        with _REGISTRY.lock:
            _REGISTRY.records[subagent_id] = record
            if request.correlation_id:
                _REGISTRY.correlations[correlation_key] = subagent_id
        record.future = _EXECUTOR.submit(self._run, record, request.goal, parent)
        return handle

    def status(self, handle: SubagentHandle) -> SubagentStatus:
        record = self._record(handle)
        if record is None:
            return SubagentStatus(handle, SubagentState.UNKNOWN, time.time(), "UNKNOWN_HANDLE")
        with _REGISTRY.lock:
            return SubagentStatus(record.handle, record.state, record.updated_at)

    def wait(self, handle: SubagentHandle, *, timeout_seconds: Optional[float] = None) -> SubagentTerminalState:
        record = self._record(handle)
        if record is None:
            return SubagentTerminalState(handle, SubagentState.UNKNOWN, True, diagnostic="UNKNOWN_HANDLE")
        try:
            if record.future is not None:
                record.future.result(timeout=timeout_seconds)
        except TimeoutError:
            return SubagentTerminalState(record.handle, record.state, False, True)
        except Exception:
            pass
        with _REGISTRY.lock:
            return SubagentTerminalState(record.handle, record.state, record.result is not None)

    def cancel(self, handle: SubagentHandle, *, reason: str) -> SubagentCancelResult:
        record = self._record(handle)
        if record is None:
            return SubagentCancelResult(False, unknown_handle=True)
        with _REGISTRY.lock:
            if record.result is not None:
                return SubagentCancelResult(False, already_terminal=True, state=record.state)
            agent = record.agent
            record.state = SubagentState.CANCEL_REQUESTED
            record.updated_at = time.time()
        accepted = False
        if agent is not None:
            with contextlib.suppress(Exception):
                accepted = request_hard_interrupt(
                    agent, f"Lifecycle cancellation requested: {reason[:500]}", tool_reason="subagent cancellation requested",
                )
        return SubagentCancelResult(bool(accepted), unsupported=not accepted, state=SubagentState.CANCEL_REQUESTED)

    def result(self, handle: SubagentHandle) -> SubagentResult:
        record = self._record(handle)
        if record is None:
            return SubagentResult(handle, SubagentState.UNKNOWN, False, error_classification="UNKNOWN_HANDLE")
        with _REGISTRY.lock:
            return record.result or SubagentResult(record.handle, record.state, False, error_classification="NOT_READY")

    def reconnect(self, handle: SubagentHandle) -> SubagentReconnectResult:
        record = self._record(handle)
        if record is None:
            return SubagentReconnectResult(False, SubagentState.UNKNOWN, "RECONNECT_UNAVAILABLE")
        with _REGISTRY.lock:
            return SubagentReconnectResult(True, record.state)

    def _record(self, handle: SubagentHandle) -> Optional[_Record]:
        """Registry record for a well-formed, capability-verified handle owned by the active parent."""
        if not _handle_is_well_formed(handle):
            return None
        expected = self._capability(handle.subagent_id, handle.parent_session_id, handle.created_at)
        if not hmac.compare_digest(handle.capability, expected):
            return None
        if _session_id_of(self._parent_agent_resolver()) != handle.parent_session_id:
            return None
        with _REGISTRY.lock:
            return _REGISTRY.records.get(handle.subagent_id)

    @staticmethod
    def _cleanup_locked() -> None:
        """Retain terminal snapshots for a bounded period, never live work."""
        cutoff = time.time() - _TERMINAL_RETENTION_SECONDS
        expired = [
            sid for sid, record in _REGISTRY.records.items()
            if record.result is not None and record.completed_at is not None and record.completed_at < cutoff
        ]
        for subagent_id in expired:
            handle = _REGISTRY.records.pop(subagent_id).handle
            if handle.correlation_id:
                _REGISTRY.correlations.pop((handle.parent_session_id, handle.correlation_id), None)

    def _run(self, record: _Record, goal: str, parent: Any) -> None:
        with _REGISTRY.lock:
            if record.state is not SubagentState.CANCEL_REQUESTED:
                record.state = SubagentState.RUNNING
            record.started_at = record.updated_at = time.time()
        try:
            from tools.delegate_tool import _run_child_lifecycle
            raw = _run_child_lifecycle(0, goal, record.agent, parent)
            is_dict = isinstance(raw, dict)
            raw = raw if is_dict else {}
            status = str(raw.get("status", "error"))
            if status == "interrupted":
                state = SubagentState.CANCELLED if record.state == SubagentState.CANCEL_REQUESTED else SubagentState.INTERRUPTED
            else:
                state = SubagentState.SUCCEEDED if status == "completed" else SubagentState.FAILED
            fields: dict[str, Any] = dict(
                summary=_clip(raw.get("summary")), error_message=_clip(raw.get("error") or None),
                error_classification=None if state == SubagentState.SUCCEEDED else status.upper(),
                usage_metadata={"api_calls": raw.get("api_calls", 0)} if is_dict else {},
                tool_execution_summary={"duration_seconds": raw.get("duration_seconds", 0)} if is_dict else {},
            )
        except Exception as exc:
            state = SubagentState.FAILED
            fields = dict(error_classification=type(exc).__name__, error_message=_clip(exc))
        result = SubagentResult(record.handle, state, True, started_at=record.started_at, completed_at=time.time(), **fields)
        payload = dataclasses.asdict(result)
        payload.pop("result_hash", None)
        result = dataclasses.replace(result, result_hash=hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest())
        with _REGISTRY.lock:
            record.agent, record.result, record.state = None, result, result.terminal_state
            record.completed_at = record.updated_at = result.completed_at

    @staticmethod
    def _capability(subagent_id: str, parent_session_id: Optional[str], created_at: float) -> str:
        value = f"{subagent_id}|{parent_session_id or ''}|{created_at:.6f}".encode()
        return hmac.new(_SECRET, value, hashlib.sha256).hexdigest()

    @staticmethod
    def _validate_request(request: SubagentLaunchRequest, parent: Any) -> None:
        for rejected, message in _REQUEST_REJECTIONS:
            if rejected(request):
                raise SubagentLifecycleError(message)
        try:
            metadata_bytes = len(json.dumps(dict(request.metadata), sort_keys=True).encode())
        except (TypeError, ValueError) as exc:
            raise SubagentLifecycleError("metadata must be JSON-serializable.") from exc
        if metadata_bytes > _MAX_METADATA_BYTES:
            raise SubagentLifecycleError("metadata exceeds 8192 bytes.")
        if not request.allowed_toolsets:
            return
        from toolsets import TOOLSETS
        unknown = set(request.allowed_toolsets) - set(TOOLSETS)
        if unknown:
            raise SubagentLifecycleError(f"Unknown toolsets: {', '.join(sorted(unknown))}.")
        enabled = getattr(parent, "enabled_toolsets", None)
        if enabled is not None and not set(request.allowed_toolsets).issubset(set(enabled)):
            raise SubagentLifecycleError("Requested toolsets would broaden parent permissions.")
