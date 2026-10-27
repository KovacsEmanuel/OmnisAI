import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, expect, it, vi } from 'vitest';
import { App } from './App';
import { health, session } from '../../tests/fixtures';

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
it('opens on persisted models, not a wizard, and does not invent a persisted default', async () => {
  backend(); mount();
  expect(await screen.findByRole('region', { name: 'Configured models' })).toHaveTextContent('Exact/Model');
  expect(screen.queryByRole('region', { name: 'Add models wizard' })).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Models' })).toHaveAttribute('aria-current', 'page');
  expect(screen.queryByText(/All roles use/)).not.toBeInTheDocument();
  expect(screen.getByText(/Save assignments separately/)).toBeVisible();
  expect(writes).toEqual([]);
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
  await screen.findByText(/Outcome unknown/); expect(key).toHaveValue('');
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
