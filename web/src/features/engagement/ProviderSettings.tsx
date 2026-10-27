import { useEffect, useState } from 'react';
import { useSession } from '../bootstrap/BrowserSession';
import { sessionScope } from './SettingsModels';
import { SettingsModelsPage } from './SettingsModelsPage';

export function ProviderSettings() {
  const { session, transition } = useSession();
  const ready = !!session.data && !session.isError && transition === 'idle';
  const grant = session.data?.csrf_token;
  const [binding, setBinding] = useState<{ grant: string; scope: string | null } | null>(null);
  useEffect(() => {
    if (!grant) return;
    let active = true;
    void sessionScope(grant).then(
      scope => { if (active) setBinding({ grant, scope }); },
      () => { if (active) setBinding({ grant, scope: null }); },
    );
    return () => { active = false; };
  }, [grant]);
  // Unmount the old wizard and lifetime before the new grant's fingerprint resolves.
  const current = ready && binding?.grant === grant ? binding : null;
  return current?.scope ? <SettingsModelsPage key={current.scope} scope={current.scope} /> : <output>{current ? 'Session binding unavailable. No configuration action is admitted.' : 'Loading current settings…'}</output>;
}
