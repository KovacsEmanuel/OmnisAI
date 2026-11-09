import { expect, it, vi } from 'vitest';
import { api } from './client';
import { decodeError } from './errors';
import { decodeEvents, decodePublications } from './runs';
import { decodeAgents, decodeAgentHistory, runDuration } from './runs';
import type { RunCommand } from './runs';
import { syntheticSummary, emptyUsage, inspection, partialUsage, observedDispatch } from '../../../tests/run-fixtures';

it('SOURCE duration freezes at the persisted final event, never mount time, and missing is UNKNOWN', () => {
  expect(runDuration(syntheticSummary)).toBe('1h 0m 0s');
  const terminal = { ...syntheticSummary, run: { ...syntheticSummary.run, state: 'STOPPED' as const }, as_of: '2026-12-01T00:00:00Z', metrics: { ...syntheticSummary.metrics, finished_at: '2026-11-04T11:00:30Z' } };
  expect(runDuration(terminal)).toBe('0h 0m 30s');
  expect(runDuration({ ...terminal, metrics: { ...terminal.metrics, finished_at: null } })).toBe('UNKNOWN');
});
it('SOURCE agent decoders refuse foreign scopes, duplicate rows and contradictory pairing', () => {
  const run = syntheticSummary.run.run_id;
  const actor = { agent_id: 'brain', role: 'BRAIN', parent_agent_id: null, attempt_id: run, state: 'SUCCEEDED', brief: 'Mission', attempts: 25 };
  const roster = { run_id: run, revision: 7, agents: [actor], has_more: true, next_after: `${run}:7:brain`, as_of: syntheticSummary.as_of };
  expect(decodeAgents(roster, run, null).agents).toHaveLength(1);
  expect(() => decodeAgents({ ...roster, run_id: actor.attempt_id + 'x' }, run, null)).toThrow();
  expect(() => decodeAgents({ ...roster, agents: [actor, actor] }, run, null)).toThrow();
  const worker = { ...actor, agent_id: "00000000-0000-4000-8000-000000000099", role: "RECON" };
  expect(decodeAgents({ ...roster, revision: 8, agents: [worker], next_after: `${run}:7:${worker.agent_id}` }, run, `${run}:7:brain`).agents).toEqual([worker]);
  for (const cursor of ['', `${run}:0:brain`, `${run}:07:brain`, `${run}:9:brain`, `foreign:7:brain`, `${run}:7:invalid`]) expect(() => decodeAgents(roster, run, cursor)).toThrow();
  const history = { run_id: run, agent_id: 'brain', through_cursor: 0, events: [], has_more: false, as_of: syntheticSummary.as_of };
  expect(decodeAgentHistory(history, run, 'brain', 0).events).toEqual([]);
  expect(() => decodeAgentHistory(history, run, run, 0)).toThrow();
  expect(() => decodeAgentHistory({ ...history, has_more: true }, run, 'brain', 0)).toThrow();
});

it('SOURCE history validates kinds, IDs, directions and reciprocal visible pairs', () => {
  const run = syntheticSummary.run.run_id;
  const event = (sequence: number, kind: string, paired: number | null, call: string | null = 'reused') => ({ event_id: `00000000-0000-4000-8000-${String(sequence).padStart(12, '0')}`, run_id: run, task_id: run, attempt_id: run, sequence, kind, summary: 'Retained event', refs: [], call_id: call, created_at: syntheticSummary.as_of, pairing: paired === null ? 'UNMATCHED' : 'MATCHED', paired_sequence: paired });
  const decode = (events: ReturnType<typeof event>[]) => decodeAgentHistory({ run_id: run, agent_id: 'brain', through_cursor: events.at(-1)?.sequence ?? 0, events, has_more: false, as_of: syntheticSummary.as_of }, run, 'brain', 0);
  const pairs = [event(1, 'tool_called', 2), event(2, 'tool_result', 1), event(3, 'tool_called', 4), event(4, 'result', 3)];
  expect(decode(pairs).events).toHaveLength(4);
  expect(decode([pairs[0]!]).events).toHaveLength(1);
  expect(decode([pairs[3]!]).events).toHaveLength(1);
  expect(decode([event(1, 'tool_called', null, null), event(2, 'tool_result', null, null)]).events.every(item => item.pairing === 'UNMATCHED')).toBe(true);
  const direct = { ...event(1, 'result', null, null), pairing: 'NOT_APPLICABLE' };
  expect(decode([direct]).events).toEqual([direct]);
  expect(decode([{ ...event(1, 'control', null, null), pairing: 'NOT_APPLICABLE' }]).events).toHaveLength(1);
  expect(decode([{ ...event(1, 'tool_called', null), pairing: 'PENDING' }]).events).toHaveLength(1);
  for (const invalid of [
    [event(1, 'result', null, null)], [event(2, 'result', 1, null)],
    [{ ...direct, pairing: 'PENDING' }], [{ ...direct, call_id: 'finish' }],
    [{ ...event(1, 'tool_result', null, null), pairing: 'NOT_APPLICABLE' }],
    [event(2, 'control', 1, null)],
    [{ ...event(1, 'tool_called', null), pairing: 'NOT_APPLICABLE' }],
    [{ ...event(1, 'result', null), pairing: 'PENDING' }],
    [{ ...event(1, 'tool_called', null, null), pairing: 'PENDING' }],
    [event(1, 'tool_called', 2, null)], [event(1, 'tool_result', 2)], [event(2, 'tool_called', 1)],
    [pairs[0]!, pairs[1]!, pairs[2]!, { ...pairs[3]!, paired_sequence: 1 }],
    [pairs[0]!, { ...pairs[1]!, call_id: 'other' }],
    [pairs[0]!, { ...pairs[1]!, attempt_id: '00000000-0000-4000-8000-000000000099' }],
    [pairs[0]!, { ...pairs[1]!, task_id: '00000000-0000-4000-8000-000000000099' }],
    [pairs[0]!, event(2, 'tool_result', null)],
  ]) expect(() => decode(invalid)).toThrow();
});

