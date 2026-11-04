import { expect, it, vi } from 'vitest';
import { api } from './client';
import { decodeAttempt, decodeAttemptInspection, decodeRunSummary } from './runs';
import { isRecord } from './errors';
import { emptyUsage, inspection, observedDispatch, partialUsage, syntheticAttempt, syntheticRun, syntheticSummary, consumingBrain } from '../../../tests/run-fixtures';

const other = '00000000-0000-4000-8000-000000000099';
function detailed() { return { ...inspection(), usage: partialUsage('ATTEMPT'), dispatches: [observedDispatch()], dispatches_has_more: true }; }
function change(wire: unknown, path: string, replacement: unknown) {
  const parts = path.split('.');
  let target = wire;
  for (const key of parts.slice(0, -1)) target = Array.isArray(target) ? target[parseInt(key, 10)] : isRecord(target) ? target[key] : undefined;
  const key = parts.at(-1);
  if (!isRecord(target) || !key) throw new Error('Invalid synthetic test mutation');
  target[key] = replacement;
}

it.each([[0, '0.0'], [1, '1.0'], [0.125, '0.125'], ['1.2300e-2', '0.012300'], ['000.0100e1', '0.100'], ['0e-100', `0.${'0'.repeat(100)}`], [null, null]] as const)('SOURCE preserves original cost %s and declared decimal scale %s after JSON parsing', (cost, amount) => {
  const wire = detailed();
  wire.dispatches[0]!.usage!.reported.cost = cost;
  wire.dispatches[0]!.usage!.measures.cost_observed = amount;
  const subtotal = { value: amount, observed_dispatches: amount === null ? 0 : 2, state: amount === null ? 'UNKNOWN' : 'PARTIAL' } as const;
  wire.usage.totals.cost_observed = subtotal;
  wire.usage.roles[0]!.totals.cost_observed = subtotal;
  expect(decodeAttemptInspection(wire, wire.run_id, wire.attempt_id)).toEqual(wire);
});

it.each(['run-decision-v1', 'run-decision-v2'] as const)('SOURCE Brain %s preserves exact action/detail/consumed refs and legacy kind', kind => {
  const brain = consumingBrain();
  brain.result_ref = { ...brain.result_ref!, kind };
  brain.decision_completion_kind = kind === 'run-decision-v1' ? null : 'direct';
  expect(decodeAttemptInspection(brain, brain.run_id, brain.attempt_id)).toEqual(brain);
  expect(() => decodeAttemptInspection({ ...brain, decision_completion_kind: kind === 'run-decision-v1' ? 'direct' : null }, brain.run_id, brain.attempt_id)).toThrow();
  expect(() => decodeAttemptInspection({ ...brain, decision: { ...brain.decision, consumed_refs: [{ ...syntheticAttempt.result_ref, instance_id: other }] } }, brain.run_id, brain.attempt_id)).toThrow();
});

it('SOURCE Brain success requires a decision, never a worker final', () => {
  const wire = inspection();
  wire.role = 'BRAIN'; wire.state = 'SUCCEEDED';
  wire.result = { ...wire.result!, state: 'SUCCEEDED', completion_kind: 'direct' };
  expect(() => decodeAttemptInspection(wire, wire.run_id, wire.attempt_id)).toThrow();
});

it.each(['legacy', 'conflicting-alias', 'mismatching-total'] as const)('SOURCE preserves %s originals without double-counting cache/reasoning or inventing total', mode => {
  const wire = inspection();
  const dispatch = observedDispatch();
  dispatch.usage_ref = { ...dispatch.usage_ref!, kind: mode === 'legacy' ? 'run-usage-v1' : 'run-usage-v2' };
  dispatch.usage!.observed_model = null;
  dispatch.usage!.reported = { prompt_tokens: 3, completion_tokens: 2, total_tokens: mode === 'legacy' ? null : mode === 'conflicting-alias' ? 5 : 6, input_tokens: mode === 'conflicting-alias' ? 4 : null, output_tokens: null, cached_tokens: null, reasoning_tokens: null, cache_read_input_tokens: null, cache_creation_input_tokens: null, prompt_tokens_details: { cached_tokens: null }, completion_tokens_details: { reasoning_tokens: null }, cost: null };
  dispatch.usage!.measures = { input_tokens: mode === 'conflicting-alias' ? null : 3, output_tokens: 2, total_tokens: mode === 'mismatching-total' ? null : 5, cached_tokens: null, reasoning_tokens: null, cache_creation_tokens: null, cost_observed: null };
  const totals = { ...emptyUsage().totals, dispatches: 1, unobserved_dispatches: 0,
    input_tokens: mode === 'conflicting-alias' ? emptyUsage().totals.input_tokens : { value: '3', observed_dispatches: 1, state: 'OBSERVED' as const },
    output_tokens: { value: '2', observed_dispatches: 1, state: 'OBSERVED' as const },
    total_tokens: mode === 'mismatching-total' ? emptyUsage().totals.total_tokens : { value: '5', observed_dispatches: 1, state: 'OBSERVED' as const } };
  wire.usage = { scope: 'ATTEMPT', accounting_policy: 'MONITOR', totals, roles: [{ role: 'RECON', configured_model: wire.configured_model, connection_id: syntheticAttempt.task_id, connection_revision: 2, totals }] };
  wire.dispatches = [dispatch];
  expect(decodeAttemptInspection(wire, wire.run_id, wire.attempt_id)).toEqual(wire);
});

