import { useCallback, useEffect, useRef, useState } from 'react';
import { CancelledError, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import { ApiError } from '../../shared/api/errors';
import { copy } from './copy';

type Transition = 'idle' | 'pairing' | 'logout';

// Single browser-auth writer. Query cancellation plus an epoch fences direct readbacks too.
export function useBrowserSession() {
  const client = useQueryClient();
  const epoch = useRef(0);
  const phase = useRef<Transition>('idle');
  const hadSession = useRef(false);
  const [transition, setTransition] = useState<Transition>('idle');
  const [notice, setNotice] = useState<string | null>(null);
  const [logoutError, setLogoutError] = useState<unknown>(null);
  const session = useQuery({
    queryKey: ['session'],
    queryFn: async ({ signal }) => {
      const observed = epoch.current;
      const result = await api.session(signal);
      if (observed !== epoch.current) throw new CancelledError({ silent: true });
      return result;
    },
    enabled: transition === 'idle', retry: false, refetchInterval: 15000,
  });

  const expire = useCallback(() => {
    epoch.current += 1;
    phase.current = 'idle';
    setTransition('idle');
    hadSession.current = false;
    void client.cancelQueries({ queryKey: ['session'] });
    void client.cancelQueries({ queryKey: ['instance'] });
    client.setQueryData(['session'], null);
    client.removeQueries({ queryKey: ['instance'] });
    setNotice(copy.expired);
  }, [client]);

  useEffect(() => {
    if (session.data) hadSession.current = true;
    else if (session.data === null && hadSession.current) expire();
  }, [session.data, expire]);
  useEffect(() => () => { epoch.current += 1; }, []);

  async function begin(next: Exclude<Transition, 'idle'>) {
    if (phase.current !== 'idle') throw new Error('AUTH_OPERATION_PENDING');
    const operation = ++epoch.current;
    phase.current = next;
    setTransition(next);
    await client.cancelQueries({ queryKey: ['session'] });
    await client.cancelQueries({ queryKey: ['instance'] });
    return operation;
  }

  function finish(operation: number) {
    if (operation === epoch.current) {
      phase.current = 'idle';
      setTransition('idle');
    }
  }

  async function pair(code: string) {
    const operation = await begin('pairing');
    try {
      if (operation !== epoch.current) return;
      const grant = await api.pair(code);
      if (operation !== epoch.current) return;
      const readback = await api.session();
      if (operation !== epoch.current) return;
      if (readback === null) throw new ApiError('UNAUTHENTICATED');
      if (readback.csrf_token !== grant.csrf_token) throw new ApiError('INVALID_RESPONSE');
      hadSession.current = true;
      setNotice(null);
      setLogoutError(null);
      client.setQueryData(['session'], readback);
    } catch (error) {
      if (operation === epoch.current) throw error;
    } finally {
      finish(operation);
    }
  }

  async function logout() {
    if (!session.data || phase.current !== 'idle') return;
    const csrf = session.data.csrf_token;
    const operation = await begin('logout');
    setLogoutError(null);
    try {
      if (operation !== epoch.current) return;
      await api.logout(csrf);
      if (operation !== epoch.current) return;
      const readback = await api.session();
      if (operation !== epoch.current) return;
      if (readback !== null) throw new Error('LOGOUT_UNCONFIRMED');
      hadSession.current = false;
      client.setQueryData(['session'], null);
      client.removeQueries({ queryKey: ['instance'] });
      setNotice(copy.loggedOut);
    } catch (error) {
      if (operation === epoch.current) setLogoutError(error);
    } finally {
      finish(operation);
    }
  }

  return { session, transition, notice, logoutError, pair, logout, expire };
}
