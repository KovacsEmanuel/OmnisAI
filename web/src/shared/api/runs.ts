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
export type RunSummary = components['schemas']['RunSummary'];
export type RunCommand = components['schemas']['RunCommand'];
export function runCommandFits(command: RunCommand) {
  return new TextEncoder().encode(JSON.stringify(command)).length <= 3600 && (command.action !== 'answer' || (typeof command.answer === 'string' && command.answer.trim().length > 0 && Array.from(command.answer).length <= 2048 && !/[\0\uD800-\uDFFF]/u.test(command.answer)));
}
export type Preflight = components['schemas']['Preflight'];
export type StartRun = components['schemas']['StartRun'];
export type Receipt = components['schemas']['CommandReceipt'];
export type Attempt = components['schemas']['Attempt'];
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
export function decodeAttempt(value: unknown): Attempt {
  const row = record(value, ['instance_id', 'run_id', 'task_id', 'attempt_id', 'role', 'parent_task_id', 'state', 'brief', 'input_refs', 'input_text', 'instructions', 'configured_model', 'observed_model', 'skill_refs', 'result_summary', 'result_ref', 'read_receipt_ref', 'call_id', 'tool_arguments', 'tool_output', 'correction_count']);
  if (integer(row.correction_count) > 1) return fail();
  return { configured_model: text(row.configured_model, 256), observed_model: nullable(row.observed_model, value => text(value, 256)), skill_refs: list(row.skill_refs, 32, decodeExactRef), result_summary: nullable(row.result_summary, value => text(value, 256)), instance_id: id(row.instance_id), run_id: id(row.run_id), task_id: id(row.task_id), attempt_id: id(row.attempt_id), role: oneOf(row.role, ['BRAIN', 'RECON']), parent_task_id: nullable(row.parent_task_id, id), state: oneOf(row.state, ['RUNNING', 'SUCCEEDED', 'INCONCLUSIVE', 'FAILED', 'CANCELLED', 'NEEDS_RECONCILIATION']), brief: text(row.brief, 1024), input_refs: list(row.input_refs, 32, decodeRef), input_text: text(row.input_text), instructions: text(row.instructions), result_ref: nullable(row.result_ref, decodeRef), read_receipt_ref: nullable(row.read_receipt_ref, decodeRef), call_id: nullable(row.call_id, value => text(value, 128)), tool_arguments: nullable(row.tool_arguments, value => text(value, 128)), tool_output: nullable(row.tool_output, text), correction_count: integer(row.correction_count) };
}
function question(value: unknown): components['schemas']['Question'] {
  const row = record(value, ['question_id', 'run_id', 'task_id', 'revision', 'kind', 'cause', 'text', 'refs', 'state', 'answer_ref', 'command_id']);
  if (row.kind !== 'CLARIFICATION') return fail();
  if ((row.state === 'PENDING') !== (row.answer_ref === null && row.command_id === null) || (row.state !== 'PENDING' && (row.answer_ref === null || row.command_id === null))) return fail();
  return { question_id: id(row.question_id), run_id: id(row.run_id), task_id: id(row.task_id), revision: integer(row.revision, 1), kind: 'CLARIFICATION', cause: text(row.cause, 256), text: text(row.text, 1024), refs: list(row.refs, 32, decodeRef), state: oneOf(row.state, ['PENDING', 'ANSWER_ADMITTED', 'CONSUMED']), answer_ref: nullable(row.answer_ref, decodeRef), command_id: nullable(row.command_id, id) };
}
export function decodeRunSummary(value: unknown, runId: string): RunSummary {
  const row = record(value, ['run', 'owner_live', 'phase_active', 'question', 'attempts', 'has_more', 'as_of']);
  if (new TextEncoder().encode(JSON.stringify(value)).length > 65536) return fail();
  const result = { owner_live: bool(row.owner_live), phase_active: bool(row.phase_active), run: decodeRun(row.run), question: nullable(row.question, question), attempts: list(row.attempts, 50, decodeAttempt), has_more: bool(row.has_more), as_of: text(row.as_of, 40) };
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
