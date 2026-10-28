import { afterEach, expect, it, vi } from 'vitest';
import { decodeProviderCatalog } from './providerCatalog';
import { decodeEntryTest } from './modelTest';
import { api } from './client';

const id = '11111111-1111-4111-8111-111111111111';
const other = '22222222-2222-4222-8222-222222222222';
const search = { action: 'search' as const, connection_id: id, connection_revision: 1, catalog_command_id: other, query: '', offset: 0 };
const row = { model: 'Vendor/Exact', name: 'Display name', max_output_tokens: 128, supports_max_tokens: true, reason: null };
const view = { schema_version: 1, connection_id: id, connection_revision: 1, provider: 'openrouter', catalog_command_id: other, state: 'READY', reason: null, query: '', offset: 0, next_offset: null, total: 1, entries: [row] };
const exact = {
  schema_version: 2, operation_id: id, state: 'FINISHED', state_revision: 3, finish_reason: 'COMPLETED',
  selection_revision: null, metadata_state: 'NOT_REQUESTED', metadata_command_id: null, reason: null,
  requested_provider: 'openrouter', requested_model: 'Vendor/Exact', requested_output_tokens: 64, observed_model: 'Observed/model',
  provider_status: '200', result_state: 'COMPLETED', output_state: 'COMPLETE', response_text: 'OMNIS_MODEL_TEST_OK',
  usage_state: 'UNKNOWN', input_tokens: null, output_tokens: null, reasoning_tokens: null, cost_observed: null,
  system_message: 'Respond only with OMNIS_MODEL_TEST_OK. Use no tools.',
  user_message: 'This is a synthetic local settings test. Reply with OMNIS_MODEL_TEST_OK.', calls_limit: 1, wall_seconds: 300,
  entry_id: other, entry_revision: 1, connection_id: id, connection_revision: 1, current: true,
};
afterEach(() => vi.unstubAllGlobals());

it('reads latest by exact entry without a browser pointer and rejects mismatched identity', async () => {
  const fetcher = vi.fn().mockResolvedValue(Response.json(exact)); vi.stubGlobal('fetch', fetcher);
  expect(await api.latestEntryModelTest(other)).toEqual(exact);
  expect(fetcher.mock.calls[0]?.[0]).toBe(`/api/v1/model-test/entries/latest/${other}`);
  fetcher.mockResolvedValueOnce(Response.json({ ...exact, entry_id: id }));
  await expect(api.latestEntryModelTest(other)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  fetcher.mockResolvedValueOnce(Response.json({ error: { code: 'NOT_FOUND', correlation_id: id } }, { status: 404 }));
  await expect(api.latestEntryModelTest(other)).rejects.toMatchObject({ code: 'NOT_FOUND' });
  await expect(api.latestEntryModelTest('not-a-uuid')).rejects.toMatchObject({ code: 'INVALID_INPUT' });
  expect(fetcher).toHaveBeenCalledTimes(3);
});

it('binds local pages to exact connection/revision, catalog command, query and offset', () => {
  expect(decodeProviderCatalog(view, search)).toEqual(view);
  for (const bad of [{ ...view, connection_id: other }, { ...view, connection_revision: 2 }, { ...view, catalog_command_id: id }, { ...view, query: 'different' }, { ...view, offset: 16 }, { ...view, total: 17 }, { ...view, secret: 'forbidden' }, { ...view, entries: [{ ...row, model: 'trailing\n' }] }, { ...view, entries: [{ ...row, supports_max_tokens: 'true' }] }, { ...view, state: 'STALE' }, { ...view, reason: 'raw provider error' }, { ...view, entries: [{ ...row, name: '😀'.repeat(129) }] }]) {
    expect(() => decodeProviderCatalog(bad, search)).toThrow();
  }
  expect(decodeProviderCatalog({ ...view, state: 'PARTIAL', reason: 'TOTAL_MISMATCH', entries: [{ ...row, max_output_tokens: null, supports_max_tokens: null }] }, search).state).toBe('PARTIAL');
});
it('keeps exact-entry historical success separate from current eligibility', () => {
  expect(decodeEntryTest(exact, id)).toEqual(exact);
  expect(decodeEntryTest({ ...exact, current: false }, id).result_state).toBe('COMPLETED');
  for (const bad of [{ ...exact, entry_revision: 0 }, { ...exact, selection_revision: 1 }, { ...exact, current: 'yes' }, { ...exact, operation_id: other }, { ...exact, observed_model: '😀'.repeat(257) }, { ...exact, response_text: 'x'.repeat(8193) }]) expect(() => decodeEntryTest(bad, id)).toThrow();
});
it('requires an unchanged safe-integer generation without coercion before any HTTP start', async () => {
  const fetcher = vi.fn().mockImplementation(async () => Response.json(exact)); vi.stubGlobal('fetch', fetcher);
  const intent = { expected_generation: 1, operation_id: id, entry_id: other, expected_entry_revision: 1, expected_connection_revision: 1, catalog_command_id: other, consent: true as const };
  for (const value of [null, undefined, true, '1', -1, 1.5, Number.MAX_SAFE_INTEGER + 1]) {
    Reflect.set(intent, 'expected_generation', value);
    await expect(api.startEntryModelTest(intent, 'csrf')).rejects.toMatchObject({ code: 'INVALID_INPUT' });
  }
  Reflect.deleteProperty(intent, 'expected_generation');
  await expect(api.startEntryModelTest(intent, 'csrf')).rejects.toMatchObject({ code: 'INVALID_INPUT' });
  expect(fetcher).not.toHaveBeenCalled();
  for (const generation of [0, Number.MAX_SAFE_INTEGER]) {
    intent.expected_generation = generation;
    await api.startEntryModelTest(intent, 'csrf');
    expect(fetcher.mock.lastCall?.[1].body).toBe(JSON.stringify(intent));
  }
});
it('uses paired local POST search and one explicit refresh/test, with no retry after a lost reply', async () => {
  const fetcher = vi.fn().mockImplementation(async () => new Response(JSON.stringify(view)));
  vi.stubGlobal('fetch', fetcher);
  expect(await api.providerCatalog(search, 'csrf')).toEqual(view);
  expect(fetcher.mock.calls[0]?.[0]).toBe('/api/v1/settings/provider-catalog/search');
  expect(fetcher.mock.calls[0]?.[1]).toMatchObject({ method: 'POST', credentials: 'same-origin', redirect: 'error', headers: { 'X-CSRF-Token': 'csrf' }, body: JSON.stringify(search) });
  const refresh = { action: 'refresh' as const, connection_id: id, connection_revision: 1, command_id: other };
  await api.refreshProviderCatalog(refresh, 'csrf');
  expect(fetcher.mock.calls[1]?.[0]).toBe('/api/v1/settings/provider-catalog/refresh');
  fetcher.mockResolvedValueOnce(new Response(JSON.stringify(exact)));
  const intent = { expected_generation: 1, operation_id: id, entry_id: other, expected_entry_revision: 1, expected_connection_revision: 1, catalog_command_id: other, consent: true as const };
  expect(await api.startEntryModelTest(intent, 'csrf')).toEqual(exact);
  expect(fetcher.mock.calls[2]?.[0]).toBe('/api/v1/model-test/entries');
  expect(fetcher.mock.calls[2]?.[1]).toMatchObject({ method: 'PUT', body: JSON.stringify(intent) });
  fetcher.mockRejectedValueOnce(new Error('lost reply'));
  await expect(api.startEntryModelTest(intent, 'csrf')).rejects.toMatchObject({ code: 'API_UNAVAILABLE' });
  expect(fetcher).toHaveBeenCalledTimes(4);
});
