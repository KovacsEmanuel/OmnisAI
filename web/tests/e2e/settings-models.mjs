// Real built App -> paired HTTP API -> existing control/PG owner -> owned TLS peer.
// Invoke only from test_model_test_v2.py's settings_ui case, never standalone production.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
export async function runSettingsRemove({ page, check, paired, origin, output, screenshot, secretChecks }) {
  const models = '/api/v1/settings/models';
  const tests = '/api/v1/model-test/entries';
  const providers = '/api/v1/settings/providers';
  const writes = [];
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (request.method() === 'PUT' || (request.method() === 'POST' && path.endsWith('/refresh'))) {
      writes.push({ path, body: path === models ? request.postDataJSON() : null });
    }
  });
  async function read(path) {
    return page.evaluate(async path => {
      const response = await fetch(path);
      return { status: response.status, body: await response.json() };
    }, path);
  }
  async function put(body) {
    return page.evaluate(async ({ models, body }) => {
      const session = await (await fetch('/api/session')).json();
      const response = await fetch(models, { method: 'PUT', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf_token }, body: JSON.stringify(body) });
      return { status: response.status, body: await response.json() };
    }, { models, body });
  }
  await paired();
  await page.goto(`${origin}/settings/providers`);
  const configured = page.getByRole('region', { name: 'Configured models' });
  const row = model => configured.getByRole('listitem', { name: `Model ${model} via OpenRouter`, exact: true });
  const details = model => row(model).getByRole('button', { name: `Details for ${model} via OpenRouter`, exact: true });
  if (process.env.OMNIS_E2E_STAGE === 'after') {
    const previous = JSON.parse(await readFile(join(output, 'browser-result.json'), 'utf8'));
    assert.equal(previous.scenario, 'settings-remove');
    const saved = previous.catalog;
    assert.deepEqual((await read(`${models}/commands/${saved.command.command_id}`)).body, saved.receipt);
    assert.deepEqual((await read(`${tests}/${saved.history.operation_id}`)).body, saved.history);
    assert.equal((await read(`${tests}/latest/${saved.newEntry}`)).status, 404);
    await check(row('fixture/selected')).toContainText('Not tested');
    assert.deepEqual(writes, [], 'Restart readback must not resend any command');
    await secretChecks();
    return { ...saved, apiRestartReadback: true };
  }
  const library = (await read(models)).body;
  assert.equal(library.total, 18);
  assert.equal(library.entries.length, 16);
  assert.equal(library.entries.some(entry => entry.model === 'fixture/selected'), false);
  const second = (await read(`${models}/pages/${library.registry_revision}/${library.next_after}`)).body;
  assert.equal(second.registry_revision, library.registry_revision);
  const entry = second.entries.find(entry => entry.model === 'fixture/selected');
  assert.ok(entry, 'Remove target must be on page two');
  const baseline = (await read(providers)).body;
  const historyBefore = (await read(`${tests}/latest/${entry.entry_id}`)).body;
  assert.equal(historyBefore.result_state, 'COMPLETED');
  await check(row('fixture/selected')).toContainText('Connected');
  await details('fixture/00').focus(); await page.keyboard.press('Enter');
  const usedRemove = row('fixture/00').getByRole('button', { name: 'Remove fixture/00 via OpenRouter', exact: true });
  await check(usedRemove).toBeDisabled();
  const usedHint = row('fixture/00').getByText('Used by Default. Reassign explicitly in Model assignments before removing this model.', { exact: true });
  await check(usedHint).toBeVisible();
  await usedHint.scrollIntoViewIfNeeded();
  assert.ok(await usedHint.evaluate(node => { const box = node.getBoundingClientRect(); return box.top >= 0 && box.bottom <= innerHeight; }));
  assert.equal(await usedRemove.getAttribute('aria-describedby'), await usedHint.getAttribute('id'));
  await screenshot('settings-remove-in-use-viewport', { fullPage: false });
  await page.keyboard.press('Tab');
  await check(row('fixture/00').getByRole('button', { name: 'Test fixture/00 via OpenRouter', exact: true })).toBeFocused();
  await page.keyboard.press('Tab');
  await check(usedRemove).not.toBeFocused();
  assert.match(await page.evaluate(() => document.activeElement?.getAttribute('aria-label') ?? ''), /^Details for /);
  assert.deepEqual(writes, []);
  await details('fixture/selected').focus(); await page.keyboard.press('Enter');
  const remove = row('fixture/selected').getByRole('button', { name: 'Remove fixture/selected via OpenRouter', exact: true });
  for (const width of [1440, 1280, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await remove.scrollIntoViewIfNeeded();
    await details('fixture/selected').focus();
    await page.keyboard.press('Tab');
    await check(row('fixture/selected').getByRole('button', { name: 'Test fixture/selected via OpenRouter', exact: true })).toBeFocused();
    await page.keyboard.press('Tab');
    await check(remove).toBeFocused();
    // Frame the focused target and outline, rather than the viewport's edge.
    await remove.evaluate(button => button.scrollIntoView({ block: 'center' }));
    const geometry = await remove.evaluate(button => {
      const box = button.getBoundingClientRect(), style = getComputedStyle(button);
      const metrics = button.parentElement.querySelector('dl').getBoundingClientRect();
      return { height: box.height, width: box.width, outline: style.outlineStyle, inside: box.top >= 4 && box.bottom <= innerHeight - 4,
        hit: button.contains(document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2)),
        overlaps: box.left < metrics.right && box.right > metrics.left && box.top < metrics.bottom && box.bottom > metrics.top,
        overflow: document.documentElement.scrollWidth > innerWidth };
    });
    assert.ok(geometry.height >= 44 && geometry.width >= 44 && geometry.hit && geometry.inside);
    assert.notEqual(geometry.outline, 'none');
    assert.equal(geometry.overlaps, false); assert.equal(geometry.overflow, false);
    await secretChecks(); await screenshot(`settings-remove-focus-${width}x1000`, { fullPage: false });
    await page.keyboard.press('Enter');
    const confirmation = row('fixture/selected').getByRole('region', { name: 'Remove model confirmation', exact: true });
    await check(confirmation).toContainText('fixture/selected · OpenRouter');
    await page.keyboard.press('Tab');
    await check(confirmation.getByRole('button', { name: 'Cancel', exact: true })).toBeFocused();
    await confirmation.scrollIntoViewIfNeeded();
    await screenshot(`settings-remove-inline-${width}x1000`, { fullPage: false });
    await page.keyboard.press('Enter'); await check(confirmation).toHaveCount(0);
    await check(remove).toBeFocused();
  }
  await page.keyboard.press('Enter');
  const confirmation = row('fixture/selected').getByRole('region', { name: 'Remove model confirmation', exact: true });
  await page.keyboard.press('Tab'); await page.keyboard.press('Escape');
  await check(confirmation).toHaveCount(0);
  await check(remove).toBeFocused();
  assert.deepEqual((await read(models)).body, library);
  assert.deepEqual((await read(providers)).body, baseline);
  assert.deepEqual(writes, []);
  let command, receipt;
  await page.route(`**${models}`, async route => {
    if (route.request().method() !== 'PUT') return route.continue();
    command = route.request().postDataJSON();
    assert.equal(command.action, 'remove_model');
    const response = await route.fetch();
    assert.equal(response.status(), 200); receipt = await response.json();
    await route.abort('failed');
  });
  await page.keyboard.press('Enter');
  await page.keyboard.press('Tab');
  await check(confirmation.getByRole('button', { name: 'Cancel', exact: true })).toBeFocused();
  await page.keyboard.press('Tab');
  await check(confirmation.getByRole('button', { name: 'Remove', exact: true })).toBeFocused();
  await page.keyboard.press('Enter');
  await check(page.getByRole('region', { name: 'Settings recovery' })).toContainText('Save unconfirmed');
  await page.unroute(`**${models}`);
  const recover = page.getByRole('button', { name: 'Read current state', exact: true });
  await recover.focus(); await page.keyboard.press('Enter');
  await check(row('fixture/selected')).toHaveCount(0);
  await check(page.getByRole('button', { name: 'Add models', exact: true })).toBeFocused();
  assert.deepEqual((await read(`${models}/commands/${command.command_id}`)).body, receipt);
  assert.equal(command.entry_id, entry.entry_id);
  assert.equal(command.expected_revision, entry.revision);
  assert.equal(command.expected_registry_revision, library.registry_revision);
  let pageRead = (await read(models)).body, membership = [...pageRead.entries];
  while (pageRead.next_after !== null) {
    pageRead = (await read(`${models}/pages/${receipt.registry_revision}/${pageRead.next_after}`)).body;
    assert.equal(pageRead.registry_revision, receipt.registry_revision);
    membership.push(...pageRead.entries);
  }
  assert.equal(receipt.total, 17); assert.notEqual(receipt.next_after, null);
  assert.equal(membership.length, new Set(membership.map(item => item.entry_id)).size);
  assert.equal(membership.length, receipt.total); assert.equal(membership.some(item => item.entry_id === entry.entry_id), false);
  const history = (await read(`${tests}/${historyBefore.operation_id}`)).body;
  assert.deepEqual(history, { ...historyBefore, current: false });
  assert.deepEqual((await read(`${tests}/latest/${entry.entry_id}`)).body, history);
  assert.deepEqual((await read(providers)).body, baseline);
  await page.reload(); await check(row('fixture/selected')).toHaveCount(0);
  assert.equal(writes.length, 1, 'Lost reply/recovery/reload must not resend Remove/Test/Refresh');
  const newEntry = crypto.randomUUID();
  assert.equal((await put({ action: 'save_models', command_id: crypto.randomUUID(), expected_registry_revision: receipt.registry_revision,
    connection_id: entry.connection_id, connection_revision: entry.connection_revision,
    models: [{ entry_id: newEntry, expected_revision: 0, model: entry.model, output_tokens: entry.output_tokens }] })).status, 200);
  await page.getByRole('button', { name: 'Reload current settings', exact: true }).click();
  await check(row('fixture/selected')).toContainText('Not tested');
  assert.equal((await read(`${tests}/latest/${newEntry}`)).status, 404);
  await secretChecks();
  return { command, receipt, history, newEntry, lostReplyRecovered: true, entries: 18 };
}

