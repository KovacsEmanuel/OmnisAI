import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { api } from '../shared/api/client';
import { ApiError } from '../shared/api/errors';
import { health, instance, session } from '../../tests/fixtures';
import { App } from './App';

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><App /></MemoryRouter></QueryClientProvider>);
  return client;
}

function deferred<T>() {
  let settle: ((value: T) => void) | undefined;
  const promise = new Promise<T>(resolve => { settle = resolve; });
  return { promise, resolve(value: T) { if (!settle) throw new Error('Missing deferred resolver'); settle(value); } };
}

it('pairs a browser, reads actual instance state, and confirms logout with a session readback', async () => {
  vi.spyOn(api, 'health').mockResolvedValue(health);
  const sessionRead = vi.spyOn(api, 'session').mockResolvedValue(null);
  vi.spyOn(api, 'instance').mockResolvedValue(instance);
  const pair = vi.spyOn(api, 'pair').mockImplementation(async () => { sessionRead.mockResolvedValue(session); return session; });
  const logout = vi.spyOn(api, 'logout').mockImplementation(async () => { sessionRead.mockResolvedValue(null); });
  mount();
  const user = userEvent.setup();
  const input = await screen.findByLabelText('Pairing code');
  await user.type(input, 'synthetic-pairing-code');
  await user.click(screen.getByRole('button', { name: 'Pair browser' }));
  expect(pair).toHaveBeenCalledExactlyOnceWith('synthetic-pairing-code');
  expect(await screen.findByText(instance.instance_id)).toBeVisible();
  expect(screen.getByRole('button', { name: 'Start assessment' })).toBeDisabled();
  expect(screen.queryByLabelText('Pairing code')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Log out' }));
  await waitFor(() => expect(logout).toHaveBeenCalledExactlyOnceWith(session.csrf_token));
  expect(await screen.findByText('Logged out. The server session was revoked.')).toBeVisible();
  expect(screen.queryByText(instance.instance_id)).not.toBeInTheDocument();
  expect(localStorage.length + sessionStorage.length).toBe(0);
});

it('keeps pairing errors beside an empty field with keyboard focus', async () => {
  vi.spyOn(api, 'health').mockResolvedValue(health);
  vi.spyOn(api, 'session').mockResolvedValue(null);
  vi.spyOn(api, 'pair').mockRejectedValue(new ApiError('PAIRING_DENIED'));
  mount();
  const user = userEvent.setup();
  const input = await screen.findByLabelText('Pairing code');
  await user.type(input, 'synthetic-refused-code');
  await user.keyboard('{Enter}');
  expect(await screen.findByRole('alert')).toHaveTextContent('invalid, expired or already used');
  expect(input).toHaveValue('');
  expect(input).toHaveFocus();
  expect(input).toHaveAttribute('aria-invalid', 'true');
  expect(input).toHaveAccessibleDescription(/Pairing refused/);
});

it('does not claim pairing when the cookie session cannot be read back', async () => {
  vi.spyOn(api, 'health').mockResolvedValue(health);
  vi.spyOn(api, 'session').mockResolvedValue(null);
  vi.spyOn(api, 'pair').mockResolvedValue(session);
  const status = vi.spyOn(api, 'instance').mockResolvedValue(instance);
  mount();
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText('Pairing code'), 'synthetic-pairing-code');
  await user.keyboard('{Enter}');
  expect(await screen.findByRole('alert')).toHaveTextContent('session expired or was revoked');
  expect(status).not.toHaveBeenCalled();
});

it('clears authenticated state and explains a session expired during status refresh', async () => {
  vi.spyOn(api, 'health').mockResolvedValue(health);
  vi.spyOn(api, 'session').mockResolvedValue(session);
  const status = vi.spyOn(api, 'instance').mockResolvedValue(instance);
  mount();
  await screen.findByText(instance.instance_id);
  status.mockRejectedValue(new ApiError('UNAUTHENTICATED'));
  await userEvent.setup().click(screen.getByRole('button', { name: 'Refresh status' }));
  expect(await screen.findByLabelText('Pairing code')).toBeVisible();
  expect(screen.getByText('Your session expired or was revoked. Pair this browser again.')).toBeVisible();
  expect(screen.queryByText(instance.instance_id)).not.toBeInTheDocument();
});

