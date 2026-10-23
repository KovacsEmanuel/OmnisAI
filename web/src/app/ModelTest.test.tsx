import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { health, session } from '../../tests/fixtures';
import { ModelTest } from '../features/engagement/ModelTest';
import { BrowserSessionProvider } from '../features/bootstrap/BrowserSession';
import { decodeModelTest } from '../shared/api/modelTest';

const available = {
  schema_version: 2, operation_id: null, state: null, state_revision: null, finish_reason: null,
  selection_revision: 1, metadata_state: 'READY', metadata_command_id: null, reason: null,
  requested_provider: null, requested_model: null, requested_output_tokens: null, observed_model: null,
  provider_status: null, result_state: null, output_state: 'ABSENT', response_text: null,
  usage_state: 'UNKNOWN', input_tokens: null, output_tokens: null, reasoning_tokens: null, cost_observed: null,
  system_message: 'Respond only with OMNIS_MODEL_TEST_OK. Use no tools.',
  user_message: 'This is a synthetic local settings test. Reply with OMNIS_MODEL_TEST_OK.', calls_limit: 1, wall_seconds: 300,
};
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter><BrowserSessionProvider><ModelTest /></BrowserSessionProvider></MemoryRouter></QueryClientProvider>);
}
it('rejects invented observed values and malformed nullable fields', () => {
  expect(decodeModelTest(available).observed_model).toBeNull();
  expect(() => decodeModelTest({ ...available, cost_observed: 0 })).toThrow();
  expect(() => decodeModelTest({ ...available, state_revision: -1 })).toThrow();
});
it('remembers a lost metadata command and reload reads only that receipt', async () => {
  sessionStorage.clear();
  const calls: string[] = [];
  let writes = 0;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input); calls.push(path);
    if (path.startsWith('/api/v1/model-test')) {
      if (init?.method === 'POST') { writes += 1; throw new Error('lost reply'); }
      const command = sessionStorage.getItem('omnis-model-test-metadata');
      if (path === '/api/v1/model-test/capabilities/' + command) return new Response(JSON.stringify({ ...available, metadata_command_id: command }));
      return new Response(JSON.stringify(available));
    }
    return new Response(JSON.stringify(path === '/api/session' ? session : health));
  }));
  const page = mount(); const user = userEvent.setup();
  const button = await screen.findByRole('button', { name: 'Refresh model metadata' });
  await waitFor(() => expect(button).toBeEnabled());
  await user.dblClick(button);
  await waitFor(() => expect(writes).toBe(1));
  const command = sessionStorage.getItem('omnis-model-test-metadata');
  expect(command).toMatch(/^[0-9a-f-]{36}$/);
  page.unmount(); mount();
  await waitFor(() => expect(calls).toContain('/api/v1/model-test/capabilities/' + command));
  expect(writes).toBe(1);
});
it('requires explicit consent, sends the finite intent once, and reload reads by the same ID', async () => {
  sessionStorage.clear();
  let current = available;
  let writes = 0;
  const calls: string[] = [];
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input); calls.push(path);
    if (path.startsWith('/api/v1/model-test')) {
      if (init?.method === 'PUT') {
        writes += 1;
        const value: unknown = JSON.parse(String(init.body));
        expect(value).toEqual({ operation_id: expect.any(String), expected_selection_revision: 1, consent: true });
        if (typeof value !== 'object' || value === null || !('operation_id' in value) || typeof value.operation_id !== 'string') throw new Error('invalid fixture');
        return new Response(JSON.stringify({ ...current, operation_id: value.operation_id, state: 'FINISHED', state_revision: 3,
          finish_reason: 'COMPLETED', result_state: 'COMPLETED', output_state: 'COMPLETE',
          response_text: '<img src=x onerror=alert(1)>', observed_model: 'fixture/observed' }), { status: 202 });
      }
      const remembered = sessionStorage.getItem('omnis-model-test-operation');
      if (remembered) return new Response(JSON.stringify({ ...current, operation_id: remembered, state: 'FINISHED', state_revision: 3,
        finish_reason: 'COMPLETED', result_state: 'COMPLETED', output_state: 'COMPLETE', response_text: '<img src=x onerror=alert(1)>', observed_model: 'fixture/observed' }));
      return new Response(JSON.stringify(current));
    }
    return new Response(JSON.stringify(path === '/api/session' ? session : health));
  }));
  const page = mount(); const user = userEvent.setup();
  const button = await screen.findByRole('button', { name: 'Trimite testul modelului' });
  await waitFor(() => expect(screen.getByRole('checkbox')).toBeEnabled());
  expect(button).toBeDisabled(); expect(writes).toBe(0);
  await user.click(screen.getByRole('checkbox'));
  await user.dblClick(button);
  expect(await screen.findByLabelText('Răspuns model')).toHaveTextContent('<img src=x onerror=alert(1)>');
  expect(screen.queryByRole('img')).not.toBeInTheDocument(); expect(writes).toBe(1);
  page.unmount(); mount();
  await screen.findByLabelText('Răspuns model');
  expect(calls.some(path => path === '/api/v1/model-test/' + sessionStorage.getItem('omnis-model-test-operation'))).toBe(true);
  expect(writes).toBe(1);
  current = available;
});
