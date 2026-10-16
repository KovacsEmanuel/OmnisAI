import type { components } from './generated';
import { ApiError, isRecord, isUuid } from './errors';

export type ProviderView = components['schemas']['ProviderView'];
export type ProviderCommand = components['schemas']['ProviderCommand'];
export const requestedSelection = { provider: 'openai-codex', model: 'gpt-6.1-sol', effort: 'xhigh' } as const;
export function decodeProvider(value: unknown, operationId: string): ProviderView {
  if (!isRecord(value) || Object.keys(value).length !== 7 || value.operation_id !== operationId || !isUuid(operationId) ||
    !['PENDING', 'CONFIRMED', 'INDETERMINATE', 'BUSY', 'UNAVAILABLE'].includes(String(value.status)) ||
    value.reachable !== 'NOT_VERIFIED' || value.inference_ready !== false) throw new ApiError('INVALID_RESPONSE');
  const authenticated = value.authenticated;
  if (authenticated !== 'NOT_VERIFIED' && authenticated !== 'ABSENT' && authenticated !== 'LOCAL_PRESENT' && authenticated !== 'LOCAL_EXPIRED' && authenticated !== 'LOCAL_UNKNOWN') throw new ApiError('INVALID_RESPONSE');
  if (value.status !== 'CONFIRMED' && authenticated !== 'NOT_VERIFIED') throw new ApiError('INVALID_RESPONSE');
  const selected = value.selection;
  if (selected !== null && (!isRecord(selected) || Object.keys(selected).length !== 3 ||
    selected.provider !== requestedSelection.provider || selected.model !== requestedSelection.model || selected.effort !== requestedSelection.effort)) throw new ApiError('INVALID_RESPONSE');
  if (value.configured !== (value.status === 'CONFIRMED' && selected !== null) || (value.status !== 'CONFIRMED' && selected !== null)) throw new ApiError('INVALID_RESPONSE');
  const status = value.status;
  if (status !== 'PENDING' && status !== 'CONFIRMED' && status !== 'INDETERMINATE' && status !== 'BUSY' && status !== 'UNAVAILABLE') throw new ApiError('INVALID_RESPONSE');
  return { operation_id: operationId, status, selection: selected === null ? null : requestedSelection,
    configured: value.configured, authenticated, reachable: 'NOT_VERIFIED', inference_ready: false };
}
