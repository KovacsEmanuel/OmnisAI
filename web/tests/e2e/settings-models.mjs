// Real built App -> paired HTTP API -> existing control/PG owner -> owned TLS peer.
// Invoke only from test_model_test_v2.py's settings_ui case, never standalone production.
import assert from 'node:assert/strict';
export async function runSettingsModels({ page, check, paired, origin, screenshot }) {
  await paired();
  await page.goto(`${origin}/settings/providers`);
  const configured = page.getByRole('region', { name: 'Configured models' });
  if (process.env.OMNIS_E2E_STAGE === 'after') {
    await check(configured.getByRole('button', { name: /^Test fixture\// })).toHaveCount(32);
    await check(configured.getByText('Connection disabled', { exact: true })).toBeVisible();
    await check(page.getByLabel('Brain', { exact: true })).toHaveDisplayValue(/fixture\/01/);
    await page.getByText('Output controls', { exact: true }).click();
    await check(page.getByLabel('Brain output tokens', { exact: true })).toHaveValue('37');
    await screenshot('settings-models-api-restart-loaded');
    return { entries: 32, apiRestartReadback: true, disabled: true };
  }
  await check(configured).toContainText('No models configured.');
  await check(page.getByRole('region', { name: 'Add models wizard' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Add models', exact: true }).click();
  const wizard = page.getByRole('region', { name: 'Add models wizard' });
  await check(wizard.getByText('Saved key', { exact: true })).toBeVisible();
  await check(wizard.getByLabel('API key', { exact: true })).toHaveCount(0);
  await wizard.getByRole('button', { name: 'Continue', exact: true }).click();
  await check(wizard.getByRole('button', { name: 'Add fixture/00', exact: true })).toBeVisible();
  await check(wizard).toContainText('READY · 32 matching cached models');
  for (let pageNumber = 0; pageNumber < 2; pageNumber++) {
    for (let index = pageNumber * 16; index < (pageNumber + 1) * 16; index++) await wizard.getByRole('button', { name: `Add fixture/${String(index).padStart(2, '0')}`, exact: true }).click();
    if (!pageNumber) await wizard.getByRole('button', { name: 'Next results', exact: true }).click();
  }
  await check(wizard.getByRole('list', { name: 'Selected models' }).locator('li')).toHaveCount(32);
  await wizard.getByRole('button', { name: 'Continue', exact: true }).click();
  await check(wizard.getByRole('button', { name: 'Back', exact: true })).toBeVisible();
  await wizard.getByText('Output controls', { exact: true }).click();
  await wizard.getByLabel('fixture/00 output tokens', { exact: true }).fill('64');
  await wizard.getByLabel('fixture/02 output tokens', { exact: true }).fill('64');
  await wizard.getByRole('button', { name: 'Save models', exact: true }).click();
  await check(configured.getByRole('button', { name: /^Test fixture\// })).toHaveCount(32);
  await check(page.getByText(/Save assignments separately to choose a default/)).toBeVisible();
  const choose = page.getByLabel('Default model', { exact: true });
  const first = await choose.locator('option').evaluateAll(options => options.find(item => item.textContent.startsWith('fixture/00 ·'))?.value);
  const second = await choose.locator('option').evaluateAll(options => options.find(item => item.textContent.startsWith('fixture/01 ·'))?.value);
  assert.ok(first && second);
  await choose.selectOption(first); await page.getByLabel('Brain', { exact: true }).selectOption(second);
  await page.getByText('Output controls', { exact: true }).click();
  await page.getByLabel('Default output tokens', { exact: true }).fill('64');
  await page.getByLabel('Brain output tokens', { exact: true }).fill('37');
  await page.getByRole('button', { name: 'Save assignments', exact: true }).click();
  await check(page.getByText('Assignments saved. Applies to future runs only.', { exact: true })).toBeVisible();
  await page.reload(); await check(configured.getByRole('button', { name: /^Test fixture\// })).toHaveCount(32);
  await check(page.getByLabel('Brain', { exact: true })).toHaveValue(second);
  await page.getByText('Output controls', { exact: true }).click();
  await check(page.getByLabel('Brain output tokens', { exact: true })).toHaveValue('37');
  await screenshot('settings-models-1440-loaded');
  const savedSelection = await page.evaluate(async () => (await (await fetch('/api/v1/settings/providers')).json()).selection);
  await configured.getByRole('button', { name: 'Test fixture/02 via OpenRouter', exact: true }).click();
  await page.getByRole('checkbox', { name: /I approve the fixed input/ }).check();
  const submitted = page.waitForRequest(request => request.method() === 'PUT' && request.url() === `${origin}/api/v1/model-test/entries`);
  await page.getByRole('button', { name: 'Send model test', exact: true }).click();
  const testIntent = (await submitted).postDataJSON();
  const test = page.getByRole('region', { name: 'Model test operation' });
  await check(test).toContainText('COMPLETED');
  await check(test).toContainText('fixture/02');
  assert.deepEqual(await page.evaluate(async () => (await (await fetch('/api/v1/settings/providers')).json()).selection), savedSelection, 'Testing a non-default entry must not swap assignments');
  const operation = (await test.innerText()).match(/Operation ([0-9a-f-]{36})/)?.[1]; assert.ok(operation);
  await page.reload(); await check(test).toContainText(operation); await check(test).toContainText('COMPLETED');
  await page.getByText('Connection options', { exact: true }).click(); page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Disable connection', exact: true }).click();
  await check(configured.getByText('Connection disabled', { exact: true })).toBeVisible();
  await check(configured.getByRole('button', { name: 'Test fixture/00 via OpenRouter', exact: true })).toBeDisabled();
  await check(page.getByRole('button', { name: 'Save assignments', exact: true })).toBeDisabled();
  const refusal = await page.evaluate(async intent => {
    const session = await (await fetch('/api/session')).json();
    const response = await fetch('/api/v1/model-test/entries', { method: 'PUT', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf_token }, body: JSON.stringify({ ...intent, operation_id: crypto.randomUUID(), consent: true }) });
    return { status: response.status, code: (await response.json()).error?.code };
  }, testIntent);
  assert.deepEqual(refusal, { status: 409, code: 'CONNECTION_UNAVAILABLE' }, 'A disabled connection must refuse an explicit test before new dispatch');
  assert.deepEqual(await page.evaluate(async () => (await (await fetch('/api/v1/settings/providers')).json()).selection), savedSelection);
  await page.setViewportSize({ width: 390, height: 844 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Mobile overflow');
  await screenshot('settings-models-390-disabled');
  return { entries: 32, exactTestOperation: operation, testedModel: 'fixture/02', savedDefault: 'fixture/00', defaultUnchanged: true, refusal, explicitBrain: 'fixture/01', brainOutputTokens: 37, disabled: true };
}
