import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import { printable } from '../../shared/api/providerKeys';
import type { KeySettings } from '../../shared/api/providerKeys';
import type { CatalogView } from '../../shared/api/providerCatalog';
import type { SaveModels } from '../../shared/api/providerModels';
import { useSession } from '../bootstrap/BrowserSession';
import { providerName, supports } from './SettingsModels';
import type { Connection, Library, ModelEntry } from './SettingsModels';
import styles from './SettingsModels.module.css';

export type ModelDraft = { entry_id: string; expected_revision: number; model: string; name: string; output_tokens: number; known: boolean };
export function SettingsModelWizard({ settings, library, provider: initialProvider, replace = false, blocked, working, canTest, generation, close, saveKey, refresh, saveModels }: {
  settings: KeySettings; library: Library; provider: Connection['provider']; replace?: boolean | undefined;
  blocked: boolean; working: boolean; canTest: boolean; generation: number | null; close: () => void;
  saveKey: (provider: Connection['provider'], connection: Connection | undefined, secret: string) => Promise<Connection | undefined>;
  refresh: (connection: Connection) => Promise<CatalogView | undefined>;
  saveModels: (payload: SaveModels, test: { catalog: string; generation: number } | null) => Promise<ModelEntry[] | undefined>;
}) {
  const { session, readPrivate } = useSession();
  const [provider, setProvider] = useState(initialProvider);
  const [step, setStep] = useState(0);
  const [replacing, setReplacing] = useState(replace);
  const [chosen, setChosen] = useState<ModelDraft[]>([]);
  const [query, setQuery] = useState('');
  const [offset, setOffset] = useState(0);
  const [catalogId, setCatalogId] = useState<string | null>(null);
  const [manual, setManual] = useState('');

  const [consent, setConsent] = useState(false);
  const [testGeneration, setTestGeneration] = useState<number | null>(null);
  const [validKey, setValidKey] = useState(false);
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(false);
  const [pinned, setPinned] = useState(() => settings.connections.find(item => item.provider === initialProvider));
  const keyInput = useRef<HTMLInputElement>(null);
  const alive = useRef(true);
  const busy = useRef(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const keyNode = useRef<HTMLInputElement | null>(null);
  const current = settings.connections.find(item => item.provider === provider);
  const stale = pinned ? !current || current.connection_id !== pinned.connection_id || current.revision !== pinned.revision || current.enabled !== pinned.enabled : !!current;
  const connection = pinned;
  const savedKey = !!connection?.enabled && !!connection.credential_present && !replacing;
  const locked = blocked || stale || settings.vault_status === 'LOCKED';
  const transient = working || loading;
  const catalog = useQuery({ queryKey: ['private', 'settings-catalog', connection?.connection_id, connection?.revision, catalogId, query, offset],
    queryFn: ({ signal }) => readPrivate(() => api.providerCatalog({ action: 'search', connection_id: connection!.connection_id, connection_revision: connection!.revision, catalog_command_id: catalogId, query, offset }, session.data!.csrf_token, signal), signal),
    enabled: step > 0 && savedKey && !stale && !blocked && !!session.data, retry: false, gcTime: 0,
    refetchOnWindowFocus: false, refetchOnReconnect: false,
    refetchInterval: state => state.state.data?.state === 'PENDING' ? 750 : false });
  useEffect(() => { alive.current = true; heading.current?.focus({ preventScroll: true }); return () => { alive.current = false; if (keyNode.current) keyNode.current.value = ''; }; }, []);
  useEffect(() => { if (locked && keyInput.current) { keyInput.current.value = ''; setValidKey(false); } }, [locked]);
  const view = catalog.data;

  // Selected metadata remains pinned even when the operator searches another page.
  const selectedMetadata = useRef(new Map<string, { max_output_tokens: number | null; supports_max_tokens: boolean | null; catalog: string }>());
  const testable = chosen.filter(item => {
    const proof = selectedMetadata.current.get(item.model);
    return item.known && !!proof && proof.catalog === view?.catalog_command_id && supports(proof, item.output_tokens);
  });
  function wipe() { if (keyInput.current) keyInput.current.value = ''; if (keyNode.current) keyNode.current.value = ''; setValidKey(false); }
  function chooseProvider(value: string) {
    if (transient || blocked || (value !== 'openrouter' && value !== 'orcarouter')) return;
    if (chosen.length && !window.confirm('Discard selected models and change provider?')) return;
    wipe(); setProvider(value); setPinned(settings.connections.find(item => item.provider === value)); setChosen([]); setQuery(''); setOffset(0); setCatalogId(null); setReplacing(false); setConsent(false); selectedMetadata.current.clear();
  }
  async function load(connection: Connection) {
    const value = await refresh(connection);
    if (!alive.current || !value) return;
    setCatalogId(value.catalog_command_id ?? null); setQuery(''); setOffset(0); setConsent(false);
  }
  async function next() {
    if (locked || transient || busy.current) return;
    if (step === 1) { if (chosen.length) { setStep(2); setTestGeneration(generation); setConsent(false); heading.current?.focus({ preventScroll: true }); } return; }
    const focused = document.activeElement;
    busy.current = true; setLoading(true); setNotice('');
    let secret = keyInput.current?.value ?? ''; wipe();
    try {
      let nextConnection = connection;
      if (!savedKey) {
        if (!printable(secret, 512)) { setNotice('Use 1–512 printable ASCII characters without whitespace.'); return; }
        nextConnection = await saveKey(provider, connection, secret);
        secret = '';
      }
      if (!alive.current || !nextConnection) return;
      if (document.activeElement === focused) heading.current?.focus({ preventScroll: true });
      setPinned(nextConnection); setReplacing(false); setStep(1);
      await load(nextConnection);
    } finally { secret = ''; busy.current = false; if (alive.current) setLoading(false); }
  }
  function add(model: string, name: string, verified: boolean) {
    const previous = library.entries.find(item => item.connection_id === connection?.connection_id && item.model === model);
    if (locked || transient || chosen.some(item => item.model === model) || previous?.connection_revision === connection?.revision) return;
    if (!previous && library.entries.length + chosen.filter(item => item.expected_revision === 0).length >= 64) { setNotice('The instance is limited to 64 configured models.'); return; }
    const detail = verified ? view?.entries.find(item => item.model === model) : undefined;
    if (detail && view?.catalog_command_id) selectedMetadata.current.set(model, { max_output_tokens: detail.max_output_tokens ?? null, supports_max_tokens: detail.supports_max_tokens ?? null, catalog: view.catalog_command_id });
    setChosen([...chosen, { entry_id: previous?.entry_id ?? crypto.randomUUID(), expected_revision: previous?.revision ?? 0, model, name, output_tokens: previous?.output_tokens ?? Math.min(detail?.max_output_tokens ?? 128, 128), known: verified }]); setConsent(false);
  }
  async function save(test: boolean) {
    if (locked || transient || busy.current || !connection || !chosen.length || chosen.some(item => !Number.isSafeInteger(item.output_tokens) || item.output_tokens < 1 || item.output_tokens > 65536) || (test && (generation === null || testGeneration === null || !canTest || !consent || testable.length !== chosen.length || !view?.catalog_command_id))) return;
    busy.current = true; setLoading(true);
    try {
      const result = await saveModels({ action: 'save_models', command_id: crypto.randomUUID(), expected_registry_revision: library.revision, connection_id: connection.connection_id, connection_revision: connection.revision,
        models: chosen.map(item => ({ entry_id: item.entry_id, expected_revision: item.expected_revision, model: item.model, output_tokens: item.output_tokens })) }, test && testGeneration !== null ? { catalog: view!.catalog_command_id!, generation: testGeneration } : null);
      if (alive.current && result) close();
    } finally { busy.current = false; if (alive.current) setLoading(false); }
  }
  return <section className={styles.panel} aria-label="Add models wizard"><div className={styles.core}>
    <div className={styles.heading}><h2 ref={heading} tabIndex={-1}>Add models</h2><button type="button" className={styles.secondary} onClick={() => { wipe(); close(); }}>Cancel</button></div>
    <ol className={styles.steps} aria-label="Setup steps">{['Connection', 'Models', 'Review'].map((name, index) => <li key={name} aria-current={step === index ? 'step' : undefined}>{index + 1} · {name}</li>)}</ol>
    {stale && <p role="alert" className={styles.notice}>This connection changed or was disabled. Cancel and reopen to use its current revision.</p>}
    {notice && <p role="alert" className={styles.notice}>{notice}</p>}
    {step === 0 && <><div className={styles.fields}><label className={styles.field}>Provider<select value={provider} disabled={blocked} aria-disabled={transient} onChange={event => chooseProvider(event.target.value)}><option value="openrouter">OpenRouter</option><option value="orcarouter">OrcaRouter</option></select></label>
      {savedKey ? <div className={styles.field}><span>API key</span><span className={styles.saved}>Saved key</span></div> : <label className={styles.field}>API key<input ref={node => { keyInput.current = node; if (node) keyNode.current = node; }} type="password" name="secret" autoComplete="new-password" spellCheck={false} maxLength={512} disabled={locked} aria-disabled={transient} onChange={event => setValidKey(printable(event.target.value, 512))} /></label>}
    </div><p className={styles.hint}>{savedKey ? 'Continue loads the catalog using your saved key.' : 'Continue saves this key locally and loads the catalog.'} Cancel discards model choices, not the saved key.</p></>}
    {step === 1 && <>
      <div className={styles.search}><label className={styles.field}>Search models<input type="search" value={query} placeholder="Search by name or exact model ID" onChange={event => { if (Array.from(event.target.value).length <= 256) { setQuery(event.target.value); setOffset(0); } }} /></label><button type="button" className={styles.secondary} disabled={locked || !savedKey} aria-disabled={transient || view?.state === 'PENDING'} onClick={() => { if (!transient && view?.state !== 'PENDING' && connection) { setLoading(true); void load(connection).finally(() => { if (alive.current) setLoading(false); }); } }}>Refresh</button></div>
      <output className={styles.hint}>{catalog.isFetching ? 'Reading cached models…' : catalog.isError ? 'Catalog read failed. No results are confirmed.' : view ? `${view.state} · ${view.total} matching cached models · showing ${view.entries.length ? offset + 1 : 0}–${offset + view.entries.length}${view.reason ? ' · ' + view.reason : ''}` : 'Catalog not requested.'}</output>
      {view?.state === 'PARTIAL' && <p className={styles.notice}>Partial catalog. These are loaded results, not all provider models.</p>}
      {view && ['FAILED', 'STALE', 'NOT_REQUESTED'].includes(view.state) && <p className={styles.notice}>Catalog {view.state.toLowerCase()}. Refresh explicitly or enter an exact model ID.</p>}
      {view && ['READY', 'PARTIAL'].includes(view.state) && !view.entries.length && <p>No matching models.</p>}
      <ul className={`${styles.list} ${styles.catalog}`} aria-label="Provider models">{!catalog.isError && view?.entries.map(item => {
        const previous = library.entries.find(entry => entry.connection_id === connection?.connection_id && entry.model === item.model), added = !!previous && previous.connection_revision === connection?.revision, selected = chosen.some(entry => entry.model === item.model);
        return <li key={item.model} className={styles.row}><div className={styles.identity}><strong>{item.name ?? item.model}</strong><small className={styles.mono}>{item.model}</small>{!supports(item, 1) && <small>Details unavailable for testing</small>}</div><button type="button" className={styles.secondary} disabled={locked || added || selected} aria-label={`${added ? 'Added' : selected ? 'Selected' : previous ? 'Update' : 'Add'} ${item.model}`} onClick={() => add(item.model, item.name ?? item.model, true)}>{added ? 'Added' : selected ? 'Selected' : previous ? 'Update' : '+ Add'}</button></li>;
      })}</ul>
      <div className={styles.actions}><button type="button" className={styles.secondary} disabled={offset === 0 || catalog.isFetching} onClick={() => setOffset(Math.max(0, offset - 16))}>Previous results</button><button type="button" className={styles.secondary} disabled={view?.next_offset == null || catalog.isFetching} onClick={() => { if (view?.next_offset != null) setOffset(view.next_offset); }}>Next results</button></div>
      <ul className={styles.chips} aria-label="Selected models">{chosen.map(item => <li key={item.model}><span>{item.name}</span><button type="button" aria-label={`Remove selected ${item.model}`} onClick={() => { setChosen(chosen.filter(value => value.model !== item.model)); setConsent(false); }}>×</button></li>)}</ul>
      <details><summary>Enter a model ID</summary><div className={styles.search}><label className={styles.field}>Exact model ID<input value={manual} maxLength={256} autoComplete="off" onChange={event => setManual(event.target.value)} /></label><button type="button" className={styles.secondary} disabled={locked} onClick={() => { if (!printable(manual, 256)) { setNotice('Use the exact printable ASCII model ID, without spaces (maximum 256 characters).'); return; } add(manual, manual, false); setManual(''); }}>Add model ID</button></div><p className={styles.hint}>Saved as UNVERIFIED. No access, capability or inference claim is made.</p></details>
    </>}
    {step === 2 && <><p>{providerName(provider)} · Saved key</p><ul className={`${styles.list} ${styles.review}`}>{chosen.map(item => <li key={item.model} className={styles.row}><div className={styles.identity}><strong>{item.name}</strong><small className={styles.mono}>{item.model}</small><small>{item.known ? 'Not tested' : 'UNVERIFIED — manual model ID'}</small></div></li>)}</ul>
      <p className={styles.hint}>{settings.selection ? 'Default and role overrides stay unchanged.' : 'No Default assigned. Save assignments after adding models.'}</p>
      {testable.length !== chosen.length && <p className={styles.hint}>Some model details are unavailable. Save models now; connect after refreshing their details.</p>}
      <label className={styles.check}><input type="checkbox" checked={consent} disabled={locked || generation === null || testGeneration === null || !canTest || testable.length !== chosen.length} onChange={event => setConsent(event.target.checked)} />I approve the fixed synthetic input and up to {chosen.length} {chosen.length === 1 ? 'call' : 'calls'}, one per listed model via {providerName(provider)}. Provider charges may apply.</label>
      {!canTest && <p className={styles.hint}>A test is active or unconfirmed. Cancel and readback remain available outside this wizard.</p>}
      <p className={styles.hint}>One call / 300 seconds, no tools or target traffic. Cancel is not a refund.</p>
      <details><summary>Fixed input</summary><p>Respond only with OMNIS_MODEL_TEST_OK. Use no tools.</p><p>This is a synthetic local settings test. Reply with OMNIS_MODEL_TEST_OK.</p></details>
      <details><summary>Output controls</summary><p className={styles.hint}>Output caps are not a total run budget.</p><div className={styles.fields}>{chosen.map(item => <label className={styles.field} key={item.model}>{item.model} output tokens<input type="number" min={1} max={65536} step={1} value={item.output_tokens} onChange={event => { setChosen(chosen.map(value => value.model === item.model ? { ...value, output_tokens: Number(event.target.value) } : value)); setConsent(false); }} /></label>)}</div></details>
    </>}
    <div className={styles.actions}>{step > 0 && <button type="button" className={styles.secondary} aria-disabled={transient} onClick={() => { if (!transient) setStep(step - 1); }}>Back</button>}<div className={styles.forward}>
      {step < 2 ? <button type="button" disabled={locked || (step === 0 && !savedKey && !validKey && !transient) || (step === 1 && !chosen.length)} aria-disabled={transient} aria-busy={transient} onClick={() => { void next(); }}>Continue</button> : <><button type="button" className={styles.secondary} disabled={locked || !chosen.length || chosen.some(item => !Number.isSafeInteger(item.output_tokens) || item.output_tokens < 1 || item.output_tokens > 65536)} aria-disabled={transient} onClick={() => { void save(false); }}>Save models</button><button type="button" disabled={locked || generation === null || testGeneration === null || !canTest || !consent || testable.length !== chosen.length} aria-disabled={transient} onClick={() => { void save(true); }}>Save &amp; connect</button></>}
    </div></div>
  </div></section>;
}
