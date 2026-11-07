import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useLocation, useNavigate } from 'react-router';
import { api } from '../../shared/api/client';
import { isFullDraft, isUtcTimestamp } from '../../shared/api/drafts';
import type { Draft, Revision } from '../../shared/api/drafts';
import { ApiError, isRecord } from '../../shared/api/errors';
import type { FieldError } from '../../shared/api/errors';
import { useSession } from '../bootstrap/BrowserSession';
import { dashboardCopy } from '../dashboard/copy';
import { engagementCopy } from './copy';
import { Field, errorText, fieldId, focusField } from './WizardFields';
import { ApplicationStep, RulesStep, ReviewStep } from './WizardSections';
import { DatePicker } from './DatePicker';
import styles from './Wizard.module.css';
import { observeControl } from '../../shared/uiDiagnostics';

const DEFAULT_OBJECTIVE = 'Assess the authorized Web/API surface within the selected profile.';
const steps = ['Target & permission', 'Application context', 'Identities', 'Rules & budgets', 'Review & preflight'];
const empty = (): Draft => ({
  name: '', authorization: { owner: '', statement: '', valid_from: null, valid_until: null },
  scope: [{ origin: '', port: 443, path_prefix: '/', exclusions: [], access: 'BLOCKED' }],
  assessment_mode: 'FULL_ASSESSMENT', objective_text: DEFAULT_OBJECTIVE, objective_constraints: [],
  workflow_profile_ref: null,
  application_context: { seed_urls: [], priority_workflows: [], test_objects: [], import_ref: null },
  effect_rules: [], budgets: { max_requests: 0, max_duration_seconds: 0, max_storage_bytes: 0, validation_reserved_requests: 0, max_model_calls: 0 },
  data_policy: { model_projection: 'NONE', research_egress: 'NONE', retention_days: 0 },
  business_matrix: [], business_rules_ref: null,
});
function editableLegacy(payload: Revision['payload']): Draft {
  const defaults = empty();
  return { ...payload, application_context: defaults.application_context, effect_rules: defaults.effect_rules,
    budgets: defaults.budgets, data_policy: defaults.data_policy, business_matrix: defaults.business_matrix,
    business_rules_ref: null };
}
function equal(a: unknown, b: unknown): boolean {
  if (Array.isArray(a) || Array.isArray(b)) return Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((item, i) => equal(item, b[i]));
  if (isRecord(a) || isRecord(b)) return isRecord(a) && isRecord(b) && Object.keys(a).length === Object.keys(b).length &&
    Object.keys(a).every(key => Object.hasOwn(b, key) && equal(a[key], b[key]));
  return a === b;
}
function localErrors(form: Draft): FieldError[] {
  const { valid_from: from, valid_until: until } = form.authorization;
  if (from !== null || until !== null) {
    if (!isUtcTimestamp(from)) return [{ field: 'authorization.valid_from', code: from === '' ? 'REQUIRED' : 'INVALID_VALUE' }];
    if (!isUtcTimestamp(until) || Date.parse(until) <= Date.parse(from))
      return [{ field: 'authorization.valid_until', code: until === '' ? 'REQUIRED' : 'INVALID_VALUE' }];
  }
  const count = Array.from(form.objective_text).length;
  if (count > 8192 || new TextEncoder().encode(form.objective_text).length > 32768)
    return [{ field: 'objective_text', code: 'TOO_LONG' }];
  if (!count || (form.assessment_mode === 'FOCUSED_TEST' && !form.objective_text.trim()))
    return [{ field: 'objective_text', code: 'REQUIRED' }];
  if (form.budgets.max_requests < 0)
    return [{ field: 'budgets.max_requests', code: 'INVALID_VALUE' }];
  if (form.budgets.validation_reserved_requests > form.budgets.max_requests)
    return [{ field: 'budgets.validation_reserved_requests', code: 'INVALID_VALUE' }];
  return [];
}
function scopeAccess(value: string): Draft['scope'][number]['access'] {
  if (value === 'BLOCKED' || value === 'VISIT_ONLY' || value === 'ATTACKABLE') return value;
  throw new ApiError('INVALID_INPUT');
}
function constraintKind(value: string): Draft['objective_constraints'][number]['kind'] {
  if (value === 'READ_ONLY' || value === 'EXCLUDE_FEATURE' || value === 'REQUIRE_CRITERION') return value;
  throw new ApiError('INVALID_INPUT');
}
function stepFor(path: string) {
  if (path.startsWith('application_context') || path.startsWith('business_matrix') || path === 'business_rules_ref') return 1;
  if (path.startsWith('effect_rules') || path.startsWith('budgets') || path.startsWith('data_policy')) return 3;
  return 0;
}
export function Wizard({ id }: { id?: string }) {
  const { session, transition, readPrivate } = useSession();
  const client = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const initialStep = isRecord(location.state) && typeof location.state.step === 'number' && Number.isInteger(location.state.step) &&
    location.state.step >= 0 && location.state.step < steps.length ? location.state.step : 0;
  const [step, setStep] = useState(initialStep);
  const [form, setForm] = useState<Draft>(empty);
  const [defaultUntouched, setDefaultUntouched] = useState(!id);
  const [legacyActivated, setLegacyActivated] = useState(false);
  const [saved, setSaved] = useState<Revision | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [phase, setPhase] = useState<'idle' | 'saving' | 'checking' | 'conflict' | 'stale' | 'uncertain'>('idle');
  const [errors, setErrors] = useState<FieldError[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [server, setServer] = useState<Revision | null>(null);
  const saving = useRef(false);
  const pending = useRef<Revision | null>(null);
  const abort = useRef<AbortController | null>(null);
  const lastObserved = useRef<string | null>(null);
  const summaryRef = useRef<HTMLDivElement>(null);
  useEffect(() => () => { abort.current?.abort(); }, []);
  const query = useQuery({ queryKey: ['private', 'draft', id], queryFn: ({ signal }) => readPrivate(() => api.draft(id ?? '', signal), signal),
    enabled: !!id && !!session.data && !session.isError && transition === 'idle', retry: false, networkMode: 'always',
    refetchOnWindowFocus: false, refetchOnMount: 'always' });
  const dirty = !saved || !equal(form, saved.payload);
  useEffect(() => {
    if (!query.data || query.isFetching || query.isError || phase === 'saving' || phase === 'checking' ||
      (hydrated && lastObserved.current === query.data.id)) return;
    lastObserved.current = query.data.id;
    if (!hydrated) {
      if (isFullDraft(query.data.payload)) { setForm(query.data.payload); setDefaultUntouched(false); }
      setSaved(query.data);
      setHydrated(true);
    } else if (saved && query.data.id !== saved.id) {
      if (dirty || !isFullDraft(query.data.payload)) {
        setServer(query.data);
        setPhase('conflict');
        setNotice('A newer server revision was observed. Local edits are preserved; compare before saving.');
      } else {
        setForm(query.data.payload);
        setSaved(query.data);
      }
    }
  }, [hydrated, query.data, query.isFetching, query.isError, saved, dirty, phase]);
  function change(next: Draft, field?: string) {
    setForm(next);
    if (field === 'objective_text') setDefaultUntouched(false);
    if (field) setErrors(current => current.filter(error => focusField(error.field) !== field));
    if (phase !== 'conflict' && phase !== 'uncertain' && phase !== 'stale') setPhase('idle');
    if (phase !== 'stale') setNotice(null);
  }
  function showErrors(problems: FieldError[]) {
    setErrors(problems);
    if (problems.length) {
      const firstField = problems.find(problem => problem.field !== 'body');
      if (firstField) setStep(stepFor(firstField.field));
      setNotice('Check the indicated fields before saving.');
      requestAnimationFrame(() => summaryRef.current?.focus());
    }
  }
  async function confirm(receipt: Revision, snapshot: Draft, signal: AbortSignal) {
    const verified = await readPrivate(() => api.draft(receipt.engagement_id, signal), signal);
    if (verified.id !== receipt.id || verified.revision !== receipt.revision || verified.digest !== receipt.digest ||
      !equal(verified.payload, snapshot)) throw new ApiError('INVALID_RESPONSE');
    pending.current = null;
    setSaved(verified);
    setForm(snapshot);
    setPhase('idle');
    setErrors([]);
    setNotice(null);
    client.setQueryData(['private', 'engagement', verified.engagement_id], verified);
    client.setQueryData(['private', 'draft', verified.engagement_id], verified);
    void client.invalidateQueries({ queryKey: ['private', 'dashboard'] });
    return verified;
  }
  async function save(advance = false) {
    if (saving.current || phase === 'conflict' || phase === 'uncertain' || phase === 'stale' || !session.data) return;
    const problems = localErrors(form);
    if (problems.length) { showErrors(problems); return; }
    if (!dirty && saved) { if (advance) setStep(current => Math.min(current + 1, 4)); return; }
    saving.current = true;
    setPhase('saving');
    setNotice(null);
    const controller = new AbortController();
    abort.current = controller;
    const snapshot = form;
    let receipt: Revision | null = null;
    try {
      receipt = await readPrivate(() => saved
        ? api.updateDraft(saved.engagement_id, snapshot, saved.revision, saved.digest, crypto.randomUUID(), session.data!.csrf_token, controller.signal)
        : api.createDraft(snapshot, session.data!.csrf_token, controller.signal), controller.signal);
      pending.current = receipt;
      const verified = await confirm(receipt, snapshot, controller.signal);
      if (!id) navigate(`/engagements/${verified.engagement_id}/setup`, { state: { step: advance ? Math.min(step + 1, 4) : step } });
      else if (advance) setStep(current => Math.min(current + 1, 4));
    } catch (error) {
      if (controller.signal.aborted) return;
      if (error instanceof ApiError && error.code === 'ENGAGEMENT_CONFLICT') {
        setPhase('conflict'); setNotice('Conflict: this draft has a newer revision. Local edits are preserved. Compare the server revision before choosing how to reconcile.');
      } else if (receipt) {
        setPhase('stale'); setNotice('Save receipt received, but GET confirmation failed. Retry the exact readback; do not submit again.');
      } else if (error instanceof ApiError && error.code === 'BODY_TOO_LARGE') {
        setPhase('idle'); setNotice('The request is too large and was not saved. Shorten context, scope or matrix entries before saving again.');
      } else if (error instanceof ApiError && error.code === 'INVALID_INPUT' && error.fieldErrors.length) {
        setPhase('idle'); showErrors(error.fieldErrors);
      } else {
        setPhase('uncertain'); setNotice(error instanceof ApiError ? error.message : 'Save outcome uncertain. No success was confirmed.');
      }
    } finally { saving.current = false; abort.current = null; }
  }
  async function reconcile() {
    if (!session.data || saving.current) return;
    const target = id ?? pending.current?.engagement_id;
    if (!target) return;
    const priorPhase = phase;
    saving.current = true;
    setPhase('checking');
    const controller = new AbortController();
    abort.current = controller;
    try {
      const latest = await readPrivate(() => api.draft(target, controller.signal), controller.signal);
      if (pending.current && latest.id === pending.current.id && latest.digest === pending.current.digest && equal(latest.payload, form)) {
        await confirm(pending.current, form, controller.signal);
        if (!id) navigate(`/engagements/${target}/setup`, { state: { step } });
      } else { setServer(latest); setPhase('conflict'); setNotice('Server revision loaded. Choose explicitly whether to discard or keep your local edits.'); }
    } catch (error) {
      if (!controller.signal.aborted) {
        setPhase(priorPhase);
        setNotice(error instanceof ApiError ? error.message : 'Readback unavailable.');
      }
    } finally { saving.current = false; abort.current = null; }
  }
  const lock = phase === 'saving' || phase === 'checking' || transition !== 'idle';
  if (id && !hydrated && !query.isError) return <section aria-busy="true"><p>Loading draft…</p></section>;
  if (id && query.isError && !hydrated) return <div role="alert">{query.error instanceof ApiError ? query.error.message : 'Draft unavailable.'}</div>;
  if (id && hydrated && !saved) return <div role="alert">Draft unavailable. No revision was accepted.</div>;
  if (id && saved && !isFullDraft(saved.payload) && !legacyActivated) return <section aria-label="Legacy draft conversion">
    <p>Legacy draft is read-only until you explicitly convert it. Revision {saved.revision} and digest {saved.digest} remain unchanged.</p>
    <p>Conversion adds only declarative empty context/rules/matrix, zero budgets and NONE data policy. Review these before Save; no provider, catalog or target effect is granted.</p>
    <button type="button" onClick={() => { setForm(editableLegacy(saved.payload)); setDefaultUntouched(false); setLegacyActivated(true); }}>
      Convert legacy draft to editable revision</button>
  </section>;
  return <section className={styles.wizard} aria-label="Draft setup" aria-busy={lock}>
    {!id && <><h1>{dashboardCopy.new}</h1><Link className={styles.back} to="/">← {engagementCopy.dashboard}</Link></>}
    <div className={styles.layout}>
      <nav aria-label="Setup steps" className={styles.steps}>{steps.map((label, index) =>
        <button key={label} type="button" aria-current={step === index ? 'step' : undefined} onClick={() => setStep(index)}>{index + 1}. {label}</button>)}</nav>
      <div className={styles.panel}>
        <h2>{steps[step]}</h2>
        {legacyActivated && saved && !isFullDraft(saved.payload) && <p>Declarative defaults: zero budgets, empty context/rules/matrix and NONE data policy. Your original legacy revision is unchanged until Save creates a new CAS revision.</p>}
        <output aria-live="polite">{phase === 'checking' ? 'Checking saved revision…' : lock ? 'Saving…' : phase === 'conflict' ? 'Conflict · local edits preserved' :
          phase === 'stale' ? 'Unconfirmed readback' : phase === 'uncertain' ? 'Save outcome uncertain' :
          query.isError ? 'Unconfirmed readback' : dirty ? 'Unsaved changes' : `Saved · revision ${saved?.revision}`}</output>
        {query.isError && <p role="alert">{query.error instanceof ApiError ? query.error.message : 'Draft unavailable.'}</p>}
        {notice && <p role={errors.length ? undefined : 'alert'}>{notice}</p>}
        {errors.length > 0 && <div ref={summaryRef} role="alert" className={styles.summary} tabIndex={-1}>
          <h3>Check these fields</h3><ul>{errors.map((error, index) => <li key={`${error.field}-${index}`}>
            {error.field === 'body' ? <span>Draft exceeds the 1,000,000-byte aggregate limit. Shorten context, scope or matrix entries.</span> :
              <button type="button" onClick={() => { setStep(stepFor(error.field)); requestAnimationFrame(() => document.getElementById(fieldId(error.field))?.focus()); }}>
                {error.field}: {errorText[error.code]}</button>}</li>)}</ul></div>}
        <fieldset disabled={lock} className={styles.form}>
          {step === 0 && <>
            <Field path="name" label="Engagement name" errors={errors}>{props => <input {...props} value={form.name} onChange={event => change({ ...form, name: event.target.value }, 'name')} />}</Field>
            <Field path="authorization.owner" label="Authorization owner" errors={errors}>{props => <input {...props} value={form.authorization.owner} onChange={event => change({ ...form, authorization: { ...form.authorization, owner: event.target.value } }, 'authorization.owner')} />}</Field>
            <Field path="authorization.statement" label="Authorization statement" errors={errors}>{props => <textarea {...props} value={form.authorization.statement} onChange={event => change({ ...form, authorization: { ...form.authorization, statement: event.target.value } }, 'authorization.statement')} />}</Field>
            <label className={styles.validity}><input type="checkbox" checked={form.authorization.valid_from !== null || form.authorization.valid_until !== null}
              onChange={event => {
                observeControl('period_toggle');
                change({ ...form, authorization: { ...form.authorization, valid_from: event.target.checked ? '' : null, valid_until: event.target.checked ? '' : null } });
                setErrors(current => current.filter(error => !['authorization.valid_from', 'authorization.valid_until'].includes(error.field)));
              }} />Limit to a period</label>
            {form.authorization.valid_from === null && form.authorization.valid_until === null ? <p>No end date — until closed or revoked.</p> : <>
              <DatePicker path="authorization.valid_from" label="Valid from (UTC)" value={form.authorization.valid_from} errors={errors}
                onChange={value => change({ ...form, authorization: { ...form.authorization, valid_from: value } }, 'authorization.valid_from')} />
              <DatePicker path="authorization.valid_until" label="Valid until (UTC)" value={form.authorization.valid_until} endOfDay errors={errors}
                onChange={value => change({ ...form, authorization: { ...form.authorization, valid_until: value } }, 'authorization.valid_until')} />
            </>}
            <fieldset className={styles.mode}><legend>Assessment mode</legend>
              <label><input type="radio" name="assessment_mode" checked={form.assessment_mode === 'FULL_ASSESSMENT'} onChange={() => {
                if (!form.objective_text) setDefaultUntouched(true);
                change({ ...form, assessment_mode: 'FULL_ASSESSMENT', objective_text: form.objective_text || DEFAULT_OBJECTIVE });
              }} />Full assessment</label>
              <label><input type="radio" name="assessment_mode" checked={form.assessment_mode === 'FOCUSED_TEST'} onChange={() => {
                change({ ...form, assessment_mode: 'FOCUSED_TEST', objective_text: defaultUntouched ? '' : form.objective_text });
                setDefaultUntouched(false);
              }} />Focused test</label>
            </fieldset>
            <Field path="objective_text" label="Objective / Brain instructions" hint="1–8192 code points; at most 32768 UTF-8 bytes. Do not enter credentials." errors={errors}>{props => <textarea {...props} rows={6} value={form.objective_text} onChange={event => change({ ...form, objective_text: event.target.value }, 'objective_text')} />}</Field>
            <p>{Array.from(form.objective_text).length} / 8192 code points · {new TextEncoder().encode(form.objective_text).length} / 32768 UTF-8 bytes</p>
            <h3>Objective constraints</h3>
            {form.objective_constraints.map((item, index) => <div key={item.id} className={styles.entry}>
              <Field path={`objective_constraints.${index}.kind`} label={`Constraint kind ${index + 1}`} errors={errors}>{props =>
                <select {...props} value={item.kind} onChange={event => change({ ...form, objective_constraints: form.objective_constraints.map((entry, i) =>
                  i === index ? { ...entry, kind: constraintKind(event.target.value) } : entry) }, `objective_constraints.${index}.kind`)}>
                  <option>READ_ONLY</option><option>EXCLUDE_FEATURE</option><option>REQUIRE_CRITERION</option></select>}</Field>
              <Field path={`objective_constraints.${index}.text`} label={`Constraint text ${index + 1}`} errors={errors}>{props =>
                <textarea {...props} value={item.text} onChange={event => change({ ...form, objective_constraints: form.objective_constraints.map((entry, i) =>
                  i === index ? { ...entry, text: event.target.value } : entry) }, `objective_constraints.${index}.text`)} />}</Field>
              <button type="button" onClick={() => change({ ...form, objective_constraints: form.objective_constraints.filter((_, i) => i !== index) })}>Remove constraint {index + 1}</button>
            </div>)}
            <button type="button" disabled={form.objective_constraints.length >= 64} onClick={() => change({ ...form, objective_constraints: [...form.objective_constraints,
              { id: crypto.randomUUID(), kind: 'READ_ONLY', text: '', operation_refs: [] }] })}>Add objective constraint</button>
            <p>Operation catalog unavailable: operation references cannot be selected or saved.</p>
            {form.scope.map((item, index) => <div key={index} className={styles.entry}><h3>Scope {index + 1}</h3>
              <Field path={`scope.${index}.origin`} label="Scope origin" errors={errors}>{props => <input {...props} value={item.origin} onChange={event => change({ ...form, scope: form.scope.map((entry, i) => i === index ? { ...entry, origin: event.target.value } : entry) }, `scope.${index}.origin`)} />}</Field>
              <Field path={`scope.${index}.port`} label="Port" errors={errors}>{props => <input {...props} type="number" min="1" max="65535" value={item.port} onChange={event => change({ ...form, scope: form.scope.map((entry, i) => i === index ? { ...entry, port: Number(event.target.value) } : entry) }, `scope.${index}.port`)} />}</Field>
              <Field path={`scope.${index}.path_prefix`} label="Path prefix" errors={errors}>{props => <input {...props} value={item.path_prefix} onChange={event => change({ ...form, scope: form.scope.map((entry, i) => i === index ? { ...entry, path_prefix: event.target.value } : entry) }, `scope.${index}.path_prefix`)} />}</Field>
              <Field path={`scope.${index}.access`} label="Scope access" errors={errors}>{props => <select {...props} value={item.access} onChange={event => change({ ...form, scope: form.scope.map((entry, i) => i === index ? { ...entry, access: scopeAccess(event.target.value) } : entry) }, `scope.${index}.access`)}><option>BLOCKED</option><option>VISIT_ONLY</option><option>ATTACKABLE</option></select>}</Field>
              <Field path={`scope.${index}.exclusions`} label="Exclusions (one path per line)" errors={errors}>{props => <textarea {...props} value={item.exclusions.join('\n')} onChange={event => change({ ...form, scope: form.scope.map((entry, i) => i === index ? { ...entry, exclusions: event.target.value ? event.target.value.split('\n') : [] } : entry) }, `scope.${index}.exclusions`)} />}</Field>
              {form.scope.length > 1 && <button type="button" onClick={() => change({ ...form, scope: form.scope.filter((_, i) => i !== index) })}>Remove scope {index + 1}</button>}
            </div>)}
            <button type="button" disabled={form.scope.length >= 64} onClick={() => change({ ...form, scope: [...form.scope, { origin: '', port: 443, path_prefix: '/', exclusions: [], access: 'BLOCKED' }] })}>Add scope</button>
          </>}
          {step === 1 && <ApplicationStep form={form} errors={errors} change={change} />}
          {step === 2 && <p>Anonymous is valid. Secret fields, vault, Verify login and assisted browser login are UNAVAILABLE.</p>}
          {step === 3 && <RulesStep form={form} errors={errors} change={change} />}
          {step === 4 && <ReviewStep saved={saved} dirty={dirty} />}
        </fieldset>
        {phase === 'conflict' && <div className={styles.warning}>
          <button type="button" onClick={() => { void reconcile(); }}>Compare server revision</button>
          {server && <><p>Server revision {server.revision} · digest {server.digest}. Local edits remain unsaved.</p>
            <button type="button" onClick={() => { if (isFullDraft(server.payload)) {
              setForm(server.payload); setSaved(server); setServer(null); setPhase('idle'); setErrors([]); setNotice(null);
              client.setQueryData(['private', 'draft', server.engagement_id], server);
            } }}>Discard local edits and load server revision</button>
            <button type="button" onClick={() => {
              setSaved(server); setServer(null); setPhase('idle'); setNotice(null);
              client.setQueryData(['private', 'draft', server.engagement_id], server);
            }}>Use server revision as base, keep local edits (Save separately)</button>
          </>}
        </div>}
        {phase === 'stale' && <button type="button" onClick={() => { void reconcile(); }}>Retry exact GET readback</button>}
        {phase === 'uncertain' && <>
          <p>Check the engagement list and reconcile before submitting again. No automatic retry.</p>
          {id && <button type="button" onClick={() => { void reconcile(); }}>Compare server revision</button>}
        </>}
        <div className={styles.actions}>
          <button type="button" disabled={lock || step === 0} onClick={() => setStep(current => current - 1)}>Back</button>
          <button type="button" disabled={lock || phase !== 'idle' || !dirty} onClick={() => { void save(); }}>Save draft</button>
          <button type="button" disabled={lock || step === 4 || phase !== 'idle'} onClick={() => { void save(true); }}>Next</button>
        </div>
      </div>
      <aside className={styles.aside} aria-label="Draft summary"><h2>Draft status</h2>
        <p>{saved ? `Revision ${saved.revision} · ${saved.digest}` : 'Not yet saved'}</p>
        <p>{form.assessment_mode === 'FULL_ASSESSMENT' ? 'Full assessment' : 'Focused test'}</p>
        <p>CATALOG_UNAVAILABLE / NOT_SELECTED</p>
        <button type="button" disabled aria-describedby="wizard-start-reason">Start assessment</button>
        <p id="wizard-start-reason">No published workflow profile is selected. Assessment execution is unavailable.</p>
      </aside>
    </div>
  </section>;
}
