import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import type { SelectedDraft } from '../../shared/api/projections';
import type { Receipt, RunCommand, StartRun, RunView, RunSummary, EventPage, Attempt } from '../../shared/api/runs';
import { runCommandFits, runPolling as polling, checkRunProgress, runTerminal } from '../../shared/api/runs';
import { RunStop } from './GlobalStop';
import { ApiError, isUuid } from '../../shared/api/errors';
import { useSession } from '../bootstrap/BrowserSession';
import { remembered, remember, sessionScope } from './SettingsModels';
import styles from './Engagement.module.css';

export function RunPanel({ draft, stream }: { draft: SelectedDraft; stream: boolean }) {
  const { session, transition, readPrivate } = useSession();
  const client = useQueryClient();
  const enabled = !!session.data && !session.isError && transition === 'idle';
  const [context, setContext] = useState('');
  const [publication, setPublication] = useState('');
  const [consent, setConsent] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [preview, setReview] = useState<{ start: StartRun; context: string; model: string; draftRevision: number; binding: string; publication: string } | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [scope, setScope] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const [answerDraft, setAnswerDraft] = useState({ identity: '', text: '' });
  const lifetime = useRef(new AbortController());
  const busy = useRef(false);
  useEffect(() => { const controller = new AbortController(); lifetime.current = controller; return () => controller.abort(); }, []);
  const [inspected, setInspected] = useState<{ run: string | undefined; attempt: string | null } | null>(null);
  const [page, setPage] = useState<{ run: string | undefined; after: number } | null>(null);
  const pointer = `omnis-run-command-${draft.engagement_id}`;
  useEffect(() => {
    let current = true;
    const csrf = session.data?.csrf_token;
    if (!csrf) return;
    void sessionScope(csrf).then(value => { if (current) { setScope(value); const old = remembered(pointer, value); if (isUuid(old)) setPending(old); } }).catch(() => { if (current) setMessage('Session command recovery unavailable. Nothing was sent.'); });
    return () => { current = false; };
  }, [pointer, session.data?.csrf_token]);
  const status = useQuery({ queryKey: ['instance'], queryFn: ({ signal }) => readPrivate(() => api.instance(signal), signal), enabled, ...polling });
  const settings = useQuery({ queryKey: ['private', 'run-settings'], queryFn: ({ signal }) => readPrivate(() => api.providerKeys(null, signal), signal), enabled, ...polling });
  const publications = useQuery({ queryKey: ['private', 'run-publications'], queryFn: ({ signal }) => readPrivate(() => api.runPublications(signal), signal), enabled, ...polling });
  const chosen = publications.data?.find(item => item.id === publication);
  const selection = settings.data?.selection;
  const binding = JSON.stringify([draft.id, draft.revision, draft.digest, chosen, selection?.revision, context, consent]);
  const review = preview?.binding === binding ? preview : null;
  useEffect(() => { if (preview && preview.binding !== binding) { setReview(null); setConfirmed(false); } }, [binding, preview]);
  const currentKey = ['private', 'engagement-run', draft.engagement_id];
  const currentRun = useQuery({ queryKey: currentKey, queryFn: ({ signal }) => readPrivate(async () => checkRunProgress(await api.engagementRun(draft.engagement_id, signal), client.getQueryData<RunView | null>(currentKey)), signal), enabled, ...polling });
  const runId = currentRun.data?.run_id;
  const selected = inspected?.run === runId ? inspected?.attempt : null;
  const after = page?.run === runId ? page?.after ?? 0 : 0;
  const setSelected = (attempt: string | null) => setInspected({ run: runId, attempt });
  const setAfter = (after: number) => setPage({ run: runId, after });
  const summary = useQuery({ queryKey: ['private', 'run-summary', runId], queryFn: ({ signal }) => { if (!runId) throw new ApiError('INVALID_INPUT'); return readPrivate(async () => { const result = await api.runSummary(runId, signal); checkRunProgress(result.run, client.getQueryData<RunSummary>(['private', 'run-summary', runId])?.run); checkRunProgress(result.run, client.getQueryData<RunView | null>(currentKey)); return result; }, signal); }, enabled: enabled && !!runId, ...polling });
  const events = useQuery({ queryKey: ['private', 'run-events', runId, after], queryFn: ({ signal }) => { if (!runId) throw new ApiError('INVALID_INPUT'); return readPrivate(async () => { const result = await api.runEvents(runId, after, signal); const previous = client.getQueryData<EventPage>(['private', 'run-events', runId, after]); if (previous && result.through_cursor < previous.through_cursor) throw new ApiError('INVALID_RESPONSE'); return result; }, signal); }, enabled: enabled && !!runId && stream, ...polling });
  const inspector = useQuery({ queryKey: ['private', 'run-attempt', runId, selected], queryFn: ({ signal }) => { if (!runId || !selected) throw new ApiError('INVALID_INPUT'); return readPrivate(() => api.runAttempt(runId, selected, signal), signal); }, enabled: enabled && !!runId && !!selected && stream, ...polling });
  const run = summary.data && summary.data.run.revision >= (currentRun.data?.revision ?? 0) ? summary.data.run : currentRun.data;
  const active = !!run && !runTerminal(run);
  const csrf = session.data?.csrf_token;
  const coherent = summary.data?.run.revision === run?.revision ? summary.data : undefined;
  const question = coherent?.question;
  const answerIdentity = `${runId}:${question?.question_id}:${question?.revision}:${run?.revision}`;
  const answer = answerDraft.identity === answerIdentity ? answerDraft.text : '';
  const answerPayload: RunCommand | null = run && question ? { action: 'answer', command_id: question.question_id, expected_generation: run.generation, expected_revision: run.revision, run_id: run.run_id, question_id: question.question_id, answer } : null;
  const answerFits = !!answerPayload && runCommandFits(answerPayload);
  async function execute(commandId: string, action: () => Promise<Receipt>): Promise<Receipt | null> {
    if (!scope || busy.current || pending) return null;
    busy.current = true;
    const signal = lifetime.current.signal;
    setSending(true); setPending(commandId); setMessage('Command pending; waiting for persisted receipt');
    try {
      remember(pointer, scope, commandId);
      const receipt = await readPrivate(action, signal);
      remember(pointer, scope, null); setPending(null); setMessage(`${receipt.state} · ${receipt.command_id}`);
      await client.invalidateQueries({ queryKey: ['private'] });
      return receipt;
    } catch (error) {
      if (signal.aborted) return null;
      const refused = error instanceof ApiError && ['REVISION_CONFLICT', 'GENERATION_CONFLICT', 'AUTHORITY_DENIED', 'ANSWER_DENIED', 'REF_UNAVAILABLE', 'OPERATION_ACTIVE', 'CAPABILITIES_REQUIRED', 'INVALID_INPUT'].includes(error.code);
      if (refused) { remember(pointer, scope, null); setPending(null); setReview(null); setConfirmed(false); }
      setMessage(`${error instanceof ApiError ? error.message : 'Outcome unknown'}. ${refused ? 'Refused; refresh and give fresh explicit consent.' : 'Read the same command; no resend.'}`); return null;
    }
    finally { busy.current = false; if (!signal.aborted) setSending(false); }
  }
  async function preflight() {
    const generation = status.data?.generation;
    if (!csrf || !chosen || !selection || generation === undefined || !consent) return;
    const commandId = crypto.randomUUID();
    const receipt = await execute(commandId, () => api.preflightRun({ command_id: commandId, expected_generation: generation, engagement_id: draft.engagement_id, draft_ref: { kind: 'engagement-revision', id: draft.id, revision: draft.revision, digest: draft.digest }, selection_revision: selection.revision, publication_ref: chosen, synthetic_context: context, data_consent: true }, csrf));
    if (receipt?.setup_ref) {
      const recon = 'recon' in selection ? selection.recon : null;
      setReview({ binding, publication: `${chosen.kind} · ${chosen.id} · revision ${chosen.revision} · ${chosen.digest}`, start: { command_id: crypto.randomUUID(), expected_generation: generation, expected_revision: 1, setup_ref: receipt.setup_ref }, context, draftRevision: draft.revision, model: `Brain ${(selection.brain ?? selection.default).model}; Recon ${(recon ?? selection.default).model}; selection revision ${selection.revision}` });
      setConfirmed(false);
    }
  }
  async function start() {
    if (!review || !confirmed || !csrf || status.isError || !status.data?.admission_open || status.data.generation !== review.start.expected_generation || settings.isError || publications.isError || currentRun.isError) return;
    const receipt = await execute(review.start.command_id, () => api.startRun(review.start, csrf));
    if (receipt) { setReview(null); setConfirmed(false); }
  }
  async function command(action: RunCommand['action']) {
    if (!run || !csrf || (action === 'answer' && !answerFits)) return;
    const commandId = crypto.randomUUID();
    await execute(commandId, () => api.runCommand({ action, command_id: commandId, expected_generation: run.generation, expected_revision: run.revision, run_id: run.run_id, question_id: action === 'answer' ? question?.question_id ?? null : null, answer: action === 'answer' ? answer : null }, csrf));
  }
  async function readReceipt() {
    if (!pending || !scope) return;
    try { const signal = lifetime.current.signal; const receipt = await readPrivate(() => api.runCommandReceipt(pending, signal), signal); remember(pointer, scope, null); setPending(null); setReview(null); setConfirmed(false); setMessage(`${receipt.state} · ${receipt.command_id}. Refresh persisted run; a recovered preflight requires fresh review.`); await client.invalidateQueries({ queryKey: ['private'] }); }
    catch { if (!lifetime.current.signal.aborted) setMessage('Receipt unavailable; command remains unknown. No automatic resend.'); }
  }
  const attempts = summary.data?.attempts ?? [];
  const agentButton = (item: Attempt) => <button aria-pressed={selected === item.attempt_id} onClick={() => { setSelected(item.attempt_id); }}>{item.role} · {item.task_id} · {item.state}{item.parent_task_id ? ` · parent ${item.parent_task_id}` : ''}</button>;
  return <section className={`${styles.panel} ${styles.run}`} aria-label="Inert run"><div className={styles.core}>
    <h2>{stream ? 'Brain stream' : 'Inert run · S1'}</h2>
    <p>Only the selected synthetic context is sent. No target requests, shell or browser tools. Models may make successive calls; 300 seconds per operation, no total LLM cost cap.</p>
    {!run && <p>{currentRun.isPending ? 'Reading persisted run…' : currentRun.isError ? 'Run unavailable; no run state inferred.' : 'No run observed.'}</p>}
    {run && <p>Run {run.run_id} · {run.state} · revision {run.revision} · {run.reason} · owner {coherent?.owner_live ? 'current' : 'unverified'} · phase {coherent ? coherent.phase_active ? 'active' : 'inactive' : 'unknown'} · setup {run.setup_ref.id} · {run.setup_ref.digest} · generation {run.generation}</p>}
    {active && <div className={styles.providerActions}>
      <button disabled={sending || !!pending || run?.state !== 'RUNNING'} onClick={() => { void command('pause'); }}>Pause run</button>
      <button disabled={sending || !!pending || !run || !['PAUSED', 'HOLD'].includes(run.state)} onClick={() => { void command('resume'); }}>Resume run</button>
      <RunStop run={run} />
    </div>}
    {!active && !stream && <>
      <label>Qualified core publication<select value={publication} onChange={event => { setPublication(event.target.value); setReview(null); setConsent(false); }}><option value="">Choose an exact published core</option>{publications.data?.map(item => <option key={item.id} value={item.id}>{item.id} · {item.digest}</option>)}</select></label>
      <label>Selected synthetic inert context<textarea value={context} maxLength={1024} onChange={event => { setContext(event.target.value); setReview(null); setConsent(false); }} /></label>
      <label><input type="checkbox" checked={consent} onChange={event => { setConsent(event.target.checked); setReview(null); }} />This text is synthetic and non-secret; I approve projecting only this selected context.</label>
      <button disabled={sending || !!pending || !scope || !publication || !context.trim() || !consent || !status.data?.admission_open || status.isError || !settings.data?.selection || settings.isError || publications.isError || currentRun.isPending || currentRun.isError} onClick={() => { void preflight(); }}>Preflight inert run</button>
      {review && <section aria-label="Run preflight confirmation"><h3>Review pinned setup</h3><p>Draft revision {review.draftRevision} · {review.model}</p><p>Pinned generation {review.start.expected_generation} · {review.publication}</p><p>Setup {review.start.setup_ref.id} · {review.start.setup_ref.digest}</p><pre>{review.context}</pre><label><input type="checkbox" checked={confirmed} onChange={event => { setConfirmed(event.target.checked); }} />Confirm model execution with this exact setup and possible provider cost.</label><button disabled={!confirmed || sending || !!pending || !csrf || status.isError || !status.data?.admission_open || status.data.generation !== review.start.expected_generation || settings.isError || publications.isError || currentRun.isError} onClick={() => { void start(); }}>Start inert run</button></section>}
      {review && status.data?.generation !== review.start.expected_generation && <p>Instance generation changed. Repeat preflight and review; the old setup is not rebased.</p>}
      {publications.isError && <p>Published core unavailable. Nothing was started.</p>}
      {publications.data?.length === 0 && <p>No qualified published core is available. Import and Publish are not automatic.</p>}
      {(settings.isError || !selection) && <p>Model selection unavailable. Configure models in Settings before preflight.</p>}
    </>}
    {question && <section aria-label="Needs you"><h3>Needs you · {question.state}</h3><p>{question.text}</p><ul>{question.refs.map(ref => <li key={ref.id}>{ref.kind} · {ref.id} · revision {ref.revision} · {ref.digest}</li>)}</ul>{question.answer_ref && <p>Answer {question.answer_ref.id} · {question.answer_ref.digest} · command {question.command_id}</p>}<p>{question.cause} · question {question.question_id} · revision {question.revision} · run revision {run?.revision} · task {question.task_id}</p>{question.state === 'PENDING' && <><label>Non-secret clarification<textarea maxLength={2048} value={answer} onChange={event => { setAnswerDraft({ identity: answerIdentity, text: event.target.value }); }} /></label><p>Clarification cannot change scope/ROE, supply secrets or resume HOLD. Complete command limit: 3600 UTF-8 bytes including JSON escaping.</p>{answer && !answerFits && <p role="alert">Clarification exceeds the command limit or contains invalid text. Nothing was sent.</p>}<button disabled={!answer.trim() || !answerFits || sending || !!pending || run?.state !== 'RUNNING'} onClick={() => { void command('answer'); }}>Submit clarification</button></>}</section>}
    {stream && <>
      <ul aria-label="Spawned agents">{attempts.filter(item => !attempts.some(parent => parent.task_id === item.parent_task_id)).map(item => <li key={item.attempt_id}>{agentButton(item)}{item.parent_task_id && <p>Parent outside this bounded summary: {item.parent_task_id}</p>}<ul>{attempts.filter(child => child.parent_task_id === item.task_id).map(child => <li key={child.attempt_id}>{agentButton(child)}</li>)}</ul></li>)}</ul>
      {summary.data?.has_more && <p>Some attempts are omitted from this bounded summary. Page through events to select their exact attempt IDs.</p>}
      {summary.data?.attempts.length === 0 && <p>No spawned agents in this summary.</p>}
      <ol aria-label="Run events">{events.data?.events.map(event => <li key={event.event_id}><button disabled={!event.attempt_id} onClick={() => { setSelected(event.attempt_id); }}>{event.kind} · {event.summary}</button> · {event.event_id}{event.call_id && ` · call ${event.call_id}`}</li>)}</ol>
      {events.data && <p>Events after {after} · through {events.data.through_cursor} · {events.data.has_more ? 'More events available' : 'End of observed events'} · as of {events.data.as_of}</p>}
      {after > 0 && <button onClick={() => { setAfter(0); }}>First events</button>}
      {events.data?.has_more && <button disabled={events.isFetching || events.data.through_cursor <= after} onClick={() => { setAfter(events.data?.through_cursor ?? after); }}>Next events</button>}
      {selected && inspector.isPending && <p>Loading selected agent…</p>}
      {selected && inspector.data && <section aria-label="Agent inspector"><h3>{inspector.data.role} · {inspector.data.attempt_id}</h3><p>Run {inspector.data.run_id} · task {inspector.data.task_id} · parent {inspector.data.parent_task_id ?? 'none'} · {inspector.data.state}</p><p>{inspector.data.brief}</p><ul>{inspector.data.input_refs.map(ref => <li key={ref.id}>Input {ref.kind} · {ref.id} · revision {ref.revision} · {ref.digest}</li>)}</ul><p>Configured model: {inspector.data.configured_model} · Observed model: {inspector.data.observed_model ?? 'UNKNOWN'}</p><ul>{inspector.data.skill_refs.map(ref => <li key={ref.id}>Skill {ref.id} · {ref.digest}</li>)}</ul><p>{inspector.data.result_summary}</p><h4>Allowed input actually sent</h4><pre>{inspector.data.input_text}</pre><h4>Composed instructions and pinned skills</h4><pre>{inspector.data.instructions}</pre><p>Call {inspector.data.call_id ?? 'none'} · tool {inspector.data.tool_arguments ?? 'none'}</p><h4>Persisted tool result</h4><pre>{inspector.data.tool_output ?? 'No tool result'}</pre><p>Read receipt: {inspector.data.read_receipt_ref ? `${inspector.data.read_receipt_ref.id} · ${inspector.data.read_receipt_ref.digest}` : 'Not observed'}</p><p>Final result: {inspector.data.result_ref ? `${inspector.data.result_ref.id} · ${inspector.data.result_ref.digest}` : 'Not finalized'}</p></section>}
    </>}
    <output aria-live="polite">{message}</output>
    {pending && <button disabled={sending} onClick={() => { void readReceipt(); }}>Read command receipt</button>}
    <button onClick={() => { void client.invalidateQueries({ queryKey: ['private', 'engagement-run', draft.engagement_id] }); if (runId) { void summary.refetch(); if (stream) void events.refetch(); } }}>Refresh run</button>
    {(currentRun.isError || summary.isError || events.isError || inspector.isError) && <p>Run readback unavailable or stale; no state or effects are inferred.</p>}
  </div></section>;
}
