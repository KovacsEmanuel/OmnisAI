"""Finite FULL_PINNED_SOURCE probe, NOT installed/OCI/provider proof.

Real AIAgent and registry; exact source overlay, no native substitutions. CLI:
source overlay adapter fresh-home. All network/process/credential sinks denied.
"""

import importlib.abc
import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from uuid import uuid4


def bootstrap():
    source, overlay, adapter, home = map(lambda x: Path(x).resolve(), sys.argv[1:5])
    if not home.is_dir() or any(home.iterdir()):
        raise ValueError("Fresh private home required")
    os.environ.clear()
    os.environ.update(
        HOME=str(home),
        HERMES_HOME=str(home / "hermes"),
        TMPDIR=str(home),
        HERMES_OMNIS_INERT="1",
        HERMES_DISABLE_LAZY_INSTALLS="1",
        HERMES_SKIP_NODE_BOOTSTRAP="1",
        PYTHONDONTWRITEBYTECODE="1",
    )
    effects = []

    def audit(event, args):
        denied = event in {"socket.connect", "subprocess.Popen", "os.system"}
        if event == "open" and isinstance(args[0], (str, bytes)):
            denied |= os.fsdecode(args[0]).endswith((".env", "auth.json", "credentials.json"))
        if denied:
            effects.append(event)
            raise RuntimeError("Forbidden source probe effect: " + event)

    sys.addaudithook(audit)

    class Overlay(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            relative = Path(*fullname.split("."))
            package = overlay / relative / "__init__.py"
            if package.is_file():
                return importlib.util.spec_from_file_location(
                    fullname,
                    package,
                    submodule_search_locations=[str(package.parent), str(source / relative)],
                )
            module = (overlay / relative).with_suffix(".py")
            if module.is_file():
                return importlib.util.spec_from_file_location(fullname, module)

    sys.meta_path.insert(0, Overlay())
    sys.path[:0] = [str(source), str(adapter), str(Path(__file__).parent)]
    import agent

    agent.__path__.insert(0, str(overlay / "agent"))
    return effects


class ContractNative(unittest.TestCase):
    def setUp(self):
        from agent.cold_admission import ColdAdmission
        from agent.subagent_lifecycle import SubagentLifecycleService
        from run_agent import AIAgent
        from test_contract_method import method_fixture

        self.attempts = []

        def observe(frame, event, arg):
            if event == "call" and frame.f_code.co_name in {
                "init_agent",
                "_resolve_child_runtime",
                "run_conversation",
                "handle_function_call",
                "_init_client",
                "_resolve_runtime",
                "load_credential_pool",
                "get_api_key",
            }:
                self.attempts.append(frame.f_code.co_name)
                raise AssertionError("Forbidden native sink")

        self.previous_profile = sys.getprofile()
        sys.setprofile(observe)
        self.root = AIAgent(cold_admission=ColdAdmission())
        self.service = SubagentLifecycleService(lambda: self.root)
        self.payload = method_fixture()
        self.children = []

    def tearDown(self):
        for child in self.children:
            child.close()
        self.root.close()
        sys.setprofile(self.previous_profile)
        self.assertEqual(self.attempts, [])

    def compact(self):
        from composition_fixture import ref, seal
        from omnis_hermes.native_preparation_contract import canonical

        composition = self.payload["compositions"][0]
        body = composition["payload"]
        sections = json.loads(body["text"])
        pool = [
            body["prompt_bundle"],
            *[s["record"] for s in sections[:4]],
            sections[4]["context"],
            sections[4]["input"],
        ]
        compact_sections = [
            {"section": s["section"], "record_ref": ref(s["record"])} for s in sections[:4]
        ]
        compact_sections.append(
            {
                **{k: v for k, v in sections[4].items() if k not in {"context", "input"}},
                "context_ref": ref(pool[5]),
                "input_ref": ref(pool[6]),
            }
        )
        composition["payload"] = {
            **{k: v for k, v in body.items() if k not in {"prompt_bundle", "text"}},
            "format": "record-refs-v1",
            "prompt_bundle_ref": ref(pool[0]),
            "sections": [*compact_sections, *sections[5:]],
        }
        seal(composition)
        self.payload["record_pool"] = pool
        self.payload["manifest"]["payload"]["entries"][0]["composition_ref"] = ref(composition)
        seal(self.payload["manifest"])
        return canonical(sections)

    def test_compact_pool_is_lossless_in_real_native_child(self):
        from omnis_hermes.contract_method import assignment
        from omnis_hermes.native_preparation_contract import canonical

        expected = self.compact()
        brief, bound, material = assignment(canonical(self.payload))
        sections = json.loads(expected)
        self.assertEqual(
            (brief, bound, material), (sections[2]["record"], sections[3]["record"], sections[4])
        )
        self.stage()
        final = self.service.release(self.release)
        self.assertEqual(final["status"], "SUCCEEDED")
        self.assertEqual(final, self.service.release(self.release))

    def test_compact_bad_pool_refuses_before_real_native_constructor(self):
        from copy import deepcopy

        from composition_fixture import seal
        from run_agent import AIAgent

        self.compact()
        original = deepcopy(self.payload)
        constructions = []
        previous = sys.getprofile()

        def observe(frame, event, arg):
            if event == "call" and (
                frame.f_code.co_name in {"initialize_contract", "_read_bound_input", "run_handler"}
                or (
                    frame.f_code.co_name == "__init__"
                    and type(frame.f_locals.get("self")) is AIAgent
                )
            ):
                constructions.append(frame.f_code.co_name)

        try:
            sys.setprofile(observe)
            for attack in (
                "missing",
                "duplicate",
                "foreign",
                "altered",
                "resealed",
                "bool-ref",
                "extra",
                "foreign-header",
            ):
                self.payload = deepcopy(original)
                pool = self.payload["record_pool"]
                composition = self.payload["compositions"][0]
                if attack == "missing":
                    pool.pop()
                elif attack == "duplicate":
                    pool.append(deepcopy(pool[-1]))
                elif attack == "foreign":
                    pool[-1]["id"] = str(uuid4())
                    seal(pool[-1])
                elif attack in ("altered", "resealed"):
                    pool[-1]["payload"]["value"] = {"capture": "changed"}
                    if attack == "resealed":
                        seal(pool[-1])
                elif attack == "bool-ref":
                    composition["payload"]["sections"][0]["record_ref"]["revision"] = True
                    seal(composition)
                elif attack == "extra":
                    pool.reverse()
                else:
                    self.payload["manifest"]["payload"]["entries"][0]["attempt_id"] = str(uuid4())
                    seal(self.payload["manifest"])
                with self.assertRaises(ValueError):
                    self.service.stage(self.payload)
            self.assertEqual(constructions, [])
        finally:
            sys.setprofile(previous)

    def test_missing_compact_pin_refuses_stage_and_real_constructor_before_identity(self):
        from copy import deepcopy

        from agent.contract_execution import ContractAdmission
        from composition_fixture import ref, seal
        from omnis_hermes.managed_admission_contract import canonical
        from run_agent import AIAgent

        self.compact()
        positive = AIAgent(
            contract_admission=ContractAdmission(self.root, canonical(self.payload), 0)
        )
        self.children.append(positive)
        self.assertIs(type(positive), AIAgent)
        self.assertIsNone(positive.provider)
        self.assertEqual(positive.tools, ())
        self.assertIn("_contract_state", object.__getattribute__(positive, "__dict__"))
        bad = deepcopy(self.payload)
        bundle = bad["record_pool"][0]
        del bundle["payload"]["composer_revision"]
        seal(bundle)
        composition = bad["compositions"][0]
        composition["payload"]["prompt_bundle_ref"] = ref(bundle)
        seal(composition)
        bad["manifest"]["payload"]["entries"][0]["composition_ref"] = ref(composition)
        seal(bad["manifest"])
        candidate = object.__new__(AIAgent)
        calls = []
        previous = sys.getprofile()

        def observe(frame, event, arg):
            if event == "call" and frame.f_code.co_name in {
                "initialize_contract",
                "assignment",
                "_read_bound_input",
                "run_handler",
            }:
                calls.append(frame.f_code.co_name)
            if previous:
                previous(frame, event, arg)

        try:
            sys.setprofile(observe)
            with self.assertRaisesRegex(ValueError, "Invalid native preparation"):
                self.service.stage(bad)
            self.assertEqual(calls, [])
            with self.assertRaisesRegex(ValueError, "Invalid native preparation"):
                AIAgent.__init__(
                    candidate, contract_admission=ContractAdmission(self.root, canonical(bad), 0)
                )
            self.assertEqual(calls, ["initialize_contract", "assignment"])
            self.assertEqual(object.__getattribute__(candidate, "__dict__"), {})
        finally:
            sys.setprofile(previous)

    def stage(self):
        from agent.subagent_lifecycle import _REGISTRY
        from composition_fixture import record

        staged = self.service.stage(self.payload)
        self.status = {k: staged[k] for k in ("protocol", "ticket", "manifest_ref")}
        self.binding = record(
            "runtime-binding",
            {
                "runtime_boot": str(uuid4()),
                "run_id": self.payload["manifest"]["payload"]["run_id"],
                "ticket": staged["ticket"],
                "native_root_id": staged["native_root_id"],
                "entries": staged["entries"],
                "authority": {
                    "instance_id": str(uuid4()),
                    "owner": str(uuid4()),
                    "epoch": 1,
                    "generation": 0,
                },
            },
        )
        self.release = {**self.status, "binding": self.binding}
        self.record = _REGISTRY.records[staged["entries"][0]["native_child_id"]]
        self.child = self.record.agent
        self.children.append(self.child)
        return staged

    def test_capture_real_child_executes_only_after_binding_and_replays_terminal(self):
        from omnis_hermes.managed_admission_contract import ref, validate_response
        from run_agent import AIAgent

        self.stage()
        accesses = self.count_accesses()
        self.assertIs(type(self.child), AIAgent)
        self.assertTrue(
            callable(getattr(self.child, "run_contract", None)), "native method missing"
        )
        final = self.service.release(self.release)
        self.assertEqual(final["status"], "SUCCEEDED")
        self.assertEqual(final["reason"], "CONTRACT_PURE")
        self.assertEqual(validate_response(final), final)
        (execution,) = final["executions"]
        self.assertEqual(execution["native_child_id"], self.child._subagent_id)
        records = execution["records"]
        (result,) = [r for r in records if r["kind"] == "task-result"]
        receipts = [r for r in records if r["kind"] == "contract-tool-receipt"]
        artifacts = [r for r in records if r["kind"] == "contract-artifact"]
        self.assertEqual(len(receipts), 4)
        self.assertEqual(len(artifacts), 3)
        self.assertEqual([r["payload"]["sequence"] for r in receipts], list(range(4)))
        self.assertEqual(
            artifacts[-1]["payload"]["value"],
            {"surface_map": [{"path": "/c03", "methods": ["GET"], "operation_count": 1}]},
        )
        self.assertEqual(
            receipts[1]["payload"]["input_refs"], [receipts[0]["payload"]["output_ref"]]
        )
        for index in (2, 3):
            self.assertEqual(receipts[index]["payload"]["input_refs"], [ref(artifacts[index - 2])])
        self.assertEqual(
            result["payload"]["usage"],
            {"state": "KNOWN", "model_calls": 0, "target_actions": 0, "cost": "0"},
        )
        self.assertEqual(
            result["payload"]["method_results"][0]["basis_refs"], [ref(r) for r in receipts[1:]]
        )
        self.assertEqual(
            result["payload"]["method_results"][0]["artifact_refs"], [ref(artifacts[-1])]
        )
        self.assertEqual(self.service.release(self.release), final)
        self.assertEqual(self.service.readback(self.status), final)
        self.assertEqual(self.service.stage(self.payload), final)
        self.assertEqual(
            accesses, ["_read_bound_input", "run_handler", "run_handler", "run_handler"]
        )

    def test_records_two_steps_preserve_original_context_and_empty_records(self):
        from composition_fixture import ref
        from test_contract_method import method_fixture
        from test_prompt_bundle import reseal_graph

        for value in (
            {"records": []},
            {"records": [{"method": "GET", "path": "/records", "status": 200}]},
        ):
            self.payload = method_fixture(records=True, value=value)
            payload = self.payload["compositions"][0]["payload"]
            sections = json.loads(payload["text"])
            procedure = sections[3]["record"]["payload"]["resolved_procedure"]
            preserve = {
                "key": "preserve-input-context",
                "description": "Retain original records.",
                "required": False,
                "applies_if": [],
                "step_ids": ["normalize-operations"],
                "artifact_schema_refs": [procedure["input_schema_ref"]],
                "evidence_kinds": [],
            }
            procedure["method_requirements"].append(preserve)
            sections[2]["record"]["payload"]["method_plan"]["requirements"].append(
                {
                    "ref": {
                        "bound_procedure_ref": ref(sections[3]["record"]),
                        "requirement_key": preserve["key"],
                    },
                    "applicability": "APPLIES",
                    "applicability_basis_refs": [],
                    "required": False,
                }
            )
            reseal_graph(self.payload, sections, payload["prompt_bundle"])
            self.stage()
            final = self.service.release(self.release)
            records = final["executions"][0]["records"]
            self.assertEqual(len(records), 6)
            result = records[0]["payload"]
            original_ref = ref(sections[4]["input"])
            self.assertEqual(records[1]["payload"]["output_ref"], original_ref)
            self.assertEqual(result["consumed_input_refs"], [original_ref])
            self.assertEqual(result["method_results"][-1]["artifact_refs"], [original_ref])
            self.assertEqual(result["method_results"][-1]["basis_refs"], [ref(records[2])])
            self.assertEqual(result["method_results"][-1]["state"], "DONE")
            self.assertEqual(len(result["action_refs"]), 2)

    def count_accesses(self):
        from unittest.mock import patch

        from agent.contract_execution import BoundContractTools
        from omnis_hermes import contract_method

        accesses = []
        original_read = BoundContractTools._read_bound_input
        original_handler = contract_method.run_handler

        def read(tools):
            accesses.append("_read_bound_input")
            return original_read(tools)

        def handler(*args):
            accesses.append("run_handler")
            return original_handler(*args)

        for target, name, wrapper in (
            (BoundContractTools, "_read_bound_input", read),
            (contract_method, "run_handler", handler),
        ):
            observer = patch.object(target, name, wrapper)
            observer.start()
            self.addCleanup(observer.stop)
        return accesses

    def assert_indeterminate_no_retry(self, accesses):
        saved = list(accesses)
        for operation, payload in (
            (self.service.release, self.release),
            (self.service.readback, self.status),
            (self.service.stage, self.payload),
        ):
            with self.assertRaisesRegex(ValueError, "indeterminate"):
                operation(payload)
        self.assertEqual(accesses, saved)
        self.assertTrue(self.child._contract_state.closed)
        self.assertIsNone(self.record.agent)

    def test_guard_exception_latches_without_input_read_or_handler(self):
        from unittest.mock import patch

        self.stage()
        accesses = self.count_accesses()
        with patch.object(self.service, "_contract_guard", side_effect=RuntimeError("guard veto")):
            with self.assertRaisesRegex(RuntimeError, "guard veto"):
                self.service.release(self.release)
        self.assertEqual(accesses, [])
        self.assert_indeterminate_no_retry(accesses)

    def test_guard_exception_does_not_unpack_method_material(self):
        from unittest.mock import patch

        self.stage()
        entered = []
        previous = sys.getprofile()

        def observe(frame, event, arg):
            if event == "call" and frame.f_code.co_name == "assignment":
                entered.append("method-material")
            if previous:
                previous(frame, event, arg)

        sys.setprofile(observe)
        try:
            with patch.object(
                self.service, "_contract_guard", side_effect=RuntimeError("guard veto")
            ):
                with self.assertRaisesRegex(RuntimeError, "guard veto"):
                    self.service.release(self.release)
        finally:
            sys.setprofile(previous)
        self.assertEqual(entered, [], "method material unpacked before guard approval")

    def test_false_guard_is_not_approval(self):
        from unittest.mock import patch

        self.stage()
        accesses = self.count_accesses()
        with patch.object(self.service, "_contract_guard", return_value=None):
            with self.assertRaises(ValueError):
                self.service.release(self.release)
        self.assertEqual(accesses, [])
        self.assert_indeterminate_no_retry(accesses)

    def test_late_guard_exception_prevents_handler_after_input_read(self):
        from unittest.mock import patch

        self.stage()
        accesses = self.count_accesses()
        actual = self.service._contract_guard
        calls = []

        def guard(*args):
            calls.append(1)
            if len(calls) == 3:
                raise RuntimeError("pre-handler veto")
            return actual(*args)

        with patch.object(self.service, "_contract_guard", side_effect=guard):
            with self.assertRaisesRegex(RuntimeError, "pre-handler veto"):
                self.service.release(self.release)
        self.assertEqual(accesses, ["_read_bound_input"])
        self.assert_indeterminate_no_retry(accesses)

    def test_wrong_read_ref_refuses_before_real_access(self):
        from unittest.mock import patch

        from agent.contract_execution import BoundContractTools

        self.stage()
        accesses = self.count_accesses()
        actual = BoundContractTools.read_input

        def wrong(scope, requested):
            return actual(scope, {**requested, "digest": "f" * 64})

        with patch.object(BoundContractTools, "read_input", wrong):
            with self.assertRaisesRegex(ValueError, "scope mismatch"):
                self.service.release(self.release)
        self.assertEqual(accesses, [])
        self.assert_indeterminate_no_retry(accesses)

    def test_wrong_action_ref_refuses_before_real_handler(self):
        from unittest.mock import patch

        from agent.contract_execution import BoundContractTools

        self.stage()
        accesses = self.count_accesses()
        actual = BoundContractTools.pure_action

        def wrong(scope, step_id, action_ref, inputs):
            return actual(scope, step_id, {**action_ref, "digest": "f" * 64}, inputs)

        with patch.object(BoundContractTools, "pure_action", wrong):
            with self.assertRaisesRegex(ValueError, "step/ref mismatch"):
                self.service.release(self.release)
        self.assertEqual(accesses, ["_read_bound_input"])
        self.assert_indeterminate_no_retry(accesses)

    def test_different_live_root_or_child_lineage_refuses_before_access(self):
        from agent.cold_admission import ColdAdmission
        from run_agent import AIAgent

        self.stage()
        accesses = self.count_accesses()
        original = self.root
        self.root = AIAgent(cold_admission=ColdAdmission())
        self.children.append(original)
        with self.assertRaises(ValueError):
            self.service.release(self.release)
        self.assertEqual(accesses, [])
        self.root.close()
        self.root = original
        self.child.session_id = "wrong-native-session"
        with self.assertRaises(ValueError):
            self.service.release(self.release)
        self.assertEqual(accesses, [])

    def test_native_output_limit_refuses_without_truncation_or_retry(self):
        from test_prompt_bundle import reseal_graph

        payload = self.payload["compositions"][0]["payload"]
        sections = json.loads(payload["text"])
        sections[2]["record"]["payload"]["limits"]["max_output_bytes"] = 2048
        reseal_graph(self.payload, sections, payload["prompt_bundle"])
        self.stage()
        accesses = self.count_accesses()
        with self.assertRaisesRegex(ValueError, "output exceeds bound"):
            self.service.release(self.release)
        self.assert_indeterminate_no_retry(accesses)

    def test_binding_mismatch_refuses_before_access_and_preserves_pending_stage(self):
        from copy import deepcopy

        from composition_fixture import seal

        self.stage()
        accesses = self.count_accesses()
        for key in (
            "run_id",
            "native_root_id",
            "native_child_id",
            "native_session_id",
            "brief_ref",
            "composition_ref",
        ):
            wrong = deepcopy(self.release)
            body = wrong["binding"]["payload"]
            if key in ("run_id", "native_root_id"):
                body[key] = str(uuid4())
            elif key.endswith("_ref"):
                body["entries"][0][key]["digest"] = "f" * 64
            else:
                body["entries"][0][key] = str(uuid4())
            seal(wrong["binding"])
            with self.assertRaises(ValueError):
                self.service.release(wrong)
        self.assertEqual(accesses, [])
        self.assertEqual(self.service.readback(self.status)["status"], "STAGED")
        self.assertEqual(self.service.release(self.release)["status"], "SUCCEEDED")

    def test_expired_native_stage_refuses_without_access(self):
        self.stage()
        accesses = self.count_accesses()
        batch = self.service._cold_batches[self.payload["manifest"]["id"]]
        batch["expires"] = 0
        with self.assertRaises(ValueError):
            self.service.release(self.release)
        self.assertEqual(accesses, [])
        self.assertIsNone(batch["binding"])

    def test_existing_managed_rpc_dispatch_runs_same_v4_wire(self):
        from agent import managed_admission_rpc as rpc
        from composition_fixture import record
        from omnis_hermes.managed_admission_contract import validate_response

        self.assertIsNone(rpc._SERVICE)
        try:
            staged = rpc.dispatch("omnis.managed.stage", self.payload)
            status = {k: staged[k] for k in ("protocol", "ticket", "manifest_ref")}
            binding = record(
                "runtime-binding",
                {
                    "runtime_boot": str(uuid4()),
                    "run_id": self.payload["manifest"]["payload"]["run_id"],
                    "ticket": staged["ticket"],
                    "native_root_id": staged["native_root_id"],
                    "entries": staged["entries"],
                    "authority": {
                        "instance_id": str(uuid4()),
                        "owner": str(uuid4()),
                        "epoch": 1,
                        "generation": 0,
                    },
                },
            )
            final = rpc.dispatch("omnis.managed.release", {**status, "binding": binding})
            self.assertEqual(validate_response(final)["status"], "SUCCEEDED")
            self.assertEqual(rpc.dispatch("omnis.managed.status", status), final)
        finally:
            if rpc._ROOT is not None:
                rpc._ROOT.close()
            rpc._ROOT = rpc._SERVICE = None

    def test_native_contract_denies_stock_surfaces_and_constructor_dto(self):
        from agent.contract_execution import ContractAdmission
        from omnis_hermes.managed_admission_contract import canonical
        from run_agent import AIAgent

        self.stage()
        for name in (
            "run_conversation",
            "make_client",
            "_init_client",
            "execute_tool",
            "unknown_future_surface",
            "_cold_state",
        ):
            with self.assertRaises(ValueError):
                getattr(self.child, name)
        self.assertIsNone(self.child.provider)
        self.assertEqual(self.child.tools, ())
        for options in (
            {"contract_admission": {"assignment": canonical(self.payload)}},
            {
                "contract_admission": ContractAdmission(self.root, canonical(self.payload), 0),
                "model": "forbidden",
            },
        ):
            with self.assertRaises(ValueError):
                AIAgent(**options)


class Batch2Native(unittest.TestCase):
    """Full pinned SOURCE, real constructors/lifecycle/handlers; no DB claim."""

    def test_stage_and_index_denials_before_constructor(self):
        from copy import deepcopy
        from unittest.mock import patch

        from agent.cold_admission import ColdAdmission
        from agent.contract_execution import ContractAdmission
        from agent.subagent_lifecycle import SubagentLifecycleService
        from omnis_hermes import contract_method as method
        from omnis_hermes.managed_admission_contract import canonical
        from run_agent import AIAgent

        root = AIAgent(cold_admission=ColdAdmission())
        service = SubagentLifecycleService(lambda root=root: root)
        original = AIAgent.__init__
        called = []

        def constructor(agent, *args, **kwargs):
            called.append(True)
            return original(agent, *args, **kwargs)

        try:
            for attack in (
                "missing",
                "extra",
                "duplicate",
                "shadow",
                "kind",
                "revision-bool",
                "digest",
                "ref",
                "overflow",
                "second-task",
                "second-attempt",
                "second-brief",
            ):
                with self.subTest(attack=attack):
                    bad = deepcopy(BATCH2["stage"])
                    pool = bad["record_pool"]
                    if attack == "missing":
                        pool.pop()
                    elif attack == "extra":
                        pool.append(method.record("prompt-content", {"text": "extra"}))
                    elif attack == "duplicate":
                        pool.append(deepcopy(pool[0]))
                    elif attack == "shadow":
                        shadow = deepcopy(pool[0])
                        shadow["payload"]["provenance"] = []
                        pool.append(shadow)
                    elif attack == "kind":
                        pool[-1]["kind"] = "schema"
                    elif attack == "revision-bool":
                        pool[-1]["revision"] = True
                    elif attack == "digest":
                        pool[-1]["digest"] = "0" * 64
                    elif attack == "ref":
                        bad["compositions"][1]["payload"]["sections"][2]["record_ref"][
                            "revision"
                        ] = True
                    elif attack == "overflow":
                        pool[-1]["payload"]["padding"] = "x" * 32768
                    elif attack == "second-brief":
                        from omnis_hermes.native_preparation_contract import digest
                        from omnis_hermes.prompt_bundle import composition_pool, expanded_payload

                        composition = bad["compositions"][1]
                        pin = composition["payload"]["sections"][2]["record_ref"]
                        brief = next(r for r in pool if r["id"] == pin["id"])
                        brief["payload"]["limits"]["max_actions"] = 1
                        brief["digest"] = digest(
                            canonical({k: v for k, v in brief.items() if k != "digest"})
                        )
                        from omnis_hermes.managed_admission_contract import ref

                        composition["payload"]["sections"][2]["record_ref"] = ref(brief)
                        bad["manifest"]["payload"]["entries"][1]["brief_ref"] = ref(brief)
                        expanded = expanded_payload(
                            composition["payload"], composition_pool(composition["payload"], pool)
                        )
                        raw = expanded["text"].encode()
                        composition["payload"].update(
                            text_digest=digest(raw), byte_count=len(raw), token_upper_bound=len(raw)
                        )
                    else:
                        field = "task_id" if attack == "second-task" else "attempt_id"
                        bad["manifest"]["payload"]["entries"][1][field] = bad["manifest"][
                            "payload"
                        ]["entries"][0][field]
                    from omnis_hermes.managed_admission_contract import ref
                    from omnis_hermes.native_preparation_contract import digest

                    if attack not in {"digest", "kind", "ref"}:
                        for item in pool:
                            item["digest"] = digest(
                                canonical({k: v for k, v in item.items() if k != "digest"})
                            )
                    for i, composition in enumerate(bad["compositions"]):
                        composition["digest"] = digest(
                            canonical({k: v for k, v in composition.items() if k != "digest"})
                        )
                        bad["manifest"]["payload"]["entries"][i]["composition_ref"] = ref(
                            composition
                        )
                    bad["manifest"]["digest"] = digest(
                        canonical({k: v for k, v in bad["manifest"].items() if k != "digest"})
                    )
                    with (
                        patch.object(AIAgent, "__init__", constructor),
                        self.assertRaises(ValueError),
                    ):
                        service.stage(bad)
                    self.assertEqual(called, [])
            for index in (None, True, False, 0.0, 1.0, -1, 2):
                with self.subTest(index=index), self.assertRaises(ValueError):
                    method.assignment(canonical(BATCH2["stage"]), index)
            for index in (True, 1.0, -1, 2):
                with self.assertRaises(ValueError):
                    AIAgent(
                        contract_admission=ContractAdmission(
                            root, canonical(BATCH2["stage"]), index
                        )
                    )
        finally:
            root.close()

    def test_guard_failure_and_partial_submit_are_indeterminate(self):
        from concurrent.futures import CancelledError
        from unittest.mock import patch
        from uuid import uuid4

        from agent import subagent_lifecycle as lifecycle
        from agent.cold_admission import ColdAdmission
        from omnis_hermes import contract_method as method
        from run_agent import AIAgent

        for failure in ("false", "raise", "partial-submit"):
            root = AIAgent(cold_admission=ColdAdmission())
            service = lifecycle.SubagentLifecycleService(lambda root=root: root)
            stage = service.stage(BATCH2["stage"])
            binding = method.record(
                "runtime-binding",
                {
                    "runtime_boot": str(uuid4()),
                    "run_id": BATCH2["stage"]["manifest"]["payload"]["run_id"],
                    "ticket": stage["ticket"],
                    "native_root_id": stage["native_root_id"],
                    "entries": stage["entries"],
                    "authority": {
                        "instance_id": str(uuid4()),
                        "owner": str(uuid4()),
                        "epoch": 1,
                        "generation": 0,
                    },
                },
            )
            release = {
                "protocol": stage["protocol"],
                "manifest_ref": stage["manifest_ref"],
                "ticket": stage["ticket"],
                "binding": binding,
            }
            batch = service._cold_batches[stage["manifest_ref"]["id"]]
            children = [r.agent for r in batch["records"]]
            count = []
            actual_submit = lifecycle._EXECUTOR.submit

            def submit(*args, count=count, actual_submit=actual_submit):
                count.append(True)
                if len(count) == 2:
                    raise RuntimeError("SOURCE partial submit")
                return actual_submit(*args)

            def guard(*args, failure=failure):
                if failure == "raise":
                    raise RuntimeError("SOURCE guard failure")
                return False

            try:
                target, name, replacement = (
                    (lifecycle._EXECUTOR, "submit", submit)
                    if failure == "partial-submit"
                    else (service, "_contract_guard", guard)
                )
                with (
                    patch.object(target, name, replacement),
                    self.assertRaises((ValueError, RuntimeError)),
                ):
                    service.release(release)
                for record in batch["records"]:
                    if record.future is not None:
                        try:
                            record.future.result(timeout=2)
                        except (ValueError, RuntimeError, CancelledError):
                            pass
                self.assertTrue(batch["indeterminate"])
                self.assertTrue(
                    all(
                        r.state == lifecycle.SubagentState.UNKNOWN and r.result is None
                        for r in batch["records"]
                    )
                )
                self.assertTrue(all(c._contract_state.closed for c in children))
                with self.assertRaises(ValueError):
                    service.release(release)
            finally:
                root.close()

    def test_timeout_does_not_claim_worker_drain(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor, TimeoutError
        from unittest.mock import patch
        from uuid import uuid4

        from agent import subagent_lifecycle as lifecycle
        from agent.cold_admission import ColdAdmission
        from omnis_hermes import contract_method as method
        from run_agent import AIAgent

        root = AIAgent(cold_admission=ColdAdmission())
        service = lifecycle.SubagentLifecycleService(lambda root=root: root)
        stage = service.stage(BATCH2["stage"])
        binding = method.record(
            "runtime-binding",
            {
                "runtime_boot": str(uuid4()),
                "run_id": BATCH2["stage"]["manifest"]["payload"]["run_id"],
                "ticket": stage["ticket"],
                "native_root_id": stage["native_root_id"],
                "entries": stage["entries"],
                "authority": {
                    "instance_id": str(uuid4()),
                    "owner": str(uuid4()),
                    "epoch": 1,
                    "generation": 0,
                },
            },
        )
        release = {
            "protocol": stage["protocol"],
            "manifest_ref": stage["manifest_ref"],
            "ticket": stage["ticket"],
            "binding": binding,
        }
        batch = service._cold_batches[stage["manifest_ref"]["id"]]
        children = [r.agent for r in batch["records"]]
        entered, finish = threading.Barrier(3), threading.Event()
        actual = method.run_handler

        def held(name, value):
            entered.wait(timeout=1)
            if not finish.wait(timeout=5):
                raise AssertionError("SOURCE settlement missing")
            return actual(name, value)

        try:
            with (
                ThreadPoolExecutor(max_workers=1) as executor,
                patch.object(method, "run_handler", held),
            ):
                pending = executor.submit(service.release, release)
                try:
                    entered.wait(timeout=2)
                    with self.assertRaises(TimeoutError):
                        pending.result(timeout=4)
                    self.assertTrue(batch["indeterminate"])
                    self.assertTrue(all(not r.future.done() for r in batch["records"]))
                    self.assertTrue(
                        all(
                            r.state == lifecycle.SubagentState.UNKNOWN and r.result is None
                            for r in batch["records"]
                        )
                    )
                    with self.assertRaises(ValueError):
                        service.release(release)
                finally:
                    finish.set()
                for record in batch["records"]:
                    with self.assertRaises(ValueError):
                        record.future.result(timeout=2)
                self.assertTrue(all(c._contract_state.closed for c in children))
                self.assertTrue(all(r.agent is None for r in batch["records"]))
        finally:
            finish.set()
            root.close()

    def test_complete_batch(self):
        import threading
        import time
        from unittest.mock import patch

        from agent.cold_admission import ColdAdmission
        from agent.contract_execution import BoundContractTools
        from agent.subagent_lifecycle import _REGISTRY, SubagentLifecycleService, SubagentState
        from omnis_hermes import contract_method as method
        from omnis_hermes.managed_admission_contract import canonical, ref, validate_response
        from run_agent import AIAgent

        stage = BATCH2["stage"]
        root = AIAgent(cold_admission=ColdAdmission())
        service = SubagentLifecycleService(lambda root=root: root)
        staged = service.stage(stage)
        binding = method.record(
            "runtime-binding",
            {
                "runtime_boot": str(__import__("uuid").uuid4()),
                "run_id": stage["manifest"]["payload"]["run_id"],
                "ticket": staged["ticket"],
                "native_root_id": staged["native_root_id"],
                "entries": staged["entries"],
                "authority": {
                    "instance_id": str(__import__("uuid").uuid4()),
                    "owner": str(__import__("uuid").uuid4()),
                    "epoch": 1,
                    "generation": 0,
                },
            },
        )
        release = {
            "protocol": stage["protocol"],
            "ticket": staged["ticket"],
            "manifest_ref": ref(stage["manifest"]),
            "binding": binding,
        }
        batch = service._cold_batches[stage["manifest"]["id"]]
        children = [r.agent for r in batch["records"]]
        self.assertEqual([c._contract_state.batch_index for c in children], [0, 1])
        read_barrier, handler_barrier = threading.Barrier(2), threading.Barrier(2)
        observed, lock = [], threading.Lock()
        tools_by_index = {}
        output_barrier = threading.Barrier(2)
        original_action = BoundContractTools.pure_action
        original_read, original_handler = BoundContractTools._read_bound_input, method.run_handler

        def read(tools):
            with lock:
                tools_by_index[tools.state.batch_index] = tools
            with _REGISTRY.lock:
                self.assertEqual(batch["binding"], canonical(binding))
                self.assertTrue(all(r.state == SubagentState.RUNNING for r in batch["records"]))
            bad_ref = {**tools.original_ref, "revision": True}

            def forbidden_read():
                raise AssertionError("invalid revision reached reader")

            with (
                patch.object(tools, "_read_bound_input", forbidden_read),
                self.assertRaises(ValueError),
            ):
                tools.read_input(bad_ref)
            read_barrier.wait(timeout=1)
            return original_read(tools)

        def handler(name, value):
            start = time.monotonic()
            handler_barrier.wait(timeout=1)
            output = original_handler(name, value)
            with lock:
                observed.append((name, threading.get_ident(), start, time.monotonic()))
            return output

        def action(tools, step_id, action_ref, input_refs):
            if step_id == "build-map":
                output_barrier.wait(timeout=1)
                sibling = tools_by_index[1 - tools.state.batch_index]
                with self.assertRaises(ValueError):
                    original_action(tools, step_id, action_ref, [ref(sibling.artifacts[0])])
                with self.assertRaises(ValueError):
                    original_action(tools, step_id, action_ref, [ref(sibling.receipts[0])])
            return original_action(tools, step_id, action_ref, input_refs)

        try:
            with (
                patch.object(BoundContractTools, "_read_bound_input", read),
                patch.object(method, "run_handler", handler),
                patch.object(BoundContractTools, "pure_action", action),
            ):
                final = service.release(release)
            validate_response(final)
            self.assertEqual(len(final["executions"]), 2)
            self.assertEqual(final["status"], "SUCCEEDED")
            self.assertEqual(service.release(release), final)
            self.assertEqual(
                service.readback({k: release[k] for k in ("protocol", "ticket", "manifest_ref")}),
                final,
            )
            for name in {r[0] for r in observed}:
                pair = [r for r in observed if r[0] == name]
                self.assertEqual(len(pair), 2)
                self.assertNotEqual(pair[0][1], pair[1][1])
                self.assertLess(max(r[2] for r in pair), min(r[3] for r in pair))
            self.assertTrue(all(r.future.done() for r in batch["records"]))
            self.assertTrue(all(c._contract_state.closed for c in children))
            BATCH2_OUTPUT.write_bytes(
                canonical({"binding": binding, "final": final, "overlap": observed})
            )
        finally:
            for child in children:
                child.close()
            root.close()


if __name__ == "__main__":
    BATCH2 = json.loads(Path(sys.argv[5]).read_bytes()) if len(sys.argv) == 6 else None
    BATCH2_OUTPUT = Path(sys.argv[5]).with_name("batch2-native-result.json") if BATCH2 else None
    effects = bootstrap()
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(Batch2Native if BATCH2 else ContractNative)
    )
    print(
        json.dumps(
            {
                "scope": "FULL_PINNED_SOURCE_HOST_INTERPRETER_NOT_INSTALLED",
                "tests": result.testsRun,
                "effects": effects,
                "pass": result.wasSuccessful() and not effects,
            }
        )
    )
    raise SystemExit(0 if result.wasSuccessful() and result.testsRun and not effects else 1)
