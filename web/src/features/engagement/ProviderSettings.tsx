import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import { requestedSelection } from '../../shared/api/providers';
import type { ProviderCommand, ProviderView } from '../../shared/api/providers';
import { useSession } from '../bootstrap/BrowserSession';
import styles from './Engagement.module.css';
import formStyles from './Wizard.module.css';

export function ProviderSettings() {
  const { session, transition, readPrivate } = useSession();
  const [receipt, setReceipt] = useState<ProviderView | null>(null);
  const [operation, setOperation] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const started = useRef(0);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    if (transition !== 'idle' || session.isError || !session.data) controller.current?.abort();
  }, [transition, session.isError, session.data]);
  const status = useQuery({ queryKey: ['private', 'provider-operation', operation],
    queryFn: ({ signal }) => readPrivate(() => api.providerOperation(operation!, signal), signal),
    enabled: !!operation && receipt?.status === 'PENDING' && !uncertain && transition === 'idle' && !!session.data && !session.isError,
    retry: false, networkMode: 'always',
    refetchInterval: query => query.state.data?.status === 'PENDING' && Date.now() - started.current < 30000 ? 500 : false,
  });
  const observed = receipt?.status !== 'PENDING' ? receipt : status.data?.operation_id === operation ? status.data : receipt;
  const unknown = uncertain || (receipt?.status === 'PENDING' && status.isError) || observed?.status === 'INDETERMINATE' || observed?.status === 'UNAVAILABLE';
  const pending = sending || observed?.status === 'PENDING';
  const authReady = !!session.data && !session.isError && transition === 'idle';

  async function perform(action: ProviderCommand['action']) {
    if (!authReady || pending) return;
    const id = crypto.randomUUID();
    const abort = new AbortController();
    controller.current?.abort(); controller.current = abort;
    setOperation(id); setReceipt(null); setUncertain(false); setSending(true); started.current = Date.now();
    try {
      const value = await readPrivate(() => api.providerCommand({ operation_id: id, action,
        selection: action === 'save' ? requestedSelection : null }, session.data!.csrf_token, abort.signal), abort.signal);
      if (!abort.signal.aborted) setReceipt(value);
    } catch { if (!abort.signal.aborted) setUncertain(true); }
    finally { if (!abort.signal.aborted) setSending(false); }
  }
  async function recover() {
    if (!operation || !authReady || sending) return;
    const abort = new AbortController(); controller.current?.abort(); controller.current = abort;
    setSending(true);
    try {
      const value = await readPrivate(() => api.providerOperation(operation, abort.signal), abort.signal);
      if (!abort.signal.aborted) { setReceipt(value); setUncertain(false); }
    } catch { if (!abort.signal.aborted) setUncertain(true); }
    finally { if (!abort.signal.aborted) setSending(false); }
  }
  return <section className={styles.core} aria-labelledby="provider-heading">
    <h2 id="provider-heading">Provider configuration</h2>
    <p>Requested selection only. Model and effort compatibility have not been verified. Account connection is not available yet. Local grant reads never refresh credentials; local logout does not revoke the grant upstream. No inference is performed here.</p>
    <label className={formStyles.field}>Provider <select aria-label="Provider" defaultValue="openai-codex" disabled={pending}><option value="openai-codex">openai-codex</option></select></label>
    <label className={formStyles.field}>Model <select aria-label="Model" defaultValue="gpt-6.1-sol" disabled={pending}><option value="gpt-6.1-sol">gpt-6.1-sol</option></select></label>
    <label className={formStyles.field}>Effort <select aria-label="Effort" defaultValue="xhigh" disabled={pending}><option value="xhigh">xhigh</option></select></label>
    <p>Configured: {observed?.status === 'CONFIRMED' && !unknown ? (observed.configured ? 'yes — native readback' : 'no — native readback') : 'not confirmed'}</p>
    <p>Authenticated: not verified</p><p>Provider reachable: not verified</p><p>Inference ready: no</p>
    <p>Local grant: {unknown || observed?.status !== 'CONFIRMED' ? 'not confirmed' : observed.authenticated === 'ABSENT' ? 'absent — native readback' : observed.authenticated === 'LOCAL_PRESENT' ? 'present — not provider-verified' : observed.authenticated === 'LOCAL_EXPIRED' ? 'expired — local observation only' : observed.authenticated === 'LOCAL_UNKNOWN' ? 'unknown — no refresh attempted' : 'not checked'}</p>
    <output aria-live="polite">
      {unknown ? 'Outcome unknown. Do not repeat this action; recover the exact operation.' : pending ? 'Native operation pending; no success yet.' : observed?.status === 'BUSY' ? 'Runtime busy. Stop execution before changing Settings.' : observed?.status === 'CONFIRMED' ? 'Native readback confirmed.' : 'Read the native configuration before saving.'}
    </output>
    <div className={formStyles.actions}>
    <button type="button" onClick={() => void perform('read')} disabled={!authReady || pending}>Read native configuration</button>
    <button type="button" onClick={() => void perform('save')} disabled={!authReady || pending || unknown || observed?.status !== 'CONFIRMED' || observed.configured}>Save selection</button>
    <button type="button" onClick={() => void perform('auth_read')} disabled={!authReady || pending || unknown || !observed?.configured}>Read local Codex grant</button>
    <button type="button" onClick={() => void perform('logout')} disabled={!authReady || pending || unknown || !observed?.configured || observed.authenticated === 'NOT_VERIFIED' || observed.authenticated === 'ABSENT'}>Log out of Codex locally</button>
    {operation && (unknown || pending) && <button type="button" onClick={() => void recover()} disabled={!authReady || sending}>Recover exact operation</button>}
    </div>
  </section>;
}
