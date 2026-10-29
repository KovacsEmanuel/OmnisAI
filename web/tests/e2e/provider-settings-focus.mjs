// SOURCE browser only: built App + synthetic HTTP, not API/PG/provider QA.
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import test from 'node:test';
import { preview } from 'vite';
import { chromium, expect } from '@playwright/test';
import { instance } from '../fixtures.ts';
const check = expect.configure({ timeout: 5000 });
const id = '11111111-1111-4111-8111-111111111111';
const other = '22222222-2222-4222-8222-222222222222';
const catalogId = '33333333-3333-4333-8333-333333333333';
const connection = { connection_id: id, provider: 'openrouter', revision: 1, enabled: true, credential_present: true };
const selected = { connection_id: id, connection_revision: 1, model: 'Exact/Current', output_tokens: 512 };
const initial = { schema_version: 2, command_id: null, vault_status: 'UNLOCKED', connections: [connection], selection: { selection_id: id, revision: 1, default: selected, brain: { ...selected, output_tokens: 37 }, investigator: null, validator: null }, reachable: 'NOT_VERIFIED' };
const paint = page => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
await test('Settings C SOURCE: painted focus, shared 900px axis, mobile and long 64-entry library', { timeout: 90000 }, async t => {
  const server = await preview({ configFile: false, root: fileURLToPath(new URL('../..', import.meta.url)), preview: { host: '127.0.0.1', port: 0, strictPort: true, cors: false } });
  const origin = `http://127.0.0.1:${server.httpServer.address().port}`;
  let browser;
  try {
    browser = await chromium.launch();
    for (const scenario of ['retained', 'moved', 'stale', 'long64']) await t.test(scenario, async () => {
      const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
      const writes = [], unexpected = [], errors = [], receipts = new Map();
      const put = Promise.withResolvers();
      let current = structuredClone(initial);
      let entries = scenario === 'long64' ? Array.from({ length: 64 }, (_, i) => ({ entry_id: `00000000-0000-4000-8000-${String(i).padStart(12, '0')}`, revision: 1, ...selected, model: `Exact/${String(i).padStart(2, '0')}/${'Long-exact-ID-'.repeat(18)}`.slice(0, 256) })) : [{ entry_id: id, revision: 1, ...selected }, { entry_id: other, revision: 1, ...selected, model: 'Other/Model' }];
      let registryRevision = 1;
      const catalogEntries = [...entries, ...(scenario === 'long64' ? [] : [{ ...selected, model: 'New/Model' }])].sort((a, b) => a.model.localeCompare(b.model));
      if (scenario === 'long64') current = { ...current, selection: null };
      function registry(after = null) {
        const start = after ? entries.findIndex(entry => entry.entry_id === after) + 1 : 0;
        const page = entries.slice(start, start + 16);
        return { schema_version: 1, command_id: null, registry_revision: registryRevision, total: entries.length, after, next_after: start + page.length < entries.length ? page.at(-1).entry_id : null, entries: page };
      }
      try {
        await context.route('**/*', async route => {
          const request = route.request(), url = new URL(request.url());
          if (url.origin !== origin) { unexpected.push(url.origin); return route.abort(); }
          const path = url.pathname;
          if (path === '/api/session') return route.fulfill({ json: { authenticated: true, csrf_token: 'a'.repeat(64) } });
          if (path === '/api/instance') return route.fulfill({ json: { ...instance, generation: 1, admission_open: true } });
          if (path.startsWith('/api/v1/model-test/entries/latest/')) return route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', correlation_id: id } } });
          if (path === '/health/ready') return route.fulfill({ json: { api_ready: true, dashboard_ready: true, assessment_ready: false, reason: null, dashboard_reason: null } });
          if (path === '/api/v1/settings/providers') {
            if (request.method() === 'PUT') {
              const body = request.postDataJSON(); writes.push(body); await put.promise;
              if (scenario === 'stale') return route.fulfill({ status: 409, json: { error: { code: 'REVISION_CONFLICT', correlation_id: id } } });
              current = { ...current, selection: { selection_id: body.command_id, revision: 2, default: body.default, brain: body.brain, investigator: body.investigator, validator: body.validator } };
              receipts.set(body.command_id, { ...current, command_id: body.command_id });
              return route.fulfill({ json: receipts.get(body.command_id) });
            }
            return route.fulfill({ json: current });
          }
          if (path.startsWith('/api/v1/settings/providers/commands/')) return route.fulfill({ json: receipts.get(path.split('/').at(-1)) });
          if (path === '/api/v1/settings/models') {
            if (request.method() === 'PUT') {
              const body = request.postDataJSON(); writes.push(body);
              entries.push(...body.models.map(item => ({ entry_id: item.entry_id, revision: item.expected_revision + 1, connection_id: body.connection_id, connection_revision: body.connection_revision, model: item.model, output_tokens: item.output_tokens })));
              entries.sort((a, b) => a.entry_id.localeCompare(b.entry_id)); registryRevision++;
              receipts.set(body.command_id, { ...registry(), command_id: body.command_id });
              return route.fulfill({ json: receipts.get(body.command_id) });
            }
            return route.fulfill({ json: registry() });
          }
          if (path.startsWith('/api/v1/settings/models/commands/')) return route.fulfill({ json: receipts.get(path.split('/').at(-1)) });
          if (path.startsWith('/api/v1/settings/models/pages/')) return route.fulfill({ json: registry(path.split('/').at(-1)) });
          if (path.endsWith('/provider-catalog/search') || path.endsWith('/provider-catalog/refresh')) {
            const body = request.postDataJSON(), query = body.query ?? '', offset = body.offset ?? 0;
            const found = catalogEntries.filter(entry => entry.model.toLowerCase().includes(query.toLowerCase()));
            const page = found.slice(offset, offset + 16).map(entry => ({ model: entry.model, name: entry.model === selected.model ? 'Current model' : entry.model.slice(0, 128), max_output_tokens: 4096, supports_max_tokens: true, reason: null }));
            return route.fulfill({ json: { schema_version: 1, connection_id: id, connection_revision: 1, provider: 'openrouter', catalog_command_id: body.command_id ?? body.catalog_command_id ?? catalogId, state: 'READY', reason: null, query, offset, next_offset: offset + page.length < found.length ? offset + 16 : null, total: found.length, entries: page } });
          }
          if (path.startsWith('/api/') || path.startsWith('/health/')) { unexpected.push(`${request.method()} ${path}`); return route.abort(); }
          return route.continue();
        });
        const page = await context.newPage(); page.setDefaultTimeout(5000); page.on('pageerror', error => errors.push(error.message));
        async function capture(name) {
          for (const width of [1440, 1280, 390, 320]) {
            await page.setViewportSize({ width, height: 1000 }); await page.evaluate(() => scrollTo(0, 0)); await paint(page);
            assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${name}: overflow at ${width}px`);
            assert.ok(await page.locator('[aria-label="Provider models"] button').evaluateAll(buttons => buttons.every(button => button.getBoundingClientRect().height <= 48)), 'Catalog action labels must remain on one line');
            assert.ok(await page.getByRole('link', { name: 'Skip to content', exact: true }).evaluate(link => link.getBoundingClientRect().bottom <= 0), 'Unfocused skip link must be outside the viewport');
            if (process.env.OMNIS_E2E_OUTPUT) await page.screenshot({ path: join(process.env.OMNIS_E2E_OUTPUT, `SOURCE-${name}-${width}-loaded.png`), fullPage: true });
          }
          await page.setViewportSize({ width: 1440, height: 1000 });
        }
        await page.goto(`${origin}/settings/providers`);
        const list = page.getByRole('region', { name: 'Configured models' }); await check(list.getByRole('button', { name: /^Test / })).toHaveCount(entries.length);
        await check(page.getByRole('button', { name: 'Add models', exact: true })).toBeEnabled();
        await paint(page);
        const geometry = await page.evaluate(() => {
          const selectors = ['h1', 'nav[aria-label="Settings navigation"]', '[aria-label="Configured models"]', '[aria-labelledby="assignments-heading"]'];
          return selectors.map(selector => { const box = document.querySelector(selector).getBoundingClientRect(); return { selector, x: box.x, width: box.width }; });
        });
        assert.ok(geometry.every(box => Math.abs(box.x - 270) < 1 && Math.abs(box.width - 900) < 1), 'All Settings surfaces share the centered 900px axis');
        console.log(JSON.stringify({ scenario, boundary: 'SOURCE built App/synthetic HTTP', geometry, loaded: entries.length }));
        console.log(JSON.stringify({ scenario, assignmentLabels: await page.locator('[aria-labelledby="assignments-heading"] label').evaluateAll(labels => labels.map(label => label.textContent)) }));
        if (scenario === 'long64') {
          for (const width of [390, 320]) {
            await page.setViewportSize({ width, height: 844 }); await paint(page);
            assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Overflow at ${width}px`);
          }
          if (process.env.OMNIS_E2E_OUTPUT) await page.screenshot({ path: join(process.env.OMNIS_E2E_OUTPUT, 'SOURCE-settings-64-320-loaded.png') });
        } else {
          await check(page.getByLabel('Brain', { exact: true }).locator('option:checked')).toHaveText(/^Exact\/Current · OpenRouter$/);
          const save = page.getByRole('button', { name: 'Save assignments', exact: true }), elsewhere = page.getByRole('link', { name: 'Models', exact: true });
          await page.getByLabel('Default model', { exact: true }).selectOption(other); await save.focus(); await page.keyboard.press('Enter');
          await check.poll(() => writes.length).toBe(1); await paint(page); await check(save).toBeFocused(); await check(save).toHaveAttribute('aria-disabled', 'true'); assert.equal(await save.evaluate(button => button.disabled), false, 'Transient busy must not natively disable the focused button');
          if (scenario === 'moved') await elsewhere.focus(); else { await page.keyboard.press('Enter'); await save.evaluate(button => button.form.requestSubmit()); }
          assert.equal(writes.length, 1); put.resolve();
          if (scenario === 'stale') { await check(page.getByText(/Settings changed/)).toBeVisible(); await check(save).toBeDisabled(); assert.equal(await save.evaluate(button => button.disabled), true); await capture('settings-failure'); }
          else { await check(page.getByText(/Assignments saved/)).toBeVisible(); await check(scenario === 'moved' ? elsewhere : save).toBeFocused(); assert.equal(writes[0].brain.output_tokens, 37); }
          if (scenario === 'retained') {
            await capture('settings-models-assignments');
            await page.getByRole('button', { name: 'Add models', exact: true }).click(); await check(page.getByRole('region', { name: 'Add models wizard' })).toBeVisible();
            await capture('settings-connection');
            await page.getByRole('button', { name: 'Continue', exact: true }).click();
            await check(page.getByRole('button', { name: 'Add New/Model', exact: true })).toBeVisible();
            await capture('settings-model-results');
            await page.getByRole('button', { name: 'Add New/Model', exact: true }).click();
            await page.getByRole('button', { name: 'Continue', exact: true }).click();
            await check(page.getByRole('button', { name: 'Save models', exact: true })).toBeVisible();
            const modelToTest = page.getByRole('region', { name: 'Add models wizard' }).getByRole('combobox', { name: 'Model to test', exact: true });
            await check(modelToTest).toHaveCount(0);
            await check(page.getByRole('region', { name: 'Add models wizard' }).getByText('New/Model', { exact: true, selector: 'small' })).toBeVisible();
            await check(page.getByRole('checkbox', { name: 'I approve using this model.', exact: true })).not.toBeChecked();
            assert.equal(writes.length, 1);
            await capture('settings-review');
            await page.getByRole('button', { name: 'Save models', exact: true }).click();
            await check(page.getByText('Models saved.', { exact: true })).toBeVisible();
            await check(page.getByRole('region', { name: 'Add models wizard' })).toHaveCount(0);
            await capture('settings-saved');
            await page.evaluate(() => { document.documentElement.style.zoom = '2'; }); await paint(page);
            assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Overflow at CSS zoom 200%');
            if (process.env.OMNIS_E2E_OUTPUT) await page.screenshot({ path: join(process.env.OMNIS_E2E_OUTPUT, 'SOURCE-settings-zoom-200.png'), fullPage: true });
            await page.evaluate(() => { document.documentElement.style.zoom = ''; });
            await save.focus(); await page.keyboard.press('Tab'); await page.keyboard.press('Shift+Tab'); await check(save).toBeFocused();
            const style = await save.evaluate(button => { const value = getComputedStyle(button); return { outline: value.outlineStyle, outlineWidth: value.outlineWidth, transition: value.transitionDuration, animation: value.animationName }; });
            assert.notEqual(style.outline, 'none'); assert.equal(style.outlineWidth, '2px'); assert.equal(style.transition, '0s'); assert.equal(style.animation, 'none');
            const colors = await page.evaluate(() => {
              const button = getComputedStyle(document.querySelector('[aria-labelledby="assignments-heading"] button[type=submit]'));
              const input = getComputedStyle(document.querySelector('[aria-labelledby="assignments-heading"] input'));
              const secondary = getComputedStyle(document.querySelector('[aria-label="Configured models"] button'));
              const panel = getComputedStyle(document.querySelector('[aria-label="Configured models"]').firstElementChild);
              return { text: button.color, button: button.backgroundColor, secondary: secondary.color, panel: panel.backgroundColor, border: input.borderColor, input: input.backgroundColor, focus: button.outlineColor };
            });
            function luminance(color) {
              const values = color.match(/[\d.]+/g).slice(0, 3).map(Number).map(value => { const channel = value / 255; return channel <= .04045 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4; });
              return values[0] * .2126 + values[1] * .7152 + values[2] * .0722;
            }
            const contrast = (a, b) => (Math.max(luminance(a), luminance(b)) + .05) / (Math.min(luminance(a), luminance(b)) + .05);
            const ratios = { primaryText: contrast(colors.text, colors.button), secondaryText: contrast(colors.secondary, colors.panel), inputBorder: contrast(colors.border, colors.input), focus: contrast(colors.focus, colors.panel) };
            assert.ok(ratios.primaryText >= 4.5 && ratios.secondaryText >= 4.5 && ratios.inputBorder >= 3 && ratios.focus >= 3);
            console.log(JSON.stringify({ boundary: 'SOURCE computed CSS', colors, contrast: ratios }));
            await page.emulateMedia({ forcedColors: 'active' }); await page.evaluate(() => scrollTo(0, 0)); await paint(page);
            if (process.env.OMNIS_E2E_OUTPUT) await page.screenshot({ path: join(process.env.OMNIS_E2E_OUTPUT, 'SOURCE-settings-forced-colors-focus.png'), fullPage: true });
          }
        }
        assert.deepEqual(unexpected, []); assert.deepEqual(errors, []);
      } finally { put.resolve(); await context.close(); }
    });
  } finally { await browser?.close(); await new Promise((resolve, reject) => server.httpServer.close(error => error ? reject(error) : resolve())); }
});
