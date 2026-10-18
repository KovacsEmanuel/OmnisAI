import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import { ApiError } from '../../shared/api/errors';
import { copy, readinessCopy } from './copy';
import { PairingForm } from './PairingForm';
import { useSession } from './BrowserSession';
import fontLicense from '../../shared/styles/fonts-OFL.txt?url';
import styles from './Bootstrap.module.css';

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return <section className={styles.panel}><div className={styles.core}><h2>{title}</h2>{children}</div></section>;
}

function Failure({ error, retry }: { error: unknown; retry: () => void }) {
  return <div className={styles.error} role="alert">
    <p>{error instanceof ApiError ? error.message : copy.healthUnavailable}</p>
    {error instanceof ApiError && error.correlation && <p className={styles.mono}>Reference: {error.correlation}</p>}
    <button type="button" onClick={retry}>{copy.retry}</button>
  </div>;
}

export function Bootstrap() {
  const { session, transition, notice, logoutError, pair, logout, readPrivate } = useSession();
  const logoutPending = transition === 'logout';
  const heading = useRef<HTMLHeadingElement>(null);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const health = useQuery({ queryKey: ['health'], queryFn: ({ signal }) => api.health(signal), networkMode: 'always', retry: false, refetchInterval: 5000 });
  const status = useQuery({ queryKey: ['instance'], queryFn: ({ signal }) => readPrivate(() => api.instance(signal), signal),
    enabled: !!session.data && !session.isError && transition === 'idle', networkMode: 'always', retry: false, refetchInterval: 5000 });

  useEffect(() => {
    if (notice) heading.current?.focus();
  }, [notice]);

  const ready = health.data;
  const healthUnverified = health.isError || health.fetchStatus === 'paused' || (!!ready && now - health.dataUpdatedAt > 15000);
  const statusUnverified = status.isError || status.fetchStatus === 'paused' || (!!status.data && now - status.dataUpdatedAt > 15000);
  const sessionUnverified = transition !== 'idle' || session.fetchStatus === 'paused' || now - session.dataUpdatedAt > 30000;
  const currentHealth = ready && !healthUnverified;
  const healthLabel = (available: boolean | undefined) => healthUnverified ? 'UNKNOWN' : health.isPending ? 'LOADING' : available ? copy.ready : copy.unavailable;
  const statusLabel = status.data ? (statusUnverified ? copy.stale : copy.live) : copy.noConfirmedStatus;

  return <>
    <div>
      <div className={styles.runbar}>
        <div><span className={styles.eyebrow}>{copy.runControls}</span> <span className={styles.pill}>{copy.notRun}</span></div>
        <div className={styles.actions}><button className="withIcon" disabled aria-describedby="run-unavailable">{copy.start}<span className="buttonIcon" aria-hidden="true"><svg viewBox="0 0 24 24" focusable="false"><path d="m8 5 11 7-11 7Z" /></svg></span></button><button className={`${styles.stop} withIcon`} disabled aria-describedby="run-unavailable">{copy.stop}<span className="buttonIcon" aria-hidden="true"><svg viewBox="0 0 24 24" focusable="false"><rect x="6" y="6" width="12" height="12" rx="1" /></svg></span></button></div>
      </div>
      <p id="run-unavailable" className={styles.small}>{copy.runReason}</p>
      <div className={styles.hero}>
        <div className={styles.heroCopy}><p className={styles.eyebrow}>{copy.kicker}</p>
          <h1 ref={heading} tabIndex={-1}>{copy.title}<br /><span>{copy.accent}</span></h1>
          <p>{session.data && !session.isError ? copy.pairedIntro : copy.intro}</p>
        </div>
        {session.isPending ? <Panel title={copy.sessionTitle}><output>{copy.checking}</output></Panel>
          : session.isError ? <Panel title={copy.sessionTitle}><Failure error={session.error} retry={() => { void session.refetch(); }} /></Panel>
          : session.data ? <Panel title={copy.sessionTitle}>
            <span className={styles.pill}>{sessionUnverified ? copy.unverified : copy.sessionActive}</span>
            <p>{copy.boundary}</p><button onClick={() => { void logout(); }} disabled={logoutPending}>{logoutPending ? copy.loggingOut : copy.logout}</button>
            {logoutError !== null && <><p role="alert">{copy.logoutUncertain}</p><Failure error={logoutError} retry={() => { void session.refetch(); }} /></>}
          </Panel> : <PairingForm onPair={async code => {
            await pair(code);
            heading.current?.focus();
          }} />}
      </div>
      {notice && <output className={styles.notice}>{notice}</output>}
      <section aria-label="Service readiness">
        {health.isPending && <output>{copy.checkingHealth}</output>}
        {health.isError && <Failure error={health.error} retry={() => { void health.refetch(); }} />}
        {healthUnverified && !health.isError && <output className={styles.notice}>{copy.staleReadiness} <button onClick={() => { void health.refetch(); }}>{copy.retry}</button></output>}
        {currentHealth && ready.dashboard_reason && <output className={styles.notice}>{readinessCopy[ready.dashboard_reason]}</output>}
        <div className={styles.metrics}>
          <Panel title={copy.api}><p className={styles.readiness}>{healthLabel(ready?.api_ready)}</p><p className={styles.small}>PostgreSQL · compatible schema</p></Panel>
          <Panel title={copy.dashboard}><p className={styles.readiness}>{healthLabel(ready?.dashboard_ready)}</p><p className={styles.small}>Trusted build · private control</p></Panel>
          <Panel title={copy.assessment}><p className={styles.readiness}>{copy.unavailable}</p><p className={styles.small}>{copy.assessmentReason}</p></Panel>
        </div>
      </section>
      {session.data && !session.isError && <Panel title={copy.instanceTitle}>
        <div className={styles.cardHead}><p className={styles.small}>{statusLabel}</p><button onClick={() => { void status.refetch(); void health.refetch(); }} disabled={status.isFetching}>{status.isFetching ? copy.refreshing : copy.refresh}</button></div>
        {status.isPending && <output>{copy.loading}</output>}
        {status.isError && <Failure error={status.error} retry={() => { void status.refetch(); }} />}
        {status.data && <dl className={styles.details}>
          <div className={styles.identity}><dt>{copy.instanceId}</dt><dd className={styles.mono}>{status.data.instance_id}</dd></div>
          <div><dt>{copy.generation}</dt><dd>{status.data.generation}</dd></div>
          <div><dt>{copy.epoch}</dt><dd>{status.data.supervisor_epoch}</dd></div>
          <div><dt>{copy.supervisor}</dt><dd>{status.data.supervisor_ready ? copy.ready : copy.unavailable}</dd></div>
          <div><dt>{copy.admission}</dt><dd>{status.data.admission_open ? copy.open : copy.closed}</dd></div>
          <div><dt>{copy.shutdown}</dt><dd className={styles.mono}>{status.data.shutdown_command_id ?? copy.none}</dd></div>
          <div><dt>{copy.quiesced}</dt><dd>{status.data.quiesced_generation ?? copy.none}</dd></div>
          <div><dt>{copy.finalized}</dt><dd>{status.data.shutdown_finalized ? copy.yes : copy.no}</dd></div>
        </dl>}
      </Panel>}
      <footer className={styles.footer}>{copy.footer} · <a href={fontLicense}>Font license</a></footer>
    </div>
  </>;
}