it('shows loading, then explicit API failure rather than a pairing form or fake zero metrics', async () => {
  vi.spyOn(api, 'health').mockResolvedValue(health);
  let fail: (reason: Error) => void = () => { throw new Error('Deferred fetch not initialized'); };
  vi.spyOn(api, 'session').mockReturnValue(new Promise((_, reject) => { fail = reject; }));
  mount();
  expect(screen.getByText('Checking local session…')).toBeVisible();
  fail(new ApiError('API_UNAVAILABLE'));
  expect(await screen.findByRole('alert')).toHaveTextContent('API could not be reached');
  expect(screen.queryByLabelText('Pairing code')).not.toBeInTheDocument();
});

it('a late session poll cannot restore authenticated state after a newer instance 401', async () => {
  vi.spyOn(api, 'health').mockResolvedValue(health);
  const read = vi.spyOn(api, 'session').mockResolvedValue(session);
  const status = vi.spyOn(api, 'instance').mockResolvedValue(instance);
  const client = mount();
  await screen.findByText(instance.instance_id);
  const older = deferred<typeof session | null>();
  read.mockReturnValueOnce(older.promise);
  let pending: Promise<void> | undefined;
  act(() => { pending = client.refetchQueries({ queryKey: ['session'] }); });
  await waitFor(() => expect(read).toHaveBeenCalledTimes(2));
  status.mockRejectedValue(new ApiError('UNAUTHENTICATED'));
  await userEvent.setup().click(screen.getByRole('button', { name: 'Refresh status' }));
  await screen.findByLabelText('Pairing code');
  await act(async () => { older.resolve(session); await pending; });
  expect(screen.getByLabelText('Pairing code')).toBeVisible();
  expect(screen.queryByText('PAIRED')).not.toBeInTheDocument();
});

it('a held pairing readback cannot overtake confirmed logout via concurrent polling', async () => {
  vi.spyOn(api, 'health').mockResolvedValue(health);
  const read = vi.spyOn(api, 'session').mockResolvedValue(null);
  vi.spyOn(api, 'instance').mockResolvedValue(instance);
  vi.spyOn(api, 'pair').mockResolvedValue(session);
  vi.spyOn(api, 'logout').mockImplementation(async () => { read.mockResolvedValue(null); });
  const client = mount();
  const user = userEvent.setup();
  const input = await screen.findByLabelText('Pairing code');
  const older = deferred<typeof session | null>();
  read.mockReturnValueOnce(older.promise).mockResolvedValue(session);
  await user.type(input, 'synthetic-pairing-code');
  await user.keyboard('{Enter}');
  await waitFor(() => expect(read).toHaveBeenCalledTimes(2));
  await act(async () => {
    await client.refetchQueries({ queryKey: ['session'] });
    await new Promise(resolve => setTimeout(resolve, 25));
  });
  const prematureLogout = screen.queryByRole('button', { name: 'Log out' });
  if (prematureLogout) {
    // Reproduce the pre-fix race: the poll exposes Logout ahead of the held readback.
    await user.click(prematureLogout);
    await screen.findByText('Logged out. The server session was revoked.');
    await act(async () => {
      older.resolve(session);
      await new Promise(resolve => setTimeout(resolve, 25));
    });
  } else {
    // Correctly serialized path: no poll may expose a session before pairing readback.
    expect(screen.getByRole('button', { name: 'Pairing…' })).toBeDisabled();
    await act(async () => { older.resolve(session); });
    await user.click(await screen.findByRole('button', { name: 'Log out' }));
  }
  expect(await screen.findByText('Logged out. The server session was revoked.')).toBeVisible();
  expect(screen.queryByText('PAIRED')).not.toBeInTheDocument();
});
