import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router';
import { api } from '../../shared/api/client';
import { ApiError, isRecord, isUuid } from '../../shared/api/errors';
import { runPolling, checkRunProgress, runTerminal } from '../../shared/api/runs';
import type { RunView } from '../../shared/api/runs';
import { useSession } from '../bootstrap/BrowserSession';
import { remember, sessionScope } from './SettingsModels';
import styles from './Engagement.module.css';

type PendingStop = { command: string; run: string };
const pointer = 'omnis-run-stop';
const recoveryUnavailable = 'Stop recovery storage unavailable or invalid. Unresolved records were not cleared. Use local CLI omnis stop if needed.';
function pendingStops(scope: string): PendingStop[] {
  const raw = sessionStorage.getItem(pointer);
  if (raw === null) return [];
  const parsed: unknown = JSON.parse(raw);
  if (!isRecord(parsed) || parsed.scope !== scope) throw new Error('Stop recovery scope unavailable');
  // Retain the original single-pointer format until an explicit command settles or adds an identity.
  const values: unknown[] = Array.isArray(parsed.value) ? parsed.value : [parsed.value];
  const result = values.map(value => {
    if (!isRecord(value) || Object.keys(value).length !== 2 || !isUuid(value.command) || !isUuid(value.run)) throw new Error('Invalid Stop recovery identity');
    return { command: value.command, run: value.run };
  });
  if (new Set(result.map(item => item.command)).size !== result.length) throw new Error('Duplicate Stop recovery identity');
  return result;
}
export function RunStop({ run, label = 'Stop run' }: { run: RunView | null | undefined; label?: string }) {
  const { session, readPrivate } = useSession();
  const client = useQueryClient();
  const [scope, setScope] = useState<string | null>(null);
  const key = ['private', 'run-stops', scope];
  const recovery = useQuery<PendingStop[]>({ queryKey: key, enabled: false });
  const pending = recovery.data ?? [];
  const [sending, setSending] = useState<string[]>([]);
  const [storageFailed, setStorageFailed] = useState(false);
  const [message, setMessage] = useState('');
  const busy = useRef(new Set<string>());
  const hasRun = !!run;
  const lifetime = useRef(new AbortController());
  useEffect(() => {
    const controller = new AbortController(); lifetime.current = controller;
    const csrf = session.data?.csrf_token;
    let stored = false;
    try { stored = sessionStorage.getItem(pointer) !== null; }
    catch { setStorageFailed(true); setMessage(recoveryUnavailable); }
    if (csrf && (hasRun || stored)) void sessionScope(csrf).then(value => {
      if (controller.signal.aborted) return;
      const old = pendingStops(value);
      client.setQueryData(['private', 'run-stops', value], old);
      setScope(value);
    }).catch(() => { if (!controller.signal.aborted) { setStorageFailed(true); setMessage(recoveryUnavailable); } });
    return () => controller.abort();
  }, [session.data?.csrf_token, hasRun, client]);
  function savePending(value: PendingStop[]) {
    if (!scope) return;
    remember(pointer, scope, value.length ? value : null);
    client.setQueryData(key, value);
  }
  function clearPending(target: PendingStop) {
    if (!scope) return false;
    try { savePending(pendingStops(scope).filter(item => item.command !== target.command || item.run !== target.run)); return true; }
    catch { setStorageFailed(true); setMessage(recoveryUnavailable); return false; }
  }
  async function settle(target: PendingStop, send: (() => ReturnType<typeof api.runCommand>) | null) {
    if (!scope || busy.current.has(target.command)) return;
    // Read shared storage at the click, before awaiting, so competing controls cannot resend this run.
    if (send) {
      try {
        const current = pendingStops(scope);
        client.setQueryData(key, current);
        if (current.some(item => item.run === target.run)) return;
        savePending([...current, target]);
      } catch { setStorageFailed(true); setMessage(recoveryUnavailable); return; }
    }
    busy.current.add(target.command); setSending(current => [...current, target.command]);
    const signal = lifetime.current.signal;
    try {
      if (send) setMessage(`Stop pending · run ${target.run} · command ${target.command}`);
      const receipt = await readPrivate(send ?? (() => api.runCommandReceipt(target.command, signal)), signal);
      if (signal.aborted) return;
      if (receipt.run_id !== target.run) throw new ApiError('INVALID_RESPONSE');
      if (!clearPending(target)) return;
      setMessage(`${receipt.state} · Stop run ${target.run} · command ${target.command}. Read run state; this is not confirmation of STOPPED.`);
      await client.invalidateQueries({ queryKey: ['private'] });
    } catch (error) {
      if (signal.aborted) return;
      const refused = send && error instanceof ApiError && ['REVISION_CONFLICT', 'GENERATION_CONFLICT', 'AUTHORITY_DENIED', 'OPERATION_FINISHED', 'INVALID_INPUT'].includes(error.code);
      if (refused && !clearPending(target)) return;
      setMessage(refused ? `Stop refused · run ${target.run} · command ${target.command}. Read the run; no automatic retry.` : `Stop outcome unknown · run ${target.run} · command ${target.command}. Read this receipt; no resend. Use local CLI omnis stop if needed.`);
    } finally { busy.current.delete(target.command); if (!signal.aborted) setSending(current => current.filter(command => command !== target.command)); }
  }
  function stop() {
    const csrf = session.data?.csrf_token;
    if (!run || !csrf || !scope || storageFailed || pending.some(item => item.run === run.run_id) || runTerminal(run) || run.state === 'STOPPING') return;
    const payload = { action: 'stop', command_id: crypto.randomUUID(), run_id: run.run_id, expected_revision: run.revision, expected_generation: run.generation, question_id: null, answer: null } as const;
    void settle({ command: payload.command_id, run: run.run_id }, () => api.runCommand(payload, csrf));
  }
  return <>
    <button type="button" disabled={!run || runTerminal(run) || run.state === 'STOPPING' || !scope || storageFailed || pending.some(item => item.run === run.run_id)} onClick={stop}>{label}</button>
    {pending.length > 0 && <ul aria-label="Unacknowledged Stops">{pending.map(item => <li key={`${item.run}:${item.command}`}>Unacknowledged Stop · run {item.run} · command {item.command} · {item.run === run?.run_id ? 'currently displayed run' : 'not the currently displayed run'}. Outcome unknown; no resend. <button type="button" aria-label={`Read Stop receipt · run ${item.run} · command ${item.command}`} disabled={sending.includes(item.command)} onClick={() => { void settle(item, null); }}>Read Stop receipt</button></li>)}</ul>}
    <output aria-live="polite">{message}</output>
  </>;
}
export function GlobalStop() {
  const { readPrivate } = useSession();
  const client = useQueryClient();
  const key = ['private', 'active-run'];
  const active = useQuery({ queryKey: key, queryFn: ({ signal }) => readPrivate(async () => checkRunProgress(await api.activeRun(signal), client.getQueryData<RunView | null>(key)), signal), ...runPolling });
  return <section className={styles.globalControl} aria-label="Global run control">
    {active.data && <Link to={`/engagements/${active.data.engagement_id}/stream`}>Engagement {active.data.engagement_id} · Run {active.data.run_id} · {active.data.state} · revision {active.data.revision} · generation {active.data.generation}</Link>}
    <RunStop run={active.data} label="Stop active run" />
    <button type="button" onClick={() => { void active.refetch(); }}>Read active run</button>
    {(active.isError || !active.data) && <p>{active.isError ? 'Active run unavailable or stale; Stop can target only the last observed identity.' : active.isPending ? 'Reading active run.' : 'No active run observed.'} No shutdown acknowledged. Local fallback: <code>omnis stop</code>.</p>}
  </section>;
}
