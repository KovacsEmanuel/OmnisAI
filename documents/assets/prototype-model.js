/* SYNTHETIC UI FIXTURE ONLY. No transport, credentials, scanner or backend. */
(function (root) {
  'use strict';
  const transcript = text => 'SYNTHETIC TRANSCRIPT — No request was sent.\n' + text;
  const seed = {
    schema_version: 'ui-preview.v1', demo: true, snapshot_id: 'demo-r3', revision: 1,
    engagement: {id: 'demo-engagement-01', name: 'Invoice lab', origin: 'https://lab.invalid'},
    run: {id: 'run-demo', status: 'RUNNING', phase: 'VALIDATE', phase_label: 'Validation', activity: 'Reviewing findings and validation gaps', elapsed_seconds: 720, requests_used: 84, request_limit: 300, time_limit_seconds: 1200, validation_reserve_percent: 25, llm_cost_usd: null},
    identity: {name: 'Alice', role: 'member', auth_epoch: 'demo-epoch-a'},
    action_approval: {id: 'demo-approval-01', status: 'PENDING', title: 'Session setup', effect: 'SESSION_CHANGE', path: '/login'},
    operations: [
      {id: 'invoice', method: 'GET', path: '/api/invoices/{id}', identity: 'Alice / member', auth_epoch: 'demo-epoch-a', source: 'Browser', state: 'observed', parameter: 'id · path · object reference'},
      {id: 'profile', method: 'GET', path: '/api/profile', identity: 'Alice / member', auth_epoch: 'demo-epoch-a', source: 'HTTP', state: 'observed', parameter: 'No object parameter'},
      {id: 'export', method: 'POST', path: '/api/export', identity: 'Unknown', auth_epoch: null, source: 'JS hint', state: 'inferred', parameter: 'Body fields not observed'},
      {id: 'search', method: 'GET', path: '/search', identity: 'Alice / member', auth_epoch: 'demo-epoch-a', source: 'Browser', state: 'observed', parameter: 'q · query · reflected input'},
      {id: 'file', method: 'GET', path: '/api/files/preview', identity: 'Alice / member', auth_epoch: 'demo-epoch-a', source: 'HTTP', state: 'observed', parameter: 'name · query · file reference'}
    ],
    findings: [
      {
        id: 'demo-f-01', revision: 1, severity: 'HIGH', title: 'Private invoice visible to another account', classification: 'CWE-639 · Object authorization', operation_id: 'invoice',
        validation_status: 'CONFIRMED', remediation_status: 'OPEN', evidence_status: 'AVAILABLE', report_review: {required: false, status: 'NOT_REQUIRED'},
        investigator_id: 'demo-task-01', validator_id: 'demo-val-01', procedure: 'object-authorization / demo release', rule: 'demo-rule-02 · expected DENY',
        summary: 'In this demo, Alice reads the private invoice test object owned by Bob despite an explicit deny rule.',
        risk: 'Cross-account disclosure of one designated billing test object. No mass enumeration, write access or access to every invoice is claimed.',
        severity_reason: 'High: private account data crosses an authorization boundary. No numeric CVSS score is asserted.',
        preconditions: ['Authorized fixture and scope revision demo-r3.', 'Verified Alice / member context, auth epoch demo-epoch-a.', 'Private and shared test objects with versioned DENY/ALLOW rules.'],
        steps: ['Verify the principal and restore the authorized test objects.', 'Read the shared invoice and match its allowed object marker.', 'Independently replay the private-invoice read as Alice.', 'On the protected fixture, require private access to fail while shared access still succeeds.'],
        poc: transcript('GET /api/invoices/demo-private\nHost: lab.invalid\nAuthorization: [REDACTED]\n\nExpected: DENY\nExample observation: 200 + demo-private object marker'),
        evidence: [
          {id: 'demo-ev-baseline', role: 'Allowed baseline', body: transcript('GET /api/invoices/demo-shared\nIdentity: Alice / demo-epoch-a\nExpected ALLOW → example 200 + demo-shared marker')},
          {id: 'demo-ev-replay', role: 'Independent replay', body: transcript('GET /api/invoices/demo-private\nIdentity: Alice / demo-epoch-a\nExpected DENY → example 200 + demo-private marker\nFresh validator context: demo-val-01')},
          {id: 'demo-ev-control', role: 'Paired secure control', body: transcript('Protected fixture, same principal/rule:\nPrivate object → denied (example 403)\nShared object → allowed + expected marker\nThis is an authorization control, not an expired-login failure.')}
        ],
        validation_reason: 'Independent replay reproduced the private-object marker. The positive baseline and secure control distinguish an authorization defect from invalid authentication.',
        remediation: 'Apply the versioned principal/tenant/object-access rule on every invoice read. Add both private-denial and shared-access regression tests.',
        limits: 'One authorized synthetic object and operation. The fixture transcripts are illustrative, not actual security evidence.'
      },
      {
        id: 'demo-f-02', revision: 1, severity: 'HIGH', title: 'Reflected script execution in search results', classification: 'CWE-79 · Reflected XSS', operation_id: 'search',
        validation_status: 'CONFIRMED', remediation_status: 'OPEN', evidence_status: 'AVAILABLE', report_review: {required: true, status: 'PENDING'},
        investigator_id: 'demo-task-03', validator_id: 'demo-val-02', procedure: 'reflected-xss / demo release', rule: 'demo-rule-03 · input must render as text',
        summary: 'The demo search response reflects input into an executable HTML context. A fresh browser-context replay produces the designated test marker.',
        risk: 'Script execution in the authorized search-page context. The example does not demonstrate session theft, stored XSS or a cross-origin attack.',
        severity_reason: 'High in this synthetic authenticated-page scenario. Impact and report wording require operator review before inclusion.',
        preconditions: ['Authorized /search route and synthetic marker.', 'A fresh isolated browser context with the same identity.', 'The target CSP remains enabled; no bypass flag is used.'],
        steps: ['Load an ordinary query as the baseline.', 'Supply the bounded synthetic marker payload in q.', 'Replay independently and observe the page marker, not only reflected source text.', 'Repeat on the encoded-input control; require text rendering and no script marker.'],
        poc: transcript('GET /search?q=[BOUNDED_DEMO_MARKER]\nHost: lab.invalid\n\nBaseline: ordinary query renders\nReplay: designated script marker observed\nProtected control: encoded text, no marker'),
        evidence: [
          {id: 'demo-xss-baseline', role: 'Browser baseline', body: transcript('Ordinary query rendered under Alice.\nFresh context and expected route verified.')},
          {id: 'demo-xss-replay', role: 'Independent browser replay', body: transcript('Validator demo-val-02 observed the designated page marker.\nCSP unchanged. No screenshot or trace is fabricated here.')},
          {id: 'demo-xss-control', role: 'Encoded-input control', body: transcript('The protected fixture rendered input as text.\nNo script marker. Baseline remained available.')}
        ],
        validation_reason: 'The validator observed the execution marker with CSP unchanged and an independently passing encoded-input control. Technical status and human report review are separate.',
        remediation: 'Use context-appropriate output encoding and safe DOM text APIs. Retain CSP as defense in depth; test the actual output context.',
        limits: 'Reflected XSS only on the designated synthetic search route; no stored/DOM XSS or credential theft claim.'
      },
      {
        id: 'demo-f-03', revision: 1, severity: 'MEDIUM', title: 'File preview escapes its authorized directory', classification: 'CWE-22 · Traversal canary', operation_id: 'file',
        validation_status: 'CONFIRMED', remediation_status: 'OPEN', evidence_status: 'AVAILABLE', report_review: {required: false, status: 'NOT_REQUIRED'},
        investigator_id: 'demo-task-04', validator_id: 'demo-val-03', procedure: 'traversal-canary / demo release', rule: 'demo-rule-04 · preview directory boundary',
        summary: 'The demo file-preview parameter reaches a pre-authorized canary outside the intended preview directory.',
        risk: 'A bounded read-boundary violation. No real system file, credential or arbitrary filesystem access is claimed.',
        severity_reason: 'Medium: the demonstrated impact is limited to the controlled canary read.',
        preconditions: ['The evaluator owns the synthetic canary and reset procedure.', 'Only the declared name parameter and route are authorized.', 'No write/delete operation or generic shell is available.'],
        steps: ['Read a valid in-directory sample as the positive baseline.', 'Submit the bounded traversal-canary parameter.', 'Replay independently and match the exact authorized canary marker.', 'Require the protected fixture to reject escape while keeping the normal preview working.'],
        poc: transcript('GET /api/files/preview?name=..%2Fdemo-canary\nHost: lab.invalid\n\nExample: designated canary marker returned\nControl: boundary escape denied; normal preview available'),
        evidence: [
          {id: 'demo-file-baseline', role: 'In-directory baseline', body: transcript('Normal preview returned the authorized sample marker.')},
          {id: 'demo-file-replay', role: 'Canary replay', body: transcript('Fresh validator context matched the designated canary marker.\nNo real host file was accessed.')},
          {id: 'demo-file-control', role: 'Protected boundary control', body: transcript('Escape input denied.\nNormal in-directory preview still succeeded.')}
        ],
        validation_reason: 'Independent replay matched the exact canary, and the protected boundary control rejected escape without breaking the baseline.',
        remediation: 'Resolve file references within the authorized root, reject path escape and test both allowed previews and denied traversal.',
        limits: 'Read-only synthetic canary; no claim about arbitrary files or write capabilities.'
      },
      {
        id: 'demo-candidate-01', revision: 1, severity: 'CRITICAL', title: 'Export authorization needs verification', classification: 'Potential object-authorization issue', operation_id: 'export',
        validation_status: 'CANDIDATE', remediation_status: null, evidence_status: 'MISSING', report_review: {required: true, status: 'PENDING'},
        investigator_id: 'demo-task-02', validator_id: null, procedure: 'object-authorization / demo release', rule: 'UNKNOWN',
        summary: 'A static route hint suggests an export surface. The expected access rule and verified identity are missing.',
        risk: 'Potential impact is unverified. Critical is a hypothesis-priority label, not a confirmed vulnerability severity.',
        severity_reason: 'Unvalidated hypothesis; excluded from confirmed severity totals and reports.',
        preconditions: ['Establish the expected business rule.', 'Verify the authorized identity and classify the effect before execution.'],
        steps: [], poc: 'No PoC has been executed or established.', evidence: [],
        validation_reason: 'Blocked: missing policy, identity and qualifying evidence. An operator click cannot confirm this candidate.',
        remediation: 'No vulnerability remediation is asserted before validation.', limits: 'Inferred endpoint, not exercised.'
      }
    ],
    coverage: [], evidence: {},
    events: [
      {id: 'demo-c18', type: 'decision', actor: 'Brain', time: 'T+12:00', title: 'Defer the export test', summary: 'The access rule is unknown. Keep this candidate blocked.', ref_type: 'candidate', ref_id: 'demo-candidate-01'},
      {id: 'demo-c17', type: 'validation', actor: 'Validator', time: 'T+11:42', title: 'Search finding validated', summary: 'Replay and controls passed. Report inclusion requires operator review.', ref_type: 'finding', ref_id: 'demo-f-02'},
      {id: 'demo-c16', type: 'tool_result', actor: 'Validator', time: 'T+11:26', title: 'browser_check returned evidence', summary: 'Execution marker and protected control attached to the search case.', ref_type: 'finding', ref_id: 'demo-f-02'},
      {id: 'demo-c15', type: 'tool_called', actor: 'Validator', time: 'T+11:20', title: 'browser_check · GET /search', summary: 'Independent replay in an isolated context; bounded synthetic input.', ref_type: 'operation', ref_id: 'search'},
      {id: 'demo-c14', type: 'endpoint', actor: 'Investigator', time: 'T+10:34', title: 'GET /api/files/preview observed', summary: 'The name query parameter was added to the endpoint inventory.', ref_type: 'operation', ref_id: 'file'},
      {id: 'demo-c13', type: 'validation', actor: 'Validator', time: 'T+09:58', title: 'Replay and controls support the invoice finding', summary: 'A private-object read was reproduced under the same authorized rule.', ref_type: 'finding', ref_id: 'demo-f-01'},
      {id: 'demo-c12', type: 'tool_called', actor: 'Investigator', time: 'T+09:12', title: 'http_probe · GET /api/invoices/{id}', summary: 'Compare the shared-object baseline with a private-object read.', ref_type: 'operation', ref_id: 'invoice'},
      {id: 'demo-c11', type: 'decision', actor: 'Brain', time: 'T+08:40', title: 'Request independent validation', summary: 'Hand the candidate and procedure to a separate validator.', ref_type: 'finding', ref_id: 'demo-f-01'}
    ]
  };

  const families = ['Object authorization', 'Reflected XSS', 'Traversal canary'];
  const rows = {
    invoice: ['confirmed', 'not_applicable', 'not_tested'],
    profile: ['tested_no_issue', 'not_applicable', 'not_applicable'],
    export: ['blocked', 'unsupported', 'not_tested'],
    search: ['tested_no_issue', 'confirmed', 'tested_no_issue'],
    file: ['tested_no_issue', 'not_applicable', 'confirmed']
  };
  Object.entries(rows).forEach(([operation, statuses]) => statuses.forEach((status, index) => {
    const complete = ['confirmed', 'tested_no_issue'].includes(status);
    const finding = status === 'confirmed' ? seed.findings.find(f => f.operation_id === operation && f.validation_status === 'CONFIRMED') : null;
    const artifacts = complete ? ['baseline', 'test', 'control'].map((purpose, artifactIndex) => {
      const source = finding ? finding.evidence[artifactIndex] : {id: 'demo-negative-' + operation + '-' + index + '-' + purpose,
        role: purpose, body: transcript('Operation: ' + operation + '\nFamily: ' + families[index] + '\n' + purpose + ': synthetic qualifying procedure record.\nNo issue demonstrated by this procedure; not a claim that the endpoint is safe.')};
      seed.evidence[source.id] = {...source, purpose, status: 'AVAILABLE', operation_id: operation, family: families[index],
        run_id: seed.run.id, snapshot_id: seed.snapshot_id, parameter: seed.operations.find(op => op.id === operation).parameter,
        identity: 'Alice / member', auth_epoch: 'demo-epoch-a', procedure_revision: 'demo-procedure-r1'};
      return source.id;
    }) : [];
    seed.coverage.push({id: 'demo-cell-' + operation + '-' + index, run_id: seed.run.id, operation_id: operation, family: families[index], status,
      identity: operation === 'export' ? 'Unknown' : 'Alice / member', auth_epoch: operation === 'export' ? null : 'demo-epoch-a',
      parameter: seed.operations.find(item => item.id === operation).parameter, snapshot_id: seed.snapshot_id,
      applicability_reason: status === 'not_applicable' ? 'This fixture operation has no applicable input/output context for this family.' : null,
      procedure_revision: complete ? 'demo-procedure-r1' : null, auth_verified: complete, evidence_complete: complete,
      evidence_refs: artifacts, finding_id: finding ? finding.id : null,
      explanation: status === 'tested_no_issue' ? 'No issue demonstrated by this procedure. Baseline and protected control are present in the synthetic fixture.' : status === 'confirmed' ? 'A confirmed synthetic finding is linked to this operation/family.' : status === 'blocked' ? 'Expected access rule, identity or effect classification is missing.' : status === 'unsupported' ? 'This transport/output context is not tested by the selected procedure.' : status === 'not_applicable' ? 'Excluded with an explicit applicability reason; not counted as tested.' : 'No qualifying procedure evidence exists yet.'});
  }));

  root.createOmnisDemo = function () {
    const state = structuredClone(seed);
    const reports = [];
    const percent = (used, limit) => Number.isFinite(used) && Number.isFinite(limit) && limit > 0 ? Math.round(100 * used / limit) : null;
    function qualifyingCell(cell) {
      const operation = state.operations.find(op => op.id === cell.operation_id);
      if (!['confirmed', 'tested_no_issue'].includes(cell.status) || !cell.auth_verified || !cell.evidence_complete ||
          !cell.procedure_revision || !cell.auth_epoch || cell.snapshot_id !== state.snapshot_id || cell.run_id !== state.run.id || !operation ||
          cell.auth_epoch !== operation.auth_epoch || cell.identity !== operation.identity || !cell.evidence_refs.length) return false;
      if (cell.status === 'confirmed' && !state.findings.some(f => f.id === cell.finding_id && f.validation_status === 'CONFIRMED' && f.operation_id === cell.operation_id)) return false;
      const artifacts = cell.evidence_refs.map(id => state.evidence[id]);
      const contextMatches = artifacts.every(a => a && a.status === 'AVAILABLE' &&
        ['run_id', 'operation_id', 'parameter', 'family', 'snapshot_id', 'identity', 'auth_epoch', 'procedure_revision'].every(key => a[key] === cell[key]));
      return contextMatches && ['baseline', 'test', 'control'].every(purpose => artifacts.some(a => a.purpose === purpose));
    }
    // A demo equality snapshot, not a cryptographic proof or a backend authorization mechanism.
    function reviewMaterial(finding) {
      const fields = ['id', 'severity', 'title', 'classification', 'operation_id', 'validation_status', 'procedure', 'rule',
        'summary', 'risk', 'severity_reason', 'preconditions', 'steps', 'poc', 'evidence', 'validation_reason', 'remediation', 'limits'];
      return JSON.stringify([state.run.id, state.snapshot_id, state.identity, fields.map(key => finding[key])]);
    }
    function reviewStatus(finding) {
      return finding.report_review.status === 'APPROVED' && finding.report_review.material_snapshot !== reviewMaterial(finding) ? 'PENDING' : finding.report_review.status;
    }
    function summary() {
      const confirmed = state.findings.filter(f => f.validation_status === 'CONFIRMED');
      const severity = Object.fromEntries(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'].map(key => [key, confirmed.filter(f => f.severity === key).length]));
      const eligible = state.coverage.filter(cell => !(cell.status === 'not_applicable' && cell.applicability_reason));
      const covered = eligible.filter(qualifyingCell).length;
      return {confirmed: confirmed.length, severity, needsReview: confirmed.filter(f => f.report_review.required && reviewStatus(f) === 'PENDING').length,
        candidates: state.findings.filter(f => f.validation_status !== 'CONFIRMED').length,
        endpoints: state.operations.length, observed: state.operations.filter(op => op.state === 'observed').length, inferred: state.operations.filter(op => op.state === 'inferred').length,
        coverage: {covered, total: eligible.length, excluded: state.coverage.length - eligible.length, percent: percent(covered, eligible.length)},
        requests: {used: state.run.requests_used, limit: state.run.request_limit, percent: percent(state.run.requests_used, state.run.request_limit)},
        time: {used: state.run.elapsed_seconds, limit: state.run.time_limit_seconds, percent: percent(state.run.elapsed_seconds, state.run.time_limit_seconds)}, llmCostUsd: state.run.llm_cost_usd};
    }
    function reviewFinding(id, decision, expectedRevision) {
      const finding = state.findings.find(f => f.id === id);
      if (!finding || !['APPROVED', 'HELD'].includes(decision)) return {ok: false, reason: 'INVALID_REVIEW'};
      if (finding.revision !== expectedRevision) return {ok: false, reason: 'STALE_REVISION'};
      if (finding.validation_status !== 'CONFIRMED' || !finding.report_review.required) return {ok: false, reason: 'TECHNICAL_VALIDATION_REQUIRED'};
      if (decision === 'APPROVED' && finding.evidence_status !== 'AVAILABLE') return {ok: false, reason: 'EVIDENCE_UNAVAILABLE'};
      finding.report_review.status = decision;
      finding.report_review.actor = 'Local operator · DEMO';
      finding.report_review.finding_revision = expectedRevision;
      finding.report_review.material_snapshot = decision === 'APPROVED' ? reviewMaterial(finding) : null;
      finding.revision += 1;
      state.revision += 1;
      return {ok: true, revision: finding.revision};
    }
    function reportEligible(finding) {
      return finding.validation_status === 'CONFIRMED' && finding.report_review &&
        typeof finding.report_review.required === 'boolean' &&
        (finding.report_review.required ? reviewStatus(finding) === 'APPROVED' : finding.report_review.status === 'NOT_REQUIRED');
    }
    function generateReport() {
      const report = {id: 'demo-report-' + (reports.length + 1), schema_version: state.schema_version, demo: true,
        notice: 'DEMO ONLY — NOT AN ASSESSMENT. No target requests or validation were executed.',
        source_snapshot: state.snapshot_id, source_revision: state.revision, run_id: state.run.id,
        engagement: structuredClone(state.engagement), findings: structuredClone(state.findings.filter(reportEligible)),
        coverage: structuredClone(summary().coverage), limits: ['Synthetic UI fixture only.', 'Current evidence availability must be checked separately.', 'Candidate and unreviewed-required records are excluded.']};
      reports.push(structuredClone(report));
      return report;
    }
    return {state, summary, qualifyingCell, reviewFinding, reviewStatus, reportEligible, generateReport, reports: () => structuredClone(reports)};
  };
})(globalThis);
