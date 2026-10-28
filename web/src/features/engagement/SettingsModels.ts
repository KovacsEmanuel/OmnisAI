import { api } from '../../shared/api/client';
import { ApiError, isRecord, isUuid } from '../../shared/api/errors';
import type { components } from '../../shared/api/generated';
import type { CatalogView } from '../../shared/api/providerCatalog';
import type { KeySettings, KeySelection } from '../../shared/api/providerKeys';
import type { EntryTestView } from '../../shared/api/modelTest';

export type ModelEntry = components['schemas']['ModelEntry'];
export type Connection = components['schemas']['ConnectionView'];
export type CatalogModel = components['schemas']['CatalogModel'];
export type Library = { revision: number; entries: ModelEntry[] };
export type Evidence = { catalog: string; connectionRevision: number; model: CatalogModel };
export type Pending = { id: string; kind: 'keys' | 'models' };
export type CatalogOperation = { id: string; connection: string; revision: number };
export type EntryCheck = EntryTestView | null | 'UNKNOWN';
export function exactCheck(entry: ModelEntry, provider: Connection['provider'], check: EntryTestView) {
  return check.current && check.entry_id === entry.entry_id && check.entry_revision === entry.revision && check.connection_id === entry.connection_id && check.connection_revision === entry.connection_revision && check.requested_provider === provider && check.requested_model === entry.model && check.requested_output_tokens === entry.output_tokens;
}
export const providerName = (provider: string) => provider === 'openrouter' ? 'OpenRouter' : 'OrcaRouter';
export const message = (error: unknown) => error instanceof ApiError ? error.message : 'Current state is not confirmed. Read back before another action.';
export const matches = (entry: ModelEntry, choice: KeySelection | null | undefined) => !!choice && entry.connection_id === choice.connection_id && entry.connection_revision === choice.connection_revision && entry.model === choice.model;
export const currentConnection = (entry: ModelEntry, settings: KeySettings) => settings.connections.find(item => item.connection_id === entry.connection_id && item.revision === entry.connection_revision && item.enabled && item.credential_present);
export const supports = (model: Pick<CatalogModel, 'supports_max_tokens' | 'max_output_tokens'> | undefined, tokens: number) => Number.isSafeInteger(tokens) && tokens >= 1 && tokens <= 65536 && !!model && model.supports_max_tokens === true && model.max_output_tokens != null && model.max_output_tokens >= tokens;
export function usable(entry: ModelEntry, settings: KeySettings, evidence: Record<string, Evidence>) {
  const proof = evidence[entry.entry_id];
  return !!currentConnection(entry, settings) && proof?.connectionRevision === entry.connection_revision && supports(proof.model, entry.output_tokens);
}
export async function readLibrary(signal: AbortSignal): Promise<Library> {
  const first = await api.providerModels(null, signal);
  const entries = [...first.entries];
  let after = first.next_after;
  const seen = new Set<string>();
  while (after) {
    if (seen.has(after) || seen.size >= 3) throw new ApiError('INVALID_RESPONSE');
    seen.add(after);
    const page = await api.providerModelPage(first.registry_revision, after, signal);
    if (page.total !== first.total) throw new ApiError('INVALID_RESPONSE');
    entries.push(...page.entries); after = page.next_after;
  }
  if (entries.length !== first.total || new Set(entries.map(item => item.entry_id)).size !== entries.length || new Set(entries.map(item => JSON.stringify([item.connection_id, item.model]))).size !== entries.length || entries.some((item, i) => i > 0 && item.entry_id <= entries[i - 1]!.entry_id)) throw new ApiError('INVALID_RESPONSE');
  return { revision: first.registry_revision, entries };
}
export function catalogEvidence(view: CatalogView, entry: ModelEntry): Evidence | undefined {
  const model = view.entries.find(item => item.model === entry.model);
  return ['READY', 'PARTIAL'].includes(view.state) && view.catalog_command_id && view.connection_id === entry.connection_id && view.connection_revision === entry.connection_revision && model ? { catalog: view.catalog_command_id, connectionRevision: view.connection_revision, model } : undefined;
}
// Only non-secret identities and their session binding survive an uncertain response.
export async function sessionScope(csrf: string) {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(csrf));
  return Array.from(new Uint8Array(bytes), value => value.toString(16).padStart(2, '0')).join('');
}
export function remember(key: string, scope: string, value: object | string | null) {
  if (value === null) sessionStorage.removeItem(key);
  else sessionStorage.setItem(key, JSON.stringify({ scope, value }));
}
export function remembered(key: string, scope: string): unknown {
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    return isRecord(parsed) && parsed.scope === scope ? parsed.value : null;
  } catch { return null; }
}
export function readPending(value: unknown): Pending | null {
  return isRecord(value) && isUuid(value.id) && (value.kind === 'keys' || value.kind === 'models') ? { id: value.id, kind: value.kind } : null;
}
export function readCatalogOperation(value: unknown): CatalogOperation | null {
  return isRecord(value) && isUuid(value.id) && isUuid(value.connection) && typeof value.revision === 'number' && Number.isSafeInteger(value.revision) && value.revision >= 1 ? { id: value.id, connection: value.connection, revision: value.revision } : null;
}
export const pendingStorage = 'omnis-settings-command-v1';
export const catalogStorage = 'omnis-settings-catalog-v1';
export const testStorage = 'omnis-entry-test-v1';
