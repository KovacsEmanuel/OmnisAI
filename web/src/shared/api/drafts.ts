import type { components } from './generated';
import { ApiError, isRecord, isUuid } from './errors';

export type Draft = components['schemas']['EngagementDraft'];
export type Revision = components['schemas']['EngagementView'];
const invalid = (): never => { throw new ApiError('INVALID_RESPONSE'); };
const keys = (value: Record<string, unknown>, fields: string[]) =>
  Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
const record = (value: unknown, fields: string[]): value is Record<string, unknown> => isRecord(value) && keys(value, fields);
const integer = (value: unknown, min: number, max: number): value is number =>
  typeof value === 'number' && Number.isSafeInteger(value) && value >= min && value <= max;
const text = (value: unknown, min: number, max: number): value is string =>
  typeof value === 'string' && Array.from(value).length >= min && Array.from(value).length <= max &&
  !value.includes('\0') && !/[\uD800-\uDFFF]/u.test(value);
const oneOf = <T extends string>(value: unknown, options: readonly T[]): value is T =>
  typeof value === 'string' && options.some(option => option === value);
const list = <T>(value: unknown, min: number, max: number, item: (value: unknown) => value is T): value is T[] =>
  Array.isArray(value) && value.length >= min && value.length <= max && value.every(item);
