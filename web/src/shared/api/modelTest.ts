import type { components } from './generated';
import { ApiError, isRecord, isUuid } from './errors';

export type ModelTestView = components['schemas']['ModelTestView'];
function text(value: unknown): string | null {
  if (value === null || typeof value === 'string') return value;
  throw new ApiError('INVALID_RESPONSE');
}
function integer(value: unknown, minimum = 0, maximum = Number.MAX_SAFE_INTEGER): number | null {
  if (value === null) return null;
  if (typeof value === 'number' && Number.isSafeInteger(value) && value >= minimum && value <= maximum) return value;
  throw new ApiError('INVALID_RESPONSE');
}
function oneOf<const T extends string>(value: unknown, allowed: readonly T[]): T {
  const result = allowed.find(item => item === value);
  if (result === undefined) throw new ApiError('INVALID_RESPONSE');
  return result;
}
export function decodeModelTest(value: unknown): ModelTestView {
  if (!isRecord(value) || value.schema_version !== 2 || value.calls_limit !== 1 || value.wall_seconds !== 300 ||
      value.system_message !== 'Respond only with OMNIS_MODEL_TEST_OK. Use no tools.' ||
      value.user_message !== 'This is a synthetic local settings test. Reply with OMNIS_MODEL_TEST_OK.' ||
      (value.operation_id !== null && !isUuid(value.operation_id)) ||
      (value.metadata_command_id !== null && !isUuid(value.metadata_command_id))) throw new ApiError('INVALID_RESPONSE');
  const result: ModelTestView = {
    schema_version: 2, operation_id: value.operation_id, metadata_command_id: value.metadata_command_id,
    state: value.state === null ? null : oneOf(value.state, ['PENDING', 'RUNNING', 'STOPPING', 'FINISHED', 'NEEDS_RECONCILIATION']),
    state_revision: integer(value.state_revision, 1), finish_reason: text(value.finish_reason),
    selection_revision: integer(value.selection_revision, 1),
    metadata_state: oneOf(value.metadata_state, ['NOT_REQUESTED', 'PENDING', 'READY', 'FAILED']), reason: text(value.reason),
    requested_provider: value.requested_provider === null ? null : oneOf(value.requested_provider, ['openrouter', 'orcarouter']),
    requested_model: text(value.requested_model), requested_output_tokens: integer(value.requested_output_tokens, 1, 65536),
    observed_model: text(value.observed_model), provider_status: text(value.provider_status),
    result_state: value.result_state === null ? null : oneOf(value.result_state, ['NOT_SENT', 'COMPLETED', 'INCOMPLETE', 'FAILED', 'UNKNOWN']),
    output_state: oneOf(value.output_state, ['COMPLETE', 'TRUNCATED', 'ABSENT']), response_text: text(value.response_text),
    usage_state: oneOf(value.usage_state, ['KNOWN', 'PARTIAL', 'UNKNOWN']), input_tokens: integer(value.input_tokens),
    output_tokens: integer(value.output_tokens), reasoning_tokens: integer(value.reasoning_tokens), cost_observed: text(value.cost_observed),
    system_message: value.system_message, user_message: value.user_message, calls_limit: 1, wall_seconds: 300,
  };
  if (Object.keys(value).length !== Object.keys(result).length ||
      (result.response_text !== null && new TextEncoder().encode(result.response_text).length > 8192) ||
      ((result.operation_id === null) !== (result.state === null)) ||
      (result.state === 'FINISHED' && result.result_state === null)) throw new ApiError('INVALID_RESPONSE');
  return result;
}

export type EntryTestView = components['schemas']['EntryTestView'];
export type EntryTestRequest = components['schemas']['EntryTestRequest'];
export function decodeEntryTest(value: unknown, operationId: string): EntryTestView {
  if (!isRecord(value)) throw new ApiError('INVALID_RESPONSE');
  const { entry_id, entry_revision, connection_id, connection_revision, current, ...legacy } = value;
  const decoded = decodeModelTest(legacy);
  const entryRevision = integer(entry_revision, 1), connectionRevision = integer(connection_revision, 1);
  if (decoded.operation_id !== operationId || !isUuid(decoded.operation_id) || !isUuid(entry_id) || !isUuid(connection_id) ||
      entryRevision === null || connectionRevision === null || typeof current !== 'boolean' ||
      decoded.requested_provider == null || decoded.requested_output_tokens == null || decoded.state_revision == null ||
      decoded.selection_revision !== null || decoded.metadata_command_id !== null || decoded.metadata_state !== 'NOT_REQUESTED' ||
      typeof decoded.requested_model !== 'string' || decoded.requested_model.length < 1 || decoded.requested_model.length > 256 || /[^!-~]/.test(decoded.requested_model) ||
      (decoded.observed_model != null && Array.from(decoded.observed_model).length > 256) ||
      [decoded.reason, decoded.finish_reason].some(item => item != null && (item.length > 64 || !/^[A-Z_]+$/.test(item))) ||
      (decoded.provider_status != null && !/^[0-9]{3}$/.test(decoded.provider_status)) ||
      (decoded.cost_observed != null && decoded.cost_observed.length > 128)) throw new ApiError('INVALID_RESPONSE');
  return { ...decoded, entry_id, entry_revision: entryRevision, connection_id, connection_revision: connectionRevision, current };
}
