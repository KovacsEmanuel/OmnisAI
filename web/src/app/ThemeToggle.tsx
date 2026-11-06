import { useLayoutEffect, useState } from 'react';

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
  return <button type="button" onClick={toggle}>{theme === 'dark' ? 'Light theme' : 'Dark theme'}</button>;
}
