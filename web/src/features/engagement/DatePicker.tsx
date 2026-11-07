import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { isUtcTimestamp } from '../../shared/api/drafts';
import type { Draft } from '../../shared/api/drafts';
import type { FieldError } from '../../shared/api/errors';
import { Field, fieldId } from './WizardFields';
import styles from './DatePicker.module.css';
import { observeControl } from '../../shared/uiDiagnostics';

const dayLabel = (date: Date) => new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(date);
const dayKey = (date: Date) => date.toISOString().slice(0, 10);
function utcDay(year: number, month: number, day: number) {
  const date = new Date(0);
  date.setUTCFullYear(year, month, day);
  date.setUTCHours(0, 0, 0, 0);
  return date;
}
export function readableUtc(value: string | null) {
  return isUtcTimestamp(value) ? dayLabel(new Date(value)) : 'Choose date';
}
export function validitySummary(value: Draft['authorization']) {
  return value.valid_from === null && value.valid_until === null ? 'No end date — until closed or revoked'
    : `${readableUtc(value.valid_from)} – ${readableUtc(value.valid_until)}`;
}

export function DatePicker({ path, label, value, endOfDay, errors, onChange }: {
  path: string; label: string; value: string | null; endOfDay?: boolean;
  errors: FieldError[]; onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(() => new Date());
  const [timeError, setTimeError] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const focused = useRef<HTMLButtonElement>(null);
  const dialogId = `${fieldId(path)}-calendar`;
  const today = dayKey(new Date());
  const selected = isUtcTimestamp(value) ? value.slice(0, 10) : null;
  const clock = isUtcTimestamp(value) ? value.slice(11, 19) : endOfDay ? '23:59:59' : '00:00:00';
  const month = new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(cursor);
  const start = utcDay(cursor.getUTCFullYear(), cursor.getUTCMonth(), 1);
  const offset = (start.getUTCDay() + 6) % 7;
  const length = utcDay(cursor.getUTCFullYear(), cursor.getUTCMonth() + 1, 0).getUTCDate();
  const cells = Array.from({ length: Math.ceil((offset + length) / 7) * 7 }, (_, index) => {
    const day = index - offset + 1;
    return day >= 1 && day <= length ? utcDay(cursor.getUTCFullYear(), cursor.getUTCMonth(), day) : null;
  });
  useEffect(() => { if (open) focused.current?.focus(); }, [open, cursor]);
  useEffect(() => {
    if (!open) return;
    function outside(event: PointerEvent) {
      if (event.target instanceof Node && !root.current?.contains(event.target)) setOpen(false);
    }
    function leave(event: FocusEvent) {
      if (event.target instanceof Node && !root.current?.contains(event.target)) setOpen(false);
    }
    document.addEventListener('pointerdown', outside);
    document.addEventListener('focusin', leave);
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('focusin', leave); };
  }, [open]);
  function close() { setOpen(false); trigger.current?.focus(); }
  function moveMonth(amount: number) {
    const next = utcDay(cursor.getUTCFullYear(), cursor.getUTCMonth() + amount, 1);
    if (next.getUTCFullYear() < 1 || next.getUTCFullYear() > 9999) return;
    const last = utcDay(next.getUTCFullYear(), next.getUTCMonth() + 1, 0).getUTCDate();
    setCursor(utcDay(next.getUTCFullYear(), next.getUTCMonth(), Math.min(cursor.getUTCDate(), last)));
  }
  function keys(event: KeyboardEvent<HTMLButtonElement>) {
    const weekday = (cursor.getUTCDay() + 6) % 7;
    const delta: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7, Home: -weekday, End: 6 - weekday };
    const days = delta[event.key];
    if (event.key === 'PageUp' || event.key === 'PageDown') {
      event.preventDefault(); moveMonth((event.key === 'PageUp' ? -1 : 1) * (event.shiftKey ? 12 : 1));
    } else if (days !== undefined) {
      event.preventDefault();
      const next = utcDay(cursor.getUTCFullYear(), cursor.getUTCMonth(), cursor.getUTCDate() + days);
      if (next.getUTCFullYear() >= 1 && next.getUTCFullYear() <= 9999) setCursor(next);
    }
  }
  return <div ref={root} className={styles.anchor}>
    <Field path={path} label={label} errors={errors}>{props => <button {...props} ref={trigger} type="button"
      aria-haspopup="dialog" aria-expanded={open} aria-controls={open ? dialogId : undefined}
      onClick={() => {
        if (open) close();
        else { setCursor(new Date(`${selected ?? today}T00:00:00Z`)); setTimeError(false); setOpen(true); }
      }}>{readableUtc(value)}</button>}</Field>
    {open && <dialog open id={dialogId} aria-label={`${label} calendar`} className={styles.panel}
      onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); close(); } }}>
      <div className={styles.heading}>
        <button type="button" aria-label="Previous month" onClick={() => moveMonth(-1)}>‹</button>
        <strong aria-live="polite">{month}</strong>
        <button type="button" aria-label="Next month" onClick={() => moveMonth(1)}>›</button>
      </div>
      <table aria-label={`${month} UTC`} className={styles.days}>
        <thead><tr>{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(day => <th key={day} scope="col">{day}</th>)}</tr></thead>
        <tbody>{Array.from({ length: cells.length / 7 }, (_, row) => <tr key={row}>{cells.slice(row * 7, row * 7 + 7).map((date, column) =>
          <td key={column}>{date && <button type="button" aria-pressed={dayKey(date) === selected}
            ref={dayKey(date) === dayKey(cursor) ? focused : undefined} tabIndex={dayKey(date) === dayKey(cursor) ? 0 : -1}
            aria-label={dayLabel(date)} aria-current={dayKey(date) === today ? 'date' : undefined} onKeyDown={keys}
            onClick={() => { observeControl('calendar_choice'); onChange(`${dayKey(date)}T${clock}Z`); close(); }}>{date.getUTCDate()}</button>}</td>)}</tr>)}</tbody>
      </table>
      <p className={styles.hint}>UTC · new dates use {endOfDay ? '23:59:59 (end of day)' : '00:00:00 (start of day)'}. Existing times are preserved.</p>
      <label className={styles.time} htmlFor={`${dialogId}-time`}>Time (UTC)
        <input id={`${dialogId}-time`} type="time" step="1" value={clock} disabled={!selected} aria-invalid={timeError}
          onChange={event => {
            const time = event.target.value.length === 5 ? `${event.target.value}:00` : event.target.value;
            const next = `${selected}T${time}Z`;
            if (isUtcTimestamp(next)) { onChange(next); setTimeError(false); }
            else setTimeError(true);
          }} />
      </label>
      {timeError && <p role="alert">Enter a valid UTC time; the previous value is unchanged.</p>}
      <button type="button" onClick={close}>Done</button>
    </dialog>}
  </div>;
}
