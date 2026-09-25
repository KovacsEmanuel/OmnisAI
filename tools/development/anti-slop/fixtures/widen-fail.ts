export function erased(): string {
  const known = 'label';
  const broad: unknown = known;
  // SAFETY: deliberately invalid fixture for evidence loss.
  return broad as string;
}
