import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router';
import { api } from '../../shared/api/client';
import { ApiError } from '../../shared/api/errors';
import { copy, readinessCopy } from './copy';
import { PairingForm } from './PairingForm';
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
  const client = useQueryClient();
  const [notice, setNotice] = useState<string | null>(null);
  const [logoutPending, setLogoutPending] = useState(false);
  const [logoutError, setLogoutError] = useState<unknown>(null);
  const hadSession = useRef(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const session = useQuery({ queryKey: ['session'], queryFn: ({ signal }) => api.session(signal), retry: false, refetchInterval: 15000 });
  const health = useQuery({ queryKey: ['health'], queryFn: ({ signal }) => api.health(signal), retry: false, refetchInterval: 5000 });
  const status = useQuery({ queryKey: ['instance'], queryFn: ({ signal }) => api.instance(signal),
    enabled: !!session.data && !session.isError, retry: false, refetchInterval: 5000 });

  useEffect(() => {
    if (session.data) hadSession.current = true;
    if (session.data === null && hadSession.current) {
      setNotice(copy.expired);
      hadSession.current = false;
      client.removeQueries({ queryKey: ['instance'] });
      heading.current?.focus();
    }
  }, [session.data, client]);

  useEffect(() => {
    if (status.error instanceof ApiError && status.error.code === 'UNAUTHENTICATED') {
      client.setQueryData(['session'], null);
    }
  }, [status.error, client]);

  async function logout() {
    if (!session.data || logoutPending) return;
    setLogoutPending(true);
    setLogoutError(null);
    try {
      await api.logout(session.data.csrf_token);
      await client.cancelQueries({ queryKey: ['session'] });
      const readback = await api.session();
      if (readback !== null) throw new Error(copy.logoutUncertain);
      hadSession.current = false;
      client.removeQueries({ queryKey: ['instance'] });
      client.setQueryData(['session'], null);
      setNotice(copy.loggedOut);
      heading.current?.focus();
    } catch (error) {
      setLogoutError(error);
    } finally {
      setLogoutPending(false);
    }
  }

  const ready = health.data;
  const currentHealth = ready && !health.isError;
  const healthLabel = (available: boolean | undefined) => health.isPending ? 'LOADING' : health.isError ? 'UNKNOWN' : available ? copy.ready : copy.unavailable;

  return <>
    <a className={styles.skip} href="#content">{copy.skip}</a>
    <header className={styles.header}><nav className={styles.nav} aria-label="Main navigation">
      <Link className={styles.brand} to="/">{copy.brand}</Link>
      <Link to="/" aria-current="page">{copy.home}</Link>
      <button disabled aria-describedby="engagement-unavailable">{copy.engagement}</button>
      <button disabled aria-describedby="settings-unavailable">{copy.settings}</button>
      <span className={styles.small}>{copy.local}</span>
    </nav></header>
    <main id="content" tabIndex={-1} className={styles.main}>
      <div className={styles.runbar}>
        <div><span className={styles.eyebrow}>{copy.runControls}</span> <span className={styles.pill}>{copy.notRun}</span></div>
        <div className={styles.actions}><button disabled aria-describedby="run-unavailable">{copy.start}</button><button className={styles.stop} disabled aria-describedby="run-unavailable">{copy.stop}</button></div>
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
            <span className={styles.pill}>{copy.sessionActive}</span>
            <p>{copy.boundary}</p><button onClick={() => { void logout(); }} disabled={logoutPending}>{logoutPending ? copy.loggingOut : copy.logout}</button>
            {logoutError !== null && <><p role="alert">{copy.logoutUncertain}</p><Failure error={logoutError} retry={() => { void session.refetch(); }} /></>}
          </Panel> : <PairingForm onPaired={async grant => {
            await client.cancelQueries({ queryKey: ['session'] });
            const readback = await api.session();
            if (readback === null) throw new ApiError('UNAUTHENTICATED');
            if (readback.csrf_token !== grant.csrf_token) throw new ApiError('INVALID_RESPONSE');
            setNotice(null);
            setLogoutError(null);
            client.setQueryData(['session'], readback);
            heading.current?.focus();
          }} />}
      </div>
      {notice && <output className={styles.notice}>{notice}</output>}
      <section aria-label="Service readiness">
        {health.isPending && <output>{copy.checkingHealth}</output>}
        {health.isError && <Failure error={health.error} retry={() => { void health.refetch(); }} />}
        {currentHealth && ready.dashboard_reason && <output className={styles.notice}>{readinessCopy[ready.dashboard_reason]}</output>}
        <div className={styles.metrics}>
          <Panel title={copy.api}><p className={styles.readiness}>{healthLabel(ready?.api_ready)}</p><p className={styles.small}>PostgreSQL · compatible schema</p></Panel>
          <Panel title={copy.dashboard}><p className={styles.readiness}>{healthLabel(ready?.dashboard_ready)}</p><p className={styles.small}>Trusted build · private control</p></Panel>
          <Panel title={copy.assessment}><p className={styles.readiness}>{copy.unavailable}</p><p className={styles.small}>{copy.assessmentReason}</p></Panel>
        </div>
      </section>
      {session.data && !session.isError && <Panel title={copy.instanceTitle}>
        <div className={styles.cardHead}><p className={styles.small}>{status.isError ? copy.stale : copy.live}</p><button onClick={() => { void status.refetch(); void health.refetch(); }} disabled={status.isFetching}>{status.isFetching ? copy.refreshing : copy.refresh}</button></div>
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
      <h2 className={styles.sectionTitle}>{copy.futureTitle}</h2>
      <div className={styles.future}>
        <Panel title={copy.engagement}><span className={styles.pill}>{copy.unavailable}</span><p id="engagement-unavailable">{copy.engagementReason}</p></Panel>
        <Panel title={copy.settings}><span className={styles.pill}>{copy.unavailable}</span><p id="settings-unavailable">{copy.settingsReason}</p></Panel>
      </div>
      <footer className={styles.footer}>{copy.footer} · <a href={fontLicense}>Font license</a></footer>
    </main>
  </>;
}
