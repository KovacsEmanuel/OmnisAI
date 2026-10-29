import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, expect, it, vi } from 'vitest';
import { App } from './App';
import { health, instance, session } from '../../tests/fixtures';
import { configured, connection as savedConnection, settingsBackend } from '../../tests/settings-fixtures';

const connectionId = '11111111-1111-4111-8111-111111111111';
const entryId = '22222222-2222-4222-8222-222222222222';
const connection = { connection_id: connectionId, provider: 'openrouter', revision: 1, enabled: true, credential_present: true };
const entry = { entry_id: entryId, revision: 1, connection_id: connectionId, connection_revision: 1, model: 'Exact/Model', output_tokens: 512 };
const settings = { schema_version: 2, command_id: null, vault_status: 'UNLOCKED', reachable: 'NOT_VERIFIED', connections: [connection], selection: null };
const registry = { schema_version: 1, command_id: null, registry_revision: 1, total: 1, after: null, next_after: null, entries: [entry] };
const metadata = { model: entry.model, name: 'Exact model', max_output_tokens: 4096, supports_max_tokens: true, reason: null };
const catalogId = '33333333-3333-4333-8333-333333333333';
const catalog = { schema_version: 1, connection_id: connectionId, connection_revision: 1, provider: 'openrouter', catalog_command_id: catalogId, state: 'READY', reason: null, query: '', offset: 0, next_offset: null, total: 1, entries: [metadata] };
let writes: { path: string; body: Record<string, unknown> }[];
function backend(options: { empty?: boolean; lost?: boolean } = {}) {
  let keys = options.empty ? { ...settings, vault_status: 'UNCONFIGURED', connections: [] } : settings;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input);
    if (path === '/api/session') return Response.json(session);
    if (path === '/health/ready') return Response.json(health);
    if (path === '/api/instance') return Response.json({ ...instance, generation: 1, admission_open: true });
    if (path.includes('/entries/latest/')) return Response.json({ error: { code: 'NOT_FOUND', correlation_id: entryId } }, { status: 404 });
    const body: Record<string, unknown> = init?.body ? JSON.parse(String(init.body)) : {};
    if (init?.method === 'PUT' || path.endsWith('/refresh')) {
      writes.push({ path, body });
      if (options.lost) throw new TypeError('synthetic lost response');
      if (path.endsWith('/providers')) { keys = { ...settings, connections: [{ ...connection, connection_id: String(body.connection_id) }] }; return Response.json({ ...keys, command_id: body.command_id }); }
      if (path.endsWith('/refresh')) return Response.json({ ...catalog, connection_id: body.connection_id, catalog_command_id: body.command_id });
    }
    if (path.includes('/providers/commands/')) return Response.json({ ...keys, command_id: path.split('/').at(-1) });
    if (path.endsWith('/providers')) return Response.json(keys);
    if (path.endsWith('/models')) return Response.json(options.empty ? { ...registry, registry_revision: 0, total: 0, entries: [] } : registry);
    if (path.endsWith('/search')) return Response.json({ ...catalog, query: body.query ?? '', offset: body.offset ?? 0 });
    throw new Error('Unexpected SOURCE request: ' + path);
  }));
}
function mount() { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={['/settings/providers']}><App /></MemoryRouter></QueryClientProvider>); }
beforeEach(() => { sessionStorage.clear(); writes = []; });
it('offers Remove only in expanded details and names exact confirmation without sending on cancel', async () => {
  backend(); vi.spyOn(window, 'confirm').mockReturnValue(false); mount();
  await screen.findByRole('region', { name: 'Configured models' });
  expect(screen.queryByRole('button', { name: 'Remove Exact/Model via OpenRouter' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Details for Exact/Model via OpenRouter' }));
  fireEvent.click(screen.getByRole('button', { name: 'Remove Exact/Model via OpenRouter' }));
  expect(window.confirm).toHaveBeenCalledWith('Remove Exact/Model via OpenRouter? Saved history remains.');
  expect(writes).toEqual([]);
});
it('opens on persisted models, not a wizard, and does not invent a persisted default', async () => {
  backend(); mount();
  expect(await screen.findByRole('region', { name: 'Configured models' })).toHaveTextContent('Exact/Model');
  expect(screen.queryByRole('region', { name: 'Add models wizard' })).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Models' })).toHaveAttribute('aria-current', 'page');
  expect(screen.queryByText(/All roles use/)).not.toBeInTheDocument();
  expect(screen.getByText('All roles will use Exact/Model · OpenRouter after saving assignments.')).toBeVisible();
  expect(writes).toEqual([]);
  expect(screen.queryByRole('button', { name: '+ Add model' })).not.toBeInTheDocument();
  expect(screen.queryByText('Test details')).not.toBeInTheDocument();
});
it.each([false, true])('persists Remove with exact receipt and no resend on lost reply=%s', async lost => {
  const { state, hook } = settingsBackend();
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  hook.intercept = (_path, body, method): Response | undefined => {
    if (!lost || method !== 'PUT' || body.action !== 'remove_model') return undefined;
    state.entries = []; state.revision += 1;
    state.receipts.set(String(body.command_id), { schema_version: 1, command_id: body.command_id, registry_revision: state.revision, total: 0, after: null, next_after: null, entries: [] });
    throw new TypeError('SOURCE committed reply lost');
  };
  const mounted = mount(); await screen.findByRole('region', { name: 'Configured models' });
  fireEvent.click(screen.getByRole('button', { name: 'Details for Exact/Model via OpenRouter' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Remove Exact/Model via OpenRouter' })).toHaveAttribute('aria-disabled', 'false'));
  fireEvent.click(screen.getByRole('button', { name: 'Remove Exact/Model via OpenRouter' }));
  if (lost) { fireEvent.click(await screen.findByRole('button', { name: 'Recover exact receipt' })); }
  await screen.findByText('No models configured.');
  expect(state.writes).toHaveLength(1);
  expect(state.writes[0]!.body).toMatchObject({ action: 'remove_model', entry_id: entryId, expected_registry_revision: 1, expected_revision: 1 });
  expect(state.reads).toContain('/api/v1/settings/models/commands/' + String(state.writes[0]!.body.command_id));
  mounted.unmount(); mount(); await screen.findByText('No models configured.');
  expect(state.writes).toHaveLength(1);
});
it.each([[false, false], [false, true], [true, false], [true, true]])('keeps or restores focus after Remove lost=%s moved=%s', async (lost, moved) => {
  const { state, hook } = settingsBackend();
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  let release = () => {}, held = false;
  const gate = new Promise<void>(resolve => { release = resolve; });
  hook.intercept = async (path, body, method) => {
    if (lost && method === 'PUT' && body.action === 'remove_model') {
      state.entries = []; state.revision += 1;
      state.receipts.set(String(body.command_id), { schema_version: 1, command_id: body.command_id, registry_revision: state.revision, total: 0, after: null, next_after: null, entries: [] });
      throw new TypeError('SOURCE committed reply lost');
    }
    if (path.includes('/settings/models/commands/')) { held = true; await gate; }
    return undefined;
  };
  mount(); await screen.findByRole('region', { name: 'Configured models' });
  fireEvent.click(screen.getByRole('button', { name: 'Details for Exact/Model via OpenRouter' }));
  const remove = screen.getByRole('button', { name: 'Remove Exact/Model via OpenRouter' });
  await waitFor(() => expect(remove).toHaveAttribute('aria-disabled', 'false'));
  remove.focus(); fireEvent.click(remove);
  if (lost) { const recover = await screen.findByRole('button', { name: 'Read current state' }); recover.focus(); fireEvent.click(recover); }
  await waitFor(() => expect(held).toBe(true));
  const reload = screen.getByRole('link', { name: 'Models' });
  if (moved) reload.focus();
  await act(async () => { release(); await gate; });
  await screen.findByText('No models configured.');
  await waitFor(() => expect(moved ? reload : screen.getByRole('button', { name: 'Add models' })).toHaveFocus());
  expect(state.writes).toHaveLength(1);
});
it('enumerates assignments without confirmation, replacement or writes', async () => {
  const choice = { connection_id: connectionId, connection_revision: 1, model: entry.model, output_tokens: 512 };
  const { state } = settingsBackend({ ...configured, selection: { selection_id: entryId, revision: 1, default: choice, brain: choice, investigator: null, validator: choice } });
  vi.spyOn(window, 'confirm').mockReturnValue(true); mount();
  await screen.findByRole('region', { name: 'Configured models' });
  fireEvent.click(screen.getByRole('button', { name: 'Details for Exact/Model via OpenRouter' }));
  const remove = screen.getByRole('button', { name: 'Remove Exact/Model via OpenRouter' });
  expect(remove).toBeDisabled();
  const hint = within(screen.getByRole('listitem', { name: 'Model Exact/Model via OpenRouter' })).getByText('Used by Default, Brain, Validator. Reassign explicitly in Model assignments before removing this model.');
  expect(hint).toBeVisible();
  expect(remove).toHaveAttribute('aria-describedby', hint.id);
  fireEvent.click(remove);
  expect(state.writes).toEqual([]);
  expect(window.confirm).not.toHaveBeenCalled();
});
it('groups quiet reload with Add models and confirms a read without writes', async () => {
  backend(); mount();
  const actions = await screen.findByRole('group', { name: 'Model library actions' });
  expect(within(actions).getAllByRole('button').map(button => button.textContent)).toEqual(['Reload', 'Add models']);
  fireEvent.click(within(actions).getByRole('button', { name: 'Reload current settings' }));
  await screen.findByText('Settings reloaded.');
  expect(writes).toEqual([]);
});
it('expires confirmations but retains actionable uncertainty and its inline state', async () => {
  backend(); const mounted = mount(); await screen.findByRole('region', { name: 'Configured models' });
  vi.useFakeTimers();
  try {
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Reload current settings' })); await vi.advanceTimersByTimeAsync(50); });
    expect(screen.getByRole('complementary', { name: 'Settings notification' })).toHaveTextContent('Settings reloaded.');
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(screen.queryByRole('complementary', { name: 'Settings notification' })).not.toBeInTheDocument();
  } finally { vi.useRealTimers(); mounted.unmount(); }
  backend({ empty: true, lost: true }); mount(); await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Add models' })); fireEvent.change(screen.getByLabelText('API key'), { target: { value: 'synthetic-not-a-secret' } });
  vi.useFakeTimers();
  try {
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Continue' })); await vi.advanceTimersByTimeAsync(50); });
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(screen.getByRole('region', { name: 'Settings recovery' })).toHaveTextContent('Save unconfirmed');
    expect(screen.getByRole('button', { name: 'Recover exact receipt' })).toBeEnabled();
    expect(screen.getByText('Save unconfirmed. Recover the exact receipt before another mutation.')).toBeVisible();
  } finally { vi.useRealTimers(); }
});
it('shows passive feedback only where it does not cover controls or focus', async () => {
  backend(); let collision = false;
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
    if (this.matches('aside')) return new DOMRect(700, 900, 280, 52);
    if (this.matches('main')) return new DOMRect(0, 0, 1000, 1000);
    if (collision && this.getAttribute('aria-label') === 'Reload current settings') return new DOMRect(750, 910, 100, 44);
    return new DOMRect(0, 0, 0, 0);
  });
  mount(); await screen.findByRole('region', { name: 'Configured models' });
  fireEvent.click(screen.getByRole('button', { name: 'Reload current settings' }));
  const feedback = await screen.findByRole('complementary', { name: 'Settings notification' });
  expect(feedback).toBeVisible();
  collision = true; fireEvent(window, new Event('resize')); expect(feedback).not.toBeVisible();
  collision = false; fireEvent(window, new Event('scroll')); expect(feedback).toBeVisible();
  expect(writes).toEqual([]);
});
it('keeps actionable save recovery inline after dismissing the compact feedback', async () => {
  backend({ empty: true, lost: true }); mount(); await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Add models' })); fireEvent.change(screen.getByLabelText('API key'), { target: { value: 'synthetic-only' } });
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
  const feedback = await screen.findByRole('complementary', { name: 'Settings notification' });
  expect(feedback).toHaveTextContent('Settings need attention.'); expect(feedback).not.toHaveTextContent(/Command|Recover the exact|No success/);
  expect(within(feedback).getAllByRole('button')).toHaveLength(1);
  fireEvent.click(within(feedback).getByRole('button', { name: 'Dismiss notification' }));
  const recovery = screen.getByRole('region', { name: 'Settings recovery' });
  expect(recovery).toHaveTextContent('Save unconfirmed. Recover the exact receipt before another mutation.');
  expect(within(recovery).getByRole('button', { name: 'Read current state' })).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Recover exact receipt' })).toBeEnabled(); expect(writes).toHaveLength(1);
});
it('uses the saved key without a password field or key resubmission; Back preserves selection', async () => {
  backend(); mount();
  await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled()); fireEvent.click(screen.getByRole('button', { name: 'Add models' }));
  const wizard = screen.getByRole('region', { name: 'Add models wizard' });
  expect(within(wizard).getByText('Saved key')).toBeVisible();
  expect(within(wizard).queryByLabelText('API key')).not.toBeInTheDocument();
  fireEvent.click(within(wizard).getByRole('button', { name: 'Continue' }));
  await within(wizard).findByLabelText('Search models');
  expect(writes).toHaveLength(1); expect(writes[0]!.path).toMatch(/catalog\/refresh$/);
  fireEvent.click(within(wizard).getByRole('button', { name: 'Cancel' }));
  expect(screen.queryByRole('region', { name: 'Add models wizard' })).not.toBeInTheDocument();
});
it('lost connection save wipes the DOM secret and recovery never starts a fresh catalog', async () => {
  backend({ empty: true, lost: true }); const mounted = mount();
  await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled()); fireEvent.click(screen.getByRole('button', { name: 'Add models' }));
  const key = screen.getByLabelText('API key');
  fireEvent.change(key, { target: { value: 'synthetic-only-secret' } });
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
  await within(screen.getByRole('region', { name: 'Settings recovery' })).findByText(/Save unconfirmed/); expect(key).toHaveValue('');
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  mounted.unmount(); mount();
  fireEvent.click(await screen.findByRole('button', { name: 'Recover exact receipt' }));
  await screen.findByText(/Exact receipt recovered/);
  expect(writes).toHaveLength(1); expect(writes[0]!.path).toMatch(/providers$/);
  expect(JSON.stringify(sessionStorage)).not.toContain('synthetic-only-secret');
});
it('Cancel wipes an unsent secret even from a detached node', async () => {
  backend({ empty: true }); mount(); await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled()); fireEvent.click(screen.getByRole('button', { name: 'Add models' }));
  const input = screen.getByLabelText('API key'); fireEvent.change(input, { target: { value: 'synthetic-only' } });
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  expect(input).toHaveValue(''); expect(writes).toHaveLength(0);
});
it.each(['openrouter', 'orcarouter'] as const)('direct test consent names the exact model and %s before Send', async provider => {
  const providerLabel = provider === 'openrouter' ? 'OpenRouter' : 'OrcaRouter';
  const model = 'Exact/' + 'x'.repeat(250), otherConnection = '44444444-4444-4444-8444-444444444444';
  const { state } = settingsBackend({ ...configured, connections: [savedConnection, { ...savedConnection, connection_id: otherConnection, provider: 'orcarouter' }] },
    [{ ...entry, model }, { ...entry, model, entry_id: otherConnection, connection_id: otherConnection }], [{ ...metadata, model }]);
  mount();
  const test = await screen.findByRole('button', { name: `Test ${model} via ${providerLabel}` });
  await waitFor(() => expect(test).toBeEnabled()); fireEvent.click(test);
  const consent = screen.getByRole('region', { name: 'Test consent' });
  expect(model).toHaveLength(256);
  expect(consent).toHaveTextContent(`${providerLabel} · ${model}`);
  expect(within(consent).getByText(model, { exact: true })).toBeVisible();
  expect(consent).toHaveTextContent('Provider charges may apply.');
  expect(within(consent).getByRole('checkbox')).not.toBeChecked();
  expect(within(consent).getByRole('button', { name: 'Send model test' })).toBeDisabled();
  expect(screen.getByText('Fixed input').closest('details')).not.toHaveAttribute('open');
  fireEvent.click(screen.getByText('Fixed input'));
  expect(screen.getByText('Respond only with OMNIS_MODEL_TEST_OK. Use no tools.')).toBeVisible();
  expect(screen.getByText('This is a synthetic local settings test. Reply with OMNIS_MODEL_TEST_OK.')).toBeVisible();
  fireEvent.click(within(consent).getByRole('checkbox'));
  expect(within(consent).getByRole('button', { name: 'Send model test' })).toBeEnabled();
  fireEvent.click(within(consent).getByRole('button', { name: 'Cancel' }));
  expect(state.writes).toHaveLength(0);
});
it('keeps single-model output controls secondary before assignment confirmation', async () => {
  backend();
  mount();
  await waitFor(() => expect(screen.getByRole('button', { name: 'Save assignments' })).toHaveAttribute('aria-disabled', 'false'));
  expect(screen.queryByLabelText('Default model')).not.toBeInTheDocument();
  const controls = screen.getByText('Output controls', { exact: true });
  expect(controls.closest('details')).not.toHaveAttribute('open');
  fireEvent.click(controls);
  expect(screen.getByLabelText('Default output tokens')).toHaveValue(512);
});
