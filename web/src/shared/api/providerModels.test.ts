import { afterEach, expect, it, vi } from 'vitest';
import { decodeProviderModels } from './providerModels';
import { api } from './client';

const id = '11111111-1111-4111-8111-111111111111';
const other = '22222222-2222-4222-8222-222222222222';
const entry = { entry_id: id, revision: 1, connection_id: id, connection_revision: 1, model: 'Exact/ID', output_tokens: 64 };
const view = { schema_version: 1, command_id: null, registry_revision: 1, after: null, next_after: null, total: 1, entries: [entry] };
afterEach(() => vi.unstubAllGlobals());

it('preserves exact model IDs, immutable entry/key revisions and receipt context', () => {
  expect(decodeProviderModels(view, null)).toEqual(view);
  expect(decodeProviderModels({ ...view, command_id: id }, id).command_id).toBe(id);
  const entries = [entry, { ...entry, entry_id: other, model: 'exact/ID' }];
  expect(decodeProviderModels({ ...view, total: 2, entries }, null).entries).toEqual(entries);
});
it.each([
  { ...view, secret: 'forbidden' }, { ...view, command_id: id }, { ...view, registry_revision: 0 },
  { ...view, total: 65 }, { ...view, total: 17 }, { ...view, entries: Array(17).fill(entry) },
  { ...view, entries: [{ ...entry, entry_id: id + '\n' }] },
  { ...view, entries: [{ ...entry, revision: true }] },
  { ...view, entries: [{ ...entry, connection_revision: Number.MAX_SAFE_INTEGER + 1 }] },
  { ...view, entries: [{ ...entry, model: 'trailing\n' }] },
  { ...view, entries: [{ ...entry, output_tokens: 65537 }] },
  { ...view, entries: [{ ...entry, secret: 'forbidden' }] },
  { ...view, entries: [entry, { ...entry, entry_id: other }], total: 2 },
  { ...view, entries: [{ ...entry, entry_id: other }, entry], total: 2 },
  { ...view, next_after: id }, { ...view, after: other },
])('rejects incompatible, duplicate or unbound pages without reflecting values', bad => {
  expect(() => decodeProviderModels(bad, null)).toThrow('The API response is incompatible. No state was accepted.');
});
it('binds continuation reads to both the requested registry revision and cursor', () => {
  const page = { ...view, after: id, total: 17, entries: [{ ...entry, entry_id: other }] };
  expect(decodeProviderModels(page, null, 1, id)).toEqual(page);
  expect(() => decodeProviderModels(page, null, 2, id)).toThrow();
  expect(() => decodeProviderModels(page, null, 1, other)).toThrow();
  expect(() => decodeProviderModels(page, null, null, id)).toThrow();
});
it('uses paired same-origin save, exact receipt read and bound pages without retries', async () => {
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...view, command_id: id })));
  vi.stubGlobal('fetch', fetcher);
  const payload = { action: 'save_models' as const, command_id: id, expected_registry_revision: 0,
    connection_id: id, connection_revision: 1, models: [{ entry_id: id, expected_revision: 0, model: 'Exact/ID', output_tokens: 64 }] };
  expect(await api.saveProviderModels(payload, 'csrf')).toEqual({ ...view, command_id: id });
  expect(fetcher.mock.calls[0]?.[0]).toBe('/api/v1/settings/models');
  expect(fetcher.mock.calls[0]?.[1]).toMatchObject({ method: 'PUT', credentials: 'same-origin', redirect: 'error', headers: { 'X-CSRF-Token': 'csrf' }, body: JSON.stringify(payload) });
  fetcher.mockResolvedValueOnce(new Response(JSON.stringify({ ...view, command_id: id })));
  await api.providerModels(id);
  expect(fetcher.mock.calls[1]?.[0]).toBe(`/api/v1/settings/models/commands/${id}`);
  fetcher.mockResolvedValueOnce(new Response(JSON.stringify({ ...view, after: id, total: 17, entries: [{ ...entry, entry_id: other }] })));
  await api.providerModelPage(1, id);
  expect(fetcher.mock.calls[2]?.[0]).toBe(`/api/v1/settings/models/pages/1/${id}`);
  await expect(api.providerModelPage(0, 'not-a-uuid')).rejects.toMatchObject({ code: 'INVALID_INPUT' });
  fetcher.mockRejectedValueOnce(new Error('lost reply'));
  await expect(api.saveProviderModels(payload, 'csrf')).rejects.toMatchObject({ code: 'API_UNAVAILABLE' });
  expect(fetcher).toHaveBeenCalledTimes(4);
});
