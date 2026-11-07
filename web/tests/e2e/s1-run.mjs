// S1 built browser/API/PG journey; SDK and relay ACK are scripted by the existing PG test.
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

export async function runS1({ page, check, paired, origin, output, screenshot, secretChecks, remember }) {
  const record = join(output, 's1-run-record.json');
  const writes = [];
  page.on('request', request => {
    if (['POST', 'PUT', 'DELETE'].includes(request.method()) && new URL(request.url()).pathname.startsWith('/api/v1/')) writes.push(`${request.method()} ${new URL(request.url()).pathname}`);
  });
  const read = path => page.evaluate(async path => {
    const response = await fetch(path);
    if (!response.ok) throw new Error('S1 readback unavailable');
    return response.json();
  }, path);
  async function openDisclosure(region, name) {
    const trigger = region.getByText(name, { exact: true });
    const disclosure = trigger.locator('..');
    if (await disclosure.getAttribute('open') === null) await trigger.click();
    await check(disclosure).toHaveJSProperty('open', true);
    return disclosure;
  }
  async function accounting(region, usage) {
    assert.equal(usage.accounting_policy, 'MONITOR');
    const full = usage.scope === 'RUN' ? await openDisclosure(region, 'Exact accounting & provenance') : region;
    await check(full).toContainText(`Allocations: ${usage.totals.dispatches} · without observation: ${usage.totals.unobserved_dispatches}`);
    for (const key of ['input_tokens', 'output_tokens', 'total_tokens', 'cached_tokens', 'reasoning_tokens', 'cache_creation_tokens', 'cost_observed']) {
      const amount = usage.totals[key];
      await check(full.locator(':scope > dl').locator('dt').filter({ hasText: new RegExp(`^${key}$`) }).locator('..')).toContainText(`${amount.value ?? 'UNKNOWN'} · ${amount.state} · ${amount.observed_dispatches}/${usage.totals.dispatches} observed`);
    }
    for (const role of usage.roles) {
      const group = full.getByRole('region', { name: `${role.role} usage`, exact: true });
      await check(group).toContainText(`${role.role} · ${role.configured_model}`);
      await check(group).toContainText(`connection ${role.connection_id} · revision ${role.connection_revision}`);
    }
  }
  async function inspectWorker(run, worker) {
    const value = await read(`/api/v1/runs/${run}/attempts/${worker.attempt_id}`);
    assert.equal(value.result.state, 'SUCCEEDED');
    assert.equal(value.result.completion_kind, 'finish');
    assert.equal(value.consumption.held, false);
    assert.ok(value.consumption.decision_ref && value.consumption.consumer_attempt_id);
    await page.getByLabel('Spawned agents').getByRole('button', { name: new RegExp(`^RECON · ${worker.task_id} ·`) }).click();
    const inspector = page.getByRole('region', { name: 'Agent inspector' });
    await check(inspector).toContainText('Configured model: fixture/s1-recon');
    await check(inspector).toContainText('Observed model: fixture/s1-recon');
    await check(inspector).toContainText('Completion kind: finish');
    await check(inspector).toContainText(value.result.summary);
    await check(inspector).toContainText(value.result_ref.digest);
    await check(inspector).toContainText('Consumption: CONSUMED');
    await check(inspector).toContainText(value.consumption.decision_ref.digest);
    for (const gap of value.result.gaps) await check(inspector).toContainText(gap);
    await openDisclosure(inspector, 'Prompt & input');
    await openDisclosure(inspector, 'Tools & results');
    await openDisclosure(inspector, 'Usage');
    await accounting(inspector.getByRole('region', { name: 'Attempt accounting' }), value.usage);
    assert.equal(value.dispatches_has_more, false);
    for (const dispatch of value.dispatches) {
      assert.ok(dispatch.usage && dispatch.usage_ref);
      await check(inspector).toContainText(dispatch.dispatch_id);
      await check(inspector).toContainText(dispatch.usage_ref.digest);
      await check(inspector).toContainText(dispatch.usage.observed_at);
      const dispatchRow = inspector.getByRole('list', { name: 'Dispatch observations' }).getByRole('listitem').filter({ hasText: dispatch.dispatch_id });
      await check(dispatchRow.locator('pre').last()).toHaveText(JSON.stringify(dispatch.usage.reported, null, 2));
    }
    return value;
  }
  remember('synthetic-s1-not-a-key');
  await paired();
  if (process.env.OMNIS_E2E_STAGE === 'after') {
    const previous = JSON.parse(await readFile(record, 'utf8'));
    await page.goto(`${origin}/engagements/${previous.engagement}/stream`);
    await check(page.getByRole('region', { name: 'Inert run', exact: true })).toContainText('LIMITED');
    await check(page.getByRole('region', { name: 'Needs you' })).toContainText('CONSUMED');
    const current = await read(`/api/v1/runs/${previous.run}/summary`);
    delete current.as_of;
    assert.deepEqual(current, previous.summary);
    await accounting(page.getByRole('region', { name: 'Run accounting' }), current.usage);
    const inspected = await inspectWorker(previous.run, previous.worker);
    delete inspected.as_of;
    assert.deepEqual(inspected, previous.inspection);
    await page.reload();
    await check(page.getByRole('region', { name: 'Inert run', exact: true })).toContainText(previous.run);
    await inspectWorker(previous.run, previous.worker);
    assert.deepEqual(writes, [], 'API restart and reload must never start or consume');
    await secretChecks();
    return { run: previous.run, engagement: previous.engagement, apiRestartReadback: true };
  }
  await page.goto(`${origin}/settings/providers`);
  await check(page.getByRole('region', { name: 'Configured models' })).toContainText('fixture/s1');
  const before = await read('/api/v1/settings/providers');
  assert.equal(before.selection.default.model, 'fixture/s1');
  assert.equal(before.selection.recon, null);
  const library = await read('/api/v1/settings/models');
  const recon = library.entries.find(entry => entry.model === 'fixture/s1-recon');
  assert.ok(recon, 'The admitted synthetic Recon model must be registered by the real fixture');
  const assignments = page.getByRole('region', { name: 'Model assignments', exact: true });
  await check(assignments.getByLabel('Recon', { exact: true }).locator(`option[value="${recon.entry_id}"]`)).toBeEnabled();
  await assignments.getByLabel('Recon', { exact: true }).selectOption(recon.entry_id);
  await assignments.getByRole('button', { name: 'Save assignments', exact: true }).click();
  await check(page.getByRole('complementary', { name: 'Settings notification', exact: true })).toContainText('Assignments saved.');
  await page.reload();
  await check(assignments.getByLabel('Recon', { exact: true })).toHaveValue(recon.entry_id);
  const savedSelection = (await read('/api/v1/settings/providers')).selection;
  assert.equal(savedSelection.recon.model, 'fixture/s1-recon');
  assert.equal(savedSelection.recon.connection_id, savedSelection.default.connection_id);
  assert.equal(savedSelection.recon.connection_revision, savedSelection.default.connection_revision);
  assert.equal(savedSelection.recon.output_tokens, 1024);
  assert.equal((savedSelection.brain ?? savedSelection.default).model, 'fixture/s1');
  assert.ok(savedSelection.revision > before.selection.revision);
  await check(page.getByRole('button', { name: 'Stop active run', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Home', exact: true }).click();
  await page.getByRole('link', { name: /New engagement/ }).first().click();
  await page.getByLabel('Engagement name').fill('S1 synthetic inert run');
  await page.getByLabel('Authorization owner').fill('Synthetic fixture operator');
  await page.getByLabel('Authorization statement').fill('Inert context only; no target traffic');
  await check(page.getByRole('checkbox', { name: 'Limit to a period', exact: true })).not.toBeChecked();
  await page.getByLabel('Scope origin').fill('https://synthetic.invalid');
  await page.getByRole('button', { name: 'Save draft', exact: true }).click();
  await check(page.getByText('Saved · revision 1')).toBeVisible();
  const engagement = page.url().match(/\/engagements\/([0-9a-f-]{36})\/setup$/)?.[1];
  assert.ok(engagement);
  await page.getByRole('link', { name: 'Overview', exact: true }).click();
  const input = 'Selected S1 browser synthetic context 🧪';
  await page.getByLabel('Selected synthetic inert context').fill(input);
  const publication = page.getByLabel('Qualified core publication');
  await check(publication.locator('option')).toHaveCount(2);
  await publication.selectOption({ index: 1 });
  await page.getByLabel(/This text is synthetic and non-secret/).check();
  const preflight = page.getByRole('button', { name: 'Preflight inert run', exact: true });
  await check(preflight).toBeEnabled();
  await preflight.focus(); await check(preflight).toBeFocused();
  const preflightPath = `/api/v1/engagements/${engagement}/run-preflight`;
  const [prepared] = await Promise.all([
    page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === preflightPath, { timeout: 15000 }),
    page.keyboard.press('Enter'),
  ]);
  assert.equal(prepared.status(), 200, 'Preflight must return its persisted setup receipt');
  const preparedReceipt = await prepared.json();
  assert.equal(preparedReceipt.state, 'READY');
  assert.ok(preparedReceipt.setup_ref);
  assert.equal(writes.filter(path => path === `POST ${preflightPath}`).length, 1, 'Preflight is not retried');
  const confirmation = page.getByRole('region', { name: 'Run preflight confirmation' });
  await check(confirmation).toContainText(input);
  await check(confirmation).toContainText('fixture/s1');
  await check(confirmation).toContainText(`Brain fixture/s1; Recon fixture/s1-recon; selection revision ${savedSelection.revision}`);
  await page.getByLabel(/Confirm model execution/).check();
  await page.getByRole('button', { name: 'Start inert run', exact: true }).click();
  await check(page.getByRole('region', { name: 'Needs you' })).toContainText('PENDING');
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    const stop = page.getByRole('button', { name: 'Stop active run', exact: true });
    await check(stop).toBeEnabled(); await stop.focus(); await check(stop).toBeFocused();
    const box = await stop.boundingBox(); assert.ok(box && box.width >= 44 && box.height >= 44);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `S1 control overflow ${width}`);
    await screenshot(`s1-controls-${width}`);
  }
  await page.reload();
  await check(page.getByRole('region', { name: 'Needs you' })).toContainText('PENDING');
  await page.getByLabel('Non-secret clarification').fill('Use only the selected synthetic context');
  const [answer] = await Promise.all([
    page.waitForResponse(response => response.request().method() === 'POST' && /\/runs\/[0-9a-f-]+\/commands$/.test(new URL(response.url()).pathname)),
    page.getByRole('button', { name: 'Submit clarification', exact: true }).click(),
  ]);
  assert.equal(answer.status(), 202);
  assert.equal((await answer.json()).state, 'ADMITTED');
  await check(page.getByRole('region', { name: 'Needs you' })).toContainText('CONSUMED');
  await check(page.getByRole('region', { name: 'Inert run', exact: true })).toContainText('LIMITED');
  const selected = await read(`/api/v1/engagements/${engagement}/run`);
  const summary = await read(`/api/v1/runs/${selected.run_id}/summary`);
  const workers = summary.attempts.filter(item => item.role === 'RECON');
  assert.equal(workers.length, 3);
  assert.equal(new Set(workers.map(item => item.task_id)).size, 3);
  assert.ok(workers.every(item => item.state === 'SUCCEEDED' && item.result_ref && item.read_receipt_ref));
  assert.ok(workers.every(item => item.configured_model === 'fixture/s1-recon' && item.observed_model === 'fixture/s1-recon'));
  assert.ok(summary.attempts.filter(item => item.role === 'BRAIN').every(item => item.configured_model === 'fixture/s1'));
  assert.equal(summary.usage.scope, 'RUN');
  assert.deepEqual(summary.usage.roles.map(role => [role.role, role.configured_model]).sort(), [['BRAIN', 'fixture/s1'], ['RECON', 'fixture/s1-recon']]);
  const completions = await Promise.all(workers.map(worker => read(`/api/v1/runs/${selected.run_id}/attempts/${worker.attempt_id}`)));
  assert.deepEqual(completions.map(worker => worker.result.completion_kind).sort(), ['direct', 'direct', 'finish']);
  const finish = completions.find(worker => worker.result.completion_kind === 'finish');
  assert.ok(finish);
  await page.getByRole('link', { name: 'Brain stream', exact: true }).click();
  await accounting(page.getByRole('region', { name: 'Run accounting' }), summary.usage);
  const workerInspection = await inspectWorker(selected.run_id, finish);
  const inspector = page.getByRole('region', { name: 'Agent inspector' });
  await check(inspector).toContainText(input);
  const consumer = await read(`/api/v1/runs/${selected.run_id}/attempts/${workerInspection.consumption.consumer_attempt_id}`);
  assert.deepEqual(consumer.result_ref, workerInspection.consumption.decision_ref);
  assert.ok(consumer.decision.consumed_refs.some(ref => ref.id === workerInspection.result_ref.id && ref.digest === workerInspection.result_ref.digest));
  const consuming = inspector.getByRole('button', { name: /Inspect consuming Brain/ });
  await consuming.focus(); await page.keyboard.press('Enter');
  await check(inspector.getByRole('heading', { level: 3 })).toBeFocused();
  await check(inspector).toContainText('Configured model: fixture/s1 ·');
  await check(inspector).toContainText(`Decision action: ${consumer.decision.action}`);
  await check(inspector).toContainText(consumer.decision.detail);
  await check(inspector).toContainText(workerInspection.result_ref.digest);
  const writesBeforeReload = [...writes];
  await page.reload();
  const reloadedInspection = await inspectWorker(selected.run_id, finish);
  delete reloadedInspection.as_of;
  delete workerInspection.as_of;
  assert.deepEqual(reloadedInspection, workerInspection);
  assert.deepEqual(writes, writesBeforeReload, 'Reload/inspection/consumption navigation must be receive-only');
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    const stop = page.getByRole('button', { name: 'Stop active run', exact: true });
    await check(stop).toBeDisabled();
    const selectedAgent = page.getByLabel('Spawned agents').getByRole('button', { name: /^RECON/ }).first();
    await selectedAgent.focus(); await check(selectedAgent).toBeFocused();
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `S1 overflow ${width}`);
    await screenshot(`s1-inspector-${width}`);
  }
  await secretChecks();
  delete summary.as_of;
  await writeFile(record, JSON.stringify({ engagement, run: selected.run_id, summary, savedSelection, worker: { task_id: finish.task_id, attempt_id: finish.attempt_id }, inspection: workerInspection }));
  return { run: selected.run_id, engagement, workerTasks: workers.map(item => item.task_id), needsYou: summary.question.question_id };
}
