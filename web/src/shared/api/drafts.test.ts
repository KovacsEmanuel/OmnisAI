import { expect, it, vi } from 'vitest';
import type { components } from './generated';
import { api } from './client';
import { ApiError, decodeError } from './errors';
import { decodeRevision } from './drafts';

const id = '00000000-0000-4000-8000-000000000010';
const revisionId = '00000000-0000-4000-8000-000000000011';
const csrf = 'a'.repeat(64);
const payload: components['schemas']['EngagementDraft'] = {
  name: 'Synthetic case',
  authorization: { owner: 'Owner', statement: 'Synthetic permission', valid_from: '2030-01-01T00:00:00Z', valid_until: '2030-12-31T00:00:00Z' },
  scope: [{ origin: 'https://synthetic.invalid', port: 443, path_prefix: '/api', exclusions: ['/private'], access: 'BLOCKED' }],
  assessment_mode: 'FOCUSED_TEST', objective_text: '  Δ\n🧪  ',
  objective_constraints: [{ id: revisionId, kind: 'READ_ONLY', text: 'No writes', operation_refs: [] }],
  workflow_profile_ref: null,
  application_context: { seed_urls: ['https://synthetic.invalid/api'], priority_workflows: ['Review'], test_objects: ['Record'], import_ref: null },
  effect_rules: [{ effect_class: 'READ_ONLY_KNOWN', decision: 'ALLOW', note: 'Synthetic' }],
  budgets: { max_requests: 10, max_duration_seconds: 60, max_storage_bytes: 1024, validation_reserved_requests: 2, max_model_calls: 0 },
  data_policy: { model_projection: 'NONE', research_egress: 'NONE', retention_days: 1 },
  business_matrix: [{ id: revisionId, principal: 'Anonymous', role: 'Visitor', tenant: 'T', object: 'Record', operation: 'GET', expected: 'DENY', source: 'Synthetic', source_revision: 1 }],
  business_rules_ref: null,
};
const view = { schema_version: 1, kind: 'engagement-revision', id: revisionId, engagement_id: id,
  revision: 2, digest: 'b'.repeat(64), created_at: '2030-01-01T00:00:00Z', payload };

it('creates, edits with exact CAS headers, and reads the complete authored payload without normalizing text', async () => {
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async (_path, init) =>
    new Response(JSON.stringify({ ...view, revision: init?.method === 'POST' ? 1 : 2 }), { status: init?.method === 'POST' ? 201 : 200 }));
  vi.stubGlobal('fetch', fetcher);
  expect((await api.createDraft(payload, csrf)).payload).toEqual(payload);
  expect((await api.updateDraft(id, payload, 1, 'b'.repeat(64), revisionId, csrf)).payload.objective_text).toBe('  Δ\n🧪  ');
  expect((await api.draft(id)).payload).toEqual(payload);
  expect(fetcher.mock.calls[0]).toEqual(['/api/v1/engagements', expect.objectContaining({
    method: 'POST', body: JSON.stringify(payload), credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
  })]);
  expect(fetcher.mock.calls[1]).toEqual([`/api/v1/engagements/${id}`, expect.objectContaining({
    method: 'PUT', body: JSON.stringify(payload), headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf,
      'If-Match': `"rev-1-${'b'.repeat(64)}"`, 'X-Command-ID': revisionId },
  })]);
});

it('rejects an incomplete or cross-engagement write receipt and does not turn it into confirmed state', async () => {
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ ...view, engagement_id: revisionId }))));
  await expect(api.updateDraft(id, payload, 1, 'b'.repeat(64), revisionId, csrf)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
});

it('strictly decodes allowlisted per-field errors and never reflects input values or arbitrary paths', () => {
  const error = decodeError({ error: { code: 'INVALID_INPUT', correlation_id: id,
    field_errors: [{ field: 'business_matrix.0.principal', code: 'REQUIRED' }, { field: 'objective_text', code: 'TOO_LONG' }] } });
  expect(error).toBeInstanceOf(ApiError);
  expect(error.fieldErrors).toEqual([{ field: 'business_matrix.0.principal', code: 'REQUIRED' }, { field: 'objective_text', code: 'TOO_LONG' }]);
  for (const field of ['<img src=x>', 'business_matrix.100.principal', 'authorization.secret']) {
    expect(decodeError({ error: { code: 'INVALID_INPUT', correlation_id: id, field_errors: [{ field, code: 'REQUIRED' }] } }).code).toBe('INVALID_RESPONSE');
  }
});

it('retains bounded nested list field paths from the declared API error DTO', () => {
  for (const field of ['application_context.seed_urls.0', 'scope.0.exclusions.1']) {
    expect(decodeError({ error: { code: 'INVALID_INPUT', correlation_id: id,
      field_errors: [{ field, code: 'INVALID_VALUE' }] } }).fieldErrors).toEqual([{ field, code: 'INVALID_VALUE' }]);
  }
  expect(decodeError({ error: { code: 'INVALID_INPUT', correlation_id: id,
    field_errors: [{ field: 'application_context.seed_urls.65', code: 'INVALID_VALUE' }] } }).code).toBe('INVALID_RESPONSE');
});

it('accepts the exact noncompressed IPv6 origin the API accepts without canonicalizing it', () => {
  for (const exact of ['https://[2001:0db8:0000:0000:0000:0000:0000:0001]', 'https://0177.0.0.1']) {
    const original = { ...payload, scope: [{ ...payload.scope[0]!, origin: exact }] };
    expect(decodeRevision({ ...view, payload: original }, id).payload.scope[0]!.origin).toBe(exact);
  }
});

it('rejects an origin or seed URL with an invalid empty port delimiter on the same revision channel', () => {
  for (const changes of [
    { scope: [{ ...payload.scope[0]!, origin: 'https://synthetic.invalid:' }] },
    { application_context: { ...payload.application_context, seed_urls: ['https://synthetic.invalid:/api'] } },
  ]) {
    expect(() => decodeRevision({ ...view, payload: { ...payload, ...changes } }, id)).toThrowError(ApiError);
  }
});

it('refuses a duplicate revision write receipt rather than reporting a newer confirmed draft', async () => {
  const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ ...view, revision: 1 })));
  vi.stubGlobal('fetch', fetcher);
  await expect(api.updateDraft(id, { ...payload, objective_text: 'Changed' }, 1, 'b'.repeat(64), revisionId, csrf))
    .rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  expect(fetcher).toHaveBeenCalledTimes(1);
});
