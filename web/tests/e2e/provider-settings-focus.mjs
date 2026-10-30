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
await test('Assignments SOURCE: held receipt in the long mobile form confirms without occlusion', { timeout: 90000 }, async t => {
  const server = await preview({ configFile: false, envDir: false, publicDir: false, root: fileURLToPath(new URL('../..', import.meta.url)), preview: { host: '127.0.0.1', port: 0, strictPort: true, cors: false } });
  const origin = `http://127.0.0.1:${server.httpServer.address().port}`;
  const names = ['fixture/extra-05', 'fixture/extra-14', 'fixture/selected', 'fixture/extra-13', 'fixture/extra-00', 'fixture/extra-07', 'fixture/00', 'fixture/extra-04', 'fixture/extra-11', 'fixture/extra-12', 'fixture/extra-03', 'manual/model', 'fixture/extra-06', 'fixture/extra-10', 'fixture/extra-09', 'fixture/extra-02', 'fixture/01', 'fixture/extra-01', 'fixture/extra-08'];
  const entries = names.map((model, index) => ({ entry_id: `00000000-0000-4000-8000-${String(index).padStart(12, '0')}`, revision: 1, connection_id: id, connection_revision: 1, model, output_tokens: 64 }));
  const choice = { connection_id: id, connection_revision: 1, model: 'fixture/00', output_tokens: 64 };
  const keys = { ...initial, selection: { selection_id: id, revision: 1, default: choice, brain: null, investigator: null, validator: null } };
  const completed = entry => ({ schema_version: 2, operation_id: entry.entry_id, state: 'FINISHED', state_revision: 3, finish_reason: 'COMPLETED', selection_revision: null, metadata_command_id: null, metadata_state: 'NOT_REQUESTED', reason: null, requested_provider: 'openrouter', requested_model: entry.model, requested_output_tokens: 64, observed_model: entry.model, provider_status: '200', result_state: 'COMPLETED', output_state: 'COMPLETE', response_text: 'OMNIS_MODEL_TEST_OK', usage_state: 'KNOWN', input_tokens: 9, output_tokens: 7, reasoning_tokens: null, cost_observed: null, system_message: 'Respond only with OMNIS_MODEL_TEST_OK. Use no tools.', user_message: 'This is a synthetic local settings test. Reply with OMNIS_MODEL_TEST_OK.', calls_limit: 1, wall_seconds: 300, entry_id: entry.entry_id, entry_revision: 1, connection_id: id, connection_revision: 1, current: true });
  let browser;
  try {
    browser = await chromium.launch();
    for (const width of [320, 390, 1280, 1440]) await t.test(String(width), async () => {
      const context = await browser.newContext({ viewport: { width, height: 1000 }, reducedMotion: 'reduce', serviceWorkers: 'block' });
      const gate = Promise.withResolvers(), writes = [], reads = [], errors = [], unexpected = [];
      let current = structuredClone(keys), receipt, held = false;
      try {
        await context.route('**/*', async route => {
          const request = route.request(), url = new URL(request.url()), path = url.pathname, method = request.method();
          if (url.origin !== origin) { unexpected.push(`${method} ${url.origin}`); return route.abort(); }
          if (!path.startsWith('/api/') && !path.startsWith('/health/')) return route.continue();
          reads.push(`${method} ${path}`);
          if (path === '/api/session' && method === 'GET') return route.fulfill({ json: { authenticated: true, csrf_token: 'a'.repeat(64) } });
          if (path === '/api/instance' && method === 'GET') return route.fulfill({ json: { ...instance, generation: 1, admission_open: true } });
          if (path === '/health/ready' && method === 'GET') return route.fulfill({ json: { api_ready: true, dashboard_ready: true, assessment_ready: false, reason: null, dashboard_reason: null } });
          if (path === '/api/v1/settings/providers') {
            if (method === 'PUT') {
              const body = request.postDataJSON(); assert.equal(body.action, 'save_selection'); assert.equal(body.expected_revision, 1); writes.push(body);
              current = { ...current, selection: { selection_id: body.command_id, revision: 2, default: body.default, brain: body.brain, investigator: body.investigator, validator: body.validator } };
              receipt = { ...current, command_id: body.command_id }; return route.fulfill({ json: receipt });
            }
            if (method === 'GET') return route.fulfill({ json: current });
          }
          if (path.startsWith('/api/v1/settings/providers/commands/') && method === 'GET') {
            assert.equal(path.split('/').at(-1), receipt.command_id); held = true; await gate.promise; return route.fulfill({ json: receipt });
          }
          if ((path === '/api/v1/settings/models' || path.startsWith('/api/v1/settings/models/pages/')) && method === 'GET') {
            const after = path === '/api/v1/settings/models' ? null : path.split('/').at(-1), offset = after ? entries.findIndex(entry => entry.entry_id === after) + 1 : 0, page = entries.slice(offset, offset + 16);
            return route.fulfill({ json: { schema_version: 1, command_id: null, registry_revision: 1, total: entries.length, after, next_after: offset + page.length < entries.length ? page.at(-1).entry_id : null, entries: page } });
          }
          if (path.startsWith('/api/v1/model-test/entries/latest/') && method === 'GET') {
            const entry = entries.find(item => path.endsWith(item.entry_id));
            return ['fixture/01', 'fixture/selected'].includes(entry?.model) ? route.fulfill({ json: completed(entry) }) : route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', correlation_id: id } } });
          }
          if (path === '/api/v1/settings/provider-catalog/search' && method === 'POST') {
            const body = request.postDataJSON();
            const found = entries.filter(entry => ['fixture/00', 'fixture/01', 'fixture/selected'].includes(entry.model) && entry.model === body.query).map(entry => ({ model: entry.model, name: entry.model === 'fixture/selected' ? 'Selected exact model' : `Synthetic model ${entry.model.endsWith('00') ? 0 : 1}`, max_output_tokens: 128, supports_max_tokens: true, reason: null }));
            return route.fulfill({ json: { schema_version: 1, connection_id: id, connection_revision: 1, provider: 'openrouter', catalog_command_id: catalogId, state: 'READY', reason: null, query: body.query, offset: 0, next_offset: null, total: found.length, entries: found } });
          }
          unexpected.push(`${method} ${path}`); return route.abort();
        });
        const page = await context.newPage(); page.setDefaultTimeout(5000); page.on('pageerror', error => errors.push(error.message));
        await page.goto(`${origin}/settings/providers`);
        const configured = page.getByRole('region', { name: 'Configured models', exact: true });
        await check(configured.getByRole('listitem')).toHaveCount(19); await check(configured.getByText('Connected', { exact: true })).toHaveCount(2);
        const assignments = page.getByRole('region', { name: 'Model assignments', exact: true });
        for (const role of ['Brain', 'Investigator', 'Validator']) {
          await assignments.getByLabel(role, { exact: true }).selectOption(entries[2].entry_id); await assignments.getByLabel(role, { exact: true }).selectOption('');
        }
        await assignments.getByText('Output controls', { exact: true }).click();
        const cap = assignments.getByLabel('Default output tokens', { exact: true }), save = assignments.getByRole('button', { name: 'Save assignments', exact: true });
        await cap.fill('0'); await check(save).toBeDisabled(); await cap.fill('64');
        await save.focus(); await page.keyboard.press('Enter'); await check.poll(() => held).toBe(true);
        await check(save).toHaveAttribute('aria-busy', 'true'); await check(save).toBeFocused();
        await check(page.getByRole('region', { name: 'Settings recovery', exact: true })).toHaveCount(0);
        await check(page.locator('[aria-label="Settings notification"]')).toHaveCount(0);
        if (process.env.OMNIS_E2E_OUTPUT) await page.screenshot({ path: join(process.env.OMNIS_E2E_OUTPUT, `assignments-${width}-pending.png`), fullPage: false });
        gate.resolve(); await check(save).toHaveAttribute('aria-busy', 'false');
        const notification = page.locator('[aria-label="Settings notification"]'); await check(notification).toHaveCount(1); await paint(page);
        const observe = () => notification.evaluate(node => {
          const rect = node.getBoundingClientRect(), style = getComputedStyle(node);
          const hintClass = document.querySelector('[aria-labelledby="assignments-heading"] h2 + p').className;
          const targets = [...document.querySelectorAll(`button, input, select, summary, a, :focus, [role="alert"], label, .${hintClass}, h1, h2, h3, [class*="_identity_"], [class*="_state_"], [class*="_saved_"], [class*="_connectionHeading_"] small`)].filter(target => !node.contains(target)).map(target => ({ tag: target.tagName, text: target.textContent.slice(0, 100), visible: target.checkVisibility({ checkVisibilityCSS: true }), rect: target.getBoundingClientRect().toJSON() })).filter(target => target.rect.width && target.rect.height);
          return { text: node.textContent, visibility: style.visibility, rect: rect.toJSON(), scrollY, focus: document.activeElement?.textContent, targets };
        });
        const observation = await observe();
        console.log('ASSIGNMENTS_SOURCE ' + JSON.stringify({ width, writes: writes.length, receiptReads: reads.filter(path => path.startsWith('GET /api/v1/settings/providers/commands/')).length, currentRevision: current.selection.revision, readbackGets: reads.filter(path => path === 'GET /api/v1/settings/providers').length, accessibleNotifications: await page.getByRole('complementary', { name: 'Settings notification', exact: true }).count(), observation }));
        if (process.env.OMNIS_E2E_OUTPUT) await page.screenshot({ path: join(process.env.OMNIS_E2E_OUTPUT, `assignments-${width}-confirmed.png`), fullPage: false });
        assert.equal(writes.length, 1); assert.equal(current.selection.revision, 2);
        assert.equal(reads.filter(path => path.startsWith('GET /api/v1/settings/providers/commands/')).length, 1);
        assert.equal(reads.filter(path => path === 'GET /api/v1/settings/providers').length, 2);
        for (const role of ['default', 'brain', 'investigator', 'validator']) assert.deepEqual(current.selection[role], keys.selection[role]);
        await check(save).toBeFocused(); await check(cap).toHaveValue('64');
        await check(configured.getByText('Connected', { exact: true })).toHaveCount(2);
        await check(page.getByRole('complementary', { name: 'Settings notification', exact: true })).toContainText('Assignments saved.');
        await check(notification).toBeInViewport();
        assert.ok(observation.targets.filter(target => target.visible).every(({ rect: box }) => observation.rect.left >= box.right || observation.rect.right <= box.left || observation.rect.top >= box.bottom || observation.rect.bottom <= box.top), 'Confirmation must not cover visible controls or essential text');
        await configured.getByText('Connection options', { exact: true }).click(); await paint(page);
        await check(configured.getByRole('button', { name: 'Replace key', exact: true })).toBeVisible();
        const expanded = await observe();
        if (expanded.visibility !== 'hidden') {
          await check(notification).toBeInViewport();
          assert.ok(expanded.targets.filter(target => target.visible).every(({ rect: box }) => expanded.rect.left >= box.right || expanded.rect.right <= box.left || expanded.rect.top >= box.bottom || expanded.rect.bottom <= box.top), 'Opening the disclosure must restore its visible controls as obstacles');
        } else await check(page.getByRole('complementary', { name: 'Settings notification', exact: true })).toHaveCount(0);
        console.log('ASSIGNMENTS_VISIBLE_OBSTACLES ' + JSON.stringify({ width, visibility: expanded.visibility, rect: expanded.rect, replaceKeyVisible: true, writes: writes.length }));
        if (process.env.OMNIS_E2E_OUTPUT) await page.screenshot({ path: join(process.env.OMNIS_E2E_OUTPUT, `assignments-${width}-expanded.png`), fullPage: false });
        assert.deepEqual(unexpected, []); assert.deepEqual(errors, []);
      } finally { gate.resolve(); await context.unrouteAll({ behavior: 'wait' }); await context.close(); }
    });
  } finally { await browser?.close(); await new Promise((resolve, reject) => server.httpServer.close(error => error ? reject(error) : resolve())); }
});
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
            if (name === 'settings-models-assignments') await page.getByRole('button', { name: 'Dismiss notification', exact: true }).evaluate(button => button.blur());
            await page.setViewportSize({ width, height: 1000 }); await page.evaluate(() => scrollTo(0, 0)); await paint(page);
            assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${name}: overflow at ${width}px`);
            assert.ok(await page.locator('[aria-label="Provider models"] button').evaluateAll(buttons => buttons.every(button => button.getBoundingClientRect().height <= 48)), 'Catalog action labels must remain on one line');
            assert.ok(await page.getByRole('link', { name: 'Skip to content', exact: true }).evaluate(link => link.getBoundingClientRect().bottom <= 0), 'Unfocused skip link must be outside the viewport');
            if (name === 'settings-models-assignments') {
              const notification = page.getByRole('complementary', { name: 'Settings notification', exact: true });
              await check(notification).toBeVisible(); await check(notification).toContainText('Assignments saved.'); await check(notification).toBeInViewport();
              const clearance = await notification.evaluate(node => {
                const rect = node.getBoundingClientRect();
                const hintClass = document.querySelector('[aria-labelledby="assignments-heading"] h2 + p').className;
                const essential = 'h1, h2, h3, [class*="_identity_"], [class*="_state_"], [class*="_saved_"], [class*="_connectionHeading_"] small';
                return {
                  identities: [...document.querySelectorAll(essential)].map(target => ({ text: target.textContent, rect: target.getBoundingClientRect().toJSON() })),
                  clear: [...document.querySelectorAll(`button, input, select, summary, a, :focus, [role="alert"], label, .${hintClass}, ${essential}`)].filter(target => !node.contains(target)).every(target => {
                    const box = target.getBoundingClientRect();
                    return !box.width || !box.height || rect.left >= box.right || rect.right <= box.left || rect.top >= box.bottom || rect.bottom <= box.top;
                  }),
                };
              });
              assert.equal(clearance.identities.length, 9, 'Four headings, two model identities/statuses and provider key status must be counted');
              assert.ok(clearance.clear, `Notification overlaps a control, label, hint, heading, identity or status at ${width}px`);
              console.log(JSON.stringify({ boundary: 'SOURCE actual viewport before notification focus', width, notification: await notification.boundingBox(), text: await notification.innerText(), ...clearance }));
              if (process.env.OMNIS_E2E_OUTPUT) await page.screenshot({ path: join(process.env.OMNIS_E2E_OUTPUT, `SOURCE-${name}-${width}-before-focus-viewport.png`), fullPage: false });
              await notification.getByRole('button', { name: 'Dismiss notification', exact: true }).focus();
            }
            if (process.env.OMNIS_E2E_OUTPUT) {
              await page.screenshot({ path: join(process.env.OMNIS_E2E_OUTPUT, `SOURCE-${name}-${width}-loaded.png`), fullPage: true });
              await page.screenshot({ path: join(process.env.OMNIS_E2E_OUTPUT, `SOURCE-${name}-${width}-viewport.png`), fullPage: false });
            }
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
          if (scenario === 'retained') await capture('settings-assignment-pending');
          if (scenario === 'moved') await elsewhere.focus(); else { await page.keyboard.press('Enter'); await save.evaluate(button => button.form.requestSubmit()); }
          assert.equal(writes.length, 1); put.resolve();
          if (scenario === 'stale') { await check(page.getByText(/Settings changed/)).toBeVisible(); await check(save).toBeDisabled(); assert.equal(await save.evaluate(button => button.disabled), true); await capture('settings-failure'); }
          else { await check(page.getByText(/Assignments saved/)).toBeVisible(); await check(scenario === 'moved' ? elsewhere : save).toBeFocused(); assert.equal(writes[0].brain.output_tokens, 37); }
          if (scenario === 'retained') {
            const notification = page.getByRole('complementary', { name: 'Settings notification', exact: true });
            const dismiss = notification.getByRole('button', { name: 'Dismiss notification', exact: true });
            await dismiss.focus();
            await capture('settings-models-assignments');
            await check(dismiss).toBeFocused();
            const targets = await dismiss.boundingBox(); assert.ok(targets.width >= 44 && targets.height >= 44);
            await save.focus(); await check(save).toBeFocused();
            await dismiss.click(); await check(notification).toHaveCount(0);
            await page.getByRole('button', { name: 'Add models', exact: true }).click(); await check(page.getByRole('region', { name: 'Add models wizard' })).toBeVisible();
            await capture('settings-connection');
            await page.getByRole('button', { name: 'Continue', exact: true }).click();
            await check(page.getByRole('button', { name: 'Add New/Model', exact: true })).toBeVisible();
            await capture('settings-model-results');
            await page.getByRole('button', { name: 'Add New/Model', exact: true }).click();
            const wizard = page.getByRole('region', { name: 'Add models wizard', exact: true });
            await wizard.getByText('Enter a model ID', { exact: true }).click();
            await wizard.getByLabel('Exact model ID', { exact: true }).fill('manual/preview');
            await wizard.getByRole('button', { name: 'Add model ID', exact: true }).click();
            await wizard.getByRole('button', { name: 'Remove selected manual/preview', exact: true }).click();
            await wizard.getByRole('button', { name: 'Back', exact: true }).click();
            const provider = wizard.getByRole('combobox', { name: 'Provider', exact: true });
            await check(provider).toBeVisible(); await check(wizard.getByText('Saved key', { exact: true })).toBeVisible();
            assert.equal(await wizard.getByLabel('Provider', { exact: true }).count(), 0, 'Native label text includes select options; the exact accessible role name does not');
            console.log(JSON.stringify({ scenario, boundary: 'SOURCE actual built App after Back', exactLabelCount: 0, exactRoleCount: await provider.count(), value: await provider.inputValue() }));
            for (const escape of [false, true]) {
              await provider.selectOption('orcarouter');
              const change = wizard.getByRole('region', { name: 'Provider change confirmation', exact: true });
              await check(change).toContainText('New/Model');
              await change.getByRole('button', { name: 'Cancel', exact: true }).focus();
              await page.keyboard.press(escape ? 'Escape' : 'Enter');
              await check(provider).toBeFocused(); await check(provider).toHaveValue('openrouter');
              await check(wizard.getByText('Saved key', { exact: true })).toBeVisible();
            }
            await wizard.getByRole('button', { name: 'Continue', exact: true }).click();
            await check(wizard.getByRole('list', { name: 'Selected models', exact: true })).toContainText('New/Model');
            await page.getByRole('button', { name: 'Continue', exact: true }).click();
            await check(page.getByRole('button', { name: 'Save models', exact: true })).toBeVisible();
            const modelToTest = page.getByRole('region', { name: 'Add models wizard' }).getByRole('combobox', { name: 'Model to test', exact: true });
            await check(modelToTest).toHaveCount(0);
            await check(page.getByRole('region', { name: 'Add models wizard' }).locator('small').getByText('New/Model', { exact: true })).toBeVisible();
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
