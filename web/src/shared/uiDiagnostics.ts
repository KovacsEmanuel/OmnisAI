import type { components } from './api/generated';
import { errorCopy, isRecord, isUuid } from './api/errors';
import type { ErrorCode } from './api/errors';

type Event = components['schemas']['UiEvent'];
type Surface = Event['surface'];
type Site = Event['site'];
type Metadata = Pick<Event, 'site' | 'action' | 'outcome'> & Partial<Pick<Event, 'surface' | 'error_code' | 'correlation_id' | 'run_id' | 'command_id'>>;
type Observation = (metadata: Metadata) => void;
const endpoint = '/api/v1/diagnostics/ui-events';
const states = ['RECORDED', 'RATE_LIMITED', 'BUDGET_EXHAUSTED', 'BUSY', 'UNAVAILABLE', 'BACKPRESSURED'];
let current: { emit: Observation; surface: Surface } | null = null;

export function diagnosticSurface(path: string): Surface {
  if (path.startsWith('/settings/')) return 'settings';
  if (path === '/engagements/new' || /^\/engagements\/[0-9a-f-]{36}\/setup$/.test(path)) return 'engagement_setup';
  if (/^\/engagements\/[0-9a-f-]{36}\/stream$/.test(path)) return 'brain_stream';
  if (/^\/engagements\/[0-9a-f-]{36}(?:\/overview)?$/.test(path)) return 'engagement_overview';
  return path === '/pair' ? 'bootstrap' : 'dashboard';
}

export function bindDiagnostics(csrf: string, admit: (send: () => void) => boolean, signal: AbortSignal) {
  const seen = new Map<string, number>();
  let pending = 0, total = 0, active = true;
  const bound = { surface: diagnosticSurface(window.location.pathname), emit };
  current = bound;
  function emit(metadata: Metadata) {
    const now = performance.now();
    const key = JSON.stringify([metadata.surface ?? bound.surface, metadata.site, metadata.action, metadata.outcome, metadata.error_code]);
    const previous = seen.get(key);
    if (!active || signal.aborted || pending >= 2 || total >= 64 || (previous !== undefined && (metadata.action === 'ERROR' || now - previous < 1000))) return;
    if ((metadata.run_id != null && !isUuid(metadata.run_id)) || (metadata.command_id != null && !isUuid(metadata.command_id)) || (metadata.correlation_id != null && !isUuid(metadata.correlation_id)) || (metadata.error_code != null && !Object.hasOwn(errorCopy, metadata.error_code))) return;
    let request: Promise<Response> | undefined;
    let event: Event | undefined;
    try {
      if (!admit(() => {
        event = { version: 1, source: 'browser_untrusted', event_id: crypto.randomUUID(), surface: metadata.surface ?? bound.surface,
          site: metadata.site, action: metadata.action, outcome: metadata.outcome,
          error_code: metadata.error_code ?? null, correlation_id: metadata.correlation_id ?? null,
          run_id: metadata.run_id ?? null, command_id: metadata.command_id ?? null };
        total += 1; pending += 1; seen.set(key, now);
        request = fetch(endpoint, { method: 'POST', credentials: 'same-origin', redirect: 'error', cache: 'no-store',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify(event),
          signal: AbortSignal.any([signal, AbortSignal.timeout(750)]) });
      })) return;
    } catch { pending = Math.max(0, pending - 1); return; } // No diagnostic failure can escape to a control.
    const sent = event;
    if (!request || !sent) return;
    void request.then(async response => {
      const value: unknown = await response.json();
      // Accepted is not recorded, and neither means a domain command succeeded.
      return response.status === 202 && isRecord(value) && Object.keys(value).length === 4 && value.version === 1 &&
        value.event_id === sent.event_id && value.accepted === true && typeof value.state === 'string' && states.includes(value.state) && value.state === 'RECORDED';
    }).catch(() => false).finally(() => { pending -= 1; });
  }
  return () => { active = false; if (current === bound) current = null; };
}

export function captureObservation(): Observation {
  const bound = current;
  const surface = bound?.surface;
  return metadata => { try { if (bound && surface) bound.emit({ ...metadata, surface }); } catch { return; } };
}

export function observeControl(site: Site, ids: Pick<Partial<Event>, 'run_id' | 'command_id'> = {}, surface?: Surface) {
  try {
    if (current && surface) current.surface = surface;
    current?.emit({ site, action: 'OBSERVE', outcome: 'OBSERVED', ...ids });
  } catch { return; } // Observation failure must never become an action failure.
}

export function httpObservation(path: string, method: string): Observation | null {
  if (path === endpoint) return null;
  const clean = path.split('?')[0] ?? '';
  if (!clean.startsWith('/api/') && clean !== '/health/ready') return null;
  let site: Site = 'http_read';
  let run: string | undefined, command: string | undefined;
  if (clean.startsWith('/api/v1/model-test')) site = 'model_request';
  else if (clean.startsWith('/api/v1/settings/provider-catalog/')) site = 'provider_catalog_search';
  else if (clean.startsWith('/api/v1/settings/')) site = 'provider_request';
  else if (method !== 'GET' && /^\/api\/v1\/engagements(?:\/[0-9a-f-]{36})?$/.test(clean)) site = 'draft_save';
  else if (/^\/api\/v1\/runs\/commands\/[0-9a-f-]{36}$/.test(clean)) { site = 'command_receipt'; command = clean.split('/').at(-1); }
  else if (/^\/api\/v1\/runs\/[0-9a-f-]{36}\/commands$/.test(clean)) { site = 'run_command'; run = clean.split('/')[4]; }
  const observe = captureObservation();
  return metadata => observe({ ...metadata, site, run_id: run ?? null, command_id: command ?? null });
}

export function reportTypedError(observe: Observation, code: ErrorCode, correlation?: string) {
  observe({ site: 'http_read', action: 'ERROR', outcome: 'REFUSED', error_code: code, correlation_id: correlation ?? null });
}
