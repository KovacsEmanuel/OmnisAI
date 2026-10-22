import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, expect, it, vi } from 'vitest';
beforeEach(() => sessionStorage.clear());
import { App } from './App';
import { health } from '../../tests/fixtures';

const id = '11111111-1111-4111-8111-111111111111';
const connection = { connection_id: id, provider: 'openrouter', revision: 1, enabled: true, credential_present: true };
const selected = { connection_id: id, connection_revision: 1, model: 'exact/Model', output_tokens: 128 };
const empty = { schema_version: 2, command_id: null, vault_status: 'UNCONFIGURED', connections: [], selection: null, reachable: 'NOT_VERIFIED' };
function mount() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={['/settings/providers']}><App /></MemoryRouter></QueryClientProvider>);
}
function backend(write: (body: Record<string, unknown>) => Response | Promise<Response>, read: (url: string) => Response) {
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return Response.json({ authenticated: true, csrf_token: 'a'.repeat(64) });
    if (String(input) === '/health/ready') return Response.json(health);
    if (init?.method === 'PUT') return write(JSON.parse(String(init.body)));
    return read(String(input));
  }));
}
it('Settings saves write-only key once through new API and reads current state after remount', async () => {
  const writes: Record<string, unknown>[] = [];
  let current: Record<string, unknown> = empty;
  backend(body => {
    writes.push(body);
    current = { ...empty, vault_status: 'UNLOCKED', connections: [{ ...connection, connection_id: String(body.connection_id) }] };
    return Response.json({ ...current, command_id: body.command_id });
  }, () => Response.json(current));
  const mounted = mount();
  const key = await screen.findByLabelText('API key');
  await waitFor(() => expect(screen.getByRole('button', { name: 'Save API key' })).toBeDisabled());
  fireEvent.change(key, { target: { value: 'synthetic-key-not-a-credential' } });
  fireEvent.submit(key.closest('form')!);
  await screen.findByText('openrouter: configured — credential present');
  expect(writes).toHaveLength(1);
  expect(writes[0]).toMatchObject({ action: 'save_connection', expected_revision: 0, provider: 'openrouter', secret: 'synthetic-key-not-a-credential' });
  expect(key).toHaveValue('');
  expect(screen.queryByText('Connect Codex')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Test/ })).not.toBeInTheDocument();
  mounted.unmount(); mount();
  await screen.findByText('openrouter: configured — credential present');
  expect(screen.getByLabelText('API key')).toHaveValue('');
  expect(writes).toHaveLength(1);
});
it('lost reply retains command ID, clears key and recovers GET exact receipt without replay', async () => {
  const writes: Record<string, unknown>[] = [];
  const reads: string[] = [];
  backend(body => { writes.push(body); throw new TypeError('synthetic lost reply'); }, url => {
    reads.push(url);
    return Response.json(url.includes('/commands/') ? { ...empty, command_id: url.split('/').at(-1) } : empty);
  });
  const mounted = mount();
  const key = await screen.findByLabelText('API key');
  fireEvent.change(key, { target: { value: 'synthetic-key' } });
  await waitFor(() => expect(screen.getByRole('button', { name: 'Save API key' })).toBeEnabled());
  fireEvent.submit(key.closest('form')!);
  await screen.findByText(/Outcome unknown/);
  expect(key).toHaveValue('');
  expect(screen.getByRole('button', { name: 'Save API key' })).toBeDisabled();
  const command = writes[0]!.command_id;
  mounted.unmount(); mount();
  await screen.findByText(/Outcome unknown/);
  fireEvent.click(screen.getByRole('button', { name: 'Recover exact receipt' }));
  await waitFor(() => expect(reads).toContain(`/api/v1/settings/providers/commands/${String(command)}`));
  await screen.findByText(/Exact receipt recovered/);
  expect(writes).toHaveLength(1);
});
it('default and three overrides preserve exact models, allow clear, and show saved source', async () => {
  const writes: Record<string, unknown>[] = [];
  const current = { ...empty, vault_status: 'UNLOCKED', connections: [connection], selection: { selection_id: id, revision: 1, default: selected, brain: selected, investigator: null, validator: null } };
  backend(body => { writes.push(body); return Response.json({ ...current, selection: { ...current.selection, ...body, selection_id: id, revision: 2, action: undefined, command_id: undefined, expected_revision: undefined }, command_id: body.command_id }); }, () => Response.json(current));
  mount();
  await screen.findByLabelText('Default model');
  fireEvent.click(screen.getByLabelText('Brain override'));
  fireEvent.change(screen.getByLabelText('Default model'), { target: { value: 'Exact/Model:Case' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save model selection' }));
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0]).toMatchObject({ action: 'save_selection', expected_revision: 1, default: { ...selected, model: 'Exact/Model:Case' }, brain: null, investigator: null, validator: null });
  expect(screen.getByText(/Investigator source: default/)).toBeInTheDocument();
});
it('CAS rejection is stale, not success; explicit reload is required before another save', async () => {
  backend(() => Response.json({ error: { code: 'REVISION_CONFLICT', correlation_id: id } }, { status: 409 }), () => Response.json(empty));
  mount();
  const key = await screen.findByLabelText('API key');
  fireEvent.change(key, { target: { value: 'synthetic-key' } });
  await waitFor(() => expect(screen.getByRole('button', { name: 'Save API key' })).toBeEnabled());
  fireEvent.submit(key.closest('form')!);
  await screen.findByText(/Settings changed/);
  expect(screen.getByRole('button', { name: 'Save API key' })).toBeDisabled();
  expect(key).toHaveValue('');
  fireEvent.click(screen.getByRole('button', { name: 'Reload current settings' }));
  await screen.findByText('Current settings loaded.');
});
it('locked and revoked remain distinct from provider or inference verification', async () => {
  backend(() => { throw new Error('no write'); }, () => Response.json({ ...empty, vault_status: 'LOCKED', connections: [{ ...connection, enabled: false, credential_present: false }] }));
  mount();
  await screen.findByText('Vault: LOCKED');
  expect(screen.getByText('openrouter: revoked — credential absent')).toBeInTheDocument();
  expect(screen.getByText('Provider reachable: NOT_VERIFIED. Inference: NOT_VERIFIED.')).toBeInTheDocument();
});
