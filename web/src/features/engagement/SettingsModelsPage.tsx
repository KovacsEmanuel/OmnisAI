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
import { availabilityIssue, catalogEvidence, catalogStorage, currentConnection, exactCheck, message, pendingStorage, providerName, readCatalogOperation, readLibrary, readPending, remember, remembered, testStorage, usable } from './SettingsModels';
import type { CatalogOperation, CatalogRead, Connection, EntryCheck, Evidence, ModelEntry, Pending } from './SettingsModels';
import styles from './SettingsModels.module.css';

const definitive = (error: unknown) => error instanceof ApiError && ['REVISION_CONFLICT', 'CONNECTION_UNAVAILABLE', 'MODEL_NOT_REGISTERED', 'REGISTRY_FULL', 'CAPABILITIES_REQUIRED', 'OPERATION_ACTIVE', 'INVALID_INPUT', 'INVALID_CSRF', 'BODY_TOO_LARGE'].includes(error.code);
const confirmations = ['Key saved.', 'Connection disabled.', 'Assignments saved. Applies to future runs only.', 'Settings reloaded.', 'Models saved. Assignments stay unchanged.', 'Models connected.', 'Exact receipt recovered; current settings loaded. No catalog refresh or test was sent.', 'Test was not admitted. A new test requires new consent.'];
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
  const [notification, setNotification] = useState('');
  const [wizard, setWizard] = useState<{ id: number; provider: Connection['provider']; replace?: boolean } | null>(null);
  const [testChoice, setTestChoice] = useState<ModelEntry | null>(null);
  const [consent, setConsent] = useState(false);
  const [testGeneration, setTestGeneration] = useState<number | null>(null);
  const [testUnknown, setTestUnknown] = useState(false);
  const [testNotice, setTestNotice] = useState('');
  const [operationEntry, setOperationEntry] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string[]>([]);
  const [catalogNotice, setCatalogNotice] = useState<{ connection: string; text: string; detail: string } | null>(null);
  const [refusedTest, setRefusedTest] = useState<string | null>(() => { const value = remembered(testStorage + '-refused', scope); return isUuid(value) ? value : null; });
  const mutationBusy = useRef(false);
  const readController = useRef<AbortController | null>(null);
  const lifetime = useRef(new AbortController());
  const wizardGeneration = useRef(0);
  const continuation = useRef<AbortController | null>(null);
  const [connecting, setConnecting] = useState(false);
  const addButton = useRef<HTMLButtonElement>(null);
  const feedback = useRef<HTMLElement>(null);
  const testHeading = useRef<HTMLHeadingElement>(null);
  const [legacy] = useState(() => { try { return !!sessionStorage.getItem('omnis-model-test-operation') || !!sessionStorage.getItem('omnis-model-test-metadata'); } catch { return false; } });
  const queryKey = ['private', 'settings-model-library', scope];
  const authReady = !!session.data;
  async function load(signal: AbortSignal) {
    let instance: Awaited<ReturnType<typeof api.instance>> | null = null;
    try { instance = await api.instance(signal); }
    catch (error) { if (signal.aborted || !(error instanceof ApiError) || error.code === 'UNAUTHENTICATED') throw error; }
    const settings = await api.providerKeys(null, signal);
    const library = await readLibrary(signal);
    const evidence: Record<string, Evidence> = {};
    const checks: Record<string, EntryCheck> = {};
    const catalogs: Record<string, CatalogRead> = {};
    // Cached, local reads only. Batches bound local concurrency; no refresh on boot.
    for (let index = 0; index < library.entries.length; index += 4) {
      signal.throwIfAborted();
      await Promise.all(library.entries.slice(index, index + 4).map(async entry => {
        try { checks[entry.entry_id] = await api.latestEntryModelTest(entry.entry_id, signal); }
        catch (error) { if (signal.aborted || (error instanceof ApiError && error.code === 'UNAUTHENTICATED')) throw error; checks[entry.entry_id] = error instanceof ApiError && error.code === 'NOT_FOUND' ? null : 'UNKNOWN'; }
        signal.throwIfAborted();
        if (!currentConnection(entry, settings)) return;
        try {
          const catalog = await api.providerCatalog({ action: 'search', connection_id: entry.connection_id, connection_revision: entry.connection_revision, query: entry.model, offset: 0, catalog_command_id: null }, session.data!.csrf_token, signal);
          catalogs[entry.entry_id] = catalog;
          const proof = catalogEvidence(catalog, entry); if (proof) evidence[entry.entry_id] = proof;
        } catch (error) { if (signal.aborted || (error instanceof ApiError && error.code === 'UNAUTHENTICATED')) throw error; catalogs[entry.entry_id] = { code: error instanceof ApiError ? error.code : 'API_UNAVAILABLE' }; }
      }));
    }
    const generation = instance?.admission_open && instance.supervisor_ready && !instance.shutdown_finalized && instance.shutdown_command_id === null ? instance.generation : null;
    return { generation, settings, library, evidence, checks, catalogs };
  }
  const current = useQuery({ queryKey, queryFn: ({ signal }) => readPrivate(() => load(signal), signal), retry: false, gcTime: 0,
    enabled: authReady, refetchOnWindowFocus: false, refetchOnReconnect: false, refetchOnMount: 'always' });
  const data = current.data;
  const generation = data?.generation ?? null;
  const testConnection = data?.settings.connections.find(item => item.connection_id === testChoice?.connection_id);
  const test = useQuery({ queryKey: ['private', 'settings-entry-test', scope, operation],
    queryFn: ({ signal }) => readPrivate(() => api.entryModelTest(operation!, signal), signal), enabled: authReady && !!operation && !sending && !connecting,
    retry: false, gcTime: 0, refetchOnWindowFocus: false,
    refetchInterval: state => state.state.data?.state && !['FINISHED', 'NEEDS_RECONCILIATION'].includes(state.state.data.state) ? 750 : false });
  const observed = test.data;
  const canCancel = !!observed?.state_revision && observed.state !== 'FINISHED';
  const operationEntryId = observed?.entry_id ?? operationEntry ?? data?.library.entries.find(entry => { const check = data.checks[entry.entry_id]; return check && check !== 'UNKNOWN' && check.operation_id === operation; })?.entry_id;
  const operationInList = data?.library.entries.some(entry => entry.entry_id === operationEntryId);
  const operationPending = !!operation && (!observed || observed.state !== 'FINISHED' || observed.result_state === 'UNKNOWN' || testUnknown || test.isError);
  const activeTest = connecting || operationPending || Object.values(data?.checks ?? {}).some(check => check && check !== 'UNKNOWN' && check.state !== 'FINISHED');
  const blocked = !authReady || stale || (!!pending && !sending) || current.isError || !data;
  const busy = sending || reading || current.isFetching;
  // Fresh tabs recover the admitted operation from the existing latest-entry projection, never from consent.
  useEffect(() => {
    if (operationPending || sending || connecting) return;
    const active = Object.values(data?.checks ?? {}).find(check => check && check !== 'UNKNOWN' && (check.state !== 'FINISHED' || check.result_state === 'UNKNOWN'));
    if (active && active !== 'UNKNOWN') {
      client.setQueryData(['private', 'settings-entry-test', scope, active.operation_id], active);
      setOperation(active.operation_id ?? null);
    }
  }, [data, operationPending, sending, connecting, client, scope]);
  useEffect(() => {
    const controller = new AbortController(); lifetime.current = controller;
    return () => { controller.abort(); continuation.current?.abort(); readController.current?.abort(); wizardGeneration.current += 1; };
  }, []);
  useEffect(() => {
    if (!notice) { setNotification(''); return; }
    setNotification(confirmations.includes(notice) ? notice : 'Settings need attention.');
    const timer = window.setTimeout(() => setNotification(''), 5000); return () => window.clearTimeout(timer);
  }, [notice]);
  useEffect(() => {
    if (!notification) return;
    // A passive confirmation yields to controls and keyboard focus, including on narrow screens.
    const place = () => {
      const node = feedback.current;
      if (!node) return;
      const rect = node.getBoundingClientRect();
      const overlaps = [...document.querySelectorAll('button, input, select, summary, a, :focus, [role="alert"]')].some(target => {
        if (node.contains(target)) return false;
        const box = target.getBoundingClientRect();
        return box.width > 0 && box.height > 0 && rect.left < box.right + 4 && rect.right > box.left - 4 && rect.top < box.bottom + 4 && rect.bottom > box.top - 4;
      });
      node.style.visibility = overlaps ? 'hidden' : '';
    };
    place(); window.addEventListener('scroll', place, true); window.addEventListener('resize', place); document.addEventListener('focusin', place);
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(place); observer?.observe(document.body);
    return () => { window.removeEventListener('scroll', place, true); window.removeEventListener('resize', place); document.removeEventListener('focusin', place); observer?.disconnect(); };
  }, [notification]);
  function updateCheck(id: string, value: EntryCheck) { client.setQueryData<Awaited<ReturnType<typeof load>>>(queryKey, previous => previous ? { ...previous, checks: { ...previous.checks, [id]: value } } : previous); }
  useEffect(() => {
    if (!observed || connecting) return;
    client.setQueryData<Awaited<ReturnType<typeof load>>>(['private', 'settings-model-library', scope], previous => {
      const latest = previous?.checks[observed.entry_id];
      return previous && latest && latest !== 'UNKNOWN' && latest.operation_id === observed.operation_id ? { ...previous, checks: { ...previous.checks, [observed.entry_id]: testUnknown || test.isError ? 'UNKNOWN' : observed } } : previous;
    });
  }, [observed, connecting, testUnknown, test.isError, client, scope]);
  function closeWizard(restore = true) { const inside = document.activeElement?.closest('[aria-label="Add models wizard"]'); wizardGeneration.current += 1; setWizard(null); if (restore && inside) addButton.current?.focus({ preventScroll: true }); }
  function open(provider: Connection['provider'] = 'openrouter', replace = false) {
    if (blocked || sending) return;
    const id = ++wizardGeneration.current; setWizard({ id, provider, replace });
  }
  async function readCurrent(recover = false) {
    if (!authReady || reading || mutationBusy.current || continuation.current || (pending && !recover)) return;
    setReading(true); setNotice(''); const abort = new AbortController(); readController.current = abort;
    try {
      if (recover && pending) await readPrivate(async () => { if (pending.kind === 'keys') await api.providerKeys(pending.id, abort.signal); else await api.providerModels(pending.id, abort.signal); }, abort.signal);
      const value = await readPrivate(() => load(abort.signal), abort.signal);
      if (abort.signal.aborted || lifetime.current.signal.aborted) return;
      remember(pendingStorage, scope, null); setPending(null); setStale(false); client.setQueryData(queryKey, value);
      setNotice(recover ? 'Exact receipt recovered; current settings loaded. No catalog refresh or test was sent.' : 'Settings reloaded.');
    } catch (error) { if (!abort.signal.aborted && !lifetime.current.signal.aborted) { setStale(true); setNotice(recover ? 'Receipt not confirmed. Do not repeat this command.' : message(error)); } }
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
      const confirmed = await readPrivate(async () => kind === 'keys' ? await api.providerKeys(id, lifetime.current.signal) : await api.providerModels(id, lifetime.current.signal), lifetime.current.signal);
      if (JSON.stringify(confirmed) !== JSON.stringify(receipt)) throw new ApiError('INVALID_RESPONSE');
      const value = await readPrivate(() => load(lifetime.current.signal), lifetime.current.signal);
      if (lifetime.current.signal.aborted) return;
      remember(pendingStorage, scope, null); setPending(null); client.setQueryData(queryKey, value);
      await client.invalidateQueries({ queryKey: ['private', 'model-test'] });
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
    continuation.current?.abort();
    const result = await mutate('keys', command.command_id, () => api.saveProviderKeys(command, session.data!.csrf_token, lifetime.current.signal));
    if (result) setNotice(command.action === 'save_selection' ? 'Assignments saved. Applies to future runs only.' : command.action === 'revoke_connection' ? 'Connection disabled.' : 'Key saved.');
    return result;
  }
  async function refresh(connection: Connection): Promise<CatalogView | undefined> {
    if (blocked || mutationBusy.current || catalogOperation) return;
    const operation = { id: crypto.randomUUID(), connection: connection.connection_id, revision: connection.revision };
    mutationBusy.current = true; setSending(true); setCatalogNotice(null);
    try {
      remember(catalogStorage, scope, operation); setCatalogOperation(operation);
      const value = await readPrivate(() => api.refreshProviderCatalog({ action: 'refresh', command_id: operation.id, connection_id: operation.connection, connection_revision: operation.revision }, session.data!.csrf_token, lifetime.current.signal), lifetime.current.signal);
      if (value.state !== 'PENDING') { remember(catalogStorage, scope, null); setCatalogOperation(null); void client.invalidateQueries({ queryKey }); }
      return value;
    } catch (error) { if (!lifetime.current.signal.aborted) { if (definitive(error)) { remember(catalogStorage, scope, null); setCatalogOperation(null); setStale(true); } setCatalogNotice({ connection: connection.connection_id, text: definitive(error) ? 'Models could not be loaded. Reload settings before trying again.' : 'Model list update is unconfirmed. Read its status before refreshing again.', detail: error instanceof ApiError ? error.code : 'API_UNAVAILABLE' }); } }
    finally { mutationBusy.current = false; if (!lifetime.current.signal.aborted) setSending(false); }
  }
  async function readCatalog(cancel = false) {
    if (!catalogOperation || !session.data) return;
    const snapshot = catalogOperation, signal = lifetime.current.signal;
    try {
      const value = await readPrivate(() => cancel ? api.cancelProviderCatalog({ action: 'cancel', connection_id: snapshot.connection, connection_revision: snapshot.revision, catalog_command_id: snapshot.id, command_id: crypto.randomUUID() }, session.data!.csrf_token, signal) : api.providerCatalog({ action: 'search', connection_id: snapshot.connection, connection_revision: snapshot.revision, catalog_command_id: snapshot.id, query: '', offset: 0 }, session.data!.csrf_token, signal), signal);
      setCatalogNotice(value.state === 'READY' && value.reason === null ? null : { connection: snapshot.connection, text: value.state === 'PENDING' ? 'Loading models…' : value.state === 'PARTIAL' ? 'Some models could not be loaded. Open Add models to inspect the available list.' : 'Models could not be loaded. Open Add models to refresh the list or enter an exact model ID.', detail: `${value.state}${value.reason ? ' · ' + value.reason : ''}` });
      if (value.state !== 'PENDING') { remember(catalogStorage, scope, null); setCatalogOperation(null); }
      await client.invalidateQueries({ queryKey: ['private', 'settings-catalog'] });
      if (value.state !== 'PENDING') void client.invalidateQueries({ queryKey });
    } catch (error) { if (!signal.aborted) setCatalogNotice({ connection: snapshot.connection, text: 'Model list update is unconfirmed. Read its status before refreshing again.', detail: error instanceof ApiError ? error.code : 'API_UNAVAILABLE' }); }
  }
  function catalogRead(value: CatalogView) {
    if (!catalogOperation || value.catalog_command_id !== catalogOperation.id || value.connection_id !== catalogOperation.connection || value.connection_revision !== catalogOperation.revision || value.state === 'PENDING') return;
    remember(catalogStorage, scope, null); setCatalogOperation(null); setCatalogNotice(null);
    void client.invalidateQueries({ queryKey });
  }
  async function startTest(entry: ModelEntry, catalog: string, expectedGeneration: number, sequence?: AbortSignal) {
    if (!session.data || (!sequence && activeTest) || mutationBusy.current || lifetime.current.signal.aborted || sequence?.aborted) return;
    mutationBusy.current = true; setSending(true); setConsent(false); setNotice('');
    const id = crypto.randomUUID(); let submitted = false;
    try {
      readController.current?.abort();
      await client.cancelQueries({ queryKey });
      if (lifetime.current.signal.aborted || sequence?.aborted) return;
      remember(testStorage, scope, id); remember(testStorage + '-refused', scope, null); setRefusedTest(null); setOperation(id); setOperationEntry(entry.entry_id); setTestUnknown(false); setTestNotice('');
      updateCheck(entry.entry_id, 'UNKNOWN');
      submitted = true;
      const value = await readPrivate(() => api.startEntryModelTest({ operation_id: id, expected_generation: expectedGeneration, entry_id: entry.entry_id, expected_entry_revision: entry.revision, expected_connection_revision: entry.connection_revision, catalog_command_id: catalog, consent: true }, session.data!.csrf_token, lifetime.current.signal), lifetime.current.signal);
      if (lifetime.current.signal.aborted) return;
      client.setQueryData(['private', 'settings-entry-test', scope, id], value); updateCheck(entry.entry_id, value);
      setTestChoice(null);
      return value;
    } catch (error) { if (!lifetime.current.signal.aborted) { setTestUnknown(submitted); if (definitive(error)) { remember(testStorage + '-refused', scope, id); setRefusedTest(id); setStale(true); setTestChoice(null); } setTestNotice(submitted ? `Test outcome unconfirmed. Read the same operation. ${message(error)}` : 'Test identity could not be retained. No test submitted.'); } }
    finally { mutationBusy.current = false; if (!lifetime.current.signal.aborted) setSending(false); }
  }
  async function readTest(cancel = false) {
    if (cancel) continuation.current?.abort();
    if (!operation || !session.data) return;
    const id = operation, signal = lifetime.current.signal;
    try {
      const value = await readPrivate(() => cancel && observed?.state_revision ? api.cancelEntryModelTest(id, crypto.randomUUID(), observed.state_revision, session.data!.csrf_token, signal) : api.entryModelTest(id, signal), signal);
      if (signal.aborted) return;
      client.setQueryData(['private', 'settings-entry-test', scope, id], value); setTestUnknown(false); setTestNotice('');
      const latest = await readPrivate(() => api.latestEntryModelTest(value.entry_id, signal), signal);
      if (!signal.aborted) updateCheck(value.entry_id, latest);
    } catch (error) {
      if (signal.aborted) return;
      continuation.current?.abort();
      if (!cancel && error instanceof ApiError && error.code === 'NOT_FOUND' && refusedTest === id) {
        remember(testStorage, scope, null); remember(testStorage + '-refused', scope, null); setOperation(null); setOperationEntry(null); setRefusedTest(null); setTestUnknown(false); setTestNotice(''); setNotice('Test was not admitted. A new test requires new consent.');
      } else { setTestUnknown(true); setTestNotice('UNKNOWN — keep the same operation ID. No test was resent.'); }
    }
  }
  function checkSelectionBlocked(check: EntryCheck | undefined) {
    return (sending || connecting || operationPending) && !(check && check !== 'UNKNOWN' && check.operation_id === operation);
  }
  function readCheck(check: EntryCheck | undefined) {
    if (check && check !== 'UNKNOWN' && check.operation_id === operation) { void readTest(); return; }
    if (mutationBusy.current || continuation.current || checkSelectionBlocked(check)) return;
    if (check && check !== 'UNKNOWN') { setOperation(check.operation_id ?? null); setOperationEntry(check.entry_id); setTestUnknown(false); setTestNotice(''); } else void readCurrent();
  }
  async function connectEntries(entries: ModelEntry[], catalog: string, provider: Connection['provider'], expectedGeneration: number) {
    const controller = new AbortController(); continuation.current = controller; setConnecting(true);
    const signal = AbortSignal.any([controller.signal, lifetime.current.signal]);
    let checking: ModelEntry | undefined;
    try {
      for (const entry of entries) {
        if (signal.aborted) return;
        checking = entry;
        const started = await startTest(entry, catalog, expectedGeneration, signal);
        if (!started || signal.aborted) return;
        const deadline = performance.now() + started.wall_seconds * 1000;
        let checked: EntryTestView;
        do {
          checked = await readPrivate(() => api.entryModelTest(started.operation_id!, signal), signal);
          if (signal.aborted) return;
          client.setQueryData(['private', 'settings-entry-test', scope, checked.operation_id], checked); updateCheck(entry.entry_id, checked);
          if (!exactCheck(entry, provider, checked) || checked.state === 'NEEDS_RECONCILIATION' || checked.state === 'STOPPING' || (checked.result_state && checked.result_state !== 'COMPLETED')) throw new Error('Check did not complete');
          if (checked.state === 'FINISHED') break;
          if (performance.now() >= deadline) throw new Error('Read deadline reached');
          await new Promise<void>(resolve => { const done = () => { clearTimeout(timer); signal.removeEventListener('abort', done); resolve(); }; const timer = setTimeout(done, 750); signal.addEventListener('abort', done, { once: true }); });
        } while (!signal.aborted);
        if (signal.aborted) return;
        if (checked.state !== 'FINISHED' || checked.result_state !== 'COMPLETED' || checked.finish_reason !== 'COMPLETED') throw new Error('Check did not complete');
        const latest = await readPrivate(() => api.latestEntryModelTest(entry.entry_id, signal), signal);
        if (signal.aborted) return;
        updateCheck(entry.entry_id, latest);
        if (latest.operation_id !== checked.operation_id || latest.state !== 'FINISHED' || latest.result_state !== 'COMPLETED' || latest.finish_reason !== 'COMPLETED' || !exactCheck(entry, provider, latest)) throw new Error('Check changed');
      }
      setNotice('Models connected.');
    } catch (error) {
      if (!signal.aborted) {
        if (error instanceof ApiError && checking) { updateCheck(checking.entry_id, 'UNKNOWN'); setTestUnknown(true); }
        setTestNotice('Connection checks stopped. Read the current operation; remaining models were not sent. New checks require new consent.');
      }
    } finally {
      if (continuation.current === controller) continuation.current = null;
      if (!lifetime.current.signal.aborted) setConnecting(false);
    }
  }
  async function saveModels(payload: SaveModels, testIntent: { catalog: string; generation: number } | null, generation: number) {
    const receipt = await mutate('models', payload.command_id, () => api.saveProviderModels(payload, session.data!.csrf_token, lifetime.current.signal));
    if (!receipt) return;
    const latest = client.getQueryData<Awaited<ReturnType<typeof load>>>(queryKey);
    const entries = latest?.library.entries.filter(item => payload.models.some(request => request.entry_id === item.entry_id && request.model === item.model && item.revision === request.expected_revision + 1 && item.output_tokens === request.output_tokens) && item.connection_id === payload.connection_id && item.connection_revision === payload.connection_revision) ?? [];
    if (latest?.library.revision !== receipt.registry_revision || receipt.registry_revision !== payload.expected_registry_revision + 1 || entries.length !== payload.models.length) { setStale(true); setNotice('Saved entries do not match the requested revisions. Read current settings; no test was sent.'); return; }
    if (testIntent && latest?.generation == null) { setNotice('Models saved. Instance admission is unavailable; no test was sent. Reload settings and give new consent.'); return entries; }
    if (!testIntent) setNotice('Models saved. Assignments stay unchanged.');
    const connection = data?.settings.connections.find(item => item.connection_id === payload.connection_id);
    if (testIntent && connection && generation === wizardGeneration.current && !lifetime.current.signal.aborted) void connectEntries(payload.models.map(request => entries.find(item => item.entry_id === request.entry_id)!), testIntent.catalog, connection.provider, testIntent.generation);
    return entries;
  }
  return <>
    <div className={styles.heading}><h2>Models</h2><fieldset className={styles.headingActions} aria-label="Model library actions">
      <button type="button" className={pending || stale || current.isError ? undefined : styles.quiet} aria-label={pending ? undefined : 'Reload current settings'} disabled={!authReady} aria-disabled={reading || sending || connecting} onClick={() => { if (!reading) void readCurrent(!!pending); }}>{pending ? 'Recover exact receipt' : stale || current.isError ? 'Reload current settings' : 'Reload'}</button>
      <button ref={addButton} type="button" disabled={blocked} aria-disabled={busy} onClick={() => { if (!busy) open(); }}>Add models</button>
    </fieldset></div>
    {notification && <aside ref={feedback} className={styles.notification} aria-label="Settings notification"><output aria-live="polite">{notification}</output><button type="button" className={styles.quiet} aria-label="Dismiss notification" onClick={() => setNotification('')}>×</button></aside>}
    {(pending || stale || current.isError || (notice && !confirmations.includes(notice))) && <section className={styles.notice} aria-label="Settings recovery">
      <output aria-live="polite">{pending ? sending ? 'Saving locally…' : 'Save unconfirmed. Recover the exact receipt before another mutation.' : notice && !confirmations.includes(notice) ? notice : 'Read failed. Current settings are not confirmed.'}</output>
      {pending && notice && !confirmations.includes(notice) && <p>{notice}</p>}
      {!sending && <button type="button" className={styles.secondary} onClick={() => { void readCurrent(!!pending); }}>Read current state</button>}
      {pending && <details><summary>Command details</summary><p className={styles.mono}>Command {pending.id}</p></details>}
    </section>}

    {!data?.settings.connections.some(connection => connection.connection_id === (catalogOperation?.connection ?? catalogNotice?.connection)) && catalogRecovery()}

    {operationPending && !operationInList && <section className={styles.notice} aria-label="Unconfirmed model check">
      <p>{observed?.requested_model ?? 'Test outcome unconfirmed.'} Read the same operation; no automatic resend.</p>
      {testNotice && <p>{testNotice}</p>}
      {operationControls()}
      <details><summary>Operation details</summary><p className={styles.mono}>Operation {operation}</p></details>
    </section>}
    {data && <>
      {generation === null && <p className={styles.hint}>Instance admission is unavailable. Reload current settings before opening new test consent.</p>}
      {wizard && <SettingsModelWizard key={wizard.id} settings={data.settings} library={data.library} provider={wizard.provider} replace={wizard.replace} blocked={blocked} working={sending} canTest={!activeTest} generation={generation} catalogFeedback={data.settings.connections.some(connection => connection.provider === wizard.provider && connection.connection_id === (catalogOperation?.connection ?? catalogNotice?.connection)) ? catalogRecovery() : null} catalogRead={catalogRead} close={() => closeWizard()} refresh={refresh} saveKey={async (provider, connection, secret) => {
        const result = await saveKeys({ action: 'save_connection', command_id: crypto.randomUUID(), connection_id: connection?.connection_id ?? crypto.randomUUID(), expected_revision: connection?.revision ?? 0, provider, secret });
        const saved = result?.connections.find(item => item.provider === provider);
        const latest = client.getQueryData<{ settings: KeySettings }>(queryKey)?.settings.connections.find(item => item.provider === provider);
        if (saved && latest && saved.connection_id === latest.connection_id && saved.revision === latest.revision && latest.enabled && latest.credential_present) return latest;
        if (result) { setStale(true); setNotice('The connection changed after its receipt. Reload; no catalog refresh was sent.'); }
      }} saveModels={(payload, test) => saveModels(payload, test, wizard.id)} />}
      <section className={styles.panel} aria-label="Configured models"><div className={styles.core}>
      {data.settings.vault_status === 'LOCKED' && <output>Vault locked. Restore the local master key. Connections may still be disabled locally.</output>}
      {!data.library.entries.length && <p className={styles.hint}>No models configured.</p>}
      {data.settings.connections.map(connection => {
        const entries = data.library.entries.filter(entry => entry.connection_id === connection.connection_id);
        const unread = entries.filter(entry => data.catalogs[entry.entry_id] && 'code' in data.catalogs[entry.entry_id]!);
        const failed = entries.filter(entry => { const catalog = data.catalogs[entry.entry_id]; return catalog && !('code' in catalog) && catalog.state === 'FAILED'; });
        return <section className={styles.connection} key={connection.connection_id} aria-label={providerName(connection.provider)}>
        <div className={styles.connectionHeading}><h3>{providerName(connection.provider)}</h3><small>{!connection.enabled ? 'Connection disabled' : connection.credential_present ? 'Key saved' : 'Key unavailable — vault locked'}</small>
        </div>
        <ul className={styles.list}>{entries.map(entry => {
          const latest = data.checks[entry.entry_id], bound = operationEntryId === entry.entry_id && !!operation;
          const check = latest && latest !== 'UNKNOWN' ? latest : bound && observed ? observed : null;
          const open = expanded.includes(entry.entry_id), uncertain = latest === 'UNKNOWN' || check?.result_state === 'UNKNOWN' || check?.state === 'NEEDS_RECONCILIATION' || (bound && (testUnknown || test.isError));
          const needsRecovery = bound && (operationPending || connecting || !!testNotice);
          const detailsId = `model-details-${entry.entry_id}`, statusId = `model-status-${entry.entry_id}`;
          return <li className={styles.model} key={entry.entry_id} aria-label={`Model ${entry.model} via ${providerName(connection.provider)}`}>
            <div className={styles.modelRow}>
              <button type="button" className={styles.modelToggle} aria-label={`Details for ${entry.model} via ${providerName(connection.provider)}`} aria-describedby={statusId} aria-expanded={open} aria-controls={detailsId} onClick={() => setExpanded(previous => open ? previous.filter(id => id !== entry.entry_id) : [...previous, entry.entry_id])}>
                <span className={styles.identity}><strong>{data.evidence[entry.entry_id]?.model.name ?? entry.model}</strong><small className={styles.mono}>{entry.model}</small></span>
                <span id={statusId} className={styles.state}>{stale || current.isError ? 'Unconfirmed — reload settings' : entryStatus(entry, data.settings, data.evidence, latest, data.catalogs)}</span>
              </button>
              {needsRecovery ? <button type="button" className={styles.secondary} onClick={() => { void readTest(canCancel); }}>{canCancel ? 'Cancel test' : 'Read test status'}</button> : <button type="button" className={styles.secondary} aria-label={`Test ${entry.model} via ${providerName(connection.provider)}`} disabled={blocked || activeTest || generation === null || !usable(entry, data.settings, data.evidence)} aria-disabled={busy} onClick={() => { if (!busy) { setTestChoice(entry); setTestGeneration(generation); setConsent(false); requestAnimationFrame(() => testHeading.current?.focus({ preventScroll: true })); } }}>Test</button>}
            </div>
            {needsRecovery && <div className={styles.operation} aria-label="Active model check">
              {testNotice && <output aria-live="polite">{testNotice}</output>}
              {uncertain && !testNotice && <p>Test outcome unconfirmed. Read the same operation; no test is resent.</p>}
              {operationControls(false)}
            </div>}
            {!needsRecovery && uncertain && <p className={styles.hint}>Saved check could not be read. Reload settings to confirm its result.</p>}
            <section id={detailsId} hidden={!open} className={styles.modelDetails} aria-label={`Model details for ${entry.model} via ${providerName(connection.provider)}`}>
              {check ? <>
                <p>{check.state === 'FINISHED' ? check.result_state === 'COMPLETED' && check.finish_reason === 'COMPLETED' ? 'Test completed.' : check.finish_reason === 'CANCELLED' ? 'Test cancelled. Read the saved result before testing again.' : 'Test did not complete successfully. Read the saved result before testing again.' : check.state === 'STOPPING' ? 'Test is stopping. Remote completion is not yet confirmed.' : check.state === 'NEEDS_RECONCILIATION' ? 'Test outcome unconfirmed. Read the same operation; no test is resent.' : 'Test in progress.'}</p>
                {!check.current && <p>This saved result belongs to an earlier entry or connection revision.</p>}
                <p>Requested model: <span className={styles.mono}>{check.requested_model}</span> · {providerName(check.requested_provider ?? connection.provider)}</p>
                <p>Observed model: <span className={styles.mono}>{check.observed_model ?? 'Not reported'}</span></p>
                <p aria-label="Model response" className={styles.response}>{check.response_text ?? 'No output confirmed.'}</p>
                {check.output_state === 'TRUNCATED' && <p>Response truncated.</p>}
                <div className={styles.usage}>{check.input_tokens !== null && <span>Input tokens: {check.input_tokens}</span>}{check.output_tokens !== null && <span>Output tokens: {check.output_tokens}</span>}{check.reasoning_tokens !== null && <span>Reasoning tokens: {check.reasoning_tokens}</span>}{check.cost_observed !== null && <span>Cost: {check.cost_observed}</span>}</div>
                {check.usage_state !== 'KNOWN' && <p className={styles.hint}>{check.usage_state === 'PARTIAL' ? 'Usage is incomplete.' : 'Usage was not reported.'}</p>}
                {!needsRecovery && <button type="button" className={styles.quiet} disabled={checkSelectionBlocked(check)} onClick={() => readCheck(check)}>Read test status</button>}
                <details><summary>Operation details</summary><p className={styles.mono}>Operation {check.operation_id}</p><p>{check.state} · {check.result_state ?? 'NOT_VERIFIED'} · {check.finish_reason ?? 'No finish reason'}{check.reason ? ` · ${check.reason}` : ''}</p><p className={styles.mono}>Entry {check.entry_id} revision {check.entry_revision} · connection {check.connection_id} revision {check.connection_revision}</p><p>Requested output cap: {check.requested_output_tokens}. Provider status: {check.provider_status ?? 'Not reported'}.</p></details>
              </> : <p>{uncertain ? 'No result confirmed. Read back before another test.' : 'No saved test for this model.'}</p>}
            </section>
          </li>;
        })}</ul>
        {wizard?.provider !== connection.provider && connection.connection_id === (catalogOperation?.connection ?? catalogNotice?.connection) && catalogRecovery()}
        {wizard?.provider !== connection.provider && connection.connection_id !== (catalogOperation?.connection ?? catalogNotice?.connection) && (unread.length > 0 || failed.length > 0) && <div>
          <p className={styles.hint}>{unread.length ? 'Model details could not be read. Reload settings to try the local read again.' : 'The model catalog is unavailable. Saved test results are unchanged. Open Add models to refresh it explicitly.'}</p>
          <details><summary>Catalog details</summary>{[...unread, ...failed].map(entry => {
            const catalog = data.catalogs[entry.entry_id]!;
            return <p key={entry.entry_id} className={styles.mono}>{entry.model} · {'code' in catalog ? catalog.code : `${catalog.state} · ${catalog.reason} · Catalog ${catalog.catalog_command_id}`} · connection revision {entry.connection_revision}</p>;
          })}</details>
        </div>}
          <details><summary>Connection options</summary><div className={styles.actions}><button type="button" className={styles.secondary} disabled={blocked || data.settings.vault_status === 'LOCKED'} onClick={() => { if (window.confirm(`${connection.enabled ? 'Replace the key for' : 'Reconnect'} ${providerName(connection.provider)}? Saved checks and assignments keep their original revision.`)) open(connection.provider, true); }}>{connection.enabled ? 'Replace key' : 'Reconnect'}</button><button type="button" className={styles.secondary} disabled={blocked || !connection.enabled} aria-disabled={sending} onClick={() => {
            if (sending || !window.confirm(`Disable ${providerName(connection.provider)}? Saved models and history remain. This does not revoke the upstream key.`)) return;
            if (wizard?.provider === connection.provider) closeWizard(false);
            setTestChoice(null); setConsent(false);
            void saveKeys({ action: 'revoke_connection', command_id: crypto.randomUUID(), connection_id: connection.connection_id, expected_revision: connection.revision });
          }}>Disable connection</button></div></details>
      </section>; })}

    </div></section>
      {testChoice && <section className={styles.panel} aria-label="Test consent"><div className={styles.core}><h2 tabIndex={-1} ref={testHeading}>Test model</h2><p>{testConnection ? providerName(testConnection.provider) : 'Unavailable connection'} · <span className={styles.mono}>{testChoice.model}</span></p><p>One fixed synthetic call / 300 seconds. Provider charges may apply.</p><label className={styles.check}><input type="checkbox" checked={consent} disabled={blocked || activeTest || generation === null || testGeneration === null} onChange={event => setConsent(event.target.checked)} />I approve one synthetic acknowledgement call for {testChoice.model}. No tools or target data.</label><details><summary>Fixed input</summary><p>Respond only with OMNIS_MODEL_TEST_OK. Use no tools.</p><p>This is a synthetic local settings test. Reply with OMNIS_MODEL_TEST_OK.</p></details><div className={styles.actions}><button type="button" className={styles.secondary} onClick={() => { setTestChoice(null); setConsent(false); }}>Cancel</button><button type="button" disabled={blocked || activeTest || generation === null || testGeneration === null || !consent || !usable(testChoice, data.settings, data.evidence)} aria-disabled={sending} onClick={() => { const proof = data.evidence[testChoice.entry_id]; if (!sending && consent && proof && testGeneration !== null) void startTest(testChoice, proof.catalog, testGeneration); }}>Send model test</button></div></div></section>}
      <SettingsAssignments settings={data.settings} library={data.library} evidence={data.evidence} catalogs={data.catalogs} blocked={blocked} working={busy} save={async command => !!await saveKeys(command)} />
    </>}
    {legacy && <ModelTest receiveOnly />}
  </>;
  function catalogRecovery() {
    if (!catalogOperation && !catalogNotice) return null;
    return <section className={styles.catalogStatus} aria-label="Catalog recovery"><output aria-live="polite">{catalogNotice?.text ?? 'Loading models…'}</output>
      {catalogOperation && <div className={styles.actions}><button type="button" className={styles.secondary} onClick={() => { void readCatalog(); }}>Read catalog status</button><button type="button" className={styles.secondary} onClick={() => { void readCatalog(true); }}>Cancel catalog</button></div>}
      <details><summary>Catalog details</summary>{catalogOperation && <p className={styles.mono}>Catalog operation {catalogOperation.id} · connection revision {catalogOperation.revision}</p>}{catalogNotice && <p className={styles.mono}>{catalogNotice.detail}</p>}</details>
    </section>;
  }
  function operationControls(cancel = true) {
    return <>
      <div className={styles.actions}>{cancel && canCancel && <button type="button" onClick={() => { void readTest(true); }}>Cancel test</button>}{connecting && <button type="button" className={styles.secondary} onClick={() => { continuation.current?.abort(); setTestNotice('Remaining checks stopped. The admitted call may still finish; read its status.'); }}>Stop remaining checks</button>}{(cancel || canCancel) && <button type="button" className={styles.secondary} onClick={() => { void readTest(); }}>Read test status</button>}</div>
      {observed?.state !== 'FINISHED' && <p className={styles.hint}>Cancel does not guarantee remote cancellation or a refund.</p>}
    </>;
  }
}
function entryStatus(entry: ModelEntry, settings: KeySettings, evidence: Record<string, Evidence>, test: EntryCheck | undefined, catalogs: Record<string, CatalogRead>) {
  const connection = currentConnection(entry, settings);
  if (!connection) return 'Unavailable — stale or disabled connection';
  if (test === 'UNKNOWN') return 'Unconfirmed';
  if (test) {
    if (!exactCheck(entry, connection.provider, test)) return 'Unavailable — stale check';
    if (test.state === 'NEEDS_RECONCILIATION' || test.result_state === 'UNKNOWN') return 'Unconfirmed';
    if (test.state !== 'FINISHED') return test.state === 'STOPPING' ? 'Stopping' : 'Connecting';
    const issue = availabilityIssue(entry, settings, evidence, catalogs);
    return test.result_state === 'COMPLETED' && test.finish_reason === 'COMPLETED' ? issue ? `Test passed · ${issue.toLowerCase()}` : 'Connected' : 'Failed';
  }
  return usable(entry, settings, evidence) ? 'Not tested' : 'UNVERIFIED — details needed';
}
