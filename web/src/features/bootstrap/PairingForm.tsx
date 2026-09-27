import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiError } from '../../shared/api/errors';
import { copy } from './copy';
import styles from './Bootstrap.module.css';

export function PairingForm({ onPair }: { onPair: (code: string) => Promise<void> }) {
  const [code, setCode] = useState('');
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    if (!/^[A-Za-z0-9_-]{16,128}$/.test(code)) {
      setFailure(copy.invalidCode);
      input.current?.focus();
      return;
    }
    setPending(true);
    setFailure(null);
    const submitted = code;
    setCode('');
    try {
      await onPair(submitted);
    } catch (error) {
      setFailure(error instanceof ApiError ? error.message : copy.pairingUncertain);
      input.current?.focus();
    } finally {
      setPending(false);
    }
  }

  return <section className={styles.panel} aria-labelledby="pair-title"><div className={styles.core}>
    <h2 id="pair-title">{copy.pairTitle}</h2>
    <form onSubmit={submit} noValidate aria-busy={pending}>
      <label htmlFor="pair-code">{copy.code}</label>
      <p className={styles.muted} id="code-hint">{copy.codeHint}</p>
      <input ref={input} id="pair-code" type="password" value={code} maxLength={128}
        autoComplete="off" autoCapitalize="none" spellCheck={false} required
        aria-invalid={failure !== null} aria-describedby={failure ? 'code-hint code-error' : 'code-hint'}
        onChange={event => setCode(event.target.value)} readOnly={pending} />
      {failure && <p id="code-error" role="alert" className={styles.error}>{failure}</p>}
      <button type="submit" disabled={pending}>{pending ? copy.pairing : copy.pair}<span aria-hidden="true"> →</span></button>
      <p className={styles.small}>{copy.privateHint}</p>
    </form>
    <p className={styles.small}>{copy.issuer}</p>
  </div></section>;
}
