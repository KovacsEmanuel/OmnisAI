import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const source = readFileSync(new URL('../tests/e2e/run.mjs', import.meta.url), 'utf8');
const start = source.indexOf("context.on('response', response => {");
const end = source.indexOf("\ncontext.on('page'", start);
assert.ok(start >= 0 && end > start);
const register = new Function('context', 'diagnosticPost', 'diagnosticTasks', 'negativeDiagnostic', 'diagnosticContract', 'assert', 'diagnosticReceipts', 'diagnosticErrors', source.slice(start, end));
const predicate = source.match(/^function diagnosticPost\(request\).*$/m);
assert.ok(predicate);
const origin = 'http://127.0.0.1:1';
const path = '/api/v1/diagnostics/ui-events';
const diagnosticPost = new Function('origin', 'diagnosticPath', predicate[0] + ';return diagnosticPost;')(origin, path);
const schemas = JSON.parse(readFileSync(new URL('../../contracts/omnis.openapi.json', import.meta.url))).components.schemas;
const id = '00000000-0000-4000-8000-000000000001';
const event = { version: 1, source: 'browser_untrusted', event_id: id, surface: 'brain_stream', site: 'http_read', action: 'REQUEST', outcome: 'UNCONFIRMED', error_code: null, correlation_id: null, run_id: null, command_id: null };
const ack = { version: 1, event_id: id, accepted: true, state: 'RECORDED' };

async function observe({ bytes = JSON.stringify(ack), unavailable = false, status = 202, correlation = id, negative = false, method = 'POST', url = origin + path } = {}) {
  const tasks = [], receipts = [], errors = [];
  let listener, bodyReads = 0;
  register({ on(name, callback) { assert.equal(name, 'response'); listener = callback; } }, diagnosticPost, tasks, negative ? { id } : null, schemas, assert, receipts, errors);
  // No request.failure flag: body availability, not a guessed abort event, defines this seam.
  const request = { method: () => method, url: () => url, postDataJSON: () => event };
  const response = { request: () => request, headers: () => ({ 'x-correlation-id': correlation }), status: () => status,
    async body() { bodyReads += 1; if (unavailable) throw new Error('Synthetic unavailable body'); return Buffer.from(bytes); },
    async json() { return JSON.parse((await this.body()).toString('utf8')); } };
  listener(response);
  await Promise.all(tasks);
  return { tasks: tasks.length, receipts, errors, bodyReads };
}

test('unavailable body is transport-unconfirmed, never a malformed or recorded ACK', async () => {
  const result = await observe({ unavailable: true });
  assert.equal(result.tasks, 1); assert.equal(result.bodyReads, 1);
  assert.deepEqual(result.errors, []);
  assert.deepEqual(result.receipts, [{ event, request_correlation_id: id, state: 'TRANSPORT_UNCONFIRMED' }]);
  assert.equal(result.receipts.some(receipt => receipt.state === 'RECORDED' || Object.hasOwn(receipt, 'accepted')), false);
});

test('complete delivered ACKs retain every contract delivery state', async () => {
  for (const state of schemas.UiAck.properties.state.enum) {
    const result = await observe({ bytes: JSON.stringify({ ...ack, state }) });
    assert.deepEqual(result.errors, []); assert.equal(result.bodyReads, 1);
    assert.deepEqual(result.receipts, [{ event, request_correlation_id: id, state }]);
  }
});

for (const [name, bytes] of [
  ['unparseable JSON', '{'], ['null', 'null'], ['array', '[]'], ['missing shape', '{}'],
  ['extra field', JSON.stringify({ ...ack, extra: true })], ['version', JSON.stringify({ ...ack, version: 2 })],
  ['accepted false', JSON.stringify({ ...ack, accepted: false })],
  ['foreign identity', JSON.stringify({ ...ack, event_id: '00000000-0000-4000-8000-000000000002' })],
  ['unknown state', JSON.stringify({ ...ack, state: 'NOT_A_STATE' })],
]) {
  test(`readable malformed ACK remains an error: ${name}`, async () => {
    const result = await observe({ bytes });
    assert.equal(result.bodyReads, 1); assert.deepEqual(result.receipts, []);
    assert.deepEqual(result.errors, ['INVALID_DIAGNOSTIC_ACK']);
  });
}

for (const correlation of [null, 'invalid']) {
  test(`invalid correlation is not excused by an unavailable body: ${String(correlation)}`, async () => {
    const result = await observe({ correlation, unavailable: true });
    assert.equal(result.bodyReads, 0); assert.deepEqual(result.receipts, []);
    assert.deepEqual(result.errors, ['INVALID_DIAGNOSTIC_ACK']);
  });
}

for (const status of [401, 403, 503]) {
  test(`HTTP refusal ${status} remains distinct from an ACK or transport loss`, async () => {
    const result = await observe({ status, unavailable: true });
    assert.equal(result.bodyReads, 0); assert.deepEqual(result.errors, []);
    assert.deepEqual(result.receipts, [{ event, request_correlation_id: id, state: 'HTTP_REFUSED' }]);
  });
}

for (const status of [200, 422, 500]) {
  test(`unexpected status ${status} remains an error`, async () => {
    const result = await observe({ status, unavailable: true });
    assert.equal(result.bodyReads, 0); assert.deepEqual(result.receipts, []);
    assert.deepEqual(result.errors, ['INVALID_DIAGNOSTIC_ACK']);
  });
}

test('explicit negative probe accepts only422 and never reads or records its body', async () => {
  const result = await observe({ negative: true, status: 422, correlation: null, unavailable: true });
  assert.equal(result.tasks, 1); assert.equal(result.bodyReads, 0);
  assert.deepEqual(result.receipts, []); assert.deepEqual(result.errors, []);
  const refused = await observe({ negative: true, status: 202, unavailable: true });
  assert.equal(refused.bodyReads, 0); assert.deepEqual(refused.receipts, []);
  assert.deepEqual(refused.errors, ['INVALID_DIAGNOSTIC_ACK']);
});

test('unchanged diagnostic predicate ignores GET and other endpoints', async () => {
  for (const options of [{ method: 'GET' }, { url: origin + '/other' }]) {
    const result = await observe(options);
    assert.deepEqual(result, { tasks: 0, receipts: [], errors: [], bodyReads: 0 });
  }
});