it('SOURCE normal attempt inspection retains exact result, consumption and original dispatch observations', async () => {
  const value = { ...inspection(), usage: partialUsage('ATTEMPT'), dispatches: [observedDispatch()], dispatches_has_more: true };
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async () => new Response(JSON.stringify(value))));
  expect(await api.runAttempt(value.run_id, value.attempt_id)).toEqual(value);
});

it('SOURCE decodes the normal summary required accounting without rounding decimal strings or expanding the roster', async () => {
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async () => new Response(JSON.stringify(syntheticSummary)));
  vi.stubGlobal('fetch', fetcher);
  expect(await api.runSummary(syntheticSummary.run.run_id)).toEqual(syntheticSummary);
  fetcher.mockImplementation(async () => new Response(JSON.stringify({ ...syntheticSummary, usage: emptyUsage() })));
  expect((await api.runSummary(syntheticSummary.run.run_id)).usage.totals.cost_observed.value).toBeNull();
});

const run = '00000000-0000-4000-8000-000000000001';
const command = '00000000-0000-4000-8000-000000000002';
const event = { event_id: command, run_id: run, task_id: null, attempt_id: null, sequence: 2, kind: 'control', summary: 'Persisted control', refs: [], call_id: null, created_at: '2026-11-04T00:00:00Z' };
const page = { run_id: run, events: [event], through_cursor: 2, has_more: false, as_of: '2026-11-04T00:00:00Z' };
it.each(['AUTHORITY_DENIED', 'ANSWER_DENIED', 'REF_UNAVAILABLE', 'GENERATION_CONFLICT', 'CURSOR_DENIED', 'PROJECTION_LIMIT', 'CATALOG_LIST_LIMIT'])('SOURCE recognizes public run refusal %s without accepting an unknown response', code => {
  expect(decodeError({ error: { code, correlation_id: run } }).code).toBe(code);
});
it('SOURCE binds event pages to the requested cursor and never accepts incoherent cursor claims', async () => {
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async () => new Response(JSON.stringify(page)));
  vi.stubGlobal('fetch', fetcher);
  expect(await api.runEvents(run, 1)).toEqual(page);
  await expect(api.runEvents(run, 2)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  expect(() => decodeEvents({ ...page, through_cursor: 3 }, run)).toThrow();
  expect(() => decodeEvents({ ...page, run_id: command }, run)).toThrow();
  expect(() => decodeEvents({ ...page, events: [event, event] }, run)).toThrow();
});
it('SOURCE rejects foreign command receipts without reporting admission', async () => {
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async () => new Response(JSON.stringify({ command_id: command, run_id: command, setup_ref: null, revision: 2, state: 'ADMITTED' }))));
  await expect(api.runCommand({ action: 'stop', command_id: command, run_id: run, expected_generation: 0, expected_revision: 1, answer: null, question_id: null }, 'synthetic')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
});
it('SOURCE admits only exact catalog publication refs for preflight selection', () => {
  const publication = { kind: 'catalog-publication', id: run, revision: 1, digest: 'a'.repeat(64) };
  expect(decodePublications([publication])).toEqual([publication]);
  expect(() => decodePublications([{ ...publication, kind: 'unqualified-candidate' }])).toThrow();
  expect(() => decodePublications([publication, publication])).toThrow();
});
it('SOURCE limits the complete answer command including UTF-8 and JSON escaping before fetch', async () => {
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async () => new Response(JSON.stringify({ command_id: command, run_id: run, setup_ref: null, revision: 2, state: 'ADMITTED' })));
  vi.stubGlobal('fetch', fetcher);
  const payload: RunCommand = { action: 'answer', command_id: command, run_id: run, question_id: run, expected_generation: 0, expected_revision: 1, answer: '' };
  const overhead = new TextEncoder().encode(JSON.stringify(payload)).length;
  const exact = { ...payload, answer: 'a'.repeat(3600 - overhead) };
  // Text's 2048-character bound and the wire bound are independent.
  await expect(api.runCommand(exact, 'synthetic')).rejects.toMatchObject({ code: 'INVALID_INPUT' });
  const escaped = { ...payload, answer: '\\'.repeat(Math.floor((3600 - overhead) / 2)) + 'a'.repeat((3600 - overhead) % 2) };
  expect(new TextEncoder().encode(JSON.stringify(escaped)).length).toBe(3600);
  await api.runCommand(escaped, 'synthetic');
  await expect(api.runCommand({ ...escaped, answer: escaped.answer + 'a' }, 'synthetic')).rejects.toMatchObject({ code: 'INVALID_INPUT' });
  await expect(api.runCommand({ ...payload, answer: '🧪'.repeat(900) }, 'synthetic')).rejects.toMatchObject({ code: 'INVALID_INPUT' });
  expect(fetcher).toHaveBeenCalledTimes(1);
});
