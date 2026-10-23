import { NavLink, useParams } from 'react-router';
import { Bootstrap } from '../bootstrap/Bootstrap';
import { ProviderSettings } from './ProviderSettings';
import { ModelTest } from './ModelTest';
import { CatalogSettings } from './CatalogSettings';
import { engagementCopy as copy } from './copy';
import styles from './Engagement.module.css';
export function Settings() {
  const { surface = 'runtime' } = useParams();
  return <><div className={styles.heading}><h1>{copy.settings}</h1></div><nav aria-label="Settings navigation" className={styles.tabs}>
    {[[copy.providers, 'providers'], [copy.skills, 'skills'], [copy.runtime, 'runtime']].map(([label, path]) => <NavLink key={path} to={`/settings/${path}`}>{label}</NavLink>)}
  </nav>{surface === 'runtime' ? <Bootstrap compact /> : <div className={styles.panel}>{surface === 'providers' ? <><ProviderSettings /><ModelTest /></> : surface === 'skills' ? <CatalogSettings /> : <p>{copy.settingsReason}</p>}</div>}</>;
}
