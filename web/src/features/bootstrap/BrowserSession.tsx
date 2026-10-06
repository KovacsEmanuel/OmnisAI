import { createContext, useContext } from 'react';
import type { ReactNode } from 'react';
import { useBrowserSession } from './useBrowserSession';

const BrowserSessionContext = createContext<ReturnType<typeof useBrowserSession> | null>(null);
export function BrowserSessionProvider({ children }: { children: ReactNode }) {
  const state = useBrowserSession();
  return <BrowserSessionContext.Provider value={state}>{children}</BrowserSessionContext.Provider>;
}
export function useSession() {
  const state = useContext(BrowserSessionContext);
  if (!state) throw new Error('Browser session provider is missing');
  return state;
}
