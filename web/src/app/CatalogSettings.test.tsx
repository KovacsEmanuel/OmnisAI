import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { App } from './App';
import { health, session } from '../../tests/fixtures';
import { inspectionFixture } from '../../tests/catalog-fixtures';

it('shows retained qualification separately from material/runtime and clears it on failed refresh', async () => {
  const view = inspectionFixture(), ref = view.publication_ref;
  let fail = false;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async input => {
    const path = String(input);
    if (path === '/api/session') return Response.json(session);
    if (path === '/health/ready') return Response.json(health);
    if (path === '/api/v1/settings/catalog') return Response.json({ items: [], has_more: false, next_after: null });
    return fail ? Response.json({ error: { code: 'CONTROL_UNAVAILABLE' } }, { status: 503 }) : Response.json(view);
  }));
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[`/settings/skills?publication=${ref.id}&digest=${ref.digest}`]}><App /></MemoryRouter></QueryClientProvider>);
  await screen.findByText(/Review: RECORDED_STATIC_PASS/);
  expect(screen.getByText(/Material: NOT_VERIFIED · Runtime: NOT_AVAILABLE/)).toBeInTheDocument();
  fail = true;
  await userEvent.setup().click(screen.getByRole('button', { name: 'Reload read-only catalog' }));
  await screen.findByText('Exact publication unavailable or unsupported. No readiness is confirmed.');
  expect(screen.queryByText(/Review: RECORDED_STATIC_PASS/)).not.toBeInTheDocument();
});

it('lists published heads and keeps exact immutable selection in the reload URL without writes', async () => {
  const id = '11111111-1111-4111-8111-111111111111';
  const digest = 'a'.repeat(64);
  const reads: string[] = [];
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    expect(init?.method ?? 'GET').toBe('GET');
    const path = String(input); reads.push(path);
    if (path === '/api/session') return Response.json(session);
    if (path === '/health/ready') return Response.json(health);
    if (path === '/api/v1/settings/catalog') return Response.json({ items: [{
      publication_ref: { kind: 'catalog-publication', id, revision: 1, digest },
      profile_key: 'contract-profile', generation: 2 }], has_more: false, next_after: null });
    return Response.json({ error: { code: 'CONTROL_UNAVAILABLE' } }, { status: 503 });
  }));
  const mount = (route: string) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[route]}><App /></MemoryRouter></QueryClientProvider>);
  const mounted = mount('/settings/skills');
  await userEvent.setup().click(await screen.findByRole('button', { name: 'Inspect contract-profile' }));
  await screen.findByText('Exact publication unavailable or unsupported. No readiness is confirmed.');
  expect(reads).toContain(`/api/v1/settings/catalog/publications/${id}/${digest}`);
  expect(screen.getByText(/Applies to new runs/)).toBeInTheDocument();
  mounted.unmount(); reads.length = 0;
  mount(`/settings/skills?publication=${id}&digest=${digest}`);
  await screen.findByText('Exact publication unavailable or unsupported. No readiness is confirmed.');
  expect(reads).toContain(`/api/v1/settings/catalog/publications/${id}/${digest}`);
  expect(screen.queryByRole('button', { name: /Start|Evaluate|Publish/ })).not.toBeInTheDocument();
});
