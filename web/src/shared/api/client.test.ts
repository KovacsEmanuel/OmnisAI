import { describe, expect, it, vi } from 'vitest';
import { api } from './client';

const session = { authenticated: true, csrf_token: 'a'.repeat(64) };
const correlation = '00000000-0000-4000-8000-000000000001';

function respond(payload: unknown, status = 200) {
  return vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(payload), {
    status, headers: { 'Content-Type': 'application/json' },
  }));
}

describe('Omnis HTTP boundary', () => {
  it('exchanges a code in POST body only, without persistence or automatic retries', async () => {
    const fetcher = respond(session);
    vi.stubGlobal('fetch', fetcher);
    expect(await api.pair('synthetic-one-use-code')).toEqual(session);
    expect(fetcher).toHaveBeenCalledOnce();
    expect(fetcher).toHaveBeenCalledWith('/api/pairing', expect.objectContaining({
      method: 'POST', body: JSON.stringify({ code: 'synthetic-one-use-code' }),
      credentials: 'same-origin', cache: 'no-store', redirect: 'error',
    }));
    expect(localStorage.length + sessionStorage.length).toBe(0);
  });

  it('treats an expired session as unauthenticated, not empty success', async () => {
    vi.stubGlobal('fetch', respond({ error: { code: 'UNAUTHENTICATED', correlation_id: correlation } }, 401));
    expect(await api.session()).toBeNull();
  });

  it.each([null, { authenticated: true, csrf_token: 1 }, { authenticated: false, csrf_token: 'a'.repeat(64) }])(
    'rejects malformed session data without type assertions (%j)', async payload => {
      vi.stubGlobal('fetch', respond(payload));
      await expect(api.session()).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
    },
  );

  it('does not log or reflect a network exception', async () => {
    const fetcher = vi.fn<typeof fetch>().mockRejectedValue(new Error('synthetic-secret-marker'));
    vi.stubGlobal('fetch', fetcher);
    await expect(api.session()).rejects.toMatchObject({ code: 'API_UNAVAILABLE' });
    await expect(api.session()).rejects.not.toThrow('synthetic-secret-marker');
  });

  it('requires a valid error envelope and keeps its correlation', async () => {
    vi.stubGlobal('fetch', respond({ error: { code: 'PAIRING_DENIED', correlation_id: correlation } }, 401));
    await expect(api.pair('synthetic-code')).rejects.toMatchObject({ code: 'PAIRING_DENIED', correlation });
  });

  it('sends logout CSRF only in its header and accepts only 204', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal('fetch', fetcher);
    await api.logout(session.csrf_token);
    expect(fetcher).toHaveBeenCalledWith('/api/logout', expect.objectContaining({
      method: 'POST', headers: { 'X-CSRF-Token': session.csrf_token },
    }));
    fetcher.mockResolvedValue(new Response('{}', { status: 200 }));
    await expect(api.logout(session.csrf_token)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });

  it('preserves explicit unavailable health, including a real 503 health payload', async () => {
    const health = { api_ready: false, dashboard_ready: false, assessment_ready: false,
      reason: 'DATABASE_UNAVAILABLE', dashboard_reason: 'DATABASE_UNAVAILABLE' };
    vi.stubGlobal('fetch', respond(health, 503));
    expect(await api.health()).toEqual(health);
  });

  it('validates instance identity and generation without coercion or fake defaults', async () => {
    const instance = { instance_id: correlation, generation: 1, admission_open: false,
      shutdown_command_id: null, quiesced_generation: null, supervisor_epoch: 1,
      supervisor_ready: true, shutdown_finalized: false, assessment_ready: false, dashboard_ready: true };
    const fetcher = respond(instance);
    vi.stubGlobal('fetch', fetcher);
    expect(await api.instance()).toEqual(instance);
    fetcher.mockResolvedValue(new Response(JSON.stringify({ ...instance, generation: '1' })));
    await expect(api.instance()).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
    fetcher.mockResolvedValue(new Response(JSON.stringify({ ...instance, generation: Number.MAX_SAFE_INTEGER + 1 })));
    await expect(api.instance()).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });
});
