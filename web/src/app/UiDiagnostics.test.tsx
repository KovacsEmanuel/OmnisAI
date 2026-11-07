import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import { health, session, instance } from '../../tests/fixtures';
import { syntheticRun, syntheticSummary, syntheticAttempt, inspection } from '../../tests/run-fixtures';
import { draft, id, projection } from '../../tests/projection-fixtures';
import { payload } from '../../tests/draft-fixtures';
import { api } from '../shared/api/client';
import { ApiError, isRecord } from '../shared/api/errors';
import { bindDiagnostics, observeControl } from '../shared/uiDiagnostics';
import { remember, sessionScope } from '../features/engagement/SettingsModels';
import { App } from './App';

vi.unmock('../shared/uiDiagnostics');
afterEach(() => { vi.restoreAllMocks(); });
const endpoint = '/api/v1/diagnostics/ui-events';

it('preserves malformed response header correlation and emits finite metadata, not request contents', async () => {
  const correlation = syntheticRun.run_id;
  const events: object[] = [];
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (path, init) => {
    if (String(path) === endpoint) {
      const event: unknown = JSON.parse(String(init?.body));
      if (!event || typeof event !== 'object' || !('event_id' in event)) throw new Error('Missing event');
      events.push(event);
      return Response.json({ version: 1, accepted: true, state: 'RECORDED', event_id: event.event_id }, { status: 202 });
    }
    return new Response('not JSON', { status: 503, headers: { 'X-Correlation-ID': correlation } });
  }));
  const controller = new AbortController();
  const detach = bindDiagnostics(session.csrf_token, callback => { callback(); return true; }, controller.signal);
  await expect(api.updateDraft(syntheticRun.engagement_id, payload, 1, 'a'.repeat(64), correlation, session.csrf_token)).rejects.toMatchObject({ code: 'INVALID_RESPONSE', correlation });
  await waitFor(() => expect(events.length).toBeGreaterThan(0));
  expect(JSON.stringify(events)).not.toContain(session.csrf_token);
  expect(JSON.stringify(events)).not.toContain('not JSON');
  expect(events).toContainEqual(expect.objectContaining({ site: 'draft_save', action: 'ERROR', outcome: 'UNCONFIRMED', error_code: 'INVALID_RESPONSE', correlation_id: correlation }));
  detach(); controller.abort();
});

it('never adopts stale HTTP observations into a new session and never retries diagnostics', async () => {
  let current = true;
  const sent: string[] = [];
  let release: ((response: Response) => void) | undefined;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (path) => {
    if (String(path) === endpoint) { sent.push(String(path)); throw new Error('Synthetic unavailable sink'); }
    return new Promise(resolve => { release = resolve; });
  }));
  const controller = new AbortController();
  const detach = bindDiagnostics(session.csrf_token, callback => { if (!current) return false; callback(); return true; }, controller.signal);
  const old = api.activeRun().catch((error: unknown) => error);
  current = false; detach(); controller.abort();
  const next = new AbortController();
  const detachNext = bindDiagnostics(session.csrf_token, callback => { callback(); return true; }, next.signal);
  release?.(new Response('invalid', { status: 503, headers: { 'X-Correlation-ID': syntheticRun.run_id } }));
  expect(await old).toBeInstanceOf(ApiError);
  expect(sent).toHaveLength(0);
  observeControl('theme_toggle');
  await waitFor(() => expect(sent).toHaveLength(1));
  await new Promise(resolve => setTimeout(resolve, 30));
  expect(sent).toHaveLength(1);
  detachNext(); next.abort();
});

