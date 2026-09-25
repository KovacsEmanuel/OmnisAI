/* Offline presentation of prototype-model.js. No API calls or assessment execution. */
(function (root) {
  'use strict';
  const model = root.createOmnisDemo();
  const state = model.state;
  const $ = id => document.getElementById(id);
  const page = name => document.querySelector('[data-page="' + name + '"]');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const colors = {CRITICAL:'var(--crit)',HIGH:'var(--high)',MEDIUM:'var(--med)',LOW:'var(--low)',INFO:'var(--info-sev)'};
  const severityNames = {CRITICAL:'Critical',HIGH:'High',MEDIUM:'Medium',LOW:'Low',INFO:'Info'};
  let findingFilter = 'confirmed';
  let streamKind = 'all';
  let streamActor = 'all';
  const time = seconds => Math.floor(seconds / 60).toString().padStart(2, '0') + ':' + (seconds % 60).toString().padStart(2, '0');
  const pct = value => value === null ? 'N/A' : value + '%';
  const money = value => Number.isFinite(value) ? '$' + value.toFixed(2) : 'Unknown';
  const operation = id => state.operations.find(op => op.id === id);
  const confirmed = () => state.findings.filter(f => f.validation_status === 'CONFIRMED');
  const pending = () => confirmed().filter(f => f.report_review.required && model.reviewStatus(f) === 'PENDING');

  const activeCount = () => ['RUNNING','PAUSING','PAUSED','STOPPING'].includes(state.run.status) ? 1 : 0;
  const phase = () => state.run.status === 'RUNNING' ? state.run.phase : state.run.status;
  const bezel = (body, classes = '', attrs = '') => '<div class="bezeled ' + classes + '" ' + attrs + '><div class="core">' + body + '</div></div>';
  const button = (label, attrs, primary = false, icon = '→') => '<button class="pill-button' + (primary ? ' primary' : '') + '" ' + attrs + '><span class="button-cap">' + esc(label) + '</span><span class="button-icon" aria-hidden="true">' + icon + '</span></button>';
  const chip = (label, kind = '') => '<span class="chip ' + kind + '">' + esc(label) + '</span>';
  const sev = severity => '<span class="sev-tag sev-' + severity.toLowerCase() + '">' + esc(severityNames[severity]) + '</span>';
  const head = (title, meta = '') => '<div class="card-head"><h2>' + esc(title) + '</h2>' + (meta ? '<span class="meta">' + esc(meta) + '</span>' : '') + '</div>';
  const progress = (value, label) => '<div class="progress-track" role="img" aria-label="' + esc(label) + '"><i style="width:' + Math.max(0, Math.min(100, value ?? 0)) + '%"></i></div>';
  function bars(findings) {
    const total = findings.length;
    return '<div class="severity-bars" role="img" aria-label="' + total + ' confirmed demo findings by severity">' + Object.keys(colors).map(key => {
      const count = findings.filter(f => f.severity === key).length;
      return count ? '<i style="width:' + 100 * count / total + '%;background:' + colors[key] + '"></i>' : '';
    }).join('') + '</div>';
  }
  function metric(key, label, value, note, kind = '') {
    return bezel('<div class="metric-label">' + esc(label) + '</div><div class="metric-value">' + esc(value) + '</div><div class="metric-note">' + esc(note) + '</div>', 'metric-card ' + kind, 'data-metric="' + key + '"');
  }
  function attention(globalView = false) {
    const rows = [];
    if (state.action_approval.status === 'PENDING') {
      rows.push('<div class="attention-row"><span class="attention-dot"></span><div class="attention-copy"><strong>Session setup requires approval</strong><p>' + (globalView ? 'Invoice lab · ' : '') + 'SESSION_CHANGE · /login · Alice</p></div>' + button('Review action', 'data-review-action' + (globalView ? '' : ' id="approval-open-inline"')) + '</div>');
    }
    pending().forEach(f => rows.push('<div class="attention-row">' + sev(f.severity) + '<div class="attention-copy"><strong>' + esc(f.title) + '</strong><p>' + (globalView ? 'Invoice lab · ' : '') + 'Validator confirmed · report review required</p></div>' + button('Review finding', 'data-open-finding="' + f.id + '"', true) + '</div>'));
    return bezel(head(globalView ? 'Needs your review' : 'Needs you', rows.length + ' pending') + (rows.join('') || '<p class="attention-empty">No operator decisions pending in this demo snapshot.</p>'), 'attention-card');
  }
  function renderDashboard() {
    const s = model.summary();
    const hero = '<div class="hero-layout"><div class="hero-copy"><h1>Your security<br><span>workspace.</span></h1><p>' + activeCount() + ' engagement active. ' + s.confirmed + ' findings confirmed; ' + s.needsReview + ' awaiting your review.</p></div>' + bezel('<p class="eyebrow">Start a new engagement</p><label class="sr-only" for="dashboard-target">Demo target</label><div class="start-target"><span aria-hidden="true">⌕</span><input id="dashboard-target" value="https://lab.invalid" readonly></div>' + button('New engagement', 'data-go="new-engagement"', true) + '<p class="hint">Scope and authorization before any live probe.</p>', 'start-card') + '</div>';
    const metrics = '<div class="metric-grid" id="dashboard-metrics">' +
      metric('active', 'Active engagements', activeCount(), 'Single active run · demo') +
      metric('confirmed', 'Confirmed findings', s.confirmed, s.needsReview + ' awaiting report review') +
      metric('review', 'Report reviews', s.needsReview, 'Technical verdict stays separate') +
      metric('coverage', 'Active-run coverage', pct(s.coverage.percent), s.coverage.covered + ' / ' + s.coverage.total + ' applicable checks') + '</div>';
    const pulse = '<div class="pulse-bar"><div class="pulse-item"><b>' + esc(state.run.phase_label) + '</b><span>phase · snapshot</span></div><div class="pulse-item"><b>' + time(state.run.elapsed_seconds) + '</b><span>elapsed · demo snapshot</span></div><div class="pulse-item"><b>' + s.requests.used + ' / ' + s.requests.limit + '</b><span>requests / limit</span></div><div class="pulse-item"><b>' + money(s.llmCostUsd) + '</b><span>AI cost · snapshot</span></div></div>';
    const engagement = bezel('<div class="eng-top"><span class="run-stage"><i class="live-dot"></i><span data-run-label>' + esc(state.run.status) + ' · demo</span></span><span class="mono">' + time(state.run.elapsed_seconds) + ' elapsed</span></div><h3>' + esc(state.engagement.name) + '</h3><p class="target">' + esc(state.engagement.origin) + '</p><div class="brain-line"><span>brain →</span><strong data-demo-phase>' + esc(phase()) + '</strong>' + chip('Validator · demo') + '</div>' + bars(confirmed()) + '<div class="budget-label"><span>Request budget</span><b>' + s.requests.used + ' / ' + s.requests.limit + '</b></div>' + progress(s.requests.percent, 'Demo request budget ' + s.requests.used + ' of ' + s.requests.limit) + '<div class="eng-bottom" style="margin-top:18px"><span><b class="number">' + s.confirmed + '</b><small>confirmed</small></span><span><b class="number">' + s.endpoints + '</b><small>endpoints</small></span>' + button('Open engagement', 'data-go="overview"', true) + '</div>', 'engagement-main');
    const fresh = bezel('<span class="plus" aria-hidden="true">+</span><h3>New engagement</h3><p>Target, scope and rules. Start only after preflight.</p>' + button('Set up', 'data-go="new-engagement"'), 'new-card');
    page('dashboard').innerHTML = hero + attention(true) + metrics + pulse + '<div class="section-title"><h2>Recent engagements</h2><span class="small muted">One synthetic engagement</span></div><div class="engagement-bento">' + engagement + fresh + '</div>';
  }
  function phaseStrip(id) {
    const current = phase();
    const tool = state.events.find(event => event.type === 'tool_called');
    return bezel('<div class="phase-main"><i class="live-dot"></i><span class="phase-prefix">brain →</span><strong class="phase-name" data-demo-phase>' + esc(current) + '</strong>' + chip('DEMO snapshot') + '<span class="phase-tool">last tool <b>' + esc(tool ? tool.title : 'No tool event') + '</b></span></div><div class="phase-vitals"><div><b>' + time(state.run.elapsed_seconds) + '</b><span>elapsed</span></div><div><b>' + state.run.requests_used + '</b><span>requests</span></div><div><b>' + model.summary().candidates + '</b><span>candidate</span></div></div>', 'phase-card', 'id="' + id + '"');
  }
  function topFindings() {
    return bezel(head('Top findings', 'Confirmed only') + confirmed().map(f => {
      const op = operation(f.operation_id);
      return '<div class="top-finding-row">' + sev(f.severity) + '<div class="finding-copy"><button class="finding-title" data-open-finding="' + f.id + '">' + esc(f.title) + '<span class="route">' + esc(op.method + ' ' + op.path) + '</span></button></div>' + chip(model.reviewStatus(f) === 'PENDING' ? 'review needed' : 'confirmed', model.reviewStatus(f) === 'PENDING' ? 'review' : 'confirmed') + '</div>';
    }).join(''), '', 'id="top-findings"');
  }
  function severityPanel() {
    const s = model.summary();
    let offset = 0;
    const stops = [];
    Object.entries(s.severity).forEach(([key, count]) => {
      if (!count) return;
      const start = offset;
      offset += 100 * count / s.confirmed;
      stops.push(colors[key] + ' ' + start + '% ' + offset + '%');
    });
    const background = stops.length ? 'conic-gradient(from -90deg,' + stops.join(',') + ')' : 'var(--raised)';
    return bezel(head('Severity', s.confirmed + ' confirmed') + '<div class="severity-layout"><div class="severity-donut" style="background:' + background + '" role="img" aria-label="Confirmed demo findings: ' + esc(Object.entries(s.severity).map(([k,v]) => severityNames[k] + ' ' + v).join(', ')) + '"><div class="donut-label"><b id="severity-total">' + s.confirmed + '</b><span>findings</span></div></div><ul class="severity-legend">' + Object.keys(colors).map(key => '<li><i style="background:' + colors[key] + '"></i>' + severityNames[key] + '<strong>' + s.severity[key] + '</strong></li>').join('') + '</ul></div>');
  }
  function budgetPanel() {
    const s = model.summary();
    return bezel(head('Budget & gates', 'This run · demo') + '<div class="budget-item"><div class="budget-label"><span>Requests</span><b>' + s.requests.used + ' / ' + s.requests.limit + '</b></div>' + progress(s.requests.percent, 'Requests ' + s.requests.used + ' of ' + s.requests.limit) + '</div><div class="budget-item"><div class="budget-label"><span>Time budget</span><b>' + time(s.time.used) + ' / ' + time(s.time.limit) + '</b></div>' + progress(s.time.percent, 'Time budget ' + s.time.used + ' of ' + s.time.limit + ' seconds') + '</div><div class="budget-foot"><span>Validation reserve <b>' + state.run.validation_reserve_percent + '%</b></span><span>AI cost <b>' + money(s.llmCostUsd) + '</b></span></div><div class="gate-pills"><span>Scope pinned · demo</span><span>Bounded requests</span><span>Evidence gate</span><span>' + s.needsReview + ' report review</span></div>', '', 'id="budget-panel"');
  }
  function contextPanel() {
    return bezel(head('Run snapshot', state.snapshot_id) + '<dl class="context-list"><div><dt>Run</dt><dd class="mono">' + esc(state.run.id) + '</dd></div><div><dt>Identity</dt><dd>Alice / member</dd></div><div><dt>Auth epoch</dt><dd class="mono">' + esc(state.identity.auth_epoch) + '</dd></div><div><dt>Validator</dt><dd>Independent context</dd></div><div><dt>Provider</dt><dd>Not connected · prototype</dd></div></dl><div class="divider"><button class="quiet-link" data-go="investigations">Inspect candidate & validation tasks →</button></div>');
  }
  function renderOverview() {
    const s = model.summary();
    page('overview').innerHTML = '<h1 class="sr-only">Engagement overview</h1>' + phaseStrip('overview-phase') + '<div class="plan-progress" id="overview-progress"><span>CHECKS</span>' + progress(s.coverage.percent, 'Procedure coverage ' + s.coverage.covered + ' of ' + s.coverage.total) + '<span class="progress-caption">' + s.coverage.covered + ' / ' + s.coverage.total + ' applicable · ' + esc(state.run.phase_label) + '</span></div>' + attention() +
      '<div class="metric-grid five" id="overview-metrics">' + metric('confirmed', 'Confirmed', s.confirmed, 'Validator + evidence gate') + metric('critical', 'Critical', s.severity.CRITICAL, 'Confirmed findings', 'critical') + metric('high', 'High', s.severity.HIGH, 'Confirmed findings', 'high') + metric('coverage', 'Coverage', pct(s.coverage.percent), s.coverage.covered + ' / ' + s.coverage.total + ' applicable checks') + metric('endpoints', 'Endpoints', s.endpoints, s.observed + ' observed · ' + s.inferred + ' inferred') + '</div><div class="overview-panels">' + topFindings() + severityPanel() + '</div><div class="overview-panels">' + budgetPanel() + contextPanel() + '</div>';
  }
  const kindLabel = {decision:'Decision',tool_called:'Tool called',tool_result:'Tool result',endpoint:'Endpoint',validation:'Validation',approval:'Approval'};
  function renderStream() {
    page('stream').innerHTML = '<h1 class="sr-only">Brain stream activity</h1>' + phaseStrip('stream-phase') + '<div class="stream-toolbar"><div class="filter-pills" aria-label="Event kinds">' + [['all','All'],['decision','Decisions'],['tools','Tools'],['endpoint','Endpoints'],['validation','Validation']].map(([key,label]) => '<button data-stream-kind="' + key + '" aria-pressed="' + (streamKind === key) + '">' + label + '</button>').join('') + '</div><label>Actor <select id="stream-filter"><option value="all">All actors</option><option value="brain">Brain</option><option value="investigator">Investigator</option><option value="validator">Validator</option></select></label></div>' + bezel('<div class="card-head"><h2>Brain stream</h2><span class="meta" id="stream-status" role="status"></span></div><div id="brain-stream" class="stream-log" tabindex="0" role="region" aria-label="Engagement decision stream">' + state.events.map(event => {
      const action = event.ref_type === 'operation' ? '<button class="quiet-link" data-operation-link="' + esc(event.ref_id) + '">Inspect operation →</button>' : event.ref_type === 'candidate' ? '<button class="quiet-link" data-go="investigations">Inspect blocked task</button>' : '<button class="quiet-link" data-open-finding="' + esc(event.ref_id) + '">Inspect finding</button>';
      return '<article class="stream-event" data-actor="' + event.actor.toLowerCase() + '" data-event-kind="' + event.type + '"><div class="stream-entry"><header><span class="stream-time">' + esc(event.time) + '</span><span class="chip">' + esc(kindLabel[event.type]) + '</span><span>' + esc(event.actor) + '</span><h3>' + esc(event.title) + '</h3><span class="event-id">' + esc(event.id) + '</span></header><section><p>' + esc(event.summary) + '</p>' + action + '</section></div></article>';
    }).join('') + '<p id="stream-empty" class="empty-inline" hidden>No events match these filters.</p></div>');
    $('stream-filter').value = streamActor;
    applyStreamFilters();
  }
  function applyStreamFilters() {
    const entries = [...document.querySelectorAll('#brain-stream [data-event-kind]')];
    entries.forEach(entry => {
      const kind = streamKind === 'all' || (streamKind === 'tools' ? ['tool_called','tool_result'].includes(entry.dataset.eventKind) : entry.dataset.eventKind === streamKind);
      entry.hidden = !kind || (streamActor !== 'all' && entry.dataset.actor !== streamActor);
    });
    const count = entries.filter(entry => !entry.hidden).length;
    $('stream-status').textContent = count + ' of ' + state.events.length + ' demo events · newest first';
    $('stream-empty').hidden = count !== 0;
    document.querySelectorAll('[data-stream-kind]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.streamKind === streamKind)));
  }
  function demoFindingTools() {
    return '<details class="prototype-tools" id="finding-demo-tools"><summary>Finding demo controls · design testing only</summary><p>Simulated UI states only. These controls do not execute a test.</p><label class="field"><span>Current evidence state · DEMO</span><select id="finding-evidence-state"><option>AVAILABLE</option><option>MISSING</option><option>TRUNCATED</option><option>CORRUPT</option><option>DELETED</option></select></label><div class="tool-actions"><button id="replay-preview">Preview replay requirements</button><button id="retest-preview">Preview retest state</button></div><p id="replay-message" class="statusline" role="status"></p><p id="retest-state" class="statusline" role="status"></p></details>';
  }
  function findingDetail(f) {
    const first = f.id === 'demo-f-01';
    const review = model.reviewStatus(f);
    const available = f.evidence_status === 'AVAILABLE';
    const reviewText = review === 'APPROVED' ? 'Approved for report' : review === 'HELD' ? 'Held from report' : 'Operator review required';
    const evidence = '<div class="evidence-pair"' + (first ? ' id="evidence-bundle"' : '') + (available ? '' : ' hidden') + '>' + f.evidence.map((artifact,index) => '<details class="evidence-item" id="' + (first ? ['baseline-evidence','replay-evidence','control-evidence'][index] : f.id + '-evidence-' + index) + '"><summary>' + esc(artifact.role) + ' <span class="mono muted">/ ' + esc(artifact.id) + '</span></summary><pre class="evidence">' + esc(artifact.body) + '</pre></details>').join('') + '</div>';
    const reviewBox = f.report_review.required ? '<section class="verdict-box review-box"><span class="verdict-mark" aria-hidden="true">◇</span><div class="verdict-copy"><h3>' + reviewText + '</h3><p>Technical verdict: CONFIRMED. Your decision controls report inclusion, not technical validity. ' + (review === 'APPROVED' ? 'Accepted by Local operator · DEMO.' : review === 'HELD' ? 'The finding remains confirmed and is excluded from new reports.' : 'Inspect the claim and evidence before accepting it for the report.') + '</p><div class="review-actions">' + button('Accept for report', 'data-review-finding="' + f.id + '" data-review-revision="' + f.revision + '" data-review-decision="APPROVED"' + (!available || review === 'APPROVED' ? ' disabled' : ''), true, '✓') + button('Hold', 'data-review-finding="' + f.id + '" data-review-revision="' + f.revision + '" data-review-decision="HELD"' + (review === 'HELD' ? ' disabled' : ''), false, '−') + '</div>' + (!available ? '<p>New acceptance is unavailable while required evidence is missing.</p>' : '') + '</div></section>' : '';
    return '<div class="finding-body"><div class="finding-context"' + (first ? ' id="finding-context"' : '') + '>' + chip(f.id) + chip(state.run.id + ' / ' + state.snapshot_id) + chip('Alice / member / ' + state.identity.auth_epoch) + chip(f.rule) + '</div><div class="finding-sections"><div class="detail-pair"><section class="detail-section"><h2>Summary</h2><p>' + esc(f.summary) + '</p></section><section class="detail-section"><h2>Risk & impact</h2><p>' + esc(f.risk) + '</p><p>' + esc(f.severity_reason) + '</p></section></div><section class="detail-section"><h2>Proof of concept · demo</h2><pre class="poc-block">' + esc(f.poc) + '</pre></section><section class="detail-section"><h2>Reproduction</h2><ol class="repro-steps">' + f.steps.map(step => '<li><div>' + esc(step) + '</div></li>').join('') + '</ol></section><section class="detail-section"><h2>Evidence</h2><p' + (first ? ' id="evidence-availability" role="status"' : '') + '>' + esc(f.evidence_status) + (available ? ' · synthetic transcripts only' : ' · required evidence unavailable for replay. Historical verdict retained.') + '</p>' + evidence + '</section><section class="verdict-box"><span class="verdict-mark" aria-hidden="true">✓</span><div class="verdict-copy"><h2>Validator decision</h2><p' + (first ? ' id="finding-verdict"' : '') + '>CONFIRMED · ' + esc(f.validator_id) + ' · DEMO</p><p>' + esc(f.validation_reason) + '</p></div></section>' + reviewBox + '<div class="detail-pair"><section class="detail-section"><h2>Remediation</h2><p>' + esc(f.remediation) + '</p></section><section class="detail-section"><h2>Preconditions & limits</h2><p>' + f.preconditions.map(esc).join('<br>') + '</p><p>' + esc(f.limits) + '</p></section></div><div><button class="quiet-link" data-go="reports">Inspect report snapshots →</button></div></div>' + (first ? demoFindingTools() : '') + '</div>';
  }
  function renderFindings(openIds) {
    const open = openIds || new Set([...document.querySelectorAll('[data-finding][open]')].map(node => node.dataset.finding));
    const toolsOpen = $('finding-demo-tools')?.open;
    const s = model.summary();
    page('findings').innerHTML = '<h1 class="sr-only">Findings</h1><div class="filter-pills" aria-label="Finding views"><button data-finding-filter="confirmed" aria-pressed="' + (findingFilter === 'confirmed') + '">Confirmed<span class="filter-count">' + s.confirmed + '</span></button><button data-finding-filter="review" aria-pressed="' + (findingFilter === 'review') + '">Needs review<span class="filter-count">' + s.needsReview + '</span></button><button data-go="investigations">Candidates<span class="filter-count">' + s.candidates + ' ↗</span></button><button data-finding-filter="held" aria-pressed="' + (findingFilter === 'held') + '">Held from report<span class="filter-count">' + confirmed().filter(f => model.reviewStatus(f) === 'HELD').length + '</span></button></div>' + bezel(confirmed().map(f => {
      const op = operation(f.operation_id);
      const status = model.reviewStatus(f);
      const visible = findingFilter === 'confirmed' || (findingFilter === 'review' ? status === 'PENDING' && f.report_review.required : status === 'HELD');
      return '<details class="finding-record" data-finding="' + f.id + '" data-validation="CONFIRMED"' + (open.has(f.id) ? ' open' : '') + (visible ? '' : ' hidden') + '><summary class="finding-row">' + sev(f.severity) + '<span class="finding-heading"><strong>' + esc(f.title) + '</strong><span class="mono">' + esc(op.method + ' ' + op.path) + ' · ' + esc(f.classification) + '</span><span class="finding-provenance">found <span>' + esc(f.investigator_id) + '</span> → validated <span>' + esc(f.validator_id) + '</span></span></span>' + chip(status === 'PENDING' && f.report_review.required ? 'review required' : status === 'HELD' ? 'held from report' : 'confirmed', status === 'PENDING' && f.report_review.required ? 'review' : 'confirmed') + '<span class="finding-chevron" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m6 9 6 6 6-6"/></svg></span></summary>' + findingDetail(f) + '</details>';
    }).join('') + '<p class="empty-inline" id="finding-empty" hidden>No findings match this view.</p>', 'findings-shell') + '<p class="stream-note">DEMO data. Candidates and inconclusive outcomes are not confirmed vulnerabilities.</p>';
    $('finding-empty').hidden = [...document.querySelectorAll('[data-finding]')].some(node => !node.hidden);
    $('finding-evidence-state').value = state.findings[0].evidence_status;
    $('replay-preview').disabled = state.findings[0].evidence_status !== 'AVAILABLE';
    if (toolsOpen) $('finding-demo-tools').open = true;
  }
  const statusNames = {confirmed:'Confirmed',tested_no_issue:'Tested',not_tested:'Not tested',not_applicable:'N/A',blocked:'Blocked',unsupported:'Unsupported'};
  function renderCoverage() {
    const s = model.summary();
    $('coverage-panel').innerHTML = '<div class="coverage-summary"><div><strong>' + pct(s.coverage.percent) + '</strong> <span>' + s.coverage.covered + ' / ' + s.coverage.total + ' applicable checks · ' + s.coverage.excluded + ' justified N/A</span></div>' + chip(state.snapshot_id + ' · demo') + '</div>' + progress(s.coverage.percent, 'Demo coverage ' + s.coverage.covered + ' of ' + s.coverage.total) + '<div class="coverage-legend"><span><i style="background:var(--accent)"></i>Confirmed / tested</span><span><i style="background:var(--high)"></i>Blocked</span><span><i style="background:var(--line)"></i>Not tested / unsupported</span><span>Run denominator; filters change visible operations only.</span></div><div class="coverage-grid">' + state.operations.map(op => '<article class="coverage-operation ' + op.state + '" data-coverage-operation data-operation="' + op.id + '"><h3>' + esc(op.method + ' ' + op.path) + '</h3><p class="source">' + esc(op.identity) + ' · ' + esc(op.state) + '</p>' + state.coverage.filter(cell => cell.operation_id === op.id).map(cell => '<button class="coverage-cell ' + cell.status + '" data-coverage="' + cell.status + '" data-cell-id="' + cell.id + '" data-family="' + esc(cell.family) + '"><span>' + esc(cell.family) + '</span><span class="cell-state">' + esc(['confirmed','tested_no_issue'].includes(cell.status) && !model.qualifyingCell(cell) ? 'Evidence unavailable' : statusNames[cell.status]) + '</span></button>').join('') + '</article>').join('') + '</div><section class="panel coverage-detail"><h2 id="coverage-heading">Select a cell to inspect the test contract</h2><p id="coverage-detail" class="muted">Coverage does not certify that an endpoint is safe. Unknown applicability stays visible in the denominator.</p><pre id="coverage-evidence" class="evidence" hidden></pre></section>';
  }
  function renderEndpoints() {
    $('surface-rows').innerHTML = state.operations.map(op => '<tr data-operation="' + op.id + '"' + (op.id === 'invoice' ? ' class="selected-row"' : '') + '><td><span class="method">' + op.method + '</span><button class="rowbutton" data-inspect="' + op.id + '">' + esc(op.path) + '</button><br><span class="small muted">' + esc(op.state === 'observed' ? 'Observed · demo fixture' : 'Inferred · not exercised') + '</span></td><td>' + esc(op.identity === 'Unknown' ? 'Unknown' : 'Alice') + '</td><td>' + esc(op.source) + '</td></tr>').join('');
    document.querySelector('.tree ul').innerHTML = '<li>lab.invalid</li>' + state.operations.map(op => '<li class="indent' + (op.id === 'invoice' ? ' selected' : '') + '" data-tree-operation="' + op.id + '">' + esc(op.path) + '</li>').join('');
  }
  function renderReports() {
    const eligible = confirmed().filter(model.reportEligible);
    const s = model.summary();
    const reports = model.reports().reverse();
    page('reports').innerHTML = '<div class="heading"><div><h1>Reports</h1><p>Confirmed findings, evidence and limits from one snapshot.</p></div>' + button('Generate demo report', 'id="generate-demo-report"', true, '↓') + '</div><div class="report-readiness">' + bezel('<strong>' + eligible.length + '</strong><span>confirmed & eligible</span>') + bezel('<strong>' + s.needsReview + '</strong><span>awaiting manual review</span>') + bezel('<strong>' + s.candidates + '</strong><span>candidate excluded</span>') + '</div><div class="report-notice">Only eligible CONFIRMED findings. Pending/held reviews and candidates are excluded. DEMO export — not an assessment.</div><p id="report-state" role="status" tabindex="-1"></p><div id="report-history">' + (reports.length ? reports.map(report => bezel('<div class="report-icon" aria-hidden="true">▤</div><div class="report-copy"><h2>Invoice lab · ' + esc(report.id) + '</h2><p>' + esc(report.source_snapshot) + ' · revision ' + report.source_revision + ' · ' + report.findings.length + ' confirmed</p>' + bars(report.findings) + chip('Immutable DEMO snapshot') + '</div><div class="report-actions">' + button('HTML', 'data-report-export="' + report.id + '" data-export-format="html"', false, '↓') + button('JSON', 'data-report-export="' + report.id + '" data-export-format="json"', false, '↓') + '</div>', 'report-card', 'data-report-id="' + report.id + '"')).join('') : bezel(head('Ready to generate', 'DEMO') + '<p class="muted">Create a snapshot from the eligible confirmed findings. Later reviews never rewrite an existing report.</p>')) + '</div>';
  }
  function syncBadges() {
    const s = model.summary();
    document.querySelectorAll('[data-findings-count]').forEach(node => node.textContent = s.confirmed);
    document.querySelectorAll('[data-coverage-count]').forEach(node => node.textContent = pct(s.coverage.percent));
  }
  function renderProjections(openIds) {
    renderDashboard(); renderOverview(); renderFindings(openIds); renderReports(); syncBadges();
  }
  function notice(text, error = false) {
    const target = $('ui-feedback');
    target.hidden = false; target.setAttribute('role', error ? 'alert' : 'status'); target.textContent = text;
  }
  function openFinding(id) {
    const finding = state.findings.find(f => f.id === id);
    if (!finding) return;
    if (finding.validation_status !== 'CONFIRMED') { root.showView('investigations'); return; }
    findingFilter = 'confirmed'; renderFindings(new Set([id])); root.showView('findings');
    root.focusContent(document.querySelector('[data-finding="' + id + '"] > summary'));
  }
  function updateRunState(status) {
    state.run.status = status;
    renderDashboard(); renderOverview();
    document.querySelectorAll('[data-demo-phase]').forEach(node => node.textContent = phase());
  }
  function approveAction() {
    state.action_approval.status = 'APPROVED'; state.revision += 1;
    renderDashboard(); renderOverview();
    notice('Demo action approved locally. No request or authorization was sent to a backend.');
  }
  function reportHtml(report) {
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"><title>Omnis DEMO report</title><style>body{font:16px/1.6 system-ui;max-width:850px;margin:40px auto;padding:24px;color:#222}header{border:2px solid #985b20;padding:20px}article{border-top:1px solid #bbb;margin-top:28px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eee;padding:16px}small{color:#555}@media print{body{font-size:12pt}}</style></head><body><header><h1>Omnis · DEMO report</h1><p>' + esc(report.notice) + '</p></header><p>' + esc(report.id + ' / ' + report.source_snapshot + ' / ' + report.run_id) + '</p><p>' + report.findings.length + ' confirmed findings in this immutable demo snapshot.</p>' + report.findings.map(f => '<article><h2>' + esc(f.severity + ' · ' + f.title) + '</h2><p>' + esc(f.summary) + '</p><h3>Risk & scope</h3><p>' + esc(f.risk) + '</p><h3>PoC · synthetic</h3><pre>' + esc(f.poc) + '</pre><h3>Reproduction</h3><ol>' + f.steps.map(step => '<li>' + esc(step) + '</li>').join('') + '</ol><h3>Evidence</h3><p>Availability at generation: ' + esc(f.evidence_status) + '</p>' + f.evidence.map(a => '<h4>' + esc(a.role + ' / ' + a.id) + '</h4><pre>' + esc(a.body) + '</pre>').join('') + '<h3>Validation and review</h3><p>' + esc(f.validation_status + ' / ' + f.validator_id + ' / review: ' + f.report_review.status) + '</p><p>' + esc(f.validation_reason) + '</p><h3>Remediation</h3><p>' + esc(f.remediation) + '</p><small>' + esc(f.limits) + '</small></article>').join('') + '<h2>Coverage & limits</h2><p>' + report.coverage.covered + ' / ' + report.coverage.total + ' applicable synthetic checks.</p><ul>' + report.limits.map(limit => '<li>' + esc(limit) + '</li>').join('') + '</ul></body></html>';
  }
  function exportReport(id, format) {
    if (!['json','html'].includes(format)) return;
    const report = model.reports().find(item => item.id === id);
    if (!report) return;
    const blob = new Blob([format === 'json' ? JSON.stringify(report, null, 2) : reportHtml(report)], {type: format === 'json' ? 'application/json' : 'text/html'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a'); link.href = url; link.download = 'omnis-DEMO-' + id + '.' + format;
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  document.addEventListener('click', event => {
    const b = event.target.closest('button'); if (!b) return;
    if (b.hasAttribute('data-open-finding')) { openFinding(b.dataset.openFinding); return; }
    if (b.hasAttribute('data-review-action')) { root.showView('overview'); root.openDialog('approval-dialog'); return; }
    if (b.hasAttribute('data-stream-kind')) { streamKind = b.dataset.streamKind; applyStreamFilters(); return; }
    if (b.hasAttribute('data-finding-filter')) { findingFilter = b.dataset.findingFilter; renderFindings(); document.querySelector('[data-finding-filter="' + findingFilter + '"]').focus(); return; }
    if (b.hasAttribute('data-review-finding')) {
      const id = b.dataset.reviewFinding;
      const result = model.reviewFinding(id, b.dataset.reviewDecision, Number(b.dataset.reviewRevision));
      if (!result.ok) { notice('Review not applied: ' + result.reason + '. No technical verdict changed.', true); return; }
      findingFilter = 'confirmed'; renderProjections(new Set([id]));
      notice('Demo report review updated. Technical verdict unchanged; existing snapshots retained.');
      root.focusContent(document.querySelector('[data-finding="' + id + '"] > summary')); return;
    }
    if (b.id === 'generate-demo-report') { const report = model.generateReport(); renderReports(); $('report-state').textContent = 'Created ' + report.id + ' with ' + report.findings.length + ' confirmed demo findings. No assessment was executed.'; $('generate-demo-report').focus(); return; }
    if (b.hasAttribute('data-report-export')) { exportReport(b.dataset.reportExport, b.dataset.exportFormat); return; }
    if (b.id === 'replay-preview') { $('replay-message').textContent = 'No replay was executed. Real replay requires intact evidence, fresh authorization, verified identity, scope, policy and budget.'; return; }
    if (b.id === 'retest-preview') $('retest-state').textContent = 'RETEST_INCONCLUSIVE · demo: auth expired. This is not FIXED.';
  });
  document.addEventListener('change', event => {
    if (event.target.id === 'stream-filter') { streamActor = event.target.value; applyStreamFilters(); }
    if (event.target.id === 'finding-evidence-state') {
      const f = state.findings[0]; f.evidence_status = event.target.value;
      f.evidence.forEach(a => { state.evidence[a.id].status = f.evidence_status; });
      state.revision += 1;
      renderDashboard(); renderOverview(); renderFindings(); renderCoverage(); renderReports(); syncBadges();
      if (typeof root.filterRows === 'function') root.filterRows();
      $('finding-demo-tools').open = true; $('finding-evidence-state').focus();
    }
  });
  renderProjections(); renderStream(); renderCoverage(); renderEndpoints();
  root.OmnisUI = {model, openFinding, updateRunState, approveAction, renderProjections, applyStreamFilters, reportHtml, notice};
})(globalThis);
