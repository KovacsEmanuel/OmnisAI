import { StrictMode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, expect, it, vi } from 'vitest';
import { App } from './App';
import { catalogId, configured, empty, entry, entryId, selected, settingsBackend } from '../../tests/settings-fixtures';
import type { ModelEntry } from '../features/engagement/SettingsModels';
import type { EntryTestView } from '../shared/api/modelTest';
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
it('review keeps short not-tested status, exact consent and closed output controls', async () => {
  const { state } = settingsBackend(configured, [], models); mount(); const panel = await wizard();
  fireEvent.click(within(panel).getByRole('button', { name: 'Add Catalog/00' })); await review();
  expect(within(panel).getByText('Not tested', { exact: true })).toBeVisible();
  expect(within(panel).getByText('Catalog/00', { selector: 'small', exact: true })).toBeVisible();
  expect(within(panel).getByText('Output controls').closest('details')).not.toHaveAttribute('open');
  expect(within(panel).getByLabelText('Catalog/00 output tokens')).not.toBeVisible();
  expect(within(panel).getByRole('checkbox', { name: /one call for Catalog\/00 via OpenRouter/ })).not.toBeChecked();
  expect(panel).toHaveTextContent('Provider charges may apply.');
  expect(panel).toHaveTextContent('One call / 300 seconds, no tools or target traffic. Cancel is not a refund.');
  expect(within(panel).getByRole('button', { name: 'Save & test' })).toBeDisabled();
  expect(state.writes.map(item => item.body.action)).toEqual(['refresh']);
});
it('manual 256-character exact ID saves UNVERIFIED and cannot acquire test consent', async () => {
  const { state } = settingsBackend(configured, [], models); mount(); await wizard(); const id = 'M'.repeat(256);
  fireEvent.click(screen.getByText('Enter a model ID')); fireEvent.change(screen.getByLabelText('Exact model ID'), { target: { value: id } }); fireEvent.click(screen.getByRole('button', { name: 'Add model ID' })); await review();
  expect(screen.getByRole('button', { name: 'Save & test' })).toBeDisabled(); expect(screen.getByText('UNVERIFIED — manual model ID')).toBeVisible(); fireEvent.click(screen.getByRole('button', { name: 'Save models' }));
  await screen.findByText('Models saved. Assignments stay unchanged.'); expect(state.entries[0]!.model).toBe(id); expect(state.keys.selection).toBeNull(); expect(screen.queryByText(/All roles use/)).not.toBeInTheDocument();
});
it.each([0, 1.5, 65537])('invalid output cap %s cannot authorize Save & test or send a registry write', async tokens => {
  const { state } = settingsBackend(configured, [], models); mount(); await wizard();
  fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); await review();
  fireEvent.click(screen.getByText('Output controls', { exact: true }));
  fireEvent.change(screen.getByLabelText('Catalog/00 output tokens'), { target: { value: tokens } });
  expect(screen.getByRole('checkbox', { name: /I approve the fixed synthetic input/ })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Save & test' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Save models' })).toBeDisabled();
  expect(state.writes.map(item => item.body.action)).toEqual(['refresh']);
});
it('provider switch confirmation retains pending choices when refused', async () => {
  settingsBackend(configured, [], models); mount(); const panel = await wizard(); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); fireEvent.click(within(panel).getByRole('button', { name: 'Back' }));
  vi.stubGlobal('confirm', vi.fn(() => false)); fireEvent.change(screen.getByLabelText('Provider'), { target: { value: 'orcarouter' } }); expect(screen.getByLabelText('Provider')).toHaveValue('openrouter');
  fireEvent.click(screen.getByRole('button', { name: 'Continue' })); await screen.findByLabelText('Search models'); expect(screen.getByRole('list', { name: 'Selected models' })).toHaveTextContent('Model 0');
});
it('Save & test targets one persisted entry, keeps Cancel/readback outside wizard, and reload never resends', async () => {
  const { state, hook } = settingsBackend(configured, [], models); let view: EntryTestView | undefined;
  hook.intercept = (path, body, method) => {
    if (path === '/api/v1/model-test/entries' && method === 'PUT') {
      const target = state.entries.find(item => item.entry_id === body.entry_id)!; view = operation(String(body.operation_id), target); return Response.json(view);
    }
    if (path.startsWith('/api/v1/model-test/entries/')) return Response.json(view);
  };
  const mounted = mount(); await wizard(); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/00' })); fireEvent.click(screen.getByRole('button', { name: 'Add Catalog/01' })); await review();
  expect(screen.getByRole('button', { name: 'Save & test' })).toBeDisabled(); fireEvent.click(screen.getByRole('checkbox', { name: /I approve the fixed synthetic input/ })); fireEvent.click(screen.getByRole('button', { name: 'Save & test' }));
  const panel = await screen.findByRole('region', { name: 'Model test operation' }); await waitFor(() => expect(within(panel).getByRole('button', { name: 'Cancel test' })).toBeEnabled());
  expect(screen.queryByRole('region', { name: 'Add models wizard' })).not.toBeInTheDocument(); expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(1);
  expect(view?.requested_model).toBe('Catalog/00'); expect(state.keys.selection).toBeNull(); expect(view?.entry_id).toBe(state.entries[0]!.entry_id);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled()); fireEvent.click(screen.getByRole('button', { name: 'Add models' }));
  expect(within(panel).getByRole('button', { name: 'Read test status' })).toBeEnabled(); fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  mounted.unmount(); mount(); await screen.findByRole('region', { name: 'Model test operation' }); expect(state.writes.filter(item => item.path === '/api/v1/model-test/entries')).toHaveLength(1);
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
