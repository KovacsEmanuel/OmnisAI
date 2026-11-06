import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { api } from '../shared/api/client';
import { health, session } from '../../tests/fixtures';
import { App } from './App';

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute('data-theme');
  vi.spyOn(api, 'session').mockResolvedValue(null);
  vi.spyOn(api, 'health').mockResolvedValue(health);
});
afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  document.documentElement.removeAttribute('data-theme');
});

function mount(route = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[route]}><App /></MemoryRouter></QueryClientProvider>);
  return { ...view, client };
}

it('switches globally before pairing, retains input/navigation, and reads only the theme back on remount', async () => {
  const view = mount();
  const input = await screen.findByLabelText('Pairing code');
  fireEvent.change(input, { target: { value: 'synthetic-unsent-code' } });
  const user = userEvent.setup();
  expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
  const toggle = screen.getByRole('button', { name: 'Light theme' });
  await user.click(toggle);
  expect(document.documentElement).toHaveAttribute('data-theme', 'light');
  expect(toggle).toHaveFocus();
  expect(screen.getByLabelText('Pairing code')).toBe(input);
  expect(input).toHaveValue('synthetic-unsent-code');
  await user.click(screen.getByRole('link', { name: 'Settings' }));
  expect(document.documentElement).toHaveAttribute('data-theme', 'light');
  expect(input).toHaveValue('synthetic-unsent-code');
  expect(api.session).toHaveBeenCalledTimes(1);
  expect(Object.keys(localStorage)).toEqual(['omnis-theme']);
  expect(localStorage.getItem('omnis-theme')).toBe('light');
  expect(sessionStorage.length).toBe(0);
  view.unmount(); view.client.clear();
  document.documentElement.removeAttribute('data-theme');
  const reloaded = mount('/settings/models');
  expect(document.documentElement).toHaveAttribute('data-theme', 'light');
  await user.click(screen.getByRole('button', { name: 'Dark theme' }));
  expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
  expect(localStorage.getItem('omnis-theme')).toBe('dark');
  reloaded.unmount(); reloaded.client.clear();
});

it.each(['invalid', 'unavailable'] as const)('falls back to dark with %s storage and still toggles', async mode => {
  if (mode === 'invalid') localStorage.setItem('omnis-theme', 'foreign-value');
  else {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new DOMException('Unavailable', 'SecurityError'); });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('Unavailable', 'QuotaExceededError'); });
  }
  const view = mount();
  await screen.findByLabelText('Pairing code');
  expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
  await userEvent.setup().click(screen.getByRole('button', { name: 'Light theme' }));
  expect(document.documentElement).toHaveAttribute('data-theme', 'light');
  expect(api.session).toHaveBeenCalledTimes(1);
  view.unmount(); view.client.clear();
});

it('keeps the authenticated wizard draft and step mounted without extra requests or writes', async () => {
  const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response('null'));
  vi.stubGlobal('fetch', fetcher);
  vi.mocked(api.session).mockResolvedValue(session);
  const view = mount('/engagements/new');
  const name = await screen.findByLabelText('Engagement name');
  fireEvent.change(name, { target: { value: 'Unsent local draft' } });
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: '2. Application context' }));
  const scope = screen.getByLabelText('Seed URLs (one per line)');
  fireEvent.change(scope, { target: { value: 'https://synthetic.invalid' } });
  const reads = fetcher.mock.calls.length;
  await user.click(screen.getByRole('button', { name: 'Light theme' }));
  expect(screen.getByLabelText('Seed URLs (one per line)')).toBe(scope);
  expect(scope).toHaveValue('https://synthetic.invalid');
  expect(screen.getByRole('button', { name: '2. Application context' })).toHaveAttribute('aria-current', 'step');
  expect(fetcher).toHaveBeenCalledTimes(reads);
  await user.click(screen.getByRole('button', { name: '1. Target & permission' }));
  expect(screen.getByLabelText('Engagement name')).toHaveValue('Unsent local draft');
  expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
  view.unmount(); view.client.clear();
});
