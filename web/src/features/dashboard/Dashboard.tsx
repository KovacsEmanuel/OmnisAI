import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { useObservationClock } from '../../shared/useObservationClock';
import type { Projection } from '../../shared/api/projections';
import { api } from '../../shared/api/client';
import { ApiError } from '../../shared/api/errors';
import { useSession } from '../bootstrap/BrowserSession';
import { dashboardCopy as copy } from './copy';
import styles from './Dashboard.module.css';

export function Dashboard() {
  const { session, transition, readPrivate } = useSession();
  const [after, setAfter] = useState<string | null>(null);
  const query = useQuery({ queryKey: ['private', 'dashboard', after], queryFn: ({ signal }) => readPrivate(() => api.dashboard(after, signal), signal),
    enabled: !!session.data && !session.isError && transition === 'idle', networkMode: 'always', retry: false, refetchInterval: 5000, refetchIntervalInBackground: false, refetchOnWindowFocus: 'always', refetchOnReconnect: 'always' });
  const now = useObservationClock();
  const [accepted, setAccepted] = useState<Projection | null>(null);
  useEffect(() => { if (query.data) setAccepted(query.data); }, [query.data]);
  // Keep a whole confirmed projection during replacement; never append pages or own revision.
  const projection = query.data ?? accepted;
  const stale = !!projection && (query.isFetching || query.isError || query.fetchStatus === 'paused' || now - query.dataUpdatedAt > 15000);
  return <section aria-label="Dashboard projection" aria-busy={query.isFetching}>
    <div className={styles.hero}><div><h1>{copy.title}</h1></div>
      <section className={`${styles.panel} ${styles.start}`}><div className={styles.core}><Link className={`${styles.action} withIcon`} to="/engagements/new">{copy.new}<span className="buttonIcon" aria-hidden="true"><svg viewBox="0 0 24 24" focusable="false"><path d="M5 12h14m-6-6 6 6-6 6" /></svg></span></Link><p>{copy.createHint}</p></div></section>
    </div>
    {query.isPending && <output>{copy.loading}</output>}
    {query.isError && <div role="alert"><p>{query.error instanceof ApiError ? query.error.message : copy.unavailable}</p><button onClick={() => { void query.refetch(); }}>{copy.retry}</button></div>}
    {stale && <output>{copy.stale}</output>}
    {projection && <>
      <section className={`${styles.panel} ${styles.attention}`} aria-label="Workspace status"><div className={styles.core}>
        <div><h2>Attention unavailable</h2><p>No cross-engagement review queue is available. Open an engagement for its persisted run and questions.</p></div><span className={styles.state}>{projection.data.attention_state}</span>
      </div></section>
      <div className={styles.metrics}>
        <section aria-label={copy.total} className={styles.panel}><div className={`${styles.core} ${styles.metric}`}><p className={styles.value}>{projection.data.total_engagements}</p><h2>{copy.total}</h2></div></section>
        {[copy.confirmed, copy.coverage, copy.cost].map(label => <section key={label} aria-label={label} aria-describedby="assessment-unavailable" className={styles.panel}><div className={`${styles.core} ${styles.metric}`}><p className={`${styles.value} ${styles.unknown}`}>—</p><h2>{label}</h2></div></section>)}
      </div>
      <div className={styles.availability}><p id="assessment-unavailable">{copy.runReason}</p><span>{projection.data.items.length} loaded on this page</span></div>
      <div className={styles.recentHead}><h2>{copy.recent}</h2><button disabled={query.isFetching} onClick={() => { void query.refetch(); }}>{copy.refresh}</button></div>
      <p className={styles.metadata}>{copy.snapshot} <time>{projection.as_of}</time></p>
      <div className={styles.bento}>
        {projection.data.items.length === 0 && <p className={styles.empty}>{copy.empty}</p>}
        {projection.data.items.map(item => <article className={styles.panel} key={item.engagement_id}><div className={styles.core}>
          <div className={styles.cardHeading}><span className={styles.state}>{item.run_state}</span><span>{item.assessment_mode}</span></div><h3><Link to={`/engagements/${item.engagement_id}/overview`}>{item.name}</Link></h3>
          <p>Stage · {item.stage}</p>
          <details className={styles.snapshot}><summary>Snapshot details</summary><dl><dt>Engagement</dt><dd>{item.engagement_id}</dd><dt>Revision {item.revision}</dt><dd>{item.id}</dd><dt>Digest</dt><dd>{item.digest}</dd>{item.run_id && <><dt>Inert run</dt><dd>{item.run_id} · through {item.through_cursor}</dd></>}</dl></details>
        </div></article>)}
      </div>
      <div className={styles.pages}>{after && <button disabled={query.isFetching} onClick={() => setAfter(null)}>{copy.first}</button>}{projection.has_more && <button disabled={query.isFetching} onClick={() => setAfter(projection.next_page ?? null)}>{copy.next}</button>}</div>
    </>}
  </section>;
}
