// Real built App -> paired HTTP API -> existing control/PG owner -> owned TLS peer.
// Invoke only from test_model_test_v2.py's settings_ui case, never standalone production.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
export async function runSettingsModels({ page, check, paired, origin, output, screenshot, secretChecks, remember }) {
  const providers = '/api/v1/settings/providers';
  const catalog = '/api/v1/settings/provider-catalog';
  const configured = page.getByRole('region', { name: 'Configured models' });
  const wizard = page.getByRole('region', { name: 'Add models wizard' });
  const assignments = page.getByRole('region', { name: 'Model assignments' });
  const test = page.getByRole('region', { name: 'Model test operation' });
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
    await check(wizard).toContainText('READY · 32 matching cached models');
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
      await check(page.getByText('Reading cached models…', { exact: true })).toHaveCount(0);
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
    await check(page.getByLabel('Brain', { exact: true }).locator('option:checked')).toHaveText(/^fixture\/01 · OpenRouter(?: · Unavailable — details needed or connection stale)?$/);
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
    const operation = previous.catalog.exactTestOperation;
    assert.match(operation, /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/);
    const history = await page.evaluate(async id => {
      const response = await fetch(`/api/v1/model-test/entries/${id}`);
      if (!response.ok) throw new Error('Exact test history readback refused');
      return response.json();
    }, operation);
    assert.equal(history.operation_id, operation);
    assert.equal(history.result_state, 'COMPLETED');
    assert.equal(history.requested_model, 'fixture/02');
    const current = await loadedMany();
    assert.equal(current.connections.length, 1);
    assert.equal(current.connections[0].enabled, false);
    assert.equal(current.connections[0].revision, 2);
    await check(configured.getByText('Connection disabled', { exact: true })).toBeVisible();
    await check(page.getByRole('button', { name: 'Save assignments', exact: true })).toBeDisabled();
    assert.deepEqual(writes, [], 'API restart/readback must not write or resend');
    await capture('api-restart-disabled', configured.getByText('Connection disabled', { exact: true }));
    return { entries: 32, apiRestartReadback: true, exactTestOperation: operation, historyReadback: true, disabled: true, selectionRevision: 3 };
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
  await wizard.getByRole('button', { name: 'Continue', exact: true }).click();
  const receipt = await (await saved).json();
  const requested = (await refresh).postDataJSON();
  const connection = receipt.connections[0];
  assert.equal(receipt.command_id, (await saved).request().postDataJSON().command_id);
  assert.equal(connection.enabled, true);
  assert.equal(connection.credential_present, true);
  assert.equal(requested.connection_id, connection.connection_id);
  assert.equal(requested.connection_revision, connection.revision);
  await catalogReady();
  await check(wizard.getByLabel('API key', { exact: true })).toHaveCount(0);
  await capture('loaded-results', wizard.getByRole('button', { name: 'Add fixture/00', exact: true }));
  await wizard.getByRole('button', { name: 'Add fixture/00', exact: true }).click();
  await wizard.getByRole('button', { name: 'Continue', exact: true }).click();
  await wizard.getByText('Output controls', { exact: true }).click();
  await wizard.getByLabel('fixture/00 output tokens', { exact: true }).fill('64');
  await check(wizard.getByRole('button', { name: 'Save & test', exact: true })).toBeDisabled();
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
  await capture('direct-test-consent', consent, configured.getByText('Test details', { exact: true }));
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
  await check(page.getByText('Settings changed. Reload the current revision before saving.', { exact: true })).toBeVisible();
  assert.deepEqual((await readSettings()).selection, preserved);
  await page.getByRole('button', { name: 'Reload current settings', exact: true }).click();
  await check(page.getByText('Settings reloaded.', { exact: true })).toBeVisible();
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
  await search.fill('fixture/02');
  await check(wizard).toContainText('READY · 1 matching cached models');
  await wizard.getByRole('button', { name: 'Add fixture/02', exact: true }).click();
  await search.fill('');
  await check(wizard).toContainText('READY · 32 matching cached models');
  await check(wizard.getByRole('button', { name: 'Selected fixture/02', exact: true })).toBeDisabled();
  for (let pageNumber = 0; pageNumber < 2; pageNumber++) {
    for (let index = pageNumber * 16; index < (pageNumber + 1) * 16; index++) {
      if (index === 0 || index === 2) continue;
      await wizard.getByRole('button', { name: `Add fixture/${String(index).padStart(2, '0')}`, exact: true }).click();
    }
    if (!pageNumber) await wizard.getByRole('button', { name: 'Next results', exact: true }).click();
  }
  const chips = wizard.getByRole('list', { name: 'Selected models' }).locator('button');
  await check(chips).toHaveCount(31);
  const selectedIds = await chips.evaluateAll(elements => elements.map(element => element.getAttribute('aria-label')).sort());
  assert.deepEqual(selectedIds, Array.from({ length: 31 }, (_, index) => `Remove selected fixture/${String(index + 1).padStart(2, '0')}`));
  await check(wizard.getByRole('button', { name: 'Next results', exact: true })).toBeDisabled();
  await wizard.getByRole('button', { name: 'Continue', exact: true }).click();
  await wizard.getByRole('button', { name: 'Back', exact: true }).click();
  assert.deepEqual(await chips.evaluateAll(elements => elements.map(element => element.getAttribute('aria-label')).sort()), selectedIds);
  await wizard.getByRole('button', { name: 'Continue', exact: true }).click();
  await wizard.getByText('Output controls', { exact: true }).click();
  await wizard.getByLabel('fixture/02 output tokens', { exact: true }).fill('64');
  await wizard.getByRole('combobox', { name: 'Model to test', exact: true }).selectOption('fixture/02');
  await check(wizard).toContainText('Default and role overrides stay unchanged.');
  await wizard.getByText('Output controls', { exact: true }).click();
  await capture('review-many', wizard.getByRole('button', { name: 'Save models', exact: true }), wizard.getByText('Output controls', { exact: true }));
  assert.deepEqual((await readSettings()).selection, preserved);
  assert.equal(writes.filter(item => item.path === '/api/v1/model-test/entries').length, 0);
  await wizard.getByRole('checkbox', { name: /I approve the fixed synthetic input and one call for fixture\/02 via OpenRouter/ }).check();
  const submitted = page.waitForRequest(request => request.method() === 'PUT' && request.url() === `${origin}/api/v1/model-test/entries`);
  await wizard.getByRole('button', { name: 'Save & test', exact: true }).click();
  const testIntent = (await submitted).postDataJSON();
  await check(test).toContainText('COMPLETED');
  await check(test).toContainText('fixture/02');
  await check(configured.getByRole('button', { name: /^Test fixture\// })).toHaveCount(32);
  assert.deepEqual((await configured.getByRole('button', { name: /^Test fixture\// }).evaluateAll(elements => elements.map(element => element.getAttribute('aria-label')))).sort(), Array.from({ length: 32 }, (_, index) => `Test fixture/${String(index).padStart(2, '0')} via OpenRouter`));
  assert.deepEqual((await readSettings()).selection, preserved, 'Save & test must preserve Default, explicit override, caps and revision');
  const operationDetails = test.getByText('Operation details', { exact: true });
  await operationDetails.click();
  const operation = (await test.innerText()).match(/Operation ([0-9a-f-]{36})/)?.[1]; assert.ok(operation);
  await check(test.getByLabel('Model response', { exact: true })).toHaveText('OMNIS_MODEL_TEST_OK');
  await operationDetails.click();
  await check(test.getByRole('button', { name: 'Cancel test', exact: true })).toHaveCount(0);
  await capture('test-completed', test, operationDetails);
  assert.equal(testIntent.operation_id, operation);
  await page.reload();
  await operationDetails.click();
  await check(test.getByText(`Operation ${operation}`, { exact: true })).toBeVisible();
  await operationDetails.click();
  await check(test).toContainText('COMPLETED');
  await check(page.getByLabel('Brain', { exact: true }).locator('option:checked')).toHaveText(/^fixture\/00 · OpenRouter$/);
  const brain = page.getByLabel('Brain', { exact: true });
  const second = await brain.locator('option').evaluateAll(options => options.find(item => item.textContent.startsWith('fixture/01 ·'))?.value);
  assert.ok(second);
  await brain.selectOption(second);
  await assignments.getByText('Output controls', { exact: true }).click();
  await check(page.getByLabel('Brain output tokens', { exact: true })).toHaveValue('37');
  await assignments.getByRole('button', { name: 'Save assignments', exact: true }).click();
  await check(assignments).toContainText('Assignments saved. Applies to future runs only.');
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
  await check(page.getByText(/Catalog outcome unknown\./)).toBeVisible();
  await check(wizard.getByRole('button', { name: 'Continue', exact: true })).toBeDisabled();
  await check(wizard.getByRole('button', { name: /^Add fixture\// })).toHaveCount(0);
  assert.deepEqual((await readSettings()).selection, savedSelection);
  assert.equal((await readSettings()).connections[0].enabled, false);
  await capture('stale-wizard-denied', page.getByText(/Catalog outcome unknown\./));
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
  assert.equal(writes.filter(item => item.path === '/api/v1/settings/models').length, 2);
  assert.equal(writes.filter(item => item.path === '/api/v1/model-test/entries').length, 2);
  return { entries: 32, firstSetup: true, oneModelConfirmation: true, realCas: 'REVISION_CONFLICT', savedKeyMultiAdd: true, reviewBackRetained: 31, saveAndTest: true, exactTestOperation: operation, testedModel: 'fixture/02', savedDefault: 'fixture/00', defaultUnchanged: true, refusal: { status: refusal.status, code: refusal.body.error.code }, staleWizard: { status: staleDenied.status(), code: 'CONNECTION_UNAVAILABLE' }, explicitBrain: 'fixture/01', brainOutputTokens: 37, selectionRevision: 3, disabled: true };
}
