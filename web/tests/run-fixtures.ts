import type { components } from '../src/shared/api/generated';
import { instance } from './fixtures';
import { id } from './projection-fixtures';

// SOURCE-only synthetic wire data; never substituted for owner/API/PG evidence.
export function emptyUsage(scope: 'RUN' | 'ATTEMPT' = 'RUN'): components['schemas']['UsageSummary'] {
  const unknown = { value: null, observed_dispatches: 0, state: 'UNKNOWN' } as const;
  return { scope, accounting_policy: 'MONITOR', roles: [], totals: { dispatches: 0, unobserved_dispatches: 0, input_tokens: unknown, output_tokens: unknown, total_tokens: unknown, cached_tokens: unknown, reasoning_tokens: unknown, cache_creation_tokens: unknown, cost_observed: unknown } };
}
export function partialUsage(scope: 'RUN' | 'ATTEMPT' = 'RUN'): components['schemas']['UsageSummary'] {
  const totals: components['schemas']['UsageTotals'] = { ...emptyUsage().totals, dispatches: 3, unobserved_dispatches: 1,
    input_tokens: { value: '18014398509481982', observed_dispatches: 2, state: 'PARTIAL' },
    output_tokens: { value: '2', observed_dispatches: 2, state: 'PARTIAL' },
    cached_tokens: { value: '0', observed_dispatches: 2, state: 'PARTIAL' },
    cost_observed: { value: '0.000000000000000000123', observed_dispatches: 2, state: 'PARTIAL' } };
  return { scope, accounting_policy: 'MONITOR', totals, roles: [{ role: 'RECON', configured_model: 'fixture/recon', connection_id: id, connection_revision: 2, totals }] };
}
export const syntheticRun: components['schemas']['RunView'] = { schema_version: 1, instance_id: instance.instance_id, engagement_id: id, run_id: '00000000-0000-4000-8000-000000000032', setup_ref: { instance_id: instance.instance_id, kind: 'run-setup-v1', id: '00000000-0000-4000-8000-000000000031', revision: 1, digest: 'd'.repeat(64) }, revision: 7, generation: 3, owner_id: instance.instance_id, owner_epoch: 1, fence: 1, state: 'RUNNING', reason: null, active_attempt_id: null, question_id: null, stagnation: 0, through_cursor: 6 };
export const syntheticAttempt: components['schemas']['Attempt'] = { instance_id: instance.instance_id, run_id: syntheticRun.run_id, task_id: id, attempt_id: id, role: 'RECON', parent_task_id: instance.instance_id, state: 'INCONCLUSIVE', brief: 'Synthetic delegated task', input_refs: [], input_text: 'Allowed synthetic input', instructions: 'Pinned synthetic instructions', configured_model: 'fixture/recon', observed_model: null, skill_refs: [], result_summary: 'Exact synthetic final', result_ref: { ...syntheticRun.setup_ref, kind: 'run-result-v1' }, read_receipt_ref: null, call_id: 'synthetic-call', tool_arguments: null, tool_output: null, correction_count: 0 };
export function inspection(actor: components['schemas']['Attempt'] = syntheticAttempt): components['schemas']['AttemptInspection'] {
  return { ...actor, result: actor.result_ref ? { run_id: actor.run_id, task_id: actor.task_id, attempt_id: actor.attempt_id, state: actor.state === 'SUCCEEDED' ? 'SUCCEEDED' : 'INCONCLUSIVE', completion_kind: 'finish', summary: actor.result_summary ?? null, consumed_refs: [], gaps: actor.state === 'SUCCEEDED' ? [] : ['INERT_READ_PROOF_INCOMPLETE', 'Synthetic gap'] } : null, decision: null, decision_completion_kind: null, consumption: actor.result_ref ? { held: false, decision_ref: null, consumer_attempt_id: null } : null, usage: emptyUsage('ATTEMPT'), dispatches: [], dispatches_has_more: false, as_of: '2026-11-04T12:00:00Z' };
}
export const syntheticMetrics = { started_at: '2026-11-04T11:00:00Z', finished_at: null, agents: 2, attempts: 4, failed_attempts: 1, sent: 3, reserved: 0, released: 0, inflight: 0, settled: 2, unknown: 1 };
export const syntheticSummary: components['schemas']['RunSummary'] = { metrics: syntheticMetrics, run: syntheticRun, owner_live: true, phase_active: false, question: null, attempts: [syntheticAttempt], usage: partialUsage(), has_more: false, as_of: '2026-11-04T12:00:00Z' };

