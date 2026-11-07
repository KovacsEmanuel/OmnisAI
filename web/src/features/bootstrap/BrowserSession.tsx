import { createContext, useContext, useEffect } from 'react';
import type { ReactNode } from 'react';
import { useBrowserSession } from './useBrowserSession';
import { bindDiagnostics, observeControl } from '../../shared/uiDiagnostics';

const BrowserSessionContext = createContext<ReturnType<typeof useBrowserSession> | null>(null);
export function BrowserSessionProvider({ children }: { children: ReactNode }) {
  const state = useBrowserSession();
  const { session, transition, commitPrivate } = state;
  useEffect(() => {
    if (!session.data || session.isError || transition !== 'idle') return;
    const controller = new AbortController();
    const detach = bindDiagnostics(session.data.csrf_token, send => commitPrivate(send, controller.signal), controller.signal);
    observeControl('navigation');
    return () => { controller.abort(); detach(); };
  }, [session.data, session.isError, transition, commitPrivate]);
  return <BrowserSessionContext.Provider value={state}>{children}</BrowserSessionContext.Provider>;
}
export function useSession() {
  const state = useContext(BrowserSessionContext);
  if (!state) throw new Error('Browser session provider is missing');
  return state;
}
