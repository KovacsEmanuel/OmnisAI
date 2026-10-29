// SOURCE UI fixture only: synthetic HTTP is not API/PostgreSQL/provider QA.
import { vi } from 'vitest';
import { health, instance, session } from './fixtures';
import type { KeySettings } from '../src/shared/api/providerKeys';
import { decodeKeySettings } from '../src/shared/api/providerKeys';
import { isRecord } from '../src/shared/api/errors';
import type { CatalogModel, ModelEntry } from '../src/features/engagement/SettingsModels';

export const connectionId = '11111111-1111-4111-8111-111111111111';
export const catalogId = '33333333-3333-4333-8333-333333333333';
export const entryId = '22222222-2222-4222-8222-222222222222';
export const connection = { connection_id: connectionId, provider: 'openrouter' as const, revision: 1, enabled: true, credential_present: true };
export const entry: ModelEntry = { entry_id: entryId, revision: 1, connection_id: connectionId, connection_revision: 1, model: 'Exact/Model', output_tokens: 512 };
export const empty: KeySettings = { schema_version: 2, command_id: null, vault_status: 'UNCONFIGURED', connections: [], selection: null, reachable: 'NOT_VERIFIED' };
export const configured: KeySettings = { ...empty, vault_status: 'UNLOCKED', connections: [connection] };
export const selected = { connection_id: connectionId, connection_revision: 1, model: entry.model, output_tokens: 512 };
export function settingsBackend(initial: KeySettings = configured, entries: ModelEntry[] = [entry], models: CatalogModel[] = [{ model: entry.model, name: 'Exact model', max_output_tokens: 4096, supports_max_tokens: true, reason: null }]) {
  const writes: { path: string; body: Record<string, unknown> }[] = [], reads: string[] = [];
  const state = { instance: { ...instance, generation: 1, admission_open: true }, keys: initial, entries, revision: entries.length ? 1 : 0, catalog: models, catalogState: 'READY', writes, reads, receipts: new Map<string, object>() };
  const hook: { intercept?: (path: string, body: Record<string, unknown>, method: string) => Response | undefined | Promise<Response | undefined> } = {};
  function registry(command_id: string | null = null, after: string | null = null) {
    const sorted = [...state.entries].sort((a, b) => a.entry_id.localeCompare(b.entry_id));
    const offset = after ? sorted.findIndex(item => item.entry_id === after) + 1 : 0;
    const page = sorted.slice(offset, offset + 16);
    return { schema_version: 1, command_id, registry_revision: state.revision, total: sorted.length, after, next_after: offset + page.length < sorted.length ? page.at(-1)!.entry_id : null, entries: page };
  }
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input), method = init?.method ?? 'GET';
    const body: Record<string, unknown> = init?.body ? JSON.parse(String(init.body)) : {};
    if (path === '/api/session') return Response.json(session);
    if (path === '/health/ready') return Response.json(health);
    const write = method === 'PUT' || /\/(refresh|cancel)$/.test(path);
    if (write) state.writes.push({ path, body }); else state.reads.push(path);
    if (path === '/api/instance') { const intercepted = await hook.intercept?.(path, body, method); return intercepted ?? Response.json(state.instance); }
    // SOURCE admission double: a refused HTTP attempt never creates a fixture operation.
    if (path === '/api/v1/model-test/entries' && method === 'PUT' && body.expected_generation !== state.instance.generation) return Response.json({ error: { code: 'REVISION_CONFLICT', correlation_id: entryId } }, { status: 409 });
    const intercepted = await hook.intercept?.(path, body, method); if (intercepted) return intercepted;
    if (method === 'GET' && state.entries.some(item => path === '/api/v1/model-test/entries/latest/' + item.entry_id)) return Response.json({ error: { code: 'NOT_FOUND', correlation_id: entryId } }, { status: 404 });
    if (path.includes('/commands/')) return Response.json(state.receipts.get(path.split('/').at(-1)!) ?? { error: { code: 'NOT_FOUND', correlation_id: entryId } }, { status: state.receipts.has(path.split('/').at(-1)!) ? 200 : 404 });
    if (path === '/api/v1/settings/providers') {
      if (method === 'PUT') {
        if (body.action === 'save_selection') state.keys = decodeKeySettings({ ...state.keys, selection: { selection_id: String(body.command_id), revision: (state.keys.selection?.revision ?? 0) + 1, default: body.default, brain: body.brain, investigator: body.investigator, validator: body.validator } }, null);
        else if (body.action === 'revoke_connection') state.keys = { ...state.keys, connections: state.keys.connections.map(item => item.connection_id === body.connection_id ? { ...item, enabled: false, revision: item.revision + 1 } : item) };
        else state.keys = { ...state.keys, vault_status: 'UNLOCKED', connections: [...state.keys.connections.filter(item => item.provider !== body.provider), { connection_id: String(body.connection_id), provider: body.provider === 'orcarouter' ? 'orcarouter' : 'openrouter', revision: Number(body.expected_revision) + 1, enabled: true, credential_present: true }] };
        const value = { ...state.keys, command_id: body.command_id }; state.receipts.set(String(body.command_id), value); return Response.json(value);
      }
      return Response.json(state.keys);
    }
    if (path === '/api/v1/settings/models') {
      if (method === 'PUT') {
        if (body.action === 'remove_model') {
          state.entries = state.entries.filter(item => item.entry_id !== body.entry_id); state.revision += 1;
          const value = registry(String(body.command_id)); state.receipts.set(String(body.command_id), value); return Response.json(value);
        }
        if (!Array.isArray(body.models)) throw new Error('Malformed SOURCE fixture intent');
        const added: ModelEntry[] = body.models.map((item: unknown) => {
          if (!isRecord(item) || typeof item.entry_id !== 'string' || typeof item.model !== 'string' || typeof item.output_tokens !== 'number' || typeof item.expected_revision !== 'number') throw new Error('Malformed SOURCE model intent');
          return { entry_id: item.entry_id, model: item.model, output_tokens: item.output_tokens, revision: item.expected_revision + 1, connection_id: String(body.connection_id), connection_revision: Number(body.connection_revision) };
        });
        state.entries = [...state.entries.filter(item => !added.some(next => next.entry_id === item.entry_id)), ...added]; state.revision += 1;
        const value = registry(String(body.command_id)); state.receipts.set(String(body.command_id), value); return Response.json(value);
      }
      return Response.json(registry());
    }
    if (path.startsWith('/api/v1/settings/models/pages/')) return Response.json(registry(null, path.split('/').at(-1)!));
    if (path.endsWith('/search') || path.endsWith('/refresh')) {
      const query = String(body.query ?? ''), offset = Number(body.offset ?? 0);
      const matching = state.catalog.filter(item => `${item.model} ${item.name ?? ''}`.toLowerCase().includes(query.toLowerCase()));
      const page = matching.slice(offset, offset + 16).map(item => ({ model: item.model, name: item.name ?? null, max_output_tokens: item.max_output_tokens ?? null, supports_max_tokens: item.supports_max_tokens ?? null, reason: item.reason ?? null })), currentConnection = state.keys.connections.find(item => item.connection_id === body.connection_id);
      return Response.json({ schema_version: 1, connection_id: body.connection_id, connection_revision: body.connection_revision, provider: currentConnection?.provider ?? 'openrouter', catalog_command_id: body.command_id ?? body.catalog_command_id ?? catalogId, state: state.catalogState, reason: state.catalogState === 'PARTIAL' ? 'CATALOG_LIMIT' : null, query, offset, next_offset: offset + page.length < matching.length ? offset + 16 : null, total: matching.length, entries: page });
    }
    throw new Error('Unexpected SOURCE request ' + method + ' ' + path);
  }));
  return { state, hook };
}
