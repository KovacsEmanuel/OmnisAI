import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, expect, it, vi } from 'vitest';
beforeEach(() => sessionStorage.clear());
import { App } from './App';
import { health } from '../../tests/fixtures';
import revoked from '../../tests/provider-key-revoked.json';

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
it('clears an unsubmitted secret from the detached input on unmount', async () => {
  backend(() => { throw new Error('No mutation admitted'); }, () => Response.json(empty));
  const mounted = mount();
  const input = await screen.findByLabelText('API key');
  await waitFor(() => expect(input).toBeEnabled());
  fireEvent.change(input, { target: { value: 'synthetic-unsent-key' } });
  mounted.unmount();
  expect(input).toHaveValue('');
});
it('does not describe an inaccessible configured key as absent when the vault is locked', async () => {
  backend(() => { throw new Error('No write'); }, () => Response.json({ ...empty, vault_status: 'LOCKED', connections: [{ ...connection, credential_present: false }] }));
  mount();
  await screen.findByText('openrouter: configured — credential unavailable (vault LOCKED)');
  expect(screen.getByRole('button', { name: 'Rotate API key' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Revoke locally' })).toBeEnabled();
});
it('locked and revoked remain distinct from provider or inference verification', async () => {
  backend(() => { throw new Error('no write'); }, () => Response.json({ ...empty, vault_status: 'LOCKED', connections: [{ ...connection, enabled: false, credential_present: false }] }));
  mount();
  await screen.findByText('Vault: LOCKED');
  expect(screen.getByText('openrouter: revoked — credential absent')).toBeInTheDocument();
  expect(screen.getByText('Provider reachable: NOT_VERIFIED. Inference: NOT_VERIFIED.')).toBeInTheDocument();
});
it.each([false, true])('SOURCE reviewer2: revision readback preserves Save focus without stealing it after operator moved=%s', async moved => {
  const selection = { selection_id: id, revision: 1, default: selected, brain: selected, investigator: null, validator: null };
  let current = { ...empty, vault_status: 'UNLOCKED', connections: [connection], selection };
  let resolveWrite: (response: Response) => void = () => { throw new Error('No pending write'); };
  const writes: Record<string, unknown>[] = [];
  backend(body => {
    writes.push(body);
    current = { ...current, selection: { ...selection, revision: 2 } };
    return new Promise<Response>(resolve => { resolveWrite = resolve; });
  }, () => Response.json(current));
  mount();
  const save = await screen.findByRole('button', { name: 'Save model selection' });
  await waitFor(() => expect(save).toBeEnabled());
  save.focus(); expect(save).toHaveFocus();
  fireEvent.click(save);
  await waitFor(() => expect(writes).toHaveLength(1));
  const elsewhere = screen.getByRole('link', { name: 'Providers' });
  if (moved) elsewhere.focus();
  resolveWrite(Response.json({ ...current, command_id: writes[0]!.command_id }));
  await screen.findByText(/Saved locally/);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Save model selection' })).toBeEnabled());
  expect(screen.getByRole('button', { name: 'Save model selection' })).toBe(save);
  expect(moved ? elsewhere : screen.getByRole('button', { name: 'Save model selection' })).toHaveFocus();
  // A later authoritative reload must still discard unsaved fields and override toggles.
  fireEvent.change(screen.getByLabelText('Default model'), { target: { value: 'Unsubmitted/Draft' } });
  fireEvent.click(screen.getByLabelText('Brain override'));
  current = { ...current, selection: { ...selection, revision: 3, default: { ...selected, model: 'Exact/Current' } } };
  elsewhere.focus();
  fireEvent.click(screen.getByRole('button', { name: 'Reload current settings' }));
  await screen.findByText('Current settings loaded.');
  expect(screen.getByLabelText('Default model')).toHaveValue('Exact/Current');
  expect(screen.getByLabelText('Brain override')).toBeChecked();
  expect(elsewhere).toHaveFocus();
  expect(writes).toHaveLength(1);
});
it('Revoke accepts the real owner receipt and current truth, including reload and remount, with exactly one PUT', async () => {
  const writes: Record<string, unknown>[] = [];
  let current = { ...revoked, connections: [{ ...revoked.connections[0], revision: 1, enabled: true }] };
  backend(body => { writes.push(body); current = revoked; return Response.json({ ...revoked, command_id: body.command_id }); }, () => Response.json(current));
  const mounted = mount();
  const revoke = await screen.findByRole('button', { name: 'Revoke locally' });
  await waitFor(() => expect(revoke).toBeEnabled());
  fireEvent.click(revoke);
  await screen.findByText(/Saved locally/);
  expect(screen.getByText('openrouter: revoked — credential present')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Revoke locally' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Save model selection' })).toBeDisabled();
  expect(sessionStorage.getItem('omnis-provider-settings-command')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Reload current settings' }));
  await screen.findByText('Current settings loaded.');
  mounted.unmount(); mount();
  await screen.findByText('openrouter: revoked — credential present');
  expect(screen.getByText('Provider reachable: NOT_VERIFIED. Inference: NOT_VERIFIED.')).toBeInTheDocument();
  expect(writes).toHaveLength(1);
  expect(writes[0]).toMatchObject({ action: 'revoke_connection', connection_id: revoked.connections[0]!.connection_id, expected_revision: 1 });
});
it.each(['lost reply', 'wrong receipt', 'invalid current'])('Revoke %s stays receive-only until exact receipt and valid current truth recover', async fault => {
  const writes: Record<string, unknown>[] = [];
  const reads: string[] = [];
  let recoveryValid = false;
  const before = { ...revoked, connections: [{ ...revoked.connections[0], revision: 1, enabled: true }] };
  backend(body => {
    writes.push(body);
    if (fault === 'lost reply') throw new TypeError('synthetic lost reply');
    return Response.json({ ...revoked, command_id: fault === 'wrong receipt' ? id : body.command_id });
  }, url => {
    reads.push(url);
    if (url.includes('/commands/')) return Response.json({ ...revoked, command_id: recoveryValid ? url.split('/').at(-1) : null });
    return Response.json(!writes.length ? before : recoveryValid ? revoked : { ...revoked, reachable: 'READY' });
  });
  const mounted = mount();
  const revoke = await screen.findByRole('button', { name: 'Revoke locally' });
  await waitFor(() => expect(revoke).toBeEnabled());
  fireEvent.click(revoke);
  await screen.findByText(/Outcome unknown/);
  expect(screen.queryByText(/Saved locally/)).not.toBeInTheDocument();
  expect(revoke).toBeDisabled();
  mounted.unmount(); mount();
  await screen.findByText(/Outcome unknown/);
  fireEvent.click(screen.getByRole('button', { name: 'Recover exact receipt' }));
  await screen.findByText('Receipt not confirmed. Do not repeat this command.');
  expect(sessionStorage.getItem('omnis-provider-settings-command')).toBe(writes[0]!.command_id);
  recoveryValid = true;
  fireEvent.click(screen.getByRole('button', { name: 'Recover exact receipt' }));
  await screen.findByText(/Exact receipt recovered/);
  expect(screen.getByText('openrouter: revoked — credential present')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Save model selection' })).toBeDisabled();
  expect(sessionStorage.getItem('omnis-provider-settings-command')).toBeNull();
  expect(reads).toContain(`/api/v1/settings/providers/commands/${String(writes[0]!.command_id)}`);
  fireEvent.click(screen.getByRole('button', { name: 'Reload current settings' }));
  await screen.findByText('Current settings loaded.');
  expect(writes).toHaveLength(1);
});
