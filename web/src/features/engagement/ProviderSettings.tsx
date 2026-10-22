import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import { ApiError, isUuid } from '../../shared/api/errors';
import { printable, roles } from '../../shared/api/providerKeys';
import type { KeyCommand, KeySelection, KeySettings } from '../../shared/api/providerKeys';
import { useSession } from '../bootstrap/BrowserSession';
import styles from './Engagement.module.css';
import formStyles from './Wizard.module.css';

const pendingKey = 'omnis-provider-settings-command';
function pendingCommand() {
  try { const id = sessionStorage.getItem(pendingKey); return isUuid(id) ? id : null; }
  catch { return null; }
}
export function ProviderSettings() {
  const { session, transition, readPrivate } = useSession();
  const client = useQueryClient();
  const [pending, setPending] = useState(pendingCommand);
  const [sending, setSending] = useState(false);
  const [stale, setStale] = useState(false);
  const [notice, setNotice] = useState('');
  const [provider, setProvider] = useState<'openrouter' | 'orcarouter'>('openrouter');
  const [validKey, setValidKey] = useState(false);
  const keyInput = useRef<HTMLInputElement>(null);
  const controller = useRef<AbortController | null>(null);
  const busy = useRef(false);
  const authReady = !!session.data && !session.isError && transition === 'idle';
  const queryKey = ['private', 'provider-keys'];
  const current = useQuery({ queryKey, queryFn: ({ signal }) => readPrivate(() => api.providerKeys(null, signal), signal),
    enabled: authReady && !sending && !pending && !stale, retry: false, gcTime: 0, networkMode: 'always',
    refetchOnWindowFocus: false, refetchOnReconnect: false, refetchOnMount: 'always' });
  useEffect(() => () => { controller.current?.abort(); if (keyInput.current) keyInput.current.value = ''; }, []);
  useEffect(() => {
    if (!authReady) { controller.current?.abort(); if (keyInput.current) keyInput.current.value = ''; setValidKey(false); }
  }, [authReady]);
  const view = current.data;
  const disabled = !authReady || sending || !!pending || stale || current.isError || current.isFetching || !view;
  const connection = view?.connections.find(item => item.provider === provider);
  async function reload(recover = false) {
    if (!authReady || busy.current || (pending && !recover)) return;
    busy.current = true; setSending(true);
    const abort = new AbortController(); controller.current = abort;
    try {
      if (recover && pending) await readPrivate(() => api.providerKeys(pending, abort.signal), abort.signal);
      const value = await readPrivate(() => api.providerKeys(null, abort.signal), abort.signal);
      if (abort.signal.aborted) return;
      sessionStorage.removeItem(pendingKey); setPending(null); setStale(false);
      client.setQueryData(queryKey, value); setNotice(recover ? 'Exact receipt recovered; current settings loaded.' : 'Current settings loaded.');
    } catch { if (!abort.signal.aborted) setNotice(recover ? 'Receipt not confirmed. Do not repeat this command.' : 'Read failed. Current settings are not confirmed.'); }
    finally { busy.current = false; if (!abort.signal.aborted) setSending(false); }
  }
  async function save(command: KeyCommand) {
    if (disabled || busy.current || !session.data) return;
    busy.current = true; setSending(true); setNotice('');
    const abort = new AbortController(); controller.current = abort;
    let submitted = false;
    try {
      // Only the non-secret ID survives reload; never retain the mutation payload.
      sessionStorage.setItem(pendingKey, command.command_id); setPending(command.command_id);
      await client.cancelQueries({ queryKey });
      submitted = true;
      await readPrivate(() => api.saveProviderKeys(command, session.data!.csrf_token, abort.signal), abort.signal);
      const value = await readPrivate(() => api.providerKeys(null, abort.signal), abort.signal);
      if (!abort.signal.aborted) { sessionStorage.removeItem(pendingKey); setPending(null); client.setQueryData(queryKey, value); setNotice('Saved locally; current settings loaded. No provider call performed.'); }
    } catch (error) {
      if (abort.signal.aborted) return;
      if (!submitted) { setPending(null); setStale(true); setNotice('Command ID could not be retained. No save submitted.'); }
      else if (error instanceof ApiError && ['REVISION_CONFLICT', 'CONNECTION_UNAVAILABLE', 'INVALID_INPUT', 'INVALID_CSRF', 'BODY_TOO_LARGE'].includes(error.code)) {
        sessionStorage.removeItem(pendingKey); setPending(null); setStale(true); setNotice(error.message);
      } else setNotice('Recovery is receive-only; no retry was sent.');
    } finally { busy.current = false; if (!abort.signal.aborted) setSending(false); }
  }
  function saveKey(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const secret = keyInput.current?.value ?? '';
    if (keyInput.current) keyInput.current.value = '';
    setValidKey(false);
    if (!printable(secret, 512) || disabled) return;
    void save({ action: 'save_connection', command_id: crypto.randomUUID(), connection_id: connection?.connection_id ?? crypto.randomUUID(),
      expected_revision: connection?.revision ?? 0, provider, secret });
  }
  return <section className={`${styles.core} ${styles.provider}`} aria-labelledby="provider-heading">
    <h2 id="provider-heading">Provider configuration</h2>
    <p>API keys are write-only. Save stores configuration locally; it never validates a provider or runs inference.</p>
    <p>Provider reachable: NOT_VERIFIED. Inference: NOT_VERIFIED.</p>
    <output aria-live="polite">{sending ? 'Operation pending; no success confirmed.' : pending ? `Outcome unknown. Command ${pending}. Recover its exact receipt before another mutation.` : notice || (current.isError ? 'Read failed. Current settings are not confirmed.' : !view ? 'Loading current settings…' : '')}</output>
    {notice && pending && !sending && <p>{notice}</p>}
    {view && <><p>Vault: {view.vault_status}</p>{view.connections.map(item => <p key={item.connection_id}>{item.provider}: {item.enabled ? 'configured' : 'revoked'} — credential {item.credential_present ? 'present' : 'absent'}</p>)}</>}
    <div className={`${formStyles.actions} ${styles.providerActions}`}>
      {pending ? <button type="button" disabled={!authReady || sending} onClick={() => void reload(true)}>Recover exact receipt</button> :
        <button type="button" disabled={!authReady || sending} onClick={() => void reload()}>Reload current settings</button>}
    </div>
    <form onSubmit={saveKey} autoComplete="off">
      <div className={styles.providerSelection}>
        <label className={formStyles.field}>Provider<select value={provider} disabled={disabled} onChange={event => { const value = event.target.value; if (value === 'openrouter' || value === 'orcarouter') setProvider(value); if (keyInput.current) keyInput.current.value = ''; setValidKey(false); }}><option value="openrouter">OpenRouter</option><option value="orcarouter">OrcaRouter</option></select></label>
        <label className={formStyles.field}>API key<input ref={keyInput} type="password" name="secret" autoComplete="new-password" spellCheck={false} maxLength={512} required pattern="[!-~]{1,512}" disabled={disabled || view?.vault_status === 'LOCKED'} onChange={event => setValidKey(printable(event.target.value, 512))} /></label>
      </div>
      <div className={`${formStyles.actions} ${styles.providerActions}`}>
        <button type="submit" disabled={disabled || !validKey || view?.vault_status === 'LOCKED'}>{connection ? 'Rotate API key' : 'Save API key'}</button>
        {connection?.enabled && <button type="button" disabled={disabled} onClick={() => void save({ action: 'revoke_connection', command_id: crypto.randomUUID(), connection_id: connection.connection_id, expected_revision: connection.revision })}>Revoke locally</button>}
      </div>
      <p className={styles.providerHint}>1–512 printable ASCII characters, no whitespace. Local revocation does not revoke the upstream key.</p>
    </form>
    {view && <SelectionForm key={JSON.stringify(view)} view={view} disabled={disabled} save={save} />}
  </section>;
}
function SelectionForm({ view, disabled, save }: { view: KeySettings; disabled: boolean; save: (command: KeyCommand) => Promise<void> }) {
  const [overrides, setOverrides] = useState({ brain: view.selection?.brain !== null && !!view.selection?.brain, investigator: !!view.selection?.investigator, validator: !!view.selection?.validator });
  const available = view.connections.filter(item => item.enabled && item.credential_present);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (disabled) return;
    const data = new FormData(event.currentTarget);
    function read(role: typeof roles[number]): KeySelection | null {
      if (role !== 'default' && !overrides[role]) return null;
      const connection = available.find(item => item.connection_id === data.get(`${role}-connection`));
      const model = data.get(`${role}-model`); const tokens = Number(data.get(`${role}-tokens`));
      if (!connection || typeof model !== 'string' || !printable(model, 256) || !Number.isSafeInteger(tokens) || tokens < 1 || tokens > 65536) throw new ApiError('INVALID_INPUT');
      return { connection_id: connection.connection_id, connection_revision: connection.revision, model, output_tokens: tokens };
    }
    const defaultSelection = read('default');
    if (defaultSelection) void save({ action: 'save_selection', command_id: crypto.randomUUID(), expected_revision: view.selection?.revision ?? 0,
      default: defaultSelection, brain: read('brain'), investigator: read('investigator'), validator: read('validator') });
  }
  return <form onSubmit={submit}>
    <h3>Model selection</h3>
    {roles.map(role => {
      const label = role[0]!.toUpperCase() + role.slice(1);
      const saved = view.selection?.[role]; const effective = saved ?? view.selection?.default;
      const stale = effective && !available.some(item => item.connection_id === effective.connection_id && item.revision === effective.connection_revision);
      const enabled = role === 'default' || overrides[role];
      return <fieldset key={role} disabled={disabled || !available.length}>
        <legend>{label}</legend>
        {role !== 'default' && <label><input type="checkbox" checked={overrides[role]} onChange={event => setOverrides({ ...overrides, [role]: event.target.checked })} />{label} override</label>}
        <p>{label} source: {saved ? (role === 'default' ? 'default' : 'override') : effective ? 'default' : 'not configured'}{effective ? ` — ${effective.connection_id} revision ${effective.connection_revision} · ${effective.model} · output ${effective.output_tokens}` : ''}{stale ? ' — stale or unavailable connection; save a new selection explicitly.' : ''}</p>
        {enabled && <div className={styles.providerSelection}>
          <label className={formStyles.field}>{label} connection<select name={`${role}-connection`} defaultValue={saved?.connection_id ?? ''} required><option value="" disabled>Choose connection</option>{available.map(item => <option key={item.connection_id} value={item.connection_id}>{item.provider} · revision {item.revision}</option>)}</select></label>
          <label className={formStyles.field}>{label} model<input name={`${role}-model`} defaultValue={saved?.model ?? ''} required maxLength={256} pattern="[!-~]{1,256}" /></label>
          <label className={formStyles.field}>{label} output tokens<input name={`${role}-tokens`} type="number" min={1} max={65536} step={1} required defaultValue={saved?.output_tokens ?? 128} /></label>
        </div>}
      </fieldset>;
    })}
    <div className={`${formStyles.actions} ${styles.providerActions}`}><button type="submit" disabled={disabled || !available.length}>Save model selection</button></div>
  </form>;
}
