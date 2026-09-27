import assert from 'node:assert/strict';
import { randomBytes, randomUUID, createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { createConnection } from 'node:net';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import { chromium, expect } from '@playwright/test';

const check = expect.configure({ timeout: 15000 });
const origin = process.env.OMNIS_E2E_ORIGIN;
const directory = process.env.OMNIS_E2E_CONTROL;
const output = process.env.OMNIS_E2E_OUTPUT;
const scenario = process.argv[2];
assert.match(origin ?? '', /^http:\/\/127\.0\.0\.1:[0-9]+$/);
assert.ok(directory && output && process.env.OMNIS_E2E_DATABASE_URL, 'Run via make test-e2e with an owned DB');
const sensitive = [];
const requests = [];
const consoleMessages = [];
const pageErrors = [];
const external = [];
const faultPath = fileURLToPath(new URL('../../../api/tests/web_fault.py', import.meta.url));

async function control(command) {
  const capability = await readFile(join(directory, 'control.cap'), 'utf8');
  sensitive.push(capability);
  return new Promise((resolve, reject) => {
    let data = '';
    const socket = createConnection(join(directory, 'control.sock'));
    socket.setTimeout(5000);
    socket.on('connect', () => socket.write(JSON.stringify({ version: 1, capability, command }) + '\n'));
    socket.on('data', chunk => {
      data += chunk.toString();
      if (data.length > 4096) { socket.destroy(); reject(new Error('Oversized private reply')); }
      else if (data.endsWith('\n')) {
        socket.end();
        try {
          const response = JSON.parse(data);
          assert.equal(response.ok, true, 'Private status/pairing was refused');
          resolve(response);
        } catch { reject(new Error('Invalid private reply')); }
      }
    });
    socket.on('timeout', () => { socket.destroy(); reject(new Error('Private control timeout')); });
    socket.on('error', () => reject(new Error('Private control unavailable')));
  });
}

async function issue() {
  const status = (await control({ op: 'status' })).status;
  const code = randomBytes(24).toString('base64url');
  sensitive.push(code);
  await control({ op: 'pairing', instance_id: status.instance_id, issuance_id: randomUUID(),
    digest: createHash('sha256').update(code).digest('hex') });
  return { code, status };
}

function fault(operation) {
  const result = spawnSync(process.env.OMNIS_E2E_PYTHON, ['-I', faultPath, operation], {
    env: process.env, encoding: 'utf8', timeout: 15000,
  });
  assert.equal(result.status, 0, 'Attested DB fault helper failed');
}

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
await context.route('**/*', async route => {
  const url = route.request().url();
  if (!url.startsWith(`${origin}/`)) { external.push(url); await route.abort(); }
  else await route.continue();
});
const page = await context.newPage();
page.on('request', request => requests.push(request.url()));
page.on('console', message => consoleMessages.push(message.text()));
page.on('pageerror', error => pageErrors.push(error.message));

async function pair(code) {
  await page.getByLabel('Pairing code').fill(code);
  await page.getByRole('button', { name: 'Pair browser' }).click();
}

async function paired() {
  const grant = await issue();
  await pair(grant.code);
  await check(page.getByText(grant.status.instance_id, { exact: true })).toBeVisible();
  await check(page.getByRole('button', { name: 'Start assessment' })).toBeDisabled();
  return grant;
}

async function secretChecks() {
  const storage = await page.evaluate(async () => ({ local: localStorage.length, session: sessionStorage.length,
    cookies: document.cookie, caches: await caches.keys(), databases: await indexedDB.databases(),
    workers: (await navigator.serviceWorker.getRegistrations()).length }));
  assert.equal(storage.local, 0);
  assert.equal(storage.session, 0);
  assert.equal(storage.cookies, '');
  assert.deepEqual(storage.caches, []);
  assert.deepEqual(storage.databases, []);
  assert.equal(storage.workers, 0);
  const content = await page.content();
  for (const value of sensitive) {
    assert.ok(!requests.some(url => url.includes(value)), 'Secret in URL');
    assert.ok(!consoleMessages.some(line => line.includes(value)), 'Secret in browser log');
    assert.ok(!content.includes(value), 'Secret retained in DOM');
  }
  assert.deepEqual(external, [], 'Browser attempted an external request');
  assert.deepEqual(pageErrors, [], 'Browser JavaScript failure');
}

async function screenshot(name) {
  await page.screenshot({ path: join(output, `${name}.png`), fullPage: true });
}

let blocker;
try {
  await page.goto(origin);
  await check(page.getByLabel('Pairing code')).toBeVisible();
  if (scenario === 'flow') {
    const foreignHost = await context.request.get(`${origin}/health/live`, { headers: { Host: 'attacker.invalid', 'X-Forwarded-Host': new URL(origin).host } });
    assert.equal(foreignHost.status(), 400);
    const foreignOrigin = await context.request.post(`${origin}/api/pairing`, { headers: { Origin: 'null' }, data: { code: 'synthetic-invalid-origin-code' } });
    assert.equal(foreignOrigin.status(), 403);
    await pair('synthetic-invalid-pairing-code');
    await check(page.getByRole('alert')).toContainText('invalid, expired or already used');
    await check(page.getByLabel('Pairing code')).toBeFocused();
    assert.equal(await page.getByLabel('Pairing code').inputValue(), '');
    const grant = await paired();
    const cookies = await context.cookies();
    const cookie = cookies.find(item => item.name === 'omnis_session');
    assert.ok(cookie, 'Cookie missing');
    sensitive.push(cookie.value);
    assert.ok(cookie.httpOnly && cookie.sameSite === 'Strict' && cookie.path === '/' && !cookie.secure);
    const payload = await page.evaluate(async () => (await fetch('/api/session')).json());
    sensitive.push(payload.csrf_token);
    assert.equal(typeof payload.csrf_token, 'string');
    for (const token of [null, 'synthetic-wrong-csrf']) {
      const denied = await page.evaluate(async value => {
        const response = await fetch('/api/logout', { method: 'POST', headers: value ? { 'X-CSRF-Token': value } : {} });
        return { status: response.status, body: await response.json() };
      }, token);
      assert.equal(denied.status, 403);
      assert.equal(denied.body.error.code, 'INVALID_CSRF');
    }
    await page.reload();
    await check(page.getByText(grant.status.instance_id, { exact: true })).toBeVisible();
    await screenshot('instance-desktop');
    await secretChecks();
    await page.getByRole('button', { name: 'Log out' }).click();
    await check(page.getByText('Logged out. The server session was revoked.')).toBeVisible();
    assert.equal((await context.request.get(`${origin}/api/session`)).status(), 401);
    await pair(grant.code);
    await check(page.getByRole('alert')).toContainText('invalid, expired or already used');
  } else if (scenario === 'expiry') {
    const expired = await issue();
    fault('expire-code');
    await pair(expired.code);
    await check(page.getByRole('alert')).toContainText('invalid, expired or already used');
    await paired();
    fault('expire-session');
    await page.getByRole('button', { name: 'Refresh status' }).click();
    await check(page.getByLabel('Pairing code')).toBeVisible();
    await check(page.getByText('Your session expired or was revoked. Pair this browser again.')).toBeVisible();
    await screenshot('session-expired');
  } else if (scenario === 'control') {
    await paired();
    process.kill(Number(process.env.OMNIS_E2E_SUPERVISOR_PID), 'SIGTERM');
    await page.getByRole('button', { name: 'Refresh status' }).click();
    await check(page.getByText('The private control channel could not be verified. Check the local supervisor.')).toBeVisible();
    const health = await context.request.get(`${origin}/health/ready`);
    assert.equal((await health.json()).dashboard_ready, false);
    await screenshot('control-unavailable');
  } else if (scenario === 'database') {
    await paired();
    blocker = spawn(process.env.OMNIS_E2E_PYTHON, ['-I', faultPath, 'block-db'], { env: process.env, stdio: ['pipe', 'pipe', 'pipe'] });
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('DB lock fixture timeout')), 15000);
      blocker.stdout.once('data', data => { clearTimeout(timeout); if (data.toString().trim() === 'DB_LOCKED') resolve(); else reject(new Error('Unexpected DB lock signal')); });
      blocker.once('exit', () => { clearTimeout(timeout); reject(new Error('DB lock fixture exited early')); });
    });
    await page.getByRole('button', { name: 'Refresh status' }).click();
    await check(page.getByText('PostgreSQL is unavailable. Check the local database service.')).toBeVisible();
    await check(page.getByRole('alert').first()).toContainText('unavailable');
    await screenshot('database-unavailable');
  } else if (scenario === 'api') {
    await paired();
    process.kill(Number(process.env.OMNIS_E2E_API_PID), 'SIGTERM');
    await page.getByRole('button', { name: 'Refresh status' }).click();
    await check(page.getByRole('alert').first()).toContainText('API could not be reached');
    await check(page.getByText('UNKNOWN', { exact: true }).first()).toBeVisible();
    await screenshot('api-unavailable');
  } else if (scenario === 'offline') {
    await paired();
    await context.setOffline(true);
    assert.equal(await page.evaluate(() => navigator.onLine), false);
    await page.getByRole('button', { name: 'Refresh status' }).click();
    await check(page.getByRole('alert').first()).toContainText('API could not be reached');
    await check(page.getByText('UNKNOWN', { exact: true }).first()).toBeVisible();
    await check(page.getByText('STALE — showing the last confirmed response, not current state.')).toBeVisible();
    await screenshot('browser-offline');
    await context.setOffline(false);
  } else if (scenario === 'accessibility') {
    await page.keyboard.press('Tab');
    await check(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
    await page.keyboard.press('Enter');
    await check(page.locator('main')).toBeFocused();
    for (const width of [320, 390, 1024, 1280, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Overflow at ${width}`);
      await page.getByLabel('Pairing code').focus();
      const outline = await page.getByLabel('Pairing code').evaluate(element => getComputedStyle(element).outlineWidth);
      assert.equal(outline, '2px');
      const inputBox = await page.getByLabel('Pairing code').boundingBox();
      assert.ok(inputBox && inputBox.height >= 44 && inputBox.width >= 44);
      if (width === 390 || width === 1440) { await page.locator('body').click({ position: { x: 1, y: 1 } }); await page.evaluate(() => scrollTo(0, 0)); await screenshot(`pairing-${width}`); }
    }
    for (const element of await page.locator('a:visible, button:visible, input:visible').all()) {
      const box = await element.boundingBox();
      assert.ok(box && box.height >= 44, `Touch target under 44px: ${await element.textContent()}`);
    }
    await page.getByLabel('Pairing code').focus();
    await page.keyboard.type('short');
    await page.keyboard.press('Enter');
    await check(page.getByRole('alert')).toContainText('Enter the exact code');
    await check(page.getByLabel('Pairing code')).toBeFocused();
    await page.getByLabel('Pairing code').fill('');
    await page.emulateMedia({ reducedMotion: 'reduce', forcedColors: 'active' });
    assert.ok(await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches));
    assert.equal(await page.getByLabel('Pairing code').evaluate(element => getComputedStyle(element).animationName), 'none');
    await screenshot('forced-colors-focus');
    await page.emulateMedia({ reducedMotion: 'reduce', forcedColors: 'none' });
    await page.evaluate(() => { document.documentElement.style.zoom = '2'; });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Overflow at 200% CSS zoom');
    await screenshot('zoom-200');
    await page.evaluate(() => { document.documentElement.style.zoom = ''; });
    const colors = await page.evaluate(() => {
      const style = getComputedStyle(document.documentElement);
      return Object.fromEntries(['text', 'secondary', 'surface', 'danger', 'dangerBg', 'warning', 'warningBg', 'border', 'neutral', 'focus'].map(name => [name, style.getPropertyValue(`--color-${name}`).trim()]));
    });
    const luminance = hex => {
      const channels = hex.slice(1).match(/../g).map(value => parseInt(value, 16) / 255).map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
      return .2126 * channels[0] + .7152 * channels[1] + .0722 * channels[2];
    };
    const contrast = [];
    for (const [fg, bg, minimum] of [['text','surface',4.5], ['secondary','surface',4.5], ['danger','dangerBg',4.5], ['warning','warningBg',4.5], ['border','neutral',3], ['focus','neutral',3]]) {
      const a = luminance(colors[fg]); const b = luminance(colors[bg]);
      const ratio = (Math.max(a,b) + .05) / (Math.min(a,b) + .05);
      assert.ok(ratio >= minimum, `Contrast ${fg}/${bg} below ${minimum}`);
      contrast.push({ fg, bg, ratio, minimum });
    }
    await writeFile(join(output, 'contrast.json'), JSON.stringify(contrast, null, 2));
  } else throw new Error('Unknown E2E case');
  await secretChecks();
  await writeFile(join(output, 'result.json'), JSON.stringify({ scenario, passed: true, browser: browser.version(),
    requestCount: requests.length, externalRequests: external.length, pageErrors: pageErrors.length,
    secretChecks: true, scope: 'owned PostgreSQL/API/supervisor + built assets, synthetic pairing only' }, null, 2));
  console.log(`E2E PASS ${scenario}: real backend, synthetic pairing, browser ${browser.version()}`);
} finally {
  if (blocker) { blocker.stdin.end('release\n'); await new Promise(resolve => { blocker.once('exit', resolve); setTimeout(() => { blocker.kill(); resolve(); }, 3000).unref(); }); }
  await context.close();
  await browser.close();
}
