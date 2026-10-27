import { useQuery } from '@tanstack/react-query';
import { useSession } from '../bootstrap/BrowserSession';
import { sessionScope } from './SettingsModels';
import { SettingsModelsPage } from './SettingsModelsPage';

export function ProviderSettings() {
  const { session, transition, readPrivate } = useSession();
  const ready = !!session.data && !session.isError && transition === 'idle';
  const scope = useQuery({ queryKey: ['private', 'settings-session-scope'],
    queryFn: ({ signal }) => readPrivate(() => sessionScope(session.data!.csrf_token), signal),
    enabled: ready, retry: false, gcTime: 0, refetchOnWindowFocus: false });
  return ready && scope.data ? <SettingsModelsPage key={scope.data} scope={scope.data} /> : <output>{scope.isError ? 'Session binding unavailable. No configuration action is admitted.' : 'Loading current settings…'}</output>;
}
