import { useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import type { KeyCommand, KeySelection, KeySettings } from '../../shared/api/providerKeys';
import { roles } from '../../shared/api/providerKeys';
import { availabilityIssue, matches, providerName, supports, usable } from './SettingsModels';
import type { CatalogRead, Evidence, Library, ModelEntry } from './SettingsModels';
import styles from './SettingsModels.module.css';

type Role = typeof roles[number];
export function SettingsAssignments({ settings, library, evidence, catalogs, blocked, working, feedback, save }: {
  settings: KeySettings; library: Library; evidence: Record<string, Evidence>; catalogs: Record<string, CatalogRead>; blocked: boolean; working: boolean;
  save: (command: KeyCommand) => Promise<boolean>;
  feedback: ReactNode;
}) {
  const eligible = library.entries.filter(entry => usable(entry, settings, evidence));
  const initial = (role: Role) => settings.selection?.[role] ?? (role === 'default' && eligible[0] ? { connection_id: eligible[0].connection_id, connection_revision: eligible[0].connection_revision, model: eligible[0].model, output_tokens: eligible[0].output_tokens } : null);
  const [draft, setDraft] = useState<Record<Role, KeySelection | null>>(() => ({ default: initial('default'), brain: initial('brain'), investigator: initial('investigator'), validator: initial('validator') }));
  const [notice, setNotice] = useState('');
  const version = `${settings.selection?.revision ?? 0}:${library.revision}:${settings.connections.map(item => item.revision).join(',')}`;
  const [loadedVersion, setLoadedVersion] = useState(version);
  if (loadedVersion !== version) {
    setLoadedVersion(version);
    setDraft({ default: initial('default'), brain: initial('brain'), investigator: initial('investigator'), validator: initial('validator') });
  }
  const selectedEntry = (choice: KeySelection | null) => library.entries.find(entry => matches(entry, choice));
  const available = (choice: KeySelection | null) => {
    const entry = selectedEntry(choice);
    return !!choice && !!entry && usable(entry, settings, evidence) && supports(evidence[entry.entry_id]?.model, choice.output_tokens);
  };
  const valid = available(draft.default) && roles.slice(1).every(role => draft[role] === null || available(draft[role]));
  const simple = eligible.length === 1 && (!settings.selection || (available(settings.selection.default) && matches(eligible[0]!, settings.selection.default) && roles.slice(1).every(role => {
    const choice = settings.selection?.[role];
    return choice === null || (!!choice && available(choice) && matches(eligible[0]!, choice));
  })));
  function label(entry: ModelEntry) {
    const provider = settings.connections.find(item => item.connection_id === entry.connection_id)?.provider;
    const issue = availabilityIssue(entry, settings, evidence, catalogs);
    return `${entry.model} · ${provider ? providerName(provider) : 'Unavailable connection'}${issue ? ' · ' + issue : ''}`;
  }
  function change(role: Role, value: string) {
    if (blocked || working) return;
    const entry = library.entries.find(item => item.entry_id === value);
    setDraft(previous => ({ ...previous, [role]: entry ? { connection_id: entry.connection_id, connection_revision: entry.connection_revision, model: entry.model, output_tokens: previous[role]?.output_tokens ?? entry.output_tokens } : null }));
    setNotice('Unsaved assignments.');
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (blocked || working || !valid || !draft.default) return;
    if (await save({ action: 'save_selection', command_id: crypto.randomUUID(), expected_revision: settings.selection?.revision ?? 0, default: draft.default, brain: draft.brain, investigator: draft.investigator, validator: draft.validator })) setNotice('');
  }
  return <section className={styles.panel} aria-labelledby="assignments-heading"><div className={styles.core}>
    <h2 id="assignments-heading">Model assignments</h2><p className={styles.hint}>For future runs. Existing runs keep their pinned settings.</p>
    {!library.entries.length ? <p>Add a model first.</p> : <>
      {!settings.selection && !simple && <p>Save assignments to confirm a default. Adding models does not assign roles.</p>}
      {simple && <p>{settings.selection ? 'All roles use' : 'All roles will use'} {eligible[0]!.model} · {providerName(settings.connections.find(item => item.connection_id === eligible[0]!.connection_id)!.provider)}{settings.selection ? '.' : ' after saving assignments.'}</p>}
      {!valid && <p className={styles.hint}>Choose available saved entries for the affected roles. Unverified, disabled or stale choices are not replaced automatically.</p>}
      <form onSubmit={event => { void submit(event); }}>
        {!simple && <><div className={styles.defaultField}>{picker('default')}</div><div className={styles.assignmentGrid}>{roles.slice(1).map(picker)}</div></>}
        <details><summary>Output controls</summary><p className={styles.hint}>Per-role output caps are preserved independently. These are not a total run budget.</p><div className={styles.fields}>{roles.map(role => {
          const choice = draft[role], entry = selectedEntry(choice);
          return choice && <div className={styles.field} key={role}><label htmlFor={`settings-output-${role}`}>{title(role)} output tokens</label><input id={`settings-output-${role}`} type="number" min={1} max={65536} step={1} value={choice.output_tokens} disabled={blocked} aria-disabled={working} onChange={event => { if (!working) { setDraft({ ...draft, [role]: { ...choice, output_tokens: Number(event.target.value) } }); setNotice('Unsaved assignments.'); } }} /><small className={styles.mono}>{entry ? label(entry) : `${choice.model} · ${choice.connection_id} revision ${choice.connection_revision} · Unavailable`}</small></div>;
        })}</div></details>
        <div className={styles.actions}><button type="submit" disabled={blocked || !valid} aria-disabled={working} aria-busy={working}>Save assignments</button></div>
      </form><output className={styles.hint} aria-live="polite">{notice}</output>
    </>}
    {feedback}
  </div></section>;
  function picker(role: Role) {
    const choice = draft[role], entry = selectedEntry(choice);
    const stale = !!choice && !entry;
    return <div className={styles.field} key={role}><label htmlFor={`settings-assignment-${role}`}>{role === 'default' ? 'Default model' : title(role)}</label><select id={`settings-assignment-${role}`} value={entry?.entry_id ?? (stale ? 'stale' : '')} disabled={blocked} aria-disabled={working} onChange={event => change(role, event.target.value)}>
      <option value="" disabled={role === 'default'}>{role === 'default' ? 'Choose a saved model' : 'Use default'}</option>
      {stale && <option value="stale" disabled>{choice.model} · {choice.connection_id} revision {choice.connection_revision} · Unavailable</option>}
      {library.entries.map(item => <option key={item.entry_id} value={item.entry_id} disabled={!usable(item, settings, evidence)}>{label(item)}</option>)}
    </select>{choice && !available(choice) && <small>{entry ? `Not available for assignment: ${availabilityIssue(entry, settings, evidence, catalogs, choice.output_tokens)?.toLowerCase()}.` : `${choice.model} · ${choice.connection_id} revision ${choice.connection_revision} · Unavailable`}</small>}</div>;
  }
}
function title(value: string) { return value[0]!.toUpperCase() + value.slice(1); }
