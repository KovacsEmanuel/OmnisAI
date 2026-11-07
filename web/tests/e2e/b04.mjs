// G01 inert draft journey against the real owned API/PostgreSQL and built browser assets.
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { join } from 'node:path';
import { readFile, writeFile } from 'node:fs/promises';

const objective = '  Focus 🧪\nRespectă spațiul.  ';
export async function runB04({ page, context, check, paired, fault, output, origin, screenshot, secretChecks }) {
  const stage = process.env.OMNIS_E2E_STAGE;
  assert.ok(stage === 'before' || stage === 'after');
  await paired();
  const recordPath = join(output, 'b04-record.json');
  if (stage === 'after') {
    const previous = JSON.parse(await readFile(recordPath, 'utf8'));
    await page.goto(`${origin}/engagements/${previous.id}/setup`);
    await check(page.getByLabel('Objective / Brain instructions')).toHaveValue(previous.objective);
    await check(page.getByText(`Saved · revision ${previous.revision}`)).toBeVisible();
    await check(page.getByRole('region', { name: 'Test model', exact: true })).toHaveCount(0);
    const restored = await page.evaluate(async id => (await fetch(`/api/v1/engagements/${id}`)).json(), previous.id);
    assert.equal(restored.engagement_id, previous.id);
    assert.equal(restored.revision, previous.revision);
    assert.equal(restored.digest, previous.digest);
    assert.equal(restored.payload.objective_text, previous.objective);
    assert.equal(restored.payload.authorization.valid_from, null);
    assert.equal(restored.payload.authorization.valid_until, null);
    await check(page.getByRole('checkbox', { name: 'Limit to a period', exact: true })).not.toBeChecked();
    await check(page.getByLabel('Valid from (UTC)', { exact: true })).toHaveCount(0);
    await page.reload();
    await check(page.getByLabel('Objective / Brain instructions')).toHaveValue(previous.objective);
    await page.getByRole('button', { name: '2. Application context' }).click();
    await check(page.getByLabel('Principal 1')).toHaveValue('Visitor');
    await page.getByRole('button', { name: '4. Rules & budgets' }).click();
    await check(page.getByLabel('Maximum requests')).toHaveValue('40');
    const review = page.getByRole('button', { name: '5. Review & preflight' });
    await review.focus();
    await check(review).toBeFocused();
    await page.keyboard.press('Enter');
    await check(page.getByRole('heading', { name: 'Review & preflight' })).toBeVisible();
    await check(page.getByText(previous.objective, { exact: true })).toBeVisible();
    await check(page.getByText('No end date — until closed or revoked', { exact: true })).toBeVisible();
    await check(page.getByRole('button', { name: 'Start assessment' })).toBeDisabled();
    for (const width of [320, 390, 1280, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `G01 overflow ${width}`);
      if (width === 390 || width === 1440) await screenshot(`b04-review-${width}`);
    }
    await secretChecks();
    console.log('B04_G01_RESTART_PASS same DB, new backend PID, fresh browser, exact revision/digest/objective');
    return;
  }
  await page.setViewportSize({ width: 390, height: 900 });
  await page.goto(`${origin}/engagements/new`);
  await check(page.getByRole('heading', { name: 'New engagement' })).toBeVisible();
  await check(page.getByRole('region', { name: 'Test model', exact: true })).toHaveCount(0);
  await page.keyboard.press('Tab');
  await check(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  await page.keyboard.press('Enter');
  await check(page.locator('main')).toBeFocused();
  const name = page.getByLabel('Engagement name');
  await name.focus();
  await page.keyboard.type('G01 synthetic draft');
  await check(name).toHaveValue('G01 synthetic draft');
  const box = await name.boundingBox();
  assert.ok(box && box.width >= 44 && box.height >= 44, 'Mobile create input touch target below 44px');
  assert.equal(await name.evaluate(element => getComputedStyle(element).outlineWidth), '2px');
  await page.getByLabel('Authorization owner').fill('Fixture operator');
  await page.getByLabel('Authorization statement').fill('Disposable synthetic only');
  await check(page.getByRole('checkbox', { name: 'Limit to a period', exact: true })).not.toBeChecked();
  await page.getByLabel('Scope origin').fill('https://synthetic.invalid');
  await check(page.getByLabel('Scope access')).toHaveValue('BLOCKED');
  // Real current UTC month, not a fixed future month, patched clock or an ISO-input shortcut.
  const utc = await page.evaluate(() => { const now = new Date(); return { year: now.getUTCFullYear(), month: now.getUTCMonth(), day: now.getUTCDate() }; });
  const dayLabel = day => new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(Date.UTC(utc.year, utc.month, day)));
  const finite = { valid_from: new Date(Date.UTC(utc.year, utc.month, 15, 0, 0, 0)).toISOString().replace('.000Z', 'Z'), valid_until: new Date(Date.UTC(utc.year, utc.month, 16, 23, 59, 59)).toISOString().replace('.000Z', 'Z') };
  let creates = 0;
  page.on('request', request => { if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/v1/engagements') creates += 1; });
  await page.getByRole('checkbox', { name: 'Limit to a period', exact: true }).check();
  const from = page.getByLabel('Valid from (UTC)', { exact: true });
  await check(from).toHaveText('Choose date');
  await from.focus(); await check(from).toBeFocused();
  const fromBox = await from.boundingBox(); assert.ok(fromBox && fromBox.width >= 44 && fromBox.height >= 44);
  await page.keyboard.press('Enter');
  const calendar = page.getByRole('dialog', { name: 'Valid from (UTC) calendar', exact: true });
  await check(calendar.getByRole('button', { name: dayLabel(utc.day), exact: true })).toBeFocused();
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 900 });
    const bounds = await calendar.boundingBox();
    assert.ok(bounds && bounds.x >= 0 && bounds.x + bounds.width <= width && bounds.y >= 0 && bounds.y + bounds.height <= 900, `Calendar outside ${width}px viewport`);
    for (const button of await calendar.getByRole('button').all()) {
      const target = await button.boundingBox();
      assert.ok(target && target.width >= 44 && target.height >= 44, `Calendar button below 44px at ${width}px`);
    }
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Calendar overflow ${width}`);
  }
  await page.keyboard.press('Escape');
  await check(calendar).toHaveCount(0); await check(from).toBeFocused();
  await page.keyboard.press('Enter');
  await calendar.getByRole('button', { name: dayLabel(15), exact: true }).click();
  await check(from).toHaveText(dayLabel(15)); await check(from).toBeFocused();
  await page.getByRole('button', { name: 'Save draft' }).click();
  await check(page.getByLabel('Valid until (UTC)', { exact: true })).toHaveAttribute('aria-invalid', 'true');
  assert.equal(creates, 0, 'An incomplete enabled period must not dispatch POST');
  await page.getByLabel('Valid until (UTC)', { exact: true }).click();
  await page.getByRole('dialog', { name: 'Valid until (UTC) calendar', exact: true }).getByRole('button', { name: dayLabel(16), exact: true }).click();
  await check(page.getByLabel('Valid until (UTC)', { exact: true })).toHaveText(dayLabel(16));
  await check(page.getByLabel('Objective / Brain instructions')).toHaveValue('Assess the authorized Web/API surface within the selected profile.');
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 900 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Mobile create overflow ${width}`);
  }
  const skip = await page.getByRole('link', { name: 'Skip to content' }).evaluate(element => {
    const rect = element.getBoundingClientRect();
    return { bottom: rect.bottom, focused: document.activeElement === element };
  });
  assert.ok(skip.bottom <= 0 && !skip.focused, 'Skip link obscures the mobile form after focus moves');
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: join(output, 'b04-create-viewport-390.png'), fullPage: false });
  await screenshot('b04-create-390');
  const save = page.getByRole('button', { name: 'Save draft' });
  await save.focus();
  await check(save).toBeFocused();
  await page.keyboard.press('Enter');
  await check(page.getByText('Saved · revision 1')).toBeVisible();
  assert.equal(creates, 1, 'Finite calendar save is one actual create');
  const id = page.url().match(/\/engagements\/([0-9a-f-]{36})\/setup$/)?.[1];
  assert.ok(id, 'POST must lead to an authenticated, confirmed engagement readback');
  const finiteReadback = await page.evaluate(async target => (await fetch(`/api/v1/engagements/${target}`)).json(), id);
  assert.equal(finiteReadback.revision, 1);
  assert.equal(finiteReadback.payload.authorization.valid_from, finite.valid_from);
  assert.equal(finiteReadback.payload.authorization.valid_until, finite.valid_until);
  await check(page.getByRole('checkbox', { name: 'Limit to a period', exact: true })).toBeChecked();
  await check(page.getByLabel('Valid from (UTC)', { exact: true })).toHaveText(dayLabel(15));
  await check(page.getByLabel('Valid until (UTC)', { exact: true })).toHaveText(dayLabel(16));
  await check(page.getByRole('region', { name: 'Test model', exact: true })).toHaveCount(0);
  await check(page.getByRole('button', { name: 'Start assessment' })).toBeDisabled();
  await page.getByRole('button', { name: 'Next' }).click();
  await check(page.getByRole('heading', { name: 'Application context' })).toBeVisible();
  await page.getByRole('button', { name: 'Back' }).click();
  await check(page.getByLabel('Objective / Brain instructions')).toHaveValue('Assess the authorized Web/API surface within the selected profile.');
  await page.getByLabel('Scope origin').fill('https://synthetic.invalid:');
  const [invalid] = await Promise.all([
    page.waitForResponse(response => response.request().method() === 'PUT' &&
      response.url() === `${origin}/api/v1/engagements/${id}`),
    page.getByRole('button', { name: 'Save draft' }).click(),
  ]);
  assert.equal(invalid.status(), 422, 'Invalid scope origin must reach the real API field validator');
  await check(page.getByLabel('Scope origin')).toHaveAttribute('aria-invalid', 'true');
  await page.getByRole('button', { name: 'scope.0.origin: Invalid value.' }).click();
  await check(page.getByLabel('Scope origin')).toBeFocused();
  await page.getByLabel('Scope origin').fill('https://synthetic.invalid');
  await page.getByLabel('Focused test').check();
  // A persisted General objective has no provenance flag in B02; switching modes must not delete saved text by literal equality.
  await check(page.getByLabel('Objective / Brain instructions')).toHaveValue('Assess the authorized Web/API surface within the selected profile.');
  await page.getByLabel('Objective / Brain instructions').fill('   ');
  await page.getByRole('button', { name: 'Save draft' }).click();
  await check(page.getByLabel('Objective / Brain instructions')).toHaveAttribute('aria-invalid', 'true');
  await page.getByLabel('Objective / Brain instructions').fill(objective);
  await page.getByRole('checkbox', { name: 'Limit to a period', exact: true }).uncheck();
  await check(page.getByLabel('Valid from (UTC)', { exact: true })).toHaveCount(0);
  await check(page.getByText(/code points/).first()).toContainText('8192');
  await page.getByRole('button', { name: '2. Application context' }).click();
  await page.getByLabel('Seed URLs (one per line)').fill('https://synthetic.invalid/api');
  await page.getByRole('button', { name: 'Add business rule' }).click();
  for (const [label, value] of Object.entries({ 'Principal 1': 'Visitor', 'Role 1': 'Viewer', 'Tenant 1': 'Tenant A',
    'Object 1': 'Invoice', 'Operation 1': 'GET', 'Source 1': 'Fixture declaration' })) await page.getByLabel(label).fill(value);
  await page.getByLabel('Expected decision 1').selectOption('DENY');
  await page.getByRole('button', { name: '3. Identities' }).click();
  await check(page.getByText(/Anonymous is valid/)).toBeVisible();
  await page.getByRole('button', { name: '4. Rules & budgets' }).click();
  await page.getByLabel('Maximum requests').fill('40');
  await page.getByLabel('Validation reserved requests').fill('5');
  await page.getByRole('button', { name: 'Add effect rule' }).click();
  await page.getByLabel('Decision for READ_ONLY_KNOWN').selectOption('DENY');
  await page.getByLabel('Retention days').fill('7');
  await page.getByRole('button', { name: 'Save draft' }).click();
  await check(page.getByText('Saved · revision 2')).toBeVisible();
  const unboundedReadback = await page.evaluate(async target => (await fetch(`/api/v1/engagements/${target}`)).json(), id);
  assert.equal(unboundedReadback.revision, 2);
  assert.equal(unboundedReadback.payload.authorization.valid_from, null);
  assert.equal(unboundedReadback.payload.authorization.valid_until, null);
  await page.reload();
  await check(page.getByLabel('Objective / Brain instructions')).toHaveValue(objective);
  await check(page.getByRole('checkbox', { name: 'Limit to a period', exact: true })).not.toBeChecked();
  await page.getByRole('button', { name: '2. Application context' }).click();
  await check(page.getByLabel('Principal 1')).toHaveValue('Visitor');
  await page.getByRole('button', { name: '4. Rules & budgets' }).click();
  await check(page.getByLabel('Maximum requests')).toHaveValue('40');
  const second = await context.newPage();
  try {
    await second.goto(`${origin}/engagements/${id}/setup`);
    await check(second.getByLabel('Objective / Brain instructions')).toHaveValue(objective);
    await page.getByRole('button', { name: '1. Target & permission' }).click();
    await page.getByLabel('Objective / Brain instructions').fill(objective + '\nFirst editor');
    await page.getByRole('button', { name: 'Save draft' }).click();
    await check(page.getByText('Saved · revision 3')).toBeVisible();
    await second.getByLabel('Objective / Brain instructions').fill(objective + '\nSecond editor');
    const [conflict] = await Promise.all([
      second.waitForResponse(response => response.request().method() === 'PUT' &&
        response.url() === `${origin}/api/v1/engagements/${id}`),
      second.getByRole('button', { name: 'Save draft' }).click(),
    ]);
    assert.equal(conflict.status(), 409, 'Stale second tab must receive real CAS conflict');
    await check(second.getByText('Conflict · local edits preserved')).toBeVisible();
    await check(second.getByLabel('Objective / Brain instructions')).toHaveValue(objective + '\nSecond editor');
    await second.getByRole('button', { name: 'Compare server revision' }).click();
    await check(second.getByText(/Server revision 3/)).toBeVisible();
    await check(second.getByLabel('Objective / Brain instructions')).toHaveValue(objective + '\nSecond editor');
    await check(second.getByRole('button', { name: 'Save draft' })).toBeDisabled();
    await secretChecks(second);
  } finally { await second.close(); }
  const session = await page.evaluate(async () => (await fetch('/api/session')).json());
  const latest = await page.evaluate(async target => (await fetch(`/api/v1/engagements/${target}`)).json(), id);
  assert.equal(latest.revision, 3);
  assert.equal(latest.payload.authorization.valid_from, null);
  assert.equal(latest.payload.authorization.valid_until, null);
  assert.equal(latest.payload.objective_text, objective + '\nFirst editor');
  assert.equal(latest.payload.scope[0].access, 'BLOCKED', 'BLOCKED declaration is legitimate persisted data');
  assert.equal(latest.payload.business_matrix[0].principal, 'Visitor');
  assert.equal(latest.payload.budgets.max_requests, 40);
  const headers = { 'Content-Type': 'application/json', Origin: origin, 'X-CSRF-Token': session.csrf_token,
    'If-Match': `"rev-${latest.revision}-${latest.digest}"`, 'X-Command-ID': randomUUID() };
  const body = latest.payload;
  const denied = [
    await context.request.put(`${origin}/api/v1/engagements/${id}`, { headers: { ...headers, Host: 'foreign.invalid' }, data: body }),
    await context.request.put(`${origin}/api/v1/engagements/${id}`, { headers: { ...headers, Origin: 'https://foreign.invalid' }, data: body }),
    await context.request.put(`${origin}/api/v1/engagements/${id}`, { headers: { ...headers, 'X-CSRF-Token': '' }, data: body }),
    await context.request.put(`${origin}/api/v1/engagements/${id}`, { headers: { ...headers, 'X-CSRF-Token': 'invalid' }, data: body }),
  ];
  assert.deepEqual(await Promise.all(denied.map(async response => [response.status(), (await response.json()).error.code])),
    [[400, 'INVALID_HOST'], [403, 'INVALID_ORIGIN'], [403, 'INVALID_CSRF'], [403, 'INVALID_CSRF']]);
  const fakeRef = { kind: 'operation', id: randomUUID(), revision: 1, digest: 'f'.repeat(64) };
  const blockedRef = await context.request.put(`${origin}/api/v1/engagements/${id}`, { headers,
    data: { ...body, objective_constraints: [{ id: randomUUID(), kind: 'READ_ONLY', text: 'No writes', operation_refs: [fakeRef] }] } });
  assert.equal(blockedRef.status(), 422);
  const crossRef = await context.request.put(`${origin}/api/v1/engagements/${id}`, { headers: { ...headers, 'X-Command-ID': randomUUID() },
    data: { ...body, business_rules_ref: { kind: 'business-rule', id: randomUUID(), revision: 1, digest: 'f'.repeat(64) } } });
  assert.equal(crossRef.status(), 422);
  const final = await page.evaluate(async target => (await fetch(`/api/v1/engagements/${target}`)).json(), id);
  assert.equal(final.revision, 3);
  fault('expire-session');
  await page.getByRole('button', { name: 'Refresh engagement' }).click();
  await check(page.getByLabel('Pairing code')).toBeVisible();
  await paired();
  await page.goto(`${origin}/engagements/${id}/setup`);
  await check(page.getByLabel('Objective / Brain instructions')).toHaveValue(objective + '\nFirst editor');
  await writeFile(recordPath, JSON.stringify({ id, objective: objective + '\nFirst editor', revision: final.revision, digest: final.digest }));
  await secretChecks();
  console.log('B04_G01_BEFORE_PASS create/edit/GET/reload, real CAS 409, denials, expiry and re-pair');
}
