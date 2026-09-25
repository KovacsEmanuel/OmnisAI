export function fabricated(input: unknown): string {
  // SAFETY: deliberately invalid fixture; this comment must not permit a chain.
  return input as unknown as string;
}
