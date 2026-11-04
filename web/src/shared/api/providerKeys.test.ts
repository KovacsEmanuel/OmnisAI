import { expect, it } from 'vitest';
import { decodeKeySettings } from './providerKeys';
import revoked from '../../../tests/provider-key-revoked.json';
const id = '11111111-1111-4111-8111-111111111111';
const view = { schema_version: 2, command_id: null, vault_status: 'LOCKED', connections: [{ connection_id: id, provider: 'openrouter', revision: 1, enabled: true, credential_present: false }], selection: null, reachable: 'NOT_VERIFIED' };
const choice = { connection_id: id, connection_revision: 1, model: 'Exact/Model', output_tokens: 64 };
const legacySelection = { selection_id: id, revision: 1, default: choice, brain: null, investigator: null, validator: null };
it.each([null, { ...choice, model: 'Recon/Model', connection_revision: 7 }])('preserves versioned Recon and historical selection bytes', recon => {
  const legacy = { ...view, selection: legacySelection };
  expect(JSON.stringify(decodeKeySettings(legacy, null).selection)).toBe(JSON.stringify(legacySelection));
  const next = { ...view, selection: { ...legacySelection, schema_version: 2, recon } };
  expect(decodeKeySettings(next, null)).toEqual(next);
  expect(decodeKeySettings({ ...next, command_id: id }, id)).toEqual({ ...next, command_id: id });
});
it.each([
  { ...legacySelection, recon: null }, { ...legacySelection, schema_version: 2 },
  { ...legacySelection, schema_version: 3, recon: null },
  { ...legacySelection, schema_version: 2, recon: { ...choice, output_tokens: true } },
  { ...legacySelection, schema_version: 2, recon: { ...choice, model: 'not valid' } },
])('refuses incomplete, unknown-version or malformed Recon selections', selection => {
  expect(() => decodeKeySettings({ ...view, selection }, null)).toThrow('The API response is incompatible. No state was accepted.');
});
it('decodes local presence, not reachability, and preserves stale saved selections', () => {
  expect(decodeKeySettings(view, null)).toEqual(view);
  const selected = { connection_id: id, connection_revision: 2, model: 'Exact/ID', output_tokens: 65536 };
  expect(decodeKeySettings({ ...view, selection: { selection_id: id, revision: 1, default: selected, brain: null, investigator: null, validator: null } }, null).selection?.default).toEqual(selected);
});
it('decodes the owner-produced revoked connection with retained ciphertext, including its exact receipt', () => {
  expect(decodeKeySettings(revoked, null)).toEqual(revoked);
  expect(decodeKeySettings({ ...revoked, command_id: id }, id)).toEqual({ ...revoked, command_id: id });
});
it('decodes global LOCKED with one present connection and another missing credential', () => {
  const mixed = { ...view, connections: [{ ...view.connections[0], credential_present: true },
    { ...revoked.connections[0], provider: 'orcarouter', enabled: true, credential_present: false }] };
  expect(decodeKeySettings(mixed, null)).toEqual(mixed);
});
it.each([
  { ...view, secret: 'must-not-be-accepted' }, { ...view, command_id: id }, { ...view, reachable: 'READY' },
  { ...view, connections: [...view.connections, ...view.connections] },
  { ...view, connections: [{ ...view.connections[0], credential_present: 'true' }] },
  { ...view, connections: [{ ...view.connections[0], revision: Number.MAX_SAFE_INTEGER + 1 }] },
  { ...view, selection: { selection_id: id, revision: 1, default: { connection_id: id, connection_revision: 1, model: 'with space', output_tokens: 1 }, brain: null, investigator: null, validator: null } },
])('rejects incompatible or secret-bearing readback without reflecting values', bad => {
  expect(() => decodeKeySettings(bad, null)).toThrow('The API response is incompatible. No state was accepted.');
});
