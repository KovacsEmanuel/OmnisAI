import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router';
import { api } from '../../shared/api/client';
import type { SelectedDraft } from '../../shared/api/projections';
import type { Receipt, RunCommand, StartRun, RunView, RunSummary, EventPage, Attempt, UsageSummary, UsageTotals, Ref } from '../../shared/api/runs';
import { runCommandFits, runPolling as polling, checkRunProgress, runTerminal, usageFields, sameRef } from '../../shared/api/runs';
import { RunStop } from './GlobalStop';
import { ApiError, isUuid } from '../../shared/api/errors';
import { useSession } from '../bootstrap/BrowserSession';
import { remembered, remember, sessionScope } from './SettingsModels';
import styles from './Engagement.module.css';

function UsageAmounts({ totals }: { totals: UsageTotals }) {
  return <><p>Allocations: {totals.dispatches} · without observation: {totals.unobserved_dispatches}</p><dl>{usageFields.map(key => <div key={key}><dt>{key}</dt><dd>{totals[key].value ?? 'UNKNOWN'} · {totals[key].state} · {totals[key].observed_dispatches}/{totals.dispatches} observed</dd></div>)}</dl></>;
}
function UsageReadback({ usage }: { usage: UsageSummary }) {
  return <><p>{usage.accounting_policy} · full {usage.scope} aggregate, independent of bounded detail. Allocations are not a paid-call count. Unknown is not zero; partial values cover only observed dispatches. Cost is observed only, without an inferred currency or estimate. Cache and reasoning are components, not extra total tokens.</p><UsageAmounts totals={usage.totals} />{usage.roles.map(role => <section key={role.role} aria-label={`${role.role} usage`}><h4>{role.role} · {role.configured_model}</h4><p>connection {role.connection_id} · revision {role.connection_revision}</p><UsageAmounts totals={role.totals} /></section>)}</>;
}

function refLabel(ref: Ref) { return `${ref.kind} · ${ref.id} · revision ${ref.revision} · ${ref.digest} · instance ${ref.instance_id}`; }

