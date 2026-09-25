"""Exercise the offline UI fixture, never a backend or assessment."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / 'documents' / 'assets' / 'prototype-model.js'


class PrototypeModelTests(unittest.TestCase):
    def run_model(self, assertions):
        bootstrap = """
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = process.argv[1];
const context = {structuredClone};
vm.createContext(context);
vm.runInContext(fs.existsSync(path) ? fs.readFileSync(path, 'utf8') : '', context);
assert.equal(typeof context.createOmnisDemo, 'function', 'offline fixture factory is missing');
const model = context.createOmnisDemo();
"""
        result = subprocess.run(['node', '-e', bootstrap + assertions, str(MODEL)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_summary_uses_confirmed_findings_and_defined_coverage(self):
        self.run_model("""
const s = model.summary();
assert.equal(s.confirmed, 3);
assert.equal(s.severity.CRITICAL, 0, 'candidate severity must not inflate confirmed counts');
assert.equal(s.severity.HIGH, 2);
assert.equal(s.severity.MEDIUM, 1);
assert.equal(s.needsReview, 1);
assert.equal(s.endpoints, 5);
assert.equal(s.observed, 4);
assert.equal(s.inferred, 1);
assert.equal(s.coverage.covered, 7);
assert.equal(s.coverage.total, 11);
assert.equal(s.coverage.percent, 64);
assert.equal(s.requests.used, 84);
assert.equal(s.requests.limit, 300);
assert.equal(s.requests.percent, 28);
assert.equal(s.llmCostUsd, null, 'unavailable cost is not zero');
model.state.coverage = [];
assert.equal(model.summary().coverage.percent, null, 'empty denominator is N/A');
""")

    def test_report_review_does_not_bypass_validation_revision_or_evidence(self):
        self.run_model("""
assert.equal(typeof model.reviewFinding, 'function', 'report-review transition is missing');
const candidate = model.state.findings.find(f => f.id === 'demo-candidate-01');
assert.equal(model.reviewFinding(candidate.id, 'APPROVED', 1).ok, false);
assert.equal(candidate.validation_status, 'CANDIDATE');
const f = model.state.findings.find(f => f.id === 'demo-f-02');
assert.equal(model.reviewFinding(f.id, 'APPROVED', 0).ok, false, 'stale selection must not mutate');
f.evidence_status = 'MISSING';
assert.equal(model.reviewFinding(f.id, 'APPROVED', 1).ok, false, 'missing evidence blocks a new approval');
f.evidence_status = 'AVAILABLE';
assert.equal(model.reviewFinding(f.id, 'APPROVED', 1).ok, true);
assert.equal(f.validation_status, 'CONFIRMED');
assert.equal(f.report_review.status, 'APPROVED');
assert.equal(model.summary().needsReview, 0);
assert.equal(model.summary().confirmed, 3);
assert.equal(model.reviewFinding(f.id, 'HELD', 2).ok, true);
assert.equal(f.report_review.status, 'HELD');
assert.equal(f.validation_status, 'CONFIRMED');
""")

    def test_reports_include_only_confirmed_review_eligible_snapshot_copies(self):
        self.run_model("""
assert.equal(typeof model.generateReport, 'function', 'report snapshot generation is missing');
const first = model.generateReport();
assert.equal(first.demo, true);
assert.equal(first.findings.length, 2);
assert.ok(first.findings.every(f => f.validation_status === 'CONFIRMED'));
assert.ok(!first.findings.some(f => f.id === 'demo-f-02' || f.id === 'demo-candidate-01'));
const before = JSON.stringify(first);
model.reviewFinding('demo-f-02', 'APPROVED', 1);
const second = model.generateReport();
assert.equal(second.findings.length, 3);
assert.notEqual(first.id, second.id);
assert.equal(JSON.stringify(first), before, 'new approval cannot rewrite a prior report');
model.reviewFinding('demo-f-02', 'HELD', 2);
assert.equal(model.generateReport().findings.length, 2);
assert.equal(second.findings.length, 3, 'later hold cannot rewrite old snapshot');
model.state.findings.forEach(f => f.validation_status = 'INCONCLUSIVE');
assert.equal(model.generateReport().findings.length, 0, 'unconfirmed records are never exported as vulnerabilities');
""")

    def test_material_change_invalidates_prior_report_acceptance(self):
        self.run_model("""
model.reviewFinding('demo-f-02', 'APPROVED', 1);
const f = model.state.findings.find(f => f.id === 'demo-f-02');
f.summary = 'Changed claim that has not been reviewed';
f.revision += 1;
assert.ok(!model.generateReport().findings.some(x => x.id === f.id), 'changed claim needs a fresh review');
assert.equal(model.summary().needsReview, 1);
assert.equal(model.reviewFinding(f.id, 'APPROVED', f.revision).ok, true);
assert.ok(model.generateReport().findings.some(x => x.id === f.id));
f.evidence[0].body += '\\nChanged evidence version';
assert.ok(!model.generateReport().findings.some(x => x.id === f.id), 'changed evidence needs a fresh review');
""")

    def test_coverage_references_resolve_and_reject_wrong_context(self):
        self.run_model("""
const c = model.state.coverage.find(x => x.status === 'confirmed');
const original = structuredClone(c);
for (const change of [
    {evidence_refs: []}, {auth_epoch: null}, {snapshot_id: 'another-snapshot'},
    {identity: 'another-persona'}, {procedure_revision: null}, {run_id: 'other-run'}, {parameter: 'other-input'},
    {evidence_refs: ['does-not-exist']}
]) {
    Object.assign(c, original, change);
    assert.equal(model.summary().coverage.covered, 6, JSON.stringify(change));
    Object.assign(c, original);
    assert.equal(model.summary().coverage.covered, 7, 'positive context must recover');
}
assert.ok(c.evidence_refs.every(id => model.state.evidence[id]), 'references must be inspectable, not invented dangling IDs');
const artifact = model.state.evidence[c.evidence_refs[0]];
artifact.auth_epoch = 'wrong-epoch';
assert.equal(model.summary().coverage.covered, 6, 'mismatched artifact context cannot qualify');
""")


if __name__ == '__main__':
    unittest.main()
