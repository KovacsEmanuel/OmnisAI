import { ApiError } from '../../shared/api/errors';
import type { FieldError } from '../../shared/api/errors';
import { isFullDraft } from '../../shared/api/drafts';
import type { Draft, Revision } from '../../shared/api/drafts';
import { Field } from './WizardFields';
import styles from './Wizard.module.css';

type Props = { form: Draft; errors: FieldError[]; change: (next: Draft, field?: string) => void };
function decision(value: string): Draft['business_matrix'][number]['expected'] {
  if (value === 'ALLOW' || value === 'DENY' || value === 'UNKNOWN') return value;
  throw new ApiError('INVALID_INPUT');
}
function projection(value: string): Draft['data_policy']['model_projection'] {
  if (value === 'NONE' || value === 'REDACTED') return value;
  throw new ApiError('INVALID_INPUT');
}
function egress(value: string): Draft['data_policy']['research_egress'] {
  if (value === 'NONE' || value === 'PUBLIC_FACTS') return value;
  throw new ApiError('INVALID_INPUT');
}
const matrixFields = [['principal', 'Principal'], ['role', 'Role'], ['tenant', 'Tenant'], ['object', 'Object'],
  ['operation', 'Operation'], ['source', 'Source']] as const;
const budgetFields = [['max_requests', 'Maximum requests', 100000], ['max_duration_seconds', 'Maximum duration (seconds)', 86400],
  ['max_storage_bytes', 'Maximum storage (bytes)', 1073741824], ['validation_reserved_requests', 'Validation reserved requests', 100000],
  ['max_model_calls', 'Maximum model calls (declarative only)', 10000]] as const;
const effects: Draft['effect_rules'][number]['effect_class'][] = ['READ_ONLY_KNOWN', 'SESSION_CHANGE', 'LIMITED_WRITE', 'DESTRUCTIVE', 'UNKNOWN'];

export function ApplicationStep({ form, errors, change }: Props) {
  return <>
    {([['seed_urls', 'Seed URLs (one per line)'], ['priority_workflows', 'Priority workflows (one per line)'],
      ['test_objects', 'Test objects (one per line)']] as const).map(([key, label]) =>
      <Field key={key} path={`application_context.${key}`} label={label} errors={errors}>{props =>
        <textarea {...props} rows={3} value={form.application_context[key].join('\n')} onChange={event => change({ ...form,
          application_context: { ...form.application_context, [key]: event.target.value ? event.target.value.split('\n') : [] },
        }, `application_context.${key}`)} />}</Field>)}
    <p>Executable import: UNAVAILABLE. No import reference is saved.</p>
    <h3>Business access matrix</h3><p>Each row declares principal, role, tenant, object, operation, expected decision, source and revision. It grants no execution authority.</p>
    {form.business_matrix.map((item, index) => <div key={item.id} className={styles.entry}><h4>Rule {index + 1}</h4>
      {matrixFields.map(([key, label]) => <Field key={key} path={`business_matrix.${index}.${key}`} label={`${label} ${index + 1}`} errors={errors}>{props =>
        <input {...props} value={item[key]} onChange={event => change({ ...form,
          business_matrix: form.business_matrix.map((entry, i) => i === index ? { ...entry, [key]: event.target.value } : entry),
        }, `business_matrix.${index}.${key}`)} />}</Field>)}
      <Field path={`business_matrix.${index}.expected`} label={`Expected decision ${index + 1}`} errors={errors}>{props =>
        <select {...props} value={item.expected} onChange={event => change({ ...form, business_matrix: form.business_matrix.map((entry, i) =>
          i === index ? { ...entry, expected: decision(event.target.value) } : entry) }, `business_matrix.${index}.expected`)}>
          <option>UNKNOWN</option><option>ALLOW</option><option>DENY</option></select>}</Field>
      <Field path={`business_matrix.${index}.source_revision`} label={`Source revision ${index + 1}`} errors={errors}>{props =>
        <input {...props} type="number" min="1" max="2147483647" value={item.source_revision} onChange={event => change({ ...form,
          business_matrix: form.business_matrix.map((entry, i) => i === index ? { ...entry, source_revision: Number(event.target.value) } : entry),
        }, `business_matrix.${index}.source_revision`)} />}</Field>
      <button type="button" onClick={() => change({ ...form, business_matrix: form.business_matrix.filter((_, i) => i !== index) })}>Remove rule {index + 1}</button>
    </div>)}
    <button type="button" disabled={form.business_matrix.length >= 64} onClick={() => change({ ...form, business_matrix: [...form.business_matrix,
      { id: crypto.randomUUID(), principal: '', role: '', tenant: '', object: '', operation: '', expected: 'UNKNOWN', source: '', source_revision: 1 }] })}>Add business rule</button>
    <p>Published business rules reference: UNAVAILABLE / NOT_SELECTED. The inline matrix is saved as declarative draft data.</p>
  </>;
}

