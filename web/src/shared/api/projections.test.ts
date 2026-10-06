import { expect, it, vi } from 'vitest';
import { api } from './client';
import { draft, id, projection, summary } from '../../../tests/projection-fixtures';

it('rejects consumed fields outside declared bounds, while preserving Unicode at the valid boundary', async () => {
  const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ ...draft, payload: { ...draft.payload, objective_text: 'x'.repeat(8193) } })));
  vi.stubGlobal('fetch', fetcher);
  await expect(api.engagement(id)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  fetcher.mockResolvedValue(new Response(JSON.stringify({ ...draft, payload: { ...draft.payload, name: 'x'.repeat(129) } })));
  await expect(api.engagement(id)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  fetcher.mockResolvedValue(new Response(JSON.stringify({ ...draft, payload: { ...draft.payload, objective_text: '𝔸'.repeat(8192) } })));
  expect((await api.engagement(id)).payload.objective_text).toBe('𝔸'.repeat(8192));
});

it.each([
  null, { ...projection, schema_version: 2 }, { ...projection, context: 'ENGAGEMENT' },
  { ...projection, as_of: 'not-a-date' }, { ...projection, run_id: summary.id },
  { ...projection, data: { ...projection.data, total_engagements: '1' } },
  { ...projection, data: { ...projection.data, items: [{ ...summary, revision: '2' }] } },
  { ...projection, data: { ...projection.data, metrics: { confirmed: { state: 'AVAILABLE', value: 0 } } } },
  { ...projection, has_more: true, next_page: 'unbound-cursor' },
])('rejects malformed projection at the HTTP boundary (%j)', async value => {
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(value))));
  await expect(api.dashboard(null)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
});
