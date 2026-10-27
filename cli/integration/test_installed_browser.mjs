import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { assertProvider, assertDenial, assertJourney } from './installed_browser.mjs';

test('source caller waits for pairing then opens Runtime before diagnostics', async () => {
  const source = await readFile(new URL('./installed_browser.mjs', import.meta.url), 'utf8');
  const steps = source.split('\n').map(line => line.trim());
  const paired = steps.indexOf("await page.getByRole('button', { name: 'Pair browser' }).click();");
  assert.notEqual(paired, -1);
  assert.deepEqual(steps.slice(paired + 1, paired + 4), [
    "await expect(page.getByLabel('Pairing code')).toHaveCount(0);",
    'await page.goto(`${origin}/settings/runtime`);',
    "await page.getByText('Instance diagnostics', { exact: true }).click();",
  ]);
});

const selection = { provider: 'openai-codex', model: 'gpt-6.1-sol', effort: 'xhigh' };
test('auth journey has one Connect and same-operation Cancel', () => {
  const steps = [{action:'read',id:'a'}, {action:'save',id:'b'}, {action:'read',id:'c'}, {action:'connect',id:'d'}, {action:'cancel',id:'d'}];
  assertJourney('settings-auth', steps);
  assert.throws(() => assertJourney('settings-auth', [...steps, {action:'connect',id:'e'}]));
  assert.throws(() => assertJourney('settings-auth', [...steps.slice(0,4), {action:'cancel',id:'e'}]));
});
const view = { operation_id: 'a', status: 'CONFIRMED', selection, configured: true,
  authenticated: 'NOT_VERIFIED', reachable: 'NOT_VERIFIED', inference_ready: false, oauth: 'NONE', challenge: null };
test('actual browser oracle accepts exact readback, refuses dishonest axes and selection', () => {
  assertProvider(view, 'a', true);
  assertProvider({ ...view, selection: null, configured: false }, 'a', false);
  for (const change of [{ operation_id: 'b' }, { status: 'PENDING' }, { authenticated: 'READY' },
    { reachable: 'READY' }, { inference_ready: true }, { configured: 1 },
    { selection: { ...selection, effort: 'high' } }, { extra: true }]) {
    assert.throws(() => assertProvider({ ...view, ...change }, 'a', true));
  }
});
test('denial oracle checks status and exact public reason', () => {
  assertDenial(403, { error: { code: 'INVALID_CSRF' } }, 403, 'INVALID_CSRF');
  assert.throws(() => assertDenial(200, { error: { code: 'INVALID_CSRF' } }, 403, 'INVALID_CSRF'));
  assert.throws(() => assertDenial(403, { error: { code: 'INVALID_ORIGIN' } }, 403, 'INVALID_CSRF'));
});
test('finite journey rejects replay and save after restart', () => {
  assertJourney('settings-save', [{ action: 'read', id: 'a' }, { action: 'save', id: 'b' }, { action: 'read', id: 'c' }]);
  assertJourney('settings-readback', [{ action: 'read', id: 'd' }]);
  assert.throws(() => assertJourney('settings-readback', [{ action: 'save', id: 'd' }]));
  assert.throws(() => assertJourney('settings-save', [{ action: 'read', id: 'a' }, { action: 'save', id: 'a' }, { action: 'read', id: 'c' }]));
});