it.each(['hanging', 'unavailable', 'recorded-lost', 'recorded-recovery'] as const)('actual App controls keep exact global Stop/recovery independent of %s diagnostics', async mode => {
  sessionStorage.clear();
  const domain: object[] = [], observations: object[] = [];
  const correlation = syntheticRun.setup_ref.id;
  let receiptReads = 0;
  if (mode === 'recorded-recovery') remember('omnis-run-stop', await sessionScope(session.csrf_token), { run: syntheticRun.run_id, command: syntheticAttempt.attempt_id });
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input);
    if (path === endpoint) {
      const event: unknown = JSON.parse(String(init?.body));
      if (!isRecord(event) || typeof event.event_id !== 'string') throw new Error('Missing event');
      observations.push(event);
      if (mode === 'unavailable') throw new Error('Synthetic logger outage');
      if (mode === 'hanging') return new Promise(() => {});
      return Response.json({ version: 1, event_id: event.event_id, accepted: true, state: 'RECORDED' }, { status: 202 });
    }
    if (init?.method === 'POST') {
      const body: unknown = JSON.parse(String(init.body));
      if (!body || typeof body !== 'object' || !('command_id' in body)) throw new Error('Invalid command');
      domain.push(body);
      // Let diagnostic acknowledgements settle before the controlled domain outcome.
      await new Promise(resolve => setTimeout(resolve, 0));
      if (mode !== 'hanging') throw new Error('Synthetic lost Stop reply');
      return Response.json({ command_id: body.command_id, run_id: syntheticRun.run_id, setup_ref: null, state: 'ADMITTED', revision: 8 });
    }
    if (path.startsWith('/api/v1/runs/commands/')) {
      receiptReads++;
      await new Promise(resolve => setTimeout(resolve, 0));
      return Response.json({ command_id: path.split('/').at(-1), run_id: syntheticRun.run_id, setup_ref: null, state: 'ADMITTED', revision: 8 }, { headers: { 'X-Correlation-ID': correlation } });
    }
    return Response.json(path === '/api/session' ? session : path === '/health/ready' ? health : path === '/api/instance' ? instance : path.startsWith('/api/v1/dashboard?') ? projection : path === `/api/v1/engagements/${id}` ? draft : path === '/api/v1/runs/active' ? syntheticRun : null);
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><MemoryRouter><App /></MemoryRouter></QueryClientProvider>);
  const stop = await screen.findByRole('button', { name: 'Stop active run' });
  if (mode !== 'recorded-recovery') await waitFor(() => expect(stop).toBeEnabled());
  await userEvent.setup().click(screen.getByRole('button', { name: /Light theme|Dark theme/ }));
  if (mode !== 'recorded-recovery') {
    await userEvent.setup().click(stop);
    await waitFor(() => expect(domain).toHaveLength(1));
    expect(domain[0]).toMatchObject({ action: 'stop', run_id: syntheticRun.run_id, expected_revision: 7, expected_generation: 3 });
  }
  if (mode !== 'hanging') {
    const recover = await screen.findByRole('button', { name: /^Read Stop receipt/ });
    await waitFor(() => expect(recover).toBeEnabled());
    if (mode === 'recorded-lost') expect(observations).toContainEqual(expect.objectContaining({ site: 'run_command', action: 'ERROR', error_code: 'API_UNAVAILABLE', outcome: 'UNCONFIRMED', correlation_id: null }));
    await userEvent.setup().click(recover);
    await screen.findByText(/ADMITTED · Stop run/);
    expect(domain).toHaveLength(mode === 'recorded-recovery' ? 0 : 1);
    expect(receiptReads).toBe(1);
    if (mode.startsWith('recorded')) {
      const command = mode === 'recorded-recovery' ? syntheticAttempt.attempt_id : isRecord(domain[0]) ? domain[0].command_id : null;
      expect(observations).toContainEqual(expect.objectContaining({ site: 'command_receipt', action: 'REQUEST', outcome: 'UNCONFIRMED', command_id: command, correlation_id: null }));
      expect(observations).toContainEqual(expect.objectContaining({ site: 'command_receipt', action: 'RESPONSE', outcome: 'UNCONFIRMED', command_id: command, correlation_id: correlation }));
      expect(observations).not.toContainEqual(expect.objectContaining({ outcome: 'REFUSED' }));
    }
  }
  expect(observations.length).toBeLessThanOrEqual(mode === 'hanging' ? 2 : 64);
  expect(observations).toContainEqual(expect.objectContaining({ site: 'theme_toggle', action: 'OBSERVE' }));
  expect(JSON.stringify(observations)).not.toContain(session.csrf_token);
  view.unmount(); client.clear(); sessionStorage.clear();
});

it.each(['valid-header', 'invalid-header'] as const)('observes only explicit receipt GET, not successful polling, with %s correlation', async kind => {
  const events: object[] = [];
  const command = syntheticAttempt.attempt_id, correlation = syntheticRun.setup_ref.id;
  const transport = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === endpoint) {
      const value: unknown = JSON.parse(String(init?.body));
      if (!isRecord(value)) throw new Error('Missing event');
      events.push(value);
      return Response.json({ version: 1, event_id: value.event_id, accepted: true, state: 'RECORDED' }, { status: 202 });
    }
    await new Promise(resolve => setTimeout(resolve, 0));
    return Response.json(String(input).endsWith(command) ? { command_id: command, run_id: syntheticRun.run_id, setup_ref: null, state: 'ADMITTED', revision: 8 } : null,
      { headers: { 'X-Correlation-ID': kind === 'valid-header' ? correlation : 'synthetic_invalid_header_not_for_log' } });
  });
  vi.stubGlobal('fetch', transport);
  const controller = new AbortController();
  const detach = bindDiagnostics(session.csrf_token, callback => { callback(); return true; }, controller.signal);
  await api.activeRun();
  expect(events).toEqual([]);
  await expect(api.runCommandReceipt(command)).resolves.toMatchObject({ state: 'ADMITTED' });
  expect(events).toEqual([
    expect.objectContaining({ site: 'command_receipt', command_id: command, action: 'REQUEST', outcome: 'UNCONFIRMED', correlation_id: null }),
    expect.objectContaining({ site: 'command_receipt', command_id: command, action: 'RESPONSE', outcome: 'UNCONFIRMED', correlation_id: kind === 'valid-header' ? correlation : null }),
  ]);
  expect(transport.mock.calls.filter(([input]) => String(input).endsWith(command))).toHaveLength(1);
  expect(JSON.stringify(events)).not.toContain('synthetic_invalid_header_not_for_log');
  detach(); controller.abort();
});

