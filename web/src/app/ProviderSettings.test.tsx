import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { App } from './App';

it('saves exact requested selection and keeps lost responses unconfirmed without retry', async () => {
  const writes: unknown[] = [];
  let lose = false;
  let selected: unknown = null;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return Response.json({ authenticated: true, csrf_token: 'a'.repeat(64) });
    if (init?.method === 'PUT') {
      const body = JSON.parse(String(init.body));
      if (body.action === 'save') { writes.push(body.selection); selected = body.selection; }
      if (lose) throw new TypeError('Synthetic lost response');
      return Response.json({ operation_id: body.operation_id, status: 'CONFIRMED', selection: selected,
        configured: selected !== null, authenticated: 'NOT_VERIFIED', reachable: 'NOT_VERIFIED', inference_ready: false });
    }
    throw new TypeError('Unexpected synthetic endpoint');
  }));
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={['/settings/providers']}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: 'Read native configuration' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Save selection' })).toBeEnabled());
  lose = true;
  await user.click(screen.getByRole('button', { name: 'Save selection' }));
  await screen.findByText('Outcome unknown. Do not repeat Save; recover the exact operation.');
  expect(writes).toEqual([{ provider: 'openai-codex', model: 'gpt-6.1-sol', effort: 'xhigh' }]);
  expect(screen.getByRole('button', { name: 'Save selection' })).toBeDisabled();
  expect(screen.getByText('Inference ready: no')).toBeInTheDocument();
});