export function agentPage(summary: components['schemas']['RunSummary']): components['schemas']['AgentPage'] {
  const groups = new Map<string, components['schemas']['Attempt'][]>();
  for (const item of summary.attempts) { const key = item.role === 'BRAIN' ? 'brain' : item.task_id; groups.set(key, [...groups.get(key) ?? [], item]); }
  const agents = [...groups].map(([agent_id, items]) => {
    const item = items[0]!;
    const parent = summary.attempts.find(parent => parent.task_id === item.parent_task_id);
    return { agent_id, role: item.role, parent_agent_id: item.role === 'BRAIN' ? null : parent?.role === 'BRAIN' ? 'brain' : item.parent_task_id, attempt_id: item.attempt_id, state: item.state, brief: item.brief, attempts: items.length };
  }).sort((a, b) => a.agent_id === 'brain' ? -1 : b.agent_id === 'brain' ? 1 : a.agent_id.localeCompare(b.agent_id));
  return { run_id: summary.run.run_id, revision: summary.run.revision, agents, has_more: false, next_after: null, as_of: summary.as_of };
}

export function consumingBrain(): components['schemas']['AttemptInspection'] {
  const consumed = syntheticAttempt.result_ref;
  if (!consumed) throw new Error('Synthetic result reference required');
  return { ...inspection(), attempt_id: instance.instance_id, task_id: instance.instance_id, parent_task_id: null, role: 'BRAIN', state: 'SUCCEEDED', result_ref: { ...consumed, id: '00000000-0000-4000-8000-000000000050', kind: 'run-decision-v2' }, result_summary: 'Synthetic exact decision', result: null, consumption: null, decision_completion_kind: 'direct', decision: { action: 'finish', summary: 'Synthetic exact decision', detail: '<b>inert decision detail</b>', consumed_refs: [consumed] } };
}

export function observedDispatch(): components['schemas']['DispatchUsage'] {
  const dispatch = '00000000-0000-4000-8000-000000000040';
  return { dispatch_id: dispatch, state: 'SETTLED', usage_ref: { ...syntheticRun.setup_ref, id: dispatch, kind: 'run-usage-v2' }, reserved_at: '2026-11-04T11:00:00Z', sent_at: '2026-11-04T11:00:01Z', settled_at: '2026-11-04T11:00:02Z', usage: {
    instance_id: instance.instance_id, run_id: syntheticRun.run_id, task_id: id, attempt_id: id, dispatch_id: dispatch, role: 'RECON', configured_model: 'fixture/recon', connection_id: id, connection_revision: 2, observed_model: 'fixture/observed', observed_at: '2026-11-04T11:00:02Z',
    measures: { input_tokens: 9007199254740991, output_tokens: 1, total_tokens: null, cached_tokens: 0, reasoning_tokens: null, cache_creation_tokens: null, cost_observed: '0.000000000000000000123' },
    reported: { prompt_tokens: 9007199254740991, completion_tokens: 1, total_tokens: null, input_tokens: null, output_tokens: null, cached_tokens: 0, reasoning_tokens: null, cache_read_input_tokens: null, cache_creation_input_tokens: null, prompt_tokens_details: { cached_tokens: 0 }, completion_tokens_details: { reasoning_tokens: null }, cost: '0.000000000000000000123' },
  } };
}
