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
    source, overlay, adapter, home = map(lambda x: Path(x).resolve(), sys.argv[1:])
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
        positive = AIAgent(contract_admission=ContractAdmission(self.root, canonical(self.payload)))
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
                    candidate, contract_admission=ContractAdmission(self.root, canonical(bad))
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
                "required": True,
                "applies_if": [],
                "step_ids": [],
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
                    "required": True,
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
            self.assertEqual(result["method_results"][-1]["basis_refs"], [])
            self.assertEqual(result["method_results"][-1]["state"], "DONE")
            self.assertEqual(len(result["action_refs"]), 2)

    def count_accesses(self):
        accesses = []
        previous = sys.getprofile()

        def observe(frame, event, arg):
            if event == "call" and frame.f_code.co_name in {"_read_bound_input", "run_handler"}:
                accesses.append(frame.f_code.co_name)
            if previous:
                previous(frame, event, arg)

        sys.setprofile(observe)
        self.addCleanup(sys.setprofile, previous)
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
                "contract_admission": ContractAdmission(self.root, canonical(self.payload)),
                "model": "forbidden",
            },
        ):
            with self.assertRaises(ValueError):
                AIAgent(**options)


if __name__ == "__main__":
    effects = bootstrap()
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ContractNative)
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
