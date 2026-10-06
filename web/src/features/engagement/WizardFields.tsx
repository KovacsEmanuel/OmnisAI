import type { ReactNode } from 'react';
import type { FieldError } from '../../shared/api/errors';
import styles from './Wizard.module.css';

export const errorText: Record<FieldError['code'], string> = {
  REQUIRED: 'Required value.', INVALID_VALUE: 'Invalid value.', TOO_LONG: 'Exceeds the field limit.',
  TOO_MANY: 'Too many entries.', UNKNOWN_FIELD: 'Unsupported field.',
};
export const focusField = (field: string) =>
  /^(?:application_context\.(?:seed_urls|priority_workflows|test_objects)|scope\.[0-9]+\.exclusions|objective_constraints\.[0-9]+\.operation_refs)\.[0-9]+$/.test(field)
    ? field.slice(0, field.lastIndexOf('.')) : field;
export const fieldId = (field: string) => `draft-${focusField(field).replaceAll('.', '-')}`;
export function Field({ path, label, errors, children, hint }: { path: string; label: string; errors: FieldError[];
  children: (props: { id: string; 'aria-invalid': boolean; 'aria-describedby': string | undefined }) => ReactNode; hint?: string }) {
  const problem = errors.find(error => focusField(error.field) === path);
  const id = fieldId(path);
  return <div className={styles.field}>
    <label htmlFor={id}>{label}</label>
    {children({ id, 'aria-invalid': !!problem, 'aria-describedby': problem ? `${id}-error` : hint ? `${id}-hint` : undefined })}
    {hint && <small id={`${id}-hint`}>{hint}</small>}
    {problem && <span id={`${id}-error`} className={styles.error}>{errorText[problem.code]}</span>}
  </div>;
}
