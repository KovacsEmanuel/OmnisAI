"""Consistency gates for the implementation baseline, not runtime claims."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "documents"


class BaselineContracts(unittest.TestCase):
    def test_all_original_recommendations_have_one_traceability_row(self):
        text = (DOCS / "Omnis_Implementation_Plan.md").read_text(encoding="utf-8")
        ids = re.findall(r"^\| (R\d{2}) \|", text, re.M)
        self.assertEqual(sorted(ids), [f"R{i:02d}" for i in range(1, 13)])

    def test_second_review_contracts_are_recorded(self):
        text = (DOCS / "Omnis_Implementation_Readiness_Review.md").read_text(encoding="utf-8")
        ids = re.findall(r"^\| (RR\d{2}) \|", text, re.M)
        self.assertEqual(sorted(ids), [f"RR{i:02d}" for i in range(1, 9)])

    def test_frontend_probe_matches_selected_pins(self):
        baseline = json.loads((DOCS / "Omnis_Stack_Baseline.versions.json").read_text(encoding="utf-8"))
        package = json.loads((DOCS / "verification/stack-probe-inputs/web/package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["dependencies"], baseline["frontend_runtime"])
        self.assertEqual(package["devDependencies"], baseline["frontend_build"] | baseline["frontend_tests"])
        self.assertEqual(package["engines"]["node"], baseline["runtimes"]["node"]["selected"])

    def test_rejected_proxy_is_not_marked_ready(self):
        baseline = json.loads((DOCS / "Omnis_Stack_Baseline.versions.json").read_text(encoding="utf-8"))
        self.assertEqual(baseline["proxy_candidate"]["status"], "REJECTED_FOR_TARGET_USE_DUE_TO_KNOWN_ADVISORIES")
        self.assertEqual(set(baseline["proxy_candidate"]["affected_dependencies"]), {"cryptography", "h2", "msgpack", "tornado"})
        self.assertNotEqual(baseline["api_runtime"]["cryptography"], baseline["proxy_candidate"]["pins"]["cryptography"])

    def test_evidence_record_preserves_actual_failures_and_limits(self):
        record = json.loads((DOCS / "verification/stack-probe.json").read_text(encoding="utf-8"))
        self.assertEqual(record["scope"], "DISPOSABLE_DEPENDENCY_PROBES_NOT_OMNIS_APPLICATION")
        self.assertTrue(record["failures_and_fixes"])
        self.assertIn("Hermes native runtime/provider integration", record["not_tested"])
        self.assertEqual(record["web_typecheck"]["exit_code"], 0)
        self.assertEqual(record["web_tests"]["exit_code"], 0)
        self.assertEqual(record["api"]["exit_code"], 0)


if __name__ == "__main__":
    unittest.main()
