import type { components } from './generated';
import { ApiError, isRecord, isUuid } from './errors';

export type ProviderModels = components['schemas']['ModelRegistryView'];
export type SaveModels = components['schemas']['SaveModels'];
const revision = (value: unknown, minimum = 1): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= minimum;
const keys = (value: Record<string, unknown>, names: string[]) => Object.keys(value).length === names.length && names.every(name => Object.hasOwn(value, name));

export function decodeProviderModels(value: unknown, command: string | null, registryRevision: number | null = null, after: string | null = null): ProviderModels {
  if (!isRecord(value) || !keys(value, ['schema_version', 'command_id', 'registry_revision', 'after', 'next_after', 'total', 'entries']) ||
    value.schema_version !== 1 || value.command_id !== command || (command !== null && !isUuid(command)) || value.after !== after ||
    (after !== null && (registryRevision === null || command !== null)) ||
    !revision(value.registry_revision, 0) || (registryRevision !== null && value.registry_revision !== registryRevision) ||
    !revision(value.total, 0) || value.total > 64 || (value.total > 0 && value.registry_revision === 0) ||
    !Array.isArray(value.entries) || value.entries.length > 16 || value.entries.length > value.total ||
    (after === null ? value.entries.length !== Math.min(16, value.total) : !isUuid(after) || value.entries.length === 0) ||
    (value.next_after !== null && !isUuid(value.next_after))) throw new ApiError('INVALID_RESPONSE');
  const entries = value.entries.map((item): components['schemas']['ModelEntry'] => {
    if (!isRecord(item) || !keys(item, ['entry_id', 'revision', 'connection_id', 'connection_revision', 'model', 'output_tokens']) ||
      !isUuid(item.entry_id) || !revision(item.revision) || !isUuid(item.connection_id) || !revision(item.connection_revision) ||
      typeof item.model !== 'string' || item.model.length < 1 || item.model.length > 256 || /[^!-~]/.test(item.model) ||
      !revision(item.output_tokens) || item.output_tokens > 65536) throw new ApiError('INVALID_RESPONSE');
    return { entry_id: item.entry_id, revision: item.revision, connection_id: item.connection_id,
      connection_revision: item.connection_revision, model: item.model, output_tokens: item.output_tokens };
  });
  if (entries.some((item, index) => (item.entry_id <= (entries[index - 1]?.entry_id ?? '')) || (after !== null && item.entry_id <= after)) ||
    new Set(entries.map(item => JSON.stringify([item.connection_id, item.model]))).size !== entries.length ||
    (value.next_after !== null && (entries.length !== 16 || value.next_after !== entries.at(-1)?.entry_id || value.total <= entries.length)) ||
    (after === null && (value.total > 16) !== (value.next_after !== null))) throw new ApiError('INVALID_RESPONSE');
  return { schema_version: 1, command_id: command, registry_revision: value.registry_revision,
    after, next_after: value.next_after, total: value.total, entries };
}
