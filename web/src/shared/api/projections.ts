import type { components } from './generated';
import { ApiError, isRecord, isUuid } from './errors';
import { decodeOptionalRun } from './runs';
export type Projection = components['schemas']['ProjectionEnvelope'];
type Summary = components['schemas']['DashboardEngagement'];
function invalid(): never { throw new ApiError('INVALID_RESPONSE'); }
function integer(value: unknown, minimum = 0): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= minimum;
}
function text(value: unknown, maximum: number): value is string {
  return typeof value === 'string' && value.length > 0 && Array.from(value).length <= maximum && !value.includes('\0') && !/[\uD800-\uDFFF]/u.test(value);
}
function date(value: unknown): value is string {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value) && Number.isFinite(Date.parse(value));
}
function mode(value: unknown): value is components['schemas']['AssessmentMode'] {
  return value === 'FULL_ASSESSMENT' || value === 'FOCUSED_TEST';
}
export function isDashboardCursor(value: unknown): value is string {
  return typeof value === 'string' && value.startsWith('d1.20.') && isUuid(value.slice(6));
}
function summary(value: unknown, version: 1 | 2): Summary {
  const runState = ['NOT_RUN', 'RUNNING', 'PAUSING', 'PAUSED', 'HOLD', 'STOPPING', 'STOPPED', 'COMPLETED', 'LIMITED', 'NEEDS_RECONCILIATION'] as const;
  if (!isRecord(value)) return invalid();
  const state = runState.find(state => state === value.run_state);
  if (!isRecord(value) || !isUuid(value.id) || !isUuid(value.engagement_id) || value.scope_revision_id !== value.id ||
    !text(value.name, 128) || !mode(value.assessment_mode) || !integer(value.revision, 1) ||
    typeof value.digest !== 'string' || !/^[0-9a-f]{64}$/.test(value.digest) || !date(value.created_at) ||
    !state || (value.run_id !== null && !isUuid(value.run_id)) || (value.through_cursor !== null && !integer(value.through_cursor)) ||
    (value.stage !== 'NOT_RUN' && value.stage !== 'INERT') ||
    (version === 1 && (value.run_id !== null || value.through_cursor !== null || state !== 'NOT_RUN' || value.stage !== 'NOT_RUN'))) return invalid();
  return { id: value.id, engagement_id: value.engagement_id, scope_revision_id: value.id, name: value.name,
    assessment_mode: value.assessment_mode, revision: value.revision, digest: value.digest, created_at: value.created_at,
    run_id: value.run_id, through_cursor: value.through_cursor, run_state: state, stage: value.stage };
}
function metric(value: unknown): components['schemas']['RunMetric'] {
  if (!isRecord(value) || value.state !== 'UNAVAILABLE' || value.reason !== 'NOT_RUN' || value.value !== null) return invalid();
  return { state: value.state, reason: value.reason, value: null };
}
export type SelectedDraft = Pick<components['schemas']['EngagementView'], 'schema_version' | 'kind' | 'id' | 'engagement_id' | 'revision' | 'digest' | 'created_at'> & {
  payload: Pick<components['schemas']['EngagementDraft'], 'name' | 'assessment_mode' | 'objective_text' | 'scope'>;
};
function scope(value: unknown): components['schemas']['ScopeEntry'] {
  if (!isRecord(value) || !text(value.origin, 255) || !text(value.path_prefix, 2048) ||
    !integer(value.port, 1) || value.port > 65535 ||
    !(value.access === 'ATTACKABLE' || value.access === 'VISIT_ONLY' || value.access === 'BLOCKED') ||
    !Array.isArray(value.exclusions) || value.exclusions.length > 32) return invalid();
  const exclusions = value.exclusions.map(item => { if (!text(item, 2048)) return invalid(); return item; });
  return { origin: value.origin, path_prefix: value.path_prefix, port: value.port, access: value.access, exclusions };
}
export function decodeSelectedDraft(value: unknown, engagementId: string): SelectedDraft {
  if (!isRecord(value) || value.schema_version !== 1 || value.kind !== 'engagement-revision' ||
    !isUuid(value.id) || value.engagement_id !== engagementId || !integer(value.revision, 1) ||
    typeof value.digest !== 'string' || !/^[0-9a-f]{64}$/.test(value.digest) || !date(value.created_at) ||
    !isRecord(value.payload)) return invalid();
  const payload = value.payload;
  if (!text(payload.name, 128) || !mode(payload.assessment_mode) || !text(payload.objective_text, 8192) ||
    !Array.isArray(payload.scope) || payload.scope.length === 0 || payload.scope.length > 64) return invalid();
  return { schema_version: value.schema_version, kind: value.kind, id: value.id, engagement_id: engagementId,
    revision: value.revision, digest: value.digest, created_at: value.created_at,
    payload: { name: payload.name, assessment_mode: payload.assessment_mode, objective_text: payload.objective_text,
      scope: payload.scope.map(scope) } };
}
export function decodeProjection(value: unknown): Projection {
  if (!isRecord(value) || (value.schema_version !== 1 && value.schema_version !== 2) || value.context !== 'GLOBAL' || value.data_state !== 'AVAILABLE' ||
    value.engagement_id !== null || value.run_id !== null || value.scope_revision_id !== null || value.through_cursor !== null ||
    !date(value.as_of) || value.limit !== 20 || typeof value.has_more !== 'boolean' ||
    !(value.next_page === null || isDashboardCursor(value.next_page)) || value.has_more !== (value.next_page !== null) ||
    !isRecord(value.data)) return invalid();
  const data = value.data;
  if (!integer(data.total_engagements) || !Array.isArray(data.items) || data.items.length > value.limit ||
    data.total_engagements < data.items.length ||
    (value.schema_version === 1 && (data.active_run !== null || data.run_state !== 'NOT_RUN')) ||
    data.attention_state !== 'UNAVAILABLE' || !isRecord(data.metrics)) return invalid();
  const version = value.schema_version;
  const items = data.items.map(item => summary(item, version));
  const active = decodeOptionalRun(data.active_run);
  const globalState = (['NOT_RUN', 'RUNNING', 'PAUSING', 'PAUSED', 'HOLD', 'STOPPING', 'NEEDS_RECONCILIATION'] as const).find(state => state === data.run_state);
  if (!globalState || globalState !== (active?.state ?? 'NOT_RUN')) return invalid();
  if (new Set(items.map(item => item.engagement_id)).size !== items.length) return invalid();
  return { schema_version: version, context: value.context, data_state: value.data_state, engagement_id: null,
    run_id: null, scope_revision_id: null, through_cursor: null, as_of: value.as_of, limit: value.limit,
    next_page: value.next_page, has_more: value.has_more,
    data: { total_engagements: data.total_engagements, items, active_run: active, run_state: globalState,
      attention_state: data.attention_state, metrics: { confirmed: metric(data.metrics.confirmed),
        coverage: metric(data.metrics.coverage), cost: metric(data.metrics.cost) } } };
}
