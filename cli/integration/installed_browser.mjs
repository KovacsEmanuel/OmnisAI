// Owned finite lab browser; secrets enter only on stdin, never personal profiles.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const selection = { provider: 'openai-codex', model: 'gpt-6.1-sol', effort: 'xhigh' };
const route = '/api/v1/settings/provider';
export function assertProvider(value, id, configured) {
  assert.deepEqual(value, { operation_id: id, status: 'CONFIRMED',
    selection: configured ? selection : null, configured,
    authenticated: 'NOT_VERIFIED', reachable: 'NOT_VERIFIED', inference_ready: false });
}
export function assertDenial(status, value, expected, reason) {
  assert.equal(status, expected); assert.equal(value.error?.code, reason);
}
export function assertJourney(mode, operations) {
  assert.deepEqual(operations.map(item => item.action), mode === 'settings-save' ? ['read', 'save', 'read'] : ['read']);
  assert.equal(new Set(operations.map(item => item.id)).size, operations.length);
}

async function settings(page, context, expect, origin, mode, manifestText, captures) {
  const manifest = JSON.parse(manifestText);
  const manifestSha256 = createHash('sha256').update(manifestText).digest('hex');
  // Bind the supplied installed manifest to every actual served byte, not checkout/dist alone.
  assert.equal(manifest.version, 1);
  assert.ok(Object.hasOwn(manifest.files, 'index.html'));
  assert.ok(Object.keys(manifest.files).some(name => name.endsWith('.js')));
  for (const [name, digest] of Object.entries(manifest.files)) {
    assert.match(name, /^(index\.html|assets\/[A-Za-z0-9_.-]+)$/);
    const response = await context.request.get(`${origin}/${name === 'index.html' ? '' : name}`, { maxRedirects: 0, timeout: 5000 });
    assert.equal(response.status(), 200);
    assert.equal(createHash('sha256').update(await response.body()).digest('hex'), digest);
  }
  const session = await context.request.get(`${origin}/api/session`, { maxRedirects: 0, timeout: 5000 });
  const csrf = (await session.json()).csrf_token;
  const negativeId = crypto.randomUUID();
  const data = { operation_id: negativeId, action: 'read', selection: null };
  for (const [headers, status, reason] of [
    [{ Origin: origin, Cookie: '', 'X-CSRF-Token': csrf }, 401, 'UNAUTHENTICATED'],
    [{ Origin: origin }, 403, 'INVALID_CSRF'],
    [{ Origin: 'http://attacker.invalid', 'X-CSRF-Token': csrf }, 403, 'INVALID_ORIGIN'],
    [{ Origin: origin, Host: 'attacker.invalid', 'X-CSRF-Token': csrf }, 400, 'INVALID_HOST'],
  ]) {
    const response = await context.request.put(`${origin}${route}`, { headers, data, maxRedirects: 0, timeout: 5000 });
    assertDenial(response.status(), await response.json(), status, reason);
  }
  const unseen = await context.request.get(`${origin}${route}/operations/${negativeId}`, { maxRedirects: 0, timeout: 5000 });
  assert.equal(unseen.status(), 200);
  const refused = await unseen.json();
  assert.equal(refused.status, 'UNAVAILABLE');
  assert.equal(refused.configured, false);
  const providers = page.getByRole('navigation', { name: 'Settings navigation' }).getByRole('link', { name: 'Providers', exact: true });
  await providers.focus(); await expect(providers).toBeFocused(); await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Provider configuration' })).toBeVisible();
  for (const [name, value] of Object.entries(selection)) await expect(page.getByLabel(name[0].toUpperCase() + name.slice(1), { exact: true })).toHaveValue(value);
  const operations = [];
  const observed = [];
  page.on('request', request => {
    if (request.url() === `${origin}${route}` && request.method() === 'PUT') {
      const sent = request.postDataJSON(); observed.push({ action: sent.action, id: sent.operation_id });
    }
  });
  async function operation(action, configured) {
    const button = page.getByRole('button', { name: action === 'save' ? 'Save selection' : 'Read native configuration' });
    await button.focus(); await expect(button).toBeFocused();
    const pending = page.waitForResponse(response => response.url() === `${origin}${route}` && response.request().method() === 'PUT');
    await page.keyboard.press('Enter');
    const response = await pending;
    assert.equal(response.status(), 200);
    const sent = response.request().postDataJSON();
    assert.equal(sent.action, action);
    assert.deepEqual(sent.selection, action === 'save' ? selection : null);
    operations.push({ action, id: sent.operation_id });
    let value = await response.json();
    await expect.poll(async () => {
      if (value.status === 'PENDING') {
        const read = await context.request.get(`${origin}${route}/operations/${sent.operation_id}`, { maxRedirects: 0, timeout: 5000 });
        assert.equal(read.status(), 200); value = await read.json();
      }
      return value.status;
    }, { timeout: 30000 }).toBe('CONFIRMED');
    assertProvider(value, sent.operation_id, configured);
    await expect(page.getByText(`Configured: ${configured ? 'yes' : 'no'} — native readback`, { exact: true })).toBeVisible();
    for (const text of ['Authenticated: not verified', 'Provider reachable: not verified', 'Inference ready: no']) await expect(page.getByText(text, { exact: true })).toBeVisible();
  }
  await operation('read', mode === 'settings-readback');
  if (mode === 'settings-save') {
    await operation('save', true);
    await page.reload();
    await expect(page.getByText('Configured: not confirmed', { exact: true })).toBeVisible();
    await operation('read', true);
  }
  assertJourney(mode, operations);
  assert.deepEqual(observed, operations);
  await expect(page.getByRole('button', { name: 'Save selection' })).toBeDisabled();
  for (const [label, width, height] of [['desktop', 1440, 1000], ['mobile', 390, 844]]) {
    await page.setViewportSize({ width, height });
    await expect(page.getByLabel('Pairing code')).toHaveCount(0);
    const read = page.getByRole('button', { name: 'Read native configuration' });
    await read.focus(); await expect(read).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    assert.notEqual(await page.evaluate(() => document.activeElement?.tagName), 'BODY');
    await page.screenshot({ path: `${captures}/${mode}-${label}.png`, fullPage: true });
  }
  await writeFile(`${captures}/${mode}.json`, JSON.stringify({ manifest_sha256: manifestSha256, served_files: manifest.files,
    paired: true, exact_selection: true, fresh_operations: true, denials: true,
    configured: true, authenticated: 'NOT_VERIFIED', reachable: 'NOT_VERIFIED', inference_ready: false }), { mode: 0o600, flag: 'wx' });
}

