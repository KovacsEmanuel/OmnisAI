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
