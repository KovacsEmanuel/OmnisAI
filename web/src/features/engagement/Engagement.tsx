import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, NavLink, useLocation, useParams } from 'react-router';
import { useObservationClock } from '../../shared/useObservationClock';
import { api } from '../../shared/api/client';
import type { Revision } from '../../shared/api/drafts';
import { ApiError, isUuid } from '../../shared/api/errors';
import { useSession } from '../bootstrap/BrowserSession';
import { engagementCopy as copy } from './copy';
import { Wizard } from './Wizard';
import { RunPanel } from './RunPanel';
import styles from './Engagement.module.css';

export function NewEngagement() {
  return <Wizard />;
}
export function Engagement() {
  const { id = '', surface = 'overview' } = useParams();
  const location = useLocation();
  const { session, transition, readPrivate } = useSession();
  const client = useQueryClient();
  const query = useQuery({ queryKey: ['private', 'engagement', id], queryFn: ({ signal }) => readPrivate(() => api.engagement(id, signal), signal),
    enabled: isUuid(id) && !!session.data && !session.isError && transition === 'idle', networkMode: 'always', retry: false, refetchInterval: 5000, refetchIntervalInBackground: false, refetchOnWindowFocus: 'always', refetchOnReconnect: 'always' });
  const selectedRevisionId = query.data?.id;
  useEffect(() => {
    if (surface !== 'setup' || !selectedRevisionId) return;
    const cached = client.getQueryData<Revision>(['private', 'draft', id]);
    if (cached && cached.id !== selectedRevisionId)
      void client.invalidateQueries({ queryKey: ['private', 'draft', id], exact: true });
  }, [client, id, surface, selectedRevisionId]);
  const now = useObservationClock();
  const stale = !!query.data && (query.isError || query.fetchStatus === 'paused' || now - query.dataUpdatedAt > 15000);
  if (!isUuid(id)) return <p>{copy.invalid}</p>;
  const draft = query.data;
  const full = surface === 'overview';
  return <section aria-label="Engagement projection" aria-busy={query.isFetching}>
    <Link className={styles.back} to="/">← {copy.dashboard}</Link>
    {query.isPending && <output>{copy.loading}</output>}
    {query.isError && <div role="alert"><p>{query.error instanceof ApiError ? query.error.message : copy.unavailable}</p><button onClick={() => { void query.refetch(); }}>{copy.retry}</button></div>}
    {stale && <output>{copy.stale}</output>}
    {draft && <>
      <div className={styles.heading}><div><p>{surface === 'setup' ? 'Persisted draft · Setup' : copy.readOnly}</p><h1>{draft.payload.name}</h1><p>{draft.payload.assessment_mode === 'FOCUSED_TEST' ? 'Focused test' : 'General assessment'}{surface === 'setup' ? ` · saved revision ${draft.revision}` : ''}</p></div>{surface !== 'setup' && <button disabled aria-describedby="run-reason">{copy.start}</button>}</div>
      <button disabled={query.isFetching} onClick={() => {
        void query.refetch();
        if (surface === 'setup') void client.invalidateQueries({ queryKey: ['private', 'draft', id], exact: true });
      }}>{copy.refresh}</button>
      {surface !== 'setup' && <p id="run-reason" className={styles.muted}>Target assessment is not available. Inert runs have separate preflight and consent in Overview.</p>}
      <nav aria-label="Engagement navigation" className={styles.tabs}>
        {[[copy.overview, 'overview'], [copy.stream, 'stream'], [copy.findings, 'findings'], [copy.coverage, 'coverage'], [copy.reports, 'reports'], [copy.setup, 'setup']].map(([label, path]) => <NavLink key={path} to={{ pathname: `/engagements/${id}/${path}`, search: location.search }}>{label}</NavLink>)}
      </nav>
      {surface === 'setup' && <Wizard key={id} id={id} />}
      {(full || surface === 'stream') && <RunPanel key={id} draft={draft} stream={surface === 'stream'}>
      {full && <>
        <div className={styles.assessmentMetrics} aria-label="Target assessment metrics">{['Confirmed', 'Critical', 'High', 'Coverage', 'Endpoints'].map(label => <section key={label} aria-label={label} className={styles.panel}><div className={styles.core}><p className={styles.metricValue}>—</p><h2>{label}</h2></div></section>)}</div>
        <p className={styles.muted}>Assessment metrics unavailable · no target assessment has run.</p>
      </>}
      {full && <section className={styles.panel} aria-label="Engagement scope"><div className={styles.core}>
        <div className={styles.overviewContext}><div><h2>{copy.objective}</h2><p className={styles.objective}>{draft.payload.objective_text}</p></div>
        <div><h2>{copy.scope}</h2>{draft.payload.scope.map((entry, index) => <article key={index} className={styles.scope}><h3>{entry.origin}</h3><p>{entry.access}</p><dl>
          <div><dt>{copy.port}</dt><dd>{entry.port}</dd></div><div><dt>{copy.prefix}</dt><dd>{entry.path_prefix}</dd></div><div><dt>{copy.exclusions}</dt><dd>{entry.exclusions.length ? entry.exclusions.join('\n') : copy.none}</dd></div>
        </dl></article>)}</div></div>
      </div></section>}
      {full && <>
        <div className={styles.overviewContext}>
          <section className={styles.panel}><div className={styles.core}><h2>Top findings</h2><p>No assessment findings producer is available. Inert-run results are not security findings.</p><Link className={styles.back} to={`/engagements/${id}/findings`}>Findings & limitations →</Link></div></section>
          <section className={styles.panel}><div className={styles.core}><h2>Severity</h2><p className={styles.muted}>Distribution unavailable. No counts or denominator observed.</p></div></section>
        </div>
      </>}
      </RunPanel>}
      {!full && surface !== 'setup' && surface !== 'stream' && <section className={styles.panel}><div className={styles.core}><h2>{surface === 'findings' ? copy.findings : surface === 'coverage' ? copy.coverage : surface === 'reports' ? copy.reports : copy.unavailable}</h2><p>{copy.unavailable} — {copy.future}</p></div></section>}
    </>}
  </section>;
}
