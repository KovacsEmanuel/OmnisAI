import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { health, session } from '../../tests/fixtures';
import { draft, id, projection, summary } from '../../tests/projection-fixtures';
import { api } from '../shared/api/client';
import { App } from './App';

it('selects a persisted draft, preserves identity and scope, and navigates editable Setup / New without implicit writes', async () => {
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async input => {
    const path = String(input);
    return new Response(JSON.stringify(path === '/api/session' ? session : path === '/health/ready' ? health : path === `/api/v1/engagements/${id}` ? draft : projection));
  });
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole('link', { name: summary.name }));
  expect(await screen.findByRole('heading', { name: summary.name })).toBeVisible();
  expect(screen.getByText(draft.payload.objective_text, { normalizer: value => value })).toBeVisible();
  expect(screen.getByText(summary.digest)).toBeVisible();
  expect(screen.getByText(summary.id)).toBeVisible();
  expect(screen.getByText('https://synthetic.invalid')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Start assessment' })).toBeDisabled();
  await user.click(screen.getByRole('link', { name: 'Setup' }));
  expect(await screen.findByRole('region', { name: 'Draft setup' })).toBeVisible();
  expect(await screen.findByLabelText('Engagement name')).toHaveValue(summary.name);
  expect(screen.getByRole('heading', { name: summary.name })).toBeVisible();
  expect(screen.getByRole('button', { name: 'Save draft' })).toBeDisabled();
  await user.click(screen.getByRole('link', { name: 'Brain stream' }));
  expect(await screen.findByText(/not implemented for this draft/)).toBeVisible();
  expect(screen.queryByText(draft.payload.objective_text)).not.toBeInTheDocument();
  await user.click(screen.getByRole('link', { name: 'Home' }));
  await user.click((await screen.findAllByRole('link', { name: /New engagement/ }))[0]!);
  expect(await screen.findByRole('heading', { name: 'New engagement' })).toBeVisible();
  expect(screen.getByLabelText('Engagement name')).toHaveValue('');
  expect(screen.getByText('Unsaved changes')).toBeVisible();
  expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
});

it.each(['overview', 'setup'])('exposes busy while loading and revalidating %s, then clears it after success or failure', async surface => {
  let release: ((response: Response) => void) | undefined;
  const hold = () => new Promise<Response>(resolve => { release = resolve; });
  let selected = hold();
  const settle = async (response: Response) => {
    if (!release) throw new Error('Missing selected-read resolver');
    await act(async () => { release?.(response); });
  };
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async input => {
    const path = String(input);
    return path === `/api/v1/engagements/${id}` ? selected : new Response(JSON.stringify(path === '/api/session' ? session : health));
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/engagements/${id}/${surface}`]}><App /></MemoryRouter></QueryClientProvider>);
  try {
    await screen.findByText('Loading engagement…');
    const region = screen.getByRole('region', { name: 'Engagement projection' });
    expect(region).toHaveAttribute('aria-busy', 'true');
    await settle(new Response(JSON.stringify(draft)));
    await screen.findByRole('heading', { name: summary.name });
    await waitFor(() => expect(region).toHaveAttribute('aria-busy', 'false'));
    const user = userEvent.setup();
    selected = hold();
    await user.click(screen.getByRole('button', { name: 'Refresh engagement' }));
    expect(region).toHaveAttribute('aria-busy', 'true');
    await settle(new Response(JSON.stringify(draft)));
    await waitFor(() => expect(region).toHaveAttribute('aria-busy', 'false'));
    selected = hold();
    await user.click(screen.getByRole('button', { name: 'Refresh engagement' }));
    expect(region).toHaveAttribute('aria-busy', 'true');
    await settle(new Response(JSON.stringify({ error: { code: 'CONTROL_UNAVAILABLE', correlation_id: id } }), { status: 503 }));
    expect(await screen.findByRole('alert')).toBeVisible();
    await waitFor(() => expect(region).toHaveAttribute('aria-busy', 'false'));
  } finally {
    await settle(new Response(JSON.stringify(draft)));
  }
});

it.each([null, { ...draft, engagement_id: summary.id }, { ...draft, payload: { ...draft.payload, scope: [{}] } },
  { ...draft, payload: { ...draft.payload, objective_text: 1 } }])('rejects malformed selected readback (%j)', async value => {
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(value))));
  await expect(api.engagement(id)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
});
