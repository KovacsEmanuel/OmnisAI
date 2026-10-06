import { useEffect, useRef } from 'react';
import { Link, Route, Routes, useLocation } from 'react-router';
import { Engagement, NewEngagement } from '../features/engagement/Engagement';
import { Settings } from '../features/engagement/Settings';
import { engagementCopy } from '../features/engagement/copy';
import { Dashboard } from '../features/dashboard/Dashboard';
import { Bootstrap } from '../features/bootstrap/Bootstrap';
import { BrowserSessionProvider, useSession } from '../features/bootstrap/BrowserSession';
import { copy } from '../features/bootstrap/copy';
import styles from './Shell.module.css';

function Shell() {
  const location = useLocation();
  const main = useRef<HTMLElement>(null);
  const previousPath = useRef(location.pathname);
  const { session } = useSession();
  useEffect(() => {
    // Initial entry starts at the native tab order; client navigation resets scroll/focus.
    if (previousPath.current === location.pathname) return;
    previousPath.current = location.pathname;
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
    main.current?.focus({ preventScroll: true });
  }, [location.pathname]);
  const scope = location.pathname.startsWith('/settings') ? 'settings' : /^\/engagements\/[0-9a-f-]{36}(?:\/|$)/i.test(location.pathname) ? 'engagement' : 'home';
  const selected = scope === 'engagement' ? location.pathname.split('/')[2] : null;
  return <>
    <a className={styles.skip} href="#content">{copy.skip}</a>
    <header className={styles.header}><nav aria-label="Main navigation" className={styles.nav}>
      <Link to="/" className={styles.brand ?? ''}>{copy.brand}</Link>
      <Link to="/" aria-current={scope === 'home' ? 'page' : undefined}>{copy.home}</Link>
      <Link to={selected ? `/engagements/${selected}/overview` : '/engagements'} aria-current={scope === 'engagement' ? 'page' : undefined}>{copy.engagement}</Link>
      <Link to="/settings/runtime" aria-current={scope === 'settings' ? 'page' : undefined}>{copy.settings}</Link>
    </nav></header>
    <main ref={main} id="content" tabIndex={-1} className={styles.main}>
      {!session.data || session.isError ? <Bootstrap /> : <Routes>
        <Route path="/settings" element={<Settings />} />
        <Route path="/settings/:surface" element={<Settings />} />
        <Route path="/engagements/new" element={<NewEngagement />} />
        <Route path="/engagements/:id" element={<Engagement />} />
        <Route path="/engagements/:id/:surface" element={<Engagement />} />
        <Route path="/" element={<Dashboard />} />
        <Route path="/engagements" element={<Dashboard />} />
        <Route path="*" element={<p>{engagementCopy.routeReason}</p>} />
      </Routes>}
    </main>
  </>;
}
export function App() {
  return <BrowserSessionProvider><Shell /></BrowserSessionProvider>;
}
