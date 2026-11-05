// Opt-in live S1. Manual normal Settings + human CLI publication; never scripted inference.
import assert from 'node:assert/strict';

const model = 'deepseek/deepseek-v4.1-flash';
const input = 'Read this synthetic non-secret context with Recon; report its stored read reference to Brain. No targets.';

export function liveSetupReady(settings, library, publications) {
  const selection = settings?.selection;
  return Array.isArray(publications) && publications.length === 1 && Boolean(selection) &&
    ['brain', 'recon'].every(role => {
      const choice = selection[role] ?? selection.default;
      return choice?.model === model && choice.output_tokens === 1024 &&
        settings.connections.some(c => c.provider === 'openrouter' && c.enabled && c.connection_id === choice.connection_id && c.revision === choice.connection_revision) &&
        library.entries.some(e => e.model === model && e.output_tokens === 1024 && e.connection_id === choice.connection_id && e.connection_revision === choice.connection_revision);
    });
}

if (process.argv[2] === '--source-check') {
  const choice = { model, output_tokens: 1024, connection_id: 'source', connection_revision: 1 };
  const settings = { selection: { default: choice }, connections: [{ connection_id: 'source', revision: 1, provider: 'openrouter', enabled: true }] };
  const library = { entries: [choice] };
  assert.equal(liveSetupReady(settings, library, [{}]), true);
  for (const mutation of [{ model: 'other' }, { output_tokens: 1025 }, { connection_revision: 2 }]) {
    assert.equal(liveSetupReady({ ...settings, selection: { default: { ...choice, ...mutation } } }, library, [{}]), false);
  }
  assert.equal(liveSetupReady(settings, { entries: [] }, [{}]), false);
  assert.equal(liveSetupReady(settings, library, []), false);
  assert.equal(liveSetupReady({ ...settings, selection: null }, library, [{}]), false);
  assert.equal(liveSetupReady({ ...settings, connections: [{ ...settings.connections[0], provider: 'orcarouter' }] }, library, [{}]), false);
  console.log('S1_LIVE_READY_SOURCE_PASS (no browser, key, model or publication)');
}

export async function runS1Live({ page, check, paired, origin }) {
  const read = path => page.evaluate(async path => {
    const response = await fetch(path);
    if (!response.ok) throw new Error('Live S1 public read unavailable');
    return response.json();
  }, path);
  await paired();
  await page.goto(`${origin}/settings/providers`);
  // No DOM input inspection, screenshots, traces or automatic key entry on this path.
  const preparedUntil = performance.now() + 600000;
  let ready = false;
  while (performance.now() < preparedUntil) {
    const [settings, library, publications] = await Promise.all([
      read('/api/v1/settings/providers'), read('/api/v1/settings/models'), read('/api/v1/runs/publications'),
    ]);
    if (liveSetupReady(settings, library, publications)) { ready = true; break; }
    await page.waitForTimeout(1000);
  }
  assert.ok(ready, 'Prerequisite: manual key Save, fresh metadata, exact model/cap assignments and human core publication');
  await page.getByRole('link', { name: 'Home', exact: true }).click();
  await page.getByRole('link', { name: /New engagement/ }).first().click();
  await page.getByLabel('Engagement name').fill('S1 live synthetic inert run');
  await page.getByLabel('Authorization owner').fill('Synthetic fixture operator');
  await page.getByLabel('Authorization statement').fill('Inert context only; no target traffic');
  await page.getByLabel('Valid from (UTC)').fill('2030-01-01T00:00:00Z');
  await page.getByLabel('Valid until (UTC)').fill('2030-12-31T00:00:00Z');
  await page.getByLabel('Scope origin').fill('https://synthetic.invalid');
  await page.getByRole('button', { name: 'Save draft', exact: true }).click();
  await check(page.getByText('Saved · revision 1')).toBeVisible();
  await page.getByRole('link', { name: 'Overview', exact: true }).click();
  await page.getByLabel('Selected synthetic inert context').fill(input);
  await check(page.getByLabel('Qualified core publication').locator('option')).toHaveCount(2);
  await page.getByLabel('Qualified core publication').selectOption({ index: 1 });
  await page.getByLabel(/This text is synthetic and non-secret/).check();
  await page.getByRole('button', { name: 'Preflight inert run', exact: true }).click();
  const confirmation = page.getByRole('region', { name: 'Run preflight confirmation' });
  await check(confirmation).toContainText(input);
  await check(confirmation).toContainText(`Brain ${model}; Recon ${model}`);
  await page.getByLabel(/Confirm model execution/).check();
  const [started] = await Promise.all([
    page.waitForResponse(r => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/v1/runs'),
    page.getByRole('button', { name: 'Start inert run', exact: true }).click(),
  ]);
  assert.equal(started.status(), 202, 'Live Start denied; do not retry or reset the QA budget');
  const run = (await started.json()).run_id;
  let summary;
  const until = performance.now() + 900000;
  do {
    summary = await read(`/api/v1/runs/${run}/summary`);
    if (summary.run.state !== 'RUNNING') break;
    await page.waitForTimeout(300);
  } while (performance.now() < until);
  assert.equal(summary.run.state, 'LIMITED', 'No implicit answer, Resume, retry or assessment claim');
  assert.equal(summary.has_more, false);
  assert.equal(summary.usage.accounting_policy, 'MONITOR');
  const worker = summary.attempts.find(a => a.role === 'RECON' && a.read_receipt_ref && a.result_ref);
  assert.ok(worker, 'Live model did not produce a stored read_context/result');
  const inspected = await read(`/api/v1/runs/${run}/attempts/${worker.attempt_id}`);
  assert.equal(inspected.result.state, 'SUCCEEDED');
  assert.deepEqual(inspected.result.consumed_refs, [worker.read_receipt_ref]);
  assert.deepEqual(JSON.parse(inspected.tool_output).ref, worker.read_receipt_ref);
  assert.equal(inspected.consumption.held, false);
  assert.ok(inspected.consumption.decision_ref && inspected.consumption.consumer_attempt_id);
  const brain = await read(`/api/v1/runs/${run}/attempts/${inspected.consumption.consumer_attempt_id}`);
  assert.equal(brain.role, 'BRAIN');
  assert.deepEqual(brain.result_ref, inspected.consumption.decision_ref);
  assert.ok(brain.decision.consumed_refs.some(ref => ref.id === worker.result_ref.id && ref.digest === worker.result_ref.digest));
  await page.getByLabel('Spawned agents').getByRole('button', { name: new RegExp(`^RECON · ${worker.task_id} ·`) }).click();
  await check(page.getByRole('region', { name: 'Agent inspector' })).toContainText('Consumption: CONSUMED');
  return { run, state: 'LIMITED', readRef: worker.read_receipt_ref, resultRef: worker.result_ref, decisionRef: inspected.consumption.decision_ref, scope: 'LIVE_S1_ONLY_NOT_ASSESSMENT' };
}
