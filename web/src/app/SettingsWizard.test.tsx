import { StrictMode } from 'react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, expect, it, onTestFailed, vi } from 'vitest';
import { App } from './App';
import { catalogId, configured, empty, entry, entryId, selected, settingsBackend } from '../../tests/settings-fixtures';
import type { ModelEntry } from '../features/engagement/SettingsModels';
import type { EntryTestView } from '../shared/api/modelTest';
import { ApiError } from '../shared/api/errors';
import { catalogStorage, pendingStorage, remember, sessionScope, testStorage } from '../features/engagement/SettingsModels';
import { session } from '../../tests/fixtures';
const models = Array.from({ length: 32 }, (_, i) => ({ model: `Catalog/${String(i).padStart(2, '0')}`, name: `Model ${i}`, max_output_tokens: 4096, supports_max_tokens: true, reason: null }));
beforeEach(() => { sessionStorage.clear(); });
it('explicit Refresh creates one fresh catalog identity and retains chosen models without any test or assignment', async () => {
  const { state } = settingsBackend(configured, [], models); mount(); const panel = await wizard();
  fireEvent.click(within(panel).getByRole('button', { name: 'Add Catalog/00' }));
  const initial = state.writes[0]!.body.command_id;
  fireEvent.click(within(panel).getByRole('button', { name: 'Refresh' }));
  await waitFor(() => expect(state.writes).toHaveLength(2));
  await waitFor(() => expect(within(panel).getByRole('list', { name: 'Provider models' })).toHaveAttribute('aria-busy', 'false'));
  expect(state.writes.map(write => write.body.action)).toEqual(['refresh', 'refresh']);
  expect(state.writes[1]!.body).toEqual({ action: 'refresh', command_id: expect.any(String), connection_id: entry.connection_id, connection_revision: 1 });
  expect(state.writes[1]!.body.command_id).not.toBe(initial);
  expect(within(panel).getByRole('list', { name: 'Selected models' })).toHaveTextContent('Model 0');
  expect(state.keys).toEqual(configured); expect(state.entries).toEqual([]);
});
it.each(['query', 'manual'] as const)('SOURCE wizard exposes the %s library read barrier instead of silently dropping Save', async mode => {
  const { state, hook } = settingsBackend(configured, [], models);
  const mounted = mount(true), panel = await wizard();
  const queryKey = ['private', 'settings-model-library'];
  await waitFor(() => expect(mounted.client.isFetching({ queryKey })).toBe(0));
  fireEvent.click(within(panel).getByRole('button', { name: 'Add Catalog/00' })); await review();
  const save = within(panel).getByRole('button', { name: 'Save models' });
  const connect = within(panel).getByRole('button', { name: 'Save & connect' });
  expect(connect).toBeDisabled(); fireEvent.click(connect);
  expect(state.writes.map(write => write.body.action)).toEqual(['refresh']);
  fireEvent.click(within(panel).getByRole('checkbox'));
  expect(connect).toBeEnabled();
  let held = false, release = () => {};
  const gate = new Promise<void>(resolve => { release = resolve; });
  hook.intercept = async (path, _body, method) => {
    if (path === '/api/v1/settings/models' && method === 'GET') { held = true; await gate; }
    return undefined;
  };
  try {
    // Hold the existing local read after Refresh, without delaying or changing the catalog.
    if (mode === 'query') void mounted.client.invalidateQueries({ queryKey });
    else fireEvent.click(screen.getByRole('button', { name: 'Reload current settings' }));
    await waitFor(() => expect(held).toBe(true));
    expect(mounted.client.isFetching({ queryKey })).toBe(mode === 'query' ? 1 : 0);
    connect.focus();
    await act(async () => { fireEvent.click(connect); fireEvent.click(save); });
    expect(state.writes.map(write => write.body.action)).toEqual(['refresh']);
    expect(state.entries).toEqual([]); expect(state.keys).toEqual(configured);
    expect(within(panel).getByRole('checkbox')).toBeChecked(); expect(connect).toHaveFocus();
    expect(connect).toHaveAttribute('aria-disabled', 'true');
    expect(connect).toHaveAttribute('aria-busy', 'true');
    expect(save).toHaveAttribute('aria-disabled', 'true');
    expect(save).toHaveAttribute('aria-busy', 'true');
    expect(connect).toBeEnabled(); expect(save).toBeEnabled();
    release();
    await waitFor(() => expect(connect).toHaveAttribute('aria-busy', 'false'));
    expect(connect).toHaveFocus(); expect(within(panel).getByRole('checkbox')).toBeChecked();
    expect(state.writes.map(write => write.body.action)).toEqual(['refresh']);
    expect(state.entries).toEqual([]);
    fireEvent.click(save); await screen.findByText('Models saved.');
    expect(state.writes.map(write => write.body.action)).toEqual(['refresh', 'save_models']);
    expect(state.entries).toEqual([expect.objectContaining({ model: 'Catalog/00', revision: 1, output_tokens: 128 })]);
    expect(state.keys).toEqual(configured);
    expect(screen.queryByRole('region', { name: 'Add models wizard' })).not.toBeInTheDocument();
  } finally { release(); mounted.unmount(); mounted.client.clear(); }
});
it.each(['query', 'manual', 'refresh'] as const)('SOURCE Add controls retain selection and manual input during %s work', async mode => {
  const { state, hook } = settingsBackend(configured, [], models);
  const mounted = mount(true), panel = await wizard(), user = userEvent.setup();
  const queryKey = ['private', 'settings-model-library'];
  const next = within(panel).getByRole('button', { name: 'Continue' });
  await waitFor(() => expect(next).toHaveAttribute('aria-busy', 'false'));
  fireEvent.click(within(panel).getByText('Enter a model ID'));
  const manual = within(panel).getByRole('textbox', { name: 'Exact model ID' });
  fireEvent.change(manual, { target: { value: 'manual/preview' } });
  const catalogAdd = within(panel).getByRole('button', { name: 'Add Catalog/00' });
  const manualAdd = within(panel).getByRole('button', { name: 'Add model ID' });
  const chips = within(panel).getByRole('list', { name: 'Selected models' });
  let held = false, release = () => {};
  const gate = new Promise<void>(resolve => { release = resolve; });
  hook.intercept = async (path, _body, method) => {
    if (mode === 'refresh' ? path.endsWith('/provider-catalog/refresh') : path === '/api/v1/settings/models' && method === 'GET') { held = true; await gate; }
    return undefined;
  };
  try {
    if (mode === 'query') void mounted.client.invalidateQueries({ queryKey });
    else fireEvent.click(mode === 'manual' ? screen.getByRole('button', { name: 'Reload current settings' }) : within(panel).getByRole('button', { name: 'Refresh' }));
    await waitFor(() => expect(held).toBe(true));
    await waitFor(() => expect(next).toHaveAttribute('aria-busy', 'true'));
    if (mode !== 'refresh') expect(within(panel).getByRole('list', { name: 'Provider models' })).toHaveAttribute('aria-busy', 'false');
    for (const button of [catalogAdd, manualAdd]) {
      expect(button).toBeEnabled(); // Transient blocking must not remove keyboard focus.
      expect.soft(button).toHaveAttribute('aria-disabled', 'true');
      expect.soft(button).toHaveAttribute('aria-busy', 'true');
    }
    catalogAdd.focus(); await user.keyboard('{Enter}');
    expect(catalogAdd).toHaveFocus(); expect(within(chips).queryAllByRole('listitem')).toHaveLength(0);
    manual.focus(); await user.tab(); expect(manualAdd).toHaveFocus(); await user.keyboard(' ');
    expect(manualAdd).toHaveFocus();
    expect.soft(manual).toHaveValue('manual/preview');
    expect(within(chips).queryAllByRole('listitem')).toHaveLength(0); expect(next).toBeDisabled();
    const actions = mode === 'refresh' ? ['refresh', 'refresh'] : ['refresh'];
    expect(state.writes.map(write => write.body.action)).toEqual(actions);
    release();
    await waitFor(() => expect(next).toHaveAttribute('aria-busy', 'false'));
    expect(manualAdd).toHaveFocus(); expect.soft(manual).toHaveValue('manual/preview');
    expect(within(chips).queryAllByRole('listitem')).toHaveLength(0); expect(next).toBeDisabled();
    await waitFor(() => expect(within(panel).getByRole('list', { name: 'Provider models' })).toHaveAttribute('aria-busy', 'false'));
    const settledAdd = within(panel).getByRole('button', { name: 'Add Catalog/00' });
    for (const button of [settledAdd, manualAdd]) {
      expect.soft(button).toHaveAttribute('aria-disabled', 'false');
      expect.soft(button).toHaveAttribute('aria-busy', 'false');
    }
    fireEvent.click(settledAdd);
    expect(within(chips).getByRole('button', { name: 'Remove selected Catalog/00' })).toBeVisible();
    await user.keyboard('{Enter}');
    expect.soft(within(chips).queryByRole('button', { name: 'Remove selected manual/preview' })).toBeInTheDocument();
    expect.soft(within(chips).queryAllByRole('listitem')).toHaveLength(2); expect(manual).toHaveValue('');
    expect(state.entries).toEqual([]); expect(state.keys).toEqual(configured);
    expect(state.writes.map(write => write.body.action)).toEqual(actions);
    await review();
    expect(within(panel).getByRole('button', { name: 'Save models' })).toBeEnabled();
    expect.soft(within(panel).queryByText('UNVERIFIED — manual model ID')).toBeVisible();
    expect(within(panel).getByRole('button', { name: 'Save & connect' })).toBeDisabled();
  } finally { release(); mounted.unmount(); mounted.client.clear(); }
});
it.each(['selected', 'configured', 'full'] as const)('SOURCE manual Add retains the exact input when %s admission is refused', async refusal => {
  const entries = refusal === 'configured' ? [entry] : refusal === 'full' ? Array.from({ length: 64 }, (_, index) => ({ ...entry, entry_id: `22222222-2222-4222-8222-${String(index).padStart(12, '0')}`, model: `saved/${index}` })) : [];
  const { state } = settingsBackend(configured, entries, models);
  const mounted = mount(), panel = await wizard();
  try {
    await waitFor(() => expect(within(panel).getByRole('button', { name: 'Continue' })).toHaveAttribute('aria-busy', 'false'));
    if (refusal === 'selected') fireEvent.click(within(panel).getByRole('button', { name: 'Add Catalog/00' }));
    fireEvent.click(within(panel).getByText('Enter a model ID'));
    const manual = within(panel).getByRole('textbox', { name: 'Exact model ID' });
    const value = refusal === 'configured' ? entry.model : 'Catalog/00';
    fireEvent.change(manual, { target: { value } });
    fireEvent.click(within(panel).getByRole('button', { name: 'Add model ID' }));
    expect(manual).toHaveValue(value);
    expect(within(within(panel).getByRole('list', { name: 'Selected models' })).queryAllByRole('listitem')).toHaveLength(refusal === 'selected' ? 1 : 0);
    if (refusal === 'full') expect(within(panel).getByRole('alert')).toHaveTextContent('The instance is limited to 64 configured models.');
    expect(state.entries).toEqual(entries); expect(state.keys).toEqual(configured);
    expect(state.writes.map(write => write.body.action)).toEqual(['refresh']);
  } finally { mounted.unmount(); mounted.client.clear(); }
});
it('Cancel catalog targets its retained connection revision and persists a stopped readback without resending Refresh', async () => {
  const { state, hook } = settingsBackend(); let cancelled = false;
  const scope = await sessionScope(session.csrf_token);
  remember(catalogStorage, scope, { id: catalogId, connection: entry.connection_id, revision: 1 });
  hook.intercept = (path, body) => {
    if (path.endsWith('/cancel')) cancelled = true;
    if (!path.endsWith('/cancel') && !path.endsWith('/search')) return;
    return Response.json({ schema_version: 1, connection_id: body.connection_id, connection_revision: body.connection_revision, provider: 'openrouter', catalog_command_id: body.catalog_command_id ?? catalogId, state: cancelled ? 'FAILED' : 'PENDING', reason: cancelled ? 'CANCELLED_OR_STOPPED' : null, query: body.query ?? '', offset: 0, next_offset: null, total: 0, entries: [] });
  };
  const mounted = mount();
  await screen.findByRole('region', { name: 'Configured models' });
  const recovery = await screen.findByRole('region', { name: 'Catalog recovery' });
  fireEvent.click(within(recovery).getByRole('button', { name: 'Cancel catalog' }));
  await waitFor(() => expect(sessionStorage.getItem(catalogStorage)).toBeNull());
  expect(state.writes).toEqual([{ path: '/api/v1/settings/provider-catalog/cancel', body: { action: 'cancel', command_id: expect.any(String), catalog_command_id: catalogId, connection_id: entry.connection_id, connection_revision: 1 } }]);
  fireEvent.click(within(recovery).getByText('Catalog details'));
  expect(await within(recovery).findByText('FAILED · CANCELLED_OR_STOPPED')).toBeVisible();
  mounted.unmount(); mount(); await screen.findByText('The model catalog is unavailable. Saved test results are unchanged. Open Add models to refresh it explicitly.');
  fireEvent.click(within(screen.getByRole('region', { name: 'Configured models' })).getByText('Catalog details'));
  expect(screen.getByText(/FAILED · CANCELLED_OR_STOPPED/)).toBeVisible();
  expect(state.writes).toHaveLength(1); expect(state.entries).toEqual([entry]); expect(state.keys).toEqual(configured);
});
it('orphan RUNNING Cancel uses the latest read revision, never the historical operation', async () => {
  const orphan = { ...entry, entry_id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', model: 'Orphan/Model' };
  let active = operation('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', orphan);
  const old = { ...operation('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', entry), state: 'FINISHED', state_revision: 3, result_state: 'COMPLETED', finish_reason: 'COMPLETED' };
  const { state, hook } = settingsBackend();
  hook.intercept = (path, body, method) => {
    if (path.includes('/entries/latest/') && path.endsWith(entryId)) return Response.json(old);
    if (path.includes(active.operation_id!)) {
      if (method === 'POST') { expect(body.expected_state_revision).toBe(7); active = { ...active, state: 'FINISHED', state_revision: 8, result_state: 'NOT_SENT', finish_reason: 'CANCELLED' }; }
      return Response.json(active);
    }
    if (path.endsWith(orphan.entry_id)) return Response.json(active);
  };
  const scope = await sessionScope(session.csrf_token); remember(testStorage, scope, active.operation_id!);
  const mounted = mount();
  const recovery = await screen.findByRole('region', { name: 'Unconfirmed model check' });
  active = { ...active, state_revision: 7 };
  fireEvent.click(within(recovery).getByRole('button', { name: 'Read test status' }));
  await waitFor(() => expect(mounted.client.getQueryData(['private', 'settings-entry-test', scope, active.operation_id])).toMatchObject({ state_revision: 7 }));
  fireEvent.click(within(recovery).getByRole('button', { name: 'Cancel test' }));
  await waitFor(() => expect(mounted.client.getQueryData(['private', 'settings-entry-test', scope, active.operation_id])).toMatchObject({ state: 'FINISHED', state_revision: 8 }));
  expect(state.writes).toEqual([{ path: `/api/v1/model-test/entries/${active.operation_id}/cancel`, body: { command_id: expect.any(String), expected_state_revision: 7 } }]);
  mounted.unmount(); mount(); await screen.findByRole('region', { name: 'Configured models' });
  expect(state.writes).toHaveLength(1);
});
it('SOURCE missing local projection still exposes orphan Stop and abandons the unsent sequence', async () => {
  const { state, hook } = settingsBackend(configured, [], models);
  let active: EntryTestView | undefined, release = () => {};
  const gate = new Promise<void>(resolve => { release = resolve; });
  hook.intercept = async (path, body, method) => {
    if (path === '/api/v1/model-test/entries' && method === 'PUT') {
      active = operation(String(body.operation_id), state.entries.find(item => item.entry_id === body.entry_id)!); await gate; return Response.json(active);
    }
    if (path.includes('/model-test/entries/') && active) return Response.json(active);
  };
  const mounted = mount();
  try {
    await wizard(); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/01' })); await review();
    fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: 'Save & connect' }));
    await waitFor(() => expect(active).toBeDefined());
    const query = mounted.client.getQueryCache().findAll({ queryKey: ['private', 'settings-model-library'] })[0]!;
    // Controlled SOURCE projection fault, not a claim that the API removed a running entry.
    await act(async () => { mounted.client.setQueryData(query.queryKey, (value: { library: { revision: number; entries: ModelEntry[] } }) => ({ ...value, library: { ...value.library, entries: [] } })); });
    const recovery = await screen.findByRole('region', { name: 'Unconfirmed model check' });
    fireEvent.click(within(recovery).getByRole('button', { name: 'Stop remaining checks' }));
    expect(within(recovery).getByText('Remaining checks stopped. Read the admitted check.')).toBeVisible();
    active = { ...active!, state: 'FINISHED', state_revision: 3, result_state: 'COMPLETED', finish_reason: 'COMPLETED' };
    await act(async () => { release(); await gate; });
    const scope = await sessionScope(session.csrf_token);
    await waitFor(() => expect(mounted.client.getQueryData(['private', 'settings-entry-test', scope, active!.operation_id])).toMatchObject({ state: 'FINISHED' }));
    expect(state.writes.map(write => write.body.action ?? write.path)).toEqual(['refresh', 'save_models', '/api/v1/model-test/entries']);
    mounted.unmount(); mount(); await screen.findByRole('region', { name: 'Configured models' });
    expect(state.writes.map(write => write.body.action ?? write.path)).toEqual(['refresh', 'save_models', '/api/v1/model-test/entries']);
  } finally { release(); }
});
function mount(strict = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, networkMode: 'always' } } });
  const app = <QueryClientProvider client={client}><MemoryRouter initialEntries={['/settings/providers']}><App /></MemoryRouter></QueryClientProvider>;
  return { ...render(strict ? <StrictMode>{app}</StrictMode> : app), client };
}
async function wizard() { await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled()); fireEvent.click(screen.getByRole('button', { name: 'Add models' })); fireEvent.click(screen.getByRole('button', { name: 'Continue' })); await screen.findByLabelText('Search models'); await screen.findByRole('button', { name: 'Add Catalog/00' }); return screen.getByRole('region', { name: 'Add models wizard' }); }
async function review() { const button = screen.getByRole('button', { name: 'Continue' }); await waitFor(() => expect(button).not.toHaveAttribute('aria-disabled', 'true')); fireEvent.click(button); return screen.findByRole('button', { name: 'Save models' }); }
const modelRow = (model: string) => screen.getByRole('listitem', { name: `Model ${model} via OpenRouter` });
function operation(id: string, target: ModelEntry): EntryTestView { return {
  schema_version: 2, operation_id: id, state: 'RUNNING', state_revision: 2, finish_reason: null, selection_revision: null,
  metadata_command_id: null, metadata_state: 'NOT_REQUESTED', reason: null, requested_provider: 'openrouter', requested_model: target.model, requested_output_tokens: target.output_tokens,
  observed_model: null, provider_status: null, result_state: null, output_state: 'ABSENT', response_text: null, usage_state: 'UNKNOWN', input_tokens: null, output_tokens: null, reasoning_tokens: null, cost_observed: null,
  system_message: 'Respond only with OMNIS_MODEL_TEST_OK. Use no tools.', user_message: 'This is a synthetic local settings test. Reply with OMNIS_MODEL_TEST_OK.', calls_limit: 1, wall_seconds: 300,
  entry_id: target.entry_id, entry_revision: target.revision, connection_id: target.connection_id, connection_revision: target.connection_revision, current: true,
}; }
it.each(['known', 'unknown', 'partial-zero'] as const)('expands a minimal %s usage capsule with native keyboard and no repeated success or diagnostics', async usage => {
  const user = userEvent.setup();
  const { state, hook } = settingsBackend();
  const saved = { ...operation('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', entry), state: 'FINISHED', finish_reason: 'COMPLETED', result_state: 'COMPLETED', response_text: 'OMNIS_MODEL_TEST_OK', observed_model: entry.model, usage_state: usage === 'known' ? 'KNOWN' : usage === 'unknown' ? 'UNKNOWN' : 'PARTIAL', input_tokens: usage === 'known' ? 12 : usage === 'partial-zero' ? 0 : null, output_tokens: usage === 'known' ? 7 : null, reasoning_tokens: 0, cost_observed: usage === 'known' ? '0.001' : null };
  hook.intercept = path => path.includes('/entries/latest/') ? Response.json(saved) : undefined;
  const { client } = mount();
  if (usage === 'known') onTestFailed(() => {
    console.error('SETTINGS_KNOWN_BOUNDARY ' + JSON.stringify({
      queries: client.getQueryCache().getAll().slice(0, 8).map(({ state }) => ({ status: state.status, fetchStatus: state.fetchStatus, error: state.error !== null })),
      lastPath: state.reads.at(-1)?.replace(/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}/g, ':id').split('?')[0]?.slice(0, 180) ?? null,
      phase: screen.queryByRole('region', { name: 'Configured models' }) ? 'library' : screen.queryByRole('button', { name: 'Add models' }) ? 'settings' : 'bootstrap',
    }));
  });
  const toggle = await screen.findByRole('button', { name: 'Details for Exact/Model via OpenRouter' });
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  const details = document.getElementById(toggle.getAttribute('aria-controls')!)!;
  expect(details).not.toBeVisible();
  expect(screen.queryByRole('region', { name: 'Model test operation' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Read check/ })).not.toBeInTheDocument();
  const reads = [...state.reads];
  toggle.focus(); await user.keyboard('{Enter}');
  expect(toggle).toHaveFocus(); expect(toggle).toHaveAttribute('aria-expanded', 'true');
  expect(details).toBeVisible();
  const metrics = within(details).getByLabelText('Test usage');
  expect(within(metrics).getAllByRole('term').map(node => node.textContent)).toEqual(['Input tokens', 'Output tokens', 'Cost']);
  expect(within(metrics).getAllByRole('definition').map(node => node.textContent)).toEqual(usage === 'known' ? ['12', '7', '0.001'] : usage === 'unknown' ? ['Unknown', 'Unknown', 'Unknown'] : ['0', 'Unknown', 'Unknown']);
  expect(details).not.toHaveTextContent(/Test completed|Requested model|Observed model|OMNIS_MODEL_TEST_OK|FINISHED|COMPLETED|revision|\$|€/);
  expect(modelRow(entry.model)).not.toHaveTextContent(saved.operation_id!);
  expect(screen.queryByText('Operation details')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Model response')).not.toBeInTheDocument();
  expect(within(modelRow(entry.model)).queryByRole('button', { name: 'Read test status' })).not.toBeInTheDocument();
  if (usage === 'partial-zero') expect(screen.getByText('Usage is incomplete.')).toBeVisible();
  await user.keyboard(' '); expect(toggle).toHaveAttribute('aria-expanded', 'false');
  expect(state.reads).toEqual(reads); expect(state.writes).toEqual([]);
  await user.tab(); expect(screen.getByRole('button', { name: 'Test Exact/Model via OpenRouter' })).toHaveFocus();
  await user.keyboard('{Enter}'); expect(screen.getByRole('region', { name: 'Test consent' })).toBeVisible();
  expect(toggle).toHaveAttribute('aria-expanded', 'false'); expect(state.writes).toEqual([]);
});
it.each(['failed', 'incomplete', 'mismatch', 'stale', 'truncated'] as const)('keeps actionable %s context visible with usage closed', async kind => {
  const { state, hook } = settingsBackend();
  const saved: EntryTestView = { ...operation('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', entry), state: 'FINISHED', result_state: kind === 'failed' ? 'FAILED' : kind === 'incomplete' ? 'INCOMPLETE' : 'COMPLETED', finish_reason: kind === 'failed' || kind === 'incomplete' ? 'FAILED' : 'COMPLETED', current: kind !== 'stale', observed_model: kind === 'mismatch' ? '<different/model>' : entry.model, output_state: kind === 'truncated' || kind === 'incomplete' ? 'TRUNCATED' : 'COMPLETE' };
  hook.intercept = path => path.includes('/entries/latest/') ? Response.json(saved) : path.endsWith(saved.operation_id!) ? Response.json(saved) : undefined;
  mount();
  const row = await screen.findByRole('listitem', { name: 'Model Exact/Model via OpenRouter' });
  const toggle = within(row).getByRole('button', { name: 'Details for Exact/Model via OpenRouter' });
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  expect(document.getElementById(toggle.getAttribute('aria-controls')!)).not.toBeVisible();
  const context = kind === 'failed' ? 'Test did not complete successfully. Read the saved result before testing again.' : kind === 'incomplete' ? 'Test incomplete. Read the saved result before testing again.' : kind === 'mismatch' ? /Model mismatch/ : kind === 'stale' ? 'This saved result does not match the current model settings.' : 'Response truncated.';
  expect(within(row).getByText(context)).toBeVisible();
  expect(row).not.toHaveTextContent(saved.operation_id!);
  if (kind === 'mismatch') { expect(within(row).getByText(/Model mismatch/)).toHaveTextContent('Requested: Exact/Model · OpenRouter. Observed: <different/model>.'); expect(row.querySelector('different')).toBeNull(); }
  fireEvent.click(toggle);
  if (kind !== 'truncated') {
    const before = state.reads.length;
    fireEvent.click(within(row).getByRole('button', { name: 'Read test status' }));
    await waitFor(() => expect(state.reads.slice(before)).toContain('/api/v1/model-test/entries/' + saved.operation_id));
  }
  expect(state.writes).toEqual([]);
});
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
it('marks prior Connected state unconfirmed after a settings read fails without a duplicate notification', async () => {
  const { hook } = settingsBackend(); let failed = false;
  hook.intercept = path => {
    if (path === '/api/v1/settings/providers' && failed) return Response.json({ error: { code: 'CONTROL_UNAVAILABLE', correlation_id: entryId } }, { status: 503 });
    if (path.includes('/entries/latest/')) return Response.json({ ...operation(crypto.randomUUID(), entry), state: 'FINISHED', finish_reason: 'COMPLETED', result_state: 'COMPLETED' });
  };
  mount(); await screen.findByText('Connected'); failed = true; fireEvent.click(screen.getByRole('button', { name: 'Reload current settings' }));
  await screen.findByText('Unconfirmed — reload settings');
  expect(screen.queryByRole('complementary', { name: 'Settings notification' })).not.toBeInTheDocument();
  expect(screen.getByRole('region', { name: 'Settings recovery' })).toBeVisible();
  expect(screen.getByText('Unconfirmed — reload settings')).toBeVisible(); expect(screen.queryByText('Connected')).not.toBeInTheDocument();
});
it('keeps a saved successful test distinct from a failed current catalog and preserves assignments', async () => {
  const keys = { ...configured, selection: { selection_id: entryId, revision: 7, default: selected, brain: { ...selected, output_tokens: 37 }, investigator: null, validator: null } };
  const { state, hook } = settingsBackend(keys);
  hook.intercept = (path, body) => {
    if (path.includes('/entries/latest/')) return Response.json({ ...operation('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', entry), state: 'FINISHED', finish_reason: 'COMPLETED', result_state: 'COMPLETED' });
    if (path.endsWith('/search')) return Response.json({ schema_version: 1, connection_id: entry.connection_id, connection_revision: 1, provider: 'openrouter', catalog_command_id: catalogId, state: 'FAILED', reason: 'METADATA_UNAVAILABLE', query: body.query, offset: 0, next_offset: null, total: 0, entries: [] });
  };
  mount();
  const list = await screen.findByRole('region', { name: 'Configured models' });
  expect(within(list).getByText('Test passed · catalog unavailable')).toBeVisible();
  expect(within(list).queryByText('Connected', { exact: true })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Test Exact/Model via OpenRouter' })).toBeDisabled();
  expect(screen.getByLabelText('Default model')).toHaveDisplayValue('Exact/Model · OpenRouter · Catalog unavailable');
  expect(screen.getByRole('button', { name: 'Save assignments' })).toBeDisabled();
  expect(within(list).getByText('The model catalog is unavailable. Saved test results are unchanged. Open Add models to refresh it explicitly.')).toBeVisible();
  const details = within(list).getByText('Catalog details').closest('details');
  expect(details).not.toHaveAttribute('open');
  expect(within(list).getByText(/FAILED · METADATA_UNAVAILABLE/)).not.toBeVisible();
  fireEvent.click(within(list).getByText('Catalog details'));
  expect(within(list).getByText(/FAILED · METADATA_UNAVAILABLE/)).toBeVisible();
  expect(details).toHaveTextContent(catalogId);
  expect(details).toHaveTextContent('connection revision 1');
  fireEvent.click(within(list).getByText('Catalog details'));
  expect(details).not.toHaveAttribute('open');
  expect(within(list).getByText(/FAILED · METADATA_UNAVAILABLE/)).not.toBeVisible();
  expect(state.writes).toEqual([]);
  expect(state.keys).toEqual(keys);
});
it.each([
  ['NOT_REQUESTED', null, 'Catalog not loaded'],
  ['PENDING', null, 'Catalog loading'],
  ['STALE', 'CONNECTION_STALE', 'Catalog stale'],
  ['PARTIAL', 'CATALOG_LIMIT', 'Model details unavailable'],
  ['READY', null, 'Model details unavailable'],
  ['read-error', null, 'Catalog read unconfirmed'],
  ['invalid-response', null, 'Catalog read unconfirmed'],
  ['missing-capability', null, 'Output capability unconfirmed'],
  ['unsupported-cap', null, 'Output cap unsupported'],
] as const)('explains assignment gating for %s without invalidating a saved test or sending effects', async (status, reason, issue) => {
  const keys = { ...configured, selection: { selection_id: entryId, revision: 1, default: selected, brain: null, investigator: null, validator: null } };
  const { state, hook } = settingsBackend(keys);
  hook.intercept = (path, body) => {
    if (path.includes('/entries/latest/')) return Response.json({ ...operation('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', entry), state: 'FINISHED', finish_reason: 'COMPLETED', result_state: 'COMPLETED' });
    if (!path.endsWith('/search')) return;
    if (status === 'read-error') return Response.json({ error: { code: 'CONTROL_UNAVAILABLE', correlation_id: entryId } }, { status: 503 });
    if (status === 'invalid-response') return Response.json({ incompatible: true });
    const entries = status === 'missing-capability' || status === 'unsupported-cap' ? [{ model: entry.model, name: 'Exact model', max_output_tokens: status === 'unsupported-cap' ? 128 : null, supports_max_tokens: status === 'unsupported-cap' ? true : null, reason: null }] : [];
    return Response.json({ schema_version: 1, connection_id: entry.connection_id, connection_revision: 1, provider: 'openrouter', catalog_command_id: status === 'NOT_REQUESTED' ? null : catalogId, state: entries.length ? 'READY' : status, reason, query: body.query, offset: 0, next_offset: null, total: entries.length, entries });
  };
  mount(); const list = await screen.findByRole('region', { name: 'Configured models' });
  expect(within(list).getByText(`Test passed · ${issue.toLowerCase()}`)).toBeVisible();
  expect(screen.getByLabelText('Default model')).toHaveDisplayValue(`Exact/Model · OpenRouter · ${issue}`);
  expect(screen.getByRole('button', { name: 'Test Exact/Model via OpenRouter' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Save assignments' })).toBeDisabled();
  if (status === 'read-error' || status === 'invalid-response') {
    expect(within(list).getByText('Model details could not be read. Reload settings to try the local read again.')).toBeVisible();
    fireEvent.click(within(list).getByText('Catalog details'));
    expect(list).toHaveTextContent(status === 'read-error' ? 'CONTROL_UNAVAILABLE' : 'INVALID_RESPONSE');
  }
  expect(state.writes).toEqual([]); expect(state.keys).toEqual(keys);
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
  await screen.findByText('Models saved.');
  expect(state.writes.map(item => item.body.action)).toEqual(['save_connection', 'refresh', 'save_models']);
  expect(state.entries[0]!.model).toBe('Catalog/00'); expect(state.keys.selection).toBeNull();
});
it('searches cached pages only, preserves chips across Back and saves several exact models without touching Default', async () => {
  const keys = { ...configured, selection: { selection_id: entryId, revision: 1, default: selected, brain: { ...selected, output_tokens: 37 }, investigator: null, validator: null } };
  const { state, hook } = settingsBackend(keys, [entry], [...models, { ...models[0]!, model: entry.model }]);
  const searches: Record<string, unknown>[] = [];
  hook.intercept = (path, body) => { if (path.endsWith('/search')) searches.push(body); return undefined; };
  mount(); const panel = await wizard();
  expect(screen.getByRole('button', { name: 'Previous results' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' }));
  fireEvent.click(screen.getByRole('button', { name: 'Next results' })); await screen.findByRole('button', { name: 'Add Catalog/16' }); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/16' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Previous results' })).toBeEnabled());
  const beforePrevious = searches.length;
  fireEvent.click(screen.getByRole('button', { name: 'Previous results' }));
  await screen.findByRole('button', { name: 'Selected Catalog/00' });
  await waitFor(() => expect(searches.slice(beforePrevious)).toContainEqual({ action: 'search', connection_id: entry.connection_id, connection_revision: 1, catalog_command_id: state.writes[0]!.body.command_id, query: '', offset: 0 }));
  expect(searches).toContainEqual(expect.objectContaining({ query: '', offset: 16 }));
  expect(screen.getByRole('button', { name: 'Previous results' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Search models'), { target: { value: 'Catalog/31' } }); await screen.findByRole('button', { name: 'Add Catalog/31' });
  expect(state.writes).toHaveLength(1); await review(); expect(screen.getByText('Default and role overrides stay unchanged.')).toBeVisible();
  fireEvent.click(within(panel).getByRole('button', { name: 'Back' })); expect(within(panel).getByRole('list', { name: 'Selected models' })).toHaveTextContent('Model 0'); expect(within(panel).getByRole('list', { name: 'Selected models' })).toHaveTextContent('Model 16');
  await review(); fireEvent.click(screen.getByRole('button', { name: 'Save models' })); await screen.findByText('Models saved.');
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
it.each([1, 2])('review keeps exact %s-model context, concise approval and closed output controls', async count => {
  const { state } = settingsBackend(configured, [], models); mount(); const panel = await wizard();
  fireEvent.click(within(panel).getByRole('button', { name: 'Add Catalog/00' }));
  if (count === 2) fireEvent.click(within(panel).getByRole('button', { name: 'Add Catalog/01' }));
  await review();
  expect(within(panel).getAllByText('Not tested', { exact: true })).toHaveLength(count);
  expect(within(panel).getByText('Catalog/00', { selector: 'small', exact: true })).toBeVisible();
  expect(within(panel).getByText('OpenRouter · Saved key', { exact: true })).toBeVisible();
  expect(within(panel).getByText('Output controls').closest('details')).not.toHaveAttribute('open');
  expect(within(panel).getByLabelText('Catalog/00 output tokens')).not.toBeVisible();
  expect(within(panel).getByRole('checkbox', { name: count === 1 ? 'I approve using this model.' : 'I approve using these models.' })).not.toBeChecked();
  expect(within(panel).getByText('Provider charges may apply.', { exact: true })).toBeVisible();
  expect(panel).not.toHaveTextContent(/Fixed input|300 seconds|no tools|refund|OMNIS_MODEL_TEST_OK/);
  expect(within(panel).getByRole('button', { name: 'Save & connect' })).toBeDisabled();
  expect(state.writes.map(item => item.body.action)).toEqual(['refresh']);
});
it('resets approval on output and model changes and Save models stays local even when approved', async () => {
  const { state } = settingsBackend(configured, [], models); mount(); const panel = await wizard();
  fireEvent.click(within(panel).getByRole('button', { name: 'Add Catalog/00' })); await review();
  fireEvent.click(within(panel).getByRole('checkbox')); fireEvent.click(within(panel).getByText('Output controls'));
  fireEvent.change(within(panel).getByLabelText('Catalog/00 output tokens'), { target: { value: '64' } });
  expect(within(panel).getByRole('checkbox')).not.toBeChecked();
  fireEvent.click(within(panel).getByRole('checkbox')); fireEvent.click(within(panel).getByRole('button', { name: 'Back' }));
  fireEvent.click(within(panel).getByRole('button', { name: 'Add Catalog/01' })); await review();
  const consent = within(panel).getByRole('checkbox', { name: 'I approve using these models.' });
  expect(consent).not.toBeChecked(); fireEvent.click(consent);
  fireEvent.click(within(panel).getByRole('button', { name: 'Save models' })); await screen.findByText('Models saved.');
  expect(state.writes.map(item => item.body.action)).toEqual(['refresh', 'save_models']);
  expect(state.entries.map(item => item.output_tokens)).toEqual([64, 128]);
});
it('manual 256-character exact ID saves UNVERIFIED and cannot acquire test consent', async () => {
  const { state } = settingsBackend(configured, [], models); mount(); await wizard(); const id = 'M'.repeat(256);
  fireEvent.click(screen.getByText('Enter a model ID')); fireEvent.change(screen.getByLabelText('Exact model ID'), { target: { value: id } }); fireEvent.click(screen.getByRole('button', { name: 'Add model ID' })); await review();
  expect(screen.getByRole('button', { name: 'Save & connect' })).toBeDisabled(); expect(screen.getByText('UNVERIFIED — manual model ID')).toBeVisible(); fireEvent.click(screen.getByRole('button', { name: 'Save models' }));
  await screen.findByText('Models saved.'); expect(state.entries[0]!.model).toBe(id); expect(state.keys.selection).toBeNull(); expect(screen.queryByText(/All roles use/)).not.toBeInTheDocument();
});
it.each([0, 1.5, 65537])('invalid output cap %s cannot authorize Save & connect or send a registry write', async tokens => {
  const { state } = settingsBackend(configured, [], models); mount(); await wizard();
  fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); await review();
  fireEvent.click(screen.getByText('Output controls', { exact: true }));
  fireEvent.change(screen.getByLabelText('Catalog/00 output tokens'), { target: { value: tokens } });
  expect(screen.getByRole('checkbox', { name: /I approve using (this model|these models)\./ })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Save & connect' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Save models' })).toBeDisabled();
  expect(state.writes.map(item => item.body.action)).toEqual(['refresh']);
});
it('provider switch confirmation retains pending choices when refused', async () => {
  settingsBackend(configured, [], models); mount(); const panel = await wizard(); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); fireEvent.click(within(panel).getByRole('button', { name: 'Back' }));
  fireEvent.change(screen.getByLabelText('Provider'), { target: { value: 'orcarouter' } }); expect(screen.getByLabelText('Provider')).toHaveValue('openrouter');
  const confirmation = within(panel).getByRole('region', { name: 'Provider change confirmation' });
  expect(confirmation).toHaveTextContent('OpenRouter → OrcaRouter'); expect(confirmation).toHaveTextContent('Catalog/00');
  const cancel = within(confirmation).getByRole('button', { name: 'Cancel' }); cancel.focus(); fireEvent.click(cancel);
  expect(screen.getByLabelText('Provider')).toHaveFocus();
  fireEvent.click(screen.getByRole('button', { name: 'Continue' })); await screen.findByLabelText('Search models'); expect(screen.getByRole('list', { name: 'Selected models' })).toHaveTextContent('Model 0');
});
it('cancels provider discard with Escape and only explicit confirmation wipes choices and the unsent key', async () => {
  const { state } = settingsBackend(configured, [], models); mount(); const panel = await wizard();
  fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); fireEvent.click(within(panel).getByRole('button', { name: 'Back' }));
  const provider = screen.getByLabelText('Provider');
  fireEvent.change(provider, { target: { value: 'orcarouter' } });
  const cancel = within(screen.getByRole('region', { name: 'Provider change confirmation' })).getByRole('button', { name: 'Cancel' });
  cancel.focus(); fireEvent.keyDown(cancel, { key: 'Escape' }); expect(provider).toHaveFocus(); expect(provider).toHaveValue('openrouter');
  fireEvent.change(provider, { target: { value: 'orcarouter' } });
  fireEvent.click(within(screen.getByRole('region', { name: 'Provider change confirmation' })).getByRole('button', { name: 'Change provider' }));
  expect(provider).toHaveValue('orcarouter');
  const key = screen.getByLabelText('API key'); fireEvent.change(key, { target: { value: 'synthetic-unsent' } });
  fireEvent.change(provider, { target: { value: 'openrouter' } });
  expect(key).toHaveValue(''); expect(screen.queryByRole('region', { name: 'Provider change confirmation' })).not.toBeInTheDocument();
  expect(state.writes.map(item => item.body.action)).toEqual(['refresh']);
});
it('keeps the current OrcaRouter catalog failure separate from an earlier OpenRouter update after switching provider', async () => {
  const orca = { ...configured.connections[0]!, provider: 'orcarouter' as const, connection_id: '44444444-4444-4444-8444-444444444444' };
  const orcaEntry = { ...entry, entry_id: '55555555-5555-4555-8555-555555555555', connection_id: orca.connection_id, model: 'Orca/Model' };
  const keys = { ...configured, connections: [...configured.connections, orca], selection: { selection_id: entryId, revision: 7, default: selected, brain: { ...selected, output_tokens: 37 }, investigator: null, validator: null } };
  const { state, hook } = settingsBackend(keys, [entry, orcaEntry], []);
  const reads: Record<string, unknown>[] = [];
  hook.intercept = (path, body) => {
    if (!path.endsWith('/search') && !path.endsWith('/refresh')) return;
    if (path.endsWith('/search')) reads.push(body);
    const isOrca = body.connection_id === orca.connection_id;
    return Response.json({ schema_version: 1, connection_id: body.connection_id, connection_revision: body.connection_revision, provider: isOrca ? 'orcarouter' : 'openrouter', catalog_command_id: body.command_id ?? body.catalog_command_id ?? catalogId, state: isOrca ? 'FAILED' : 'PENDING', reason: isOrca ? 'SCHEMA_UNSUPPORTED' : null, query: body.query ?? '', offset: 0, next_offset: null, total: 0, entries: [] });
  };
  mount(); await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Add models' })); fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
  const panel = screen.getByRole('region', { name: 'Add models wizard' });
  await within(panel).findByLabelText('Search models');
  await waitFor(() => expect(within(panel).getByRole('button', { name: 'Back' })).toHaveAttribute('aria-disabled', 'false'));
  expect(within(panel).getByRole('button', { name: 'Read catalog status' })).toBeEnabled();
  expect(screen.getAllByRole('region', { name: 'Catalog recovery' })).toHaveLength(1);
  fireEvent.click(within(panel).getByRole('button', { name: 'Back' }));
  fireEvent.change(within(panel).getByLabelText('Provider'), { target: { value: 'orcarouter' } });
  expect(within(panel).getByLabelText('Provider')).toHaveValue('orcarouter');
  fireEvent.click(within(panel).getByRole('button', { name: 'Continue' }));
  await waitFor(() => expect(within(panel).getByRole('list', { name: 'Provider models' })).toHaveAttribute('aria-busy', 'false'));
  expect(within(panel).queryByText('Models could not be loaded. Refresh the list or enter an exact model ID.')).toBeVisible();
  fireEvent.click(within(panel).getByText('Catalog details'));
  expect(within(panel).getByText('FAILED · SCHEMA_UNSUPPORTED')).toBeVisible();
  expect(within(panel).queryByText('Loading models…')).not.toBeInTheDocument();
  expect(within(panel).queryByRole('region', { name: 'Catalog recovery' })).not.toBeInTheDocument();
  const old = within(screen.getByRole('region', { name: 'OpenRouter' })).getByRole('region', { name: 'Catalog recovery' });
  expect(within(old).getByRole('button', { name: 'Read catalog status' })).toBeEnabled();
  expect(within(old).getByRole('button', { name: 'Cancel catalog' })).toBeEnabled();
  expect(old).toHaveTextContent('This update is separate from the current model list. Read or cancel it before refreshing another list.');
  expect(within(screen.getByRole('region', { name: 'OrcaRouter' })).queryByText('Catalog details')).not.toBeInTheDocument();
  const before = reads.length;
  fireEvent.click(within(old).getByRole('button', { name: 'Read catalog status' }));
  await waitFor(() => expect(reads.slice(before)).toContainEqual(expect.objectContaining({ connection_id: entry.connection_id, connection_revision: 1, catalog_command_id: state.writes[0]!.body.command_id })));
  expect(within(panel).getByText('FAILED · SCHEMA_UNSUPPORTED')).toBeVisible();
  fireEvent.click(within(panel).getByText('Enter a model ID'));
  fireEvent.change(within(panel).getByLabelText('Exact model ID'), { target: { value: 'Orca/New' } }); fireEvent.click(within(panel).getByRole('button', { name: 'Add model ID' }));
  await review(); fireEvent.click(within(panel).getByRole('button', { name: 'Back' }));
  expect(within(panel).getByRole('list', { name: 'Selected models' })).toHaveTextContent('Orca/New');
  fireEvent.click(within(panel).getByRole('button', { name: 'Refresh' }));
  await waitFor(() => expect(within(panel).getByRole('button', { name: 'Refresh' })).toHaveAttribute('aria-disabled', 'false'));
  expect(state.writes).toEqual([{ path: '/api/v1/settings/provider-catalog/refresh', body: expect.objectContaining({ connection_id: entry.connection_id, connection_revision: 1 }) }]);
  expect(sessionStorage.getItem(catalogStorage)).toContain(String(state.writes[0]!.body.command_id));
  expect(state.keys).toEqual(keys); expect(state.entries).toEqual([entry, orcaEntry]);
});
it('never binds an earlier connection revision recovery or notice to the current wizard catalog', async () => {
  const currentConnection = { ...configured.connections[0]!, revision: 2 };
  const { state, hook } = settingsBackend({ ...configured, connections: [currentConnection] }, [{ ...entry, connection_revision: 2 }], []);
  const old = { id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', connection: currentConnection.connection_id, revision: 1 };
  let settled = false;
  hook.intercept = (path, body) => {
    if (!path.endsWith('/search')) return;
    const earlier = body.connection_revision === 1;
    if (earlier) { expect(body.catalog_command_id).toBe(old.id); settled = true; }
    return Response.json({ schema_version: 1, connection_id: body.connection_id, connection_revision: body.connection_revision, provider: 'openrouter', catalog_command_id: body.catalog_command_id ?? catalogId, state: 'FAILED', reason: earlier ? 'CONNECTION_STALE' : 'METADATA_UNAVAILABLE', query: body.query, offset: 0, next_offset: null, total: 0, entries: [] });
  };
  remember(catalogStorage, await sessionScope(session.csrf_token), old);
  mount(); await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Add models' })); fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
  const panel = screen.getByRole('region', { name: 'Add models wizard' });
  await waitFor(() => expect(within(panel).getByRole('list', { name: 'Provider models' })).toHaveAttribute('aria-busy', 'false'));
  expect(within(panel).queryByText('Models could not be loaded. Refresh the list or enter an exact model ID.')).toBeVisible();
  fireEvent.click(within(panel).getByText('Catalog details'));
  expect(within(panel).getByText('FAILED · METADATA_UNAVAILABLE')).toBeVisible();
  expect(within(panel).queryByRole('region', { name: 'Catalog recovery' })).not.toBeInTheDocument();
  const recovery = within(screen.getByRole('region', { name: 'OpenRouter' })).getByRole('region', { name: 'Catalog recovery' });
  fireEvent.click(within(recovery).getByRole('button', { name: 'Read catalog status' }));
  await waitFor(() => expect(settled).toBe(true));
  await waitFor(() => expect(within(recovery).queryByRole('button', { name: 'Read catalog status' })).not.toBeInTheDocument());
  expect(sessionStorage.getItem(catalogStorage)).toBeNull();
  expect(within(panel).getByText('FAILED · METADATA_UNAVAILABLE')).toBeVisible();
  expect(within(panel).queryByText(/CONNECTION_STALE/)).not.toBeInTheDocument();
  fireEvent.click(within(recovery).getByText('Catalog details'));
  expect(within(recovery).getByText('FAILED · CONNECTION_STALE')).toBeVisible();
  fireEvent.click(within(panel).getByRole('button', { name: 'Cancel' }));
  const card = screen.getByRole('region', { name: 'OpenRouter' });
  expect(within(card).queryByText('The model catalog is unavailable. Saved test results are unchanged. Open Add models to refresh it explicitly.')).toBeVisible();
  expect(within(card).getAllByText('Catalog details')).toHaveLength(2);
  expect(state.writes).toEqual([]);
});
it('closes after proven Save while admission is held and keeps only row progress with one contextual control', async () => {
  const { state, hook } = settingsBackend(configured, [], models);
  let view: EntryTestView | undefined, held = false, release = () => {};
  const gate = new Promise<void>(resolve => { release = resolve; });
  hook.intercept = async (path, body, method) => {
    if (path === '/api/v1/model-test/entries' && method === 'PUT') {
      view = operation(String(body.operation_id), state.entries.find(item => item.entry_id === body.entry_id)!);
      held = true; await gate; return Response.json(view);
    }
    if (path.includes('/entries/latest/') && view?.entry_id === path.split('/').at(-1)) return Response.json(view);
    if (view && path === '/api/v1/model-test/entries/' + view.operation_id) return Response.json(view);
  };
  mount(); await wizard(); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/01' })); await review();
  fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: 'Save & connect' }));
  try {
    await waitFor(() => expect(held).toBe(true));
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Add models wizard' })).not.toBeInTheDocument());
    const row = modelRow('Catalog/00');
    expect(within(row).getByText('Connecting', { exact: true })).toBeVisible();
    expect(within(row).getAllByRole('button', { name: /Cancel test|Stop remaining checks/ })).toHaveLength(1);
    expect(screen.queryByRole('region', { name: 'Test consent' })).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Settings recovery' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Active model check')).not.toBeInTheDocument();
    expect(screen.queryByText('Connected', { exact: true })).not.toBeInTheDocument();
    release();
    await within(row).findByRole('button', { name: 'Cancel test' });
    expect(within(row).getAllByRole('button', { name: /Cancel test|Stop remaining checks/ })).toHaveLength(1);
    expect(row).not.toHaveTextContent(/refund|300 seconds|revision|OMNIS_MODEL_TEST_OK/);
    expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(1);
  } finally { release(); }
});
it.each(['COMPLETED', 'UNKNOWN'] as const)('does not claim Connected before exact latest readback returns %s', async result => {
  const { state, hook } = settingsBackend(configured, [], models);
  let view: EntryTestView | undefined, held = false, release = () => {};
  const gate = new Promise<void>(resolve => { release = resolve; });
  hook.intercept = async (path, body, method) => {
    if (path === '/api/v1/model-test/entries' && method === 'PUT') {
      view = { ...operation(String(body.operation_id), state.entries.find(item => item.entry_id === body.entry_id)!), state: 'FINISHED', finish_reason: 'COMPLETED', result_state: 'COMPLETED' };
      return Response.json(view);
    }
    if (view && path.includes('/entries/latest/') && path.endsWith(view.entry_id)) { held = true; await gate; return Response.json({ ...view, result_state: result }); }
    if (view && path === '/api/v1/model-test/entries/' + view.operation_id) return Response.json(view);
  };
  let lastCompleted: string | null = null;
  if (result === 'COMPLETED') {
    const backend = vi.mocked(fetch).getMockImplementation()!;
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const response = await backend(input, init);
      const path = String(input).split('?')[0]!;
      lastCompleted = path.replace(/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}/g, ':id');
      return response;
    });
  }
  const mounted = mount();
  try { await wizard(); }
  finally {
    if (result === 'COMPLETED') console.error('SOURCE_LATEST_PRE_WIZARD ' + JSON.stringify({
      queries: mounted.client.getQueryCache().getAll().filter(query => query.queryKey[0] === 'session' || query.queryKey[1] === 'settings-model-library').map(query => ({
        label: query.queryKey[0] === 'session' ? 'session' : 'library', status: query.state.status, fetchStatus: query.state.fetchStatus,
        errorCode: query.state.error instanceof ApiError ? query.state.error.code : query.state.error ? 'NON_API_ERROR' : null,
      })),
      lastCompletedPath: lastCompleted,
      phase: screen.queryByLabelText('Search models') ? 'catalog' : screen.queryByRole('region', { name: 'Add models wizard' }) ? 'wizard-key' : screen.queryByRole('region', { name: 'Configured models' }) ? 'library' : 'bootstrap',
      add: { disabled: screen.queryByRole('button', { name: 'Add models' })?.hasAttribute('disabled') ?? null, ariaDisabled: screen.queryByRole('button', { name: 'Add models' })?.getAttribute('aria-disabled') ?? null },
    }));
  }
  fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); await review();
  fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: 'Save & connect' }));
  try {
    await waitFor(() => expect(held).toBe(true));
    expect(within(modelRow('Catalog/00')).getByText('Connecting')).toBeVisible();
    expect(screen.queryByText('Connected', { exact: true })).not.toBeInTheDocument();
    release(); await within(modelRow('Catalog/00')).findByText(result === 'COMPLETED' ? 'Connected' : 'Unconfirmed', { exact: true });
    if (result === 'UNKNOWN') expect(within(modelRow('Catalog/00')).getByText(/Connection checks stopped/)).toBeVisible();
    expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(1);
  } finally { release(); }
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
  expect(within(panel).getByRole('checkbox')).toHaveAccessibleName('I approve using these models.');
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
  fireEvent.click(screen.getByRole('button', { name: 'Save models' })); await screen.findByText('Models saved.');
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
  const scope = await sessionScope(session.csrf_token), { client } = mount(); await wizard(); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/01' })); await review();
  fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: 'Save & connect' }));
  await waitFor(() => expect(reads).toBeGreaterThan(0)); expect(views.size).toBe(1);
  const first = [...views.values()][0]!;
  failNextRead = uncertain; fireEvent.click(screen.getByRole('button', { name: 'Read test status' }));
  if (uncertain) await screen.findByText('UNKNOWN — keep the same operation ID. No test was resent.');
  else await waitFor(() => expect(reads).toBeGreaterThan(1));
  finish = true; await new Promise(resolve => setTimeout(resolve, 1100));
  expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(uncertain ? 1 : 2);
  if (uncertain) {
    const panel = modelRow('Catalog/00'), list = screen.getByRole('region', { name: 'Configured models' });
    await waitFor(() => expect(client.getQueryData(['private', 'settings-entry-test', scope, first.operation_id])).toMatchObject({ operation_id: first.operation_id, state: 'FINISHED', result_state: 'COMPLETED' }));
    expect(state.reads).toContain('/api/v1/model-test/entries/' + first.operation_id);
    expect(panel).not.toHaveTextContent(first.operation_id!);
    expect(within(panel).getByText('UNKNOWN — keep the same operation ID. No test was resent.')).toBeVisible();
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
  let release = () => {}; const gate = new Promise<void>(resolve => { release = resolve; });
  hook.intercept = async (path, body, method) => {
    if (path === '/api/v1/model-test/entries' && method === 'PUT') {
      if (failure === 'refused') return Response.json({ error: { code: 'REVISION_CONFLICT', correlation_id: entryId } }, { status: 409 });
      const target = state.entries.find(item => item.entry_id === body.entry_id)!; view = operation(String(body.operation_id), target);
      if (failure === 'lost') throw new TypeError('Lost admission');
      if (failure === 'stop') await gate;
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
  else if (failure === 'stop') { fireEvent.click(await screen.findByRole('button', { name: 'Stop remaining checks' })); release(); }
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
  fireEvent.click(screen.getByRole('button', { name: 'Save models' })); await screen.findByText('Models saved.');
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
  expect(screen.getByRole('button', { name: 'Save & connect' })).toBeDisabled(); fireEvent.click(screen.getByRole('checkbox', { name: /I approve using (this model|these models)\./ })); fireEvent.click(screen.getByRole('button', { name: 'Save & connect' }));
  const panel = await screen.findByRole('listitem', { name: 'Model Catalog/00 via OpenRouter' }); await waitFor(() => expect(within(panel).getByRole('button', { name: 'Cancel test' })).toBeEnabled());
  expect(screen.queryByRole('region', { name: 'Add models wizard' })).not.toBeInTheDocument(); expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(1);
  expect(view?.requested_model).toBe('Catalog/00'); expect(state.keys.selection).toBeNull(); expect(view?.entry_id).toBe(state.entries[0]!.entry_id);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled()); fireEvent.click(screen.getByRole('button', { name: 'Add models' }));
  expect(within(panel).getByRole('button', { name: 'Read test status' })).toBeEnabled(); fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  mounted.unmount(); mount(); await screen.findByRole('button', { name: 'Cancel test' }); expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(1);
});
it.each(['sequence', 'single', 'pending', 'hydrated'] as const)('expands history without replacing the %s active Cancel target', async mode => {
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
  const scope = await sessionScope(session.csrf_token), { client } = mount(); await screen.findByRole('region', { name: 'Configured models' });
  if (mode === 'sequence') {
    await wizard(); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/01' })); await review();
    fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: 'Save & connect' }));
  } else if (mode !== 'hydrated') {
    const test = screen.getByRole('button', { name: 'Test Catalog/00 via OpenRouter' }); await waitFor(() => expect(test).toBeEnabled()); fireEvent.click(test);
    fireEvent.click(screen.getByRole('checkbox'));
    if (mode === 'pending') {
      fireEvent.click(screen.getByRole('button', { name: 'Send model test' })); await admission;
      const history = screen.getByRole('button', { name: 'Details for Exact/Model via OpenRouter' }); expect(history).toBeEnabled(); fireEvent.click(history);
      expect(within(modelRow('Exact/Model')).getByRole('button', { name: 'Read test status' })).toBeDisabled();
      release();
    } else fireEvent.click(screen.getByRole('button', { name: 'Send model test' }));
  } else {
    // Fresh-page hydration must expose Cancel without requiring a history selection.
    expect(sessionStorage.getItem(testStorage)).toBeNull();
  }
  const panel = await screen.findByRole('listitem', { name: 'Model Catalog/00 via OpenRouter' });
  await waitFor(() => expect(within(panel).getByRole('button', { name: 'Cancel test' })).toBeEnabled());
  const id = active!.operation_id, before = state.reads.length;
  const history = screen.getByRole('button', { name: 'Details for Exact/Model via OpenRouter' });
  if (history.getAttribute('aria-expanded') !== 'true') fireEvent.click(history);
  const historicalRead = within(modelRow('Exact/Model')).getByRole('button', { name: 'Read test status' }); expect(historicalRead).toBeDisabled(); fireEvent.click(historicalRead);
  fireEvent.click(within(panel).getByRole('button', { name: 'Read test status' }));
  await waitFor(() => expect(state.reads.slice(before)).toContain('/api/v1/model-test/entries/' + id));
  expect(history).toBeEnabled(); expect(panel).toHaveTextContent('Connecting');
  await waitFor(() => expect(client.getQueryData(['private', 'settings-entry-test', scope, id])).toMatchObject({ operation_id: id, state: 'RUNNING' }));
  const read = within(panel).getByRole('button', { name: 'Read test status' }); expect(read).toBeEnabled(); fireEvent.click(read);
  await waitFor(() => expect(state.reads.slice(before)).toContain('/api/v1/model-test/entries/' + id));
  expect(state.reads.slice(before)).not.toContain('/api/v1/model-test/entries/' + old.operation_id);
  const cancel = within(panel).getByRole('button', { name: 'Cancel test' }); expect(cancel).toBeEnabled(); fireEvent.click(cancel);
  await waitFor(() => expect(state.writes.filter(item => item.path.endsWith('/cancel'))).toEqual([{ path: `/api/v1/model-test/entries/${id}/cancel`, body: expect.objectContaining({ expected_state_revision: 2 }) }]));
  await waitFor(() => expect(client.getQueryData(['private', 'settings-entry-test', scope, id])).toMatchObject({ operation_id: id, state: 'FINISHED', result_state: 'NOT_SENT' }));
  expect(within(panel).getByText('Test cancelled. Read the saved result before testing again.')).toBeVisible();
  expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(mode === 'hydrated' ? 0 : 1);
  expect(active!.operation_id).toBe(id); expect(state.keys.selection).toBeNull();
  await waitFor(() => expect(historicalRead).toBeEnabled()); fireEvent.click(historicalRead);
  await waitFor(() => expect(state.reads).toContain('/api/v1/model-test/entries/' + old.operation_id));
  expect(modelRow('Exact/Model')).not.toHaveTextContent(old.operation_id!);
  await waitFor(() => expect(client.getQueryData(['private', 'settings-entry-test', scope, old.operation_id])).toMatchObject({ operation_id: old.operation_id, state: 'FINISHED', result_state: 'COMPLETED' }));
  expect(within(modelRow('Exact/Model')).getByText('Test passed · model details unavailable')).toBeVisible();
  expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(mode === 'hydrated' ? 0 : 1);
});
it.each(['remembered-completed', 'fresh-unknown-first', 'remembered-unknown'] as const)('recovers the actual active check with %s history', async mode => {
  const target = { ...entry, entry_id: mode === 'remembered-unknown' ? '00000000-0000-4000-8000-000000000001' : 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', model: 'Catalog/00' };
  const old: EntryTestView = { ...operation('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', entry), state: 'FINISHED', state_revision: 3, result_state: mode === 'remembered-completed' ? 'COMPLETED' : 'UNKNOWN', finish_reason: mode === 'remembered-completed' ? 'COMPLETED' : 'OWNER_LOST' };
  let active = operation('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', target);
  const { state, hook } = settingsBackend(configured, [entry, target], models);
  hook.intercept = (path, _body, method) => {
    if (path.endsWith(entryId) || path.endsWith(old.operation_id!)) return Response.json(old);
    if (path.endsWith(target.entry_id) || path.includes(active.operation_id!)) {
      if (method === 'POST') active = { ...active, state: 'FINISHED', state_revision: 3, result_state: 'NOT_SENT', finish_reason: 'CANCELLED' };
      return Response.json(active);
    }
  };
  const scope = await sessionScope(session.csrf_token);
  if (mode !== 'fresh-unknown-first') remember(testStorage, scope, old.operation_id!);
  const { client } = mount(); await screen.findByRole('region', { name: 'Configured models' });
  const row = modelRow(target.model), cancel = await within(row).findByRole('button', { name: 'Cancel test' }); expect(cancel).toBeEnabled();
  fireEvent.click(screen.getByRole('button', { name: 'Details for Exact/Model via OpenRouter' }));
  expect(client.getQueryData(['private', 'settings-model-library', scope])).toMatchObject({ checks: { [entry.entry_id]: { operation_id: old.operation_id, state: 'FINISHED', result_state: old.result_state } } });
  expect(within(modelRow(entry.model)).getByText(old.result_state === 'COMPLETED' ? 'Test passed · model details unavailable' : 'Unconfirmed')).toBeVisible();
  expect(within(modelRow(entry.model)).getByRole('button', { name: 'Read test status' })).toBeDisabled();
  const before = state.reads.length;
  fireEvent.click(within(row).getByRole('button', { name: 'Read test status' }));
  await waitFor(() => expect(state.reads.slice(before)).toContain('/api/v1/model-test/entries/' + active.operation_id));
  expect(state.reads.slice(before)).not.toContain('/api/v1/model-test/entries/' + old.operation_id); expect(state.writes).toEqual([]);
  fireEvent.click(cancel);
  await waitFor(() => expect(state.writes).toEqual([{ path: `/api/v1/model-test/entries/${active.operation_id}/cancel`, body: expect.objectContaining({ expected_state_revision: 2 }) }]));
  await waitFor(() => expect(client.getQueryData(['private', 'settings-entry-test', scope, active.operation_id])).toMatchObject({ operation_id: active.operation_id, state: 'FINISHED', result_state: 'NOT_SENT' }));
  expect(within(row).getByText('Test cancelled. Read the saved result before testing again.')).toBeVisible();
});
it.each(['FINISHED', 'NEEDS_RECONCILIATION'] as const)('remote UNKNOWN with local %s preserves history and requires fresh consent after readback', async status => {
  const old: EntryTestView = { ...operation('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', entry), state: status, state_revision: 3, result_state: 'UNKNOWN', finish_reason: status === 'FINISHED' ? 'OWNER_LOST' : null };
  const { state, hook } = settingsBackend();
  hook.intercept = (path, body, method) => {
    if (path === '/api/v1/model-test/entries' && method === 'PUT') return Response.json(operation(String(body.operation_id), entry));
    if (path.includes('/model-test/entries/')) return Response.json(old);
  };
  const scope = await sessionScope(session.csrf_token), { client } = mount(); const row = await screen.findByRole('listitem', { name: 'Model Exact/Model via OpenRouter' });
  const read = await within(row).findByRole('button', { name: 'Read test status' }), before = state.reads.filter(path => path.endsWith(old.operation_id!)).length;
  fireEvent.click(read);
  await waitFor(() => expect(state.reads.filter(path => path.endsWith(old.operation_id!)).length).toBeGreaterThan(before));
  await waitFor(() => expect(client.getQueryData(['private', 'settings-entry-test', scope, old.operation_id])).toMatchObject({ operation_id: old.operation_id, state: status, result_state: 'UNKNOWN' }));
  expect(row).not.toHaveTextContent(old.operation_id!); expect(state.writes).toEqual([]);
  expect(within(row).getByText('Unconfirmed')).toBeVisible();
  if (status === 'NEEDS_RECONCILIATION') {
    expect(within(row).queryByRole('button', { name: 'Test Exact/Model via OpenRouter' })).not.toBeInTheDocument();
    expect(within(row).getByRole('button', { name: 'Cancel test' })).toBeEnabled();
    return;
  }
  expect(within(row).queryByRole('button', { name: 'Cancel test' })).not.toBeInTheDocument();
  const test = await within(row).findByRole('button', { name: 'Test Exact/Model via OpenRouter' }); expect(test).toBeEnabled(); fireEvent.click(test);
  expect(screen.getByRole('checkbox')).not.toBeChecked(); expect(screen.getByRole('button', { name: 'Send model test' })).toBeDisabled();
  expect(state.writes).toEqual([]); expect(within(row).getByText('Remote outcome remains unknown.')).toBeVisible();
  fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: 'Send model test' }));
  await waitFor(() => expect(state.writes).toEqual([{ path: '/api/v1/model-test/entries', body: expect.objectContaining({ entry_id: entryId, expected_generation: 1, consent: true }) }]));
  expect(state.writes[0]!.body.operation_id).not.toBe(old.operation_id);
});
it.each(['RUNNING', 'UNKNOWN'] as const)('preserves receive-only recovery for an orphan %s operation', async status => {
  const orphan = { ...entry, entry_id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', model: 'Orphan/Model' };
  const view = { ...operation('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', orphan), state: status === 'UNKNOWN' ? 'FINISHED' : 'RUNNING', result_state: status === 'UNKNOWN' ? 'UNKNOWN' : null };
  const { state, hook } = settingsBackend(configured, [], models);
  hook.intercept = path => path.endsWith(view.operation_id!) ? Response.json(view) : undefined;
  remember(testStorage, await sessionScope(session.csrf_token), view.operation_id!); mount();
  const result = await screen.findByText(/Orphan\/Model/); expect(result).toBeVisible();
  const recovery = screen.getByRole('region', { name: 'Unconfirmed model check' });
  expect(recovery).not.toHaveTextContent(view.operation_id!); expect(screen.queryByText('Operation details')).not.toBeInTheDocument();
  if (status === 'UNKNOWN') expect(within(recovery).queryByRole('button', { name: 'Cancel test' })).not.toBeInTheDocument();
  const before = state.reads.length; fireEvent.click(within(recovery).getByRole('button', { name: 'Read test status' }));
  await waitFor(() => expect(state.reads.slice(before)).toContain('/api/v1/model-test/entries/' + view.operation_id));
  expect(state.writes).toEqual([]); expect(sessionStorage.getItem(testStorage)).toContain(view.operation_id!);
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
it.each(['RUNNING', 'FINISHED', 'NEEDS_RECONCILIATION'] as const)('keeps %s recovery separate from the usage capsule and exact operation identity internal', async status => {
  const { state, hook } = settingsBackend(); let view: EntryTestView | undefined;
  hook.intercept = (path, body, method) => {
    if (path === '/api/v1/model-test/entries' && method === 'PUT') {
      view = { ...operation(String(body.operation_id), entry), state: status, result_state: status === 'FINISHED' ? 'COMPLETED' : status === 'RUNNING' ? null : 'UNKNOWN', finish_reason: status === 'FINISHED' ? 'COMPLETED' : null, observed_model: status === 'FINISHED' ? entry.model : null, response_text: status === 'FINISHED' ? 'OMNIS_MODEL_TEST_OK' : null };
      return Response.json(view);
    }
    if (path.startsWith('/api/v1/model-test/entries/')) return Response.json(view);
  };
  mount(); fireEvent.click(await screen.findByRole('button', { name: 'Test Exact/Model via OpenRouter' }));
  fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: 'Send model test' }));
  const panel = modelRow('Exact/Model');
  await within(panel).findByText(status === 'FINISHED' ? 'Connected' : status === 'RUNNING' ? 'Connecting' : 'Unconfirmed');
  const toggle = within(panel).getByRole('button', { name: 'Details for Exact/Model via OpenRouter' });
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  if (status !== 'FINISHED') expect(within(panel).getByRole('button', { name: 'Read test status' })).toBeVisible();
  fireEvent.click(toggle);
  expect(screen.queryByText('Operation details')).not.toBeInTheDocument(); expect(panel).not.toHaveTextContent(view!.operation_id!);
  expect(within(panel).getByLabelText('Test usage')).toBeVisible();
  if (status === 'FINISHED') {
    expect(within(panel).queryByRole('button', { name: 'Cancel test' })).not.toBeInTheDocument();
    expect(within(panel).queryByText(/Cancel does not guarantee/)).not.toBeInTheDocument();
  } else {
    expect(within(panel).getByRole('button', { name: 'Cancel test' })).toBeEnabled();
    expect(within(panel).queryByText(/refund/)).not.toBeInTheDocument();
  }
  fireEvent.click(toggle);
  expect(within(panel).queryByLabelText('Model response')).not.toBeInTheDocument();
  if (status !== 'FINISHED') fireEvent.click(within(panel).getByRole('button', { name: 'Read test status' }));
  await waitFor(() => expect(state.reads).toContain('/api/v1/model-test/entries/' + view!.operation_id));
  expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(1);
});
it('updates saved-model eligibility after an explicit catalog refresh without retesting or changing assignments', async () => {
  const { state, hook } = settingsBackend(configured, [entry], models.concat({ model: entry.model, name: 'Exact model', max_output_tokens: 4096, supports_max_tokens: true, reason: null }));
  let refreshed = false;
  hook.intercept = (path, body) => {
    if (path.includes('/entries/latest/')) return Response.json({ ...operation('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', entry), state: 'FINISHED', result_state: 'COMPLETED', finish_reason: 'COMPLETED' });
    if (path.endsWith('/refresh')) refreshed = true;
    if (!refreshed && path.endsWith('/search')) return Response.json({ schema_version: 1, connection_id: entry.connection_id, connection_revision: 1, provider: 'openrouter', catalog_command_id: catalogId, state: 'FAILED', reason: 'METADATA_UNAVAILABLE', query: body.query, offset: 0, next_offset: null, total: 0, entries: [] });
  };
  mount(); await screen.findByText('Test passed · catalog unavailable');
  await wizard(); fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  await screen.findByText('Connected'); expect(screen.getByRole('button', { name: 'Test Exact/Model via OpenRouter' })).toBeEnabled();
  expect(state.writes.map(item => item.body.action)).toEqual(['refresh']); expect(state.keys.selection).toBeNull();
});
it('keeps catalog failure beside its list with a secondary cause and no catalog notification', async () => {
  const { state, hook } = settingsBackend(configured, [], models);
  hook.intercept = (path, body) => path.endsWith('/search') || path.endsWith('/refresh') ? Response.json({ schema_version: 1, connection_id: entry.connection_id, connection_revision: 1, provider: 'openrouter', catalog_command_id: body.command_id ?? body.catalog_command_id ?? catalogId, state: 'FAILED', reason: 'METADATA_UNAVAILABLE', query: body.query ?? '', offset: 0, next_offset: null, total: 0, entries: [] }) : undefined;
  mount(); await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled()); fireEvent.click(screen.getByRole('button', { name: 'Add models' }));
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
  const panel = screen.getByRole('region', { name: 'Add models wizard' });
  await within(panel).findByText('Models could not be loaded. Refresh the list or enter an exact model ID.');
  expect(screen.getAllByText('Models could not be loaded. Refresh the list or enter an exact model ID.')).toHaveLength(1);
  expect(screen.queryByRole('complementary', { name: 'Settings notification' })).not.toBeInTheDocument();
  const details = within(panel).getByText('Catalog details').closest('details'); expect(details).not.toHaveAttribute('open');
  expect(within(panel).getByText(/METADATA_UNAVAILABLE/)).not.toBeVisible();
  fireEvent.click(within(panel).getByText('Catalog details')); expect(within(panel).getByText(/METADATA_UNAVAILABLE/)).toBeVisible();
  expect(within(panel).getByRole('button', { name: 'Refresh' })).toBeEnabled();
  expect(screen.getByText('Key saved')).toBeVisible(); expect(state.keys).toEqual(configured);
  expect(state.writes.map(item => item.body.action)).toEqual(['refresh']);
});
it('catalog lost reply has receive-only recovery after closing its wizard', async () => {
  const { state, hook } = settingsBackend(configured, [], models);
  hook.intercept = (path, _body, method) => { if (path.endsWith('/refresh') && method === 'POST') throw new TypeError('SOURCE lost catalog response'); return undefined; };
  mount(); await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled()); fireEvent.click(screen.getByRole('button', { name: 'Add models' })); fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
  await screen.findByRole('button', { name: 'Read catalog status' }); fireEvent.click(screen.getByRole('button', { name: 'Cancel' })); fireEvent.click(screen.getByRole('button', { name: 'Read catalog status' }));
  await waitFor(() => expect(screen.queryByRole('region', { name: 'Catalog recovery' })).not.toBeInTheDocument());
  expect(screen.queryByRole('complementary', { name: 'Settings notification' })).not.toBeInTheDocument();
  expect(state.writes).toHaveLength(1); expect(state.writes[0]!.body.action).toBe('refresh'); expect(sessionStorage.getItem(catalogStorage)).toBeNull();
});
it.each(['READY', 'PARTIAL', 'FAILED', 'PENDING', 'UNKNOWN'] as const)('keeps catalog readback %s local without clearing receipt safety state or resending', async status => {
  const { state, hook } = settingsBackend();
  const scope = await sessionScope(session.csrf_token);
  remember(catalogStorage, scope, { id: catalogId, connection: entry.connection_id, revision: entry.connection_revision });
  remember(pendingStorage, scope, { kind: 'models', id: entryId });
  const pending = sessionStorage.getItem(pendingStorage);
  const reason = status === 'PARTIAL' ? 'CATALOG_LIMIT' : status === 'FAILED' ? 'METADATA_UNAVAILABLE' : null;
  hook.intercept = (path, body) => {
    if (!path.endsWith('/search') || body.catalog_command_id !== catalogId) return;
    if (status === 'UNKNOWN') throw new TypeError('SOURCE lost catalog readback');
    return Response.json({ schema_version: 1, connection_id: entry.connection_id, connection_revision: entry.connection_revision, provider: 'openrouter', catalog_command_id: catalogId, state: status, reason, query: '', offset: 0, next_offset: null, total: 0, entries: [] });
  };
  const mounted = mount();
  try {
    const list = await screen.findByRole('region', { name: 'Configured models' });
    expect(within(list).getByText('Not tested')).toBeVisible();
    vi.useFakeTimers();
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Read catalog status' })); });
    expect(screen.queryByRole('complementary', { name: 'Settings notification' })).not.toBeInTheDocument();
    if (status === 'READY') expect(screen.queryByRole('region', { name: 'Catalog recovery' })).not.toBeInTheDocument();
    else {
      const catalog = screen.getByRole('region', { name: 'Catalog recovery' });
      expect(within(catalog).getByRole('status')).toBeVisible();
      const text = catalog.textContent;
      expect(within(catalog).getByText('Catalog details').closest('details')).not.toHaveAttribute('open');
      if (reason) { expect(within(catalog).getByText(new RegExp(reason))).not.toBeVisible(); fireEvent.click(within(catalog).getByText('Catalog details')); expect(within(catalog).getByText(new RegExp(reason))).toBeVisible(); }
      await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
      expect(catalog).toHaveTextContent(text!);
    }
    const recovery = screen.getByRole('region', { name: 'Settings recovery' });
    expect(recovery).toHaveTextContent('Save unconfirmed. Recover the exact receipt before another mutation.');
    expect(within(recovery).getByText(`Command ${entryId}`)).not.toBeVisible();
    const commandDetails = within(recovery).getByText('Command details');
    expect(commandDetails.closest('details')).not.toHaveAttribute('open');
    fireEvent.click(commandDetails); expect(within(recovery).getByText(`Command ${entryId}`)).toBeVisible();
    fireEvent.click(commandDetails); expect(within(recovery).getByText(`Command ${entryId}`)).not.toBeVisible();
    expect(screen.getByRole('button', { name: 'Recover exact receipt' })).toBeEnabled();
    expect(within(recovery).getByRole('button', { name: 'Read current state' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Add models' })).toBeDisabled();
    if (status === 'PENDING' || status === 'UNKNOWN') {
      expect(screen.getByRole('region', { name: 'Catalog recovery' })).toHaveTextContent(catalogId);
      expect(screen.getByRole('button', { name: 'Read catalog status' })).toBeEnabled();
      expect(screen.getByRole('button', { name: 'Cancel catalog' })).toBeEnabled();
    }
    expect(within(list).getByText('Not tested')).toBeVisible();
    expect(sessionStorage.getItem(pendingStorage)).toBe(pending);
    expect(state.entries).toEqual([entry]); expect(state.keys).toEqual(configured);
    expect(state.writes).toHaveLength(0);
  } finally { mounted.unmount(); mounted.client.clear(); vi.useRealTimers(); }
});
it('explicitly updates a stale saved identity after key rotation instead of duplicating it', async () => {
  const { state } = settingsBackend({ ...configured, connections: configured.connections.map(item => ({ ...item, revision: 2 })) }, [entry]);
  mount(); await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled()); fireEvent.click(screen.getByRole('button', { name: 'Add models' })); fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
  const update = await screen.findByRole('button', { name: 'Update Exact/Model' }); fireEvent.click(update); await review(); fireEvent.click(screen.getByRole('button', { name: 'Save models' }));
  await screen.findByText('Models saved.'); expect(state.entries).toHaveLength(1); expect(state.entries[0]).toMatchObject({ entry_id: entry.entry_id, revision: 2, connection_revision: 2, output_tokens: 512 });
});
