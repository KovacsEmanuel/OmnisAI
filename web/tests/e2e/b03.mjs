// B03 product journey. Data is created through the real authenticated API,
// never a mocked response or the prototype DEMO model. UI performs no draft writes.
// Busy probes hold an outgoing GET, then continue it to the real API/PG.
import assert from 'node:assert/strict';
import { join } from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

export async function runB03({ page, check, paired, fault, output, origin, screenshot, secretChecks }) {
  await paired();
  await page.goto(`${origin}/engagements`);
  await check(page.getByText(/No engagements/i)).toBeVisible();
  const created = await page.evaluate(async () => {
    const session = await (await fetch('/api/session')).json();
    const result = [];
    for (let index = 0; index < 23; index++) {
      const body = {
        name: index === 0 ? '<img src=x onerror=alert(1)> Long stored engagement '.repeat(2) : `Stored B03 draft ${index}`,
        authorization: { owner: 'Synthetic B03 operator', statement: 'Owned disposable fixture only', valid_from: '2030-01-01T00:00:00Z', valid_until: '2030-12-31T00:00:00Z' },
        scope: [{ origin: 'https://b03.example', port: 443, path_prefix: '/api', exclusions: [], access: 'BLOCKED' }],
        assessment_mode: 'FOCUSED_TEST', objective_text: '<script>never execute</script> Read only within declared scope. '.repeat(60),
        objective_constraints: [], workflow_profile_ref: null,
        application_context: { seed_urls: [], priority_workflows: [], test_objects: [], import_ref: null },
        effect_rules: [], budgets: { max_requests: 10, max_duration_seconds: 60, max_storage_bytes: 1048576, validation_reserved_requests: 2, max_model_calls: 0 },
        data_policy: { model_projection: 'NONE', research_egress: 'NONE', retention_days: 1 },
        business_matrix: [], business_rules_ref: null,
      };
      const response = await fetch('/api/v1/engagements', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf_token }, body: JSON.stringify(body) });
      if (response.status !== 201) throw new Error(`Fixture API create refused ${response.status}`);
      result.push(await response.json());
    }
    return result;
  });
  const mutationRequests = [];
  page.on('request', request => { if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method()) && request.url().includes('/api/v1/')) mutationRequests.push(request.url()); });
  await page.reload();
  await check(page.getByRole('heading', { name: 'Recent engagements' })).toBeVisible();
  const summary = await page.evaluate(async () => (await fetch('/api/v1/dashboard')).json());
  assert.equal(summary.data.total_engagements, 23);
  assert.equal(summary.data.items.length, 20);
  assert.equal(summary.through_cursor, null);
  assert.ok(await page.getByText('23', { exact: true }).count());
  const selected = created[0];
  const busy = page.getByRole('region', { name: 'Engagement projection', exact: true });
  async function observeBusy(action, engagementId = selected.engagement_id) {
    let release;
    const held = new Promise(resolve => { release = resolve; });
    const readUrl = `${origin}/api/v1/engagements/${engagementId}`;
    const handler = async route => { await held; await route.continue(); };
    await page.route(readUrl, handler, { times: 1 });
    try {
      await action();
      await check(busy).toHaveAttribute('aria-busy', 'true');
      release();
      await check(busy).toHaveAttribute('aria-busy', 'false');
    } finally {
      release();
      await page.unroute(readUrl, handler);
    }
  }
  const visible = created.find(item => item.engagement_id === summary.data.items[0].engagement_id);
  assert.ok(visible, 'Visible draft must have real API identity');
  await page.getByRole('link', { name: visible.payload.name, exact: true }).click();
  await check(page.getByRole('heading', { name: visible.payload.name, exact: true })).toBeVisible();
  assert.ok(page.url().endsWith(`/${visible.engagement_id}/overview`));
  await page.reload();
  await check(page.getByRole('heading', { name: visible.payload.name, exact: true })).toBeVisible();
  await page.goto(`${origin}/engagements`);
  await page.getByRole('button', { name: 'Next page', exact: true }).click();
  await check(page.locator('main article')).toHaveCount(3);
  await check(page.getByText('23', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'First page', exact: true }).click();
  await check(page.locator('main article')).toHaveCount(20);
  // Direct entry also tests the long draft even when outside the current bounded page.
  await observeBusy(() => page.goto(`${origin}/engagements/${selected.engagement_id}/overview`));
  await check(page.getByRole('heading', { name: selected.payload.name })).toBeVisible();
  await observeBusy(() => page.getByRole('button', { name: 'Refresh engagement', exact: true }).click());
  await check(page.getByRole('button', { name: 'Start assessment' })).toBeDisabled();
  await page.getByRole('link', { name: 'Setup', exact: true }).click();
  await check(page.getByRole('region', { name: 'Draft setup' })).toBeVisible();
  await check(page.getByLabel('Engagement name')).toHaveValue(selected.payload.name);
  assert.ok(page.url().endsWith(`/${selected.engagement_id}/setup`));
  await observeBusy(() => page.reload());
  await check(page.getByRole('heading', { name: selected.payload.name })).toBeVisible();
  await observeBusy(() => page.getByRole('button', { name: 'Refresh engagement', exact: true }).click());
  assert.equal(await page.locator('script').filter({ hasText: 'never execute' }).count(), 0);
  assert.equal(await page.locator('img[src="x"]').count(), 0);
  await check(page.getByRole('button', { name: 'Save draft' })).toBeDisabled();
  for (const width of [320, 390, 1280, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    await check(page.getByRole('heading', { name: selected.payload.name })).toBeVisible();
    await check(page.getByLabel('Engagement name')).toHaveValue(selected.payload.name);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Setup overflow ${width}`);
    const setupBack = await page.getByRole('link', { name: /Dashboard/ }).boundingBox();
    assert.ok(setupBack && setupBack.height >= 44 && setupBack.width >= 44, `Setup backlink target below 44px at ${width}`);
    await screenshot(`b03-setup-${width}`);
    await page.goto(`${origin}/engagements`);
    await check(page.getByRole('heading', { name: 'Recent engagements' })).toBeVisible();
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Dashboard overflow ${width}`);
    await screenshot(`b03-dashboard-${width}`);
    await page.getByRole('link', { name: /New engagement/i }).first().click();
    await check(page.getByLabel('Engagement name')).toBeVisible();
    assert.ok(page.url().endsWith('/engagements/new'));
    const newBack = await page.getByRole('link', { name: /Dashboard/ }).boundingBox();
    assert.ok(newBack && newBack.height >= 44 && newBack.width >= 44, `New backlink target below 44px at ${width}`);
    await page.goto(`${origin}/engagements/${selected.engagement_id}/setup`);
  }
  await page.setViewportSize({ width: 390, height: 1000 });
  await page.goto(`${origin}/engagements`);
  await page.keyboard.press('Tab');
  await check(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  await page.keyboard.press('Enter');
  await check(page.locator('main')).toBeFocused();
  for (let i = 0; i < 12; i++) {
    await page.keyboard.press('Tab');
    const focused = await page.evaluate(() => {
      const element = document.activeElement;
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return { tag: element.tagName, height: rect.height, width: rect.width, top: rect.top, bottom: rect.bottom, outline: style.outlineWidth };
    });
    if (['A', 'BUTTON'].includes(focused.tag)) {
      assert.ok(focused.height >= 44, 'Keyboard target below 44px');
      assert.equal(focused.outline, '2px');
      assert.ok(focused.top >= 0 && focused.bottom <= 1000, 'Focus clipped outside viewport');
    }
  }
  await page.emulateMedia({ reducedMotion: 'reduce', forcedColors: 'active' });
  await page.getByRole('link', { name: /New engagement/i }).first().focus();
  await screenshot('b03-forced-colors-focus');
  await page.emulateMedia({ reducedMotion: 'reduce', forcedColors: 'none' });
  assert.equal(await page.locator('main').evaluate(element => getComputedStyle(element).animationName), 'none');
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.evaluate(() => { document.documentElement.style.zoom = '2'; });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Dashboard overflow 200% zoom');
  await screenshot('b03-zoom-200');
  await page.evaluate(() => { document.documentElement.style.zoom = ''; });
  await secretChecks();
  assert.deepEqual(mutationRequests, [], 'B03 UI unexpectedly mutated a draft');
  // Retain this actual draft in the same query client before the PG lock.
  await page.goto(`${origin}/engagements/${visible.engagement_id}/setup`);
  await check(page.getByRole('heading', { name: visible.payload.name, exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Home', exact: true }).click();
  await check(page.getByText('23', { exact: true })).toBeVisible();
  const faultPath = fileURLToPath(new URL('../../../api/tests/web_fault.py', import.meta.url));
  const blocker = spawn(process.env.OMNIS_E2E_PYTHON, ['-I', faultPath, 'block-dashboard'], { env: process.env, stdio: ['pipe', 'pipe', 'pipe'] });
  try {
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Dashboard DB lock timeout')), 15000);
      blocker.stdout.once('data', data => { clearTimeout(timer); if (data.toString().trim() === 'DB_LOCKED') resolve(); else reject(new Error('Unexpected lock evidence')); });
      blocker.once('exit', () => { clearTimeout(timer); reject(new Error('Lock helper exited before readiness')); });
    });
    await page.getByRole('button', { name: 'Refresh dashboard', exact: true }).click();
    await check(page.getByText(/STALE/).first()).toBeVisible();
    await check(page.getByRole('alert').first()).toContainText(/unavailable|timed out/i);
    const denial = await page.evaluate(async () => {
      const response = await fetch('/api/v1/dashboard');
      return { status: response.status, body: await response.json() };
    });
    assert.equal(denial.status, 503, 'Real locked PG projection should be unavailable');
    assert.ok(['CONTROL_UNAVAILABLE', 'CONTROL_TIMEOUT'].includes(denial.body.error.code));
    await screenshot('b03-projection-stale-503');
    await observeBusy(() => page.getByRole('link', { name: visible.payload.name, exact: true }).click(), visible.engagement_id);
    await check(page.getByRole('alert').first()).toContainText(/unavailable|timed out/i);
    await check(page.getByRole('heading', { name: visible.payload.name, exact: true })).toBeVisible();
    console.log('B03_A02_BUSY_PASS initial_overview initial_setup refresh_success both_surfaces revalidation_real_503');
  } finally {
    if (blocker.exitCode === null) {
      const exited = new Promise(resolve => blocker.once('exit', resolve));
      blocker.stdin.end('release\n');
      const fuse = setTimeout(() => blocker.kill('SIGTERM'), 3000);
      await exited;
      clearTimeout(fuse);
    }
    assert.equal(blocker.exitCode, 0, 'Owned DB lock helper did not join normally');
  }
  await page.getByRole('link', { name: 'Home', exact: true }).click();
  await page.getByRole('button', { name: 'Refresh dashboard', exact: true }).click();
  await check(page.getByRole('alert')).toHaveCount(0);
  // Real PG session expiry, not a mocked 401; every private surface must disappear.
  fault('expire-session');
  await page.getByRole('button', { name: 'Refresh dashboard', exact: true }).click();
  await check(page.getByLabel('Pairing code')).toBeVisible();
  await check(page.getByText('Your session expired or was revoked. Pair this browser again.')).toBeVisible();
  assert.equal(await page.getByRole('heading', { name: 'Recent engagements' }).count(), 0);
  await page.reload();
  await check(page.getByLabel('Pairing code')).toBeVisible();
  await page.screenshot({ path: join(output, 'b03-session-expired.png'), fullPage: true });
}
