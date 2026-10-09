"""Finite v2 native consumer probe; requires the isolated full pinned runtime.

No model, tools or positive child read. Retention is private to the lifecycle.
"""

import copy
import json
import os
import platform
import runpy
import sys
import unittest
from pathlib import Path

HELPERS = runpy.run_path(str(Path(__file__).with_name("composition_fixture.py")))
LEGACY = runpy.run_path(str(Path(__file__).with_name("managed_native_probe.py")))
fixture, seal = HELPERS["fixture"], HELPERS["seal"]


class ComposedLifecycle(unittest.TestCase):
    tearDown = LEGACY["ColdLifecycle"].tearDown
    stage = LEGACY["ColdLifecycle"].stage

    def setUp(self):
        LEGACY["ColdLifecycle"].setUp(self)
        self.payload = fixture()
        self.manifest = self.payload["manifest"]

    def test_complete_material_consumed_privately_before_cold_identities(self):
        from agent.subagent_lifecycle import _REGISTRY
        from omnis_hermes.native_preparation_contract import canonical
        from run_agent import AIAgent

        staged = self.stage()
        batch = self.service._cold_batches[self.manifest["id"]]
        self.assertEqual(
            batch["composition_material"], tuple(canonical(c) for c in self.payload["compositions"])
        )
        self.assertIs(
            type(_REGISTRY.records[staged["entries"][0]["native_child_id"]].agent), AIAgent
        )
        self.assertEqual(staged["protocol"], self.payload["protocol"])
        self.assertEqual(
            staged["entries"][0]["composition_ref"],
            self.manifest["payload"]["entries"][0]["composition_ref"],
        )
        saved = batch["composition_material"]
        altered = copy.deepcopy(self.payload)
        altered["compositions"][0]["payload"]["text"] = "changed"
        with self.assertRaises(ValueError):
            self.service.stage(altered)
        self.assertEqual(batch["composition_material"], saved)
        final = self.service.release(self.release)
        self.assertEqual(final["status"], "BLOCKED")
        self.assertEqual(final["reason"], "NO_MODEL")
        self.assertEqual(self.service.stage(self.payload), final)
        self.root.close()
        self.assertEqual(self.service.readback(self.status), final)

    def test_invalid_material_is_denied_before_any_child_constructor(self):
        from agent.subagent_lifecycle import _REGISTRY
        from omnis_hermes.managed_admission_contract import ref
        from omnis_hermes.native_preparation_contract import canonical, digest

        before = set(_REGISTRY.records)
        for change in ("missing", "content", "foreign_attempt", "overflow"):
            bad = copy.deepcopy(self.payload)
            composition = bad["compositions"][0]
            if change == "missing":
                bad["compositions"] = []
            elif change == "overflow":
                composition["payload"]["text"] += " " * 32768
            else:
                sections = json.loads(composition["payload"]["text"])
                if change == "content":
                    sections[4]["content"][0]["text"] += "tampered"
                else:
                    sections[2]["record"]["payload"]["header"]["attempt_id"] = (
                        "00000000-0000-0000-0000-000000000000"
                    )
                    seal(sections[2]["record"])
                raw = canonical(sections)
                composition["payload"].update(
                    text=raw.decode(),
                    text_digest=digest(raw),
                    byte_count=len(raw),
                    token_upper_bound=len(raw),
                )
                seal(composition)
                bad["manifest"]["payload"]["entries"][0]["composition_ref"] = ref(composition)
                seal(bad["manifest"])
            constructors = []
            old = sys.getprofile()

            def observe(frame, event, arg, constructors=constructors, old=old):
                if event == "call" and frame.f_code.co_name == "initialize_cold":
                    constructors.append("cold")
                if old:
                    old(frame, event, arg)

            sys.setprofile(observe)
            try:
                with self.subTest(change=change), self.assertRaises(ValueError):
                    self.service.stage(bad)
            finally:
                sys.setprofile(old)
            self.assertEqual(constructors, [])
            self.assertEqual(set(_REGISTRY.records), before)

    def test_status_release_and_binding_cannot_downgrade(self):
        self.stage()
        for operation, payload in (
            (self.service.readback, self.status),
            (self.service.release, self.release),
        ):
            with self.assertRaises(ValueError):
                operation({**payload, "protocol": "omnis-managed-admission-v1"})
        bad = copy.deepcopy(self.release)
        bad["binding"]["payload"]["entries"][0]["composition_ref"]["digest"] = "f" * 64
        seal(bad["binding"])
        with self.assertRaises(ValueError):
            self.service.release(bad)
        self.assertEqual(self.service.readback(self.status)["status"], "STAGED")
        self.assertEqual(self.service.release(self.release)["status"], "BLOCKED")


if __name__ == "__main__":
    if platform.python_version() != "3.13.15" or os.environ.get("HERMES_OMNIS_INERT") != "1":
        raise ValueError("Isolated installed pinned interpreter required")
    effects = []

    def audit(event, args):
        denied = event in {"socket.connect", "subprocess.Popen", "os.system"}
        if event == "open" and isinstance(args[0], (str, bytes)):
            denied |= os.fsdecode(args[0]).endswith((".env", "auth.json", "credentials.json"))
        if denied:
            effects.append(event)
            raise RuntimeError("Forbidden native probe effect")

    sys.addaudithook(audit)
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ComposedLifecycle)
    )
    passed = result.wasSuccessful() and result.testsRun == 3 and not effects
    print(
        json.dumps(
            {
                "scope": "INSTALLED_NATIVE_COMPOSITION",
                "tests": result.testsRun,
                "effects": effects,
                "pass": passed,
            }
        )
    )
    raise SystemExit(0 if passed else 1)
