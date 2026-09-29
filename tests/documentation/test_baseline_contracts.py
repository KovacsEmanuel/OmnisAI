"""Consistency gates for the implementation baseline, not runtime claims."""
import json
from graphlib import TopologicalSorter
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
        historical_review = (DOCS / 'Omnis_Implementation_Readiness_Review.md').read_text(encoding='utf-8')
        self.assertIn('START_PENDING_NEW_SESSION', historical_review)
        self.assertIn('NEÎNCEPUT', historical_review)
        for relative in ['README.md', 'documents/Omnis_Implementation_Plan.md']:
            text = (ROOT / relative).read_text(encoding='utf-8')
            self.assertIn('P0.1_IMPLEMENTED_LOCAL', text, relative)
            self.assertIn('P0.2_IMPLEMENTED_LOCAL', text, relative)
            self.assertIn('P0.3', text, relative)
            self.assertIn('G00', text, relative)
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

    def test_delivery_dependencies_are_acyclic_and_bootstrap_is_inert(self):
        plan = (DOCS / 'Omnis_Implementation_Plan.md').read_text(encoding='utf-8')
        self.assertTrue('### Ordine verificabilă' in plan, 'Missing canonical phase dependency table')
        section = plan.split('### Ordine verificabilă', 1)[1].split('## 5.', 1)[0]
        rows = re.findall(r'^\| ([A-Za-z0-9+-]+) \| ([^|]+) \|', section, re.M)
        graph = {name: set() if deps.strip() == '—' else set(deps.strip().split(', ')) for name, deps in rows}
        expected = {'P0-control', 'P1-data', 'P1-web', 'P2-inert', 'P4a-minim', 'P2-live',
                    'B01e-build', 'P3a', 'P3-auth', 'P3b', 'P5a+P6a', 'P5b+P6b', 'P4b', 'P7', 'P8',
                    'P-LOOP', 'P-FOCUS', 'P-PATH', 'P-JEV'}
        self.assertEqual(set(graph), expected)
        self.assertEqual(len(rows), len(graph))
        self.assertTrue(all(deps <= expected for deps in graph.values()))
        self.assertEqual(len(tuple(TopologicalSorter(graph).static_order())), len(expected))
        self.assertIn('P1-data', graph['P2-inert'])
        self.assertEqual(graph['P2-live'], {'P2-inert', 'P4a-minim'})
        self.assertIn('B01e-build', graph['P3a'])
        self.assertEqual(graph['P5a+P6a'], {'P3-auth'})
        self.assertEqual(graph['P-LOOP'], {'P5a+P6a'})
        self.assertEqual(graph['P-FOCUS'], {'P5a+P6a'})
        self.assertEqual(graph['P-PATH'], {'P-LOOP', 'P5b+P6b'})
        self.assertIn('P3b', graph['P5b+P6b'])
        for name in ['Omnis_MVP_Architecture.md', 'Omnis_Stack_Baseline.md']:
            text = (DOCS / name).read_text(encoding='utf-8')
            self.assertTrue('B01e-build' in text and 'B01e-integrated' in text, name)
        architecture = (DOCS / 'Omnis_MVP_Architecture.md').read_text(encoding='utf-8')
        self.assertTrue('P0-control' in architecture and 'zero apeluri provider' in architecture)

    def test_every_ui_surface_has_a_delivery_mapping_and_handoff(self):
        plan = (DOCS / 'Omnis_Implementation_Plan.md').read_text(encoding='utf-8')
        ids = re.findall(r'^\| (UI\d{2}) \|', plan, re.M)
        self.assertEqual(sorted(ids), [f'UI{i:02d}' for i in range(1, 24)])
        for token in ['## 19.', 'P0.1', 'make test-api', 'make test-migrations', 'INSTRUCTIONS_UPDATE_BLOCKED']:
            self.assertTrue(token in plan, 'Missing handoff field: ' + token)
        readiness = (DOCS / 'Omnis_Implementation_Readiness_Review.md').read_text(encoding='utf-8')
        audit_ids = re.findall(r'^\| (PA\d{2}) \|', readiness, re.M)
        self.assertEqual(sorted(audit_ids), [f'PA{i:02d}' for i in range(1, 10)])

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
