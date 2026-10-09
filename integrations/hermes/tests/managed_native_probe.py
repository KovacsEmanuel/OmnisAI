"""Finite native probe. Run ONLY with the isolated installed native interpreter.

No AIAgent replacement, monkeypatch, provider, conversation, target or credential.
The profiler independently records forbidden native function entry attempts.
"""

import copy
import json
import sys
import time
import unittest
from uuid import uuid4

from omnis_hermes.managed_admission_contract import PROTOCOL, canonical, digest, ref


def record(kind, payload):
    body = dict(schema_version=1, kind=kind, id=str(uuid4()), revision=1, payload=payload)
    return {**body, "digest": digest(canonical(body))}


def manifest():
    return record(
        "launch-manifest",
        {
            "run_id": str(uuid4()),
            "selection_ref": ref(record("execution-selection", {})),
            "resolution": "NO_MODEL",
            "effective": None,
            "entries": [
                dict(
                    batch_index=i,
                    task_id=str(uuid4()),
                    attempt_id=str(uuid4()),
                    brief_ref=ref(record("task-brief", {})),
                    goal="same goal",
                )
                for i in range(2)
            ],
        },
    )


class ColdLifecycle(unittest.TestCase):
    def setUp(self):
        from agent.cold_admission import ColdAdmission
        from agent.subagent_lifecycle import SubagentLifecycleService
        from run_agent import AIAgent

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
                raise AssertionError("forbidden native sink: " + frame.f_code.co_name)

        self.old_profiler = sys.getprofile()
        sys.setprofile(observe)
        self.root = AIAgent(cold_admission=ColdAdmission())
        self.service = SubagentLifecycleService(lambda: self.root)
        self.manifest = manifest()
        self.payload = dict(protocol=PROTOCOL, manifest=self.manifest)

    def tearDown(self):
        sys.setprofile(self.old_profiler)
        self.root.close()
        self.root.close()
        self.assertEqual(self.attempts, [])

    def stage(self):
        self.staged = self.service.stage(self.payload)
        self.status = {k: self.staged[k] for k in ("protocol", "ticket", "manifest_ref")}
        self.binding = record(
            "runtime-binding",
            dict(
                runtime_boot=str(uuid4()),
                run_id=self.manifest["payload"]["run_id"],
                ticket=self.staged["ticket"],
                native_root_id=self.staged["native_root_id"],
                entries=self.staged["entries"],
                authority=dict(instance_id=str(uuid4()), owner=str(uuid4()), epoch=1, generation=0),
            ),
        )
        self.release = {**self.status, "binding": self.binding}
        return self.staged

    def test_stage_real_distinct_agents_and_blocked_native_terminal(self):
        from agent.subagent_lifecycle import _REGISTRY, SubagentState
        from run_agent import AIAgent

        staged = self.stage()
        rows = staged["entries"]
        self.assertNotEqual(rows[0]["native_child_id"], rows[1]["native_child_id"])
        self.assertNotEqual(rows[0]["native_session_id"], rows[1]["native_session_id"])
        for row in rows:
            native = _REGISTRY.records[row["native_child_id"]]
            self.assertIs(type(native.agent), AIAgent)
            self.assertIsNone(native.future)
            self.assertEqual(native.state, SubagentState.PENDING)
        self.assertEqual(self.service.stage(self.payload), staged)
        final = self.service.release(self.release)
        self.assertEqual(final["status"], "BLOCKED")
        self.assertEqual(final["reason"], "NO_MODEL")
        self.assertEqual(self.service.readback(self.status), final)
        self.assertEqual(self.service.release(self.release), final)
        self.assertEqual(self.service.stage(self.payload), final)
        for row in rows:
            native = _REGISTRY.records[row["native_child_id"]]
            self.assertEqual(native.result.terminal_state, SubagentState.BLOCKED)
            self.assertEqual(native.result.error_classification, "NO_MODEL")
            self.assertIsNone(native.started_at)
            self.assertIsNone(native.agent)

    def test_domain_tools_conversation_wake_lineage_are_denied(self):
        from agent.cold_admission import ColdAdmissionDenied
        from agent.subagent_lifecycle import SubagentLaunchRequest

        for surface in (
            "run_conversation",
            "_execute_tool_calls",
            "_get_session_db_for_recall",
            "reset_session_state",
            "_transition_context_engine_session",
            "interrupt",
            "wake",
            "client",
            "future_unknown_surface",
        ):
            with self.subTest(surface=surface), self.assertRaises(ColdAdmissionDenied):
                getattr(self.root, surface)
        with self.assertRaises(ColdAdmissionDenied):
            self.service.launch(SubagentLaunchRequest(goal="cold cannot launch warm"))

    def test_missing_binding_tampering_and_replay_are_denied_without_mutation(self):
        self.stage()
        for key in ("binding", "ticket", "manifest_ref"):
            bad = dict(self.release)
            del bad[key]
            with self.assertRaises(ValueError):
                self.service.release(bad)
        for key in ("native_root_id", "run_id", "entries"):
            bad = copy.deepcopy(self.binding["payload"])
            bad[key] = [] if key == "entries" else str(uuid4())
            with self.assertRaises(ValueError):
                self.service.release({**self.status, "binding": record("runtime-binding", bad)})
        self.assertEqual(self.service.readback(self.status)["status"], "STAGED")
        changed = copy.deepcopy(self.manifest)
        changed["payload"]["entries"][0]["goal"] = "changed"
        changed["digest"] = digest(canonical({k: v for k, v in changed.items() if k != "digest"}))
        with self.assertRaises(ValueError):
            self.service.stage(dict(protocol=PROTOCOL, manifest=changed))
        final = self.service.release(self.release)
        with self.assertRaises(ValueError):
            self.service.release(
                {**self.status, "binding": record("runtime-binding", self.binding["payload"])}
            )
        self.assertEqual(self.service.readback(self.status), final)

    def test_late_or_closed_stage_cannot_release(self):
        self.stage()
        batch = self.service._cold_batches[self.manifest["id"]]
        batch["expires"] = time.monotonic() - 1
        with self.assertRaises(ValueError):
            self.service.release(self.release)
        batch["expires"] = time.monotonic() + 1
        self.root.close()
        with self.assertRaises(ValueError):
            self.service.release(self.release)
        self.assertEqual(self.service.readback(self.status)["status"], "STAGED")

    def test_private_rpc_uses_native_service_and_readback(self):
        from agent.managed_admission_rpc import dispatch
        from omnis_hermes.managed_admission_contract import RPC

        stage = dispatch(RPC["task_stage"], self.payload)
        status = {k: stage[k] for k in ("protocol", "ticket", "manifest_ref")}
        self.assertEqual(dispatch(RPC["task_status"], status), stage)
        self.assertEqual(dispatch(RPC["task_stage"], self.payload), stage)
        binding = record(
            "runtime-binding",
            dict(
                runtime_boot=str(uuid4()),
                run_id=self.manifest["payload"]["run_id"],
                ticket=stage["ticket"],
                native_root_id=stage["native_root_id"],
                entries=stage["entries"],
                authority=dict(instance_id=str(uuid4()), owner=str(uuid4()), generation=0, epoch=1),
            ),
        )
        final = dispatch(RPC["task_release"], {**status, "binding": binding})
        self.assertEqual(final["status"], "BLOCKED")
        self.assertEqual(dispatch(RPC["task_status"], status), final)

    def test_replacement_root_cannot_revive_an_old_pending_batch(self):
        from agent.cold_admission import ColdAdmission
        from agent.subagent_lifecycle import _REGISTRY, SubagentState
        from run_agent import AIAgent

        staged = self.stage()
        replacement = AIAgent(cold_admission=ColdAdmission())
        self.service._parent_agent_resolver = lambda: replacement
        try:
            self.assertNotEqual(replacement.session_id, self.root.session_id)
            for old_closed in (False, True):
                if old_closed:
                    self.root.close()
                with self.subTest(old_closed=old_closed):
                    with self.assertRaises(ValueError):
                        self.service.stage(self.payload)
                    with self.assertRaises(ValueError):
                        self.service.release(self.release)
                    self.assertEqual(self.service.readback(self.status), staged)
                    for row in staged["entries"]:
                        child = _REGISTRY.records[row["native_child_id"]]
                        self.assertEqual(child.state, SubagentState.PENDING)
                        self.assertIsNone(child.result)
        finally:
            replacement.close()

    def test_invalid_cold_token_and_warm_options_denied(self):
        from agent.cold_admission import ColdAdmission
        from run_agent import AIAgent

        for kwargs in (
            {"cold_admission": "NO_MODEL"},
            {"cold_admission": ColdAdmission("DEFAULT")},
            {"cold_admission": ColdAdmission(), "provider": "forbidden"},
        ):
            with self.assertRaises(ValueError):
                AIAgent(**kwargs)


if __name__ == "__main__":
    import os
    import platform

    if platform.python_version() != "3.13.15" or os.environ.get("HERMES_OMNIS_INERT") != "1":
        raise ValueError("Isolated installed pinned interpreter required")
    effects = []

    def audit(event, args):
        forbidden = event in {"socket.connect", "subprocess.Popen", "os.system"}
        if event == "open" and isinstance(args[0], (str, bytes)):
            forbidden |= os.fsdecode(args[0]).endswith((".env", "auth.json", "credentials.json"))
        if forbidden:
            effects.append(event)
            raise RuntimeError("Forbidden installed probe effect")

    sys.addaudithook(audit)
    started = time.monotonic()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ColdLifecycle)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    passed = result.wasSuccessful() and result.testsRun == 7 and not effects
    print(
        json.dumps(
            {
                "scope": "INSTALLED_NATIVE",
                "tests": result.testsRun,
                "seconds": time.monotonic() - started,
                "effects": effects,
                "pass": passed,
            }
        )
    )
    raise SystemExit(0 if passed else 1)
