import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { App } from './App';

it('connects once, displays only fixed challenge, cancels same operation and clears code', async () => {
  const actions: string[] = [];
  const ids: string[] = [];
  let current = { operation_id: '00000000-0000-0000-0000-000000000000', action: 'current' };
  const selected = { provider: 'openai-codex', model: 'gpt-6.1-sol', effort: 'xhigh' };
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return Response.json({ authenticated: true, csrf_token: 'a'.repeat(64) });
    const body = init?.method === 'PUT' ? JSON.parse(String(init.body)) : current;
    current = body;
    if (init?.method === 'PUT') { actions.push(body.action); ids.push(body.operation_id); }
    const pending = body.action === 'connect';
    return Response.json({ operation_id: body.operation_id, status: pending ? 'PENDING' : 'CONFIRMED',
      selection: pending ? null : selected, configured: !pending, authenticated: pending ? 'NOT_VERIFIED' : 'ABSENT',
      reachable: 'NOT_VERIFIED', inference_ready: false, oauth: pending ? 'CHALLENGE' : body.action === 'cancel' ? 'CANCELLED' : 'NONE',
      challenge: pending ? { code: 'ABCD-EFGH', url: 'https://auth.openai.com/codex/device' } : null });
  }));
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={['/settings/providers']}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: 'Read native configuration' }));
  await user.click(await screen.findByRole('button', { name: 'Connect Codex' }));
  await screen.findByText('ABCD-EFGH');
  expect(screen.getByRole('link', { name: 'Open Codex device authorization' })).toHaveAttribute('href', 'https://auth.openai.com/codex/device');
  await user.click(screen.getByRole('button', { name: 'Cancel connection' }));
  await waitFor(() => expect(screen.queryByText('ABCD-EFGH')).not.toBeInTheDocument());
  expect(actions).toEqual(['read', 'connect', 'cancel']);
  expect(ids[1]).toBe(ids[2]);
  expect(screen.getByText('Inference ready: no')).toBeInTheDocument();
});

it('reads a local grant and logs out once without claiming provider readiness', async () => {
  const actions: string[] = [];
  const selected = { provider: 'openai-codex', model: 'gpt-6.1-sol', effort: 'xhigh' };
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return Response.json({ authenticated: true, csrf_token: 'a'.repeat(64) });
    if (init?.method === 'PUT') {
      const body = JSON.parse(String(init.body));
      actions.push(body.action);
      return Response.json({ operation_id: body.operation_id, status: 'CONFIRMED', selection: selected,
        configured: true, authenticated: body.action === 'auth_read' ? 'LOCAL_PRESENT' : body.action === 'logout' ? 'ABSENT' : 'NOT_VERIFIED',
        reachable: 'NOT_VERIFIED', inference_ready: false });
    }
    throw new TypeError('Unexpected synthetic endpoint');
  }));
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={['/settings/providers']}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: 'Read native configuration' }));
  await user.click(await screen.findByRole('button', { name: 'Read local Codex grant' }));
  await screen.findByText('Local grant: present — not provider-verified');
  expect(screen.getByText('Provider reachable: not verified')).toBeInTheDocument();
  expect(screen.getByText('Inference ready: no')).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Log out of Codex locally' }));
  await screen.findByText('Local grant: absent — native readback');
  expect(actions).toEqual(['read', 'auth_read', 'logout']);
  expect(screen.getByRole('button', { name: 'Log out of Codex locally' })).toBeDisabled();
});

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
  await screen.findByText('Outcome unknown. Do not repeat this action; recover the exact operation.');
  expect(writes).toEqual([{ provider: 'openai-codex', model: 'gpt-6.1-sol', effort: 'xhigh' }]);
  expect(screen.getByRole('button', { name: 'Save selection' })).toBeDisabled();
  expect(screen.getByText('Inference ready: no')).toBeInTheDocument();
});
