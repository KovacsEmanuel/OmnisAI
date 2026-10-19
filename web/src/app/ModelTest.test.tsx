import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { health, session } from '../../tests/fixtures';
import { draft, id } from '../../tests/projection-fixtures';
import type { ModelTestView } from '../shared/api/modelTest';
import { App } from './App';

const available: ModelTestView = {
  operation_id: null, status: 'AVAILABLE', reason: null,
  system_message: 'Respond briefly to this synthetic model test. Use no tools.',
  user_message: 'Map supplied structured synthetic records.',
  requested_provider: 'openai-codex', requested_model: 'gpt-6.1-sol', requested_effort: 'xhigh',
  observed_model: null, observed_effort: null, response_text: null,
  input_tokens: null, output_tokens: null, reasoning_tokens: null, duration_ms: null,
  calls_limit: 1, wall_seconds: 300,
};
function mount(path = `/engagements/${id}/overview`) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></QueryClientProvider>);
}

it('can test from New before saving any authorization, scope or ROE', async () => {
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async input => {
    const path = String(input);
    if (path === '/api/v1/model-test') return new Response(JSON.stringify(available));
    if (path.startsWith('/api/v1/engagements/')) throw new Error('No saved engagement exists');
    return new Response(JSON.stringify(path === '/api/session' ? session : health));
  });
  vi.stubGlobal('fetch', fetcher);
  mount('/engagements/new');
  const button = await screen.findByRole('button', { name: 'Trimite testul modelului' });
  await waitFor(() => expect(button).toBeEnabled());
  expect(screen.getByLabelText('Engagement name')).toHaveValue('');
  expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
});

it('sends only on explicit action, renders escaped retained response and reload only reads', async () => {
  let current = available;
  let writes = 0;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input);
    if (path.endsWith('/model-test')) {
      if (init?.method === 'PUT') {
        writes += 1;
        expect(init.headers).toMatchObject({ 'X-CSRF-Token': session.csrf_token });
        const value: unknown = JSON.parse(String(init.body));
        if (typeof value !== 'object' || value === null || !('operation_id' in value) || typeof value.operation_id !== 'string') throw new Error('Invalid test fixture request');
        current = { ...available, operation_id: value.operation_id, status: 'COMPLETE',
          observed_model: 'gpt-6.1-sol', observed_effort: null,
          response_text: '<img src=x onerror=alert(1)> controlled reply', output_tokens: 3, duration_ms: 4100 };
      }
      return new Response(JSON.stringify(current));
    }
    return new Response(JSON.stringify(path === '/api/session' ? session : path === '/health/ready' ? health : draft));
  }));
  const page = mount();
  const user = userEvent.setup();
  const button = await screen.findByRole('button', { name: 'Trimite testul modelului' });
  await waitFor(() => expect(button).toBeEnabled());
  expect(writes).toBe(0);
  expect(screen.getByText(available.system_message)).toBeVisible();
  await user.dblClick(button);
  expect(await screen.findByLabelText('Răspuns model')).toHaveTextContent('<img src=x onerror=alert(1)> controlled reply');
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
  expect(writes).toBe(1);
  expect(button).toBeDisabled();
  page.unmount();
  mount();
  expect(await screen.findByLabelText('Răspuns model')).toBeVisible();
  expect(writes).toBe(1);
});

it('a lost reply is read back as UNKNOWN without resend or an enabled new operation', async () => {
  let writes = 0;
  let current = available;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input).endsWith('/model-test')) {
      if (init?.method === 'PUT') {
        writes += 1;
        current = { ...available, operation_id: '11111111-1111-4111-8111-111111111111', status: 'UNKNOWN' };
        throw new Error('Lost control response');
      }
      return new Response(JSON.stringify(current));
    }
    return new Response(JSON.stringify(String(input) === '/api/session' ? session : String(input) === '/health/ready' ? health : draft));
  }));
  const page = mount();
  const user = userEvent.setup();
  const button = await screen.findByRole('button', { name: 'Trimite testul modelului' });
  await waitFor(() => expect(button).toBeEnabled());
  await user.click(button);
  await waitFor(() => expect(screen.getByText(/UNKNOWN —/)).toBeVisible());
  await user.click(screen.getByRole('button', { name: 'Citește starea testului' }));
  expect(button).toBeDisabled();
  page.unmount();
  mount();
  await screen.findByText('UNKNOWN — nu se retrimite.');
  expect(screen.getByRole('button', { name: 'Trimite testul modelului' })).toBeDisabled();
  expect(writes).toBe(1);
});
