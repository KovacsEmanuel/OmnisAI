import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { api } from '../shared/api/client';
import { health } from '../../tests/fixtures';
import { App } from './App';

it.each(['/engagements', '/engagements/new'])('keeps %s in global Home scope, not selected Engagement', async route => {
  vi.spyOn(api, 'session').mockResolvedValue(null);
  vi.spyOn(api, 'health').mockResolvedValue(health);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[route]}><App /></MemoryRouter></QueryClientProvider>);
  await screen.findByLabelText('Pairing code');
  expect(screen.getByRole('link', { name: 'Home' })).toHaveAttribute('aria-current', 'page');
  expect(screen.queryByRole('link', { name: 'Engagement' })).not.toHaveAttribute('aria-current', 'page');
});

it('navigates Home / Engagement / Settings without duplicating browser auth', async () => {
  vi.spyOn(api, 'session').mockResolvedValue(null);
  vi.spyOn(api, 'health').mockResolvedValue(health);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><App /></MemoryRouter></QueryClientProvider>);
  await screen.findByLabelText('Pairing code');
  const user = userEvent.setup();
  expect(screen.getByRole('main')).not.toHaveFocus();
  await user.tab();
  expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveFocus();
  await user.click(screen.getByRole('link', { name: 'Settings' }));
  expect(screen.getByRole('link', { name: 'Settings' })).toHaveAttribute('aria-current', 'page');
  expect(screen.getAllByRole('navigation', { name: 'Main navigation' })).toHaveLength(1);
  expect(api.session).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('main')).toHaveFocus();
  expect(screen.getByRole('main')).toHaveAttribute('tabindex', '-1');
  await user.tab({ shift: true });
  expect(screen.getByRole('link', { name: 'Settings' })).toHaveFocus();
  await user.tab({ shift: true });
  expect(screen.getByRole('link', { name: 'Engagement' })).toHaveFocus();
  await user.keyboard('{Enter}');
  expect(screen.getByRole('main')).toHaveFocus();
  expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute('href', '#content');
});
