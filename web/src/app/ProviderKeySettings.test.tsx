import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, expect, it, vi } from 'vitest';
import { App } from './App';
import { configured, connection, empty, entry, entryId, selected, settingsBackend } from '../../tests/settings-fixtures';

beforeEach(() => { sessionStorage.clear(); vi.stubGlobal('confirm', vi.fn(() => true)); });
function mount(client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) { return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/settings/providers']}><App /></MemoryRouter></QueryClientProvider>); }
function rotatedSession() {
  const delegate = globalThis.fetch;
  let rotated = false;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session' && rotated) return Response.json({ authenticated: true, csrf_token: 'b'.repeat(64) });
    return delegate(input, init);
  }));
  return () => { rotated = true; };
}
async function open() { await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled()); fireEvent.click(screen.getByRole('button', { name: 'Add models' })); }
async function next() { const button = screen.getByRole('button', { name: 'Continue' }); await waitFor(() => expect(button).not.toHaveAttribute('aria-disabled', 'true')); fireEvent.click(button); }
const refuse = (code = 'REVISION_CONFLICT') => Response.json({ error: { code, correlation_id: entryId } }, { status: 409 });
it('saves a write-only key once, verifies exact receipt, explicitly refreshes, and re-enters the saved list', async () => {
  const { state } = settingsBackend(empty, []); const mounted = mount(); await open();
  const key = screen.getByLabelText('API key'); fireEvent.change(key, { target: { value: 'synthetic-key-not-a-credential' } }); await next();
  await screen.findByLabelText('Search models'); await waitFor(() => expect(state.writes).toHaveLength(2));
  expect(state.writes[0]!.body).toMatchObject({ action: 'save_connection', expected_revision: 0, secret: 'synthetic-key-not-a-credential' });
  expect(state.reads).toContain('/api/v1/settings/providers/commands/' + String(state.writes[0]!.body.command_id));
  expect(key).toHaveValue(''); expect(state.writes[1]!.path).toMatch(/catalog\/refresh$/);
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' })); mounted.unmount(); mount();
  await screen.findByRole('region', { name: 'Configured models' }); expect(screen.queryByLabelText('API key')).not.toBeInTheDocument(); expect(state.writes).toHaveLength(2);
});
it.each(['lost', 'wrong receipt', 'invalid current'])('uncertain key %s remains receive-only across remount until exact receipt/current truth', async fault => {
  const { state, hook } = settingsBackend(empty, []); let valid = false;
  hook.intercept = (path, body, method) => {
    if (path.endsWith('/providers') && method === 'PUT') {
      const receipt = { ...configured, command_id: body.command_id, connections: [{ ...connection, connection_id: String(body.connection_id) }] };
      state.keys = { ...configured, connections: receipt.connections }; state.receipts.set(String(body.command_id), receipt);
      if (fault === 'lost') throw new TypeError('SOURCE lost reply');
      return Response.json(fault === 'wrong receipt' ? { ...receipt, command_id: entryId } : receipt);
    }
    if (!valid && path.includes('/commands/')) return Response.json({ ...configured, command_id: null });
    if (!valid && fault === 'invalid current' && state.writes.length && path.endsWith('/providers')) return Response.json({ ...configured, reachable: 'READY' });
  };
  const mounted = mount(); await open(); const key = screen.getByLabelText('API key'); fireEvent.change(key, { target: { value: 'synthetic-key' } }); await next();
  await screen.findByText(/Outcome unknown/); expect(key).toHaveValue('');
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' })); mounted.unmount(); mount();
  fireEvent.click(await screen.findByRole('button', { name: 'Recover exact receipt' }));
  await screen.findByText('Receipt not confirmed. Do not repeat this command.');
  valid = true; fireEvent.click(screen.getByRole('button', { name: 'Recover exact receipt' }));
  await screen.findByText(/Exact receipt recovered/); expect(state.writes).toHaveLength(1);
});
it('CAS rejection is a hard stale barrier until explicit authoritative reload', async () => {
  const { state, hook } = settingsBackend(empty, []); hook.intercept = (path, _body, method) => path.endsWith('/providers') && method === 'PUT' ? refuse() : undefined;
  mount(); await open(); const input = screen.getByLabelText('API key'); fireEvent.change(input, { target: { value: 'synthetic-key' } }); await next();
  await screen.findByText(/Settings changed/); expect(input).toHaveValue(''); expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Reload current settings' })); await screen.findByText('Current settings loaded.'); expect(state.writes).toHaveLength(1);
});
it('unmount wipes a detached secret without a save', async () => {
  const { state } = settingsBackend(empty, []); const mounted = mount(); await open(); const input = screen.getByLabelText('API key'); fireEvent.change(input, { target: { value: 'synthetic-unsent' } }); mounted.unmount(); expect(input).toHaveValue(''); expect(state.writes).toHaveLength(0);
});
it('authenticated grant rotation wipes the old detached key and unmounts settings while binding is pending', async () => {
  const { state } = settingsBackend(empty, []); const rotate = rotatedSession();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); mount(client); await open();
  const input = screen.getByLabelText('API key'); fireEvent.change(input, { target: { value: 'synthetic-unsent' } });
  const digest = crypto.subtle.digest.bind(crypto.subtle);
  let release: () => void = () => {}; const paused = new Promise<void>(resolve => { release = resolve; });
  vi.spyOn(crypto.subtle, 'digest').mockImplementationOnce(async (...args) => { await paused; return digest(...args); });
  try {
    rotate(); await act(async () => { await client.invalidateQueries({ queryKey: ['session'] }); });
    expect(client.getQueryData(['session'])).toMatchObject({ csrf_token: 'b'.repeat(64) });
    await waitFor(() => expect(input).toHaveValue(''));
    expect(input).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Add models wizard' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Add models' })).not.toBeInTheDocument();
  } finally { release(); }
  await open(); expect(screen.getByLabelText('API key')).toHaveValue(''); expect(state.writes).toHaveLength(0);
  const keys = JSON.stringify(client.getQueryCache().getAll().map(query => query.queryKey));
  expect(keys.includes('a'.repeat(64)) || keys.includes('b'.repeat(64))).toBe(false);
});
it('authenticated grant rotation never adopts the previous grants UNKNOWN pending command', async () => {
  const { state, hook } = settingsBackend(empty, []);
  hook.intercept = (path, _body, method) => { if (path.endsWith('/providers') && method === 'PUT') throw new TypeError('SOURCE lost reply'); return undefined; };
  const rotate = rotatedSession(); const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); mount(client); await open();
  fireEvent.change(screen.getByLabelText('API key'), { target: { value: 'synthetic-key' } }); await next();
  await screen.findByText(/Outcome unknown/); fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  await act(async () => { await client.invalidateQueries({ queryKey: ['session'] }); });
  expect(screen.getByRole('button', { name: 'Recover exact receipt' })).toBeEnabled();
  rotate(); await act(async () => { await client.invalidateQueries({ queryKey: ['session'] }); });
  expect(client.getQueryData(['session'])).toMatchObject({ csrf_token: 'b'.repeat(64) });
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Recover exact receipt' })).not.toBeInTheDocument());
  await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled());
  expect(screen.queryByText(/Outcome unknown/)).not.toBeInTheDocument(); expect(state.writes).toHaveLength(1);
  expect(state.reads.some(path => path.includes('/commands/'))).toBe(false);
});
it('locked and disabled states never claim an absent key is usable, and local Disable remains available', async () => {
  const { state } = settingsBackend({ ...configured, vault_status: 'LOCKED', connections: [{ ...connection, credential_present: false }] }); mount();
  await screen.findByText(/Vault locked/); expect(screen.getByText('Key unavailable — vault locked')).toBeVisible();
  fireEvent.click(screen.getByText('Connection options')); expect(screen.getByRole('button', { name: 'Replace key' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Disable connection' })); await screen.findByText('Connection disabled');
  expect(state.writes).toHaveLength(1); expect(state.writes[0]!.body.action).toBe('revoke_connection'); expect(screen.getByRole('button', { name: 'Test Exact/Model via OpenRouter' })).toBeDisabled();
});
it.each([false, true])('assignment save preserves focused action or moved focus=%s and independent role caps', async moved => {
  const keys = { ...configured, selection: { selection_id: entryId, revision: 1, default: selected, brain: { ...selected, output_tokens: 37 }, investigator: null, validator: { ...selected, output_tokens: 89 } } };
  const { state, hook } = settingsBackend(keys, [entry, { ...entry, entry_id: '44444444-4444-4444-8444-444444444444', model: 'Other/Model' }], [{ model: entry.model, name: 'Exact model', max_output_tokens: 4096, supports_max_tokens: true }, { model: 'Other/Model', name: 'Other model', max_output_tokens: 4096, supports_max_tokens: true }]);
  let resolve: () => void = () => { throw new Error('No pending write'); }; const paused = new Promise<void>(done => { resolve = done; });
  hook.intercept = async (path, _body, method) => { if (path.endsWith('/providers') && method === 'PUT') await paused; return undefined; };
  mount(); const save = await screen.findByRole('button', { name: 'Save assignments' }); await waitFor(() => expect(save).toBeEnabled());
  fireEvent.change(screen.getByLabelText('Default model'), { target: { value: '44444444-4444-4444-8444-444444444444' } });
  save.focus(); fireEvent.click(save); await waitFor(() => expect(state.writes).toHaveLength(1)); expect(save).not.toBeDisabled(); expect(save).toHaveAttribute('aria-disabled', 'true');
  fireEvent.click(save); fireEvent.submit(save.closest('form')!); expect(state.writes).toHaveLength(1);
  const elsewhere = screen.getByRole('link', { name: 'Models' }); if (moved) elsewhere.focus(); resolve();
  await screen.findByText(/Assignments saved/); expect(moved ? elsewhere : save).toHaveFocus(); expect(screen.getByRole('button', { name: 'Save assignments' })).toBe(save);
  expect(state.writes[0]!.body).toMatchObject({ action: 'save_selection', default: { ...selected, model: 'Other/Model' }, brain: { ...selected, output_tokens: 37 }, validator: { ...selected, output_tokens: 89 }, investigator: null });
});
it('disabling an open connection invalidates its wizard and keeps saved identities/history', async () => {
  const { state } = settingsBackend(); mount(); await open(); fireEvent.click(screen.getByText('Connection options')); fireEvent.click(screen.getByRole('button', { name: 'Disable connection' }));
  await screen.findByText('Connection disabled'); expect(screen.queryByRole('region', { name: 'Add models wizard' })).not.toBeInTheDocument(); expect(screen.getByRole('region', { name: 'Configured models' })).toHaveTextContent(entry.model); expect(state.entries).toHaveLength(1);
  const mounted = screen.getByRole('region', { name: 'Configured models' }); expect(within(mounted).getByRole('button', { name: '+ Add model' })).toBeDisabled(); expect(state.writes).toHaveLength(1);
});
it('loads every one of 64 saved entries across four revision-bound pages and dedupes per connection', async () => {
  const entries = Array.from({ length: 64 }, (_, i) => ({ ...entry, entry_id: `00000000-0000-4000-8000-${String(i).padStart(12, '0')}`, model: `Exact/${String(i).padStart(3, '0')}` }));
  const { state } = settingsBackend(configured, entries, []); mount(); const list = await screen.findByRole('region', { name: 'Configured models' });
  expect(within(list).getAllByRole('button', { name: /^Test / })).toHaveLength(64); expect(state.reads.filter(path => path.includes('/models/pages/'))).toHaveLength(3); expect(state.writes).toHaveLength(0);
});
it('keeps full provider-qualified assignment identities readable outside native select clipping', async () => {
  const model = 'Exact/' + 'Long-ID-'.repeat(20);
  settingsBackend({ ...configured, selection: { selection_id: entryId, revision: 1, default: { ...selected, model }, brain: null, investigator: null, validator: null } }, [entry, { ...entry, entry_id: '44444444-4444-4444-8444-444444444444', model }], [{ model, max_output_tokens: 4096, supports_max_tokens: true }, { model: entry.model, max_output_tokens: 4096, supports_max_tokens: true }]);
  mount(); await screen.findByLabelText('Default model');
  expect(screen.getByText(`${model} · OpenRouter`, { selector: 'small' })).toBeVisible();
});
it('one usable model collapses valid same-entry overrides without erasing independent caps', async () => {
  const keys = { ...configured, selection: { selection_id: entryId, revision: 1, default: selected, brain: { ...selected, output_tokens: 37 }, investigator: null, validator: { ...selected, output_tokens: 89 } } };
  const { state } = settingsBackend(keys); mount();
  await screen.findByText('All roles use Exact/Model · OpenRouter.');
  expect(screen.queryByLabelText('Default model')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Brain', { exact: true })).not.toBeInTheDocument();
  expect(screen.getByLabelText('Brain output tokens')).toHaveValue(37);
  fireEvent.click(screen.getByRole('button', { name: 'Save assignments' }));
  await screen.findByText(/Assignments saved/);
  expect(state.writes[0]!.body).toMatchObject({ default: selected, brain: { ...selected, output_tokens: 37 }, investigator: null, validator: { ...selected, output_tokens: 89 } });
});
it('one usable entry cannot hide an explicit same-entry cap that exceeds capability', async () => {
  settingsBackend({ ...configured, selection: { selection_id: entryId, revision: 1, default: selected, brain: { ...selected, output_tokens: 8192 }, investigator: null, validator: null } });
  mount(); await screen.findByLabelText('Brain', { exact: true });
  expect(screen.queryByText(/All roles use/)).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Save assignments' })).toBeDisabled();
});
it('a stale historical explicit choice remains visible and cannot collapse into All roles use', async () => {
  const { state } = settingsBackend({ ...configured, selection: { selection_id: entryId, revision: 1, default: selected, brain: { ...selected, connection_revision: 77, output_tokens: 31 }, investigator: null, validator: null } });
  mount(); const brain = await screen.findByLabelText('Brain'); expect(brain).toHaveDisplayValue(/revision 77.*Unavailable/); expect(screen.queryByText(/All roles use/)).not.toBeInTheDocument(); expect(screen.getByRole('button', { name: 'Save assignments' })).toBeDisabled(); expect(state.writes).toHaveLength(0);
});
it('a pending key save keeps native Continue focus and does not steal an operator move on completion', async () => {
  const { state, hook } = settingsBackend(empty, []);
  let release: () => void = () => {}; const paused = new Promise<void>(resolve => { release = resolve; });
  hook.intercept = async (path, _body, method) => { if (path.endsWith('/providers') && method === 'PUT') await paused; return undefined; };
  mount(); await open(); fireEvent.change(screen.getByLabelText('API key'), { target: { value: 'synthetic-pending-key' } });
  const next = screen.getByRole('button', { name: 'Continue' }); next.focus(); fireEvent.click(next);
  await waitFor(() => expect(state.writes).toHaveLength(1));
  expect(next).not.toBeDisabled(); expect(next).toHaveAttribute('aria-disabled', 'true'); expect(next).toHaveFocus();
  const elsewhere = screen.getByRole('link', { name: 'Models' }); elsewhere.focus(); release();
  await screen.findByLabelText('Search models'); expect(elsewhere).toHaveFocus();
});
it('cancel before an in-flight key save settles cannot launch a catalog for another wizard', async () => {
  const { state, hook } = settingsBackend(empty, []); let resolve: () => void = () => {}; const paused = new Promise<void>(done => { resolve = done; });
  hook.intercept = async (path, _body, method) => { if (path.endsWith('/providers') && method === 'PUT') await paused; return undefined; };
  mount(); await open(); fireEvent.change(screen.getByLabelText('API key'), { target: { value: 'synthetic-key' } }); await next(); await waitFor(() => expect(state.writes).toHaveLength(1));
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' })); resolve(); await screen.findByText(/Saved locally/); expect(state.writes).toHaveLength(1); expect(state.keys.connections).toHaveLength(1);
});
