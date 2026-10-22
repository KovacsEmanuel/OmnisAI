// SOURCE browser regression: real built App, synthetic HTTP only; no API/PG/provider.
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import test from 'node:test';
import { preview } from 'vite';
import { chromium, expect } from '@playwright/test';

const check = expect.configure({ timeout: 1500 });
const id = '11111111-1111-4111-8111-111111111111';
const connection = { connection_id: id, provider: 'openrouter', revision: 1, enabled: true, credential_present: true };
const selected = { connection_id: id, connection_revision: 1, model: 'Exact/Current', output_tokens: 128 };
const current = { schema_version: 2, command_id: null, vault_status: 'UNLOCKED', connections: [connection],
  selection: { selection_id: id, revision: 1, default: selected, brain: selected, investigator: null, validator: null }, reachable: 'NOT_VERIFIED' };
const paint = page => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));

// Run after npm run build: node --test tests/e2e/provider-settings-focus.mjs
await test('QA-SETTINGS-FOCUS-01: rendered pending PUT and GET retain native focus', { timeout: 30000 }, async t => {
  const server = await preview({ configFile: false, root: fileURLToPath(new URL('../..', import.meta.url)),
    preview: { host: '127.0.0.1', port: 0, strictPort: true, cors: false } });
  const origin = `http://127.0.0.1:${server.httpServer.address().port}`;
  let browser;
  try {
    browser = await chromium.launch();
    console.log(`SOURCE Chromium ${browser.version()}; built App; synthetic HTTP; loopback only`);
    for (const moved of [false, true]) await t.test(`operator moved focus=${moved}`, async () => {
      const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
      const put = Promise.withResolvers();
      const readback = Promise.withResolvers();
      const refresh = Promise.withResolvers();
      const writes = [], unexpected = [], errors = [];
      let reading = false, refreshing = false;
      const after = { ...current, selection: { ...current.selection, revision: 2 } };
      try {
        await context.route('**/*', async route => {
          const request = route.request(), url = new URL(request.url());
          if (url.origin !== origin) { unexpected.push(request.url()); return route.abort(); }
          if (url.pathname === '/api/session') return route.fulfill({ json: { authenticated: true, csrf_token: 'a'.repeat(64) } });
          if (url.pathname === '/health/ready') return route.fulfill({ json: { api_ready: true, dashboard_ready: true, assessment_ready: false, reason: null, dashboard_reason: null } });
          if (url.pathname === '/api/v1/settings/providers') {
            if (request.method() === 'PUT') {
              const body = request.postDataJSON(); writes.push(body);
              await put.promise;
              return route.fulfill({ json: { ...after, command_id: body.command_id } });
            }
            if (request.method() === 'GET') {
              if (writes.length) {
                if (!reading) { reading = true; await readback.promise; }
                else { refreshing = true; await refresh.promise; }
              }
              return route.fulfill({ json: writes.length ? after : current });
            }
          }
          if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/health/')) {
            unexpected.push(`${request.method()} ${url.pathname}`); return route.abort();
          }
          return route.continue();
        });
        const page = await context.newPage();
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(`${origin}/settings/providers`);
        const save = page.getByRole('button', { name: 'Save model selection', exact: true });
        const elsewhere = page.getByRole('link', { name: 'Providers', exact: true });
        await check(save).toBeEnabled();
        await page.getByLabel('Default model', { exact: true }).fill('Exact/Submitted');
        await page.getByLabel('Brain override', { exact: true }).uncheck();
        // Native Tab -> Enter, not a synthetic submit or imperative focus restoration.
        await page.getByLabel('Validator override', { exact: true }).focus();
        await page.keyboard.press('Tab');
        await check(save).toBeFocused();
        await page.keyboard.press('Enter');
        await check.poll(() => writes.length).toBe(1);
        await check(page.getByText('Operation pending; no success confirmed.', { exact: true })).toBeVisible();
        await paint(page);
        console.log(JSON.stringify({ moved, phase: 'PUT pending', ...await save.evaluate(button => ({
          active: document.activeElement.tagName, disabled: button.disabled, ariaDisabled: button.getAttribute('aria-disabled'),
          cursor: getComputedStyle(button).cursor, color: getComputedStyle(button).color,
        })) }));
        if (moved) await elsewhere.focus();
        else await check(save).toBeFocused();
        await check(save).toHaveAttribute('aria-disabled', 'true');
        await check(save).toHaveCSS('cursor', 'not-allowed');
        const disabled = page.getByRole('button', { name: 'Recover exact receipt', exact: true });
        await check(save).toHaveCSS('color', await disabled.evaluate(button => getComputedStyle(button).color));
        await save.hover({ force: true });
        await check(save).toHaveCSS('background-color', await disabled.evaluate(button => getComputedStyle(button).backgroundColor));
        if (!moved && process.env.OMNIS_E2E_OUTPUT) await page.screenshot({ path: join(process.env.OMNIS_E2E_OUTPUT, 'focus-pending.png'), fullPage: true });
        const focus = moved ? elsewhere : save;
        // Native keyboard activation, click and direct form submission must all hit existing guards.
        if (!moved) for (let n = 0; n < 3; n++) await page.keyboard.press('Enter');
        await save.evaluate(button => { button.click(); button.click(); button.form.requestSubmit(); });
        await paint(page);
        assert.equal(writes.length, 1, 'no duplicate PUT while write pending');
        put.resolve();
        await check.poll(() => reading).toBe(true);
        await paint(page);
        await check(focus).toBeFocused();
        if (!moved) await page.keyboard.press('Enter');
        await save.evaluate(button => { button.click(); button.form.requestSubmit(); });
        await paint(page);
        assert.equal(writes.length, 1, 'no admission during authoritative GET');
        readback.resolve();
        await check(page.getByText(/Saved locally; current settings loaded/)).toBeVisible();
        // Re-enabling the current query starts one more read: keep that painted too.
        await check.poll(() => refreshing).toBe(true);
        await paint(page);
        await check(focus).toBeFocused();
        await check(save).toHaveAttribute('aria-disabled', 'true');
        if (!moved) await page.keyboard.press('Enter');
        await save.evaluate(button => { button.click(); button.form.requestSubmit(); });
        await paint(page);
        assert.equal(writes.length, 1, 'no admission during query refresh');
        console.log(JSON.stringify({ moved, phase: 'query refresh pending', puts: writes.length, focus: await focus.evaluate(node => document.activeElement === node) }));
        refresh.resolve();
        await check(save).toBeEnabled();
        await paint(page);
        await check(focus).toBeFocused();
        await check(page.getByLabel('Default model', { exact: true })).toHaveValue('Exact/Current');
        await check(page.getByLabel('Brain override', { exact: true })).toBeChecked();
        assert.equal(writes.length, 1);
        assert.equal(writes[0].action, 'save_selection');
        assert.equal(writes[0].expected_revision, 1);
        assert.equal(writes[0].default.model, 'Exact/Submitted');
        assert.equal(writes[0].brain, null);
        assert.deepEqual(unexpected, []);
        assert.deepEqual(errors, []);
        if (!moved) {
          await check(save).toHaveCSS('outline-style', 'solid');
          await check(save).toHaveCSS('outline-width', '2px');
        }
        console.log(JSON.stringify({ moved, phase: 'readback complete', puts: writes.length, focus: await focus.evaluate(node => document.activeElement === node) }));
      } finally {
        put.resolve(); readback.resolve(); refresh.resolve();
        await context.close();
      }
    });
  } finally {
    await browser?.close();
    await new Promise((resolve, reject) => server.httpServer.close(error => error ? reject(error) : resolve()));
    console.log('Cleanup: owned Chromium/context and loopback preview closed.');
  }
});
