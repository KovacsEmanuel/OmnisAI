import assert from 'node:assert/strict';
import { randomBytes, randomUUID, createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { writeSync, writeFileSync } from 'node:fs';
import { createConnection } from 'node:net';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import { chromium, expect } from '@playwright/test';
import { assertSecretFree } from './leaks.mjs';
import { runB03 } from './b03.mjs';
import { runB04 } from './b04.mjs';
import { runCatalog } from './catalog.mjs';
import { runSettingsModels, runSettingsRemove } from './settings-models.mjs';
import { runS1 } from './s1-run.mjs';

const check = expect.configure({ timeout: 15000 });
const origin = process.env.OMNIS_E2E_ORIGIN;
const directory = process.env.OMNIS_E2E_CONTROL;
const output = process.env.OMNIS_E2E_OUTPUT;
const scenario = process.argv[2];
assert.match(origin ?? '', /^http:\/\/127\.0\.0\.1:[0-9]+$/);
assert.ok(directory && output && process.env.OMNIS_E2E_DATABASE_URL, 'Run via make test-e2e with an owned DB');
const sensitive = [];
const markerFd = Number(process.env.OMNIS_E2E_MARKER_FD);
assert.ok(Number.isInteger(markerFd) && markerFd >= 3, 'Private marker channel is required');
// The second B04 browser joins the same parent-owned marker channel after a real API restart.
if (!(scenario === 'b04' && process.env.OMNIS_E2E_STAGE === 'after')) writeSync(markerFd, 'READY\n');
function remember(value) {
  assert.ok(typeof value === 'string' && /^[A-Za-z0-9_-]{16,128}$/.test(value), 'Invalid synthetic marker');
  if (sensitive.includes(value)) return;
  assert.ok(sensitive.length < 128, 'Too many synthetic markers');
  sensitive.push(value);
  const record = Buffer.from(`SECRET ${value}\n`);
  assert.equal(writeSync(markerFd, record), record.length, 'Incomplete private marker evidence');
}
const requests = [];
const consoleMessages = [];
const pageErrors = [];
const external = [];
const diagnosticPath = '/api/v1/diagnostics/ui-events';
const diagnosticContract = JSON.parse(await readFile(new URL('../../../contracts/omnis.openapi.json', import.meta.url), 'utf8')).components.schemas;
const diagnosticEvents = new Map(), diagnosticReceipts = [], diagnosticTasks = [], diagnosticErrors = [];
let negativeDiagnostic = null, diagnosticProbeCorrelation = null;
let postludePhase = 'NOT_ENTERED', postludeFailure = null, postludeWriteFailed = false;
function observePostlude(phase, error) {
  if (scenario !== 's1-run') return;
  if (arguments.length > 1 && postludeFailure === null) postludeFailure = { phase: postludePhase,
    kind: error instanceof assert.AssertionError ? 'ASSERTION' : error instanceof Error ? 'ERROR' : 'NON_ERROR' };
  postludePhase = phase;
  try {
    const data = JSON.stringify({ version: 1, stage: process.env.OMNIS_E2E_STAGE === 'before' ? 'BEFORE' : process.env.OMNIS_E2E_STAGE === 'after' ? 'AFTER' : 'UNKNOWN',
      phase, firstFailure: postludeFailure, tasks: diagnosticTasks.length, receipts: diagnosticReceipts.length, errors: diagnosticErrors.length, writeFailed: postludeWriteFailed });
    if (Buffer.byteLength(data) > 1024) { postludeWriteFailed = true; return; }
    writeFileSync(join(output, 's1-postlude.json'), data, { mode: 0o600 });
  } catch { postludeWriteFailed = true; }
}
function diagnosticPost(request) { return request.method() === 'POST' && request.url() === `${origin}${diagnosticPath}`; }
function diagnosticBody(value) {
  assert.ok(value && typeof value === 'object' && !Array.isArray(value));
  const schema = diagnosticContract.UiEvent;
  assert.deepEqual(Object.keys(value).sort(), [...schema.required].sort());
  assert.equal(value.version, 1); assert.equal(value.source, 'browser_untrusted');
  for (const key of ['site', 'surface', 'action', 'outcome']) assert.ok(schema.properties[key].enum.includes(value[key]));
  for (const key of ['event_id', 'run_id', 'command_id', 'correlation_id']) {
    if (key !== 'event_id' && value[key] === null) continue;
    assert.equal(typeof value[key], 'string'); assert.match(value[key], new RegExp(schema.properties.event_id.pattern));
  }
  assert.ok(value.error_code === null || [...diagnosticContract.ErrorCode.enum, 'API_UNAVAILABLE', 'INVALID_RESPONSE'].includes(value.error_code));
  assert.ok(Buffer.byteLength(JSON.stringify(value)) <= 4096);
}
const faultPath = fileURLToPath(new URL('../../../api/tests/web_fault.py', import.meta.url));

async function control(command) {
  const capability = await readFile(join(directory, 'control.cap'), 'utf8');
  remember(capability);
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
  remember(code);
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
context.on('request', request => requests.push(request.url()));
context.on('request', request => {
  if (!diagnosticPost(request)) return;
  const value = request.postDataJSON();
  if (negativeDiagnostic && value.event_id === negativeDiagnostic.id) {
    assert.equal(value.message, negativeDiagnostic.secret);
    const { message: _message, ...metadata } = value; diagnosticBody(metadata);
  } else { diagnosticBody(value); diagnosticEvents.set(value.event_id, value); }
});
context.on('response', response => {
  if (!diagnosticPost(response.request())) return;
  diagnosticTasks.push((async () => {
    const value = response.request().postDataJSON();
    if (negativeDiagnostic && value.event_id === negativeDiagnostic.id) { assert.equal(response.status(), 422); return; }
    const correlation = response.headers()['x-correlation-id'];
    assert.match(correlation ?? '', new RegExp(diagnosticContract.UiEvent.properties.event_id.pattern));
    if (response.status() !== 202) {
      assert.ok([401, 403, 503].includes(response.status()));
      diagnosticReceipts.push({ event: value, request_correlation_id: correlation, state: 'HTTP_REFUSED' }); return;
    }
    let body;
    try { body = await response.body(); }
    catch { diagnosticReceipts.push({ event: value, request_correlation_id: correlation, state: 'TRANSPORT_UNCONFIRMED' }); return; }
    const ack = JSON.parse(body.toString('utf8'));
    assert.deepEqual(Object.keys(ack).sort(), ['accepted', 'event_id', 'state', 'version']);
    assert.equal(ack.version, 1); assert.equal(ack.accepted, true); assert.equal(ack.event_id, value.event_id);
    assert.ok(diagnosticContract.UiAck.properties.state.enum.includes(ack.state));
    diagnosticReceipts.push({ event: value, request_correlation_id: correlation, state: ack.state });
  })().catch(() => { diagnosticErrors.push('INVALID_DIAGNOSTIC_ACK'); }));
});
context.on('page', opened => {
  opened.on('console', message => consoleMessages.push(message.text()));
  opened.on('pageerror', error => pageErrors.push(error.message));
});
const page = await context.newPage();

async function pair(code) {
  remember(code);
  await page.getByLabel('Pairing code').fill(code);
  await page.getByRole('button', { name: 'Pair browser' }).click();
}

async function paired() {
  const grant = await issue();
  await pair(grant.code);
  // The diagnostic P0 surface now lives under global Settings, not Home.
  await check(page.getByLabel('Pairing code')).toHaveCount(0);
  await page.goto(`${origin}/settings/runtime`);
  await page.getByText('Instance diagnostics', { exact: true }).click();
  await check(page.getByText(grant.status.instance_id, { exact: true })).toBeVisible();
  await check(page.getByRole('button', { name: 'Start assessment' })).toBeDisabled();
  const cookie = (await context.cookies()).find(item => item.name === 'omnis_session');
  assert.ok(cookie, 'Missing synthetic session cookie');
  remember(cookie.value);
  const view = await page.evaluate(async () => (await fetch('/api/session')).json());
  remember(view.csrf_token);
  if (scenario === 'b04' && process.env.OMNIS_E2E_STAGE === 'before' && !diagnosticProbeCorrelation) {
    const missing = randomUUID();
    const failures = new Set();
    const collectFailure = response => {
      if (response.request().method() === 'GET' && response.status() === 404 && response.url().startsWith(`${origin}/api/v1/engagements/${missing}`)) failures.add(response.headers()['x-correlation-id']);
    };
    page.on('response', collectFailure);
    await page.goto(`${origin}/engagements/${missing}/overview`);
    // Draft/run reads may race; match an actual same-subject 404, never an invented correlation.
    await check.poll(() => diagnosticReceipts.some(item => item.state === 'RECORDED' && item.event.action === 'ERROR' && failures.has(item.event.correlation_id))).toBe(true);
    page.off('response', collectFailure);
    const seed = diagnosticReceipts.find(item => item.state === 'RECORDED' && item.event.action === 'ERROR' && failures.has(item.event.correlation_id)).event;
    diagnosticProbeCorrelation = seed.correlation_id;
    negativeDiagnostic = { id: randomUUID(), secret: randomBytes(24).toString('base64url') };
    remember(negativeDiagnostic.secret);
    const rejected = await page.evaluate(async ({ body, csrf }) => (await fetch('/api/v1/diagnostics/ui-events', {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify(body),
    })).status, { body: { ...seed, event_id: negativeDiagnostic.id, message: negativeDiagnostic.secret }, csrf: view.csrf_token });
    assert.equal(rejected, 422);
  }
  return grant;
}

async function secretChecks(inspected = page) {
  const storage = await inspected.evaluate(async () => ({ local: localStorage.length, session: sessionStorage.length,
    cookies: document.cookie, caches: await caches.keys(), databases: await indexedDB.databases(),
    workers: (await navigator.serviceWorker.getRegistrations()).length }));
  assert.equal(storage.local, 0);
  if (!['settings-models', 'settings-remove', 'settings-stop-read', 'settings-cancel-probe', 'settings-cancel-current'].includes(scenario)) assert.equal(storage.session, 0);
  else {
    const retained = await inspected.evaluate(() => Object.fromEntries(Object.keys(sessionStorage).map(key => [key, sessionStorage.getItem(key)])));
    assert.ok(Object.keys(retained).every(key => ['omnis-entry-test-v1', 'omnis-entry-test-v1-refused', 'omnis-settings-command-v1', 'omnis-settings-catalog-v1'].includes(key)), 'Unexpected retained Settings data');
    assertSecretFree(sensitive, [JSON.stringify(retained)]);
  }
  assert.equal(storage.cookies, '');
  assert.deepEqual(storage.caches, []);
  assert.deepEqual(storage.databases, []);
  assert.equal(storage.workers, 0);
  const content = await inspected.content();
  const liveValues = await inspected.locator('input, textarea').evaluateAll(elements => elements.map(element => element.value));
  assertSecretFree(sensitive, [...requests, ...consoleMessages, ...pageErrors, content, ...liveValues]);
  assert.deepEqual(external, [], 'Browser attempted an external request');
  assert.deepEqual(pageErrors, [], 'Browser JavaScript failure');
}

async function screenshot(name, { fullPage = true } = {}) {
  await page.screenshot({ path: join(output, `${name}.png`), fullPage });
}

let blocker;
let catalogEvidence;
try {
  if (scenario !== 'accessibility') {
    // The E2E fixture boots API/supervisor without the installed launcher.
    // Open the inert admission barrier only after API/dashboard readiness;
    // this is fixture setup, not proof of installed CLI lifecycle.
    const initial = (await control({ op: 'status' })).status;
    if (['s1-run', 'settings-models', 'settings-remove', 'settings-stop-read', 'settings-cancel-probe', 'settings-cancel-current'].includes(scenario) || (scenario === 'b04' && process.env.OMNIS_E2E_STAGE === 'after')) {
      assert.equal(initial.admission_open, true, 'Backend restart must preserve the same admitted instance');
      assert.equal(initial.generation, 1);
    } else {
      assert.equal(initial.admission_open, false);
      assert.equal(initial.generation, 0);
      const opened = (await control({ op: 'open', instance_id: initial.instance_id,
        command_id: randomUUID(), expected_generation: initial.generation })).status;
      assert.equal(opened.admission_open, true);
      assert.equal(opened.generation, 1);
    }
  }
  try {
    await page.goto(origin);
  } catch (error) {
    // Initial navigation is before pairing: log only local pathnames/statuses, never values.
    console.error('E2E_BOOT_NAVIGATION_DIAGNOSTIC ' + JSON.stringify({
      paths: requests.filter(url => url.startsWith(`${origin}/`)).map(url => new URL(url).pathname).slice(0, 20),
      externalCount: external.length, pageErrorCount: pageErrors.length,
    }));
    throw error;
  }
  await check(page.getByLabel('Pairing code')).toBeVisible();
  if (scenario === 'b03') {
    await runB03({ page, context, check, paired, fault, output, origin, screenshot, secretChecks });
  } else if (scenario === 'b04') {
    await runB04({ page, context, check, paired, fault, output, origin, screenshot, secretChecks });
  } else if (scenario === 'catalog') {
    catalogEvidence = await runCatalog({ page, check, paired, output, origin, screenshot, secretChecks });
  } else if (scenario === 's1-run') {
    observePostlude('SCENARIO_ENTER');
    catalogEvidence = await runS1({ page, check, paired, origin, output, screenshot, secretChecks, remember });
    observePostlude('SCENARIO_DONE');
  } else if (scenario === 'settings-remove') {
    catalogEvidence = await runSettingsRemove({ page, check, paired, origin, output, screenshot, secretChecks, remember });
  } else if (['settings-models', 'settings-stop-read', 'settings-cancel-probe', 'settings-cancel-current'].includes(scenario)) {
    catalogEvidence = await runSettingsModels({ page, check, paired, origin, output, screenshot, secretChecks, remember });
  } else if (scenario === 'flow') {
    const foreignHost = await context.request.get(`${origin}/health/live`, { headers: { Host: 'attacker.invalid', 'X-Forwarded-Host': new URL(origin).host } });
    assert.equal(foreignHost.status(), 400);
    const foreignOrigin = await context.request.post(`${origin}/api/pairing`, { headers: { Origin: 'null' }, data: { code: 'synthetic-invalid-origin-code' } });
    remember('synthetic-invalid-origin-code');
    assert.equal(foreignOrigin.status(), 403);
    await pair('synthetic-invalid-pairing-code');
    await check(page.getByRole('alert')).toContainText('invalid, expired or already used');
    await check(page.getByLabel('Pairing code')).toBeFocused();
    assert.equal(await page.getByLabel('Pairing code').inputValue(), '');
    const grant = await paired();
    const cookies = await context.cookies();
    const cookie = cookies.find(item => item.name === 'omnis_session');
    assert.ok(cookie, 'Cookie missing');
    remember(cookie.value);
    assert.ok(cookie.httpOnly && cookie.sameSite === 'Strict' && cookie.path === '/' && !cookie.secure);
    const payload = await page.evaluate(async () => (await fetch('/api/session')).json());
    remember(payload.csrf_token);
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
    await page.getByText('Instance diagnostics', { exact: true }).click();
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
    assert.equal(await page.locator('main').evaluate(element => getComputedStyle(element).outlineWidth), '2px');
    await page.getByRole('link', { name: 'Settings', exact: true }).click();
    await check(page.locator('main')).toBeFocused();
    assert.equal(await page.locator('main').evaluate(element => getComputedStyle(element).outlineStyle), 'none');
    await page.keyboard.press('Shift+Tab');
    await check(page.getByRole('button', { name: 'Light theme', exact: true })).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await check(page.getByRole('link', { name: 'Settings', exact: true })).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await page.keyboard.press('Enter');
    await check(page.locator('main')).toBeFocused();
    assert.equal(await page.locator('main').evaluate(element => getComputedStyle(element).outlineWidth), '2px');
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
  observePostlude('SECRETS_ENTER');
  await secretChecks();
  observePostlude('SECRETS_DONE');
} catch (error) {
  observePostlude('FAILURE', error);
  throw error;
} finally {
  try {
    if (blocker) await new Promise(resolve => {
      blocker.stdin.end('release\n'); blocker.once('exit', resolve);
      setTimeout(() => { blocker.kill(); resolve(); }, 3000).unref();
    }).catch(error => { observePostlude('FAILURE', error); throw error; });
  } finally {
    try {
      observePostlude('CONTEXT_CLOSE_ENTER');
      await context.close().catch(error => { observePostlude('FAILURE', error); throw error; });
      observePostlude('CONTEXT_CLOSE_DONE');
    } finally {
      observePostlude('BROWSER_CLOSE_ENTER');
      await browser.close().catch(error => { observePostlude('FAILURE', error); throw error; });
      observePostlude('BROWSER_CLOSE_DONE');
    }
  }
}

try {
  // Pending body reads can require page closure; close their producer before joining them.
  observePostlude('DIAGNOSTICS_ENTER');
  await Promise.all(diagnosticTasks);
  observePostlude('DIAGNOSTICS_DONE');
  assert.deepEqual(diagnosticErrors, []);
  if (scenario === 'b04') await writeFile(join(output, `ui-diagnostics-${process.env.OMNIS_E2E_STAGE}.json`), JSON.stringify({
    receipts: diagnosticReceipts, probe_correlation: diagnosticProbeCorrelation, complete: false,
  }));
  observePostlude('RESULT_ENTER');
  await writeFile(join(output, 'browser-result.json'), JSON.stringify({ scenario, passed: scenario === 'settings-cancel-probe' ? null : true, browser: browser.version(),
    ...(scenario === 'b04' ? { stage: process.env.OMNIS_E2E_STAGE } : {}),
    ...(catalogEvidence ? { catalog: catalogEvidence } : {}),
    requestCount: requests.length, externalRequests: external.length, pageErrors: pageErrors.length,
    secretChecks: true, scope: 'owned PostgreSQL/API/supervisor + built assets, synthetic pairing only' }, null, 2));
  observePostlude('RESULT_DONE');
  console.log(`E2E ${scenario === 'settings-cancel-probe' ? 'DIAGNOSTIC' : 'PASS'} ${scenario}: real backend, synthetic pairing, browser ${browser.version()}`);
} catch (error) {
  observePostlude('FAILURE', error);
  throw error;
}
