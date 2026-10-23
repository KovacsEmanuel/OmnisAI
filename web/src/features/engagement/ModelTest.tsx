import { useId, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import { ApiError, isUuid } from '../../shared/api/errors';
import { useSession } from '../bootstrap/BrowserSession';
import styles from './Engagement.module.css';

const storage = 'omnis-model-test-operation';
const metadataStorage = 'omnis-model-test-metadata';
function remembered(key = storage) {
  try { const id = sessionStorage.getItem(key); return isUuid(id) ? id : null; }
  catch { return null; }
}
export function ModelTest() {
  const { session, transition, readPrivate } = useSession();
  const client = useQueryClient();
  const [operation, setOperation] = useState(remembered);
  const [metadataCommand, setMetadataCommand] = useState(() => remembered(metadataStorage));
  const [sending, setSending] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [consent, setConsent] = useState(false);
  const [notice, setNotice] = useState('');
  const busy = useRef(false);
  const gateHintId = useId();
  const key = ['private', 'model-test', operation, metadataCommand];
  const authReady = !!session.data && !session.isError && transition === 'idle';
  const query = useQuery({ queryKey: key,
    queryFn: ({ signal }) => readPrivate(async () => {
      if (metadataCommand) {
        const receipt = await api.modelCapabilities(metadataCommand, signal);
        if (receipt.metadata_state === 'PENDING') return receipt;
      }
      return api.modelTest(signal, operation);
    }, signal),
    enabled: authReady && !sending, retry: false, placeholderData: previous => previous,
    refetchInterval: query => (query.state.data?.state && query.state.data.state !== 'FINISHED') || query.state.data?.metadata_state === 'PENDING' ? 1000 : false,
    refetchOnWindowFocus: false });
  const observed = query.data;
  const active = !!observed?.state && observed.state !== 'FINISHED';
  const hardDisabled = !authReady || query.isError || !observed || uncertain;
  const working = sending || query.isFetching;
  const canStart = !hardDisabled && !working && !active && observed?.metadata_state === 'READY' && !!observed.selection_revision && consent;
  const gateHint = hardDisabled || active || sending ? null
    : !observed?.selection_revision ? 'Testul nu poate fi trimis: selecția implicită nu este salvată. Configurează și salvează selecția implicită în Settings → Providers (Save model selection), apoi apasă „Refresh model metadata”.'
    : observed.metadata_state === 'PENDING' ? 'Metadatele modelului se încarcă. Așteaptă starea READY înainte de a trimite testul; nu repeta Refresh.'
    : observed.metadata_state !== 'READY' ? 'Testul nu poate fi trimis: metadatele modelului nu sunt READY. Apasă „Refresh model metadata” și așteaptă starea READY înainte de a trimite testul.'
    : null;
  async function mutate(action: 'start' | 'refresh' | 'cancel') {
    if (busy.current || !session.data || !authReady || !observed || working) return;
    if (action === 'start' && !canStart) return;
    if (action === 'refresh' && (active || !observed.selection_revision || uncertain)) return;
    if (action === 'cancel' && (!active || !observed.operation_id || !observed.state_revision)) return;
    busy.current = true; setSending(true); setNotice('');
    let identity = operation;
    let metadataIdentity = metadataCommand;
    try {
      let value;
      if (action === 'start' && observed.selection_revision) {
        identity = crypto.randomUUID();
        // Store only identity before sending; reload and lost replies never repeat a mutation.
        sessionStorage.removeItem(storage + '-refused');
        sessionStorage.setItem(storage, identity); setOperation(identity);
        sessionStorage.removeItem(metadataStorage); setMetadataCommand(null); metadataIdentity = null;
        value = await api.startModelTest(identity, observed.selection_revision, session.data.csrf_token);
        setConsent(false);
      } else if (action === 'refresh' && observed.selection_revision) {
        const current = await api.modelTest();
        if (!current.selection_revision) throw new ApiError('INVALID_RESPONSE');
        metadataIdentity = crypto.randomUUID();
        sessionStorage.removeItem(metadataStorage + '-refused');
        sessionStorage.setItem(metadataStorage, metadataIdentity); setMetadataCommand(metadataIdentity);
        value = await api.refreshModelCapabilities(metadataIdentity, current.selection_revision, session.data.csrf_token);
      } else if (observed.operation_id && observed.state_revision) {
        value = await api.cancelModelTest(observed.operation_id, crypto.randomUUID(), observed.state_revision, session.data.csrf_token);
      }
      if (value) client.setQueryData(['private', 'model-test', identity, metadataIdentity], value);
    } catch (error) {
      setConsent(false);
      setUncertain(true);
      if (action !== 'cancel' && error instanceof ApiError && ['REVISION_CONFLICT', 'CONNECTION_UNAVAILABLE', 'CAPABILITIES_REQUIRED', 'OPERATION_ACTIVE', 'INVALID_INPUT', 'INVALID_CSRF', 'BODY_TOO_LARGE'].includes(error.code)) {
        const refused = action === 'start' ? identity : metadataIdentity;
        if (refused) sessionStorage.setItem((action === 'start' ? storage : metadataStorage) + '-refused', refused);
      }
      setNotice(error instanceof ApiError ? error.message : 'UNKNOWN — read the same operation. Do not resend.');
    } finally { busy.current = false; setSending(false); }
  }
  async function read() {
    if (!authReady || busy.current) return;
    busy.current = true; setSending(true);
    try {
      const result = await query.refetch();
      const pointer = metadataCommand ? metadataStorage : storage;
      const identity = metadataCommand ?? operation;
      if (result.error instanceof ApiError && result.error.code === 'NOT_FOUND' && identity && remembered(pointer + '-refused') === identity) {
        // Clear only a known refused ID, after its exact absence and current state are confirmed.
        const current = await readPrivate(() => api.modelTest(undefined, metadataCommand ? operation : null), new AbortController().signal);
        sessionStorage.removeItem(pointer); sessionStorage.removeItem(pointer + '-refused');
        if (metadataCommand) setMetadataCommand(null); else setOperation(null);
        client.setQueryData(['private', 'model-test', metadataCommand ? operation : null, null], current);
        setUncertain(false); setConsent(false); setNotice('Not admitted. Current state loaded; a new test requires new consent.');
      } else if (!result.error && result.data && (!result.data.state || result.data.state === 'FINISHED')) setUncertain(false);
    } catch { setNotice('Current state not confirmed. Keep the same ID; do not resend.'); }
    finally { busy.current = false; setSending(false); }
  }
  return <section className={styles.panel} aria-label="Test model"><div className={styles.core}>
    <h2>Test model</h2>
    <p>Mesaj sintetic fix · 1 apel / 300s · fără tools sau trafic către țintă.</p>
    <p>System: <span className={styles.objective}>{observed?.system_message ?? 'Respond only with OMNIS_MODEL_TEST_OK. Use no tools.'}</span></p>
    <p>User: <span className={styles.objective}>{observed?.user_message ?? 'This is a synthetic local settings test. Reply with OMNIS_MODEL_TEST_OK.'}</span></p>
    <p>Metadata: {observed?.metadata_state ?? 'UNKNOWN'} · Saved selection revision: {observed?.selection_revision ?? 'UNKNOWN'}</p>
    <p>Cerut: {observed?.requested_provider ?? 'saved default'} / {observed?.requested_model ?? 'saved default'} / output cap {observed?.requested_output_tokens ?? 'saved default'}</p>
    <p>Operation: {observed?.operation_id ?? operation ?? 'none'} · {observed?.state ?? 'not started'}</p>
    <output aria-live="polite">{sending ? 'În curs…' : notice || (query.isError ? 'UNKNOWN — read the same operation; no resend.' : `${observed?.result_state ?? 'NOT_VERIFIED'} ${observed?.reason ?? ''}`)}</output>
    <label><input type="checkbox" checked={consent} disabled={hardDisabled || active} aria-disabled={working} onChange={event => { if (!working) setConsent(event.target.checked); }} /> I approve this fixed synthetic input and one finite call using the saved default.</label>
    {gateHint && <p id={gateHintId} className={styles.providerHint}>{gateHint}</p>}
    <div className={styles.providerActions}>
      <button aria-describedby={gateHint ? gateHintId : undefined} disabled={hardDisabled || active || !observed?.selection_revision} aria-disabled={working || observed?.metadata_state === 'PENDING'} onClick={() => { void mutate('refresh'); }}>Refresh model metadata</button>
      <button aria-describedby={gateHint ? gateHintId : undefined} disabled={hardDisabled || active || !consent || observed?.metadata_state !== 'READY'} aria-disabled={working} onClick={() => { void mutate('start'); }}>Trimite testul modelului</button>
      <button disabled={!authReady || !active} aria-disabled={working} onClick={() => { void mutate('cancel'); }}>Cancel test</button>
      <button disabled={!authReady} aria-disabled={working} onClick={() => { if (!working) void read(); }}>Citește starea testului</button>
    </div>
    {observed?.response_text !== null && observed?.response_text !== undefined && <p className={styles.objective} aria-label="Răspuns model">{observed.response_text}</p>}
    <p>Observat: {observed?.observed_model ?? 'UNKNOWN'} · Provider: {observed?.provider_status ?? 'UNKNOWN'} · Output: {observed?.output_state ?? 'ABSENT'}</p>
    <p>Usage {observed?.usage_state ?? 'UNKNOWN'} input/output/reasoning: {observed?.input_tokens ?? 'UNKNOWN'} / {observed?.output_tokens ?? 'UNKNOWN'} / {observed?.reasoning_tokens ?? 'UNKNOWN'} · Cost: {observed?.cost_observed ?? 'UNKNOWN'}</p>
    <p className={styles.providerHint}>Stop drains local operations. Cancel is not a remote cancellation or a refund. Reload only reads; a new test always requires another explicit consent and action.</p>
  </div></section>;
}
