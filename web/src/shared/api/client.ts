import type { components, paths } from './generated';
import { ApiError, decodeError, isRecord, isUuid } from './errors';
import { decodeHealth, decodeInstance } from './decoders';
import { decodeProjection, decodeSelectedDraft, isDashboardCursor } from './projections';
import { decodeRevision } from './drafts';
import type { Draft } from './drafts';
import { decodeProvider } from './providers';
import type { ProviderCommand } from './providers';
import { catalogSelection, decodeCatalogInspection, decodeCatalogPage } from './catalog';
import { decodeEntryTest, decodeModelTest } from './modelTest';
import type { EntryTestRequest } from './modelTest';
import { decodeProviderCatalog } from './providerCatalog';
import type { SearchCatalog, RefreshCatalog, CancelCatalog } from './providerCatalog';
import { decodeKeySettings } from './providerKeys';
import type { KeyCommand } from './providerKeys';
import { decodeProviderModels } from './providerModels';
import type { SaveModels } from './providerModels';

type Session = components['schemas']['SessionView'];
type ApiPath = keyof paths;
type RequestPath = `/api/v1/settings/models/${string}` | `/api/v1/model-test/${string}` | `/api/v1/settings/providers/commands/${string}` | `/api/v1/settings/catalog/${string}` | `/api/v1/settings/provider/operations/${string}` | ApiPath | `/api/v1/dashboard?${string}` | `/api/v1/engagements/${string}`;

async function request(path: RequestPath, init: RequestInit = {}, signal?: AbortSignal): Promise<Response> {
  try {
    return await fetch(path, {
      ...init, credentials: 'same-origin', cache: 'no-store', redirect: 'error',
      signal: AbortSignal.any([AbortSignal.timeout(12000), ...(signal ? [signal] : [])]),
    });
  } catch {
    throw new ApiError('API_UNAVAILABLE');
  }
}

async function body(response: Response): Promise<unknown> {
  try {
    const value: unknown = await response.json();
    return value;
  } catch {
    throw new ApiError('INVALID_RESPONSE');
  }
}

async function sessionResponse(response: Response): Promise<Session> {
  const value = await body(response);
  if (!response.ok) throw decodeError(value);
  if (!isRecord(value) || value.authenticated !== true || typeof value.csrf_token !== 'string' || !/^[0-9a-f]{64}$/.test(value.csrf_token)) {
    throw new ApiError('INVALID_RESPONSE');
  }
  return { authenticated: true, csrf_token: value.csrf_token };
}