export function RulesStep({ form, errors, change }: Props) {
  return <>
    <h3>Effect rules (declarative)</h3>
    {form.effect_rules.map((item, index) => <div key={item.effect_class} className={styles.entry}>
      <h4>{item.effect_class}</h4>
      <Field path={`effect_rules.${index}.decision`} label={`Decision for ${item.effect_class}`} errors={errors}>{props =>
        <select {...props} value={item.decision} onChange={event => change({ ...form, effect_rules: form.effect_rules.map((entry, i) =>
          i === index ? { ...entry, decision: decision(event.target.value) } : entry) }, `effect_rules.${index}.decision`)}>
          <option>UNKNOWN</option><option>ALLOW</option><option>DENY</option></select>}</Field>
      <Field path={`effect_rules.${index}.note`} label={`Note for ${item.effect_class}`} errors={errors}>{props =>
        <textarea {...props} value={item.note} onChange={event => change({ ...form, effect_rules: form.effect_rules.map((entry, i) =>
          i === index ? { ...entry, note: event.target.value } : entry) }, `effect_rules.${index}.note`)} />}</Field>
      <button type="button" onClick={() => change({ ...form, effect_rules: form.effect_rules.filter((_, i) => i !== index) })}>Remove {item.effect_class}</button>
    </div>)}
    <button type="button" disabled={form.effect_rules.length >= effects.length} onClick={() => {
      const effect = effects.find(item => !form.effect_rules.some(rule => rule.effect_class === item));
      if (effect) change({ ...form, effect_rules: [...form.effect_rules, { effect_class: effect, decision: 'UNKNOWN', note: '' }] });
    }}>Add effect rule</button>
    <h3>Budgets</h3>{budgetFields.map(([key, label, max]) => <Field key={key} path={`budgets.${key}`} label={label} errors={errors}>{props =>
      <input {...props} type="number" min="0" max={max} value={form.budgets[key]} onChange={event => change({ ...form,
        budgets: { ...form.budgets, [key]: Number(event.target.value) },
      }, `budgets.${key}`)} />}</Field>)}
    <h3>Data policy</h3>
    <Field path="data_policy.model_projection" label="Model projection (declarative)" errors={errors}>{props =>
      <select {...props} value={form.data_policy.model_projection} onChange={event => change({ ...form,
        data_policy: { ...form.data_policy, model_projection: projection(event.target.value) },
      }, 'data_policy.model_projection')}><option>NONE</option><option>REDACTED</option></select>}</Field>
    <Field path="data_policy.research_egress" label="Research egress (declarative)" errors={errors}>{props =>
      <select {...props} value={form.data_policy.research_egress} onChange={event => change({ ...form,
        data_policy: { ...form.data_policy, research_egress: egress(event.target.value) },
      }, 'data_policy.research_egress')}><option>NONE</option><option>PUBLIC_FACTS</option></select>}</Field>
    <Field path="data_policy.retention_days" label="Retention days" errors={errors}>{props =>
      <input {...props} type="number" min="0" max="365" value={form.data_policy.retention_days} onChange={event => change({ ...form,
        data_policy: { ...form.data_policy, retention_days: Number(event.target.value) },
      }, 'data_policy.retention_days')} />}</Field>
    <p>Provider/model configuration, effect enforcement, policy engine, catalog editor and report-review policy: UNAVAILABLE, not saved here.</p>
  </>;
}

export function ReviewStep({ saved, dirty }: { saved: Revision | null; dirty: boolean }) {
  return <>
    {!saved ? <p>NOT_SAVED — complete and save the draft before reviewing persisted data.</p> : <>
      {dirty && <p>UNSAVED CHANGES — this summary shows only the last confirmed revision, not current edits.</p>}
      <dl className={styles.review}>
        <div><dt>Revision</dt><dd>{saved.revision} · {saved.id}</dd></div>
        <div><dt>Digest</dt><dd>{saved.digest}</dd></div>
        <div><dt>Mode</dt><dd>{saved.payload.assessment_mode}</dd></div>
        <div><dt>Exact saved objective</dt><dd className={styles.exact}>{saved.payload.objective_text}</dd></div>
        <div><dt>Constraints</dt><dd>{saved.payload.objective_constraints.map(item => `${item.kind}: ${item.text}`).join('\n') || 'None'}</dd></div>
        <div><dt>Scope</dt><dd>{saved.payload.scope.map(item => `${item.origin}:${item.port}${item.path_prefix} · ${item.access} · exclusions: ${item.exclusions.join(', ') || 'None'}`).join('\n')}</dd></div>
        {isFullDraft(saved.payload) && <>
          <div><dt>Context</dt><dd>Seeds: {saved.payload.application_context.seed_urls.join(', ') || 'None'} · workflows: {saved.payload.application_context.priority_workflows.join(', ') || 'None'} · test objects: {saved.payload.application_context.test_objects.join(', ') || 'None'}</dd></div>
          <div><dt>Business matrix</dt><dd>{saved.payload.business_matrix.map(item => `${item.principal}/${item.role}/${item.tenant} · ${item.object} · ${item.operation} → ${item.expected} · ${item.source} rev ${item.source_revision}`).join('\n') || 'None'}</dd></div>
          <div><dt>Effect rules</dt><dd>{saved.payload.effect_rules.map(item => `${item.effect_class}: ${item.decision} · ${item.note}`).join('\n') || 'None'}</dd></div>
          <div><dt>Budgets</dt><dd>{Object.entries(saved.payload.budgets).map(([key, value]) => `${key}: ${value}`).join(' · ')}</dd></div>
          <div><dt>Data policy</dt><dd>{saved.payload.data_policy.model_projection} / {saved.payload.data_policy.research_egress} · {saved.payload.data_policy.retention_days} days</dd></div>
        </>}
      </dl>
    </>}
    <p>Local syntax preflight only. CATALOG_UNAVAILABLE / NOT_SELECTED: workflow_profile_ref=null. Save is allowed; Start assessment is blocked. No AI interpretation or target health check was run.</p>
  </>;
}
