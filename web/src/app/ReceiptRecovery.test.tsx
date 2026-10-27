import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { csrf, engagementId, payload, revision } from '../../tests/draft-fixtures';
import { App } from './App';

it.each([
  ['POST', 'network'], ['PUT', 'network'], ['POST', 'BODY_TOO_LARGE'], ['PUT', 'BODY_TOO_LARGE'],
])('keeps the %s receipt barrier through edits until explicit GET reconciliation (%s)', async (method, fault) => {
  let writes = 0;
  let failRead = true;
  let stored = revision;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return new Response(JSON.stringify({ authenticated: true, csrf_token: csrf }));
    if (init?.method === 'POST' || init?.method === 'PUT') {
      writes++;
      stored = { ...revision, revision: init.method === 'POST' ? 1 : stored.revision + 1,
        digest: (writes === 1 ? 'c' : 'd').repeat(64), payload: JSON.parse(String(init.body)) };
      return new Response(JSON.stringify(stored), { status: init.method === 'POST' ? 201 : 200 });
    }
    if (writes && failRead && fault === 'network') throw new TypeError('Synthetic GET connection loss');
    if (writes && failRead) return new Response(JSON.stringify({ error: { code: 'BODY_TOO_LARGE', correlation_id: engagementId } }), { status: 413 });
    return new Response(JSON.stringify(stored));
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[method === 'POST' ? '/engagements/new' : `/engagements/${engagementId}/setup`]}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  const name = await screen.findByLabelText('Engagement name');
  if (method === 'PUT') await waitFor(() => expect(name).toHaveValue(payload.name));
  else {
    for (const [label, value] of [['Authorization owner', payload.authorization.owner], ['Authorization statement', payload.authorization.statement],
      ['Valid from (UTC)', payload.authorization.valid_from], ['Valid until (UTC)', payload.authorization.valid_until], ['Scope origin', payload.scope[0]!.origin]]) {
      fireEvent.change(screen.getByLabelText(label!), { target: { value } });
    }
  }
  fireEvent.change(name, { target: { value: 'Receipt-bound local snapshot' } });
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  await screen.findByText('Unconfirmed readback');
  expect(screen.getByRole('button', { name: 'Save draft' })).toBeDisabled();
  fireEvent.change(name, { target: { value: 'Edit after unconfirmed receipt' } });
  expect(writes).toBe(1);
  expect.soft(screen.getByRole('button', { name: 'Save draft' })).toBeDisabled();
  expect.soft(screen.queryByRole('button', { name: 'Retry exact GET readback' })).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  expect(writes).toBe(1);
  failRead = false;
  await user.click(screen.getByRole('button', { name: 'Retry exact GET readback' }));
  await screen.findByText('Conflict · local edits preserved');
  expect(name).toHaveValue('Edit after unconfirmed receipt');
  expect(stored.payload.name).toBe('Receipt-bound local snapshot');
  expect(writes).toBe(1);
  await user.click(screen.getByRole('button', { name: 'Use server revision as base, keep local edits (Save separately)' }));
  expect(writes).toBe(1);
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  await screen.findByText(`Saved · revision ${method === 'POST' ? 2 : 3}`);
  expect(writes).toBe(2);
  expect(stored.payload.name).toBe('Edit after unconfirmed receipt');
});

it.each(['keep', 'discard'] as const)('reconciles a lost PUT without a receipt against the unchanged revision before choosing to %s local edits', async choice => {
  let writes = 0;
  let stored = revision;
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input);
    if (path === '/api/session') return new Response(JSON.stringify({ authenticated: true, csrf_token: csrf }));
    if (path === `/api/v1/engagements/${engagementId}`) {
      if (init?.method === 'PUT') {
        writes++;
        expect(init.headers).toMatchObject({ 'If-Match': `"rev-1-${revision.digest}"` });
        if (writes === 1) throw new TypeError('Synthetic connection loss before the PUT was stored');
        stored = { ...revision, id: '00000000-0000-4000-8000-000000000022', revision: 2,
          digest: 'c'.repeat(64), payload: JSON.parse(String(init.body)) };
      }
      return new Response(JSON.stringify(stored));
    }
    throw new Error('Unexpected synthetic request');
  });
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/engagements/${engagementId}/setup`]}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  const name = await screen.findByLabelText('Engagement name');
  await waitFor(() => expect(name).toHaveValue(payload.name));
  fireEvent.change(name, { target: { value: 'Local edit before lost PUT' } });
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  await screen.findByText('Save outcome uncertain');
  expect(stored).toEqual(revision);
  fireEvent.change(name, { target: { value: 'Local edit after lost PUT' } });
  expect(screen.getByRole('button', { name: 'Save draft' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
  await user.click(screen.getByRole('button', { name: 'Refresh engagement' }));
  await waitFor(() => expect(client.getQueryState(['private', 'draft', engagementId])?.fetchStatus).toBe('idle'));
  expect(screen.getByText('Save outcome uncertain')).toBeVisible();
  expect(writes).toBe(1);
  await user.click(screen.getByRole('button', { name: 'Compare server revision' }));
  await screen.findByText('Conflict · local edits preserved');
  expect(name).toHaveValue('Local edit after lost PUT');
  expect(screen.getByText(`Server revision 1 · digest ${revision.digest}. Local edits remain unsaved.`)).toBeVisible();
  expect(writes).toBe(1);
  if (choice === 'discard') {
    await user.click(screen.getByRole('button', { name: 'Discard local edits and load server revision' }));
    expect(name).toHaveValue(payload.name);
    expect(screen.getByText('Saved · revision 1')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Save draft' })).toBeDisabled();
    expect(writes).toBe(1);
  } else {
    await user.click(screen.getByRole('button', { name: 'Use server revision as base, keep local edits (Save separately)' }));
    expect(name).toHaveValue('Local edit after lost PUT');
    expect(screen.getByText('Unsaved changes')).toBeVisible();
    expect(writes).toBe(1);
    await user.click(screen.getByRole('button', { name: 'Save draft' }));
    await screen.findByText('Saved · revision 2');
    expect(stored.payload.name).toBe('Local edit after lost PUT');
    expect(writes).toBe(2);
  }
});

it('does not infer an identity or offer GET reconciliation after a first POST loses its receipt', async () => {
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return new Response(JSON.stringify({ authenticated: true, csrf_token: csrf }));
    if (String(input) === '/api/v1/model-test') return new Response('{}');
    if (String(input) === '/api/v1/engagements' && init?.method === 'POST') throw new TypeError('Synthetic lost POST receipt');
    throw new Error('Unexpected synthetic request');
  });
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/engagements/new']}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  const name = await screen.findByLabelText('Engagement name');
  fireEvent.change(name, { target: { value: 'Unidentified local draft' } });
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  await screen.findByText('Save outcome uncertain');
  fireEvent.change(name, { target: { value: 'Keep unidentified local draft' } });
  expect(name).toHaveValue('Keep unidentified local draft');
  expect(screen.queryByRole('button', { name: 'Compare server revision' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Retry exact GET readback' })).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  await user.click(screen.getByRole('button', { name: 'Next' }));
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1);
  expect(fetcher.mock.calls.filter(([input]) => String(input).startsWith('/api/v1/engagements/'))).toHaveLength(0);
  expect(client.getQueryCache().findAll({ queryKey: ['private', 'draft'] }).filter(query => query.queryKey[2] !== undefined)).toHaveLength(0);
});
