import type { components } from './generated';

export type ErrorCode = components['schemas']['ErrorCode'] | 'API_UNAVAILABLE' | 'INVALID_RESPONSE';

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
  NOT_FOUND: 'This operation is not available in the installed API.',
  METHOD_NOT_ALLOWED: 'This operation is not supported.',
  HTTP_ERROR: 'The API refused the request.',
  INTERNAL_ERROR: 'The API failed. No success was confirmed.',
  WEB_UNAVAILABLE: 'The installed web build is missing or incompatible.',
  API_UNAVAILABLE: 'The API could not be reached. Check the local service and retry explicitly.',
  INVALID_RESPONSE: 'The API response is incompatible. No state was accepted.',
};

export class ApiError extends Error {
  constructor(readonly code: ErrorCode, readonly correlation?: string) {
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

export function decodeError(value: unknown): ApiError {
  if (isRecord(value) && isRecord(value.error) && isErrorCode(value.error.code) && isUuid(value.error.correlation_id)) {
    return new ApiError(value.error.code, value.error.correlation_id);
  }
  return new ApiError('INVALID_RESPONSE');
}