it('bounds pending transport and aborts at cutover without retry or resend', async () => {
  const signals: AbortSignal[] = [];
  const transport = vi.fn<typeof fetch>().mockImplementation(async (_path, init) => {
    if (init?.signal) signals.push(init.signal);
    return new Promise(() => {});
  });
  vi.stubGlobal('fetch', transport);
  const timeout = vi.spyOn(AbortSignal, 'timeout');
  const controller = new AbortController();
  const detach = bindDiagnostics(session.csrf_token, callback => { callback(); return true; }, controller.signal);
  observeControl('theme_toggle'); observeControl('theme_toggle');
  observeControl('navigation'); observeControl('period_toggle');
  expect(transport).toHaveBeenCalledTimes(2);
  expect(timeout).toHaveBeenCalledWith(750);
  controller.abort(); detach();
  expect(signals.every(signal => signal.aborted)).toBe(true);
  observeControl('inspector_open');
  expect(transport).toHaveBeenCalledTimes(2);
});

it('caps a settled session at 64 attempts including refused acknowledgements without retries', async () => {
  let now = 0;
  vi.spyOn(performance, 'now').mockImplementation(() => now);
  const transport = vi.fn<typeof fetch>().mockImplementation(async () => Response.json({ accepted: true, state: 'RECORDED' }, { status: 503 }));
  vi.stubGlobal('fetch', transport);
  const controller = new AbortController();
  const detach = bindDiagnostics(session.csrf_token, callback => { callback(); return true; }, controller.signal);
  for (let i = 0; i < 70; i++) {
    now += 1001;
    observeControl('theme_toggle');
    await waitFor(() => expect(transport).toHaveBeenCalledTimes(Math.min(i + 1, 64)));
    await new Promise(resolve => setTimeout(resolve, 0));
  }
  expect(transport).toHaveBeenCalledTimes(64);
  detach(); controller.abort();
});

it.each(['calendar', 'inspector'] as const)('actual %s control emits only finite observations, never field or record contents', async kind => {
  const events: Record<string, unknown>[] = [];
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input);
    if (path === endpoint) {
      const body: unknown = JSON.parse(String(init?.body));
      if (!body || typeof body !== 'object' || !('event_id' in body)) throw new Error('Missing event');
      events.push({ ...body });
      return Response.json({ version: 1, event_id: body.event_id, accepted: true, state: 'RECORDED' }, { status: 202 });
    }
    return Response.json(path === '/api/session' ? session : path === '/health/ready' ? health : path === '/api/instance' ? instance : path === `/api/v1/engagements/${id}` ? draft : path.endsWith('/summary') ? { ...syntheticSummary, attempts: [syntheticAttempt] } : path.includes('/attempts/') ? inspection() : path.endsWith('/run') || path === '/api/v1/runs/active' ? kind === 'inspector' ? syntheticRun : null : null);
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[kind === 'calendar' ? '/engagements/new' : `/engagements/${id}/stream`]}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  if (kind === 'calendar') {
    await user.type(await screen.findByLabelText('Engagement name'), 'synthetic_private_field_not_for_log');
    await user.click(screen.getByRole('checkbox', { name: 'Limit to a period' }));
    await user.click(screen.getByLabelText('Valid from (UTC)'));
    const now = new Date();
    const day = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 15)));
    await user.click(within(screen.getByRole('dialog', { name: 'Valid from (UTC) calendar' })).getByRole('button', { name: day }));
    await waitFor(() => expect(events.some(event => event.site === 'calendar_choice')).toBe(true));
    expect(events.some(event => event.site === 'period_toggle')).toBe(true);
  } else {
    await user.click(await screen.findByRole('button', { name: /^RECON/ }));
    await screen.findByRole('region', { name: 'Agent inspector' });
    await waitFor(() => expect(events.some(event => event.site === 'inspector_open' && event.run_id === syntheticRun.run_id)).toBe(true));
  }
  expect(JSON.stringify(events)).not.toContain('synthetic_private_field_not_for_log');
  expect(JSON.stringify(events)).not.toContain(syntheticAttempt.instructions);
  expect(JSON.stringify(events)).not.toContain(session.csrf_token);
  for (const event of events) expect(Object.keys(event).sort()).toEqual(['version', 'source', 'event_id', 'surface', 'site', 'action', 'outcome', 'error_code', 'correlation_id', 'run_id', 'command_id'].sort());
  view.unmount(); client.clear();
});
