import { StrictMode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, expect, it, vi } from 'vitest';
import { App } from './App';
import { catalogId, configured, empty, entry, entryId, selected, settingsBackend } from '../../tests/settings-fixtures';
import type { ModelEntry } from '../features/engagement/SettingsModels';
import type { EntryTestView } from '../shared/api/modelTest';
import { remember, sessionScope, testStorage } from '../features/engagement/SettingsModels';
import { session } from '../../tests/fixtures';
const models = Array.from({ length: 32 }, (_, i) => ({ model: `Catalog/${String(i).padStart(2, '0')}`, name: `Model ${i}`, max_output_tokens: 4096, supports_max_tokens: true, reason: null }));
beforeEach(() => { sessionStorage.clear(); vi.stubGlobal('confirm', vi.fn(() => true)); });
function mount(strict = false) {
  const app = <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false, networkMode: 'always' } } })}><MemoryRouter initialEntries={['/settings/providers']}><App /></MemoryRouter></QueryClientProvider>;
  return render(strict ? <StrictMode>{app}</StrictMode> : app);
}
async function wizard() { await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled()); fireEvent.click(screen.getByRole('button', { name: 'Add models' })); fireEvent.click(screen.getByRole('button', { name: 'Continue' })); await screen.findByLabelText('Search models'); await screen.findByRole('button', { name: 'Add Catalog/00' }); return screen.getByRole('region', { name: 'Add models wizard' }); }
async function review() { const button = screen.getByRole('button', { name: 'Continue' }); await waitFor(() => expect(button).not.toHaveAttribute('aria-disabled', 'true')); fireEvent.click(button); return screen.findByRole('button', { name: 'Save models' }); }
function operation(id: string, target: ModelEntry): EntryTestView { return {
  schema_version: 2, operation_id: id, state: 'RUNNING', state_revision: 2, finish_reason: null, selection_revision: null,
  metadata_command_id: null, metadata_state: 'NOT_REQUESTED', reason: null, requested_provider: 'openrouter', requested_model: target.model, requested_output_tokens: target.output_tokens,
  observed_model: null, provider_status: null, result_state: null, output_state: 'ABSENT', response_text: null, usage_state: 'UNKNOWN', input_tokens: null, output_tokens: null, reasoning_tokens: null, cost_observed: null,
  system_message: 'Respond only with OMNIS_MODEL_TEST_OK. Use no tools.', user_message: 'This is a synthetic local settings test. Reply with OMNIS_MODEL_TEST_OK.', calls_limit: 1, wall_seconds: 300,
  entry_id: target.entry_id, entry_revision: target.revision, connection_id: target.connection_id, connection_revision: target.connection_revision, current: true,
}; }
it.each(['FAILED', 'UNKNOWN', 'RUNNING', 'stale', 'missing', 'unavailable'] as const)('never resurrects an older stored green result when latest is %s', async status => {
  const { hook, state } = settingsBackend();
  const oldId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', newId = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
  const old: EntryTestView = { ...operation(oldId, entry), state: 'FINISHED', finish_reason: 'COMPLETED', result_state: 'COMPLETED' };
  const latest: EntryTestView = { ...old, operation_id: newId, state: status === 'RUNNING' ? 'RUNNING' : 'FINISHED', current: status !== 'stale', result_state: status === 'FAILED' ? 'FAILED' : status === 'UNKNOWN' ? 'UNKNOWN' : status === 'RUNNING' ? null : 'COMPLETED' };
  hook.intercept = path => {
    if (path.includes('/entries/latest/')) return status === 'unavailable' || status === 'missing' ? Response.json({ error: { code: status === 'missing' ? 'NOT_FOUND' : 'CONTROL_UNAVAILABLE', correlation_id: entryId } }, { status: status === 'missing' ? 404 : 503 }) : Response.json(latest);
    if (path.endsWith(oldId)) return Response.json(old);
  };
  remember(testStorage, await sessionScope(session.csrf_token), oldId);
  mount(); const list = await screen.findByRole('region', { name: 'Configured models' });
  expect(within(list).queryByText('Connected')).not.toBeInTheDocument();
  expect(within(list).getByText(status === 'FAILED' ? 'Failed' : status === 'RUNNING' ? 'Connecting' : status === 'stale' ? 'Unavailable — stale check' : status === 'missing' ? 'Not tested' : 'Unconfirmed')).toBeVisible();
  expect(state.writes).toHaveLength(0);
});
it('marks prior Connected state unconfirmed after a settings read fails, including after notice dismissal', async () => {
  const { hook } = settingsBackend(); let failed = false;
  hook.intercept = path => {
    if (path === '/api/v1/settings/providers' && failed) return Response.json({ error: { code: 'CONTROL_UNAVAILABLE', correlation_id: entryId } }, { status: 503 });
    if (path.includes('/entries/latest/')) return Response.json({ ...operation(crypto.randomUUID(), entry), state: 'FINISHED', finish_reason: 'COMPLETED', result_state: 'COMPLETED' });
  };
  mount(); await screen.findByText('Connected'); failed = true; fireEvent.click(screen.getByRole('button', { name: 'Reload current settings' }));
  await screen.findByText('Unconfirmed — reload settings'); fireEvent.click(screen.getByRole('button', { name: 'Dismiss notification' }));
  expect(screen.getByText('Unconfirmed — reload settings')).toBeVisible(); expect(screen.queryByText('Connected')).not.toBeInTheDocument();
});
it('hydrates at most 64 separate latest reads with concurrency four and stops on unmount', async () => {
  const entries = Array.from({ length: 64 }, (_, i) => ({ ...entry, entry_id: `00000000-0000-4000-8000-${String(i).padStart(12, '0')}`, model: `Model/${i}` }));
  const { state, hook } = settingsBackend(configured, entries, []);
  let inFlight = 0, maximum = 0;
  hook.intercept = async path => {
    if (!path.includes('/entries/latest/')) return;
    inFlight++; maximum = Math.max(maximum, inFlight); await new Promise(resolve => setTimeout(resolve, 1)); inFlight--;
    return Response.json({ error: { code: 'NOT_FOUND', correlation_id: entryId } }, { status: 404 });
  };
  const mounted = mount(); await screen.findByRole('region', { name: 'Configured models' });
  expect(state.reads.filter(path => path.includes('/entries/latest/'))).toHaveLength(64); expect(maximum).toBe(4); expect(state.writes).toHaveLength(0);
  mounted.unmount(); state.reads.length = 0;
  let release: (() => void) | undefined; const blocked = new Promise<void>(resolve => { release = resolve; });
  hook.intercept = async path => { if (path.includes('/entries/latest/')) { await blocked; return Response.json({ error: { code: 'NOT_FOUND', correlation_id: entryId } }, { status: 404 }); } };
  const second = mount(); await waitFor(() => expect(state.reads.filter(path => path.includes('/entries/latest/'))).toHaveLength(4)); second.unmount(); release!();
  await new Promise(resolve => setTimeout(resolve, 50)); expect(state.reads.filter(path => path.includes('/entries/latest/'))).toHaveLength(4);
});
it('StrictMode effect replay retains a live mutation lifetime and wizard through key receipt, catalog and model save', async () => {
  const { state } = settingsBackend(empty, [], models); mount(true);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Add models' }));
  const input = screen.getByLabelText('API key'); fireEvent.change(input, { target: { value: 'synthetic-strict-key' } });
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Add Catalog/00' }));
  expect(input).toHaveValue('');
  await review(); fireEvent.click(screen.getByRole('button', { name: 'Save models' }));
  await screen.findByText('Models saved. Assignments stay unchanged.');
  expect(state.writes.map(item => item.body.action)).toEqual(['save_connection', 'refresh', 'save_models']);
  expect(state.entries[0]!.model).toBe('Catalog/00'); expect(state.keys.selection).toBeNull();
});
it('searches cached pages only, preserves chips across Back and saves several exact models without touching Default', async () => {
  const keys = { ...configured, selection: { selection_id: entryId, revision: 1, default: selected, brain: { ...selected, output_tokens: 37 }, investigator: null, validator: null } };
  const { state } = settingsBackend(keys, [entry], [...models, { ...models[0]!, model: entry.model }]); mount(); const panel = await wizard();
  fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' }));
  fireEvent.click(screen.getByRole('button', { name: 'Next results' })); await screen.findByRole('button', { name: 'Add Catalog/16' }); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/16' }));
  fireEvent.change(screen.getByLabelText('Search models'), { target: { value: 'Catalog/31' } }); await screen.findByRole('button', { name: 'Add Catalog/31' });
  expect(state.writes).toHaveLength(1); await review(); expect(screen.getByText('Default and role overrides stay unchanged.')).toBeVisible();
  fireEvent.click(within(panel).getByRole('button', { name: 'Back' })); expect(within(panel).getByRole('list', { name: 'Selected models' })).toHaveTextContent('Model 0'); expect(within(panel).getByRole('list', { name: 'Selected models' })).toHaveTextContent('Model 16');
  await review(); fireEvent.click(screen.getByRole('button', { name: 'Save models' })); await screen.findByText('Models saved. Assignments stay unchanged.');
  expect(state.entries.map(item => item.model)).toEqual(expect.arrayContaining(['Exact/Model', 'Catalog/00', 'Catalog/16'])); expect(state.keys.selection).toEqual(keys.selection);
  expect(state.writes.map(item => item.body.action)).toEqual(['refresh', 'save_models']);
});
it('keeps focus on the wizard after Continue and on search across query refreshes', async () => {
  settingsBackend(configured, [], models); mount(); await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Add models' }));
  const next = screen.getByRole('button', { name: 'Continue' }); next.focus(); fireEvent.click(next);
  const search = await screen.findByLabelText('Search models');
  await waitFor(() => expect(within(screen.getByRole('region', { name: 'Add models wizard' })).getByRole('heading', { name: 'Add models' })).toHaveFocus());
  search.focus(); fireEvent.change(search, { target: { value: 'Catalog/01' } }); await screen.findByRole('button', { name: 'Add Catalog/01' }); expect(search).toHaveFocus();
});
it('review keeps short not-tested status, exact consent and closed output controls', async () => {
  const { state } = settingsBackend(configured, [], models); mount(); const panel = await wizard();
  fireEvent.click(within(panel).getByRole('button', { name: 'Add Catalog/00' })); await review();
  expect(within(panel).getByText('Not tested', { exact: true })).toBeVisible();
  expect(within(panel).getByText('Catalog/00', { selector: 'small', exact: true })).toBeVisible();
  expect(within(panel).getByText('Output controls').closest('details')).not.toHaveAttribute('open');
  expect(within(panel).getByLabelText('Catalog/00 output tokens')).not.toBeVisible();
  expect(within(panel).getByRole('checkbox', { name: /up to 1 call, one per listed model via OpenRouter/ })).not.toBeChecked();
  expect(panel).toHaveTextContent('Provider charges may apply.');
  expect(panel).toHaveTextContent('One call / 300 seconds, no tools or target traffic. Cancel is not a refund.');
  expect(within(panel).getByRole('button', { name: 'Save & connect' })).toBeDisabled();
  expect(state.writes.map(item => item.body.action)).toEqual(['refresh']);
});
it('manual 256-character exact ID saves UNVERIFIED and cannot acquire test consent', async () => {
  const { state } = settingsBackend(configured, [], models); mount(); await wizard(); const id = 'M'.repeat(256);
  fireEvent.click(screen.getByText('Enter a model ID')); fireEvent.change(screen.getByLabelText('Exact model ID'), { target: { value: id } }); fireEvent.click(screen.getByRole('button', { name: 'Add model ID' })); await review();
  expect(screen.getByRole('button', { name: 'Save & connect' })).toBeDisabled(); expect(screen.getByText('UNVERIFIED — manual model ID')).toBeVisible(); fireEvent.click(screen.getByRole('button', { name: 'Save models' }));
  await screen.findByText('Models saved. Assignments stay unchanged.'); expect(state.entries[0]!.model).toBe(id); expect(state.keys.selection).toBeNull(); expect(screen.queryByText(/All roles use/)).not.toBeInTheDocument();
});
it.each([0, 1.5, 65537])('invalid output cap %s cannot authorize Save & connect or send a registry write', async tokens => {
  const { state } = settingsBackend(configured, [], models); mount(); await wizard();
  fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); await review();
  fireEvent.click(screen.getByText('Output controls', { exact: true }));
  fireEvent.change(screen.getByLabelText('Catalog/00 output tokens'), { target: { value: tokens } });
  expect(screen.getByRole('checkbox', { name: /I approve the fixed synthetic input/ })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Save & connect' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Save models' })).toBeDisabled();
  expect(state.writes.map(item => item.body.action)).toEqual(['refresh']);
});
it('provider switch confirmation retains pending choices when refused', async () => {
  settingsBackend(configured, [], models); mount(); const panel = await wizard(); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); fireEvent.click(within(panel).getByRole('button', { name: 'Back' }));
  vi.stubGlobal('confirm', vi.fn(() => false)); fireEvent.change(screen.getByLabelText('Provider'), { target: { value: 'orcarouter' } }); expect(screen.getByLabelText('Provider')).toHaveValue('openrouter');
  fireEvent.click(screen.getByRole('button', { name: 'Continue' })); await screen.findByLabelText('Search models'); expect(screen.getByRole('list', { name: 'Selected models' })).toHaveTextContent('Model 0');
});
it('Save & connect waits for exact terminal readback before each next model and hydrates both without browser storage', async () => {
  const { state, hook } = settingsBackend(configured, [], models);
  const views = new Map<string, EntryTestView>(); let complete = false;
  hook.intercept = (path, body, method) => {
    if (path === '/api/v1/model-test/entries' && method === 'PUT') {
      expect(state.reads.some(read => read.includes('/models/commands/'))).toBe(true);
      const target = state.entries.find(item => item.entry_id === body.entry_id)!;
      if (views.size) expect([...views.values()][0]?.state).toBe('FINISHED');
      const view = operation(String(body.operation_id), target); views.set(target.entry_id, view); return Response.json(view);
    }
    if (path.includes('/entries/latest/')) return views.has(path.split('/').at(-1)!) ? Response.json(views.get(path.split('/').at(-1)!)) : Response.json({ error: { code: 'NOT_FOUND', correlation_id: entryId } }, { status: 404 });
    if (path.startsWith('/api/v1/model-test/entries/')) {
      const view = [...views.values()].find(item => item.operation_id === path.split('/').at(-1))!;
      const next: EntryTestView = complete ? { ...view, state: 'FINISHED', state_revision: 3, finish_reason: 'COMPLETED', result_state: 'COMPLETED' } : view;
      views.set(next.entry_id, next); return Response.json(next);
    }
  };
  const mounted = mount(); const panel = await wizard();
  fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/01' })); await review();
  expect(within(panel).queryByRole('combobox')).not.toBeInTheDocument();
  expect(within(panel).getByRole('checkbox')).toHaveAccessibleName(/2 calls/);
  fireEvent.click(within(panel).getByRole('checkbox')); const connect = screen.getByRole('button', { name: 'Save & connect' }); fireEvent.click(connect); fireEvent.click(connect);
  await waitFor(() => expect(views.size).toBe(1));
  expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(1);
  const currentReads = state.reads.filter(path => path === '/api/v1/settings/providers').length;
  fireEvent.click(screen.getByRole('button', { name: 'Reload current settings' }));
  expect(state.reads.filter(path => path === '/api/v1/settings/providers')).toHaveLength(currentReads);
  complete = true;
  await waitFor(() => expect(views.size).toBe(2), { timeout: 3000 });
  await waitFor(() => expect(within(screen.getByRole('region', { name: 'Configured models' })).getAllByText('Connected')).toHaveLength(2), { timeout: 3000 });
  mounted.unmount(); sessionStorage.clear(); mount();
  await waitFor(() => expect(within(screen.getByRole('region', { name: 'Configured models' })).getAllByText('Connected')).toHaveLength(2));
  expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(2);
  expect(state.keys.selection).toBeNull();
});
it.each(['before-first', 'between-models', 'unchanged'] as const)('pins consent across the %s generation window (SOURCE admission double)', async window => {
  const { state, hook } = settingsBackend(configured, [], models);
  const views = new Map<string, EntryTestView>();
  let held = false, release: () => void = () => {}; const gate = new Promise<void>(resolve => { release = resolve; });
  hook.intercept = async (path, body, method) => {
    if (path.includes('/models/commands/') && window !== 'between-models') { held = true; await gate; }
    if (path === '/api/v1/model-test/entries' && method === 'PUT') {
      const target = state.entries.find(item => item.entry_id === body.entry_id)!;
      const view: EntryTestView = { ...operation(String(body.operation_id), target), state: 'FINISHED', finish_reason: 'COMPLETED', result_state: 'COMPLETED' };
      views.set(view.operation_id!, view); return Response.json(view);
    }
    if (path.includes('/entries/latest/')) {
      const view = [...views.values()].find(item => item.entry_id === path.split('/').at(-1));
      if (view) return Response.json(view);
    } else if (path.startsWith('/api/v1/model-test/entries/')) {
      const view = views.get(path.split('/').at(-1)!);
      if (view && window === 'between-models' && views.size === 1) { held = true; await gate; }
      return view ? Response.json(view) : Response.json({ error: { code: 'NOT_FOUND', correlation_id: entryId } }, { status: 404 });
    }
  };
  mount(); await wizard(); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/01' })); await review();
  fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: 'Save & connect' }));
  await waitFor(() => expect(held).toBe(true));
  // Synthetic generation change only; real Stop/open and ledger counts belong to the PG scenario.
  if (window !== 'unchanged') state.instance = { ...state.instance, generation: 3 };
  release();
  if (window === 'unchanged') await screen.findByText('Models connected.');
  else await screen.findByText(/Test outcome unconfirmed/);
  const attempts = state.writes.filter(item => item.path === '/api/v1/model-test/entries');
  expect(attempts.map(item => item.body.expected_generation)).toEqual(window === 'before-first' ? [1] : [1, 1]);
  expect(views.size).toBe(window === 'before-first' ? 0 : window === 'between-models' ? 1 : 2);
  if (window !== 'unchanged') {
    fireEvent.click(screen.getByRole('button', { name: 'Read test status' }));
    await screen.findByText('Test was not admitted. A new test requires new consent.');
    fireEvent.click(screen.getByRole('button', { name: 'Reload current settings' })); await screen.findByText('Settings reloaded.');
    const test = screen.getByRole('button', { name: 'Test Catalog/01 via OpenRouter' });
    await waitFor(() => expect(test).toBeEnabled()); fireEvent.click(test);
    expect(screen.getByRole('checkbox')).not.toBeChecked(); expect(screen.getByRole('button', { name: 'Send model test' })).toBeDisabled();
    expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(attempts.length);
    fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: 'Send model test' }));
    await waitFor(() => expect(views.size).toBe(window === 'before-first' ? 1 : 2));
    expect(state.writes.at(-1)?.body.expected_generation).toBe(3);
  }
});
it.each(['single', 'review'] as const)('a delayed settings read cannot rebase open %s consent', async mode => {
  const { state, hook } = settingsBackend(configured, mode === 'single' ? [entry] : [], mode === 'single' ? undefined : models);
  let held = false, release: () => void = () => {}; const gate = new Promise<void>(resolve => { release = resolve; });
  mount();
  if (mode === 'single') {
    const test = await screen.findByRole('button', { name: `Test ${entry.model} via OpenRouter` }); await waitFor(() => expect(test).toBeEnabled()); fireEvent.click(test);
  } else { await wizard(); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); await review(); }
  hook.intercept = async path => { if (path === '/api/instance') { held = true; await gate; } return undefined; };
  fireEvent.click(screen.getByRole('button', { name: 'Reload current settings' })); await waitFor(() => expect(held).toBe(true));
  state.instance = { ...state.instance, generation: 3 }; release(); await screen.findByText('Settings reloaded.');
  fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: mode === 'single' ? 'Send model test' : 'Save & connect' }));
  await screen.findByText(/Test outcome unconfirmed/);
  expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries').map(item => item.body.expected_generation)).toEqual([1]);
  expect(state.reads.filter(path => path === '/api/instance').length).toBeGreaterThanOrEqual(2);
});
it.each(['unavailable', 'missing', 'closed', 'owner-unavailable'] as const)('cannot enable paid consent with %s instance status but allows local Save', async status => {
  const { state, hook } = settingsBackend(configured, [entry], [...models, { model: entry.model, name: 'Exact model', max_output_tokens: 4096, supports_max_tokens: true, reason: null }]);
  if (status === 'unavailable') hook.intercept = path => path === '/api/instance' ? Response.json({ error: { code: 'CONTROL_UNAVAILABLE', correlation_id: entryId } }, { status: 503 }) : undefined;
  if (status === 'missing') hook.intercept = path => path === '/api/instance' ? Response.json({}) : undefined;
  if (status === 'closed') state.instance.admission_open = false;
  if (status === 'owner-unavailable') state.instance.supervisor_ready = false;
  mount(); const panel = await wizard();
  expect(screen.getByRole('button', { name: `Test ${entry.model} via OpenRouter` })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); await review();
  expect(within(panel).getByRole('checkbox')).toBeDisabled(); expect(screen.getByRole('button', { name: 'Save & connect' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Save models' })); await screen.findByText('Models saved. Assignments stay unchanged.');
  expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(0);
});
it('an unavailable instance read after Save cannot launch the first paid check', async () => {
  const { state, hook } = settingsBackend(configured, [], models);
  mount(); await wizard(); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); await review();
  hook.intercept = path => path === '/api/instance' ? Response.json({ error: { code: 'CONTROL_UNAVAILABLE', correlation_id: entryId } }, { status: 503 }) : undefined;
  fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: 'Save & connect' }));
  await waitFor(() => expect(screen.queryByRole('region', { name: 'Add models wizard' })).not.toBeInTheDocument());
  expect(state.entries).toHaveLength(1);
  expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(0);
});
it.each([false, true])('manual read uncertainty=%s stops only unsent checks until fresh consent', async uncertain => {
  const { state, hook } = settingsBackend(configured, [], models);
  const views = new Map<string, EntryTestView>(); let failNextRead = false, finish = false, reads = 0;
  hook.intercept = (path, body, method) => {
    if (path === '/api/v1/model-test/entries' && method === 'PUT') {
      const target = state.entries.find(item => item.entry_id === body.entry_id)!;
      const view = operation(String(body.operation_id), target); views.set(target.entry_id, view); return Response.json(view);
    }
    if (path.includes('/entries/latest/')) return views.has(path.split('/').at(-1)!) ? Response.json(views.get(path.split('/').at(-1)!)) : Response.json({ error: { code: 'NOT_FOUND', correlation_id: entryId } }, { status: 404 });
    if (path.startsWith('/api/v1/model-test/entries/')) {
      reads++;
      if (failNextRead) { failNextRead = false; return Response.json({ error: { code: 'CONTROL_UNAVAILABLE', correlation_id: entryId } }, { status: 503 }); }
      const view = [...views.values()].find(item => item.operation_id === path.split('/').at(-1))!;
      const next: EntryTestView = finish ? { ...view, state: 'FINISHED', state_revision: 3, result_state: 'COMPLETED', finish_reason: 'COMPLETED' } : view;
      views.set(next.entry_id, next); return Response.json(next);
    }
  };
  mount(); await wizard(); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/01' })); await review();
  fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: 'Save & connect' }));
  await waitFor(() => expect(reads).toBeGreaterThan(0)); expect(views.size).toBe(1);
  const first = [...views.values()][0]!;
  failNextRead = uncertain; fireEvent.click(screen.getByRole('button', { name: 'Read test status' }));
  if (uncertain) await screen.findByText('UNKNOWN — keep the same operation ID. No test was resent.');
  else await waitFor(() => expect(reads).toBeGreaterThan(1));
  finish = true; await new Promise(resolve => setTimeout(resolve, 1100));
  expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(uncertain ? 1 : 2);
  if (uncertain) {
    const panel = screen.getByRole('region', { name: 'Model test operation' }), list = screen.getByRole('region', { name: 'Configured models' });
    await waitFor(() => expect(panel).toHaveTextContent('Catalog/00 · FINISHED · COMPLETED'));
    expect(panel).toHaveTextContent(`Operation ${first.operation_id}`);
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss notification' }));
    expect(within(list).getByText('Unconfirmed')).toBeVisible(); expect(within(list).queryByText('Connected')).not.toBeInTheDocument();
    expect(screen.queryByText('Models connected.')).not.toBeInTheDocument();
    fireEvent.click(within(panel).getByRole('button', { name: 'Read test status' }));
    await waitFor(() => expect(within(list).getByText('Connected')).toBeVisible());
    expect(within(list).getByText('Not tested')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Test Catalog/01 via OpenRouter' }));
    expect(screen.getByRole('checkbox')).not.toBeChecked(); expect(screen.getByRole('button', { name: 'Send model test' })).toBeDisabled();
    expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(1);
    expect(state.writes.filter(item => item.path.endsWith('/cancel'))).toHaveLength(0);
  } else await screen.findByText('Models connected.');
});
it.each(['FAILED', 'INCOMPLETE', 'UNKNOWN', 'stale', 'refused', 'lost', 'read-lost', 'cancel', 'stop', 'unmount'] as const)('ends the unsent sequence on %s and never resumes it on reload', async failure => {
  const { state, hook } = settingsBackend(configured, [], models);
  let view: EntryTestView | undefined, finish = false;
  hook.intercept = (path, body, method) => {
    if (path === '/api/v1/model-test/entries' && method === 'PUT') {
      if (failure === 'refused') return Response.json({ error: { code: 'REVISION_CONFLICT', correlation_id: entryId } }, { status: 409 });
      const target = state.entries.find(item => item.entry_id === body.entry_id)!; view = operation(String(body.operation_id), target);
      if (failure === 'lost') throw new TypeError('Lost admission');
      return Response.json(view);
    }
    if (path.includes('/entries/latest/')) return view?.entry_id === path.split('/').at(-1) ? Response.json(view) : Response.json({ error: { code: 'NOT_FOUND', correlation_id: entryId } }, { status: 404 });
    if (path.startsWith('/api/v1/model-test/entries/')) {
      if (!view) return Response.json({ error: { code: 'NOT_FOUND', correlation_id: entryId } }, { status: 404 });
      if (failure === 'read-lost') throw new TypeError('Lost read');
      if (['FAILED', 'INCOMPLETE', 'UNKNOWN'].includes(failure)) view = { ...view, state: 'FINISHED', result_state: failure === 'FAILED' ? 'FAILED' : failure === 'INCOMPLETE' ? 'INCOMPLETE' : 'UNKNOWN', finish_reason: 'FAILED' };
      if (failure === 'stale') view = { ...view, state: 'FINISHED', result_state: 'COMPLETED', finish_reason: 'COMPLETED', current: false };
      if (method === 'POST') view = { ...view, state: 'FINISHED', result_state: 'NOT_SENT', finish_reason: 'CANCELLED' };
      if (finish) view = { ...view, state: 'FINISHED', result_state: 'COMPLETED', finish_reason: 'COMPLETED' };
      return Response.json(view);
    }
  };
  const mounted = mount(); await wizard();
  fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/01' })); await review();
  fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: 'Save & connect' }));
  await waitFor(() => expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(1));
  if (failure === 'cancel') { const cancel = await screen.findByRole('button', { name: 'Cancel test' }); await waitFor(() => expect(cancel).toBeEnabled()); fireEvent.click(cancel); }
  else if (failure === 'stop') fireEvent.click(await screen.findByRole('button', { name: 'Stop remaining checks' }));
  else if (failure !== 'unmount') await screen.findByText(/Connection checks stopped|Test outcome unconfirmed/);
  if (failure === 'read-lost') expect(within(screen.getByRole('region', { name: 'Configured models' })).getByText('Unconfirmed')).toBeVisible();
  mounted.unmount(); finish = true; mount();
  await screen.findByRole('region', { name: 'Configured models' });
  await new Promise(resolve => setTimeout(resolve, 800));
  expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(1);
});
it.each(['cancel', 'unmount', 'wrong-receipt', 'changed-revision'] as const)('does not dispatch after %s during Save receipt readback', async control => {
  const { hook, state } = settingsBackend(configured, [], models);
  let release: (() => void) | undefined, entered = false; const gate = new Promise<void>(resolve => { release = resolve; });
  hook.intercept = async path => {
    if (path.includes('/models/commands/')) {
      entered = true; await gate;
      const receipt = state.receipts.get(path.split('/').at(-1)!)!;
      if (control === 'changed-revision') state.revision++;
      return Response.json(control === 'wrong-receipt' ? { ...receipt, registry_revision: 2 } : receipt);
    }
    if (path.includes('/entries/latest/')) return Response.json({ error: { code: 'NOT_FOUND', correlation_id: entryId } }, { status: 404 });
  };
  const mounted = mount(); await wizard(); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); await review();
  fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: 'Save & connect' }));
  await waitFor(() => expect(entered).toBe(true));
  if (control === 'cancel') fireEvent.click(within(screen.getByRole('region', { name: 'Add models wizard' })).getByRole('button', { name: 'Cancel' }));
  if (control === 'unmount') mounted.unmount();
  release!(); await new Promise(resolve => setTimeout(resolve, 100));
  expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(0);
});
it('missing capabilities on any selected model allow local Save but never a silent test subset', async () => {
  const { state } = settingsBackend(configured, [], models); mount(); await wizard();
  fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); fireEvent.click(screen.getByText('Enter a model ID'));
  fireEvent.change(screen.getByLabelText('Exact model ID'), { target: { value: 'Manual/unknown' } }); fireEvent.click(screen.getByRole('button', { name: 'Add model ID' })); await review();
  expect(screen.getByRole('checkbox')).toBeDisabled(); expect(screen.getByRole('button', { name: 'Save & connect' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Save models' })); await screen.findByText('Models saved. Assignments stay unchanged.');
  expect(state.entries).toHaveLength(2); expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(0);
});
it('Save & connect keeps Cancel/readback outside wizard, and unmount abandons remaining work', async () => {
  const { state, hook } = settingsBackend(configured, [], models); let view: EntryTestView | undefined;
  hook.intercept = (path, body, method) => {
    if (path === '/api/v1/model-test/entries' && method === 'PUT') {
      const target = state.entries.find(item => item.entry_id === body.entry_id)!; view = operation(String(body.operation_id), target); return Response.json(view);
    }
    if (path.startsWith('/api/v1/model-test/entries/')) return Response.json(view);
  };
  const mounted = mount(); await wizard(); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/01' })); await review();
  expect(screen.getByRole('button', { name: 'Save & connect' })).toBeDisabled(); fireEvent.click(screen.getByRole('checkbox', { name: /I approve the fixed synthetic input/ })); fireEvent.click(screen.getByRole('button', { name: 'Save & connect' }));
  const panel = await screen.findByRole('region', { name: 'Model test operation' }); await waitFor(() => expect(within(panel).getByRole('button', { name: 'Cancel test' })).toBeEnabled());
  expect(screen.queryByRole('region', { name: 'Add models wizard' })).not.toBeInTheDocument(); expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(1);
  expect(view?.requested_model).toBe('Catalog/00'); expect(state.keys.selection).toBeNull(); expect(view?.entry_id).toBe(state.entries[0]!.entry_id);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled()); fireEvent.click(screen.getByRole('button', { name: 'Add models' }));
  expect(within(panel).getByRole('button', { name: 'Read test status' })).toBeEnabled(); fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  mounted.unmount(); mount(); await screen.findByRole('region', { name: 'Model test operation' }); expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(1);
});
it.each(['sequence', 'single', 'pending', 'hydrated'] as const)('keeps historical Read check away from the %s active Cancel target', async mode => {
  const target: ModelEntry = { ...entry, entry_id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', model: 'Catalog/00' };
  const { state, hook } = settingsBackend(configured, mode === 'sequence' ? [entry] : [entry, target], models);
  const old: EntryTestView = { ...operation('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', entry), state: 'FINISHED', state_revision: 3, finish_reason: 'COMPLETED', result_state: 'COMPLETED' };
  let active: EntryTestView | undefined = mode === 'hydrated' ? operation('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', target) : undefined;
  let entered!: () => void, release!: () => void;
  const admission = new Promise<void>(resolve => { entered = resolve; }), reply = new Promise<void>(resolve => { release = resolve; });
  hook.intercept = async (path, body, method) => {
    if (path === '/api/v1/model-test/entries' && method === 'PUT') {
      active = operation(String(body.operation_id), state.entries.find(item => item.entry_id === body.entry_id)!);
      if (mode === 'pending') { entered(); await reply; }
      return Response.json(active);
    }
    if (path.includes('/entries/latest/')) return path.endsWith(entryId) ? Response.json(old) : active?.entry_id === path.split('/').at(-1) ? Response.json(active) : Response.json({ error: { code: 'NOT_FOUND', correlation_id: entryId } }, { status: 404 });
    if (path === '/api/v1/model-test/entries/' + old.operation_id) return Response.json(old);
    if (active && path.startsWith('/api/v1/model-test/entries/' + active.operation_id)) {
      if (method === 'POST') active = { ...active, state: 'FINISHED', state_revision: 3, result_state: 'NOT_SENT', finish_reason: 'CANCELLED' };
      return Response.json(active);
    }
  };
  mount(); await screen.findByRole('region', { name: 'Configured models' });
  if (mode === 'sequence') {
    await wizard(); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/01' })); await review();
    fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: 'Save & connect' }));
  } else if (mode !== 'hydrated') {
    const test = screen.getByRole('button', { name: 'Test Catalog/00 via OpenRouter' }); await waitFor(() => expect(test).toBeEnabled()); fireEvent.click(test);
    fireEvent.click(screen.getByRole('checkbox'));
    if (mode === 'pending') {
      fireEvent.click(screen.getByRole('button', { name: 'Send model test' })); await admission;
      const history = screen.getByRole('button', { name: 'Read check for Exact/Model' }); await waitFor(() => expect(history).toBeDisabled()); fireEvent.click(history);
      release();
    } else fireEvent.click(screen.getByRole('button', { name: 'Send model test' }));
  } else {
    expect(screen.queryByRole('region', { name: 'Model test operation' })).not.toBeInTheDocument();
    const read = screen.getByRole('button', { name: 'Read check for Catalog/00' }); expect(read).toBeEnabled(); fireEvent.click(read);
  }
  const panel = await screen.findByRole('region', { name: 'Model test operation' });
  await waitFor(() => expect(within(panel).getByRole('button', { name: 'Cancel test' })).toBeEnabled());
  const id = active!.operation_id, before = state.reads.length;
  const history = screen.getByRole('button', { name: 'Read check for Exact/Model' }); fireEvent.click(history);
  fireEvent.click(within(panel).getByRole('button', { name: 'Read test status' }));
  await waitFor(() => expect(panel).toHaveTextContent(`Operation ${id}`));
  expect(history).toBeDisabled(); expect(panel).toHaveTextContent('Catalog/00 · RUNNING');
  const read = screen.getByRole('button', { name: 'Read check for Catalog/00' }); expect(read).toBeEnabled(); fireEvent.click(read);
  await waitFor(() => expect(state.reads.slice(before)).toContain('/api/v1/model-test/entries/' + id));
  expect(state.reads.slice(before)).not.toContain('/api/v1/model-test/entries/' + old.operation_id);
  const cancel = within(panel).getByRole('button', { name: 'Cancel test' }); expect(cancel).toBeEnabled(); fireEvent.click(cancel);
  await waitFor(() => expect(state.writes.filter(item => item.path.endsWith('/cancel'))).toEqual([{ path: `/api/v1/model-test/entries/${id}/cancel`, body: expect.objectContaining({ expected_state_revision: 2 }) }]));
  await waitFor(() => expect(panel).toHaveTextContent('Catalog/00 · FINISHED · NOT_SENT'));
  expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(mode === 'hydrated' ? 0 : 1);
  expect(active!.operation_id).toBe(id); expect(state.keys.selection).toBeNull();
  await waitFor(() => expect(history).toBeEnabled()); fireEvent.click(history);
  await waitFor(() => expect(panel).toHaveTextContent(`Operation ${old.operation_id}`));
  await waitFor(() => expect(panel).toHaveTextContent('Exact/Model · FINISHED · COMPLETED'));
  expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(mode === 'hydrated' ? 0 : 1);
});
it('UNKNOWN entry admission keeps the same operation and cannot start a fresh test on readback', async () => {
  const { state, hook } = settingsBackend(); let id: string | undefined;
  hook.intercept = (path, body, method) => {
    if (path === '/api/v1/model-test/entries' && method === 'PUT') { id = String(body.operation_id); throw new TypeError('SOURCE lost entry reply'); }
    if (path.startsWith('/api/v1/model-test/entries/')) return Response.json(operation(id!, entry));
  };
  mount(); const button = await screen.findByRole('button', { name: 'Test Exact/Model via OpenRouter' }); await waitFor(() => expect(button).toBeEnabled()); fireEvent.click(button); fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: 'Send model test' }));
  await screen.findByText(/Test outcome unconfirmed/); fireEvent.click(screen.getByRole('button', { name: 'Read test status' })); await waitFor(() => expect(state.reads).toContain('/api/v1/model-test/entries/' + id));
  expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(1); expect(screen.getByRole('button', { name: 'Cancel test' })).toBeEnabled();
});
it.each(['RUNNING', 'FINISHED', 'NEEDS_RECONCILIATION'] as const)('keeps %s test identity and recovery visible with diagnostics collapsed', async status => {
  const { state, hook } = settingsBackend(); let view: EntryTestView | undefined;
  hook.intercept = (path, body, method) => {
    if (path === '/api/v1/model-test/entries' && method === 'PUT') {
      view = { ...operation(String(body.operation_id), entry), state: status, result_state: status === 'FINISHED' ? 'COMPLETED' : 'UNKNOWN', response_text: status === 'FINISHED' ? 'OMNIS_MODEL_TEST_OK' : null };
      return Response.json(view);
    }
    if (path.startsWith('/api/v1/model-test/entries/')) return Response.json(view);
  };
  mount(); fireEvent.click(await screen.findByRole('button', { name: 'Test Exact/Model via OpenRouter' }));
  fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: 'Send model test' }));
  const panel = await screen.findByRole('region', { name: 'Model test operation' });
  await waitFor(() => expect(panel).toHaveTextContent(`OpenRouter · Exact/Model · ${status}`));
  const id = within(panel).getByText(`Operation ${view!.operation_id}`);
  const details = within(panel).getByText('Operation details').closest('details');
  expect(details).not.toHaveAttribute('open'); expect(id).not.toBeVisible();
  if (status === 'FINISHED') {
    expect(within(panel).queryByRole('button', { name: 'Cancel test' })).not.toBeInTheDocument();
    expect(within(panel).queryByText(/Cancel does not guarantee/)).not.toBeInTheDocument();
  } else {
    expect(within(panel).getByRole('button', { name: 'Cancel test' })).toBeEnabled();
    expect(within(panel).getByText('Cancel does not guarantee remote cancellation or a refund.')).toBeVisible();
  }
  fireEvent.click(within(panel).getByText('Operation details')); expect(id).toBeVisible();
  if (status === 'FINISHED') expect(within(panel).getByLabelText('Model response')).toHaveTextContent('OMNIS_MODEL_TEST_OK');
  fireEvent.click(within(panel).getByText('Operation details')); expect(id).not.toBeVisible();
  fireEvent.click(within(panel).getByRole('button', { name: 'Read test status' }));
  await waitFor(() => expect(state.reads).toContain('/api/v1/model-test/entries/' + view!.operation_id));
  expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(1);
});
it('catalog lost reply has receive-only recovery after closing its wizard', async () => {
  const { state, hook } = settingsBackend(configured, [], models);
  hook.intercept = (path, _body, method) => { if (path.endsWith('/refresh') && method === 'POST') throw new TypeError('SOURCE lost catalog response'); return undefined; };
  mount(); await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled()); fireEvent.click(screen.getByRole('button', { name: 'Add models' })); fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
  await screen.findByRole('button', { name: 'Read catalog status' }); fireEvent.click(screen.getByRole('button', { name: 'Cancel' })); fireEvent.click(screen.getByRole('button', { name: 'Read catalog status' }));
  await screen.findByText('Catalog READY. No new refresh sent.'); expect(state.writes).toHaveLength(1); expect(state.writes[0]!.body.action).toBe('refresh'); expect(catalogId).not.toBe('');
});
it('explicitly updates a stale saved identity after key rotation instead of duplicating it', async () => {
  const { state } = settingsBackend({ ...configured, connections: configured.connections.map(item => ({ ...item, revision: 2 })) }, [entry]);
  mount(); await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled()); fireEvent.click(screen.getByRole('button', { name: 'Add models' })); fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
  const update = await screen.findByRole('button', { name: 'Update Exact/Model' }); fireEvent.click(update); await review(); fireEvent.click(screen.getByRole('button', { name: 'Save models' }));
  await screen.findByText('Models saved. Assignments stay unchanged.'); expect(state.entries).toHaveLength(1); expect(state.entries[0]).toMatchObject({ entry_id: entry.entry_id, revision: 2, connection_revision: 2, output_tokens: 512 });
});