export const api = {
  async providerCatalog(payload: SearchCatalog, csrf: string, signal?: AbortSignal) {
    if (!isUuid(payload.connection_id) || (payload.catalog_command_id != null && !isUuid(payload.catalog_command_id)) || Array.from(payload.query ?? '').length > 256) throw new ApiError('INVALID_INPUT');
    const response = await request('/api/v1/settings/provider-catalog/search', { method: 'POST', headers: {
      'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify(payload) }, signal);
    const value = await body(response); if (!response.ok) throw decodeError(value);
    return decodeProviderCatalog(value, payload);
  },
  async refreshProviderCatalog(payload: RefreshCatalog, csrf: string, signal?: AbortSignal) {
    if (!isUuid(payload.connection_id) || !isUuid(payload.command_id)) throw new ApiError('INVALID_INPUT');
    const response = await request('/api/v1/settings/provider-catalog/refresh', { method: 'POST', headers: {
      'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify(payload) }, signal);
    const value = await body(response); if (!response.ok) throw decodeError(value);
    return decodeProviderCatalog(value, payload);
  },
  async cancelProviderCatalog(payload: CancelCatalog, csrf: string, signal?: AbortSignal) {
    if (!isUuid(payload.connection_id) || !isUuid(payload.command_id) || !isUuid(payload.catalog_command_id)) throw new ApiError('INVALID_INPUT');
    const response = await request('/api/v1/settings/provider-catalog/cancel', { method: 'POST', headers: {
      'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify(payload) }, signal);
    const value = await body(response); if (!response.ok) throw decodeError(value);
    return decodeProviderCatalog(value, payload);
  },
  async startEntryModelTest(payload: EntryTestRequest, csrf: string, signal?: AbortSignal) {
    if (!isUuid(payload.operation_id) || !isUuid(payload.entry_id) || !isUuid(payload.catalog_command_id) || payload.consent !== true) throw new ApiError('INVALID_INPUT');
    const response = await request('/api/v1/model-test/entries', { method: 'PUT', headers: {
      'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify(payload) }, signal);
    const value = await body(response); if (!response.ok) throw decodeError(value);
    const result = decodeEntryTest(value, payload.operation_id);
    if (result.entry_id !== payload.entry_id || result.entry_revision !== payload.expected_entry_revision || result.connection_revision !== payload.expected_connection_revision) throw new ApiError('INVALID_RESPONSE');
    return result;
  },
  async entryModelTest(operationId: string, signal?: AbortSignal) {
    if (!isUuid(operationId)) throw new ApiError('INVALID_INPUT');
    const response = await request(`/api/v1/model-test/entries/${operationId}`, {}, signal);
    const value = await body(response); if (!response.ok) throw decodeError(value);
    return decodeEntryTest(value, operationId);
  },
  async cancelEntryModelTest(operationId: string, commandId: string, revision: number, csrf: string, signal?: AbortSignal) {
    if (!isUuid(operationId) || !isUuid(commandId)) throw new ApiError('INVALID_INPUT');
    const response = await request(`/api/v1/model-test/entries/${operationId}/cancel`, { method: 'POST', headers: {
      'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify({ command_id: commandId, expected_state_revision: revision }) }, signal);
    const value = await body(response); if (!response.ok) throw decodeError(value);
    return decodeEntryTest(value, operationId);
  },
  async providerModels(command: string | null = null, signal?: AbortSignal) {
    if (command !== null && !isUuid(command)) throw new ApiError('INVALID_INPUT');
    const response = await request(command ? `/api/v1/settings/models/commands/${command}` : '/api/v1/settings/models', {}, signal);
    const value = await body(response);
    if (!response.ok) throw decodeError(value);
    return decodeProviderModels(value, command);
  },
  async providerModelPage(revision: number, after: string, signal?: AbortSignal) {
    if (!Number.isSafeInteger(revision) || revision < 1 || !isUuid(after)) throw new ApiError('INVALID_INPUT');
    const response = await request(`/api/v1/settings/models/pages/${revision}/${after}`, {}, signal);
    const value = await body(response);
    if (!response.ok) throw decodeError(value);
    return decodeProviderModels(value, null, revision, after);
  },
  async saveProviderModels(payload: SaveModels, csrf: string, signal?: AbortSignal) {
    const response = await request('/api/v1/settings/models', { method: 'PUT', headers: {
      'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify(payload) }, signal);
    const value = await body(response);
    if (!response.ok) throw decodeError(value);
    return decodeProviderModels(value, payload.command_id);
  },
  async providerKeys(command: string | null = null, signal?: AbortSignal) {
    if (command !== null && !isUuid(command)) throw new ApiError('INVALID_INPUT');
    const response = await request(command ? `/api/v1/settings/providers/commands/${command}` : '/api/v1/settings/providers', {}, signal);
    const value = await body(response);
    if (!response.ok) throw decodeError(value);
    return decodeKeySettings(value, command);
  },
  async saveProviderKeys(payload: KeyCommand, csrf: string, signal?: AbortSignal) {
    const response = await request('/api/v1/settings/providers', { method: 'PUT', headers: {
      'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify(payload) }, signal);
    const value = await body(response);
    if (!response.ok) throw decodeError(value);
    return decodeKeySettings(value, payload.command_id);
  },
  async modelTest(signal?: AbortSignal, operationId: string | null = null) {
    if (operationId !== null && !isUuid(operationId)) throw new ApiError('INVALID_INPUT');
    const response = await request(operationId ? `/api/v1/model-test/${operationId}` : '/api/v1/model-test', {}, signal);
    const value = await body(response);
    if (!response.ok) throw decodeError(value);
    const result = decodeModelTest(value);
    if (operationId !== null && result.operation_id !== operationId) throw new ApiError('INVALID_RESPONSE');
    return result;
  },
  async startModelTest(operationId: string, revision: number, csrf: string, signal?: AbortSignal) {
    if (!isUuid(operationId)) throw new ApiError('INVALID_INPUT');
    const response = await request('/api/v1/model-test', { method: 'PUT', headers: {
      'Content-Type': 'application/json', 'X-CSRF-Token': csrf,
    }, body: JSON.stringify({ operation_id: operationId, expected_selection_revision: revision, consent: true }) }, signal);
    const value = await body(response);
    if (!response.ok) throw decodeError(value);
    const result = decodeModelTest(value);
    if (result.operation_id !== operationId) throw new ApiError('INVALID_RESPONSE');
    return result;
  },
  async modelCapabilities(commandId: string, signal?: AbortSignal) {
    if (!isUuid(commandId)) throw new ApiError('INVALID_INPUT');
    const response = await request(`/api/v1/model-test/capabilities/${commandId}`, {}, signal);
    const value = await body(response); if (!response.ok) throw decodeError(value);
    const result = decodeModelTest(value);
    if (result.metadata_command_id !== commandId || result.operation_id !== null) throw new ApiError('INVALID_RESPONSE');
    return result;
  },
  async refreshModelCapabilities(commandId: string, revision: number, csrf: string) {
    if (!isUuid(commandId)) throw new ApiError('INVALID_INPUT');
    const response = await request('/api/v1/model-test/capabilities', { method: 'POST', headers: {
      'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify({ command_id: commandId, expected_selection_revision: revision }) });
    const value = await body(response); if (!response.ok) throw decodeError(value);
    const result = decodeModelTest(value);
    if (result.metadata_command_id !== commandId || result.operation_id !== null) throw new ApiError('INVALID_RESPONSE');
    return result;
  },
  async cancelModelTest(operationId: string, commandId: string, revision: number, csrf: string) {
    if (!isUuid(operationId) || !isUuid(commandId)) throw new ApiError('INVALID_INPUT');
    const response = await request(`/api/v1/model-test/${operationId}/cancel`, { method: 'POST', headers: {
      'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify({ command_id: commandId, expected_state_revision: revision }) });
    const value = await body(response); if (!response.ok) throw decodeError(value);
    const result = decodeModelTest(value);
    if (result.operation_id !== operationId) throw new ApiError('INVALID_RESPONSE');
    return result;
  },
  async catalog(after: string | null, signal?: AbortSignal) {
    if (after !== null && !isUuid(after)) throw new ApiError('INVALID_INPUT');
    const response = await request(after ? `/api/v1/settings/catalog/page/${after}` : '/api/v1/settings/catalog', {}, signal);
    const value = await body(response);
    if (!response.ok) throw decodeError(value);
    return decodeCatalogPage(value);
  },
  async catalogPublication(id: string, digest: string, signal?: AbortSignal) {
    if (!catalogSelection(id, digest)) throw new ApiError('INVALID_INPUT');
    const response = await request(`/api/v1/settings/catalog/publications/${id}/${digest}`, {}, signal);
    const value = await body(response);
    if (!response.ok) throw decodeError(value);
    return decodeCatalogInspection(value, id, digest);
  },
  async providerCommand(payload: ProviderCommand, csrf: string, signal?: AbortSignal) {
    const response = await request('/api/v1/settings/provider', { method: 'PUT', headers: {
      'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify(payload) }, signal);
    const value = await body(response);
    if (!response.ok) throw decodeError(value);
    return decodeProvider(value, payload.operation_id);
  },
  async providerOperation(id: string, signal?: AbortSignal) {
    if (!isUuid(id) && id !== 'current') throw new ApiError('INVALID_INPUT');
    const response = await request(`/api/v1/settings/provider/operations/${id}`, {}, signal);
    const value = await body(response);
    if (!response.ok) throw decodeError(value);
    if (id === 'current') {
      if (!isRecord(value) || typeof value.operation_id !== 'string') throw new ApiError('INVALID_RESPONSE');
      return decodeProvider(value, value.operation_id);
    }
    return decodeProvider(value, id);
  },
  async draft(id: string, signal?: AbortSignal) {
    if (!isUuid(id)) throw new ApiError('INVALID_INPUT');
    const response = await request(`/api/v1/engagements/${id}`, {}, signal);
    const value = await body(response);
    if (!response.ok) throw decodeError(value);
    return decodeRevision(value, id);
  },
  async createDraft(payload: Draft, csrf: string, signal?: AbortSignal) {
    const response = await request('/api/v1/engagements', { method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify(payload) }, signal);
    const value = await body(response);
    if (!response.ok) throw decodeError(value);
    if (response.status !== 201) throw new ApiError('INVALID_RESPONSE');
    return decodeRevision(value);
  },
  async updateDraft(id: string, payload: Draft, revision: number, digest: string, commandId: string, csrf: string, signal?: AbortSignal) {
    if (!isUuid(id) || !isUuid(commandId) || !Number.isSafeInteger(revision) || revision < 1 ||
      !/^[0-9a-f]{64}$/.test(digest)) throw new ApiError('INVALID_INPUT');
    const response = await request(`/api/v1/engagements/${id}`, { method: 'PUT', headers: {
      'Content-Type': 'application/json', 'X-CSRF-Token': csrf, 'If-Match': `"rev-${revision}-${digest}"`, 'X-Command-ID': commandId,
    }, body: JSON.stringify(payload) }, signal);
    const value = await body(response);
    if (!response.ok) throw decodeError(value);
    if (response.status !== 200) throw new ApiError('INVALID_RESPONSE');
    const written = decodeRevision(value, id);
    if (written.revision !== revision + 1) throw new ApiError('INVALID_RESPONSE');
    return written;
  },
  async engagement(id: string, signal?: AbortSignal) {
    if (!isUuid(id)) throw new ApiError('INVALID_INPUT');
    const response = await request(`/api/v1/engagements/${id}`, {}, signal);
    const value = await body(response);
    if (!response.ok) throw decodeError(value);
    return decodeSelectedDraft(value, id);
  },
  async dashboard(after: string | null, signal?: AbortSignal) {
    if (after !== null && !isDashboardCursor(after)) throw new ApiError('INVALID_INPUT');
    const query = new URLSearchParams({ limit: '20' });
    if (after !== null) query.set('after', after);
    const response = await request(`/api/v1/dashboard?${query}`, {}, signal);
    const value = await body(response);
    if (!response.ok) throw decodeError(value);
    return decodeProjection(value);
  },
  async health(signal?: AbortSignal) {
    const response = await request('/health/ready', {}, signal);
    const value = await body(response);
    if (response.status !== 200 && response.status !== 503) throw decodeError(value);
    return decodeHealth(value);
  },
  async instance(signal?: AbortSignal) {
    const response = await request('/api/instance', {}, signal);
    const value = await body(response);
    if (!response.ok) throw decodeError(value);
    return decodeInstance(value);
  },
  async session(signal?: AbortSignal): Promise<Session | null> {
    try {
      return await sessionResponse(await request('/api/session', {}, signal));
    } catch (error) {
      if (error instanceof ApiError && error.code === 'UNAUTHENTICATED') return null;
      throw error;
    }
  },
  async pair(code: string): Promise<Session> {
    const payload: components['schemas']['PairingBody'] = { code };
    return sessionResponse(await request('/api/pairing', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    }));
  },
  async logout(csrf: string): Promise<void> {
    const response = await request('/api/logout', { method: 'POST', headers: { 'X-CSRF-Token': csrf } });
    if (response.status === 204) return;
    if (!response.ok) throw decodeError(await body(response));
    throw new ApiError('INVALID_RESPONSE');
  },
};
