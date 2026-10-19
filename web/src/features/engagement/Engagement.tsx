import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, NavLink, useParams } from 'react-router';
import { useObservationClock } from '../../shared/useObservationClock';
import { api } from '../../shared/api/client';
import type { Revision } from '../../shared/api/drafts';
import { ApiError, isUuid } from '../../shared/api/errors';
import { useSession } from '../bootstrap/BrowserSession';
import { engagementCopy as copy } from './copy';
import { Wizard } from './Wizard';
import { ModelTest } from './ModelTest';
import styles from './Engagement.module.css';

export function NewEngagement() {
  return <><ModelTest /><Wizard /></>;
}
export function Engagement() {
  const { id = '', surface = 'overview' } = useParams();
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
      <div className={styles.heading}><div><p>{surface === 'setup' ? 'Persisted draft · Setup' : copy.readOnly}</p><h1>{draft.payload.name}</h1><p>{draft.payload.assessment_mode} · {copy.notRun}</p></div>{surface !== 'setup' && <button disabled aria-describedby="run-reason">{copy.start}</button>}</div>
      <button disabled={query.isFetching} onClick={() => {
        void query.refetch();
        if (surface === 'setup') void client.invalidateQueries({ queryKey: ['private', 'draft', id], exact: true });
      }}>{copy.refresh}</button>
      {surface !== 'setup' && <p id="run-reason">{copy.runReason}</p>}
      <nav aria-label="Engagement navigation" className={styles.tabs}>
        {[[copy.overview, 'overview'], [copy.stream, 'stream'], [copy.findings, 'findings'], [copy.coverage, 'coverage'], [copy.reports, 'reports'], [copy.setup, 'setup']].map(([label, path]) => <NavLink key={path} to={`/engagements/${id}/${path}`}>{label}</NavLink>)}
      </nav>
      {surface === 'setup' && <Wizard key={id} id={id} />}
      {full && <ModelTest />}
      {!full && surface !== 'setup' && <p>{copy.unavailable} — {copy.future}</p>}
      {full && <section className={styles.panel}><div className={styles.core}>
        <dl className={styles.details}>
          {[[copy.identity, draft.engagement_id], [copy.revisionId, draft.id], [copy.revision, draft.revision], [copy.digest, draft.digest], [copy.mode, draft.payload.assessment_mode]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
        </dl>
        <h2>{copy.objective}</h2><p className={styles.objective}>{draft.payload.objective_text}</p>
        <h2>{copy.scope}</h2>{draft.payload.scope.map((entry, index) => <article key={index} className={styles.scope}><h3>{entry.origin}</h3><p>{entry.access}</p><dl>
          <div><dt>{copy.port}</dt><dd>{entry.port}</dd></div><div><dt>{copy.prefix}</dt><dd>{entry.path_prefix}</dd></div><div><dt>{copy.exclusions}</dt><dd>{entry.exclusions.length ? entry.exclusions.join('\n') : copy.none}</dd></div>
        </dl></article>)}
      </div></section>}
    </>}
  </section>;
}
