"""Synthetic unit controls for acceptance logic, not manufactured runtime evidence."""
from pathlib import Path
import copy
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("reticle_verdicts", ROOT / "tools/development/reticle/verdicts.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ReticleVerdictTests(unittest.TestCase):
    def setUp(self):
        self.positive = {"verified": "yes", "verifiedReason": "proved", "verdict": {"pass": True}}
        self.negative = {"verified": "no", "verifiedReason": "assertion_failed", "verdict": {"pass": False, "assertion": "net.present"}}
        self.observation = {"calls": [
            {"method": "POST", "url": "/api/ok", "status": 200},
            {"method": "POST", "url": "/api/save", "status": 500},
        ]}

    def test_requires_both_real_network_outcomes(self):
        self.assertTrue(MODULE.network_controls_passed(self.positive, self.negative, self.observation))

    def test_unrelated_negative_reason_is_not_a_pass(self):
        self.negative["verifiedReason"] = "session_disconnected"
        self.assertFalse(MODULE.network_controls_passed(self.positive, self.negative, self.observation))

    def test_always_rejecting_verifier_is_not_a_pass(self):
        self.positive["verified"] = "no"
        self.assertFalse(MODULE.network_controls_passed(self.positive, self.negative, self.observation))

    def test_missing_or_wrong_capture_is_not_a_pass(self):
        variants = [{"calls": []}, {}, {"calls": "not-a-list"}]
        for key, value in [("status", 503), ("url", "/unrelated"), ("method", "GET")]:
            wrong = copy.deepcopy(self.observation)
            wrong["calls"][1][key] = value
            variants.append(wrong)
        variants.append({"calls": [self.observation["calls"][1]]})
        for observation in variants:
            with self.subTest(observation=observation):
                self.assertFalse(MODULE.network_controls_passed(self.positive, self.negative, observation))

    def test_wrong_assertion_or_inconsistent_verdict_is_not_a_pass(self):
        for key, value in [("assertion", "state.equals"), ("pass", True)]:
            wrong = copy.deepcopy(self.negative)
            wrong["verdict"][key] = value
            self.assertFalse(MODULE.network_controls_passed(self.positive, wrong, self.observation))


if __name__ == "__main__":
    unittest.main()
