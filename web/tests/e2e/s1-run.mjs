// S1 built browser/API/PG journey; SDK and relay ACK are scripted by the existing PG test.
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

export async function runS1({ page, check, paired, origin, output, screenshot, secretChecks, remember }) {
  const record = join(output, 's1-run-record.json');
  const writes = [];
  page.on('request', request => {
    if (request.method() === 'POST' && new URL(request.url()).pathname.startsWith('/api/v1/')) writes.push(new URL(request.url()).pathname);
  });
  const read = path => page.evaluate(async path => {
    const response = await fetch(path);
    if (!response.ok) throw new Error('S1 readback unavailable');
    return response.json();
  }, path);
  remember('synthetic-s1-not-a-key');
  await paired();
  if (process.env.OMNIS_E2E_STAGE === 'after') {
    const previous = JSON.parse(await readFile(record, 'utf8'));
    await page.goto(`${origin}/engagements/${previous.engagement}/stream`);
    await check(page.getByRole('region', { name: 'Inert run' })).toContainText('LIMITED');
    await check(page.getByRole('region', { name: 'Needs you' })).toContainText('CONSUMED');
    const current = await read(`/api/v1/runs/${previous.run}/summary`);
    delete current.as_of;
    assert.deepEqual(current, previous.summary);
    await page.reload();
    await check(page.getByRole('region', { name: 'Inert run' })).toContainText(previous.run);
    assert.deepEqual(writes, [], 'API restart and reload must never start or consume');
    await secretChecks();
    return { run: previous.run, engagement: previous.engagement, apiRestartReadback: true };
  }
  await page.goto(`${origin}/settings/providers`);
  await check(page.getByRole('region', { name: 'Configured models' })).toContainText('fixture/s1');
  await check(page.getByRole('button', { name: 'Stop active run', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Home', exact: true }).click();
  await page.getByRole('link', { name: /New engagement/ }).first().click();
  await page.getByLabel('Engagement name').fill('S1 synthetic inert run');
  await page.getByLabel('Authorization owner').fill('Synthetic fixture operator');
  await page.getByLabel('Authorization statement').fill('Inert context only; no target traffic');
  await page.getByLabel('Valid from (UTC)').fill('2030-01-01T00:00:00Z');
  await page.getByLabel('Valid until (UTC)').fill('2030-12-31T00:00:00Z');
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
  await preflight.focus(); await page.keyboard.press('Enter');
  const confirmation = page.getByRole('region', { name: 'Run preflight confirmation' });
  await check(confirmation).toContainText(input);
  await check(confirmation).toContainText('fixture/s1');
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
  await check(page.getByRole('region', { name: 'Inert run' })).toContainText('LIMITED');
  const selected = await read(`/api/v1/engagements/${engagement}/run`);
  const summary = await read(`/api/v1/runs/${selected.run_id}/summary`);
  const workers = summary.attempts.filter(item => item.role === 'RECON');
  assert.equal(workers.length, 3);
  assert.equal(new Set(workers.map(item => item.task_id)).size, 3);
  assert.ok(workers.every(item => item.state === 'SUCCEEDED' && item.result_ref && item.read_receipt_ref));
  await page.getByRole('link', { name: 'Brain stream', exact: true }).click();
  await page.getByLabel('Spawned agents').getByRole('button', { name: /^RECON/ }).first().click();
  const inspector = page.getByRole('region', { name: 'Agent inspector' });
  await check(inspector).toContainText(input);
  await check(inspector).toContainText('Configured model: fixture/s1');
  await check(inspector).toContainText('Observed model: fixture/s1');
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
  await writeFile(record, JSON.stringify({ engagement, run: selected.run_id, summary }));
  return { run: selected.run_id, engagement, workerTasks: workers.map(item => item.task_id), needsYou: summary.question.question_id };
}
