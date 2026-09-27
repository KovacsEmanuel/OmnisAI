import type { components, paths } from './generated';
import { ApiError, decodeError, isRecord } from './errors';
import { decodeHealth, decodeInstance } from './decoders';

type Session = components['schemas']['SessionView'];
type ApiPath = keyof paths;

async function request(path: ApiPath, init: RequestInit = {}, signal?: AbortSignal): Promise<Response> {
  try {
    return await fetch(path, {
      ...init, credentials: 'same-origin', cache: 'no-store', redirect: 'error',
      signal: AbortSignal.any([AbortSignal.timeout(12000), ...(signal ? [signal] : [])]),
    });
  } catch {
    throw new ApiError('API_UNAVAILABLE');
  }
}

async function body(response: Response): Promise<unknown> {
  try {
    const value: unknown = await response.json();
    return value;
  } catch {
    throw new ApiError('INVALID_RESPONSE');
  }
}

async function sessionResponse(response: Response): Promise<Session> {
  const value = await body(response);
  if (!response.ok) throw decodeError(value);
  if (!isRecord(value) || value.authenticated !== true || typeof value.csrf_token !== 'string' || !/^[0-9a-f]{64}$/.test(value.csrf_token)) {
    throw new ApiError('INVALID_RESPONSE');
  }
  return { authenticated: true, csrf_token: value.csrf_token };
}

export const api = {
  async health(signal?: AbortSignal) {
    const response = await request('/health/ready', {}, signal);
    const value = await body(response);
    if (response.status !== 200 && response.status !== 503) throw decodeError(value);
    return decodeHealth(value);
  },
  async instance(signal?: AbortSignal) {
    const response = await request('/api/instance', {}, signal);
    const value = await body(response);
    if (!response.ok) throw decodeError(value);
    return decodeInstance(value);
  },
  async session(signal?: AbortSignal): Promise<Session | null> {
    try {
      return await sessionResponse(await request('/api/session', {}, signal));
    } catch (error) {
      if (error instanceof ApiError && error.code === 'UNAUTHENTICATED') return null;
      throw error;
    }
  },
  async pair(code: string): Promise<Session> {
    const payload: components['schemas']['PairingBody'] = { code };
    return sessionResponse(await request('/api/pairing', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    }));
  },
  async logout(csrf: string): Promise<void> {
    const response = await request('/api/logout', { method: 'POST', headers: { 'X-CSRF-Token': csrf } });
    if (response.status === 204) return;
    if (!response.ok) throw decodeError(await body(response));
    throw new ApiError('INVALID_RESPONSE');
  },
};
