import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { health, session } from '../../tests/fixtures';
import { projection, summary } from '../../tests/projection-fixtures';
import { App } from './App';

it('replaces cursor pages as whole snapshots instead of appending incompatible data', async () => {
  const items = Array.from({ length: 20 }, (_, index) => ({ ...summary,
    name: `Synthetic page-one ${index}`, engagement_id: `00000000-0000-4000-8000-${String(index + 100).padStart(12, '0')}` }));
  const cursor = `d1.20.${items[19]?.engagement_id}`;
  const first = { ...projection, has_more: true, next_page: cursor, data: { ...projection.data, total_engagements: 21, items } };
  const second = { ...projection, as_of: '2026-10-06T06:01:00Z', data: { ...projection.data, total_engagements: 21 } };
  let release: ((value: Response) => void) | undefined;
  const held = new Promise<Response>(resolve => { release = resolve; });
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async input => {
    const path = String(input);
    if (path.includes('after=')) return held;
    return new Response(JSON.stringify(path === '/api/session' ? session : path === '/health/ready' ? health : first));
  });
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><App /></MemoryRouter></QueryClientProvider>);
  await screen.findByRole('link', { name: 'Synthetic page-one 19' });
  await userEvent.setup().click(screen.getByRole('button', { name: 'Next page' }));
  expect(await screen.findByText('Loading dashboard…')).toBeVisible();
  expect(screen.getByRole('link', { name: 'Synthetic page-one 19' })).toBeVisible();
  expect(screen.getByText('STALE — showing the last confirmed dashboard, not current state.')).toBeVisible();
  await act(async () => { if (!release) throw new Error('Missing page resolver'); release(new Response(JSON.stringify(second))); });
  expect(await screen.findByRole('link', { name: summary.name })).toBeVisible();
  expect(screen.queryByRole('link', { name: 'Synthetic page-one 19' })).not.toBeInTheDocument();
  expect(screen.getByText(second.as_of)).toBeVisible();
  expect(fetcher).toHaveBeenCalledWith(`/api/v1/dashboard?limit=20&after=${cursor}`, expect.objectContaining({ credentials: 'same-origin' }));
});

it('renders the authenticated bounded dashboard from the real HTTP client', async () => {
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async input => {
    const path = String(input);
    const payload = path === '/api/session' ? session : path === '/health/ready' ? health : projection;
    return new Response(JSON.stringify(payload));
  });
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><App /></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByRole('heading', { name: 'Recent engagements' })).toBeVisible();
  expect(screen.getByRole('link', { name: summary.name })).toHaveAttribute('href', `/engagements/${summary.engagement_id}/overview`);
  expect(within(screen.getByRole('region', { name: 'Total engagements' })).getByText('1')).toBeVisible();
  expect(screen.getAllByText('UNAVAILABLE').length).toBeGreaterThanOrEqual(3);
  expect(fetcher).toHaveBeenCalledWith('/api/v1/dashboard?limit=20', expect.objectContaining({ credentials: 'same-origin', cache: 'no-store' }));
  expect(screen.queryByRole('button', { name: 'Start assessment' })).not.toBeInTheDocument();
});