it('SOURCE accepts uncompleted null projections without inferring a result or consumption', () => {
  const wire = { ...inspection(), result_ref: null, result_summary: null, result: null, consumption: null, state: 'RUNNING' };
  expect(decodeAttemptInspection(wire, wire.run_id, wire.attempt_id)).toEqual(wire);
});

it.each([
  ['run_id', other], ['attempt_id', other], ['result.run_id', other], ['result.task_id', other], ['result.attempt_id', other], ['result.state', 'SUCCEEDED'], ['result.completion_kind', 'error'], ['result.completion_kind', 'inferred'], ['result.summary', 'Different retained summary'], ['result.gaps', Array(18).fill('gap')],
  ['result_ref.instance_id', other], ['result_ref.kind', 'run-decision-v2'], ['result_ref.revision', 2], ['result_ref.digest', 'z'.repeat(64)],
  ['consumption.held', 'false'], ['consumption.consumer_attempt_id', other], ['consumption.decision_ref', { ...syntheticRun.setup_ref, kind: 'run-decision-v2' }], ['consumption', null], ['decision_completion_kind', 'direct'],
  ['usage', null], ['usage.scope', 'RUN'], ['usage.roles.0.role', 'BRAIN'], ['usage.roles.0.configured_model', 'fixture/foreign'], ['usage.roles.0.connection_revision', true],
  ['dispatches_has_more', false], ['dispatches.0.state', 'PAID'], ['dispatches.0.usage_ref', null], ['dispatches.0.usage', null], ['dispatches.0.usage_ref.instance_id', other], ['dispatches.0.usage_ref.digest', 'invalid'], ['dispatches.0.usage_ref.kind', 'run-result-v1'], ['dispatches.0.usage_ref.revision', 0], ['dispatches.0.sent_at', 'yesterday'],
  ['dispatches.0.usage.instance_id', other], ['dispatches.0.usage.run_id', other], ['dispatches.0.usage.task_id', other], ['dispatches.0.usage.attempt_id', other], ['dispatches.0.usage.dispatch_id', other], ['dispatches.0.usage.role', 'BRAIN'], ['dispatches.0.usage.configured_model', 'fixture/foreign'], ['dispatches.0.usage.connection_id', other], ['dispatches.0.usage.connection_revision', 3], ['dispatches.0.usage.observed_at', 'not a timestamp'], ['dispatches.0.usage.observed_model', 'private reasoning text'],
  ['dispatches.0.usage.reported.prompt_tokens', true], ['dispatches.0.usage.reported.prompt_tokens', '12'], ['dispatches.0.usage.reported.prompt_tokens', -1], ['dispatches.0.usage.reported.prompt_tokens', 1.5], ['dispatches.0.usage.reported.prompt_tokens', 9007199254740992], ['dispatches.0.usage.reported.prompt_tokens_details.cached_tokens', '0'], ['dispatches.0.usage.reported.cost', false], ['dispatches.0.usage.reported.cost', '1e999999'], ['dispatches.0.usage.reported.cost', '-0.01'], ['dispatches.0.usage.reported.cost', 'NaN'],
  ['dispatches.0.usage.measures.input_tokens', 1], ['dispatches.0.usage.measures.total_tokens', 9007199254740992], ['dispatches.0.usage.measures.cached_tokens', null], ['dispatches.0.usage.measures.cost_observed', '1e-3'], ['dispatches.0.usage.measures.cost_observed', '0.5'], ['dispatches.0.usage.reported.private_reasoning', 'must not reach UI'], ['as_of', 'invalid'],
] as const)('SOURCE inspection rejects independent malformed or foreign %s = %s', async (path, replacement) => {
  const wire = structuredClone(detailed());
  expect(decodeAttemptInspection(wire, syntheticRun.run_id, syntheticAttempt.attempt_id)).toEqual(wire);
  change(wire, path, replacement);
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async () => new Response(JSON.stringify(wire))));
  await expect(api.runAttempt(syntheticRun.run_id, syntheticAttempt.attempt_id)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
});

