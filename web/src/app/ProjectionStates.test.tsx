import { onlineManager, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { health, instance, session } from '../../tests/fixtures';
import { draft, id, projection, summary } from '../../tests/projection-fixtures';
import { App } from './App';

function deferred<T>() {
  let settle: ((value: T) => void) | undefined;
  const promise = new Promise<T>(resolve => { settle = resolve; });
  return { promise, resolve(value: T) { if (!settle) throw new Error('Missing resolver'); settle(value); } };
}
function response(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status }); }
function denial() { return response({ error: { code: 'UNAUTHENTICATED', correlation_id: id } }, 401); }
function mount(fetcher: typeof fetch, route = '/') {
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[route]}><App /></MemoryRouter></QueryClientProvider>);
  return client;
}
function local(path: string) { return response(path === '/api/session' ? session : path === '/health/ready' ? health : instance); }

it('a dashboard 401 expires auth and removes every private query', async () => {
  let expired = false;
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async input => String(input).startsWith('/api/v1/dashboard') ? expired ? denial() : response(projection) : local(String(input)));
  const client = mount(fetcher);
  await screen.findByRole('link', { name: summary.name });
  expired = true;
  await userEvent.setup().click(screen.getByRole('button', { name: 'Refresh dashboard' }));
  expect(await screen.findByLabelText('Pairing code')).toBeVisible();
  expect(screen.queryByRole('link', { name: summary.name })).not.toBeInTheDocument();
  expect(client.getQueryCache().findAll({ queryKey: ['private'] })).toHaveLength(0);
});

it('logout cancels held selected reads, purges private data, and never accepts their late completion', async () => {
  let paired = true;
  let selectedSignal: AbortSignal | null | undefined;
  const held = deferred<Response>();
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input);
    if (path === '/api/session') return paired ? response(session) : denial();
    if (path === '/api/logout') { paired = false; return new Response(null, { status: 204 }); }
    if (path.startsWith('/api/v1/dashboard')) return response(projection);
    if (path === `/api/v1/engagements/${id}`) { selectedSignal = init?.signal; return held.promise; }
    return local(path);
  });
  const client = mount(fetcher);
  const user = userEvent.setup();
  await user.click(await screen.findByRole('link', { name: summary.name }));
  await screen.findByText('Loading engagement…');
  await user.click(screen.getByRole('link', { name: 'Settings' }));
  await screen.findByText(instance.instance_id);
  await user.click(screen.getByRole('button', { name: 'Log out' }));
  await screen.findByText('Logged out. The server session was revoked.');
  expect(selectedSignal?.aborted).toBe(true);
  await act(async () => { held.resolve(response(draft)); await new Promise(resolve => setTimeout(resolve, 25)); });
  expect(client.getQueryCache().findAll({ queryKey: ['private'] })).toHaveLength(0);
  expect(screen.queryByRole('heading', { name: summary.name })).not.toBeInTheDocument();
});

it('marks aged dashboard snapshots stale while an offline loopback refresh is still in flight', async () => {
  const held = deferred<Response>();
  let fresh = true;
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async input => String(input).startsWith('/api/v1/dashboard') ? fresh ? response(projection) : held.promise : local(String(input)));
  const client = mount(fetcher);
  await screen.findByRole('link', { name: summary.name });
  fresh = false;
  act(() => { client.setQueryData(['private', 'dashboard', null], projection, { updatedAt: Date.now() - 16000 }); onlineManager.setOnline(false); });
  try {
    expect(await screen.findByText('STALE — showing the last confirmed dashboard, not current state.')).toBeVisible();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Refresh dashboard' }));
    await waitFor(() => expect(fetcher.mock.calls.filter(([input]) => String(input).startsWith('/api/v1/dashboard'))).toHaveLength(2));
  } finally {
    act(() => { onlineManager.setOnline(true); });
    await act(async () => { held.resolve(response(projection)); });
  }
});