export async function runSettingsModels({ page, check, paired, origin, output, screenshot, secretChecks, remember }) {
  if (process.argv[2] === 'settings-cancel-current') {
    assert.equal(process.env.OMNIS_E2E_STAGE, 'before', 'No restart or second Start is admitted');
    const tests = '/api/v1/model-test/entries';
    remember('synthetic-not-provider-key');
    const intents = [];
    page.on('request', request => {
      const path = new URL(request.url()).pathname;
      if (request.method() === 'PUT' || /\/(cancel|refresh)$/.test(path)) intents.push({ path });
    });
    await paired();
    await page.goto(`${origin}/settings/providers`);
    const row = page.getByRole('listitem', { name: 'Model fixture/model via OpenRouter', exact: true });
    await row.getByRole('button', { name: 'Test fixture/model via OpenRouter', exact: true }).click();
    const consent = page.getByRole('region', { name: 'Test consent', exact: true });
    await consent.getByRole('checkbox').check();
    const started = page.waitForResponse(response => response.request().method() === 'PUT' && response.url() === `${origin}${tests}`);
    await consent.getByRole('button', { name: 'Send model test', exact: true }).click();
    const start = await started;
    const startBody = await start.json();
    assert.equal(start.status(), 202);
    const operation = start.request().postDataJSON().operation_id;
    assert.equal(startBody.operation_id, operation);
    let running;
    await check.poll(async () => {
      const read = page.waitForResponse(response => response.request().method() === 'GET' && response.url() === `${origin}${tests}/${operation}`);
      const latest = page.waitForResponse(response => response.request().method() === 'GET' && response.url() === `${origin}${tests}/latest/${startBody.entry_id}`);
      await row.getByRole('button', { name: 'Read test status', exact: true }).click();
      const reply = await read;
      assert.equal(reply.status(), 200);
      running = await reply.json();
      assert.equal(running.operation_id, operation);
      const tail = await latest;
      assert.equal(tail.status(), 200);
      const current = await tail.json();
      assert.equal(current.operation_id, operation);
      await tail.finished();
      // readTest has no busy flag: its latest-entry tail and rendered frame fence the handler.
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      return [running.state, running.state_revision, current.state, current.state_revision];
    }).toEqual(['RUNNING', 2, 'RUNNING', 2]);
    await check(row.getByRole('button', { name: 'Cancel test', exact: true })).toBeVisible();
    const cancelled = page.waitForResponse(response => response.url() === `${origin}${tests}/${operation}/cancel`);
    await row.getByRole('button', { name: 'Cancel test', exact: true }).click();
    const reply = await cancelled;
    const body = await reply.json();
    assert.equal(reply.request().postDataJSON().expected_state_revision, running.state_revision);
    assert.equal(reply.status(), 202);
    assert.equal(body.operation_id, operation);
    assert.equal(body.state, 'FINISHED');
    assert.equal(body.finish_reason, 'CANCELLED');
    assert.equal(body.state_revision, 4);
    const readback = await page.evaluate(async path => {
      const response = await fetch(path);
      if (!response.ok) throw new Error('Same-operation readback refused');
      const view = await response.json();
      return { operation_id: view.operation_id, state: view.state, state_revision: view.state_revision, finish_reason: view.finish_reason };
    }, `${tests}/${operation}`);
    assert.deepEqual(readback, { operation_id: operation, state: 'FINISHED', state_revision: 4, finish_reason: 'CANCELLED' });
    assert.equal(intents.filter(item => item.path === tests).length, 1);
    assert.equal(intents.filter(item => item.path === `${tests}/${operation}/cancel`).length, 1);
    assert.ok(intents.every(item => [tests, `${tests}/${operation}/cancel`].includes(item.path)), 'No assignments, model writes or Refresh');
    await secretChecks();
    return { classification: 'CURRENT_REVISION_CANCEL', functionalPass: true,
      running: { operation_id: running.operation_id, state: running.state, state_revision: running.state_revision },
      cancel: { status: reply.status(), requested_revision: reply.request().postDataJSON().expected_state_revision }, readback };
  }
  if (process.argv[2] === 'settings-cancel-probe') {
    assert.equal(process.env.OMNIS_E2E_STAGE, 'before', 'No restart or second Start is admitted');
    const tests = '/api/v1/model-test/entries';
    remember('synthetic-not-provider-key');
    const intents = [];
    page.on('request', request => {
      const path = new URL(request.url()).pathname;
      if (request.method() === 'PUT' || /\/(cancel|refresh)$/.test(path)) intents.push({ path });
    });
    await paired();
    await page.goto(`${origin}/settings/providers`);
    const row = page.getByRole('listitem', { name: 'Model fixture/model via OpenRouter', exact: true });
    await row.getByRole('button', { name: 'Test fixture/model via OpenRouter', exact: true }).click();
    const consent = page.getByRole('region', { name: 'Test consent', exact: true });
    await consent.getByRole('checkbox').check();
    const started = page.waitForResponse(response => response.request().method() === 'PUT' && response.url() === `${origin}${tests}`);
    await consent.getByRole('button', { name: 'Send model test', exact: true }).click();
    const start = await started;
    const startBody = await start.json();
    assert.equal(start.status(), 202);
    const operation = start.request().postDataJSON().operation_id;
    assert.equal(startBody.operation_id, operation);
    const cancelled = page.waitForResponse(response => response.url() === `${origin}${tests}/${operation}/cancel`);
    // Deliberately use the first visible Cancel; no revision-refresh or retry.
    await row.getByRole('button', { name: 'Cancel test', exact: true }).click();
    const reply = await cancelled;
    const body = await reply.json();
    const diagnostic = { status: reply.status(), error_code: body.error?.code ?? null,
      operation_id: operation, requested_revision: reply.request().postDataJSON().expected_state_revision,
      response_operation_id: body.operation_id ?? null, response_state: body.state ?? null, response_revision: body.state_revision ?? null };
    console.log('CANCEL_HTTP_DIAGNOSTIC ' + JSON.stringify(diagnostic));
    assert.ok([202, 409].includes(reply.status()), JSON.stringify(diagnostic));
    let readback;
    await check.poll(async () => {
      readback = await page.evaluate(async path => {
        const response = await fetch(path);
        if (!response.ok) throw new Error('Same-operation readback refused');
        const view = await response.json();
        return { operation_id: view.operation_id, state: view.state, state_revision: view.state_revision, finish_reason: view.finish_reason };
      }, `${tests}/${operation}`);
      assert.equal(readback.operation_id, operation);
      return readback.state;
    }).toBe('FINISHED');
    if (reply.status() === 202) {
      assert.equal(body.operation_id, operation);
      assert.equal(body.finish_reason, 'CANCELLED');
      assert.equal(readback.finish_reason, 'CANCELLED');
    }
    assert.equal(intents.filter(item => item.path === tests).length, 1);
    assert.equal(intents.filter(item => item.path === `${tests}/${operation}/cancel`).length, 1);
    assert.ok(intents.every(item => [tests, `${tests}/${operation}/cancel`].includes(item.path)), 'No assignments, model writes or Refresh');
    await secretChecks();
    return { classification: 'DIAGNOSTIC_ONLY', functionalPass: false, cancel: diagnostic, readback };
  }
  const providers = '/api/v1/settings/providers';
  const catalog = '/api/v1/settings/provider-catalog';
  const configured = page.getByRole('region', { name: 'Configured models' });
  const wizard = page.getByRole('region', { name: 'Add models wizard' });
  const assignments = page.getByRole('region', { name: 'Model assignments' });
  const test = configured.getByRole('listitem', { name: 'Model fixture/03 via OpenRouter', exact: true });
  const modelDetails = test.getByRole('button', { name: 'Details for fixture/03 via OpenRouter', exact: true });
  const recovery = page.getByRole('region', { name: 'Settings recovery', exact: true });
  // Passive feedback yields to controls; persistent recovery is checked in context.
  const notification = page.getByRole('complementary', { name: 'Settings notification', exact: true, includeHidden: true }).getByRole('status', { includeHidden: true });
  const writes = [];
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (request.method() === 'PUT' && [providers, '/api/v1/settings/models', '/api/v1/model-test/entries'].includes(path)) {
      // Never retain a key-bearing request body in evidence.
      writes.push({ path, action: path === providers ? request.postDataJSON().action : null });
    }
  });
  async function readSettings() {
    return page.evaluate(async path => {
      const response = await fetch(path);
      if (!response.ok) throw new Error('Settings readback refused');
      return response.json();
    }, providers);
  }
  async function catalogReady() {
    await check(wizard).toContainText('32 matching models');
    const recovery = page.getByRole('region', { name: 'Catalog recovery' });
    if (await recovery.count()) {
      await recovery.getByRole('button', { name: 'Read catalog status', exact: true }).click();
      await check(recovery).toHaveCount(0);
    }
  }
  async function secondWriter(command, path = providers) {
    return page.evaluate(async ({ path, command }) => {
      const session = await (await fetch('/api/session')).json();
      const response = await fetch(path, { method: 'PUT', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf_token }, body: JSON.stringify(command) });
      return { status: response.status, body: await response.json() };
    }, { path, command });
  }
  async function capture(state, ready, disclosure) {
    for (const width of [1440, 1280, 390, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      await check(ready).toBeVisible();
      await check(page.getByText('Loading current settings…', { exact: true })).toHaveCount(0);
      await check(page.getByText('Loading models…', { exact: true })).toHaveCount(0);
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${state}: overflow at ${width}px`);
      await secretChecks();
      if (disclosure) assert.equal(await disclosure.evaluate(summary => summary.parentElement.open), false, `${state}: details start closed`);
      await screenshot(`settings-models-${state}-${width}x1000`);
      if (disclosure && [1440, 390].includes(width)) {
        await disclosure.focus(); await page.keyboard.press('Enter');
        await check(disclosure).toBeFocused();
        assert.equal(await disclosure.evaluate(summary => summary.parentElement.open), true);
        const focus = await disclosure.evaluate(summary => { const style = getComputedStyle(summary); return { outline: style.outlineStyle, width: style.outlineWidth }; });
        assert.notEqual(focus.outline, 'none'); assert.equal(focus.width, '2px');
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${state}: expanded overflow at ${width}px`);
        await secretChecks();
        await screenshot(`settings-models-${state}-details-expanded-${width}x1000`);
        await page.keyboard.press('Enter'); await check(disclosure).toBeFocused();
        assert.equal(await disclosure.evaluate(summary => summary.parentElement.open), false);
      }
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
  }
  async function loadedMany() {
    await check(configured.getByRole('button', { name: /^Test fixture\// })).toHaveCount(32);
    await check(page.getByLabel('Brain', { exact: true }).locator('option:checked')).toHaveText(/^fixture\/01 · OpenRouter(?: · Connection unavailable)?$/);
    await assignments.getByText('Output controls', { exact: true }).click();
    await check(page.getByLabel('Brain output tokens', { exact: true })).toHaveValue('37');
    await assignments.getByText('Output controls', { exact: true }).click();
    const current = await readSettings();
    assert.equal(current.selection.revision, 3);
    assert.equal(current.selection.default.model, 'fixture/00');
    assert.equal(current.selection.default.output_tokens, 64);
    assert.equal(current.selection.brain.model, 'fixture/01');
    assert.equal(current.selection.brain.output_tokens, 37);
    assert.equal(current.selection.investigator, null);
    assert.equal(current.selection.validator, null);
    return current;
  }
  await paired();
  await page.goto(`${origin}/settings/providers`);
  if (process.env.OMNIS_E2E_STAGE === 'after') {
    const previous = JSON.parse(await readFile(join(output, 'browser-result.json'), 'utf8'));
    assert.equal(previous.passed, true);
    assert.equal(previous.scenario, 'settings-models');
    const operations = previous.catalog.exactTestOperations;
    assert.equal(operations.length, 2);
    for (const saved of operations) {
      assert.match(saved.operation_id, /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/);
      const { history, latest } = await page.evaluate(async saved => {
        const history = await fetch(`/api/v1/model-test/entries/${saved.operation_id}`);
        const latest = await fetch(`/api/v1/model-test/entries/latest/${saved.entry_id}`);
        if (!history.ok || !latest.ok) throw new Error('Exact test history readback refused');
        return { history: await history.json(), latest: await latest.json() };
      }, saved);
      assert.equal(history.operation_id, saved.operation_id);
      assert.equal(history.result_state, 'COMPLETED');
      assert.equal(history.requested_model, saved.model);
      assert.deepEqual(latest, history);
      assert.equal(latest.current, false);
    }
    const current = await loadedMany();
    assert.equal(current.connections.length, 1);
    assert.equal(current.connections[0].enabled, false);
    assert.equal(current.connections[0].revision, 2);
    await check(configured.getByText('Connection disabled', { exact: true })).toBeVisible();
    await check(page.getByRole('button', { name: 'Save assignments', exact: true })).toBeDisabled();
    assert.deepEqual(writes, [], 'API restart/readback must not write or resend');
    await capture('api-restart-disabled', configured.getByText('Connection disabled', { exact: true }));
    return { entries: 32, apiRestartReadback: true, exactTestOperations: operations, historyReadback: true, disabled: true, selectionRevision: 3 };
  }
  await check(configured).toContainText('No models configured.');
  assert.deepEqual((await readSettings()).connections, []);
  assert.equal((await readSettings()).selection, null);
  await page.getByRole('button', { name: 'Add models', exact: true }).click();
  await check(wizard.getByLabel('API key', { exact: true })).toBeEmpty();
  await capture('first-setup', wizard.getByLabel('API key', { exact: true }));
  assert.deepEqual(writes, []);
  const key = 'synthetic-not-provider-key';
  remember(key);
  await wizard.getByLabel('API key', { exact: true }).fill(key);
  // No capture or DOM dump until Continue has wiped the write-only field.
  const saved = page.waitForResponse(response => response.url() === `${origin}${providers}` && response.request().method() === 'PUT');
  const refresh = page.waitForRequest(request => request.url() === `${origin}${catalog}/refresh`);
  await wizard.getByRole('button', { name: 'Continue', exact: true }).focus();
  const continueScroll = await page.evaluate(() => scrollY);
  await wizard.getByRole('button', { name: 'Continue', exact: true }).click();
  const receipt = await (await saved).json();
  const requested = (await refresh).postDataJSON();
  const connection = receipt.connections[0];
  assert.equal(receipt.command_id, (await saved).request().postDataJSON().command_id);
  assert.equal(connection.enabled, true);
  assert.equal(connection.credential_present, true);
  assert.equal(requested.connection_id, connection.connection_id);
  assert.equal(requested.connection_revision, connection.revision);
  await check(wizard.getByLabel('Search models', { exact: true })).toBeVisible();
  await check(wizard.getByRole('heading', { name: 'Add models', exact: true })).toBeFocused();
  assert.equal(await page.evaluate(() => scrollY), continueScroll, 'Continue must not force a scroll jump');
  await catalogReady();
  await check(wizard.getByLabel('API key', { exact: true })).toHaveCount(0);
  await capture('loaded-results', wizard.getByRole('button', { name: 'Add fixture/00', exact: true }));
  await wizard.getByRole('button', { name: 'Add fixture/00', exact: true }).click();
  await wizard.getByRole('button', { name: 'Continue', exact: true }).click();
  await wizard.getByText('Output controls', { exact: true }).click();
  await wizard.getByLabel('fixture/00 output tokens', { exact: true }).fill('64');
  await check(wizard.getByRole('button', { name: 'Save & connect', exact: true })).toBeDisabled();
  await wizard.getByRole('button', { name: 'Save models', exact: true }).click();
  await check(configured.getByRole('button', { name: /^Test fixture\// })).toHaveCount(1);
  await check(assignments.getByText(/Save assignments to confirm a default/)).toHaveCount(0);
  await check(assignments).toContainText('All roles will use fixture/00 · OpenRouter after saving assignments.');
  await check(assignments.getByRole('combobox')).toHaveCount(0);
  assert.equal((await readSettings()).selection, null, 'Registering one model is not a persisted Default');
  await capture('one-model-unassigned', assignments.getByRole('button', { name: 'Save assignments', exact: true }));
  await configured.getByRole('button', { name: 'Test fixture/00 via OpenRouter', exact: true }).click();
  const consent = page.getByRole('region', { name: 'Test consent' });
  await check(consent).toContainText('OpenRouter · fixture/00');
  await check(consent).toContainText('Provider charges may apply.');
  await check(consent.getByRole('checkbox')).not.toBeChecked();
  await check(consent.getByRole('button', { name: 'Send model test', exact: true })).toBeDisabled();
  await capture('direct-test-consent', consent, consent.getByText('Fixed input', { exact: true }));
  await consent.getByRole('checkbox').check();
  await check(consent.getByRole('button', { name: 'Send model test', exact: true })).toBeEnabled();
  await consent.getByRole('button', { name: 'Cancel', exact: true }).click();
  assert.equal(writes.filter(item => item.path === '/api/v1/model-test/entries').length, 0);
  await assignments.getByRole('button', { name: 'Save assignments', exact: true }).click();
  await check(assignments).toContainText('All roles use fixture/00 · OpenRouter.');
  const firstSelection = (await readSettings()).selection;
  assert.equal(firstSelection.revision, 1);
  assert.equal(firstSelection.default.model, 'fixture/00');
  assert.equal(firstSelection.default.output_tokens, 64);
  for (const role of ['brain', 'investigator', 'validator']) assert.equal(firstSelection[role], null);

  // A legitimate competing paired HTTP writer advances CAS, not a fabricated 409.
  const override = { ...firstSelection.default, output_tokens: 37 };
  const advanced = await secondWriter({ action: 'save_selection', command_id: crypto.randomUUID(), expected_revision: firstSelection.revision, default: firstSelection.default, brain: override, investigator: null, validator: null });
  assert.equal(advanced.status, 200);
  const preserved = advanced.body.selection;
  assert.equal(preserved.revision, 2);
  const conflict = page.waitForResponse(response => response.url() === `${origin}${providers}` && response.request().method() === 'PUT');
  await assignments.getByRole('button', { name: 'Save assignments', exact: true }).click();
  const denied = await conflict;
  assert.equal(denied.request().postDataJSON().expected_revision, 1);
  assert.equal(denied.status(), 409);
  assert.equal((await denied.json()).error.code, 'REVISION_CONFLICT');
  await check(recovery).toContainText('Settings changed. Reload the current revision before saving.');
  await check(recovery).toBeVisible();
  await check(notification).toHaveText('Settings need attention.');
  assert.deepEqual((await readSettings()).selection, preserved);
  await page.getByRole('button', { name: 'Reload current settings', exact: true }).click();
  await check(notification).toContainText('Settings reloaded.');
  await check(recovery).toHaveCount(0);
  await check(assignments.getByRole('combobox')).toHaveCount(0);
  await assignments.getByText('Output controls', { exact: true }).click();
  await check(page.getByLabel('Brain output tokens', { exact: true })).toHaveValue('37');
  await check(assignments).toContainText('All roles use fixture/00 · OpenRouter.');

  await page.getByRole('button', { name: 'Add models', exact: true }).click();
  await check(wizard.getByText('Saved key', { exact: true })).toBeVisible();
  await check(wizard.getByLabel('API key', { exact: true })).toHaveCount(0);
  assert.equal(writes.filter(item => item.action === 'save_connection').length, 1);
  await wizard.getByRole('button', { name: 'Continue', exact: true }).click();
  await catalogReady();
  await check(wizard.getByRole('button', { name: 'Added fixture/00', exact: true })).toBeDisabled();
  const search = wizard.getByLabel('Search models', { exact: true });
  await search.focus();
  const searchScroll = await page.evaluate(() => scrollY);
  await search.fill('fixture/01');
  await check(wizard).toContainText('1 matching models');
  await check(search).toBeFocused();
  assert.equal(await page.evaluate(() => scrollY), searchScroll, 'Cached search must preserve viewport and focus');
  await wizard.getByRole('button', { name: 'Add fixture/01', exact: true }).click();
  await search.fill('');
  await check(wizard).toContainText('32 matching models');
  await check(wizard.getByRole('button', { name: 'Selected fixture/01', exact: true })).toBeDisabled();
  for (let pageNumber = 0; pageNumber < 2; pageNumber++) {
    for (let index = pageNumber * 16; index < (pageNumber + 1) * 16; index++) {
      if ([0, 1, 2, 3].includes(index)) continue;
      await wizard.getByRole('button', { name: `Add fixture/${String(index).padStart(2, '0')}`, exact: true }).click();
    }
    if (!pageNumber) await wizard.getByRole('button', { name: 'Next results', exact: true }).click();
  }
  const chips = wizard.getByRole('list', { name: 'Selected models' }).locator('button');
  await check(chips).toHaveCount(29);
  const selectedIds = await chips.evaluateAll(elements => elements.map(element => element.getAttribute('aria-label')).sort());
  assert.deepEqual(selectedIds, Array.from({ length: 31 }, (_, index) => index + 1).filter(index => ![2, 3].includes(index)).map(index => `Remove selected fixture/${String(index).padStart(2, '0')}`));
  await check(wizard.getByRole('button', { name: 'Next results', exact: true })).toBeDisabled();
  await wizard.getByRole('button', { name: 'Continue', exact: true }).click();
  await wizard.getByRole('button', { name: 'Back', exact: true }).click();
  assert.deepEqual(await chips.evaluateAll(elements => elements.map(element => element.getAttribute('aria-label')).sort()), selectedIds);
  await wizard.getByRole('button', { name: 'Continue', exact: true }).click();
  await check(wizard).toContainText('Default and role overrides stay unchanged.');
  await capture('review-many', wizard.getByRole('button', { name: 'Save models', exact: true }), wizard.getByText('Output controls', { exact: true }));
  assert.deepEqual((await readSettings()).selection, preserved);
  assert.equal(writes.filter(item => item.path === '/api/v1/model-test/entries').length, 0);
  await wizard.getByRole('button', { name: 'Save models', exact: true }).click();
  await check(configured.getByRole('button', { name: /^Test fixture\// })).toHaveCount(30);
  await page.getByRole('button', { name: 'Add models', exact: true }).click();
  await wizard.getByRole('button', { name: 'Continue', exact: true }).click();
  await catalogReady();
  for (const model of ['fixture/02', 'fixture/03']) await wizard.getByRole('button', { name: `Add ${model}`, exact: true }).click();
  await wizard.getByRole('button', { name: 'Continue', exact: true }).click();
  await check(wizard.getByRole('combobox')).toHaveCount(0);
  await wizard.getByText('Output controls', { exact: true }).click();
  for (const model of ['fixture/02', 'fixture/03']) await wizard.getByLabel(`${model} output tokens`, { exact: true }).fill('64');
  await wizard.getByText('Output controls', { exact: true }).click();
  await capture('review-two', wizard.getByRole('button', { name: 'Save & connect', exact: true }));
  const consentGeneration = await page.evaluate(async () => { const response = await fetch('/api/instance'); if (!response.ok) throw new Error('Instance status unavailable'); const status = await response.json(); if (!status.admission_open || !status.supervisor_ready) throw new Error('Instance admission closed'); return status.generation; });
  assert.ok(Number.isSafeInteger(consentGeneration));
  await wizard.getByRole('checkbox', { name: /up to 2 calls, one per listed model via OpenRouter/ }).check();
  const testIntents = [];
  const collectTest = request => { if (request.method() === 'PUT' && request.url() === `${origin}/api/v1/model-test/entries`) testIntents.push(request.postDataJSON()); };
  page.on('request', collectTest);
  await wizard.getByRole('button', { name: 'Save & connect', exact: true }).click();
  await check(configured.getByText('Connected', { exact: true })).toHaveCount(2);
  page.off('request', collectTest);
  assert.equal(testIntents.length, 2);
  assert.deepEqual(testIntents.map(intent => intent.expected_generation), [consentGeneration, consentGeneration]);
  assert.notEqual(testIntents[0].operation_id, testIntents[1].operation_id);
  assert.notEqual(testIntents[0].entry_id, testIntents[1].entry_id);
  const testIntent = testIntents[0];
  const operations = testIntents.map((intent, index) => ({ operation_id: intent.operation_id, entry_id: intent.entry_id, model: ['fixture/02', 'fixture/03'][index] }));
  const results = [];
  for (const [index, saved] of operations.entries()) {
    assert.match(saved.operation_id, /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/);
    const result = await page.evaluate(async saved => {
      const history = await fetch(`/api/v1/model-test/entries/${saved.operation_id}`);
      const latest = await fetch(`/api/v1/model-test/entries/latest/${saved.entry_id}`);
      if (!history.ok || !latest.ok) throw new Error('Exact test readback refused');
      return { history: await history.json(), latest: await latest.json() };
    }, saved);
    assert.deepEqual(result.latest, result.history);
    assert.equal(result.history.operation_id, saved.operation_id);
    assert.equal(result.history.entry_id, saved.entry_id);
    assert.equal(result.history.entry_revision, testIntents[index].expected_entry_revision);
    assert.equal(result.history.connection_id, connection.connection_id);
    assert.equal(result.history.connection_revision, testIntents[index].expected_connection_revision);
    assert.equal(result.history.requested_model, saved.model);
    assert.equal(result.history.requested_provider, 'openrouter');
    assert.equal(result.history.observed_model, saved.model);
    assert.equal(result.history.state, 'FINISHED');
    assert.equal(result.history.result_state, 'COMPLETED');
    assert.equal(result.history.finish_reason, 'COMPLETED');
    assert.equal(result.history.current, true);
    assert.equal(result.history.response_text, 'OMNIS_MODEL_TEST_OK');
    results.push(result.history);
  }
  await check(page.getByRole('region', { name: 'Model test operation', exact: true })).toHaveCount(0);
  await check(modelDetails).toHaveAttribute('aria-expanded', 'false');
  await modelDetails.focus(); await page.keyboard.press('Enter');
  await check(modelDetails).toBeFocused(); await check(modelDetails).toHaveAttribute('aria-expanded', 'true');
  await check(test.getByText('Connected', { exact: true })).toBeVisible();
  const usage = test.getByLabel('Test usage', { exact: true });
  await check(usage.locator('dt')).toHaveText(['Input tokens', 'Output tokens', 'Cost']);
  await check(usage.locator('dd')).toHaveText([results[1].input_tokens, results[1].output_tokens, results[1].cost_observed].map(value => value === null ? 'Unknown' : String(value)));
  await check(test.getByText('Operation details', { exact: true })).toHaveCount(0);
  await check(test.getByLabel('Model response', { exact: true })).toHaveCount(0);
  await check(test.getByText('Test completed.', { exact: true })).toHaveCount(0);
  await check(test.getByRole('button', { name: 'Read test status', exact: true })).toHaveCount(0);
  assert.ok(!(await test.textContent()).includes(testIntents[1].operation_id));
  await check(configured.getByRole('button', { name: /^Test fixture\// })).toHaveCount(32);
  assert.deepEqual((await configured.getByRole('button', { name: /^Test fixture\// }).evaluateAll(elements => elements.map(element => element.getAttribute('aria-label')))).sort(), Array.from({ length: 32 }, (_, index) => `Test fixture/${String(index).padStart(2, '0')} via OpenRouter`));
  assert.deepEqual((await readSettings()).selection, preserved, 'Save & connect must preserve Default, explicit override, caps and revision');
  const operation = testIntents[1].operation_id;
  await check(test.getByRole('button', { name: 'Cancel test', exact: true })).toHaveCount(0);
  await capture('test-completed', usage);
  await modelDetails.focus(); await page.keyboard.press('Space');
  await check(modelDetails).toBeFocused(); await check(modelDetails).toHaveAttribute('aria-expanded', 'false');
  await page.reload();
  await check(modelDetails).toHaveAttribute('aria-expanded', 'false');
  await modelDetails.click();
  await check(usage.locator('dd')).toHaveText([results[1].input_tokens, results[1].output_tokens, results[1].cost_observed].map(value => value === null ? 'Unknown' : String(value)));
  const reloaded = await page.evaluate(async id => {
    const response = await fetch(`/api/v1/model-test/entries/${id}`);
    if (!response.ok) throw new Error('Reloaded exact test readback refused');
    return response.json();
  }, operation);
  assert.deepEqual(reloaded, results[1]);
  await check(test.getByText('Connected', { exact: true })).toBeVisible();
  await check(configured.getByText('Connected', { exact: true })).toHaveCount(2);
  const fresh = await page.context().newPage();
  try {
    await fresh.goto(`${origin}/settings/providers`);
    await check(fresh.getByRole('region', { name: 'Configured models' }).getByText('Connected', { exact: true })).toHaveCount(2);
    assert.equal(await fresh.evaluate(() => sessionStorage.getItem('omnis-entry-test-v1')), null);
    await check(fresh.getByRole('button', { name: 'Add models', exact: true })).toHaveCount(1);
    await check(fresh.getByRole('button', { name: 'Details for fixture/03 via OpenRouter', exact: true })).toHaveAttribute('aria-expanded', 'false');
  } finally { await fresh.close(); }
  await check(page.getByLabel('Brain', { exact: true }).locator('option:checked')).toHaveText(/^fixture\/00 · OpenRouter$/);
  const brain = page.getByLabel('Brain', { exact: true });
  const second = await brain.locator('option').evaluateAll(options => options.find(item => item.textContent.startsWith('fixture/01 ·'))?.value);
  assert.ok(second);
  await brain.selectOption(second);
  await assignments.getByText('Output controls', { exact: true }).click();
  await check(page.getByLabel('Brain output tokens', { exact: true })).toHaveValue('37');
  await assignments.getByRole('button', { name: 'Save assignments', exact: true }).click();
  await check(notification).toContainText('Assignments saved. Applies to future runs only.');
  await page.reload();
  const savedSelection = (await loadedMany()).selection;
  await capture('saved-many-assignments', brain, assignments.getByText('Output controls', { exact: true }));
  await brain.focus(); await page.keyboard.press('Tab');
  assert.ok(await page.evaluate(() => document.activeElement?.matches('select,input,button,a')));
  assert.equal(await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches), true);
  await page.evaluate(() => { document.documentElement.style.zoom = '2'; });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Overflow at 200% CSS zoom');
  await screenshot('settings-models-saved-many-200pct-1440x1000');
  await page.evaluate(() => { document.documentElement.style.zoom = ''; });

  await page.getByRole('button', { name: 'Add models', exact: true }).click();
  await check(wizard.getByText('Saved key', { exact: true })).toBeVisible();
  const disabled = await secondWriter({ action: 'revoke_connection', command_id: crypto.randomUUID(), connection_id: connection.connection_id, expected_revision: connection.revision });
  assert.equal(disabled.status, 200);
  assert.equal(disabled.body.connections[0].enabled, false);
  assert.equal(disabled.body.connections[0].revision, 2);
  const staleRefresh = page.waitForResponse(response => response.url() === `${origin}${catalog}/refresh` && response.request().method() === 'POST');
  await wizard.getByRole('button', { name: 'Continue', exact: true }).click();
  const staleDenied = await staleRefresh;
  assert.equal(staleDenied.status(), 409);
  assert.equal((await staleDenied.json()).error.code, 'CONNECTION_UNAVAILABLE');
  const catalogFailure = wizard.getByText('Models could not be loaded. Reload settings before trying again.', { exact: true });
  await check(catalogFailure).toBeVisible();
  await check(wizard.getByText('Catalog details', { exact: true })).toBeVisible();
  await check(page.getByRole('complementary', { name: 'Settings notification', exact: true, includeHidden: true }).filter({ hasText: /Catalog|Models could not/ })).toHaveCount(0);
  await check(wizard.getByRole('button', { name: 'Continue', exact: true })).toBeDisabled();
  await check(wizard.getByRole('button', { name: /^Add fixture\// })).toHaveCount(0);
  assert.deepEqual((await readSettings()).selection, savedSelection);
  assert.equal((await readSettings()).connections[0].enabled, false);
  await capture('stale-wizard-denied', catalogFailure);
  await page.getByRole('button', { name: 'Reload current settings', exact: true }).click();
  await check(wizard.getByRole('alert')).toContainText('This connection changed or was disabled.');
  await check(wizard.getByRole('button', { name: 'Continue', exact: true })).toBeDisabled();
  await wizard.getByRole('button', { name: 'Cancel', exact: true }).click();
  const refusal = await secondWriter({ ...testIntent, operation_id: crypto.randomUUID(), consent: true }, '/api/v1/model-test/entries');
  assert.equal(refusal.status, 409);
  assert.equal(refusal.body.error.code, 'CONNECTION_UNAVAILABLE');
  assert.deepEqual((await readSettings()).selection, savedSelection);
  await page.reload();
  await loadedMany();
  await check(configured.getByText('Connection disabled', { exact: true })).toBeVisible();
  await check(configured.getByRole('button', { name: 'Test fixture/00 via OpenRouter', exact: true })).toBeDisabled();
  await check(assignments.getByRole('button', { name: 'Save assignments', exact: true })).toBeDisabled();
  assert.equal(writes.filter(item => item.action === 'save_connection').length, 1);
  assert.equal(writes.filter(item => item.path === '/api/v1/settings/models').length, 3);
  assert.equal(writes.filter(item => item.path === '/api/v1/model-test/entries').length, 3);
  return { entries: 32, firstSetup: true, oneModelConfirmation: true, realCas: 'REVISION_CONFLICT', savedKeyMultiAdd: true, reviewBackRetained: 29, saveAndConnect: true, exactTestOperations: operations, testedModels: ['fixture/02', 'fixture/03'], freshPageConnected: true, savedDefault: 'fixture/00', defaultUnchanged: true, refusal: { status: refusal.status, code: refusal.body.error.code }, staleWizard: { status: staleDenied.status(), code: 'CONNECTION_UNAVAILABLE' }, explicitBrain: 'fixture/01', brainOutputTokens: 37, selectionRevision: 3, disabled: true };
}
