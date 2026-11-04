import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import { App } from './App';
import { health, instance, session } from '../../tests/fixtures';
import { configured, connection as savedConnection, settingsBackend } from '../../tests/settings-fixtures';
import { remember, sessionScope, testStorage } from '../features/engagement/SettingsModels';

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
it.each(['Skills', 'Runtime & data'])('activates %s and Models navigation, wiping unsent secrets without resuming work', async destination => {
  const user = userEvent.setup(), { state, hook } = settingsBackend();
  hook.intercept = path => path === '/api/v1/settings/catalog' ? Response.json({ items: [], has_more: false, next_after: null }) : undefined;
  mount(); await screen.findByRole('region', { name: 'Configured models' });
  await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Add models' }));
  fireEvent.change(screen.getByRole('combobox', { name: 'Provider' }), { target: { value: 'orcarouter' } });
  const key = screen.getByLabelText('API key'); fireEvent.change(key, { target: { value: 'synthetic-unsent-navigation' } });
  const nav = within(screen.getByRole('navigation', { name: 'Settings navigation' }));
  nav.getByRole('link', { name: destination }).focus(); await user.keyboard('{Enter}');
  await screen.findByRole('heading', { name: destination === 'Skills' ? 'Published catalog' : 'Runtime & data' });
  expect(nav.getByRole('link', { name: destination })).toHaveAttribute('aria-current', 'page');
  expect(key).toHaveValue(''); expect(key).not.toBeInTheDocument();
  nav.getByRole('link', { name: 'Models' }).focus(); await user.keyboard('{Enter}');
  await screen.findByRole('region', { name: 'Configured models' });
  expect(nav.getByRole('link', { name: 'Models' })).toHaveAttribute('aria-current', 'page');
  expect(screen.queryByRole('region', { name: 'Add models wizard' })).not.toBeInTheDocument();
  expect(screen.queryByRole('region', { name: 'Test consent' })).not.toBeInTheDocument();
  expect(JSON.stringify(sessionStorage)).not.toContain('synthetic-unsent-navigation');
  expect(state.keys).toEqual(configured); expect(state.entries).toEqual([entry]); expect(state.writes).toEqual([]);
});
it('opens inline Remove without effects and cancels by button or Escape with focus restored', async () => {
  const { state } = settingsBackend(); const confirm = vi.spyOn(window, 'confirm'); mount();
  await screen.findByRole('region', { name: 'Configured models' });
  expect(screen.queryByRole('button', { name: 'Remove Exact/Model via OpenRouter' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Details for Exact/Model via OpenRouter' }));
  const remove = screen.getByRole('button', { name: 'Remove Exact/Model via OpenRouter' });
  await waitFor(() => expect(remove).toHaveAttribute('aria-disabled', 'false'));
  for (const escape of [false, true]) {
    remove.focus(); fireEvent.click(remove);
    const confirmation = screen.getByRole('region', { name: 'Remove model confirmation' });
    expect(confirmation).toHaveTextContent('Exact/Model · OpenRouter');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    const cancel = within(confirmation).getByRole('button', { name: 'Cancel' }); cancel.focus();
    if (escape) fireEvent.keyDown(cancel, { key: 'Escape' }); else fireEvent.click(cancel);
    expect(screen.queryByRole('region', { name: 'Remove model confirmation' })).not.toBeInTheDocument();
    expect(remove).toHaveFocus();
  }
  expect(confirm).not.toHaveBeenCalled(); expect(state.writes).toEqual([]);
});
it.each(['registry', 'entry', 'assignment', 'unknown', 'active', 'collapse', 'unmount'] as const)('refuses old inline Remove consent after %s changes', async change => {
  const { state } = settingsBackend(); const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const mounted = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/settings/providers']}><App /></MemoryRouter></QueryClientProvider>);
  const toggle = await screen.findByRole('button', { name: 'Details for Exact/Model via OpenRouter' }); fireEvent.click(toggle);
  const remove = screen.getByRole('button', { name: 'Remove Exact/Model via OpenRouter' });
  await waitFor(() => expect(remove).toHaveAttribute('aria-disabled', 'false')); fireEvent.click(remove);
  const confirmation = screen.getByRole('region', { name: 'Remove model confirmation' });
  const confirm = within(confirmation).getByRole('button', { name: 'Remove' });
  const elsewhere = screen.getByRole('link', { name: 'Models' }); elsewhere.focus();
  if (change === 'collapse') { fireEvent.click(toggle); fireEvent.click(toggle); expect(screen.queryByRole('region', { name: 'Remove model confirmation' })).not.toBeInTheDocument(); }
  else if (change === 'unmount') mounted.unmount();
  else {
    const query = client.getQueryCache().findAll({ queryKey: ['private', 'settings-model-library'] })[0]!;
    // Change the real cached projection, not the confirmation snapshot.
    await act(async () => { client.setQueryData(query.queryKey, (value: { library: { revision: number; entries: typeof entry[] }; settings: typeof configured; checks: Record<string, unknown> }) => ({ ...value,
      library: { ...value.library, revision: value.library.revision + (change === 'registry' ? 1 : 0), entries: change === 'entry' ? [{ ...entry, revision: 2 }] : value.library.entries },
      settings: change === 'assignment' ? { ...value.settings, selection: { selection_id: entryId, revision: 1, default: { connection_id: connectionId, connection_revision: 1, model: entry.model, output_tokens: 512 }, brain: null, investigator: null, validator: null } } : value.settings,
      checks: change === 'unknown' ? { [entryId]: 'UNKNOWN' } : change === 'active' ? { [entryId]: { operation_id: catalogId, entry_id: entryId, state: 'RUNNING', state_revision: 2 } } : value.checks,
    })); });
  }
  fireEvent.click(confirm);
  if (change !== 'unmount') expect(elsewhere).toHaveFocus();
  expect(state.writes).toEqual([]);
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
  const confirm = within(screen.getByRole('region', { name: 'Remove model confirmation' })).getByRole('button', { name: 'Remove' });
  fireEvent.click(confirm); fireEvent.click(confirm);
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
  const confirm = within(screen.getByRole('region', { name: 'Remove model confirmation' })).getByRole('button', { name: 'Remove' });
  confirm.focus(); fireEvent.click(confirm);
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
  fireEvent.click(screen.getByRole('button', { name: 'Dismiss notification' }));
  expect(screen.queryByRole('complementary', { name: 'Settings notification' })).not.toBeInTheDocument();
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
it.each(['blur', 'another control'] as const)('pauses notification expiry during focus and resumes only remaining time after %s', async exit => {
  backend(); const mounted = mount(); await screen.findByRole('region', { name: 'Configured models' });
  vi.useFakeTimers();
  try {
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Reload current settings' })); await vi.advanceTimersByTimeAsync(50); });
    const feedback = screen.getByRole('complementary', { name: 'Settings notification' });
    const dismiss = within(feedback).getByRole('button', { name: 'Dismiss notification' });
    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    dismiss.focus(); expect(dismiss).toHaveFocus();
    await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
    expect(dismiss).toHaveFocus(); expect(feedback).toBeVisible();
    const elsewhere = screen.getByRole('link', { name: 'Models' });
    await act(async () => { if (exit === 'blur') dismiss.blur(); else elsewhere.focus(); });
    expect(exit === 'blur' ? document.body : elsewhere).toHaveFocus();
    await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
    expect(feedback).toBeVisible();
    await act(async () => { await vi.advanceTimersByTimeAsync(600); });
    expect(feedback).not.toBeInTheDocument();
    expect(exit === 'blur' ? document.body : elsewhere).toHaveFocus();
  } finally { vi.useRealTimers(); mounted.unmount(); }
});
it('does not hide a focused notification when repositioning has no safe space', async () => {
  backend(); let blocked = false;
  vi.stubGlobal('innerHeight', 1000);
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
    if (this.tagName === 'ASIDE') return new DOMRect(700, 900 - (parseFloat(this.style.bottom || '16') - 16), 280, 52);
    if (blocked && this.getAttribute('aria-label') === 'Reload current settings') return new DOMRect(0, 0, 1000, 1000);
    return new DOMRect(0, 0, 0, 0);
  });
  const mounted = mount(); await screen.findByRole('region', { name: 'Configured models' }); vi.useFakeTimers();
  try {
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Reload current settings' })); await vi.advanceTimersByTimeAsync(50); });
    const feedback = screen.getByRole('complementary', { name: 'Settings notification' });
    const dismiss = within(feedback).getByRole('button', { name: 'Dismiss notification' }); dismiss.focus();
    const bottom = feedback.style.bottom;
    blocked = true; fireEvent(window, new Event('resize'));
    expect(feedback.style.bottom).toBe(bottom);
    expect(feedback).toBeVisible(); expect(dismiss).toHaveFocus();
    await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
    expect(feedback).toBeVisible(); expect(dismiss).toHaveFocus();
    await act(async () => { dismiss.blur(); }); expect(feedback).not.toBeVisible();
    blocked = false; fireEvent(window, new Event('resize')); expect(feedback).toBeVisible();
    await act(async () => { await vi.advanceTimersByTimeAsync(5001); }); expect(feedback).not.toBeInTheDocument();
  } finally { vi.useRealTimers(); mounted.unmount(); }
});
it('moves passive feedback above a collision without hiding it or stealing focus', async () => {
  backend(); let collision = false;
  vi.stubGlobal('innerHeight', 1000);
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
    if (this.tagName === 'ASIDE') return new DOMRect(700, 900 - (parseFloat(this.style.bottom || '16') - 16), 280, 52);
    if (this.matches('main')) return new DOMRect(0, 0, 1000, 1000);
    if (collision && this.getAttribute('aria-label') === 'Reload current settings') return new DOMRect(750, 910, 100, 44);
    return new DOMRect(0, 0, 0, 0);
  });
  mount(); await screen.findByRole('region', { name: 'Configured models' });
  fireEvent.click(screen.getByRole('button', { name: 'Reload current settings' }));
  const feedback = await screen.findByRole('complementary', { name: 'Settings notification' });
  expect(feedback).toBeVisible();
  const elsewhere = screen.getByRole('link', { name: 'Models' }); elsewhere.focus();
  collision = true; await waitFor(() => { fireEvent(window, new Event('resize')); expect(parseFloat(feedback.style.bottom)).toBeGreaterThan(16); });
  expect(feedback).toBeVisible(); expect(elsewhere).toHaveFocus();
  collision = false; fireEvent(window, new Event('scroll')); expect(feedback).toBeVisible();
  expect(writes).toEqual([]);
});
it.each(['label', 'hint', 'page heading', 'section heading', 'provider heading', 'model identity', 'model status', 'provider status', 'saved key'] as const)('keeps assignment %s text clear of passive feedback after blur', async target => {
  settingsBackend(configured, [entry, { ...entry, entry_id: catalogId, model: 'Other/Model' }], [metadata, { ...metadata, model: 'Other/Model' }]);
  let obstacle: HTMLElement | null = null;
  vi.stubGlobal('innerHeight', 1000);
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
    if (this.tagName === 'ASIDE') return new DOMRect(116, 919 - (parseFloat(this.style.bottom || '16') - 16), 188, 51);
    return this === obstacle ? new DOMRect(80, 930, 220, 22) : new DOMRect(0, 0, 0, 0);
  });
  mount(); await screen.findByRole('region', { name: 'Configured models' });
  fireEvent.click(screen.getByRole('button', { name: 'Save assignments' }));
  const feedback = await screen.findByRole('complementary', { name: 'Settings notification' });
  const dismiss = within(feedback).getByRole('button', { name: 'Dismiss notification' }); dismiss.focus();
  if (target === 'saved key') fireEvent.click(screen.getByRole('button', { name: 'Add models' }));
  obstacle = target === 'label' ? screen.getByText('Default model', { selector: 'label' })
    : target === 'hint' ? screen.getByText('For future runs. Existing runs keep their pinned settings.')
    : target === 'page heading' ? screen.getByRole('heading', { name: 'Settings', level: 1 })
    : target === 'section heading' ? screen.getByRole('heading', { name: 'Models', level: 2 })
    : target === 'provider heading' ? screen.getByRole('heading', { name: 'OpenRouter', level: 3 })
    : target === 'model identity' ? within(screen.getByRole('listitem', { name: 'Model Exact/Model via OpenRouter' })).getByText('Exact model').parentElement!
    : target === 'model status' ? screen.getAllByText('Not tested')[0]!
    : screen.getByText(target === 'provider status' ? 'Key saved' : 'Saved key');
  expect(obstacle).not.toBeNull(); dismiss.focus();
  fireEvent(window, new Event('resize')); expect(feedback.style.bottom).toBe(''); expect(dismiss).toHaveFocus();
  await act(async () => { dismiss.blur(); });
  expect(feedback).toBeVisible();
  expect(feedback.getBoundingClientRect().bottom).toBeLessThanOrEqual(obstacle.getBoundingClientRect().top - 4);
  expect(document.body).toHaveFocus();
});
it('does not expire a notification while no safe viewport position is available', async () => {
  backend(); let blocked = true;
  vi.stubGlobal('innerHeight', 1000);
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
    if (this.tagName === 'ASIDE') return new DOMRect(700, 900 - (parseFloat(this.style.bottom || '16') - 16), 280, 52);
    if (blocked && this.getAttribute('aria-label') === 'Reload current settings') return new DOMRect(0, 0, 1000, 1000);
    return new DOMRect(0, 0, 0, 0);
  });
  mount(); await screen.findByRole('region', { name: 'Configured models' }); vi.useFakeTimers();
  try {
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Reload current settings' })); await vi.advanceTimersByTimeAsync(50); });
    const feedback = screen.getByLabelText('Settings notification'); expect(feedback).not.toBeVisible();
    await act(async () => { await vi.advanceTimersByTimeAsync(6000); }); expect(feedback).toBeInTheDocument();
    blocked = false; fireEvent(window, new Event('resize')); expect(feedback).toBeVisible();
    await act(async () => { await vi.advanceTimersByTimeAsync(5001); }); expect(feedback).not.toBeInTheDocument();
  } finally { vi.useRealTimers(); }
});
it('keeps actionable save recovery local without a duplicate error notification', async () => {
  backend({ empty: true, lost: true }); mount(); await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Add models' })); fireEvent.change(screen.getByLabelText('API key'), { target: { value: 'synthetic-only' } });
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
  const recovery = await screen.findByRole('region', { name: 'Settings recovery' });
  expect(screen.queryByRole('complementary', { name: 'Settings notification' })).not.toBeInTheDocument();
  expect(recovery).toHaveTextContent('Save unconfirmed. Recover the exact receipt before another mutation.');
  expect(within(recovery).getByRole('button', { name: 'Read current state' })).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Recover exact receipt' })).toBeEnabled(); expect(writes).toHaveLength(1);
});
it('keeps the completed check Connected during an assignment-only save receipt', async () => {
  const { state, hook } = settingsBackend();
  const id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
  const completed = {
    schema_version: 2, operation_id: id, state: 'FINISHED', state_revision: 3, finish_reason: 'COMPLETED', selection_revision: null,
    metadata_command_id: null, metadata_state: 'NOT_REQUESTED', reason: null, requested_provider: 'openrouter', requested_model: entry.model, requested_output_tokens: entry.output_tokens,
    observed_model: entry.model, provider_status: null, result_state: 'COMPLETED', output_state: 'COMPLETE', response_text: 'OMNIS_MODEL_TEST_OK', usage_state: 'UNKNOWN', input_tokens: null, output_tokens: null, reasoning_tokens: null, cost_observed: null,
    system_message: 'Respond only with OMNIS_MODEL_TEST_OK. Use no tools.', user_message: 'This is a synthetic local settings test. Reply with OMNIS_MODEL_TEST_OK.', calls_limit: 1, wall_seconds: 300,
    entry_id: entry.entry_id, entry_revision: entry.revision, connection_id: entry.connection_id, connection_revision: entry.connection_revision, current: true,
  };
  let held = false, release = () => {};
  const gate = new Promise<void>(resolve => { release = resolve; });
  hook.intercept = async path => {
    if (path.includes('/entries/latest/') || path === '/api/v1/model-test/entries/' + id) return Response.json(completed);
    if (path.includes('/providers/commands/')) { held = true; await gate; }
    return undefined;
  };
  remember(testStorage, await sessionScope(session.csrf_token), id);
  const mounted = mount();
  try {
    await screen.findByText('Connected');
    fireEvent.click(within(screen.getByRole('region', { name: 'Model assignments' })).getByRole('button', { name: 'Save assignments' }));
    await waitFor(() => expect(held).toBe(true));
    expect(state.writes.map(write => write.body.action)).toEqual(['save_selection_v2']);
    const row = within(screen.getByRole('listitem', { name: 'Model Exact/Model via OpenRouter' }));
    expect(row.queryByText('Connecting', { exact: true })).not.toBeInTheDocument();
    expect(row.getByText('Connected', { exact: true })).toBeVisible();
    await act(async () => { release(); await gate; });
    await screen.findByText('Assignments saved.');
    expect(row.getByText('Connected', { exact: true })).toBeVisible();
    expect(state.writes.map(write => write.body.action)).toEqual(['save_selection_v2']);
  } finally { release(); mounted.unmount(); }
});
it('keeps assignment drafts quiet and lost-save recovery beside assignments without a success claim', async () => {
  const { state, hook } = settingsBackend();
  hook.intercept = (_path, body, method) => { if (method === 'PUT' && body.action === 'save_selection_v2') throw new TypeError('SOURCE lost save'); return undefined; };
  mount(); const panel = await screen.findByRole('region', { name: 'Model assignments' });
  fireEvent.click(within(panel).getByText('Output controls'));
  fireEvent.change(screen.getByLabelText('Default output tokens'), { target: { value: '128' } });
  expect(within(panel).getByText('Unsaved assignments.')).toBeVisible();
  expect(screen.queryByRole('region', { name: 'Settings recovery' })).not.toBeInTheDocument();
  expect(screen.queryByRole('complementary', { name: 'Settings notification' })).not.toBeInTheDocument();
  fireEvent.click(within(panel).getByRole('button', { name: 'Save assignments' }));
  expect(await within(panel).findByRole('region', { name: 'Settings recovery' })).toHaveTextContent('Save unconfirmed');
  expect(screen.getAllByRole('region', { name: 'Settings recovery' })).toHaveLength(1);
  expect(screen.queryByText('Assignments saved.')).not.toBeInTheDocument();
  expect(state.writes).toHaveLength(1);
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
  await within(await screen.findByRole('region', { name: 'Settings recovery' })).findByText(/Save unconfirmed/); expect(key).toHaveValue('');
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  mounted.unmount(); mount();
  fireEvent.click(await screen.findByRole('button', { name: 'Recover exact receipt' }));
  await screen.findByText('Settings recovered.');
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
  expect(within(consent).getByRole('checkbox', { name: 'I approve using this model.' })).not.toBeChecked();
  expect(within(consent).getByRole('button', { name: 'Send model test' })).toBeDisabled();
  expect(consent).not.toHaveTextContent(/Fixed input|300 seconds|No tools|refund|OMNIS_MODEL_TEST_OK/);
  fireEvent.click(within(consent).getByRole('checkbox'));
  expect(within(consent).getByRole('button', { name: 'Send model test' })).toBeEnabled();
  fireEvent.click(within(consent).getByRole('button', { name: 'Cancel' }));
  fireEvent.click(test);
  expect(screen.getByRole('checkbox', { name: 'I approve using this model.' })).not.toBeChecked();
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
