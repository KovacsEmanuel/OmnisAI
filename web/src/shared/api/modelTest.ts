import type { components } from './generated';
import { ApiError, isRecord, isUuid } from './errors';

export type ModelTestView = components['schemas']['ModelTestView'];
export function decodeModelTest(value: unknown): ModelTestView {
  if (!isRecord(value) ||
      (value.operation_id !== null && !isUuid(value.operation_id)) ||
      !['AVAILABLE', 'UNAVAILABLE', 'PENDING', 'COMPLETE', 'UNKNOWN', 'ERROR'].includes(String(value.status)) ||
      value.requested_provider !== 'openai-codex' || value.requested_model !== 'gpt-6.1-sol' || value.requested_effort !== 'xhigh' ||
      value.calls_limit !== 1 || value.wall_seconds !== 300 ||
      value.system_message !== 'Respond briefly to this synthetic model test. Use no tools.' ||
      value.user_message !== 'Map supplied structured synthetic records.') throw new ApiError('INVALID_RESPONSE');
  for (const key of ['observed_model', 'observed_effort', 'response_text', 'reason'] as const)
    if (value[key] !== null && typeof value[key] !== 'string') throw new ApiError('INVALID_RESPONSE');
  for (const key of ['input_tokens', 'output_tokens', 'reasoning_tokens', 'duration_ms'] as const)
    if (value[key] !== null && (!Number.isSafeInteger(value[key]) || Number(value[key]) < 0)) throw new ApiError('INVALID_RESPONSE');
  if (Object.keys(value).length !== 17 || (value.status === 'COMPLETE' && value.response_text === null)) throw new ApiError('INVALID_RESPONSE');
  // SAFETY: all 17 required keys, literals, nullable values and integer ranges were checked above.
  return value as ModelTestView;
}
