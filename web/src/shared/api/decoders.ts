import type { components } from './generated';
import { ApiError, isRecord, isUuid } from './errors';

type Health = components['schemas']['HealthReady'];
type Instance = components['schemas']['InstanceView'];

function isRevision(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
}

function isDatabaseReason(value: unknown): value is Health['reason'] {
  return value === null || value === 'DATABASE_UNAVAILABLE' || value === 'SCHEMA_INCOMPATIBLE';
}

function isDashboardReason(value: unknown): value is Health['dashboard_reason'] {
  return isDatabaseReason(value) || value === 'ASSETS_UNAVAILABLE' || value === 'CONTROL_UNAVAILABLE';
}

export function decodeHealth(value: unknown): Health {
  if (!isRecord(value) || typeof value.api_ready !== 'boolean' || typeof value.dashboard_ready !== 'boolean' || typeof value.assessment_ready !== 'boolean' || !isDatabaseReason(value.reason) || !isDashboardReason(value.dashboard_reason)) {
    throw new ApiError('INVALID_RESPONSE');
  }
  if (value.api_ready !== (value.reason === null) || value.dashboard_ready !== (value.dashboard_reason === null) || (value.dashboard_ready && !value.api_ready)) {
    throw new ApiError('INVALID_RESPONSE');
  }
  return { api_ready: value.api_ready, dashboard_ready: value.dashboard_ready,
    assessment_ready: value.assessment_ready, reason: value.reason, dashboard_reason: value.dashboard_reason };
}

export function decodeInstance(value: unknown): Instance {
  if (!isRecord(value) || !isUuid(value.instance_id) || !isRevision(value.generation) || !isRevision(value.supervisor_epoch) || typeof value.admission_open !== 'boolean' || typeof value.supervisor_ready !== 'boolean' || typeof value.shutdown_finalized !== 'boolean' || typeof value.assessment_ready !== 'boolean' || typeof value.dashboard_ready !== 'boolean' || !(value.shutdown_command_id === null || isUuid(value.shutdown_command_id)) || !(value.quiesced_generation === null || isRevision(value.quiesced_generation))) {
    throw new ApiError('INVALID_RESPONSE');
  }
  return { instance_id: value.instance_id, generation: value.generation,
    admission_open: value.admission_open, supervisor_ready: value.supervisor_ready,
    supervisor_epoch: value.supervisor_epoch, shutdown_finalized: value.shutdown_finalized,
    shutdown_command_id: value.shutdown_command_id, quiesced_generation: value.quiesced_generation,
    assessment_ready: value.assessment_ready, dashboard_ready: value.dashboard_ready };
}
