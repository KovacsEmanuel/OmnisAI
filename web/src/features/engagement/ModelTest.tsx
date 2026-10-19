import { useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import { useSession } from '../bootstrap/BrowserSession';
import styles from './Engagement.module.css';

export function ModelTest() {
  const { session, transition, readPrivate } = useSession();
  const client = useQueryClient();
  const [sending, setSending] = useState(false);
  const [unknown, setUnknown] = useState(false);
  const attempted = useRef(false);
  const key = ['private', 'model-test'];
  const query = useQuery({ queryKey: key,
    queryFn: ({ signal }) => readPrivate(() => api.modelTest(signal), signal),
    enabled: !!session.data && !session.isError && transition === 'idle', retry: false,
    refetchInterval: query => query.state.data?.status === 'PENDING' ? 1000 : false,
    refetchOnWindowFocus: true });
  const observed = query.data;
  const allowed = observed?.status === 'AVAILABLE' && !query.isFetching && !query.isError && !sending && !unknown && !attempted.current;
  async function send() {
    if (!allowed || !session.data || transition !== 'idle') return;
    attempted.current = true;
    setSending(true);
    const csrf = session.data.csrf_token;
    try {
      const value = await readPrivate(() => api.startModelTest(crypto.randomUUID(), csrf), new AbortController().signal);
      client.setQueryData(key, value);
    } catch {
      setUnknown(true);
      void query.refetch();
    } finally {
      setSending(false);
    }
  }
  return <section className={styles.panel} aria-label="Test model">
    <div className={styles.core}>
      <h2>Test model</h2>
      <p>Mesaj sintetic fix · 1 apel / 300s · fără tools sau trafic către țintă.</p>
      <p>System: <span className={styles.objective}>Respond briefly to this synthetic model test. Use no tools.</span></p>
      <p>User: <span className={styles.objective}>Map supplied structured synthetic records.</span></p>
      <p>Cerut: openai-codex / gpt-6.1-sol / xhigh</p>
      <p>Observat: {observed?.observed_model ?? 'UNKNOWN'} / {observed?.observed_effort ?? 'UNKNOWN'}</p>
      <output aria-live="polite">
        {(unknown && !observed?.operation_id) || query.isError ? 'UNKNOWN — verifică aceeași operație; nu retrimite.' : sending || observed?.status === 'PENDING' ? 'În curs…' : observed?.status === 'COMPLETE' ? 'Răspuns primit' : observed?.status === 'UNAVAILABLE' ? 'Pregătirea sursei publicate sau bugetul testului nu este disponibil.' : observed?.status === 'UNKNOWN' ? 'UNKNOWN — nu se retrimite.' : observed?.status === 'AVAILABLE' ? 'Pregătit pentru test' : 'Se citește starea…'}
      </output>
      <div className={styles.providerActions}>
        <button disabled={!allowed} onClick={() => { void send(); }}>Trimite testul modelului</button>
        <button disabled={query.isFetching || sending} onClick={() => { void query.refetch(); }}>Citește starea testului</button>
      </div>
      {observed?.response_text !== null && observed?.response_text !== undefined && <p className={styles.objective} aria-label="Răspuns model">{observed.response_text}</p>}
      <p>Durată: {observed?.duration_ms === null || observed?.duration_ms === undefined ? 'UNKNOWN' : `${observed.duration_ms} ms`} · Usage input/output/reasoning: {observed?.input_tokens ?? 'UNKNOWN'} / {observed?.output_tokens ?? 'UNKNOWN'} / {observed?.reasoning_tokens ?? 'UNKNOWN'}</p>
      <p className={styles.providerHint}>Stop-ul instanței oprește testul. Reload citește aceeași operație; nu pornește un apel nou. Conectat local nu înseamnă inferență verificată.</p>
    </div>
  </section>;
}
