import { createContext, useContext, useEffect } from 'react';
import type { ReactNode } from 'react';
import { useBrowserSession } from './useBrowserSession';
import { bindDiagnostics, observeControl } from '../../shared/uiDiagnostics';

const BrowserSessionContext = createContext<ReturnType<typeof useBrowserSession> | null>(null);
export function BrowserSessionProvider({ children }: { children: ReactNode }) {
  const state = useBrowserSession();
  useEffect(() => {
    if (!state.session.data || state.session.isError || state.transition !== 'idle') return;
    const controller = new AbortController();
    const detach = bindDiagnostics(state.session.data.csrf_token, send => state.commitPrivate(send, controller.signal), controller.signal);
    observeControl('navigation');
    return () => { controller.abort(); detach(); };
  }, [state.session.data, state.session.isError, state.transition, state.commitPrivate]);
  return <BrowserSessionContext.Provider value={state}>{children}</BrowserSessionContext.Provider>;
}
export function useSession() {
  const state = useContext(BrowserSessionContext);
  if (!state) throw new Error('Browser session provider is missing');
  return state;
}
