// Boundary validation must remain valid; unknown is not prohibited.
export function parseLabel(input: unknown): string {
  if (typeof input !== 'string') throw new Error('Expected a string');
  return input.trim();
}
export const phase = 'draft' as const;
export function checkedElement(value: Element): HTMLElement {
  if (!(value instanceof HTMLElement)) throw new Error('Expected HTML');
  // SAFETY: instanceof above checks the same value before returning it.
  return value as HTMLElement;
}