it.each([
  ['usage', undefined], ['usage.accounting_policy', 'CEILING'], ['usage.scope', 'ATTEMPT'], ['usage.roles', []], ['usage.roles.0.totals.dispatches', 4], ['usage.roles.0.totals.cost_observed.value', '0.1'],
  ['usage.totals.dispatches', true], ['usage.totals.dispatches', 9007199254740992], ['usage.totals.unobserved_dispatches', 4], ['usage.totals.input_tokens.value', '1.5'], ['usage.totals.input_tokens.value', '1e2'], ['usage.totals.cost_observed.value', '-1'], ['usage.totals.cost_observed.value', '9'.repeat(257)], ['usage.totals.cost_observed.value', 0], ['usage.totals.cost_observed.observed_dispatches', 3], ['usage.totals.cost_observed.state', 'OBSERVED'], ['usage.totals.cost_observed.state', 'UNKNOWN'], ['usage.totals.total_tokens.value', '0'], ['usage.totals.total_tokens.state', 'PARTIAL'], ['usage.totals.cost_observed.extra', 'private'],
] as const)('SOURCE summary rejects coverage/decimal/source mismatch at %s', (path, replacement) => {
  const wire: unknown = JSON.parse(JSON.stringify(syntheticSummary));
  expect(decodeRunSummary(wire, syntheticRun.run_id)).toEqual(wire);
  change(wire, path, replacement);
  expect(() => decodeRunSummary(wire, syntheticRun.run_id)).toThrow();
});

it('SOURCE rejects independent cross-instance input and read receipt refs', () => {
  const wire = inspection();
  for (const field of ['input_refs', 'read_receipt_ref'] as const) {
    const ref = { ...syntheticRun.setup_ref, instance_id: other };
    expect(() => decodeAttemptInspection({ ...wire, [field]: field === 'input_refs' ? [ref] : ref }, wire.run_id, wire.attempt_id)).toThrow();
  }
});

it('SOURCE stored roster stays lean; inspector requires explicit fields and bounded unique dispatches', () => {
  const wire = detailed();
  expect(decodeAttempt(syntheticAttempt)).toEqual(syntheticAttempt);
  expect(() => decodeAttempt(wire)).toThrow();
  expect(() => decodeAttemptInspection(syntheticAttempt, wire.run_id, wire.attempt_id)).toThrow();
  expect(() => decodeAttemptInspection({ ...wire, dispatches: [observedDispatch(), observedDispatch()] }, wire.run_id, wire.attempt_id)).toThrow();
  expect(() => decodeAttemptInspection({ ...wire, dispatches: Array(21).fill(observedDispatch()) }, wire.run_id, wire.attempt_id)).toThrow();
  const empty = inspection();
  const overhead = new TextEncoder().encode(JSON.stringify({ ...empty, input_text: '', instructions: '' })).length;
  const exact = { ...empty, input_text: 'x'.repeat(32768), instructions: 'x'.repeat(65536 - overhead - 32768) };
  expect(new TextEncoder().encode(JSON.stringify(exact))).toHaveLength(65536);
  expect(decodeAttemptInspection(exact, empty.run_id, empty.attempt_id)).toEqual(exact);
  expect(() => decodeAttemptInspection({ ...exact, instructions: exact.instructions + 'x' }, empty.run_id, empty.attempt_id)).toThrow();
});

it.each(['direct', 'finish', null] as const)('SOURCE retains historical worker completion kind %s without inference', kind => {
  const wire = inspection();
  wire.result = { ...wire.result!, completion_kind: kind };
  expect(decodeAttemptInspection(wire, wire.run_id, wire.attempt_id)).toEqual(wire);
});

it.each(['FAILED', 'CANCELLED'] as const)('SOURCE accepts exact Brain failure/cancel result %s, not a decision', state => {
  const wire = inspection();
  wire.role = 'BRAIN'; wire.state = state;
  wire.result = { ...wire.result!, state, completion_kind: state === 'FAILED' ? 'error' : 'cancel' };
  expect(decodeAttemptInspection(wire, wire.run_id, wire.attempt_id)).toEqual(wire);
});

it('SOURCE lost response is UNKNOWN usage, not a receipt or zero; detail truncation never truncates aggregate', () => {
  const wire = inspection();
  const totals = { ...emptyUsage().totals, dispatches: 21, unobserved_dispatches: 21 };
  wire.usage = { scope: 'ATTEMPT', accounting_policy: 'MONITOR', totals, roles: [{ role: 'RECON', configured_model: wire.configured_model, connection_id: other, connection_revision: 1, totals }] };
  wire.dispatches = Array.from({ length: 20 }, (_, i) => ({ dispatch_id: `00000000-0000-4000-8000-${String(i + 100).padStart(12, '0')}`, state: 'UNKNOWN', usage_ref: null, usage: null, reserved_at: null, sent_at: '2026-11-04T10:00:00Z', settled_at: null }));
  wire.dispatches_has_more = true;
  expect(decodeAttemptInspection(wire, wire.run_id, wire.attempt_id)).toEqual(wire);
  expect(decodeAttemptInspection({ ...wire, dispatches: [] }, wire.run_id, wire.attempt_id).usage?.totals.dispatches).toBe(21);
  expect(() => decodeAttemptInspection({ ...wire, dispatches_has_more: false }, wire.run_id, wire.attempt_id)).toThrow();
});
