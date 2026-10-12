"""Constructor-owned finite CONTRACT/PURE child; never a warm/cold promotion.

Trusted lifecycle commits the binding and supplies a local fail-closed guard.
Only retained immutable assignment input and actual previous outputs are read.
No provider/client/tool inheritance, middleware, observer or conversation loop.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import inspect
from uuid import uuid4

from agent.cold_admission import ColdAdmissionDenied, ColdState
from omnis_hermes.managed_admission_contract import canonical, ref, validate_release
from omnis_hermes.native_preparation_contract import loads
from omnis_hermes.prompt_bundle import expanded_payload
from omnis_hermes import contract_method as method


@dataclass(frozen=True)
class ContractAdmission:
    parent: object
    assignment: bytes


@dataclass
class ContractState:
    session_id: str
    native_id: str
    parent_session_id: str
    parent: object
    assignment: bytes
    manifest: bytes
    deadline: str
    closed: bool = False
    binding: bytes | None = None
    terminal: str | None = None


CONTRACT_READABLE = frozenset(
    {
        "_contract_state",
        "session_id",
        "_subagent_id",
        "_parent_session_id",
        "_delegate_role",
        "_delegate_depth",
        "provider",
        "model",
        "enabled_toolsets",
        "tools",
        "run_contract",
        "close",
        "__class__",
        "__dict__",
        "__weakref__",
    }
)


def initialize_contract(agent, admission, kwargs):
    if type(admission) is not ContractAdmission:
        raise ColdAdmissionDenied("Unrecognized CONTRACT admission")
    defaults = inspect.signature(type(agent).__init__).parameters
    if any(value != defaults[key].default for key, value in kwargs.items()):
        raise ColdAdmissionDenied("CONTRACT admission cannot carry warm options")
    parent = admission.parent
    if type(parent) is not type(agent):
        raise ColdAdmissionDenied("Native parent required")
    cold = object.__getattribute__(parent, "__dict__").get("_cold_state")
    if (
        type(cold) is not ColdState
        or cold.closed
        or cold.parent_session_id is not None
        or cold.native_id != parent._subagent_id
        or cold.session_id != parent.session_id
    ):
        raise ColdAdmissionDenied("Live cold root required")
    brief, _, _ = method.assignment(admission.assignment)  # before any identity allocation
    manifest = canonical(loads(admission.assignment, 32768)["manifest"])
    state = ContractState(
        str(uuid4()),
        str(uuid4()),
        cold.session_id,
        parent,
        admission.assignment,
        manifest,
        brief["payload"]["deadline"],
    )
    object.__getattribute__(agent, "__dict__").update(
        _contract_state=state,
        session_id=state.session_id,
        _subagent_id=state.native_id,
        _parent_session_id=state.parent_session_id,
        _delegate_role="leaf",
        _delegate_depth=1,
        provider=None,
        model=None,
        tools=(),
        enabled_toolsets=(),
    )


class BoundContractTools:
    """Ephemeral scope owned by one real child execution, never registered stock tools."""

    def __init__(self, agent, binding, guard):
        self.agent, self.state, self.binding, self.guard = (
            agent,
            agent._contract_state,
            binding,
            guard,
        )
        self._guard()  # no method-material unpacking before the live native guard
        self.brief, self.bound, self.material = method.assignment(self.state.assignment)
        stage = loads(self.state.assignment, 65536)  # validated before bundle expansion
        self.prompt_bundle = expanded_payload(
            stage["compositions"][0]["payload"], stage.get("record_pool")
        )["prompt_bundle"]
        self.original_ref = ref(self.material["input"])
        self.receipts, self.artifacts = [], []
        self.read = False

    def _guard(self):
        # Do not swallow an exception or interpret a falsey observer as approval.
        if self.guard() is not True:
            raise ColdAdmissionDenied("CONTRACT guard refused")
        state, agent = self.state, self.agent
        parent_state = object.__getattribute__(state.parent, "__dict__").get("_cold_state")
        if (
            state.closed
            or state.binding != self.binding
            or state.terminal is not None
            or agent._contract_state is not state
            or agent._subagent_id != state.native_id
            or agent.session_id != state.session_id
            or agent._parent_session_id != state.parent_session_id
            or type(parent_state) is not ColdState
            or parent_state.closed
            or state.parent.session_id != state.parent_session_id
            or parent_state.session_id != state.parent_session_id
            or datetime.now(timezone.utc) >= datetime.fromisoformat(state.deadline)
        ):
            raise ColdAdmissionDenied("CONTRACT lineage/deadline unavailable")

    def _bounded(self, extra=()):
        maximum = min(32768, self.brief["payload"]["limits"]["max_output_bytes"])
        if len(canonical([*self.receipts, *self.artifacts, *extra])) > maximum:
            raise ColdAdmissionDenied("CONTRACT aggregate output exceeds bound")

    def _receipt(self, operation, step, inputs, output):
        receipt = method.record(
            "contract-tool-receipt",
            {
                "header": self.brief["payload"]["header"],
                "binding_ref": ref(loads(self.binding, 32768)),
                "native_child_id": self.state.native_id,
                "native_session_id": self.state.session_id,
                "sequence": len(self.receipts),
                "operation": operation,
                "step_id": None if step is None else step["id"],
                "action_definition_ref": None if step is None else step["action_definition_ref"],
                "input_refs": inputs,
                "output_ref": output,
            },
        )
        self._bounded([receipt])
        self.receipts.append(receipt)

    def read_input(self, requested_ref):
        self._guard()  # before the real bound input access below
        if requested_ref != self.original_ref or self.read:
            raise ColdAdmissionDenied("CONTRACT input scope mismatch")
        value = self._read_bound_input()
        self._receipt("READ_INPUT", None, [self.original_ref], self.original_ref)
        self.read = True
        return value

    def _read_bound_input(self):
        return loads(canonical(self.material["input"]), 8192)

    def pure_action(self, step_id, action_definition_ref, input_refs):
        self._guard()  # before any previous-output read or handler
        steps = self.bound["payload"]["resolved_procedure"]["probe"]
        index = len(self.artifacts)
        if not self.read or index >= len(steps):
            raise ColdAdmissionDenied("CONTRACT step unavailable")
        step = steps[index]
        expected = [self.original_ref] if index == 0 else [ref(self.artifacts[-1])]
        if (
            type(step_id) is not str
            or step_id != step["id"]
            or action_definition_ref != step["action_definition_ref"]
            or input_refs != expected
        ):
            raise ColdAdmissionDenied("CONTRACT exact step/ref mismatch")
        (binding,) = step["input_bindings"]
        if index == 0:
            if binding["source_ref"] != self.original_ref:
                raise ColdAdmissionDenied("CONTRACT bound slot mismatch")
            previous = self.material["input"]["payload"]["value"]
        else:
            source = binding["source_ref"]
            if source != {
                "kind": "STEP_OUTPUT",
                "step_id": steps[index - 1]["id"],
                "output_name": binding["name"],
            }:
                raise ColdAdmissionDenied("CONTRACT StepOutput mismatch")
            previous = self.artifacts[-1]["payload"]["value"]
        actual_input = {binding["name"]: previous[binding["name"]]}
        self._guard()  # fail closed immediately before the installed PURE handler
        output = method.run_handler(method.STEP_HANDLERS[step_id], actual_input)
        method.validate_value(method.OUTPUT_SCHEMAS[step_id], output)
        artifact = method.record(
            "contract-artifact",
            {
                "header": self.brief["payload"]["header"],
                "schema_ref": step["output_schema_ref"],
                "value": output,
            },
        )
        self._bounded([artifact])
        self.artifacts.append(artifact)
        self._receipt("PURE_ACTION", step, expected, ref(artifact))
        return ref(artifact)


def run_contract(agent, binding, guard):
    state = agent._contract_state
    if (
        type(state) is not ContractState
        or state.closed
        or state.binding is not None
        or type(binding) is not bytes
        or not callable(guard)
    ):
        raise ColdAdmissionDenied("CONTRACT execution unavailable")
    # Constructor-owned source and native identity, not a task ID in JSON goal.
    manifest = loads(state.manifest, 32768)
    bound = loads(binding, 32768)
    release = {
        "protocol": "omnis-managed-admission-v4",
        "ticket": bound["payload"]["ticket"],
        "manifest_ref": ref(manifest),
        "binding": bound,
    }
    validate_release(release)
    body = bound["payload"]
    (entry,) = body["entries"]
    expected = {k: v for k, v in manifest["payload"]["entries"][0].items() if k != "goal"}
    expected.update(native_child_id=state.native_id, native_session_id=state.session_id)
    if (
        canonical(bound) != binding
        or entry != expected
        or body["run_id"] != manifest["payload"]["run_id"]
        or body["native_root_id"] != state.parent._subagent_id
    ):
        raise ColdAdmissionDenied("CONTRACT native binding mismatch")
    state.binding = binding  # attempted/partial execution can never be repeated
    try:
        tools = BoundContractTools(agent, binding, guard)
        original = tools.read_input(tools.original_ref)
        previous_ref = tools.original_ref
        for step in tools.bound["payload"]["resolved_procedure"]["probe"]:
            previous_ref = tools.pure_action(
                step["id"], step["action_definition_ref"], [previous_ref]
            )
        tools._guard()
        result = method.task_result(
            tools.brief, tools.bound, original, tools.receipts, tools.artifacts,
            prompt_bundle=tools.prompt_bundle,
        )
        tools._bounded([result])
        execution = {
            "native_child_id": state.native_id,
            "native_session_id": state.session_id,
            "brief_ref": ref(tools.brief),
            "records": [result, *tools.receipts, *tools.artifacts],
        }
        if len(canonical(execution)) > 32768:
            raise ColdAdmissionDenied("CONTRACT native result exceeds bound")
        state.terminal = "SUCCEEDED"
        return execution
    except BaseException:
        state.terminal = "UNKNOWN"
        raise
