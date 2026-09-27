import assert from 'node:assert/strict';
import { test } from 'node:test';
import { JSDOM } from 'jsdom';
import { assertSecretFree } from '../tests/e2e/leaks.mjs';

test('leak verifier rejects unlabelled tokens and live input values, without reflecting them', () => {
  const marker = 'synthetic-secret-marker-for-negative-control';
  const dom = new JSDOM('<input type="password">');
  const input = dom.window.document.querySelector('input');
  input.value = marker;
  assert.ok(!dom.window.document.body.innerHTML.includes(marker));
  assertSecretFree([marker], ['ordinary output', '']);
  for (const observed of [[`raw: ${marker}`], [input.value]]) {
    assert.throws(() => assertSecretFree([marker], observed), error => {
      assert.ok(!error.message.includes(marker));
      return error.message === 'Synthetic secret leaked';
    });
  }
  dom.window.close();
});
