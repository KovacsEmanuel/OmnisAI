import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import { requestedSelection } from '../../shared/api/providers';
import type { ProviderCommand, ProviderView } from '../../shared/api/providers';
import { useSession } from '../bootstrap/BrowserSession';
import styles from './Engagement.module.css';
import formStyles from './Wizard.module.css';

export function ProviderSettings() {
  const { session, transition, readPrivate } = useSession();
  const queryClient = useQueryClient();
  const [receipt, setReceipt] = useState<ProviderView | null>(null);
  const [operation, setOperation] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [uiExpired, setUiExpired] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const busy = useRef(false);
  const preparation = useRef<'read' | 'save' | null>(null);
  const started = useRef(Date.now());
  useEffect(() => () => { preparation.current = null; controller.current?.abort(); }, []);
  useEffect(() => {
    if (transition !== 'idle' || session.isError || !session.data) {
      preparation.current = null; controller.current?.abort();
    }
  }, [transition, session.isError, session.data]);
  const status = useQuery({ queryKey: ['private', 'provider-operation', operation],
    queryFn: ({ signal }) => readPrivate(() => api.providerOperation(operation ?? 'current', signal), signal),
    enabled: !sending && (!receipt || receipt.status === 'PENDING') && !uncertain && !uiExpired && transition === 'idle' && !!session.data && !session.isError,
    retry: false, networkMode: 'always', gcTime: 0, refetchIntervalInBackground: true,
    refetchInterval: query => query.state.data?.status === 'PENDING' && Date.now() - started.current < (query.state.data.oauth && query.state.data.oauth !== 'NONE' ? 900000 : 30000) ? 500 : false,
  });
  const observed = !receipt ? status.data : receipt.status !== 'PENDING' || (cancelling && status.data?.status === 'PENDING') ? receipt : status.data && (!operation || status.data.operation_id === operation) ? status.data : receipt;
  useEffect(() => {
    if (!operation && status.data && status.data.status !== 'CONFIRMED' && status.data.operation_id !== '00000000-0000-0000-0000-000000000000') {
      setOperation(status.data.operation_id); setReceipt(status.data);
    }
  }, [operation, status.data]);
  useEffect(() => {
    if (observed?.status !== 'PENDING' || uiExpired) return;
    const limit = observed.oauth && observed.oauth !== 'NONE' ? 900000 : 30000;
    const timer = setTimeout(() => setUiExpired(true), Math.max(0, limit - (Date.now() - started.current)));
    return () => clearTimeout(timer);
  }, [observed?.operation_id, observed?.status, observed?.oauth, sending, uiExpired]);
  useEffect(() => {
    if (receipt && receipt.status !== 'PENDING') queryClient.removeQueries({ queryKey: ['private', 'provider-operation'] });
  }, [receipt, queryClient]);
  const empty = !operation && observed?.operation_id === '00000000-0000-0000-0000-000000000000' && observed.status === 'UNAVAILABLE' && observed.oauth === 'NONE';
  const unknown = uncertain || uiExpired || ((!receipt || receipt.status === 'PENDING') && status.isError) || observed?.status === 'INDETERMINATE' || observed?.oauth === 'INDETERMINATE' || (observed?.status === 'UNAVAILABLE' && !empty);
  const pending = sending || observed?.status === 'PENDING';
  const authReady = !!session.data && !session.isError && transition === 'idle';

  // Only the preparation started by this click may advance; recovery clears it.
  useEffect(() => {
    if (!authReady || unknown || observed?.status === 'BUSY' || observed?.oauth === 'EXPIRED') {
      preparation.current = null; return;
    }
    if (sending || busy.current || !preparation.current || observed?.status !== 'CONFIRMED' || observed.operation_id !== operation) return;
    const step = preparation.current; preparation.current = null;
    if (observed.configured) void perform('connect', true);
    else if (step === 'read') { preparation.current = 'save'; void perform('save', true); }
  });

  async function perform(action: ProviderCommand['action'], continuing = false) {
    if (!authReady || sending || busy.current || (preparation.current && !continuing) || ((pending || (unknown && operation)) && action !== 'cancel')) return;
    if (action === 'connect' && !(observed?.status === 'CONFIRMED' && observed.configured && !unknown)) {
      preparation.current = 'read'; action = 'read';
    }
    if (action === 'cancel' || action === 'logout') preparation.current = null;
    const id = action === 'cancel' ? observed?.operation_id : crypto.randomUUID();
    if (!id) return;
    busy.current = true;
    const abort = new AbortController();
    controller.current?.abort(); controller.current = abort;
    setOperation(id); setReceipt(null); setUncertain(false); setUiExpired(false); setSending(true); setCancelling(action === 'cancel'); started.current = Date.now();
    try {
      const value = await readPrivate(() => api.providerCommand({ operation_id: id, action,
        selection: action === 'save' ? requestedSelection : null }, session.data!.csrf_token, abort.signal), abort.signal);
      if (!abort.signal.aborted) setReceipt(value);
    } catch { preparation.current = null; if (!abort.signal.aborted) setUncertain(true); }
    finally { busy.current = false; if (!abort.signal.aborted) setSending(false); }
  }
  async function recover() {
    if (!authReady || sending || busy.current) return;
    preparation.current = null; busy.current = true;
    const id = operation ?? observed?.operation_id ?? 'current';
    const abort = new AbortController(); controller.current?.abort(); controller.current = abort;
    setSending(true);
    try {
      const value = await readPrivate(() => api.providerOperation(id, abort.signal), abort.signal);
      if (!abort.signal.aborted) {
        setOperation(value.operation_id);
        queryClient.setQueryData(['private', 'provider-operation', value.operation_id], value);
        started.current = Date.now(); setUiExpired(false); setReceipt(value); setUncertain(false);
      }
    } catch { if (!abort.signal.aborted) setUncertain(true); }
    finally { busy.current = false; if (!abort.signal.aborted) setSending(false); }
  }
  return <section className={`${styles.core} ${styles.provider}`} aria-labelledby="provider-heading">
    <h2 id="provider-heading">Provider configuration</h2>

    <div className={styles.providerSelection}>
    <label className={formStyles.field}>Provider <select aria-label="Provider" defaultValue="openai-codex" disabled={pending}><option value="openai-codex">openai-codex</option></select></label>
    <label className={formStyles.field}>Model <select aria-label="Model" defaultValue="gpt-6.1-sol" disabled={pending}><option value="gpt-6.1-sol">gpt-6.1-sol</option></select></label>
    </div>
    <div className={`${formStyles.actions} ${styles.providerActions}`}>
    <button className={`${styles.providerConnect} withIcon`} type="button" onClick={() => void perform('connect')} disabled={!authReady || pending || unknown}>Connect Codex<span className="buttonIcon" aria-hidden="true"><svg viewBox="0 0 24 24" focusable="false"><path d="M5 12h14m-6-6 6 6-6 6" /></svg></span></button>
    </div>
    <div className={styles.providerFeedback}>
    <output aria-live="polite">
      {unknown ? 'Outcome unknown. Do not repeat this action; recover the exact operation.' : pending ? 'Native operation pending; no success yet.' : observed?.status === 'BUSY' ? 'Runtime busy. Stop execution before changing Settings.' : observed?.oauth === 'SAVED' ? 'Authorization saved locally; model not tested.' : observed?.oauth === 'EXPIRED' ? 'Authorization expired; model not tested. Connect again explicitly.' : observed?.authenticated === 'LOCAL_PRESENT' ? 'Local authorization present; model not tested.' : observed?.authenticated === 'LOCAL_EXPIRED' ? 'Local authorization expired; model not tested.' : observed?.authenticated === 'LOCAL_UNKNOWN' ? 'Local authorization unknown; model not tested.' : observed?.configured ? 'Selection saved; model not tested.' : 'Choose provider and model, then Connect. Model not tested.'}
    </output>
    {authReady && !unknown && !cancelling && observed?.status === 'PENDING' && observed.oauth === 'CHALLENGE' && observed.challenge && <div>
      <p>Enter this code only on the Codex authorization page: <code>{observed.challenge.code}</code></p>
      <a href="https://auth.openai.com/codex/device" target="_blank" rel="noreferrer noopener">Open Codex device authorization</a>
    </div>}
    {observed?.oauth === 'CANCELLED' && <p>Connection cancelled and worker settled. Existing grants were not deleted.</p>}
    </div>
    <div className={`${formStyles.actions} ${styles.providerActions}`}>
    {pending && observed?.oauth && observed.oauth !== 'NONE' && <button type="button" onClick={() => void perform('cancel')} disabled={!authReady || sending || cancelling || observed.oauth === 'CANCELLING'}>Cancel connection</button>}
    {(observed?.oauth === 'SAVED' || observed?.authenticated === 'LOCAL_PRESENT' || observed?.authenticated === 'LOCAL_EXPIRED') && <button type="button" onClick={() => void perform('logout')} disabled={!authReady || pending || unknown}>Log out of Codex locally</button>}
    {(unknown || pending) && <button type="button" onClick={() => void recover()} disabled={!authReady || sending}>Recover exact operation</button>}
    </div>
    <div className={styles.providerSafety}><p>Local reads never refresh credentials.</p><p>Cancel does not log out. Local logout does not revoke upstream access.</p></div>
    <details className={styles.providerInstructions}><summary>Diagnostic</summary>
    <p className={styles.providerHint}>Model and effort compatibility are not verified. No inference is performed here.</p>
    <p>Requested effort: {requestedSelection.effort}. Readback effort: {observed?.status === 'CONFIRMED' && !unknown ? observed.selection?.effort ?? 'not configured' : 'not confirmed'}.</p>
    <div className={styles.providerStates}>
    <p>Configured: {observed?.status === 'CONFIRMED' && !unknown ? (observed.configured ? 'yes — native readback' : 'no — native readback') : 'not confirmed'}</p>
    <p>Authenticated: not verified</p><p>Provider reachable: not verified</p><p>Inference ready: no</p>
    <p>Local grant: {unknown || observed?.status !== 'CONFIRMED' ? 'not confirmed' : observed.authenticated === 'ABSENT' ? 'absent — native readback' : observed.authenticated === 'LOCAL_PRESENT' ? 'present — not provider-verified' : observed.authenticated === 'LOCAL_EXPIRED' ? 'expired — local observation only' : observed.authenticated === 'LOCAL_UNKNOWN' ? 'unknown — no refresh attempted' : 'not checked'}</p>
    </div>
    <div className={`${formStyles.actions} ${styles.providerActions}`}>
    <button type="button" onClick={() => void perform('read')} disabled={!authReady || pending || (unknown && !!operation)}>Read native configuration</button>
    <button type="button" onClick={() => void perform('save')} disabled={!authReady || pending || unknown || observed?.status !== 'CONFIRMED' || observed.configured}>Save selection</button>
    <button type="button" onClick={() => void perform('auth_read')} disabled={!authReady || pending || unknown || !observed?.configured}>Read local Codex grant</button>
    </div>
    <p>Connect starts the native Codex device flow. Open the fixed authorization link yourself in the web browser.</p>
    </details>
  </section>;
}
