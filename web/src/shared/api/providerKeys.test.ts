import { expect, it } from 'vitest';
import { decodeKeySettings } from './providerKeys';
const id = '11111111-1111-4111-8111-111111111111';
const view = { schema_version: 2, command_id: null, vault_status: 'LOCKED', connections: [{ connection_id: id, provider: 'openrouter', revision: 1, enabled: true, credential_present: false }], selection: null, reachable: 'NOT_VERIFIED' };
it('decodes local presence, not reachability, and preserves stale saved selections', () => {
  expect(decodeKeySettings(view, null)).toEqual(view);
  const selected = { connection_id: id, connection_revision: 2, model: 'Exact/ID', output_tokens: 65536 };
  expect(decodeKeySettings({ ...view, selection: { selection_id: id, revision: 1, default: selected, brain: null, investigator: null, validator: null } }, null).selection?.default).toEqual(selected);
});
it.each([
  { ...view, secret: 'must-not-be-accepted' }, { ...view, command_id: id }, { ...view, reachable: 'READY' },
  { ...view, connections: [...view.connections, ...view.connections] },
  { ...view, connections: [{ ...view.connections[0], credential_present: true }] },
  { ...view, connections: [{ ...view.connections[0], revision: Number.MAX_SAFE_INTEGER + 1 }] },
  { ...view, selection: { selection_id: id, revision: 1, default: { connection_id: id, connection_revision: 1, model: 'with space', output_tokens: 1 }, brain: null, investigator: null, validator: null } },
])('rejects incompatible or secret-bearing readback without reflecting values', bad => {
  expect(() => decodeKeySettings(bad, null)).toThrow('The API response is incompatible. No state was accepted.');
});
