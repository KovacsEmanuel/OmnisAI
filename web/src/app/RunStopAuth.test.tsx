import { CancelledError, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { BrowserSessionProvider, useSession } from '../features/bootstrap/BrowserSession';
import { RunStop } from '../features/engagement/GlobalStop';
import { ApiError } from '../shared/api/errors';
import { session } from '../../tests/fixtures';
import { syntheticRun } from '../../tests/run-fixtures';

it.each(['healthy', '401', 'expire', 'logout'] as const)('fences delayed Stop hydration at the actual commit after %s', async boundary => {
  sessionStorage.clear();
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(session.csrf_token));
  const scope = Array.from(new Uint8Array(bytes), value => value.toString(16).padStart(2, '0')).join('');
  const pending = { run: syntheticRun.run_id, command: syntheticRun.setup_ref.id };
  const saved = JSON.stringify({ scope, value: pending });
  sessionStorage.setItem('omnis-run-stop', saved);
  let release: ((value: ArrayBuffer) => void) | undefined;
  const held = new Promise<ArrayBuffer>(resolve => { release = resolve; });
  const digest = vi.spyOn(crypto.subtle, 'digest').mockReturnValue(held);
  let paired = true;
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async input => {
    if (String(input) === '/api/logout') { paired = false; return new Response(null, { status: 204 }); }
    return paired ? Response.json(session) : Response.json({ error: { code: 'UNAUTHENTICATED', correlation_id: syntheticRun.run_id } }, { status: 401 });
  });
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const writes = vi.spyOn(client, 'setQueryData');
  let invalidate: (() => Promise<void>) | undefined;
  function Consumer() {
    const owner = useSession();
    invalidate = async () => {
      if (boundary === 'expire') owner.expire();
      if (boundary === 'logout') await owner.logout();
      if (boundary === '401') await owner.readPrivate(async () => { throw new ApiError('UNAUTHENTICATED'); }, new AbortController().signal).catch(() => undefined);
    };
    return owner.session.data ? <RunStop run={syntheticRun} /> : <p>Unpaired</p>;
  }
  const view = render(<QueryClientProvider client={client}><BrowserSessionProvider><Consumer /></BrowserSessionProvider></QueryClientProvider>);
  await waitFor(() => expect(digest).toHaveBeenCalledTimes(1));
  const initialWrites = writes.mock.calls.filter(([key]) => key[0] === 'private');
  expect(initialWrites).toHaveLength(0);
  await act(async () => {
    await invalidate?.();
    if (boundary !== 'healthy') expect(client.getQueryCache().findAll({ queryKey: ['private'] })).toHaveLength(0);
    if (!release) throw new Error('Digest not held');
    release(bytes);
    await held;
    await Promise.resolve();
  });
  const explicit = writes.mock.calls.filter(([key]) => key[0] === 'private');
  // A late explicit write is a different producer from disabled-observer recreation.
  expect(explicit.map(([key]) => key)).toEqual(boundary === 'healthy' ? [['private', 'run-stops', scope]] : []);
  if (boundary === 'healthy') {
    expect(client.getQueryData(['private', 'run-stops', scope])).toEqual([pending]);
    expect(await screen.findByRole('list', { name: 'Unacknowledged Stops' })).toHaveTextContent(pending.command);
  } else {
    expect(screen.getByText('Unpaired')).toBeVisible();
    expect(client.getQueryCache().findAll({ queryKey: ['private'] })).toHaveLength(0);
  }
  expect(sessionStorage.getItem('omnis-run-stop')).toBe(saved);
  expect(fetcher.mock.calls.every(([path]) => ['/api/session', '/api/logout'].includes(String(path)))).toBe(true);
  view.unmount(); client.clear(); sessionStorage.clear();
});

it('rejects old read/commit closures even after a new authenticated life with the same synthetic identity', async () => {
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async () => Response.json(session)));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  let owner: ReturnType<typeof useSession> | undefined;
  function Consumer() { owner = useSession(); return <p>{owner.session.data ? 'Paired' : 'Unpaired'}</p>; }
  const view = render(<QueryClientProvider client={client}><BrowserSessionProvider><Consumer /></BrowserSessionProvider></QueryClientProvider>);
  await screen.findByText('Paired');
  if (!owner) throw new Error('Missing session owner');
  const old = owner;
  const sink = vi.fn(async () => 'read');
  const commit = vi.fn();
  const signal = new AbortController().signal;
  expect(await old.readPrivate(sink, signal)).toBe('read');
  expect(old.commitPrivate(commit, signal)).toBe(true);
  await act(async () => { old.expire(); });
  await expect(old.readPrivate(sink, signal)).rejects.toBeInstanceOf(CancelledError);
  expect(old.commitPrivate(commit, signal)).toBe(false);
  await act(async () => { await owner?.pair('synthetic-pairing-code'); });
  await screen.findByText('Paired');
  await expect(old.readPrivate(sink, signal)).rejects.toBeInstanceOf(CancelledError);
  expect(old.commitPrivate(commit, signal)).toBe(false);
  expect(await owner.readPrivate(sink, signal)).toBe('read');
  expect(owner.commitPrivate(commit, signal)).toBe(true);
  expect(sink).toHaveBeenCalledTimes(2);
  expect(commit).toHaveBeenCalledTimes(2);
  view.unmount(); client.clear();
});
