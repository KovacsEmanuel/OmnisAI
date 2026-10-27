import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import { ApiError, isUuid } from '../../shared/api/errors';
import type { KeyCommand, KeySettings } from '../../shared/api/providerKeys';
import type { CatalogView } from '../../shared/api/providerCatalog';
import type { SaveModels } from '../../shared/api/providerModels';
import type { EntryTestView } from '../../shared/api/modelTest';
import { useSession } from '../bootstrap/BrowserSession';
import { SettingsAssignments } from './SettingsAssignments';
import { SettingsModelWizard } from './SettingsModelWizard';
import { ModelTest } from './ModelTest';
import { catalogEvidence, catalogStorage, currentConnection, message, pendingStorage, providerName, readCatalogOperation, readLibrary, readPending, remember, remembered, testStorage, usable } from './SettingsModels';
import type { CatalogOperation, Connection, Evidence, Library, ModelEntry, Pending } from './SettingsModels';
import styles from './SettingsModels.module.css';

const definitive = (error: unknown) => error instanceof ApiError && ['REVISION_CONFLICT', 'CONNECTION_UNAVAILABLE', 'MODEL_NOT_REGISTERED', 'REGISTRY_FULL', 'CAPABILITIES_REQUIRED', 'OPERATION_ACTIVE', 'INVALID_INPUT', 'INVALID_CSRF', 'BODY_TOO_LARGE'].includes(error.code);
export function SettingsModelsPage({ scope }: { scope: string }) {
  const { session, readPrivate } = useSession();
  const client = useQueryClient();
  const [pending, setPending] = useState<Pending | null>(() => readPending(remembered(pendingStorage, scope)));
  const [catalogOperation, setCatalogOperation] = useState<CatalogOperation | null>(() => readCatalogOperation(remembered(catalogStorage, scope)));
  const [operation, setOperation] = useState<string | null>(() => { const id = remembered(testStorage, scope); return isUuid(id) ? id : null; });
  const [sending, setSending] = useState(false);
  const [reading, setReading] = useState(false);
  const [stale, setStale] = useState(false);
  const [notice, setNotice] = useState('');
  const [wizard, setWizard] = useState<{ id: number; provider: Connection['provider']; replace?: boolean; skipConnection?: boolean } | null>(null);
  const [testChoice, setTestChoice] = useState<ModelEntry | null>(null);
  const [consent, setConsent] = useState(false);
  const [testUnknown, setTestUnknown] = useState(false);
  const [catalogNotice, setCatalogNotice] = useState('');
  const [refusedTest, setRefusedTest] = useState<string | null>(() => { const value = remembered(testStorage + '-refused', scope); return isUuid(value) ? value : null; });
  const mutationBusy = useRef(false);
  const readController = useRef<AbortController | null>(null);
  const lifetime = useRef(new AbortController());
  const wizardGeneration = useRef(0);
  const addButton = useRef<HTMLButtonElement>(null);
  const testHeading = useRef<HTMLHeadingElement>(null);
  const [legacy] = useState(() => { try { return !!sessionStorage.getItem('omnis-model-test-operation') || !!sessionStorage.getItem('omnis-model-test-metadata'); } catch { return false; } });
  const queryKey = ['private', 'settings-model-library', scope];
  const authReady = !!session.data;
  async function load(signal: AbortSignal) {
    const settings = await api.providerKeys(null, signal);
    const library = await readLibrary(signal);
    const evidence: Record<string, Evidence> = {};
    let missingDetails = false;
    // Cached, local reads only. Batches bound local concurrency; no refresh on boot.
    for (let index = 0; index < library.entries.length; index += 4) {
      await Promise.all(library.entries.slice(index, index + 4).map(async entry => {
        if (!currentConnection(entry, settings)) return;
        try {
          const catalog = await api.providerCatalog({ action: 'search', connection_id: entry.connection_id, connection_revision: entry.connection_revision, query: entry.model, offset: 0, catalog_command_id: null }, session.data!.csrf_token, signal);
          const proof = catalogEvidence(catalog, entry); if (proof) evidence[entry.entry_id] = proof;
        } catch (error) { if (error instanceof ApiError && error.code === 'UNAUTHENTICATED') throw error; missingDetails = true; }
      }));
    }
    return { settings, library, evidence, missingDetails };
  }
  const current = useQuery({ queryKey, queryFn: ({ signal }) => readPrivate(() => load(signal), signal), retry: false, gcTime: 0,
    enabled: authReady && !sending && !pending && !stale, refetchOnWindowFocus: false, refetchOnReconnect: false, refetchOnMount: 'always' });
  const data = current.data;
  const testConnection = data?.settings.connections.find(item => item.connection_id === testChoice?.connection_id);
  const test = useQuery({ queryKey: ['private', 'settings-entry-test', scope, operation],
    queryFn: ({ signal }) => readPrivate(() => api.entryModelTest(operation!, signal), signal), enabled: authReady && !!operation,
    retry: false, gcTime: 0, refetchOnWindowFocus: false,
    refetchInterval: state => state.state.data?.state && !['FINISHED', 'NEEDS_RECONCILIATION'].includes(state.state.data.state) ? 750 : false });
  const observed = test.data;
  const activeTest = !!operation && (!observed || observed.state !== 'FINISHED' || testUnknown || test.isError);
  const blocked = !authReady || stale || (!!pending && !sending) || current.isError || !data;
  const busy = sending || reading || current.isFetching;
  useEffect(() => {
    const controller = new AbortController(); lifetime.current = controller;
    return () => { controller.abort(); readController.current?.abort(); wizardGeneration.current += 1; };
  }, []);
  function closeWizard(restore = true) { const inside = document.activeElement?.closest('[aria-label="Add models wizard"]'); wizardGeneration.current += 1; setWizard(null); if (restore && inside) addButton.current?.focus(); }
  function open(provider: Connection['provider'] = 'openrouter', replace = false, skipConnection = false) {
    if (blocked || sending) return;
    const id = ++wizardGeneration.current; setWizard({ id, provider, replace, skipConnection });
  }
  async function readCurrent(recover = false) {
    if (!authReady || reading || (pending && !recover)) return;
    setReading(true); const abort = new AbortController(); readController.current = abort;
    try {
      if (recover && pending) await readPrivate(async () => { if (pending.kind === 'keys') await api.providerKeys(pending.id, abort.signal); else await api.providerModels(pending.id, abort.signal); }, abort.signal);
      const value = await readPrivate(() => load(abort.signal), abort.signal);
      if (abort.signal.aborted || lifetime.current.signal.aborted) return;
      remember(pendingStorage, scope, null); setPending(null); setStale(false); client.setQueryData(queryKey, value);
      setNotice(recover ? 'Exact receipt recovered; current settings loaded. No catalog refresh or test was sent.' : 'Settings reloaded.');
    } catch (error) { if (!abort.signal.aborted && !lifetime.current.signal.aborted) setNotice(recover ? 'Receipt not confirmed. Do not repeat this command.' : message(error)); }
    finally { if (!lifetime.current.signal.aborted) setReading(false); }
  }
  async function mutate<T>(kind: Pending['kind'], id: string, send: () => Promise<T>): Promise<T | undefined> {
    if (blocked || reading || current.isFetching || mutationBusy.current) return;
    mutationBusy.current = true; setSending(true); setNotice(''); let submitted = false;
    try {
      remember(pendingStorage, scope, { kind, id }); setPending({ kind, id });
      await client.cancelQueries({ queryKey });
      if (lifetime.current.signal.aborted) return;
      submitted = true;
      const receipt = await readPrivate(send, lifetime.current.signal);
      // Read the exact durable receipt, independently of the mutation reply.
      await readPrivate(async () => { if (kind === 'keys') await api.providerKeys(id, lifetime.current.signal); else await api.providerModels(id, lifetime.current.signal); }, lifetime.current.signal);
      const value = await readPrivate(() => load(lifetime.current.signal), lifetime.current.signal);
      remember(pendingStorage, scope, null); setPending(null); client.setQueryData(queryKey, value);
      await client.invalidateQueries({ queryKey: ['private', 'model-test'] });
      setNotice('Saved locally.');
      return receipt;
    } catch (error) {
      if (lifetime.current.signal.aborted) return;
      if (!submitted || definitive(error)) {
        remember(pendingStorage, scope, null); setPending(null); setStale(true);
        setNotice(!submitted ? 'Command identity could not be retained. No save submitted.' : message(error));
      } else setNotice('Recover the exact receipt; no mutation retry is sent.');
    } finally { mutationBusy.current = false; if (!lifetime.current.signal.aborted) setSending(false); }
  }
  async function saveKeys(command: KeyCommand) {
    return mutate('keys', command.command_id, () => api.saveProviderKeys(command, session.data!.csrf_token, lifetime.current.signal));
  }
  async function refresh(connection: Connection): Promise<CatalogView | undefined> {
    if (blocked || mutationBusy.current || catalogOperation) { setCatalogNotice('Read the existing catalog operation before another refresh.'); return; }
    const operation = { id: crypto.randomUUID(), connection: connection.connection_id, revision: connection.revision };
    mutationBusy.current = true; setSending(true); setCatalogNotice('');
    try {
      remember(catalogStorage, scope, operation); setCatalogOperation(operation);
      const value = await readPrivate(() => api.refreshProviderCatalog({ action: 'refresh', command_id: operation.id, connection_id: operation.connection, connection_revision: operation.revision }, session.data!.csrf_token, lifetime.current.signal), lifetime.current.signal);
      if (value.state !== 'PENDING') { remember(catalogStorage, scope, null); setCatalogOperation(null); }
      setCatalogNotice(`Catalog ${value.state}.`); return value;
    } catch (error) { if (!lifetime.current.signal.aborted) { if (definitive(error)) { remember(catalogStorage, scope, null); setCatalogOperation(null); setStale(true); } setCatalogNotice(`Catalog outcome unknown. ${message(error)} Recover by reading the same catalog operation.`); } }
    finally { mutationBusy.current = false; if (!lifetime.current.signal.aborted) setSending(false); }
  }
  async function readCatalog(cancel = false) {
    if (!catalogOperation || !session.data) return;
    const snapshot = catalogOperation, signal = lifetime.current.signal;
    try {
      const value = await readPrivate(() => cancel ? api.cancelProviderCatalog({ action: 'cancel', connection_id: snapshot.connection, connection_revision: snapshot.revision, catalog_command_id: snapshot.id, command_id: crypto.randomUUID() }, session.data!.csrf_token, signal) : api.providerCatalog({ action: 'search', connection_id: snapshot.connection, connection_revision: snapshot.revision, catalog_command_id: snapshot.id, query: '', offset: 0 }, session.data!.csrf_token, signal), signal);
      setCatalogNotice(`Catalog ${value.state}${value.reason ? ' · ' + value.reason : ''}. No new refresh sent.`);
      if (value.state !== 'PENDING') { remember(catalogStorage, scope, null); setCatalogOperation(null); }
      await client.invalidateQueries({ queryKey: ['private', 'settings-catalog'] });
    } catch (error) { if (!signal.aborted) setCatalogNotice(`Catalog status unconfirmed. Keep operation ${snapshot.id}. ${message(error)}`); }
  }
  async function startTest(entry: ModelEntry, catalog: string) {
    if (!session.data || activeTest || mutationBusy.current || lifetime.current.signal.aborted) return;
    mutationBusy.current = true; setSending(true); setConsent(false); setNotice('');
    const id = crypto.randomUUID(); let submitted = false;
    try {
      remember(testStorage, scope, id); remember(testStorage + '-refused', scope, null); setRefusedTest(null); setOperation(id); setTestUnknown(false);
      submitted = true;
      const value = await readPrivate(() => api.startEntryModelTest({ operation_id: id, entry_id: entry.entry_id, expected_entry_revision: entry.revision, expected_connection_revision: entry.connection_revision, catalog_command_id: catalog, consent: true }, session.data!.csrf_token, lifetime.current.signal), lifetime.current.signal);
      client.setQueryData(['private', 'settings-entry-test', scope, id], value);
      setTestChoice(null);
    } catch (error) { if (!lifetime.current.signal.aborted) { setTestUnknown(submitted); if (definitive(error)) { remember(testStorage + '-refused', scope, id); setRefusedTest(id); } setNotice(submitted ? `Test outcome unconfirmed. Read the same operation. ${message(error)}` : 'Test identity could not be retained. No test submitted.'); } }
    finally { mutationBusy.current = false; if (!lifetime.current.signal.aborted) setSending(false); }
  }
  async function readTest(cancel = false) {
    if (!operation || !session.data) return;
    const id = operation, signal = lifetime.current.signal;
    try {
      const value = await readPrivate(() => cancel && observed?.state_revision ? api.cancelEntryModelTest(id, crypto.randomUUID(), observed.state_revision, session.data!.csrf_token, signal) : api.entryModelTest(id, signal), signal);
      client.setQueryData(['private', 'settings-entry-test', scope, id], value); setTestUnknown(false);
    } catch (error) {
      if (signal.aborted) return;
      if (!cancel && error instanceof ApiError && error.code === 'NOT_FOUND' && refusedTest === id) {
        remember(testStorage, scope, null); remember(testStorage + '-refused', scope, null); setOperation(null); setRefusedTest(null); setTestUnknown(false); setNotice('Test was not admitted. A new test requires new consent.');
      } else { setTestUnknown(true); setNotice('UNKNOWN — keep the same operation ID. No test was resent.'); }
    }
  }
  async function saveModels(payload: SaveModels, testIntent: { model: string; catalog: string } | null, generation: number) {
    const receipt = await mutate('models', payload.command_id, () => api.saveProviderModels(payload, session.data!.csrf_token, lifetime.current.signal));
    if (!receipt) return;
    const latest = client.getQueryData<{ library: Library }>(queryKey);
    const entries = latest?.library.entries.filter(item => payload.models.some(request => request.entry_id === item.entry_id && request.model === item.model && item.revision === request.expected_revision + 1 && item.output_tokens === request.output_tokens) && item.connection_id === payload.connection_id && item.connection_revision === payload.connection_revision) ?? [];
    if (entries.length !== payload.models.length) { setStale(true); setNotice('Saved entries do not match the requested revisions. Read current settings; no test was sent.'); return; }
    setNotice('Models saved. Assignments stay unchanged.');
    const target = entries.find(item => item.model === testIntent?.model);
    if (testIntent && target && generation === wizardGeneration.current) await startTest(target, testIntent.catalog);
    return entries;
  }
  return <>
    <div className={styles.heading}><h2>Models</h2><fieldset className={styles.headingActions} aria-label="Model library actions">
      <button type="button" className={pending || stale || current.isError ? undefined : styles.quiet} aria-label={pending ? undefined : 'Reload current settings'} disabled={!authReady} aria-disabled={reading} onClick={() => { if (!reading) void readCurrent(!!pending); }}>{pending ? 'Recover exact receipt' : stale || current.isError ? 'Reload current settings' : 'Reload'}</button>
      <button ref={addButton} type="button" disabled={blocked} aria-disabled={busy} onClick={() => { if (!busy) open(); }}>Add models</button>
    </fieldset></div>
    <output aria-live="polite" className={notice || pending || current.isError ? styles.notice : styles.hint}>{pending ? sending ? `Saving locally. Command ${pending.id}. No success confirmed.` : `Outcome unknown. Command ${pending.id}. Recover its exact receipt before another mutation.` : notice || (current.isError ? 'Read failed. Current settings are not confirmed.' : current.isFetching ? 'Loading current settings…' : '')}</output>
    {pending && notice && <p className={styles.notice}>{notice}</p>}
    {catalogOperation && <section className={styles.notice} aria-label="Catalog recovery"><p>Catalog operation {catalogOperation.id}. Pending or UNKNOWN; no automatic refresh.</p><button type="button" onClick={() => { void readCatalog(); }}>Read catalog status</button><button type="button" className={styles.secondary} onClick={() => { void readCatalog(true); }}>Cancel catalog</button></section>}
    {catalogNotice && <output className={styles.hint}>{catalogNotice}</output>}
    {data && <><section className={styles.panel} aria-label="Configured models"><div className={styles.core}>
      {data.settings.vault_status === 'LOCKED' && <output>Vault locked. Restore the local master key. Connections may still be disabled locally.</output>}
      {!data.library.entries.length && <p className={styles.hint}>No models configured.</p>}
      {data.settings.connections.map(connection => <section className={styles.connection} key={connection.connection_id} aria-label={providerName(connection.provider)}>
        <div className={styles.connectionHeading}><h3>{providerName(connection.provider)}</h3><small>{!connection.enabled ? 'Connection disabled' : connection.credential_present ? 'Key saved' : 'Key unavailable — vault locked'}</small>
          <button type="button" className={styles.secondary} disabled={blocked || !connection.enabled || !connection.credential_present} aria-disabled={busy} onClick={() => { if (!busy) open(connection.provider, false, true); }}>+ Add model</button>
          <details><summary>Connection options</summary><div className={styles.actions}><button type="button" className={styles.secondary} disabled={blocked || data.settings.vault_status === 'LOCKED'} onClick={() => open(connection.provider, true)}>{connection.enabled ? 'Replace key' : 'Reconnect'}</button><button type="button" className={styles.secondary} disabled={blocked || !connection.enabled} aria-disabled={sending} onClick={() => {
            if (sending || !window.confirm(`Disable ${providerName(connection.provider)}? Saved models and history remain. This does not revoke the upstream key.`)) return;
            if (wizard?.provider === connection.provider) closeWizard(false);
            setTestChoice(null); setConsent(false);
            void saveKeys({ action: 'revoke_connection', command_id: crypto.randomUUID(), connection_id: connection.connection_id, expected_revision: connection.revision });
          }}>Disable connection</button></div></details></div>
        <ul className={styles.list}>{data.library.entries.filter(entry => entry.connection_id === connection.connection_id).map(entry => <li className={styles.row} key={entry.entry_id}><div className={styles.identity}><strong>{data.evidence[entry.entry_id]?.model.name ?? entry.model}</strong><small className={styles.mono}>{entry.model}</small></div><span className={styles.state}>{entryStatus(entry, data.settings, data.evidence, observed)}</span><button type="button" className={styles.secondary} aria-label={`Test ${entry.model} via ${providerName(connection.provider)}`} disabled={blocked || activeTest || !usable(entry, data.settings, data.evidence)} aria-disabled={busy} onClick={() => { if (!busy) { setTestChoice(entry); setConsent(false); requestAnimationFrame(() => testHeading.current?.focus()); } }}>Test</button></li>)}</ul>
      </section>)}
      {data.missingDetails && <p className={styles.hint}>Some cached details could not be read. Those models are unavailable for assignments or testing; no fallback was selected.</p>}
      <details><summary>Test details</summary><p className={styles.hint}>One synthetic call / 300 seconds. No tools, target traffic, fallback or automatic retry. Provider charges may apply.</p><p className={styles.hint}>System: <span className={styles.mono}>Respond only with OMNIS_MODEL_TEST_OK. Use no tools.</span></p><p className={styles.hint}>User: <span className={styles.mono}>This is a synthetic local settings test. Reply with OMNIS_MODEL_TEST_OK.</span></p></details>
    </div></section>
      {wizard && <SettingsModelWizard key={wizard.id} settings={data.settings} library={data.library} provider={wizard.provider} replace={wizard.replace} skipConnection={wizard.skipConnection} blocked={blocked} working={sending} canTest={!activeTest} close={() => closeWizard()} refresh={refresh} saveKey={async (provider, connection, secret) => {
        const result = await saveKeys({ action: 'save_connection', command_id: crypto.randomUUID(), connection_id: connection?.connection_id ?? crypto.randomUUID(), expected_revision: connection?.revision ?? 0, provider, secret });
        const saved = result?.connections.find(item => item.provider === provider);
        const latest = client.getQueryData<{ settings: KeySettings }>(queryKey)?.settings.connections.find(item => item.provider === provider);
        if (saved && latest && saved.connection_id === latest.connection_id && saved.revision === latest.revision && latest.enabled && latest.credential_present) return latest;
        if (result) { setStale(true); setNotice('The connection changed after its receipt. Reload; no catalog refresh was sent.'); }
      }} saveModels={(payload, test) => saveModels(payload, test, wizard.id)} />}
      {testChoice && <section className={styles.panel} aria-label="Test consent"><div className={styles.core}><h2 tabIndex={-1} ref={testHeading}>Test model</h2><p>{testConnection ? providerName(testConnection.provider) : 'Unavailable connection'} · <span className={styles.mono}>{testChoice.model}</span></p><p>One fixed synthetic call / 300 seconds for this exact entry and connection revision. Provider charges may apply.</p><label className={styles.check}><input type="checkbox" checked={consent} disabled={blocked || activeTest} onChange={event => setConsent(event.target.checked)} />I approve the fixed input shown in Test details and one call for {testChoice.model}.</label><div className={styles.actions}><button type="button" className={styles.secondary} onClick={() => { setTestChoice(null); setConsent(false); }}>Cancel</button><button type="button" disabled={blocked || activeTest || !consent || !usable(testChoice, data.settings, data.evidence)} aria-disabled={sending} onClick={() => { const proof = data.evidence[testChoice.entry_id]; if (!sending && consent && proof) void startTest(testChoice, proof.catalog); }}>Send model test</button></div></div></section>}
      <SettingsAssignments settings={data.settings} library={data.library} evidence={data.evidence} blocked={blocked} working={busy} save={async command => !!await saveKeys(command)} />
    </>}
    {operation && <section className={styles.panel} aria-label="Model test operation"><div className={styles.core}>
      <h2>Model test</h2><p>{observed?.requested_provider ? providerName(observed.requested_provider) : 'Requested entry'} · {observed?.requested_model ?? 'Unconfirmed snapshot'} · {observed?.state ?? 'UNKNOWN'} · {observed?.result_state ?? 'NOT_VERIFIED'}{observed && !observed.current ? ' · Stale connection or entry revision' : ''}</p>
      {(testUnknown || test.isError || observed?.reason) && <p>{testUnknown || test.isError ? 'UNKNOWN — read the same operation. No automatic resend.' : observed?.reason}</p>}
      <div className={styles.actions}>{activeTest && <button type="button" disabled={!observed?.state_revision || observed.state === 'FINISHED'} onClick={() => { void readTest(true); }}>Cancel test</button>}<button type="button" className={styles.secondary} onClick={() => { void readTest(); }}>Read test status</button></div>
      {activeTest && <p className={styles.hint}>Cancel does not guarantee remote cancellation or a refund.</p>}
      <details><summary>Operation details</summary><p className={styles.mono}>Operation {operation}</p><p>Requested output cap: {observed?.requested_output_tokens ?? 'UNKNOWN'}. Observed model: {observed?.observed_model ?? 'UNKNOWN'}.</p><p aria-label="Model response" className={styles.mono}>{observed?.response_text ?? 'No output confirmed.'}</p><p>Usage {observed?.usage_state ?? 'UNKNOWN'} · input/output/reasoning {observed?.input_tokens ?? 'UNKNOWN'} / {observed?.output_tokens ?? 'UNKNOWN'} / {observed?.reasoning_tokens ?? 'UNKNOWN'} · Cost {observed?.cost_observed ?? 'UNKNOWN'}</p></details>
    </div></section>}
    {legacy && <ModelTest receiveOnly />}
  </>;
}
function entryStatus(entry: ModelEntry, settings: KeySettings, evidence: Record<string, Evidence>, test?: EntryTestView) {
  if (!currentConnection(entry, settings)) return 'Unavailable — stale or disabled connection';
  if (test?.entry_id === entry.entry_id && test.entry_revision === entry.revision && test.connection_revision === entry.connection_revision && test.current) return test.state === 'FINISHED' ? test.result_state === 'COMPLETED' ? 'Test passed' : test.result_state ?? 'UNKNOWN' : test.state ?? 'UNKNOWN';
  return usable(entry, settings, evidence) ? 'Not tested' : 'UNVERIFIED — details needed';
}
