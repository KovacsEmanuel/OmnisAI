"""Consistency gates for the implementation baseline, not runtime claims."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "documents"


class BaselineContracts(unittest.TestCase):
    def test_visual_acceptance_is_separate_from_implementation_start(self):
        # AGENTS.md is protected; its pending status-only update is disclosed in README.
        for relative in ['README.md', 'DESIGN.md',
                         'documents/Omnis_UI_UX_Spec.md',
                         'documents/Omnis_Implementation_Plan.md',
                         'documents/Omnis_Implementation_Readiness_Review.md']:
            text = (ROOT / relative).read_text(encoding='utf-8')
            self.assertIn('VISUAL_ACCEPTED', text, relative)
            self.assertIn('df17a29', text, relative)
        for name in ['Omnis_Implementation_Plan.md', 'Omnis_Implementation_Readiness_Review.md']:
            text = (DOCS / name).read_text(encoding='utf-8')
            self.assertIn('START_PENDING_NEW_SESSION', text)
            self.assertIn('NEÎNCEPUT', text)
        self.assertIn('NO-GO pentru target effects', (ROOT / 'README.md').read_text(encoding='utf-8'))
        self.assertIn('INSTRUCTIONS_UPDATE_BLOCKED', (ROOT / 'README.md').read_text(encoding='utf-8'))

    def test_all_original_recommendations_have_one_traceability_row(self):
        text = (DOCS / "Omnis_Implementation_Plan.md").read_text(encoding="utf-8")
        ids = re.findall(r"^\| (R\d{2}) \|", text, re.M)
        self.assertEqual(sorted(ids), [f"R{i:02d}" for i in range(1, 13)])

    def test_accepted_navigation_has_matching_plan_and_feature_owners(self):
        tabs = 'Overview · Brain stream · Findings · Coverage · Reports'
        for name in ['Omnis_UI_UX_Spec.md', 'Omnis_Implementation_Plan.md', 'Omnis_MVP_Architecture.md']:
            text = (DOCS / name).read_text(encoding='utf-8')
            self.assertTrue(tabs in text, name + ': accepted engagement tabs missing')
            self.assertNotIn('Overview/Map/Investigations/Findings/Reports', text)
        architecture = (DOCS / 'Omnis_MVP_Architecture.md').read_text(encoding='utf-8')
        self.assertIn('stream/BrainStreamPage.tsx', architecture)
        self.assertIn('coverage/CoveragePage.tsx', architecture)
        self.assertNotIn('overview/BrainStream.tsx', architecture)
        ui = (DOCS / 'Omnis_UI_UX_Spec.md').read_text(encoding='utf-8')
        self.assertIn('/engagements/:id/coverage?tab=endpoints', ui)
        self.assertNotIn('/engagements/:id/map?tab=', ui)


    def test_ui_projections_have_consistent_snapshot_and_phase_contracts(self):
        for name in ['Omnis_MVP_Architecture.md', 'Omnis_UI_UX_Spec.md', 'Omnis_Implementation_Plan.md']:
            text = (DOCS / name).read_text(encoding='utf-8')
            for token in ['ProjectionEnvelope', 'CURSOR_CONTEXT_MISMATCH', 'phase_active', 'denominator_revision']:
                self.assertTrue(token in text, name + ': missing ' + token)
        architecture = (DOCS / 'Omnis_MVP_Architecture.md').read_text(encoding='utf-8')
        for route in ['GET /api/v1/dashboard', 'GET /api/v1/runs/{run}/summary']:
            self.assertTrue(route in architecture, 'Missing canonical route: ' + route)

    def test_report_review_policy_revisions_and_delivery_are_explicit(self):
        for name in ['Omnis_MVP_Architecture.md', 'Omnis_UI_UX_Spec.md', 'Omnis_Implementation_Plan.md']:
            text = (DOCS / name).read_text(encoding='utf-8')
            for token in ['report_review_policy', 'OPERATOR_REQUIRED', 'VALIDATOR_ONLY', 'claim_revision', 'review_revision']:
                self.assertTrue(token in text, name + ': missing ' + token)
        architecture = (DOCS / 'Omnis_MVP_Architecture.md').read_text(encoding='utf-8')
        self.assertTrue('POST /api/v1/findings/{id}/report-review' in architecture)
        self.assertTrue('ReportReview nu blochează COMPLETED' in architecture)
        plan = (DOCS / 'Omnis_Implementation_Plan.md').read_text(encoding='utf-8')
        for ticket in ['B13a', 'B13b', 'B13c', 'B13d']:
            self.assertTrue(ticket in plan, 'Missing deliverable ' + ticket)

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