const decision = (value: unknown): value is components['schemas']['DeclaredDecision'] => oneOf(value, ['ALLOW', 'DENY', 'UNKNOWN']);
const nullValue = (value: unknown): value is null => value === null;
const url = (value: unknown): value is string => {
  if (!text(value, 1, 2048)) return false;
  const authority = value.match(/^https?:\/\/([^/?#]*)/)?.[1];
  if (!authority || authority.endsWith(':') || authority.includes('@')) return false;
  try {
    const parsed = new URL(value);
    return ['http:', 'https:'].includes(parsed.protocol) && !parsed.username && !parsed.password && !parsed.hash &&
      (parsed.port === '' || Number(parsed.port) >= 1);
  } catch { return false; }
};
const origin = (value: unknown): value is string => {
  if (!text(value, 1, 255) || !/^https?:\/\/(?:\[[^\]]+\]|[^[:/?#@\]]+)$/.test(value)) return false;
  const authority = value.slice(value.indexOf('://') + 3);
  if (authority !== authority.toLowerCase() || !Array.from(authority).every(char => char.charCodeAt(0) >= 32 && char.charCodeAt(0) < 127)) return false;
  if (!authority.startsWith('[')) return true; // URL canonicalizes valid exact hosts; validate only IPv6 syntax.
  try { return !!new URL(value).hostname; } catch { return false; }
};
const path = (value: unknown): value is string => text(value, 1, 2048) && /^\/[^?#]*$/.test(value);
const authorization = (value: unknown): value is Draft['authorization'] =>
  record(value, ['owner', 'statement', 'valid_from', 'valid_until']) && text(value.owner, 1, 128) &&
  text(value.statement, 1, 4096) && typeof value.valid_from === 'string' && typeof value.valid_until === 'string' &&
  /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(value.valid_from) &&
  /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(value.valid_until);
const scope = (value: unknown): value is Draft['scope'][number] =>
  record(value, ['origin', 'port', 'path_prefix', 'exclusions', 'access']) && origin(value.origin) &&
  integer(value.port, 1, 65535) && path(value.path_prefix) && list(value.exclusions, 0, 32, path) &&
  oneOf(value.access, ['ATTACKABLE', 'VISIT_ONLY', 'BLOCKED']);
const constraint = (value: unknown): value is Draft['objective_constraints'][number] =>
  record(value, ['id', 'kind', 'text', 'operation_refs']) && isUuid(value.id) &&
  oneOf(value.kind, ['READ_ONLY', 'EXCLUDE_FEATURE', 'REQUIRE_CRITERION']) && text(value.text, 1, 1024) &&
  list(value.operation_refs, 0, 0, (_): _ is never => false);
const application = (value: unknown): value is Draft['application_context'] =>
  record(value, ['seed_urls', 'priority_workflows', 'test_objects', 'import_ref']) &&
  list(value.seed_urls, 0, 32, url) && list(value.priority_workflows, 0, 32, (s): s is string => text(s, 1, 1024)) &&
  list(value.test_objects, 0, 64, (s): s is string => text(s, 1, 1024)) && nullValue(value.import_ref);
const effect = (value: unknown): value is Draft['effect_rules'][number] =>
  record(value, ['effect_class', 'decision', 'note']) &&
  oneOf(value.effect_class, ['READ_ONLY_KNOWN', 'SESSION_CHANGE', 'LIMITED_WRITE', 'DESTRUCTIVE', 'UNKNOWN']) &&
  decision(value.decision) && text(value.note, 0, 1024);
const budgets = (value: unknown): value is Draft['budgets'] =>
  record(value, ['max_requests', 'max_duration_seconds', 'max_storage_bytes', 'validation_reserved_requests', 'max_model_calls']) &&
  integer(value.max_requests, 0, 100000) && integer(value.max_duration_seconds, 0, 86400) &&
  integer(value.max_storage_bytes, 0, 1073741824) && integer(value.validation_reserved_requests, 0, value.max_requests) &&
  integer(value.max_model_calls, 0, 10000);
const policy = (value: unknown): value is Draft['data_policy'] =>
  record(value, ['model_projection', 'research_egress', 'retention_days']) &&
  oneOf(value.model_projection, ['NONE', 'REDACTED']) && oneOf(value.research_egress, ['NONE', 'PUBLIC_FACTS']) &&
  integer(value.retention_days, 0, 365);
const matrix = (value: unknown): value is Draft['business_matrix'][number] =>
  record(value, ['id', 'principal', 'role', 'tenant', 'object', 'operation', 'expected', 'source', 'source_revision']) &&
  isUuid(value.id) && text(value.principal, 1, 128) && text(value.role, 1, 128) && text(value.tenant, 1, 128) &&
  text(value.object, 1, 256) && text(value.operation, 1, 128) && decision(value.expected) &&
  text(value.source, 1, 1024) && integer(value.source_revision, 1, 2147483647);
const common = ['name', 'authorization', 'scope', 'assessment_mode', 'objective_text', 'objective_constraints', 'workflow_profile_ref'];
const extended = ['application_context', 'effect_rules', 'budgets', 'data_policy', 'business_matrix', 'business_rules_ref'];
export const isFullDraft = (value: unknown): value is Draft =>
  record(value, [...common, ...extended]) && application(value.application_context) &&
  list(value.effect_rules, 0, 16, effect) && budgets(value.budgets) && policy(value.data_policy) &&
  list(value.business_matrix, 0, 64, matrix) && nullValue(value.business_rules_ref) && commonDraft(value);
function commonDraft(value: unknown): value is components['schemas']['LegacyEngagementDraft'] {
  return isRecord(value) && text(value.name, 1, 128) && authorization(value.authorization) && list(value.scope, 1, 64, scope) &&
    oneOf(value.assessment_mode, ['FULL_ASSESSMENT', 'FOCUSED_TEST']) && text(value.objective_text, 1, 8192) &&
    new TextEncoder().encode(value.objective_text).length <= 32768 &&
    list(value.objective_constraints, 0, 64, constraint) && nullValue(value.workflow_profile_ref);
}
export function decodeRevision(value: unknown, engagementId?: string): Revision {
  if (!record(value, ['schema_version', 'kind', 'id', 'engagement_id', 'revision', 'digest', 'created_at', 'payload']) ||
    value.schema_version !== 1 || value.kind !== 'engagement-revision' || !isUuid(value.id) ||
    !isUuid(value.engagement_id) || (engagementId && value.engagement_id !== engagementId) ||
    !integer(value.revision, 1, 2147483647) || typeof value.digest !== 'string' || !/^[0-9a-f]{64}$/.test(value.digest) ||
    typeof value.created_at !== 'string' || !Number.isFinite(Date.parse(value.created_at)) ||
    !(isFullDraft(value.payload) || (record(value.payload, common) && commonDraft(value.payload)))) return invalid();
  return { schema_version: 1, kind: 'engagement-revision', id: value.id, engagement_id: value.engagement_id,
    revision: value.revision, digest: value.digest, created_at: value.created_at, payload: value.payload };
}
