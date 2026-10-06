import type { components } from '../src/shared/api/generated';
// Synthetic component/HTTP-boundary fixtures, not product or E2E data.
export const id = '00000000-0000-4000-8000-000000000010';
export const revisionId = '00000000-0000-4000-8000-000000000011';
export const metric: components['schemas']['RunMetric'] = { state: 'UNAVAILABLE', value: null, reason: 'NOT_RUN' };
export const summary: components['schemas']['DashboardEngagement'] = {
  id: revisionId, engagement_id: id, scope_revision_id: revisionId,
  name: 'Synthetic read-only draft', assessment_mode: 'FOCUSED_TEST', revision: 2, digest: 'b'.repeat(64),
  created_at: '2026-10-06T06:00:00Z', run_id: null, through_cursor: null, run_state: 'NOT_RUN', stage: 'NOT_RUN',
};
export const projection: components['schemas']['ProjectionEnvelope'] = {
  schema_version: 1, context: 'GLOBAL', engagement_id: null, run_id: null, scope_revision_id: null,
  through_cursor: null, as_of: '2026-10-06T06:00:00Z', data_state: 'AVAILABLE',
  limit: 20, next_page: null, has_more: false,
  data: { total_engagements: 1, items: [summary], active_run: null, run_state: 'NOT_RUN',
    attention_state: 'UNAVAILABLE', metrics: { confirmed: metric, coverage: metric, cost: metric } },
};
export const draft = {
  schema_version: 1, kind: 'engagement-revision', id: revisionId, engagement_id: id,
  revision: 2, digest: summary.digest, created_at: summary.created_at,
  payload: { name: summary.name, assessment_mode: 'FOCUSED_TEST', objective_text: 'Preserve this exact objective.\nNo writes.',
    scope: [{ origin: 'https://synthetic.invalid', port: 443, path_prefix: '/api', access: 'ATTACKABLE', exclusions: ['/api/private'] }] },
};