async function main() {
  const mode = process.env.OMNIS_BROWSER_MODE ?? 'session';
  assert.ok(['session', 'settings-save', 'settings-readback'].includes(mode));
  const origin = process.env.OMNIS_BROWSER_ORIGIN;
  const instance = process.env.OMNIS_BROWSER_INSTANCE;
  assert.match(origin ?? '', /^http:\/\/127\.0\.0\.1:[0-9]+$/);
  assert.match(instance ?? '', /^[0-9a-f-]{36}$/);
  let input = '';
  for await (const chunk of process.stdin) {
    input += chunk.toString(); assert.ok(input.length <= (mode === 'session' ? 128 : 32768));
  }
  const payload = mode === 'session' ? { code: input } : JSON.parse(input);
  const code = payload.code;
  assert.match(code, /^[A-Za-z0-9_-]{16,128}$/);
  const module = process.env.OMNIS_PLAYWRIGHT_MODULE;
  const { chromium, expect } = await import(module ? pathToFileURL(module).href : '../../web/node_modules/@playwright/test/index.mjs');
  const browser = await chromium.launch();
  try {
    const context = await browser.newContext();
    context.setDefaultTimeout(10000);
    const external = [], requestUrls = [], pageErrors = [];
    await context.route('**/*', async route => {
      const url = route.request().url();
      if (!url.startsWith(`${origin}/`)) { external.push('off-origin'); await route.abort(); }
      else await route.continue();
    });
    const page = await context.newPage();
    page.on('request', request => requestUrls.push(request.url()));
    page.on('pageerror', () => pageErrors.push('page-error'));
    await page.goto(`${origin}/${mode === 'session' ? '' : 'settings/runtime'}`);
    await expect(page.getByLabel('Pairing code')).toBeVisible();
    await page.getByLabel('Pairing code').fill(code);
    await page.getByRole('button', { name: 'Pair browser' }).click();
    await expect(page.getByText(instance, { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Start assessment' })).toBeDisabled();
    const cookie = (await context.cookies()).find(item => item.name === 'omnis_session');
    assert.ok(cookie?.httpOnly && cookie.sameSite === 'Strict');
    assert.equal((await context.request.get(`${origin}/api/session`, { maxRedirects: 0, timeout: 5000 })).status(), 200);
    if (mode !== 'session') {
      await settings(page, context, expect, origin, mode, payload.manifest, process.env.OMNIS_BROWSER_CAPTURES);
      await page.goto(`${origin}/settings/runtime`);
    }
    await page.reload();
    await expect(page.getByText(instance, { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Log out' }).click();
    await expect(page.getByText('Logged out. The server session was revoked.')).toBeVisible();
    assert.equal((await context.request.get(`${origin}/api/session`, { maxRedirects: 0, timeout: 5000 })).status(), 401);
    assert.ok(requestUrls.every(url => !url.includes(code)), 'Private URL refused');
    assert.deepEqual(external, []); assert.deepEqual(pageErrors, []);
    console.log(mode === 'session' ? 'INSTALLED_BROWSER_SESSION_OK' : 'INSTALLED_SETTINGS_OK');
  } finally {
    await browser.close(); console.log('INSTALLED_BROWSER_CLOSED');
  }
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try { await main(); }
  catch { console.log('INSTALLED_BROWSER_FAILED'); process.exitCode = 1; }
}
