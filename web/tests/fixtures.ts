import type { components } from '../src/shared/api/generated';

// Synthetic, component-test-only DTOs. Never imported by the product entrypoint.
export const session: components['schemas']['SessionView'] = { authenticated: true, csrf_token: 'a'.repeat(64) };
export const health: components['schemas']['HealthReady'] = {
  api_ready: true, dashboard_ready: true, assessment_ready: false,
  reason: null, dashboard_reason: null,
};
export const instance: components['schemas']['InstanceView'] = {
  instance_id: '00000000-0000-4000-8000-000000000001', generation: 0,
  admission_open: false, shutdown_command_id: null, quiesced_generation: null,
  supervisor_epoch: 1, supervisor_ready: true, shutdown_finalized: false,
  assessment_ready: false, dashboard_ready: true,
};
