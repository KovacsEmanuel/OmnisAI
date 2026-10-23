import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { health, session } from '../../tests/fixtures';
import { ModelTest } from '../features/engagement/ModelTest';
import { BrowserSessionProvider } from '../features/bootstrap/BrowserSession';
import { decodeModelTest } from '../shared/api/modelTest';
import { api } from '../shared/api/client';
import { ProviderSettings } from '../features/engagement/ProviderSettings';

const available = {
  schema_version: 2, operation_id: null, state: null, state_revision: null, finish_reason: null,
  selection_revision: 1, metadata_state: 'READY', metadata_command_id: null, reason: null,
  requested_provider: null, requested_model: null, requested_output_tokens: null, observed_model: null,
  provider_status: null, result_state: null, output_state: 'ABSENT', response_text: null,
  usage_state: 'UNKNOWN', input_tokens: null, output_tokens: null, reasoning_tokens: null, cost_observed: null,
  system_message: 'Respond only with OMNIS_MODEL_TEST_OK. Use no tools.',
  user_message: 'This is a synthetic local settings test. Reply with OMNIS_MODEL_TEST_OK.', calls_limit: 1, wall_seconds: 300,
};
function mount(settings = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter><BrowserSessionProvider>{settings && <ProviderSettings />}<ModelTest /></BrowserSessionProvider></MemoryRouter></QueryClientProvider>);
}
it('Settings save refreshes current selection without rewriting the active requested snapshot', async () => {
  sessionStorage.clear();
  const id = '11111111-1111-4111-8111-111111111111';
  const command = '22222222-2222-4222-8222-222222222222';
  sessionStorage.setItem('omnis-model-test-operation', id);
  sessionStorage.setItem('omnis-model-test-metadata', command);
  const selected = { connection_id: id, connection_revision: 1, model: 'fixture/new', output_tokens: 64 };
  let revision = 1; let writes = 0;
  const settings = () => ({ schema_version: 2, command_id: null, vault_status: 'UNLOCKED', reachable: 'NOT_VERIFIED',
    connections: [{ connection_id: id, provider: 'openrouter', revision: 1, enabled: true, credential_present: true }],
    selection: { selection_id: id, revision, default: selected, brain: null, investigator: null, validator: null } });
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input);
    if (path === '/api/v1/settings/providers') {
      if (init?.method === 'PUT') {
        writes += 1; revision = 2;
        const body: unknown = JSON.parse(String(init.body));
        if (typeof body !== 'object' || body === null || !('command_id' in body)) throw new Error('invalid fixture');
        return Response.json({ ...settings(), command_id: body.command_id });
      }
      return Response.json(settings());
    }
    if (path === '/api/v1/model-test/capabilities/' + command) return Response.json({ ...available, metadata_command_id: command });
    if (path === '/api/v1/model-test/' + id) return Response.json({ ...available, selection_revision: revision,
      metadata_state: revision === 1 ? 'READY' : 'NOT_REQUESTED', operation_id: id, state: 'RUNNING', state_revision: 2,
      requested_provider: 'openrouter', requested_model: 'fixture/original', requested_output_tokens: 64 });
    return Response.json(path === '/api/session' ? session : health);
  }));
  mount(true);
  await screen.findByText(/Saved selection revision: 1/);
  const save = await screen.findByRole('button', { name: 'Save model selection' });
  await waitFor(() => { expect(save).toBeEnabled(); expect(save).not.toHaveAttribute('aria-disabled', 'true'); });
  fireEvent.click(save);
  await waitFor(() => expect(writes).toBe(1));
  await screen.findByText(/Saved selection revision: 2/);
  expect(screen.getByText(/Cerut:/)).toHaveTextContent('fixture/original');
  expect(screen.getByText(/Operation:/)).toHaveTextContent(id);
  expect(sessionStorage.getItem('omnis-model-test-operation')).toBe(id);
});
it.each(['read', 'cancel'] as const)('rejects a valid response bound to another operation on %s', async action => {
  const requested = '11111111-1111-4111-8111-111111111111';
  const other = '22222222-2222-4222-8222-222222222222';
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ ...available,
    operation_id: other, state: 'FINISHED', state_revision: 3, result_state: 'UNKNOWN' }))));
  await expect(action === 'read' ? api.modelTest(undefined, requested) : api.cancelModelTest(requested, requested, 2, 'csrf')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
});
it.each(['REVISION_CONFLICT', 'API_UNAVAILABLE'])('reconciles only definitive nonadmission after %s without resending', async code => {
  sessionStorage.clear();
  let writes = 0;
  const calls: string[] = [];
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input); calls.push(path);
    if (path.startsWith('/api/v1/model-test')) {
      if (init?.method === 'PUT') {
        writes += 1;
        if (code === 'API_UNAVAILABLE') throw new Error('lost response');
        return new Response(JSON.stringify({ error: { code, correlation_id: '11111111-1111-4111-8111-111111111111' } }), { status: 409 });
      }
      if (path !== '/api/v1/model-test') return new Response(JSON.stringify({ error: { code: 'NOT_FOUND', correlation_id: '11111111-1111-4111-8111-111111111111' } }), { status: 404 });
      return new Response(JSON.stringify({ ...available, selection_revision: writes ? 2 : 1 }));
    }
    return new Response(JSON.stringify(path === '/api/session' ? session : health));
  }));
  const page = mount(); const user = userEvent.setup();
  await waitFor(() => expect(screen.getByRole('checkbox')).toBeEnabled());
  await user.click(screen.getByRole('checkbox'));
  await user.click(screen.getByRole('button', { name: 'Trimite testul modelului' }));
  await waitFor(() => expect(writes).toBe(1));
  const identity = sessionStorage.getItem('omnis-model-test-operation');
  expect(identity).not.toBeNull();
  await waitFor(() => expect(screen.getByRole('button', { name: 'Citește starea testului' })).toHaveAttribute('aria-disabled', 'false'));
  page.unmount(); mount();
  await waitFor(() => expect(calls).toContain('/api/v1/model-test/' + identity));
  await user.click(screen.getByRole('button', { name: 'Citește starea testului' }));
  if (code === 'REVISION_CONFLICT') {
    await waitFor(() => expect(screen.getByRole('button', { name: 'Refresh model metadata' })).toBeEnabled());
    expect(sessionStorage.getItem('omnis-model-test-operation')).toBeNull();
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(screen.getByRole('button', { name: 'Trimite testul modelului' })).toBeDisabled();
  } else {
    expect(sessionStorage.getItem('omnis-model-test-operation')).toBe(identity);
    expect(screen.getByRole('button', { name: 'Refresh model metadata' })).toBeDisabled();
  }
  expect(writes).toBe(1);
});
it('rejects invented observed values and malformed nullable fields', () => {
  expect(decodeModelTest(available).observed_model).toBeNull();
  expect(() => decodeModelTest({ ...available, cost_observed: 0 })).toThrow();
  expect(() => decodeModelTest({ ...available, state_revision: -1 })).toThrow();
  for (const field of ['input_tokens', 'output_tokens', 'reasoning_tokens']) {
    expect(decodeModelTest({ ...available, [field]: Number.MAX_SAFE_INTEGER })).toBeDefined();
    for (const invalid of [-1, Number.MAX_SAFE_INTEGER + 1, true, '9', 1.5]) expect(() => decodeModelTest({ ...available, [field]: invalid })).toThrow();
  }
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
