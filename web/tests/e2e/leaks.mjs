// Never put marker values into assertion messages or test reports.
export function assertSecretFree(markers, observations) {
  if (!Array.isArray(markers) || !Array.isArray(observations) ||
      !markers.every(value => typeof value === 'string' && value.length >= 16) ||
      !observations.every(value => typeof value === 'string')) throw new Error('Invalid leak evidence');
  if (markers.some(marker => observations.some(value => value.includes(marker)))) throw new Error('Synthetic secret leaked');
}