export function RunPanel({ draft, stream, children }: { draft: SelectedDraft; stream: boolean; children?: ReactNode }) {
  const { session, transition, readPrivate, commitPrivate } = useSession();
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
  const [params, setParams] = useSearchParams();
  const [page, setPage] = useState<{ run: string | undefined; cursors: number[] } | null>(null);
  const pointer = `omnis-run-command-${draft.engagement_id}`;
  useEffect(() => {
    let current = true;
    const csrf = session.data?.csrf_token;
    if (!csrf) return;
    void sessionScope(csrf).then(value => { if (current) commitPrivate(() => { setScope(value); const old = remembered(pointer, value); if (isUuid(old)) setPending(old); }, lifetime.current.signal); }).catch(() => { if (current) commitPrivate(() => { setMessage('Session command recovery unavailable. Nothing was sent.'); }, lifetime.current.signal); });
    return () => { current = false; };
  }, [pointer, session.data?.csrf_token, commitPrivate]);
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
  const viewKeys = ['run', 'attempt', 'source', 'after', 'kind', 'actor', 'agent-state'];
  const kinds = ['started', 'decision', 'tool_called', 'tool_result', 'result', 'control', 'question', 'answer'];
  const states = ['RUNNING', 'SUCCEEDED', 'INCONCLUSIVE', 'FAILED', 'CANCELLED', 'NEEDS_RECONCILIATION'];
  const hasView = viewKeys.some(key => params.has(key));
  const viewValid = !hasView || (params.get('run') === runId && isUuid(params.get('run')) &&
    viewKeys.every(key => params.getAll(key).length <= 1) &&
    (!params.has('attempt') || isUuid(params.get('attempt'))) &&
    (!params.has('source') || (isUuid(params.get('source')) && isUuid(params.get('attempt')) && params.get('source') !== params.get('attempt'))) &&
    (!params.has('after') || (/^(0|[1-9][0-9]{0,15})$/.test(params.get('after') ?? '') && Number.isSafeInteger(Number(params.get('after'))))) &&
    (!params.has('kind') || kinds.includes(params.get('kind') ?? '')) &&
    (!params.has('actor') || params.get('actor') === 'none' || isUuid(params.get('actor'))) &&
    (!params.has('agent-state') || states.includes(params.get('agent-state') ?? '')));
  const selected = viewValid && !currentRun.isError ? params.get('attempt') : null;
  const consumptionLink = viewValid ? params.get('source') : null;
  const cursors = page?.run === runId ? page?.cursors ?? [] : [];
  const after = viewValid ? Number(params.get('after') ?? 0) : 0;
  const filter = { kind: viewValid ? params.get('kind') ?? '' : '', actor: viewValid ? params.get('actor') ?? '' : '', state: viewValid ? params.get('agent-state') ?? '' : '' };
  function updateView(values: Record<string, string | null>) {
    const next = new URLSearchParams(params);
    if (!viewValid) viewKeys.forEach(key => next.delete(key));
    for (const [key, value] of Object.entries(values)) { if (value) next.set(key, value); else next.delete(key); }
    if (runId) next.set('run', runId);
    setParams(next, { replace: true });
  }
  const setSelected = (attempt: string | null, source: string | null = null) => updateView({ attempt, source });
  const setAfter = (after: number) => { setPage({ run: runId, cursors: after === 0 ? [] : [...cursors, after] }); updateView({ after: after ? String(after) : null }); };
  const summary = useQuery({ queryKey: ['private', 'run-summary', runId], queryFn: ({ signal }) => { if (!runId) throw new ApiError('INVALID_INPUT'); return readPrivate(async () => { const result = await api.runSummary(runId, signal); checkRunProgress(result.run, client.getQueryData<RunSummary>(['private', 'run-summary', runId])?.run); checkRunProgress(result.run, client.getQueryData<RunView | null>(currentKey)); return result; }, signal); }, enabled: enabled && !!runId, ...polling });
  const summaryReady = summary.isSuccess && summary.data.run.run_id === runId && summary.data.run.instance_id === currentRun.data?.instance_id;
  function actorMatches(result: Attempt, observed: RunSummary | undefined) {
    if (!observed || observed.run.run_id !== runId || observed.run.instance_id !== currentRun.data?.instance_id || result.instance_id !== observed.run.instance_id) return false;
    const roster = observed.attempts.find(item => item.attempt_id === result.attempt_id);
    // An already loaded bounded roster may legitimately omit an event-selected attempt.
    return !roster || (result.task_id === roster.task_id && result.role === roster.role && result.configured_model === roster.configured_model);
  }
  const events = useQuery({ queryKey: ['private', 'run-events', runId, after], queryFn: ({ signal }) => { if (!runId) throw new ApiError('INVALID_INPUT'); return readPrivate(async () => { const result = await api.runEvents(runId, after, signal); const previous = client.getQueryData<EventPage>(['private', 'run-events', runId, after]); if (previous && result.through_cursor < previous.through_cursor) throw new ApiError('INVALID_RESPONSE'); return result; }, signal); }, enabled: enabled && !!runId && stream, ...polling });
  const inspector = useQuery({ queryKey: ['private', 'run-attempt', runId, selected, consumptionLink], queryFn: ({ signal }) => {
    if (!runId || !selected) throw new ApiError('INVALID_INPUT');
    return readPrivate(async () => {
      const validateActor = (result: Attempt) => {
        const key = ['private', 'run-summary', runId];
        if (client.getQueryState(key)?.status !== 'success' || !actorMatches(result, client.getQueryData<RunSummary>(key))) throw new ApiError('INVALID_RESPONSE');
      };
      // URL pointers carry no authority: reconstruct consumption from the worker on every read.
      const source = consumptionLink ? await api.runAttempt(runId, consumptionLink, signal) : null;
      if (source) {
        validateActor(source);
        if (!source.result || !source.result_ref || !source.consumption?.decision_ref || source.consumption.consumer_attempt_id !== selected) throw new ApiError('INVALID_RESPONSE');
      }
      const result = await api.runAttempt(runId, selected, signal);
      if (source) validateActor(source);
      validateActor(result);
      if (source && (result.role !== 'BRAIN' || !result.decision || !result.result_ref || !source.result_ref || !source.consumption?.decision_ref || !sameRef(result.result_ref, source.consumption.decision_ref) || !result.decision.consumed_refs.some(ref => sameRef(ref, source.result_ref!)))) throw new ApiError('INVALID_RESPONSE');
      return { result, source };
    }, signal);
  }, enabled: enabled && !!runId && !!selected && stream && summaryReady, ...polling });
  const inspectionMatches = !!inspector.data && actorMatches(inspector.data.result, summary.data) && (!inspector.data.source || actorMatches(inspector.data.source, summary.data));
  const rosterMismatch = summaryReady && !!inspector.data && !inspectionMatches;
  const detail = selected && summaryReady && inspectionMatches && !(consumptionLink && inspector.isError) ? inspector.data?.result : undefined;
  const inspectorHeading = useRef<HTMLHeadingElement>(null);
  const runHeading = useRef<HTMLHeadingElement>(null);
  const selectionTrigger = useRef<HTMLButtonElement | null>(null);
  useEffect(() => { if (detail?.attempt_id && (consumptionLink || window.matchMedia?.('(max-width: 1023px)')?.matches)) inspectorHeading.current?.focus(); }, [consumptionLink, detail?.attempt_id]);
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
    const signal = lifetime.current.signal;
    try {
      if (!commitPrivate(() => {
        busy.current = true;
        setSending(true); setPending(commandId); setMessage('Command pending; waiting for persisted receipt');
        remember(pointer, scope, commandId);
      }, signal)) return null;
      const receipt = await readPrivate(action, signal);
      if (!commitPrivate(() => { remember(pointer, scope, null); setPending(null); setMessage(`${receipt.state} · ${receipt.command_id}`); }, signal)) return null;
      await client.invalidateQueries({ queryKey: ['private'] });
      return receipt;
    } catch (error) {
      commitPrivate(() => {
        const refused = error instanceof ApiError && ['REVISION_CONFLICT', 'GENERATION_CONFLICT', 'AUTHORITY_DENIED', 'ANSWER_DENIED', 'DATA_DENIED', 'REF_UNAVAILABLE', 'OPERATION_ACTIVE', 'OPERATION_FINISHED', 'CONNECTION_UNAVAILABLE', 'MODEL_NOT_REGISTERED', 'CAPABILITIES_REQUIRED', 'INVALID_INPUT'].includes(error.code);
        if (refused) { remember(pointer, scope, null); setPending(null); setReview(null); setConfirmed(false); }
        setMessage(`${error instanceof ApiError ? error.message : 'Outcome unknown'}. ${refused ? 'Refused; refresh and give fresh explicit consent.' : 'Read the same command; no resend.'}`);
      }, signal);
      return null;
    }
    finally { busy.current = false; commitPrivate(() => { setSending(false); }, signal); }
  }
  async function preflight() {
    const generation = status.data?.generation;
    if (!csrf || !chosen || !selection || generation === undefined || !consent) return;
    const commandId = crypto.randomUUID();
    const receipt = await execute(commandId, () => api.preflightRun({ command_id: commandId, expected_generation: generation, engagement_id: draft.engagement_id, draft_ref: { kind: 'engagement-revision', id: draft.id, revision: draft.revision, digest: draft.digest }, selection_revision: selection.revision, publication_ref: chosen, synthetic_context: context, data_consent: true }, csrf));
    const setupRef = receipt?.setup_ref;
    if (setupRef) commitPrivate(() => {
      const recon = 'recon' in selection ? selection.recon : null;
      setReview({ binding, publication: `${chosen.kind} · ${chosen.id} · revision ${chosen.revision} · ${chosen.digest}`, start: { command_id: crypto.randomUUID(), expected_generation: generation, expected_revision: 1, setup_ref: setupRef }, context, draftRevision: draft.revision, model: `Brain ${(selection.brain ?? selection.default).model}; Recon ${(recon ?? selection.default).model}; selection revision ${selection.revision}` });
      setConfirmed(false);
    }, lifetime.current.signal);
  }
  async function start() {
    if (!review || !confirmed || !csrf || status.isError || !status.data?.admission_open || status.data.generation !== review.start.expected_generation || settings.isError || publications.isError || currentRun.isError) return;
    const receipt = await execute(review.start.command_id, () => api.startRun(review.start, csrf));
    if (receipt) commitPrivate(() => { setReview(null); setConfirmed(false); }, lifetime.current.signal);
  }
  async function command(action: RunCommand['action']) {
    if (!run || !csrf || (action === 'answer' && !answerFits)) return;
    const commandId = crypto.randomUUID();
    await execute(commandId, () => api.runCommand({ action, command_id: commandId, expected_generation: run.generation, expected_revision: run.revision, run_id: run.run_id, question_id: action === 'answer' ? question?.question_id ?? null : null, answer: action === 'answer' ? answer : null }, csrf));
  }
  async function readReceipt() {
    if (!pending || !scope) return;
    try {
      const signal = lifetime.current.signal;
      const receipt = await readPrivate(() => api.runCommandReceipt(pending, signal), signal);
      if (!commitPrivate(() => { remember(pointer, scope, null); setPending(null); setReview(null); setConfirmed(false); setMessage(`${receipt.state} · ${receipt.command_id}. Refresh persisted run; a recovered preflight requires fresh review.`); }, signal)) return;
      await client.invalidateQueries({ queryKey: ['private'] });
    }
    catch { commitPrivate(() => { setMessage('Receipt unavailable; command remains unknown. No automatic resend.'); }, lifetime.current.signal); }
  }
  const attempts = summary.data?.attempts ?? [];
  // shortcut: filters cover only this page; whole-run filtering needs a server query contract.
  const pageEvents = events.data?.events ?? [];
  const eventTypes = [...new Set([filter.kind, ...pageEvents.map(event => event.kind)])].filter(Boolean);
  const actors = [...new Set([filter.actor, ...pageEvents.map(event => event.task_id ?? 'none')])].filter(Boolean);
  const filteredEvents = pageEvents.filter(event => (!filter.kind || event.kind === filter.kind) && (!filter.actor || (event.task_id ?? 'none') === filter.actor));
  const agentButton = (item: Attempt) => <button aria-pressed={selected === item.attempt_id} onClick={event => { selectionTrigger.current = event.currentTarget; setSelected(item.attempt_id); }}><strong>{item.role}</strong> · {item.task_id} · {item.state}{item.parent_task_id ? ` · parent ${item.parent_task_id}` : ''}</button>;
  const rendered = new Set<string>();
  function agentRow(item: Attempt, nested = false): ReactNode {
    if (rendered.has(item.attempt_id)) return null;
    rendered.add(item.attempt_id);
    const children = attempts.filter(child => child.parent_task_id === item.task_id && !rendered.has(child.attempt_id));
    // Keep real nesting, but cap indentation at the baseline's single child level.
    const rows = children.map(child => agentRow(child, true));
    const hasChildren = rows.some(row => row !== null);
    const matches = !filter.state || item.state === filter.state;
    if (!matches && !hasChildren) return null;
    return <li key={item.attempt_id}>{matches ? agentButton(item) : <p className={styles.muted}>Ancestor context: {item.role} · {item.task_id} · {item.state}</p>}{item.parent_task_id && !attempts.some(parent => parent.task_id === item.parent_task_id) && <p>Parent outside this bounded summary: {item.parent_task_id}</p>}{hasChildren && <ul style={nested ? { paddingInlineStart: 0 } : undefined}>{rows}</ul>}</li>;
  }
  return <section className={`${stream ? styles.panel : ''} ${styles.run}`} aria-label="Inert run"><div className={stream ? styles.core : styles.overviewRun}>
    <h2 ref={runHeading} tabIndex={-1}>{stream ? 'Brain stream' : 'Inert run · S1'}</h2>
    <p>Only the selected synthetic context is sent. No target requests, shell or browser tools. Models may make successive calls; 300 seconds per operation, no total LLM cost cap.</p>
    {!run && <p>{currentRun.isPending ? 'Reading persisted run…' : currentRun.isError ? 'Run unavailable; no run state inferred.' : 'No run observed.'}</p>}
    {run && <div className={styles.nowBar}><p>Run {run.run_id} · {run.state} · revision {run.revision} · {run.reason} · owner {coherent?.owner_live ? 'current' : 'unverified'} · phase {coherent ? coherent.phase_active ? 'active' : 'inactive' : 'unknown'} · generation {run.generation}</p><details className={styles.disclosure}><summary>Run snapshot details</summary><p>Setup {run.setup_ref.id} · {run.setup_ref.digest} · owner {run.owner_id} · epoch {run.owner_epoch} · fence {run.fence} · through {run.through_cursor}</p></details></div>}
    {active && <div className={`${styles.providerActions} ${styles.runControls}`}>
      <button disabled={sending || !!pending || run?.state !== 'RUNNING'} onClick={() => { void command('pause'); }}>Pause run</button>
      <button disabled={sending || !!pending || !run || !['PAUSED', 'HOLD'].includes(run.state)} onClick={() => { void command('resume'); }}>Resume run</button>
      <RunStop run={run} />
    </div>}
    {question && <section className={styles.needsYou} aria-label="Needs you"><h3>Needs you · {question.state}</h3><p>{question.text}</p><ul>{question.refs.map(ref => <li key={ref.id}>{ref.kind} · {ref.id} · revision {ref.revision} · {ref.digest}</li>)}</ul>{question.answer_ref && <p>Answer {question.answer_ref.id} · {question.answer_ref.digest} · command {question.command_id}</p>}<details className={styles.disclosure}><summary>Clarification provenance</summary><p>{question.cause} · question {question.question_id} · revision {question.revision} · run revision {run?.revision} · task {question.task_id}</p></details>{question.state === 'PENDING' && <><label>Non-secret clarification<textarea maxLength={2048} value={answer} onChange={event => { setAnswerDraft({ identity: answerIdentity, text: event.target.value }); }} /></label><p>Clarification cannot change scope/ROE, supply secrets or resume HOLD. Complete command limit: 3600 UTF-8 bytes including JSON escaping.</p>{answer && !answerFits && <p role="alert">Clarification exceeds the command limit or contains invalid text. Nothing was sent.</p>}<button disabled={!answer.trim() || !answerFits || sending || !!pending || run?.state !== 'RUNNING'} onClick={() => { void command('answer'); }}>Submit clarification</button></>}</section>}
    {!stream && !question && <section className={styles.nowBar} aria-label="Needs you"><h3>Needs you</h3><p>{coherent ? 'No clarification recorded in this run snapshot.' : 'Clarifications UNKNOWN until a coherent run snapshot is read.'}</p></section>}
    {children}
    {summary.data && <section aria-label="Run accounting" className={styles.accounting}><h3>Run accounting <span className={styles.badge}>MONITOR</span></h3><p className={styles.muted}>Snapshot {summary.data.as_of} · run revision {summary.data.run.revision}{summary.isError || !coherent ? ' · stale or unverified' : ''}</p>
      <dl className={styles.usageMetrics}>{(['total_tokens', 'cost_observed'] as const).map(key => <div key={key}><dt>{key === 'total_tokens' ? 'Total tokens' : 'Observed cost · no inferred currency'}</dt><dd>{summary.data.usage.totals[key].value ?? 'UNKNOWN'} <small>{summary.data.usage.totals[key].state} · {summary.data.usage.totals[key].observed_dispatches}/{summary.data.usage.totals.dispatches} observed</small></dd></div>)}<div><dt>Dispatch allocations · not paid calls</dt><dd>{summary.data.usage.totals.dispatches}<small>{summary.data.usage.totals.unobserved_dispatches} without observation</small></dd></div></dl>
      <details className={styles.disclosure}><summary>Exact accounting & provenance</summary><UsageReadback usage={summary.data.usage} /></details>
    </section>}
    {!active && !stream && <section className={styles.preflight} aria-label="New inert run setup"><h3>New inert run · explicit preflight</h3>
      <label>Qualified core publication<select value={publication} onChange={event => { setPublication(event.target.value); setReview(null); setConsent(false); }}><option value="">Choose an exact published core</option>{publications.data?.map(item => <option key={item.id} value={item.id}>{item.id} · {item.digest}</option>)}</select></label>
      <label>Selected synthetic inert context<textarea value={context} maxLength={1024} onChange={event => { setContext(event.target.value); setReview(null); setConsent(false); }} /></label>
      <label className={styles.fullWidth}><input type="checkbox" checked={consent} onChange={event => { setConsent(event.target.checked); setReview(null); }} />This text is synthetic and non-secret; I approve projecting only this selected context.</label>
      <button disabled={sending || !!pending || !scope || !publication || !context.trim() || !consent || !status.data?.admission_open || status.isError || !settings.data?.selection || settings.isError || publications.isError || currentRun.isPending || currentRun.isError} onClick={() => { void preflight(); }}>Preflight inert run</button>
      {review && <section aria-label="Run preflight confirmation"><h3>Review pinned setup</h3><p>Draft revision {review.draftRevision} · {review.model}</p><p>Pinned generation {review.start.expected_generation} · {review.publication}</p><p>Setup {review.start.setup_ref.id} · {review.start.setup_ref.digest}</p><pre>{review.context}</pre><label><input type="checkbox" checked={confirmed} onChange={event => { setConfirmed(event.target.checked); }} />Confirm model execution with this exact setup and possible provider cost.</label><button disabled={!confirmed || sending || !!pending || !csrf || status.isError || !status.data?.admission_open || status.data.generation !== review.start.expected_generation || settings.isError || publications.isError || currentRun.isError} onClick={() => { void start(); }}>Start inert run</button></section>}
      {review && status.data?.generation !== review.start.expected_generation && <p>Instance generation changed. Repeat preflight and review; the old setup is not rebased.</p>}
      {publications.isError && <p>Published core unavailable. Nothing was started.</p>}
      {publications.data?.length === 0 && <p>No qualified published core is available. Import and Publish are not automatic.</p>}
      {(settings.isError || !selection) && <p>Model selection unavailable. Configure models in Settings before preflight.</p>}
    </section>}
    {stream && <div className={styles.streamWorkspace}><div className={styles.streamFeed}>
      {hasView && !viewValid && !currentRun.isPending && <p role="alert">Stream URL is invalid or belongs to another run. No linked record was accepted. <button onClick={() => updateView({ attempt: null, source: null, after: null, kind: null, actor: null, 'agent-state': null })}>Reset stream view</button></p>}
      <label>Agent state<select value={filter.state} onChange={event => updateView({ 'agent-state': event.target.value })}><option value="">All states</option>{states.map(state => <option key={state}>{state}</option>)}</select></label>
      <p className={styles.muted}>Agent state filters this bounded roster; ancestor context is retained, not an additional matching agent.</p>
      {/* The second pass retains rootless cycles; each bounded-summary attempt renders once. */}
      <ul className={styles.agents} aria-label="Spawned agents">{attempts.filter(item => !attempts.some(parent => parent.task_id === item.parent_task_id)).map(item => agentRow(item))}{attempts.map(item => agentRow(item))}</ul>
      {summary.data?.has_more && <p>Some attempts are omitted from this bounded summary. Page through events to select their exact attempt IDs.</p>}
      {summary.data?.attempts.length === 0 && <p>No spawned agents in this summary.</p>}
      {attempts.length > 0 && filter.state && !attempts.some(item => item.state === filter.state) && <p>No agents match this state in the bounded summary.</p>}
      <p>Filters apply only to the loaded page, not the whole run. Page navigation remains unfiltered.</p>
      <label>Event type<select value={filter.kind} onChange={event => updateView({ kind: event.target.value })}><option value="">All types</option>{eventTypes.map(kind => <option key={kind} value={kind}>{kind}</option>)}</select></label>
      <label>Event actor (task)<select value={filter.actor} onChange={event => updateView({ actor: event.target.value })}><option value="">All actors</option>{actors.map(actor => <option key={actor} value={actor}>{actor === 'none' ? 'No actor recorded' : `Task ${actor}`}</option>)}</select></label>
      <ol className={styles.events} aria-label="Run events">{filteredEvents.map(event => <li key={event.event_id}><div className={styles.eventMeta}><time dateTime={event.created_at}>{event.created_at} UTC</time><span>{attempts.find(item => item.attempt_id === event.attempt_id)?.role ?? (event.task_id || event.attempt_id ? 'Task' : 'No actor recorded')}</span></div><button disabled={!event.attempt_id} onClick={action => { selectionTrigger.current = action.currentTarget; setSelected(event.attempt_id); }}>{event.kind} · {event.summary}</button><details className={styles.disclosure}><summary>Event identity & refs</summary><p>{event.task_id || event.attempt_id ? `Task ${event.task_id ?? 'not recorded'} · attempt ${event.attempt_id ?? 'not recorded'}` : 'No actor recorded'} · {event.event_id}{event.call_id && ` · call ${event.call_id}`}</p>{event.refs.map(ref => <p key={`${ref.kind}:${ref.id}`}>{refLabel(ref)}</p>)}</details></li>)}</ol>
      {events.data && filteredEvents.length === 0 && <p>{filter.kind || filter.actor ? 'No events match these filters on this loaded page.' : 'No events on this loaded page.'}</p>}
      {events.data && <p>Events after {after} · through {events.data.through_cursor} · {events.data.has_more ? 'More events available' : 'End of observed events'} · as of {events.data.as_of}</p>}
      {after > 0 && <button onClick={() => { setAfter(0); }}>First events</button>}
      {after > 0 && <button onClick={() => { const previous = cursors.slice(0, -1); setPage({ run: runId, cursors: previous }); updateView({ after: String(previous.at(-1) ?? 0) }); }}>Previous events</button>}
      {events.data?.has_more && <button disabled={events.isFetching || events.data.through_cursor <= after} onClick={() => { setAfter(events.data?.through_cursor ?? after); }}>Next events</button>}
      </div><aside className={styles.inspectorDock} aria-label="Contextual inspection">
      {!selected && <p className={styles.muted}>Select an agent or event to inspect its persisted result, input and usage.</p>}
      {selected && !summaryReady && <p>Waiting for a run-bound summary before inspection.</p>}
      {selected && summaryReady && inspector.isPending && <p>Loading selected agent…</p>}
      {detail && <section aria-label="Agent inspector">
        <button onClick={() => { setSelected(null); if (selectionTrigger.current?.isConnected) selectionTrigger.current.focus(); else runHeading.current?.focus(); }}>Close inspector</button>
        <h3 ref={inspectorHeading} tabIndex={-1}>{detail.role} · {detail.attempt_id}</h3><p>Run {detail.run_id} · task {detail.task_id} · parent {detail.parent_task_id ?? 'none'} · {detail.state}</p>
        <p>Snapshot {detail.as_of}{inspector.isError ? ' · stale or unavailable' : ''}</p><p>{detail.brief}</p>
        <p>Configured model: {detail.configured_model} · Observed model: {detail.observed_model ?? 'UNKNOWN'}</p>
        <h4>Exact persisted completion</h4><p>Final result: {detail.result_ref ? refLabel(detail.result_ref) : 'Not finalized'}</p>
        {detail.result && <><p>Result status: {detail.result.state} · Completion kind: {detail.result.completion_kind ?? 'UNKNOWN'}</p><pre>{detail.result.summary ?? 'UNKNOWN'}</pre><h4>Retained gaps</h4>{detail.result.gaps.length ? <ul>{detail.result.gaps.map((gap, index) => <li key={index}>{gap}</li>)}</ul> : <p>No retained gaps</p>}<ul>{detail.result.consumed_refs.map(ref => <li key={ref.id}>Consumed input {refLabel(ref)}</li>)}</ul></>}
        {detail.decision && <details className={styles.disclosure} open><summary>Decisions</summary><p>Decision action: {detail.decision.action} · Completion kind: {detail.decision_completion_kind ?? 'UNKNOWN'}</p><pre>{detail.decision.summary}</pre><pre>{detail.decision.detail}</pre><ul>{detail.decision.consumed_refs.map(ref => <li key={ref.id}>Consumed result {refLabel(ref)}</li>)}</ul></details>}
        {!detail.result && !detail.decision && <p>No completion observed</p>}
        <p>Consumption: {detail.consumption ? detail.consumption.decision_ref ? 'CONSUMED' : detail.consumption.held ? 'HELD' : 'PENDING' : 'UNKNOWN / not applicable'}. Read receipt alone is not consumption.</p>
        {detail.consumption?.decision_ref && <p>Consuming decision {refLabel(detail.consumption.decision_ref)}</p>}
        {detail.consumption?.consumer_attempt_id && detail.consumption.decision_ref && detail.result_ref && <button onClick={() => { if (detail.consumption?.consumer_attempt_id && detail.consumption.decision_ref && detail.result_ref) setSelected(detail.consumption.consumer_attempt_id, detail.attempt_id); }}>Inspect consuming Brain · {detail.consumption.consumer_attempt_id}</button>}
        <details className={styles.disclosure}><summary>Prompt & input</summary><h4>Allowed input actually sent</h4><pre>{detail.input_text}</pre><h4>Composed instructions and pinned skills</h4><pre>{detail.instructions}</pre><ul>{detail.input_refs.map(ref => <li key={ref.id}>Input {refLabel(ref)}</li>)}</ul><ul>{detail.skill_refs.map(ref => <li key={ref.id}>Skill {ref.kind} · {ref.id} · revision {ref.revision} · {ref.digest}</li>)}</ul></details>
        <details className={styles.disclosure}><summary>Tools & results</summary><p>Call {detail.call_id ?? 'none'} · tool {detail.tool_arguments ?? 'none'}</p><h4>Persisted tool result</h4><pre>{detail.tool_output ?? 'No tool result'}</pre><p>Read receipt: {detail.read_receipt_ref ? refLabel(detail.read_receipt_ref) : 'Not observed'}</p></details>
        <details className={styles.disclosure}><summary>Usage</summary><section aria-label="Attempt accounting"><h4>Attempt accounting</h4>{detail.usage ? <UsageReadback usage={detail.usage} /> : <p>Usage UNKNOWN</p>}</section>
        <h4>Bounded dispatch observations</h4><p>{detail.dispatches_has_more ? 'More dispatch details omitted; no next-page endpoint. Full aggregate above is not truncated.' : 'All dispatch details in this snapshot.'} Maximum 20 details.</p>
        <ul aria-label="Dispatch observations">{detail.dispatches?.map(dispatch => <li key={dispatch.dispatch_id}>
          <p>{dispatch.dispatch_id} · {dispatch.state}</p><p>Reserved {dispatch.reserved_at ?? 'UNKNOWN'} · sent {dispatch.sent_at ?? 'UNKNOWN'} · settled {dispatch.settled_at ?? 'UNKNOWN'}</p>
          <p>Usage receipt: {dispatch.usage_ref ? refLabel(dispatch.usage_ref) : 'UNKNOWN / not observed'}</p>
          {dispatch.usage ? <><p>{dispatch.usage.role} · configured {dispatch.usage.configured_model} · observed {dispatch.usage.observed_model ?? 'UNKNOWN'} · connection {dispatch.usage.connection_id} · revision {dispatch.usage.connection_revision} · observed at {dispatch.usage.observed_at}</p><h4>Validated measures</h4><pre>{JSON.stringify(dispatch.usage.measures, null, 2)}</pre><h4>Original validated usage</h4><pre>{JSON.stringify(dispatch.usage.reported, null, 2)}</pre></> : <p>No observation receipt; usage UNKNOWN, not zero.</p>}
        </li>)}</ul></details>
      </section>}
      {selected && (inspector.isError || rosterMismatch) && <p role="alert">Selected record unavailable or inconsistent. No linked result was accepted.</p>}
      </aside></div>}
    <output aria-live="polite">{message}</output>
    {pending && <button disabled={sending} onClick={() => { void readReceipt(); }}>Read command receipt</button>}
    <button onClick={() => { void client.invalidateQueries({ queryKey: ['private', 'engagement-run', draft.engagement_id] }); if (runId) { void summary.refetch(); if (stream) { void events.refetch(); if (selected) void inspector.refetch(); } } }}>Refresh run</button>
    {(currentRun.isError || summary.isError || events.isError || inspector.isError) && <p>Run readback unavailable or stale; no state or effects are inferred.</p>}
  </div></section>;
}