it('loading / empty / malformed first response never become invented metrics', async () => {
  const held = deferred<Response>();
  let result = held.promise;
  mount(vi.fn<typeof fetch>().mockImplementation(async input => String(input).startsWith('/api/v1/dashboard') ? result : local(String(input))));
  await screen.findByText('Loading dashboard…');
  expect(screen.getByRole('region', { name: 'Dashboard projection' })).toHaveAttribute('aria-busy', 'true');
  expect(screen.queryByText('0', { exact: true })).not.toBeInTheDocument();
  await act(async () => { held.resolve(response({ ...projection, data: { ...projection.data, items: [], total_engagements: 0 } })); });
  expect(await screen.findByText('No engagements saved yet.')).toBeVisible();
  result = Promise.resolve(response({ malformed: true }));
  await userEvent.setup().click(screen.getByRole('button', { name: 'Refresh dashboard' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('No state was accepted');
  expect(await screen.findByText('STALE — showing the last confirmed dashboard, not current state.')).toBeVisible();
});

it('a private error has no stale claim without an earlier accepted response', async () => {
  mount(vi.fn<typeof fetch>().mockImplementation(async input => String(input).startsWith('/api/v1/dashboard') ? response({ invalid: true }) : local(String(input))));
  expect(await screen.findByRole('alert')).toHaveTextContent('No state was accepted');
  expect(screen.queryByText(/last confirmed dashboard/)).not.toBeInTheDocument();
  expect(screen.queryByText('0', { exact: true })).not.toBeInTheDocument();
});

it('a held old dashboard 401 cannot expire a newer paired session', async () => {
  const held = deferred<Response>();
  let paired = true;
  let hold = false;
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async input => {
    const path = String(input);
    if (path === '/api/session') return paired ? response(session) : denial();
    if (path === '/api/pairing') { paired = true; return response(session); }
    if (path.startsWith('/api/v1/dashboard')) return hold ? held.promise : response(projection);
    return local(path);
  });
  const client = mount(fetcher);
  await screen.findByRole('link', { name: summary.name });
  hold = true;
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: 'Refresh dashboard' }));
  paired = false;
  await act(async () => { await client.refetchQueries({ queryKey: ['session'] }); });
  await screen.findByLabelText('Pairing code');
  hold = false;
  await user.type(screen.getByLabelText('Pairing code'), 'synthetic-new-pairing-code');
  await user.click(screen.getByRole('button', { name: 'Pair browser' }));
  await screen.findByRole('link', { name: summary.name });
  await act(async () => { held.resolve(denial()); await new Promise(resolve => setTimeout(resolve, 25)); });
  expect(screen.queryByLabelText('Pairing code')).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: summary.name })).toBeVisible();
});

it('a selected 401 expires auth and never retains the selected revision', async () => {
  let expired = false;
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async input => {
    const path = String(input);
    return path === `/api/v1/engagements/${id}` ? expired ? denial() : response(draft) : local(path);
  });
  const client = mount(fetcher, `/engagements/${id}/overview`);
  await screen.findByRole('heading', { name: summary.name });
  expired = true;
  await userEvent.setup().click(screen.getByRole('button', { name: 'Refresh engagement' }));
  expect(await screen.findByLabelText('Pairing code')).toBeVisible();
  expect(client.getQueryCache().findAll({ queryKey: ['private'] })).toHaveLength(0);
  expect(screen.queryByText(summary.digest)).not.toBeInTheDocument();
});

it('does not fetch private routes until the initial session is confirmed', async () => {
  const held = deferred<Response>();
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async input => String(input) === '/api/session' ? held.promise : response(health));
  mount(fetcher, `/engagements/${id}/overview`);
  await screen.findByText('Checking local session…');
  expect(fetcher.mock.calls.some(([input]) => String(input).startsWith('/api/v1/'))).toBe(false);
  await act(async () => { held.resolve(denial()); });
  await screen.findByLabelText('Pairing code');
  expect(fetcher.mock.calls.some(([input]) => String(input).startsWith('/api/v1/'))).toBe(false);
});
