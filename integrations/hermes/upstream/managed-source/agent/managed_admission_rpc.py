"""Private RPC entry for the reviewed managed admission extension.

Only reachable through the fixed inert native stdin peer. No tool registration,
plugin hooks, user goals, observers or skills can invoke this owner surface.
"""
import threading

_ROOT = None
_SERVICE = None
_LOCK = threading.RLock()


def dispatch(method, params):
    global _ROOT, _SERVICE
    from omnis_hermes.managed_admission_contract import RPC, validate_stage, validate_status, validate_release, validate_model_preflight
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
