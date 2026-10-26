import type { components } from './generated';
import { ApiError, isRecord, isUuid } from './errors';

export type CatalogView = components['schemas']['CatalogView'];
export type SearchCatalog = components['schemas']['SearchCatalog'];
export type RefreshCatalog = components['schemas']['RefreshCatalog'];
export type CancelCatalog = components['schemas']['CancelCatalog'];
const reasons = ['SCHEMA_UNSUPPORTED', 'CONTINUATION_UNSUPPORTED', 'TOTAL_MISMATCH', 'CATALOG_LIMIT', 'METADATA_UNAVAILABLE', 'CANCELLED_OR_STOPPED', 'OWNER_LOST', 'CONNECTION_STALE', 'ROW_UNSUPPORTED'] as const;
const revision = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= 1;
const bounded = (value: unknown, maximum: number): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 && value <= maximum;
const keys = (value: Record<string, unknown>, names: string[]) => Object.keys(value).length === names.length && names.every(name => Object.hasOwn(value, name));
function reason(value: unknown): NonNullable<CatalogView['reason']> | null {
  if (value === null) return null;
  const result = reasons.find(item => item === value);
  if (result === undefined) throw new ApiError('INVALID_RESPONSE');
  return result;
}
export function decodeProviderCatalog(value: unknown, request: SearchCatalog | RefreshCatalog | CancelCatalog): CatalogView {
  const command = request.action === 'refresh' ? request.command_id : request.catalog_command_id;
  const query = request.action === 'search' ? request.query ?? '' : '';
  const offset = request.action === 'search' ? request.offset ?? 0 : 0;
  if (!isRecord(value) || !keys(value, ['schema_version', 'connection_id', 'connection_revision', 'provider', 'catalog_command_id', 'state', 'reason', 'query', 'offset', 'next_offset', 'total', 'entries']) || value.schema_version !== 1 ||
    !isUuid(value.connection_id) || value.connection_id !== request.connection_id || !revision(value.connection_revision) || value.connection_revision !== request.connection_revision ||
    (value.provider !== 'openrouter' && value.provider !== 'orcarouter') || (value.catalog_command_id !== null && !isUuid(value.catalog_command_id)) ||
    (command != null && value.catalog_command_id !== command) || value.query !== query || Array.from(query).length > 256 || value.offset !== offset || !bounded(offset, 8192) || offset % 16 !== 0 ||
    !bounded(value.total, 8192) || !Array.isArray(value.entries) || value.entries.length !== Math.min(16, Math.max(0, value.total - offset))) throw new ApiError('INVALID_RESPONSE');
  const state = (['NOT_REQUESTED', 'PENDING', 'READY', 'PARTIAL', 'FAILED', 'STALE'] as const).find(item => item === value.state);
  if (state === undefined || (state === 'NOT_REQUESTED' ? value.catalog_command_id !== null : state !== 'STALE' && value.catalog_command_id === null) ||
    (!['READY', 'PARTIAL'].includes(state) && value.total !== 0) ||
    value.next_offset !== (offset + value.entries.length < value.total ? offset + 16 : null)) throw new ApiError('INVALID_RESPONSE');
  const entries = value.entries.map((item): components['schemas']['CatalogModel'] => {
    if (!isRecord(item) || !keys(item, ['model', 'name', 'max_output_tokens', 'supports_max_tokens', 'reason']) || typeof item.model !== 'string' || item.model.length < 1 || item.model.length > 256 || /[^!-~]/.test(item.model) ||
      (item.name !== null && (typeof item.name !== 'string' || Array.from(item.name).length > 128)) ||
      (item.max_output_tokens !== null && (!revision(item.max_output_tokens) || item.max_output_tokens > 65536)) ||
      (item.supports_max_tokens !== null && typeof item.supports_max_tokens !== 'boolean')) throw new ApiError('INVALID_RESPONSE');
    return { model: item.model, name: item.name, max_output_tokens: item.max_output_tokens, supports_max_tokens: item.supports_max_tokens, reason: reason(item.reason) };
  });
  if (entries.some((item, i) => i > 0 && item.model <= (entries[i - 1]?.model ?? ''))) throw new ApiError('INVALID_RESPONSE');
  const reasonCode = reason(value.reason);
  if ((['READY', 'PENDING', 'NOT_REQUESTED'].includes(state) && reasonCode !== null) || (['PARTIAL', 'FAILED', 'STALE'].includes(state) && reasonCode === null)) throw new ApiError('INVALID_RESPONSE');
  return { schema_version: 1, connection_id: value.connection_id, connection_revision: value.connection_revision, provider: value.provider,
    catalog_command_id: value.catalog_command_id, state,
    reason: reasonCode, query, offset, next_offset: value.next_offset === null ? null : offset + 16, total: value.total, entries };
}
