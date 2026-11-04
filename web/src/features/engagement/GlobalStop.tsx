import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router';
import { api } from '../../shared/api/client';
import { ApiError, isRecord, isUuid } from '../../shared/api/errors';
import { runPolling, checkRunProgress, runTerminal } from '../../shared/api/runs';
import type { RunView } from '../../shared/api/runs';
import { useSession } from '../bootstrap/BrowserSession';
import { remembered, remember, sessionScope } from './SettingsModels';
import styles from './Engagement.module.css';

type PendingStop = { command: string; run: string };
const pointer = 'omnis-run-stop';
export function RunStop({ run, label = 'Stop run' }: { run: RunView | null | undefined; label?: string }) {
  const { session, readPrivate } = useSession();
  const client = useQueryClient();
  const [pending, setPending] = useState<PendingStop | null>(null);
  const [scope, setScope] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState('');
  const busy = useRef(false);
  const hasRun = !!run;
  const lifetime = useRef(new AbortController());
  useEffect(() => {
    const controller = new AbortController(); lifetime.current = controller;
    const csrf = session.data?.csrf_token;
    let recovery = false;
    try { recovery = sessionStorage.getItem(pointer) !== null; } catch { setMessage('Stop recovery storage unavailable. Use local CLI omnis stop if needed.'); }
    if (csrf && (hasRun || recovery)) void sessionScope(csrf).then(value => {
      if (controller.signal.aborted) return;
      setScope(value);
      const old = remembered(pointer, value);
      if (isRecord(old) && isUuid(old.command) && isUuid(old.run)) setPending({ command: old.command, run: old.run });
    }).catch(() => { if (!controller.signal.aborted) setMessage('Stop unacknowledged: session recovery unavailable. Use local CLI omnis stop if needed.'); });
    return () => controller.abort();
  }, [session.data?.csrf_token, hasRun]);
  async function settle(target: PendingStop, send: (() => ReturnType<typeof api.runCommand>) | null) {
    if (!scope || busy.current) return;
    busy.current = true; setSending(true);
    const signal = lifetime.current.signal;
    try {
      if (send) { remember(pointer, scope, target); setPending(target); setMessage(`Stop pending · run ${target.run}`); }
      const receipt = await readPrivate(send ?? (() => api.runCommandReceipt(target.command, signal)), signal);
      if (receipt.run_id !== target.run) throw new ApiError('INVALID_RESPONSE');
      remember(pointer, scope, null); setPending(null);
      setMessage(`${receipt.state} · Stop run ${target.run} · command ${target.command}. Read run state; this is not confirmation of STOPPED.`);
      await client.invalidateQueries({ queryKey: ['private'] });
    } catch (error) {
      if (signal.aborted) return;
      const refused = send && error instanceof ApiError && ['REVISION_CONFLICT', 'GENERATION_CONFLICT', 'AUTHORITY_DENIED', 'INVALID_INPUT'].includes(error.code);
      if (refused) { remember(pointer, scope, null); setPending(null); }
      setMessage(refused ? `Stop refused · run ${target.run}. Read the run; no automatic retry.` : `Stop outcome unknown · run ${target.run} · command ${target.command}. Read this receipt; no resend. Use local CLI omnis stop if needed.`);
    } finally { busy.current = false; if (!signal.aborted) setSending(false); }
  }
  function stop() {
    const csrf = session.data?.csrf_token;
    if (!run || !csrf || !scope || pending || busy.current || runTerminal(run) || run.state === 'STOPPING') return;
    const payload = { action: 'stop', command_id: crypto.randomUUID(), run_id: run.run_id, expected_revision: run.revision, expected_generation: run.generation, question_id: null, answer: null } as const;
    void settle({ command: payload.command_id, run: run.run_id }, () => api.runCommand(payload, csrf));
  }
  return <>
    <button type="button" disabled={!run || runTerminal(run) || run.state === 'STOPPING' || !scope || sending || !!pending} onClick={stop}>{label}</button>
    {pending && <><p>Unacknowledged Stop · run {pending.run} · command {pending.command}</p><button type="button" disabled={sending} onClick={() => { void settle(pending, null); }}>Read Stop receipt</button></>}
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
