import type { components } from './generated';
import { ApiError, isRecord, isUuid } from './errors';

export type RunView = components['schemas']['RunView'];
export const runPolling = { networkMode: 'always', retry: false, refetchInterval: 5000, refetchIntervalInBackground: false, refetchOnWindowFocus: 'always', refetchOnReconnect: 'always' } as const;
export const runTerminal = (run: RunView) => ['STOPPED', 'COMPLETED', 'LIMITED'].includes(run.state);
export function checkRunProgress(next: RunView | null, previous: RunView | null | undefined) {
  if (next && previous?.run_id === next.run_id && (next.revision < previous.revision || next.through_cursor < previous.through_cursor)) throw new ApiError('INVALID_RESPONSE');
  return next;
}
export type EventPage = components['schemas']['EventPage'];
export type AgentPage = components['schemas']['AgentPage'];
export type AgentHistory = components['schemas']['AgentHistory'];
export type RunSummary = components['schemas']['RunSummary'];
export type RunCommand = components['schemas']['RunCommand'];
export function runCommandFits(command: RunCommand) {
  return new TextEncoder().encode(JSON.stringify(command)).length <= 3600 && (command.action !== 'answer' || (typeof command.answer === 'string' && command.answer.trim().length > 0 && Array.from(command.answer).length <= 2048 && !/[\0\uD800-\uDFFF]/u.test(command.answer)));
}
export type Preflight = components['schemas']['Preflight'];
export type StartRun = components['schemas']['StartRun'];
export type Receipt = components['schemas']['CommandReceipt'];
export type Attempt = components['schemas']['Attempt'];
export type AttemptInspection = components['schemas']['AttemptInspection'];
export type UsageSummary = components['schemas']['UsageSummary'];
export type UsageTotals = components['schemas']['UsageTotals'];
export type Ref = components['schemas']['Ref'];
export type ExactRef = components['schemas']['ExactRef'];
const fail = (): never => { throw new ApiError('INVALID_RESPONSE'); };
function record(value: unknown, names: string[]) {
  if (!isRecord(value) || Object.keys(value).length !== names.length || names.some(name => !Object.hasOwn(value, name))) return fail();
  return value;
}
function text(value: unknown, max = 32768): string {
  return typeof value === 'string' && Array.from(value).length <= max && !value.includes('\0') ? value : fail();
}
function integer(value: unknown, minimum = 0): number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= minimum ? value : fail();
}
function id(value: unknown): string { return isUuid(value) ? value : fail(); }
function bool(value: unknown): boolean { return typeof value === 'boolean' ? value : fail(); }
function oneOf<const T extends string>(value: unknown, choices: readonly T[]): T { return choices.find(choice => choice === value) ?? fail(); }
function nullable<T>(value: unknown, read: (value: unknown) => T): T | null { return value === null ? null : read(value); }
function list<T>(value: unknown, max: number, read: (value: unknown) => T): T[] {
  if (!Array.isArray(value) || value.length > max) return fail();
  return value.map(read);
}
function digest(value: unknown): string { return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value) ? value : fail(); }
function timestamp(value: unknown): string {
  const result = text(value, 40);
  return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(result) && Number.isFinite(Date.parse(result)) ? result : fail();
}
function decimal(value: unknown, max: number, tokens = false): string {
  const result = text(value, max);
  return (tokens ? /^[0-9]+$/ : /^[0-9]+(?:\.[0-9]+)?$/).test(result) ? result : fail();
}
export const usageFields = ['input_tokens', 'output_tokens', 'total_tokens', 'cached_tokens', 'reasoning_tokens', 'cache_creation_tokens', 'cost_observed'] as const;
function usageTotals(value: unknown): UsageTotals {
  const row = record(value, ['dispatches', 'unobserved_dispatches', ...usageFields]);
  const dispatches = integer(row.dispatches), unobserved = integer(row.unobserved_dispatches);
  if (unobserved > dispatches) return fail();
  function subtotal(key: typeof usageFields[number]): components['schemas']['UsageSubtotal'] {
    const item = record(row[key], ['value', 'observed_dispatches', 'state']);
    const covered = integer(item.observed_dispatches);
    const amount = nullable(item.value, value => decimal(value, 256, key !== 'cost_observed'));
    const state = oneOf(item.state, ['OBSERVED', 'PARTIAL', 'UNKNOWN']);
    if (covered > dispatches - unobserved || (covered === 0) !== (amount === null) || state !== (covered === 0 ? 'UNKNOWN' : covered === dispatches ? 'OBSERVED' : 'PARTIAL')) return fail();
    return { value: amount, observed_dispatches: covered, state };
  }
  return { dispatches, unobserved_dispatches: unobserved, input_tokens: subtotal('input_tokens'), output_tokens: subtotal('output_tokens'), total_tokens: subtotal('total_tokens'), cached_tokens: subtotal('cached_tokens'), reasoning_tokens: subtotal('reasoning_tokens'), cache_creation_tokens: subtotal('cache_creation_tokens'), cost_observed: subtotal('cost_observed') };
}
function decimalUnits(value: string, scale: number): bigint {
  const [whole = '', fraction = ''] = value.split('.');
  return BigInt(whole + fraction.padEnd(scale, '0'));
}
function usageSummary(value: unknown, scope: UsageSummary['scope']): UsageSummary {
  const row = record(value, ['scope', 'accounting_policy', 'totals', 'roles']);
  if (row.scope !== scope || row.accounting_policy !== 'MONITOR') return fail();
  const totals = usageTotals(row.totals);
  const roles = list(row.roles, 2, (value): components['schemas']['RoleUsage'] => {
    const role = record(value, ['role', 'configured_model', 'connection_id', 'connection_revision', 'totals']);
    const result = { role: oneOf(role.role, ['BRAIN', 'RECON']), configured_model: text(role.configured_model, 256), connection_id: id(role.connection_id), connection_revision: integer(role.connection_revision, 1), totals: usageTotals(role.totals) };
    if (!result.configured_model || !result.totals.dispatches) return fail();
    return result;
  });
  if (new Set(roles.map(role => role.role)).size !== roles.length) return fail();
  for (const key of ['dispatches', 'unobserved_dispatches'] as const) {
    if (roles.reduce((sum, role) => sum + BigInt(role.totals[key]), 0n) !== BigInt(totals[key])) return fail();
  }
  for (const key of usageFields) {
    const parts = roles.map(role => role.totals[key]);
    if (parts.reduce((sum, part) => sum + BigInt(part.observed_dispatches), 0n) !== BigInt(totals[key].observed_dispatches)) return fail();
    const amounts = parts.flatMap(part => part.value === null ? [] : [part.value]);
    const total = totals[key].value;
    if (total !== null) {
      const scale = Math.max(...[total, ...amounts].map(value => value.split('.')[1]?.length ?? 0));
      if (amounts.reduce((sum, value) => sum + decimalUnits(value, scale), 0n) !== decimalUnits(total, scale)) return fail();
    }
  }
  return { scope, accounting_policy: 'MONITOR', totals, roles };
}
export function decodeExactRef(value: unknown): ExactRef {
  const row = record(value, ['kind', 'id', 'revision', 'digest']);
  return { kind: text(row.kind, 128), id: id(row.id), revision: integer(row.revision, 1), digest: digest(row.digest) };
}
export function decodeRef(value: unknown): Ref {
  const row = record(value, ['instance_id', 'kind', 'id', 'revision', 'digest']);
  if (row.revision !== 1) return fail();
  return { instance_id: id(row.instance_id), kind: text(row.kind, 128), id: id(row.id), revision: 1, digest: digest(row.digest) };
}
export function decodeRun(value: unknown): RunView {
  const row = record(value, ['schema_version', 'instance_id', 'engagement_id', 'run_id', 'setup_ref', 'revision', 'generation', 'owner_id', 'owner_epoch', 'fence', 'state', 'reason', 'active_attempt_id', 'question_id', 'stagnation', 'through_cursor']);
  if (row.schema_version !== 1 || integer(row.stagnation) > 3) return fail();
  return { schema_version: 1, instance_id: id(row.instance_id), engagement_id: id(row.engagement_id), run_id: id(row.run_id), setup_ref: decodeRef(row.setup_ref), revision: integer(row.revision, 1), generation: integer(row.generation), owner_id: id(row.owner_id), owner_epoch: integer(row.owner_epoch, 1), fence: integer(row.fence, 1), state: oneOf(row.state, ['RUNNING', 'PAUSING', 'PAUSED', 'HOLD', 'STOPPING', 'STOPPED', 'COMPLETED', 'LIMITED', 'NEEDS_RECONCILIATION']), reason: nullable(row.reason, value => text(value, 256)), active_attempt_id: nullable(row.active_attempt_id, id), question_id: nullable(row.question_id, id), stagnation: integer(row.stagnation), through_cursor: integer(row.through_cursor) };
}
export const decodeOptionalRun = (value: unknown) => nullable(value, decodeRun);
export function decodeReceipt(value: unknown, command: string): Receipt {
  const row = record(value, ['command_id', 'setup_ref', 'run_id', 'revision', 'state']);
  if (row.command_id !== command) return fail();
  if ((row.state === 'READY' && (row.setup_ref === null || row.run_id !== null || row.revision !== 1)) || (row.state === 'ADMITTED' && (row.run_id === null || row.setup_ref !== null))) return fail();
  return { command_id: id(row.command_id), setup_ref: nullable(row.setup_ref, decodeRef), run_id: nullable(row.run_id, id), revision: integer(row.revision, 1), state: oneOf(row.state, ['READY', 'ADMITTED']) };
}
const attemptFields = ['instance_id', 'run_id', 'task_id', 'attempt_id', 'role', 'parent_task_id', 'state', 'brief', 'input_refs', 'input_text', 'instructions', 'configured_model', 'observed_model', 'skill_refs', 'result_summary', 'result_ref', 'read_receipt_ref', 'call_id', 'tool_arguments', 'tool_output', 'correction_count'];
export function decodeAttempt(value: unknown): Attempt {
  const row = record(value, attemptFields);
  if (integer(row.correction_count) > 1) return fail();
  return { configured_model: text(row.configured_model, 256), observed_model: nullable(row.observed_model, value => text(value, 256)), skill_refs: list(row.skill_refs, 32, decodeExactRef), result_summary: nullable(row.result_summary, value => text(value, 256)), instance_id: id(row.instance_id), run_id: id(row.run_id), task_id: id(row.task_id), attempt_id: id(row.attempt_id), role: oneOf(row.role, ['BRAIN', 'RECON']), parent_task_id: nullable(row.parent_task_id, id), state: oneOf(row.state, ['RUNNING', 'SUCCEEDED', 'INCONCLUSIVE', 'FAILED', 'CANCELLED', 'NEEDS_RECONCILIATION']), brief: text(row.brief, 1024), input_refs: list(row.input_refs, 32, value => ownedRef(value, id(row.instance_id))), input_text: text(row.input_text), instructions: text(row.instructions), result_ref: nullable(row.result_ref, value => ownedRef(value, id(row.instance_id))), read_receipt_ref: nullable(row.read_receipt_ref, value => ownedRef(value, id(row.instance_id))), call_id: nullable(row.call_id, value => text(value, 128)), tool_arguments: nullable(row.tool_arguments, value => text(value, 128)), tool_output: nullable(row.tool_output, text), correction_count: integer(row.correction_count) };
}
function ownedRef(value: unknown, instance: string, kinds?: readonly string[]): Ref {
  const ref = decodeRef(value);
  if (ref.instance_id !== instance || (kinds && !kinds.includes(ref.kind))) return fail();
  return ref;
}
export function sameRef(a: Ref, b: Ref): boolean {
  return a.instance_id === b.instance_id && a.kind === b.kind && a.id === b.id && a.revision === b.revision && a.digest === b.digest;
}
function consumedRefs(value: unknown, instance: string): Ref[] {
  const refs = list(value, 32, value => ownedRef(value, instance));
  if (refs.some((ref, i) => refs.slice(0, i).some(previous => sameRef(ref, previous)))) return fail();
  return refs;
}
function costDecimal(value: unknown): string {
  if (typeof value !== 'string' && (typeof value !== 'number' || !Number.isFinite(value) || value < 0)) return fail();
  const source = String(value);
  const match = /^([0-9]+)(?:\.([0-9]+))?(?:[eE]([+-]?[0-9]+))?$/.exec(source);
  if (source.length > 128 || !match) return fail();
  const exponent = BigInt(match[3] ?? '0');
  if (exponent < -256n || exponent > 256n) return fail();
  const whole = match[1] ?? '', fraction = match[2] ?? '';
  const digits = whole + fraction, position = whole.length + parseInt(match[3] ?? '0', 10);
  const first = digits.search(/[1-9]/);
  const adjusted = first < 0 ? position - digits.length : position - first - 1;
  if (Math.abs(adjusted) > 100) return fail();
  const fixed = position <= 0 ? `0.${'0'.repeat(-position)}${digits}` : position >= digits.length ? digits.padEnd(position, '0') : `${digits.slice(0, position)}.${digits.slice(position)}`;
  const result = fixed.replace(/^0+(?=\d)/, '');
  return decimal(result, 128);
}
function usageRecord(value: unknown, actor: Attempt, dispatch: string, summary: UsageSummary): components['schemas']['UsageRecord'] {
  const row = record(value, ['instance_id', 'run_id', 'task_id', 'attempt_id', 'dispatch_id', 'role', 'configured_model', 'connection_id', 'connection_revision', 'observed_at', 'observed_model', 'measures', 'reported']);
  const source = record(row.reported, ['prompt_tokens', 'completion_tokens', 'total_tokens', 'input_tokens', 'output_tokens', 'cached_tokens', 'reasoning_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens', 'prompt_tokens_details', 'completion_tokens_details', 'cost']);
  const count = (value: unknown) => nullable(value, integer);
  const cost = source.cost === null ? null : typeof source.cost === 'number' || typeof source.cost === 'string' ? source.cost : fail();
  const normalizedCost = cost === null ? null : costDecimal(cost);
  const reported = { prompt_tokens: count(source.prompt_tokens), completion_tokens: count(source.completion_tokens), total_tokens: count(source.total_tokens), input_tokens: count(source.input_tokens), output_tokens: count(source.output_tokens), cached_tokens: count(source.cached_tokens), reasoning_tokens: count(source.reasoning_tokens), cache_read_input_tokens: count(source.cache_read_input_tokens), cache_creation_input_tokens: count(source.cache_creation_input_tokens), prompt_tokens_details: nullable(source.prompt_tokens_details, value => ({ cached_tokens: count(record(value, ['cached_tokens']).cached_tokens) })), completion_tokens_details: nullable(source.completion_tokens_details, value => ({ reasoning_tokens: count(record(value, ['reasoning_tokens']).reasoning_tokens) })), cost };
  const measures = record(row.measures, [...usageFields]);
  const observedCost = nullable(measures.cost_observed, value => decimal(value, 128));
  if ((observedCost === null) !== (normalizedCost === null)) return fail();
  if (observedCost !== null && normalizedCost !== null) {
    // JSON numbers lose a float's trailing .0; compare exact units, retain the declared string.
    const scale = Math.max(observedCost.split('.')[1]?.length ?? 0, normalizedCost.split('.')[1]?.length ?? 0);
    if (decimalUnits(observedCost, scale) !== decimalUnits(normalizedCost, scale)) return fail();
  }
  const agreed = (...values: (number | null | undefined)[]) => { const known = [...new Set(values.filter(value => value !== null && value !== undefined))]; return known.length === 1 ? known[0] ?? null : null; };
  const input = agreed(reported.input_tokens, reported.prompt_tokens), output = agreed(reported.output_tokens, reported.completion_tokens);
  let total = input !== null && output !== null ? input + output : reported.total_tokens;
  if (total !== null && (!Number.isSafeInteger(total) || (reported.total_tokens !== null && reported.total_tokens !== total))) total = null;
  const expected = { input_tokens: input, output_tokens: output, total_tokens: total, cached_tokens: agreed(reported.cached_tokens, reported.cache_read_input_tokens, reported.prompt_tokens_details?.cached_tokens), reasoning_tokens: agreed(reported.reasoning_tokens, reported.completion_tokens_details?.reasoning_tokens), cache_creation_tokens: reported.cache_creation_input_tokens, cost_observed: observedCost };
  for (const key of usageFields) {
    const actual = key === 'cost_observed' ? nullable(measures[key], value => decimal(value, 128)) : count(measures[key]);
    if (actual !== expected[key]) return fail();
  }
  const role = summary.roles.find(role => role.role === actor.role);
  if (row.instance_id !== actor.instance_id || row.run_id !== actor.run_id || row.task_id !== actor.task_id || row.attempt_id !== actor.attempt_id || row.dispatch_id !== dispatch || row.role !== actor.role || row.configured_model !== actor.configured_model || !role || row.configured_model !== role.configured_model || row.connection_id !== role.connection_id || row.connection_revision !== role.connection_revision) return fail();
  const model = nullable(row.observed_model, value => text(value, 256));
  if (model !== null && !/^[!-~]+$/.test(model)) return fail();
  return { instance_id: actor.instance_id, run_id: actor.run_id, task_id: actor.task_id, attempt_id: actor.attempt_id, dispatch_id: dispatch, role: actor.role, configured_model: actor.configured_model, connection_id: role.connection_id, connection_revision: role.connection_revision, observed_at: timestamp(row.observed_at), observed_model: model, reported, measures: expected };
}
export function decodeAttemptInspection(value: unknown, runId: string, attemptId: string): AttemptInspection {
  if (new TextEncoder().encode(JSON.stringify(value)).length > 65536) return fail();
  const row = record(value, [...attemptFields, 'result', 'decision', 'decision_completion_kind', 'consumption', 'usage', 'dispatches', 'dispatches_has_more', 'as_of']);
  const actor = decodeAttempt(Object.fromEntries(attemptFields.map(key => [key, row[key]])));
  if (actor.run_id !== runId || actor.attempt_id !== attemptId) return fail();
  const result = nullable(row.result, (value): components['schemas']['ResultRecord'] => {
    const result = record(value, ['run_id', 'task_id', 'attempt_id', 'state', 'completion_kind', 'summary', 'consumed_refs', 'gaps']);
    if (result.run_id !== runId || result.task_id !== actor.task_id || result.attempt_id !== attemptId || result.state !== actor.state) return fail();
    const kind = nullable(result.completion_kind, value => oneOf(value, ['direct', 'finish', 'error', 'cancel']));
    if ((kind === 'error' && result.state !== 'FAILED') || (kind === 'cancel' && result.state !== 'CANCELLED') || ((kind === 'direct' || kind === 'finish') && !['SUCCEEDED', 'INCONCLUSIVE'].includes(actor.state))) return fail();
    return { run_id: runId, task_id: actor.task_id, attempt_id: attemptId, state: oneOf(result.state, ['SUCCEEDED', 'INCONCLUSIVE', 'FAILED', 'CANCELLED']), completion_kind: kind, summary: nullable(result.summary, value => text(value, 256)), consumed_refs: consumedRefs(result.consumed_refs, actor.instance_id), gaps: list(result.gaps, 17, value => text(value)) };
  });
  const decision = nullable(row.decision, (value): components['schemas']['BrainDecision'] => {
    const decision = record(value, ['action', 'summary', 'detail', 'consumed_refs']);
    return { action: oneOf(decision.action, ['delegate', 'ask', 'finish']), summary: text(decision.summary, 256), detail: text(decision.detail, 1024), consumed_refs: consumedRefs(decision.consumed_refs, actor.instance_id) };
  });
  const kind = nullable(row.decision_completion_kind, value => oneOf(value, ['direct']));
  const consumption = nullable(row.consumption, (value): components['schemas']['InboxConsumption'] => {
    const item = record(value, ['held', 'decision_ref', 'consumer_attempt_id']);
    const result = { held: bool(item.held), decision_ref: nullable(item.decision_ref, value => ownedRef(value, actor.instance_id, ['run-decision-v1', 'run-decision-v2'])), consumer_attempt_id: nullable(item.consumer_attempt_id, id) };
    if ((result.decision_ref === null) !== (result.consumer_attempt_id === null) || (result.held && result.decision_ref !== null) || result.consumer_attempt_id === attemptId) return fail();
    return result;
  });
  if ((result && decision) || (!!actor.result_ref !== !!(result || decision)) || (!!result !== !!consumption)) return fail();
  if (result && (actor.result_ref?.kind !== 'run-result-v1' || result.summary !== actor.result_summary || (actor.role === 'BRAIN' && !['FAILED', 'CANCELLED'].includes(result.state)))) return fail();
  if (decision && (actor.role !== 'BRAIN' || actor.state !== 'SUCCEEDED' || !actor.result_ref || !decision.summary || !decision.detail || decision.summary !== actor.result_summary)) return fail();
  if (decision && actor.result_ref) {
    const ref = ownedRef(actor.result_ref, actor.instance_id, ['run-decision-v1', 'run-decision-v2']);
    if (kind !== (ref.kind === 'run-decision-v2' ? 'direct' : null)) return fail();
  } else if (kind !== null) return fail();
  const usage = usageSummary(row.usage, 'ATTEMPT');
  if (usage.roles.some(role => role.role !== actor.role || role.configured_model !== actor.configured_model)) return fail();
  const dispatches = list(row.dispatches, 20, (value): components['schemas']['DispatchUsage'] => {
    const item = record(value, ['dispatch_id', 'state', 'usage_ref', 'usage', 'reserved_at', 'sent_at', 'settled_at']);
    const dispatch = id(item.dispatch_id);
    const ref = nullable(item.usage_ref, value => ownedRef(value, actor.instance_id, ['run-usage-v1', 'run-usage-v2']));
    const observed = nullable(item.usage, value => usageRecord(value, actor, dispatch, usage));
    if ((ref === null) !== (observed === null)) return fail();
    return { dispatch_id: dispatch, state: oneOf(item.state, ['RESERVED', 'SENT', 'SETTLED', 'RELEASED', 'UNKNOWN']), usage_ref: ref, usage: observed, reserved_at: nullable(item.reserved_at, timestamp), sent_at: nullable(item.sent_at, timestamp), settled_at: nullable(item.settled_at, timestamp) };
  });
  const more = bool(row.dispatches_has_more);
  if (new Set(dispatches.map(item => item.dispatch_id)).size !== dispatches.length || (more ? dispatches.length >= usage.totals.dispatches : dispatches.length !== usage.totals.dispatches)) return fail();
  const unobserved = dispatches.filter(item => item.usage === null).length;
  if (more ? unobserved > usage.totals.unobserved_dispatches : unobserved !== usage.totals.unobserved_dispatches) return fail();
  for (const key of usageFields) {
    const amounts = dispatches.flatMap(item => { const amount = item.usage?.measures[key]; return amount === null || amount === undefined ? [] : [String(amount)]; });
    const subtotal = usage.totals[key];
    if (more ? amounts.length > subtotal.observed_dispatches : amounts.length !== subtotal.observed_dispatches) return fail();
    if (amounts.length && subtotal.value !== null) {
      const scale = Math.max(...[subtotal.value, ...amounts].map(value => value.split('.')[1]?.length ?? 0));
      const sum = amounts.reduce((sum, value) => sum + decimalUnits(value, scale), 0n), total = decimalUnits(subtotal.value, scale);
      if (more ? sum > total : sum !== total) return fail();
    }
  }
  return { ...actor, result, decision, decision_completion_kind: kind, consumption, usage, dispatches, dispatches_has_more: more, as_of: timestamp(row.as_of) };
}
function question(value: unknown): components['schemas']['Question'] {
  const row = record(value, ['question_id', 'run_id', 'task_id', 'revision', 'kind', 'cause', 'text', 'refs', 'state', 'answer_ref', 'command_id']);
  if (row.kind !== 'CLARIFICATION') return fail();
  if ((row.state === 'PENDING') !== (row.answer_ref === null && row.command_id === null) || (row.state !== 'PENDING' && (row.answer_ref === null || row.command_id === null))) return fail();
  return { question_id: id(row.question_id), run_id: id(row.run_id), task_id: id(row.task_id), revision: integer(row.revision, 1), kind: 'CLARIFICATION', cause: text(row.cause, 256), text: text(row.text, 1024), refs: list(row.refs, 32, decodeRef), state: oneOf(row.state, ['PENDING', 'ANSWER_ADMITTED', 'CONSUMED']), answer_ref: nullable(row.answer_ref, decodeRef), command_id: nullable(row.command_id, id) };
}
function decodeMetrics(value: unknown): components['schemas']['RunMetrics'] {
  const row = record(value, ['started_at', 'finished_at', 'agents', 'attempts', 'failed_attempts', 'sent', 'reserved', 'released', 'inflight', 'settled', 'unknown']);
  const result = { started_at: nullable(row.started_at, timestamp), finished_at: nullable(row.finished_at, timestamp), agents: integer(row.agents), attempts: integer(row.attempts), failed_attempts: integer(row.failed_attempts), sent: integer(row.sent), reserved: integer(row.reserved), released: integer(row.released), inflight: integer(row.inflight), settled: integer(row.settled), unknown: integer(row.unknown) };
  if (result.agents > result.attempts || result.failed_attempts > result.attempts || result.sent !== result.inflight + result.settled + result.unknown || (result.started_at && result.finished_at && Date.parse(result.finished_at) < Date.parse(result.started_at))) return fail();
  return result;
}
export function runDuration(summary: RunSummary): string {
  const start = summary.metrics.started_at;
  const end = runTerminal(summary.run) ? summary.metrics.finished_at : summary.as_of;
  if (!start || !end || Date.parse(end) < Date.parse(start)) return 'UNKNOWN';
  const seconds = Math.floor((Date.parse(end) - Date.parse(start)) / 1000);
  return `${Math.floor(seconds / 3600)}h ${Math.floor(seconds % 3600 / 60)}m ${seconds % 60}s`;
}
export const isAgent = (value: unknown): value is string => value === 'brain' || isUuid(value);
export function decodeAgents(value: unknown, runId: string, after: string | null): AgentPage {
  if (new TextEncoder().encode(JSON.stringify(value)).length > 65536) return fail();
  const row = record(value, ['run_id', 'revision', 'agents', 'has_more', 'next_after', 'as_of']);
  if (row.run_id !== runId) return fail();
  const revision = integer(row.revision, 1);
  const agents = list(row.agents, 50, (value): components['schemas']['AgentRow'] => {
    const item = record(value, ['agent_id', 'role', 'parent_agent_id', 'attempt_id', 'state', 'brief', 'attempts']);
    const agent = isAgent(item.agent_id) ? item.agent_id : fail();
    const role = oneOf(item.role, ['BRAIN', 'RECON']);
    if ((role === 'BRAIN') !== (agent === 'brain')) return fail();
    return { agent_id: agent, role, parent_agent_id: nullable(item.parent_agent_id, value => isAgent(value) ? value : fail()), attempt_id: id(item.attempt_id), state: oneOf(item.state, ['RUNNING', 'SUCCEEDED', 'INCONCLUSIVE', 'FAILED', 'CANCELLED', 'NEEDS_RECONCILIATION']), brief: text(item.brief, 1024), attempts: integer(item.attempts, 1) };
  });
  const hasMore = bool(row.has_more), next = nullable(row.next_after, value => text(value, 128));
  const parts = after?.split(':'), issued = parts ? Number(parts[1]) : revision;
  const prefix = `${runId}:${issued}:`, previous = parts?.[2];
  const order = (agent: string) => agent === 'brain' ? '' : agent;
  if (after !== null && (parts?.length !== 3 || !Number.isSafeInteger(issued) || issued < 1 || issued > revision || after !== `${prefix}${previous}` || !isAgent(previous))) return fail();
  if (new Set(agents.map(item => item.agent_id)).size !== agents.length || agents.some((item, index) => (index > 0 && order(item.agent_id) <= order(agents[index - 1]!.agent_id)) || (previous && order(item.agent_id) <= order(previous)))) return fail();
  if (hasMore !== (next !== null) || (hasMore && (!agents.length || next !== `${prefix}${agents.at(-1)!.agent_id}`))) return fail();
  return { run_id: runId, revision, agents, has_more: hasMore, next_after: next, as_of: timestamp(row.as_of) };
}
export function decodeAgentHistory(value: unknown, runId: string, agent: string, after: number): AgentHistory {
  const row = record(value, ['run_id', 'agent_id', 'through_cursor', 'events', 'has_more', 'as_of']);
  if (row.agent_id !== agent || new TextEncoder().encode(JSON.stringify(value)).length > 65536) return fail();
  const entries = list(row.events, 50, value => record(value, ['event_id', 'run_id', 'task_id', 'attempt_id', 'sequence', 'kind', 'summary', 'refs', 'call_id', 'created_at', 'pairing', 'paired_sequence']));
  const page = decodeEvents({ run_id: row.run_id, through_cursor: row.through_cursor, has_more: row.has_more, as_of: row.as_of, events: entries.map(({ pairing: _pairing, paired_sequence: _paired, ...event }) => event) }, runId, after);
  const events = page.events.map((event, index) => {
    const pairing = oneOf(entries[index]!.pairing, ['MATCHED', 'PENDING', 'UNMATCHED', 'NOT_APPLICABLE']);
    const paired = nullable(entries[index]!.paired_sequence, value => integer(value, 1));
    if (!event.attempt_id || !event.task_id || (agent !== 'brain' && event.task_id !== agent) || (pairing === 'MATCHED') !== (paired !== null) || (paired !== null && (paired === event.sequence || (event.kind === 'tool_called' ? paired < event.sequence : paired > event.sequence)))) return fail();
    const pairable = ['tool_called', 'tool_result'].includes(event.kind) || (event.kind === 'result' && !!event.call_id);
    if (pairable === (pairing === 'NOT_APPLICABLE') || (pairable && !event.call_id && pairing !== 'UNMATCHED') || (pairing === 'PENDING' && event.kind !== 'tool_called')) return fail();
    return { ...event, pairing, paired_sequence: paired };
  });
  for (const event of events) {
    const paired = events.find(item => item.sequence === event.paired_sequence);
    if (paired && (paired.pairing !== 'MATCHED' || paired.paired_sequence !== event.sequence || paired.task_id !== event.task_id || paired.attempt_id !== event.attempt_id || paired.call_id !== event.call_id || (event.kind === 'tool_called' ? !['tool_result', 'result'].includes(paired.kind) : paired.kind !== 'tool_called'))) return fail();
  }
  if (page.has_more && !events.length) return fail();
  return { ...page, agent_id: agent, events };
}
export function decodeRunSummary(value: unknown, runId: string): RunSummary {
  const row = record(value, ['run', 'owner_live', 'phase_active', 'question', 'attempts', 'has_more', 'as_of', 'usage', 'metrics']);
  if (new TextEncoder().encode(JSON.stringify(value)).length > 65536) return fail();
  const result = { metrics: decodeMetrics(row.metrics), usage: usageSummary(row.usage, 'RUN'), owner_live: bool(row.owner_live), phase_active: bool(row.phase_active), run: decodeRun(row.run), question: nullable(row.question, question), attempts: list(row.attempts, 50, decodeAttempt), has_more: bool(row.has_more), as_of: timestamp(row.as_of) };
  if (result.run.run_id !== runId || result.attempts.some(item => item.run_id !== runId) || (result.question && result.question.run_id !== runId)) return fail();
  if (new Set(result.attempts.map(item => item.attempt_id)).size !== result.attempts.length || result.attempts.some(item => item.instance_id !== result.run.instance_id) || (result.phase_active && (!result.owner_live || result.run.state !== 'RUNNING' || result.run.active_attempt_id === null))) return fail();
  return result;
}
export function decodeEvents(value: unknown, runId: string, after = 0): components['schemas']['EventPage'] {
  const row = record(value, ['run_id', 'through_cursor', 'events', 'has_more', 'as_of']);
  if (row.run_id !== runId || new TextEncoder().encode(JSON.stringify(value)).length > 65536) return fail();
  const events = list(row.events, 50, (value): components['schemas']['RunEvent'] => {
    const event = record(value, ['event_id', 'run_id', 'task_id', 'attempt_id', 'sequence', 'kind', 'summary', 'refs', 'call_id', 'created_at']);
    if (event.run_id !== runId) return fail();
    return { event_id: id(event.event_id), run_id: runId, task_id: nullable(event.task_id, id), attempt_id: nullable(event.attempt_id, id), sequence: integer(event.sequence, 1), kind: oneOf(event.kind, ['started', 'decision', 'tool_called', 'tool_result', 'result', 'control', 'question', 'answer']), summary: text(event.summary, 256), refs: list(event.refs, 32, decodeRef), call_id: nullable(event.call_id, value => text(value, 128)), created_at: text(event.created_at, 40) };
  });
  if (events.some((event, index) => index > 0 && event.sequence <= events[index - 1]!.sequence)) return fail();
  if (new Set(events.map(event => event.event_id)).size !== events.length || events.some(event => event.sequence <= after) || row.through_cursor !== (events.at(-1)?.sequence ?? after)) return fail();
  return { run_id: runId, through_cursor: integer(row.through_cursor), events, has_more: bool(row.has_more), as_of: text(row.as_of, 40) };
}
export function decodePublications(value: unknown) {
  const refs = list(value, 50, decodeExactRef);
  if (refs.some(ref => ref.kind !== 'catalog-publication') || new Set(refs.map(ref => ref.id)).size !== refs.length) return fail();
  return refs;
}
