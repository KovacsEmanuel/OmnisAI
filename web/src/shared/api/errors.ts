import type { components } from './generated';

export type ErrorCode = components['schemas']['ErrorCode'] | 'API_UNAVAILABLE' | 'INVALID_RESPONSE';
export type FieldError = components['schemas']['FieldError'];

export const errorCopy: Record<ErrorCode, string> = {
  INVALID_HOST: 'The local Host was refused. Open the configured loopback address.',
  INVALID_ORIGIN: 'The request origin was refused. Use the local Omnis page.',
  QUERY_NOT_ALLOWED: 'This request does not accept URL parameters.',
  BODY_TOO_LARGE: 'The request is too large.',
  UNAUTHENTICATED: 'Your session expired or was revoked. Pair this browser again.',
  CONTROL_UNAVAILABLE: 'The database or control plane is unavailable. No success was confirmed.',
  INVALID_CSRF: 'The session verification failed. Refresh the session before trying again.',
  CONTROL_TIMEOUT: 'The control operation timed out. Its outcome may be uncertain; check the session before retrying.',
  PAIRING_DENIED: 'Pairing refused. The code is invalid, expired or already used. Request a new local code.',
  PAIRING_RATE_LIMITED: 'Too many attempts. Wait at least 60 seconds before trying again.',
  INVALID_INPUT: 'Check the pairing code format and try again.',
  ENGAGEMENT_CONFLICT: 'This draft changed in another tab. Reload before saving; local edits were not overwritten.',
  NOT_FOUND: 'This operation is not available in the installed API.',
  METHOD_NOT_ALLOWED: 'This operation is not supported.',
  HTTP_ERROR: 'The API refused the request.',
  INTERNAL_ERROR: 'The API failed. No success was confirmed.',
  WEB_UNAVAILABLE: 'The installed web build is missing or incompatible.',
  API_UNAVAILABLE: 'The API could not be reached. Check the local service and retry explicitly.',
  INVALID_RESPONSE: 'The API response is incompatible. No state was accepted.',
};

export class ApiError extends Error {
  constructor(readonly code: ErrorCode, readonly correlation?: string, readonly fieldErrors: FieldError[] = []) {
    super(errorCopy[code]);
    this.name = 'ApiError';
  }
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function isUuid(value: unknown): value is string {
  return typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value);
}

function isErrorCode(value: unknown): value is ErrorCode {
  return typeof value === 'string' && Object.hasOwn(errorCopy, value);
}

const fields = new Set(['body', 'name', 'assessment_mode', 'objective_text', 'workflow_profile_ref',
  'business_rules_ref', 'scope', 'authorization', 'objective_constraints', 'application_context',
  'effect_rules', 'budgets', 'data_policy', 'business_matrix', 'if-match', 'x-command-id']);
const children: Record<string, Set<string>> = {
  authorization: new Set(['owner', 'statement', 'valid_from', 'valid_until']),
  scope: new Set(['origin', 'port', 'path_prefix', 'exclusions', 'access']),
  objective_constraints: new Set(['id', 'kind', 'text', 'operation_refs']),
  application_context: new Set(['seed_urls', 'priority_workflows', 'test_objects', 'import_ref']),
  effect_rules: new Set(['effect_class', 'decision', 'note']),
  budgets: new Set(['max_requests', 'max_duration_seconds', 'max_storage_bytes', 'validation_reserved_requests', 'max_model_calls']),
  data_policy: new Set(['model_projection', 'research_egress', 'retention_days']),
  business_matrix: new Set(['id', 'principal', 'role', 'tenant', 'object', 'operation', 'expected', 'source', 'source_revision']),
};
const indexed = new Set(['scope', 'objective_constraints', 'effect_rules', 'business_matrix']);
const listChildren: Record<string, Set<string>> = {
  scope: new Set(['exclusions']),
  objective_constraints: new Set(['operation_refs']),
  application_context: new Set(['seed_urls', 'priority_workflows', 'test_objects']),
};
const validIndex = (value: string) => /^(0|[1-9][0-9]?)$/.test(value) && Number(value) <= 64;
const isField = (field: unknown): field is string => {
  if (typeof field !== 'string' || field.length > 96) return false;
  const [root, ...rest] = field.split('.');
  if (!root || !fields.has(root)) return false;
  if (indexed.has(root) && rest.length && validIndex(rest[0] ?? '')) rest.shift();
  if (!rest.length) return true;
  if (!children[root]?.has(rest[0] ?? '')) return false;
  return rest.length === 1 || (rest.length === 2 && !!listChildren[root]?.has(rest[0] ?? '') && validIndex(rest[1] ?? ''));
};
const codes = new Set(['REQUIRED', 'INVALID_VALUE', 'TOO_LONG', 'TOO_MANY', 'UNKNOWN_FIELD']);
const isFieldError = (item: unknown): item is FieldError =>
  isRecord(item) && Object.keys(item).length === 2 && isField(item.field) &&
  typeof item.code === 'string' && codes.has(item.code);

export function decodeError(value: unknown): ApiError {
  if (isRecord(value) && isRecord(value.error) && isErrorCode(value.error.code) && isUuid(value.error.correlation_id)) {
    const raw = value.error.field_errors ?? [];
    if (!Array.isArray(raw) || raw.length > 16 || !raw.every(isFieldError)) {
      return new ApiError('INVALID_RESPONSE');
    }
    return new ApiError(value.error.code, value.error.correlation_id, raw);
  }
  return new ApiError('INVALID_RESPONSE');
}
