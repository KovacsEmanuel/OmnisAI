"""Private RPC entry for the reviewed managed admission extension.

Only reachable through the fixed inert native stdin peer. No tool registration,
plugin hooks, user goals, observers or skills can invoke this owner surface.
"""
import threading

_ROOT = None
_SERVICE = None
_LOCK = threading.RLock()
_INITIALIZATIONS = {}
_MAX_INITIALIZATIONS = 32


def _observed_result(payload, agent):
    from agent.agent_init import observe_owned_core
    from omnis_hermes.managed_admission_contract import canonical, initialization_result

    actual = agent._owned_initialization.payload()
    if canonical({k: v for k, v in actual.items() if k != "mode"}) != canonical({k: v for k, v in payload.items() if k != "mode"}):
        raise ValueError("Native core belongs to a different initialization")
    return initialization_result(payload, observation=observe_owned_core(agent),
        native_session_id=agent.session_id, native_instance_id=agent._native_instance_id)


def _initialize(params):
    from omnis_hermes.managed_admission_contract import (
        OwnedInitialization, canonical, initialization_result, validate_initialization,
    )
    p = validate_initialization(params)  # before any native import/allocation
    key = p["initialization_id"]
    bound = canonical({k: v for k, v in p.items() if k != "mode"})
    with _LOCK:
        entry = _INITIALIZATIONS.get(key)
        if entry is not None:
            if entry["binding"] != bound:
                raise ValueError("Initialization replay conflict")
            agent = entry["agent"]
            if agent is None or agent.__dict__.get("_owned_core_closed") is True:
                return initialization_result(p)
            return _observed_result(p, agent)  # every read observes the live core
        if p["mode"] == "STATUS":
            return initialization_result(p)  # no import, constructor or reservation
        if len(_INITIALIZATIONS) >= _MAX_INITIALIZATIONS:
            raise ValueError("Initialization registry full")
        # A retained pending/failure marker makes uncertain CREATE non-repeatable.
        entry = {"binding": bound, "agent": None}
        _INITIALIZATIONS[key] = entry
        try:
            from run_agent import AIAgent
            agent = AIAgent(owned_initialization=OwnedInitialization(canonical(p)))
            result = _observed_result(p, agent)
        except Exception:
            raise ValueError("Native configuration initialization incomplete") from None
        entry["agent"] = agent
        return result


def dispatch(method, params):
    global _ROOT, _SERVICE
    from omnis_hermes.managed_admission_contract import RPC, validate_stage, validate_status, validate_release, validate_model_preflight
    if method == RPC["task_model_initialize"]:
        return _initialize(params)
    if method not in RPC.values():
        raise ValueError("Unknown managed operation")
    {RPC["task_stage"]: validate_stage, RPC["task_release"]: validate_release,
     RPC["task_status"]: validate_status, RPC["task_model_preflight"]: validate_model_preflight}[method](params)
    with _LOCK:
        if _SERVICE is None:
            if method != RPC["task_stage"]:
                raise ValueError("No managed stage")
            from run_agent import AIAgent
            from agent.cold_admission import ColdAdmission
            from agent.subagent_lifecycle import SubagentLifecycleService
            _ROOT = AIAgent(cold_admission=ColdAdmission())
            _SERVICE = SubagentLifecycleService(lambda: _ROOT)
        return {RPC["task_stage"]: _SERVICE.stage, RPC["task_release"]: _SERVICE.release,
                RPC["task_status"]: _SERVICE.readback, RPC["task_model_preflight"]: _SERVICE.model_preflight}[method](params)
