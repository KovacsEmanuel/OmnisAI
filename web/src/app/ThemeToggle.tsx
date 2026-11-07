import { useLayoutEffect, useState } from 'react';
import styles from './ThemeToggle.module.css';

export function ThemeToggle() {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    try { return localStorage.getItem('omnis-theme') === 'light' ? 'light' : 'dark'; }
    catch { return 'dark'; }
  });
  useLayoutEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
  function toggle() {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    try { localStorage.setItem('omnis-theme', next); }
    catch { return; } // Storage may be blocked; the in-memory preference still works.
  }
  const label = theme === 'dark' ? 'Light theme' : 'Dark theme';
  return <button type="button" className={styles.toggle} onClick={toggle} aria-label={label} title={label}>
    <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true" focusable="false">
      {theme === 'dark' ? <path d="M21 12.6A9 9 0 1 1 11.4 3 7 7 0 0 0 21 12.6z" /> : <>
        <circle cx="12" cy="12" r="4.2" />
        <path d="M12 2.5v2.4M12 19.1v2.4M4.6 4.6l1.7 1.7M17.7 17.7l1.7 1.7M2.5 12h2.4M19.1 12h2.4M4.6 19.4l1.7-1.7M17.7 6.3l1.7-1.7" />
      </>}
    </svg>
  </button>;
}
