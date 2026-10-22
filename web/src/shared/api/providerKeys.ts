import type { components } from './generated';
import { ApiError, isRecord, isUuid } from './errors';

export type KeySettings = components['schemas']['KeySettingsView'];
export type KeySelection = components['schemas']['ModelSelection'];
export type KeyCommand = components['schemas']['SaveConnection'] | components['schemas']['RevokeConnection'] | components['schemas']['SaveSelection'];
export const roles = ['default', 'brain', 'investigator', 'validator'] as const;
export const printable = (value: string, maximum: number) => value.length >= 1 && value.length <= maximum && /^[!-~]+$/.test(value);
const revision = (value: unknown, minimum = 1): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= minimum;
const keys = (value: Record<string, unknown>, names: string[]) => Object.keys(value).length === names.length && names.every(name => Object.hasOwn(value, name));
function selection(value: unknown): KeySelection {
  if (!isRecord(value) || !keys(value, ['connection_id', 'connection_revision', 'model', 'output_tokens']) ||
    !isUuid(value.connection_id) || !revision(value.connection_revision) || typeof value.model !== 'string' ||
    !printable(value.model, 256) || !revision(value.output_tokens) || value.output_tokens > 65536) throw new ApiError('INVALID_RESPONSE');
  return { connection_id: value.connection_id, connection_revision: value.connection_revision, model: value.model, output_tokens: value.output_tokens };
}
export function decodeKeySettings(value: unknown, command: string | null): KeySettings {
  if (!isRecord(value) || !keys(value, ['schema_version', 'command_id', 'vault_status', 'connections', 'selection', 'reachable']) ||
    value.schema_version !== 2 || value.command_id !== command || (command !== null && !isUuid(command)) ||
    (value.vault_status !== 'LOCKED' && value.vault_status !== 'UNLOCKED' && value.vault_status !== 'UNCONFIGURED') ||
    value.reachable !== 'NOT_VERIFIED' || !Array.isArray(value.connections) || value.connections.length > 2) throw new ApiError('INVALID_RESPONSE');
  const connections = value.connections.map((item): components['schemas']['ConnectionView'] => {
    if (!isRecord(item) || !keys(item, ['connection_id', 'provider', 'revision', 'enabled', 'credential_present']) ||
      !isUuid(item.connection_id) || !revision(item.revision) || (item.provider !== 'openrouter' && item.provider !== 'orcarouter') ||
      typeof item.enabled !== 'boolean' || typeof item.credential_present !== 'boolean') throw new ApiError('INVALID_RESPONSE');
    return { connection_id: item.connection_id, provider: item.provider, revision: item.revision, enabled: item.enabled, credential_present: item.credential_present };
  });
  if (new Set(connections.map(item => item.provider)).size !== connections.length || new Set(connections.map(item => item.connection_id)).size !== connections.length) throw new ApiError('INVALID_RESPONSE');
  let selected: KeySettings['selection'] = null;
  if (value.selection !== null) {
    const item = value.selection;
    if (!isRecord(item) || !keys(item, ['selection_id', 'revision', ...roles]) || !isUuid(item.selection_id) || !revision(item.revision)) throw new ApiError('INVALID_RESPONSE');
    selected = { selection_id: item.selection_id, revision: item.revision, default: selection(item.default),
      brain: item.brain === null ? null : selection(item.brain), investigator: item.investigator === null ? null : selection(item.investigator), validator: item.validator === null ? null : selection(item.validator) };
  }
  return { schema_version: 2, command_id: command, vault_status: value.vault_status, reachable: 'NOT_VERIFIED', connections, selection: selected };
}
