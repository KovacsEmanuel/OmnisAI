import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { BrowserSessionProvider } from '../features/bootstrap/BrowserSession';
import { RunStop } from '../features/engagement/GlobalStop';
import { session } from '../../tests/fixtures';

it('SOURCE Stop cache observer renders updates without queryFn warnings or GET/POST on invalidation', async () => {
  const warning = vi.spyOn(console, 'warn');
  const error = vi.spyOn(console, 'error');
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async () => new Response(JSON.stringify(session)));
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><BrowserSessionProvider><RunStop run={null} /></BrowserSessionProvider></QueryClientProvider>);
  await screen.findByRole('button', { name: 'Stop run' });
  await act(async () => { await client.refetchQueries({ queryKey: ['session'] }); });
  const reads = fetcher.mock.calls.length;
  const pending = { run: '00000000-0000-4000-8000-000000000001', command: '00000000-0000-4000-8000-000000000002' };
  await act(async () => {
    client.setQueryData(['private', 'run-stops', null], [pending]);
    await client.invalidateQueries({ queryKey: ['private', 'run-stops'], refetchType: 'all' });
  });
  expect(await screen.findByRole('list', { name: 'Unacknowledged Stops' })).toHaveTextContent(pending.command);
  expect(fetcher.mock.calls).toHaveLength(reads);
  expect([...warning.mock.calls, ...error.mock.calls].flat().some(value => String(value).includes('queryFn'))).toBe(false);
  view.unmount(); client.clear();
});
