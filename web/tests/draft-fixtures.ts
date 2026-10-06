import type { components } from '../src/shared/api/generated';

export const engagementId = '00000000-0000-4000-8000-000000000020';
export const revisionId = '00000000-0000-4000-8000-000000000021';
export const csrf = 'a'.repeat(64);
export const payload: components['schemas']['EngagementDraft'] = {
  name: 'Synthetic lab',
  authorization: { owner: 'Synthetic owner', statement: 'Disposable data only', valid_from: '2030-01-01T00:00:00Z', valid_until: '2030-12-31T00:00:00Z' },
  scope: [{ origin: 'https://synthetic.invalid', port: 443, path_prefix: '/api', exclusions: ['/excluded'], access: 'BLOCKED' }],
  assessment_mode: 'FOCUSED_TEST', objective_text: '  Preserve 🧪\nNo writes.  ',
  objective_constraints: [{ id: revisionId, kind: 'READ_ONLY', text: 'No writes', operation_refs: [] }],
  workflow_profile_ref: null,
  application_context: { seed_urls: ['https://synthetic.invalid/api'], priority_workflows: ['Browse'], test_objects: ['Record'], import_ref: null },
  effect_rules: [{ effect_class: 'READ_ONLY_KNOWN', decision: 'DENY', note: 'No effect' }],
  budgets: { max_requests: 10, max_duration_seconds: 60, max_storage_bytes: 1024, validation_reserved_requests: 2, max_model_calls: 0 },
  data_policy: { model_projection: 'NONE', research_egress: 'NONE', retention_days: 1 },
  business_matrix: [{ id: revisionId, principal: 'Anonymous', role: 'Visitor', tenant: 'T', object: 'Record', operation: 'GET', expected: 'DENY', source: 'Synthetic', source_revision: 1 }],
  business_rules_ref: null,
};
export const revision = { schema_version: 1, kind: 'engagement-revision', id: revisionId, engagement_id: engagementId,
  revision: 1, digest: 'b'.repeat(64), created_at: '2030-01-01T00:00:00Z', payload };
