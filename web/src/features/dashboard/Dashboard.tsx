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
    <div className={styles.hero}><div><p className={styles.kicker}>{copy.kicker}</p><h1>{copy.title}<br /><span>{copy.accent}</span></h1><p>{copy.intro}</p></div>
      <section className={`${styles.panel} ${styles.start}`}><div className={styles.core}><p className={styles.kicker}>{copy.createTitle}</p><Link className={styles.action} to="/engagements/new">{copy.new} →</Link><p>{copy.createHint}</p></div></section>
    </div>
    {query.isPending && <output>{copy.loading}</output>}
    {query.isError && <div role="alert"><p>{query.error instanceof ApiError ? query.error.message : copy.unavailable}</p><button onClick={() => { void query.refetch(); }}>{copy.retry}</button></div>}
    {stale && <output>{copy.stale}</output>}
    {projection && <>
      <section className={styles.panel}><div className={styles.core}><h2>{copy.review}</h2><span>{projection.data.attention_state}</span><p>{copy.attentionReason}</p></div></section>
      <div className={styles.metrics}>
        <section aria-label={copy.total} className={styles.panel}><div className={`${styles.core} ${styles.metric}`}><p className={styles.value}>{projection.data.total_engagements}</p><h2>{copy.total}</h2></div></section>
        {[copy.confirmed, copy.coverage, copy.cost].map(label => <section key={label} className={styles.panel}><div className={`${styles.core} ${styles.metric}`}><p className={styles.unknown}>{copy.unavailable}</p><h2>{label}</h2><p>{copy.notRun}</p></div></section>)}
      </div>
      <section className={styles.pulse}><div><h2>{copy.pulse}</h2><p>{copy.notRun} · {copy.runReason}</p></div><button disabled={query.isFetching} onClick={() => { void query.refetch(); }}>{copy.refresh}</button></section>
      <h2>{copy.recent}</h2><p className={styles.metadata}>{copy.snapshot} <time>{projection.as_of}</time> · {stale ? copy.unavailable : copy.live}</p>
      <div className={styles.bento}>
        {projection.data.items.length === 0 && <p>{copy.empty}</p>}
        {projection.data.items.map(item => <article className={styles.panel} key={item.engagement_id}><div className={styles.core}>
          <p className={styles.kicker}>{item.assessment_mode} · {item.stage}</p><h3><Link to={`/engagements/${item.engagement_id}/overview`}>{item.name}</Link></h3>
          <p className={styles.metadata}>{item.engagement_id}</p><p>Revision {item.revision} · {item.run_state}</p>
        </div></article>)}
        <Link className={styles.create} to="/engagements/new">{copy.new} →</Link>
      </div>
      <div className={styles.pages}>{after && <button disabled={query.isFetching} onClick={() => setAfter(null)}>{copy.first}</button>}{projection.has_more && <button disabled={query.isFetching} onClick={() => setAfter(projection.next_page ?? null)}>{copy.next}</button>}</div>
    </>}
  </section>;
}
