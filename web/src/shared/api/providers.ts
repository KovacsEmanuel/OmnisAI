import type { components } from './generated';
import { ApiError, isRecord, isUuid } from './errors';

export type ProviderView = components['schemas']['ProviderView'];
export type ProviderCommand = components['schemas']['ProviderCommand'];
export const requestedSelection = { provider: 'openai-codex', model: 'gpt-6.1-sol', effort: 'xhigh' } as const;
export function decodeProvider(value: unknown, operationId: string): ProviderView {
  if (!isRecord(value) || ![7, 9].includes(Object.keys(value).length) || value.operation_id !== operationId || !isUuid(operationId) ||
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
  const oauth = value.oauth ?? 'NONE';
  if (oauth !== 'NONE' && oauth !== 'STARTING' && oauth !== 'CHALLENGE' && oauth !== 'CANCELLING' && oauth !== 'CANCELLED' && oauth !== 'EXPIRED' && oauth !== 'SAVED' && oauth !== 'INDETERMINATE') throw new ApiError('INVALID_RESPONSE');
  const challenge = value.challenge ?? null;
  if (oauth === 'CHALLENGE') {
    if (status !== 'PENDING' || !isRecord(challenge) || Object.keys(challenge).length !== 2 || typeof challenge.code !== 'string' || !/^[A-Z0-9-]{4,32}$/.test(challenge.code) || challenge.url !== 'https://auth.openai.com/codex/device') throw new ApiError('INVALID_RESPONSE');
  } else if (challenge !== null) throw new ApiError('INVALID_RESPONSE');
  if (status !== 'PENDING' && status !== 'CONFIRMED' && status !== 'INDETERMINATE' && status !== 'BUSY' && status !== 'UNAVAILABLE') throw new ApiError('INVALID_RESPONSE');
  return { operation_id: operationId, status, selection: selected === null ? null : requestedSelection,
    configured: value.configured, authenticated, reachable: 'NOT_VERIFIED', inference_ready: false, oauth,
    challenge: isRecord(challenge) && typeof challenge.code === 'string' ? { code: challenge.code, url: 'https://auth.openai.com/codex/device' } : null };
}
