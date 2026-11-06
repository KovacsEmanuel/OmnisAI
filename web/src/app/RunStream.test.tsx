import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router';
import { expect, it, vi } from 'vitest';
import { App } from './App';
import { session, instance, health } from '../../tests/fixtures';
import { draft, id } from '../../tests/projection-fixtures';
import { syntheticRun as run, syntheticAttempt, syntheticSummary, inspection, consumingBrain } from '../../tests/run-fixtures';
import { decodeAttemptInspection } from '../shared/api/runs';

function Location() { const location = useLocation(); return <output aria-label="View URL">{location.pathname}{location.search}</output>; }
function setup(query = '', fault = '', summaryGate?: Promise<void>) {
  const brain = consumingBrain();
  const worker: ReturnType<typeof inspection> = { ...inspection(), consumption: { held: false, decision_ref: brain.result_ref ?? null, consumer_attempt_id: brain.attempt_id } };
  const parent = { ...syntheticAttempt, role: 'BRAIN' as const, task_id: brain.task_id, attempt_id: brain.attempt_id, parent_task_id: null, state: 'SUCCEEDED' as const, result_ref: brain.result_ref, result_summary: brain.result_summary };
  const workerRoster = { ...syntheticAttempt };
  const summary = { ...syntheticSummary, attempts: [parent, workerRoster] };
  if (fault === 'pending') worker.consumption = { held: false, decision_ref: null, consumer_attempt_id: null };
  if (fault === 'decision') brain.result_ref = { ...brain.result_ref!, digest: 'e'.repeat(64) };
  if (fault === 'result') brain.decision = { ...brain.decision!, consumed_refs: [{ ...syntheticAttempt.result_ref!, digest: 'e'.repeat(64) }] };
  if (fault === 'consumer' && worker.consumption) worker.consumption.consumer_attempt_id = run.setup_ref.id;
  if (fault === 'foreign') worker.instance_id = run.setup_ref.id;
  if (fault === 'roster-model') brain.configured_model = 'fixture/decoder-valid-other-model';
  if (fault === 'roster-task') brain.task_id = run.setup_ref.id;
  if (fault === 'bounded') { summary.attempts = []; summary.has_more = true; }
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (init?.method && init.method !== 'GET') throw new Error('No command admitted in stream readback');
    const path = String(input);
    if (path.endsWith('/summary')) { if (summaryGate) await summaryGate; return Response.json(summary); }
    if (path.includes('/attempts/')) {
      if (path.endsWith(worker.attempt_id) && fault !== 'missing') return Response.json(worker);
      if (path.endsWith(brain.attempt_id)) return Response.json(brain);
      return Response.json({ error: { code: 'NOT_FOUND', correlation_id: id } }, { status: 404 });
    }
    if (path.includes('/events?')) {
      const after = Number(path.split(':').at(-1));
      return Response.json({ run_id: run.run_id, through_cursor: after, has_more: false, events: [], as_of: summary.as_of });
    }
    return Response.json(path === '/api/session' ? session : path === '/health/ready' ? health : path === '/api/instance' ? instance : path === `/api/v1/engagements/${id}` ? draft : path.endsWith('/run') || path === '/api/v1/runs/active' ? run : path.endsWith('/summary') ? summary : null);
  });
  vi.stubGlobal('fetch', fetcher);
  const mount = (url = `/engagements/${id}/stream${query}`) => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[url]}><App /><Location /></MemoryRouter></QueryClientProvider>);
    return { client, unmount() { view.unmount(); client.clear(); } };
  };
  return { view: mount(), mount, fetcher, worker, brain, summary, parent, workerRoster };
}

it.each(['healthy', 'roster-model', 'roster-task'])('waits for delayed run summary before accepting decoder-valid %s inspection', async fault => {
  let release: (() => void) | undefined;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const { view, fetcher, brain, worker } = setup(`?run=${run.run_id}&attempt=${instance.instance_id}&source=${id}`, fault, gate);
  try {
    expect(() => decodeAttemptInspection(worker, run.run_id, worker.attempt_id)).not.toThrow();
    expect(() => decodeAttemptInspection(brain, run.run_id, brain.attempt_id)).not.toThrow();
    await waitFor(() => expect(fetcher.mock.calls.some(([path]) => String(path).endsWith('/summary'))).toBe(true));
    await act(async () => { await Promise.resolve(); });
    expect(fetcher.mock.calls.filter(([path]) => String(path).includes('/attempts/'))).toHaveLength(0);
    expect(screen.queryByRole('region', { name: 'Agent inspector' })).not.toBeInTheDocument();
    await act(async () => { release?.(); await gate; });
    if (fault === 'healthy') {
      const inspector = await screen.findByRole('region', { name: 'Agent inspector' });
      expect(inspector).toHaveTextContent(brain.decision!.summary);
    } else {
      expect(await screen.findByText('Selected record unavailable or inconsistent. No linked result was accepted.')).toBeVisible();
      expect(screen.queryByRole('region', { name: 'Agent inspector' })).not.toBeInTheDocument();
    }
    expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
  } finally { release?.(); view.unmount(); }
});

it.each(['consumer', 'source'])('revalidates cached inspection when the already loaded %s roster changes', async changed => {
  const { view, fetcher, parent, workerRoster } = setup(`?run=${run.run_id}&attempt=${instance.instance_id}&source=${id}`);
  await screen.findByRole('region', { name: 'Agent inspector' });
  const before = fetcher.mock.calls.filter(([path]) => String(path).includes('/attempts/')).length;
  if (changed === 'consumer') parent.configured_model = 'fixture/changed-roster-model';
  else workerRoster.configured_model = 'fixture/changed-roster-model';
  await act(async () => { await view.client.refetchQueries({ queryKey: ['private', 'run-summary', run.run_id] }); });
  expect(await screen.findByText('Selected record unavailable or inconsistent. No linked result was accepted.')).toBeVisible();
  expect(screen.queryByRole('region', { name: 'Agent inspector' })).not.toBeInTheDocument();
  expect(fetcher.mock.calls.filter(([path]) => String(path).includes('/attempts/'))).toHaveLength(before);
  view.unmount();
});

it('accepts exact causal inspection legitimately omitted from an already loaded bounded roster', async () => {
  const { view, brain, fetcher } = setup(`?run=${run.run_id}&attempt=${instance.instance_id}&source=${id}`, 'bounded');
  const inspector = await screen.findByRole('region', { name: 'Agent inspector' });
  expect(inspector).toHaveTextContent(brain.decision!.summary);
  expect(screen.getByText('Some attempts are omitted from this bounded summary. Page through events to select their exact attempt IDs.')).toBeVisible();
  expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
  view.unmount();
});

it.each([
  `?attempt=${id}`, `?run=${run.run_id}&attempt=broken`,
  `?run=${run.run_id}&attempt=${id}&attempt=${instance.instance_id}`,
  `?run=${run.setup_ref.id}&attempt=${id}`, `?run=${run.run_id}&source=${id}`,
  `?run=${run.run_id}&attempt=${id}&source=${id}`, `?run=${run.run_id}&after=-1`,
  `?run=${run.run_id}&after=9999999999999999`, `?run=${run.run_id}&kind=unknown`,
  `?run=${run.run_id}&actor=broken`, `?run=${run.run_id}&agent-state=unknown`,
])('rejects malformed, duplicate or cross-run stream URL %s without inspection or commands', async query => {
  const { view, fetcher } = setup(query);
  expect(await screen.findByRole('alert')).toHaveTextContent('Stream URL is invalid or belongs to another run');
  expect(screen.queryByRole('region', { name: 'Agent inspector' })).not.toBeInTheDocument();
  expect(fetcher.mock.calls.some(([path]) => String(path).includes('/attempts/'))).toBe(false);
  await userEvent.setup().click(screen.getByRole('button', { name: 'Reset stream view' }));
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.getByLabelText('Event type')).toHaveValue('');
  view.unmount();
});

it.each(['pending', 'decision', 'result', 'consumer', 'foreign', 'missing'])('reconstructs consuming-Brain URL from the real worker and rejects %s mismatch', async fault => {
  const { view, fetcher } = setup(`?run=${run.run_id}&attempt=${instance.instance_id}&source=${id}`, fault);
  expect(await screen.findByText('Selected record unavailable or inconsistent. No linked result was accepted.')).toBeVisible();
  expect(screen.queryByRole('region', { name: 'Agent inspector' })).not.toBeInTheDocument();
  expect(screen.queryByText('Synthetic exact decision')).not.toBeInTheDocument();
  expect(fetcher.mock.calls.filter(([path]) => String(path).includes('/attempts/'))[0]?.[0]).toBe(`/api/v1/runs/${run.run_id}/attempts/${id}`);
  expect(screen.getByRole('button', { name: 'Stop run' })).toBeVisible();
  view.unmount();
});

it('reloads the actual consuming-Brain link with exact decision/result refs and no dispatch', async () => {
  const { view, mount, fetcher, brain, worker } = setup();
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: /^RECON/ }));
  await user.click(await screen.findByRole('button', { name: /Inspect consuming Brain/ }));
  const inspector = await screen.findByRole('region', { name: 'Agent inspector' });
  await within(inspector).findByText(brain.decision!.summary);
  expect(inspector).toHaveTextContent(worker.result_ref!.digest);
  const url = screen.getByLabelText('View URL').textContent!;
  expect(url).toContain(`attempt=${brain.attempt_id}`);
  expect(url).toContain(`source=${worker.attempt_id}`);
  expect(url).not.toContain(worker.input_text);
  expect(url).not.toContain(session.csrf_token);
  view.unmount();
  const reads = fetcher.mock.calls.length;
  const reloaded = mount(url);
  const restored = await screen.findByRole('region', { name: 'Agent inspector' });
  expect(await within(restored).findByText(brain.decision!.summary)).toBeVisible();
  expect(restored).toHaveTextContent('Decision action: finish · Completion kind: direct');
  expect(restored).toHaveTextContent(brain.result_ref!.digest);
  expect(restored).toHaveTextContent(worker.result_ref!.digest);
  for (const ref of [brain.result_ref!, worker.result_ref!]) expect(restored).toHaveTextContent(`${ref.kind} · ${ref.id} · revision ${ref.revision} · ${ref.digest} · instance ${ref.instance_id}`);
  expect(fetcher.mock.calls.slice(reads).filter(([path]) => String(path).includes('/attempts/')).map(([path]) => path)).toEqual([`/api/v1/runs/${run.run_id}/attempts/${id}`, `/api/v1/runs/${run.run_id}/attempts/${brain.attempt_id}`]);
  expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
  reloaded.unmount();
});

it.each(['trigger', 'deep-link'])('closes the nonmodal inspector to a visible %s focus target', async entry => {
  const { view } = setup(entry === 'deep-link' ? `?run=${run.run_id}&attempt=${id}` : '');
  const user = userEvent.setup();
  const trigger = await screen.findByRole('button', { name: /^RECON/ });
  if (entry === 'trigger') { trigger.focus(); await user.keyboard('{Enter}'); }
  const inspector = await screen.findByRole('region', { name: 'Agent inspector' });
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(inspector.closest('[inert]')).toBeNull();
  expect(screen.getByRole('button', { name: 'Stop run' })).toBeVisible();
  await user.click(within(inspector).getByRole('button', { name: 'Close inspector' }));
  expect(screen.queryByRole('region', { name: 'Agent inspector' })).not.toBeInTheDocument();
  expect(entry === 'trigger' ? trigger : screen.getByRole('heading', { name: 'Brain stream' })).toHaveFocus();
  view.unmount();
});

it('brings narrow-screen selection to the stacked inspector and returns to its trigger without a modal', async () => {
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true })));
  const { view } = setup();
  const user = userEvent.setup();
  const trigger = await screen.findByRole('button', { name: /^RECON/ });
  await user.click(trigger);
  const inspector = await screen.findByRole('region', { name: 'Agent inspector' });
  await waitFor(() => expect(within(inspector).getByRole('heading', { level: 3 })).toHaveFocus());
  expect(screen.getByRole('button', { name: 'Stop active run' }).closest('[inert]')).toBeNull();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  await user.click(within(inspector).getByRole('button', { name: 'Close inspector' }));
  expect(trigger).toHaveFocus();
  view.unmount();
});

it('keeps a missing selected record explicit without falling back to a different attempt', async () => {
  const { view, fetcher } = setup(`?run=${run.run_id}&attempt=${run.setup_ref.id}`);
  expect(await screen.findByText('Selected record unavailable or inconsistent. No linked result was accepted.')).toBeVisible();
  expect(screen.queryByRole('region', { name: 'Agent inspector' })).not.toBeInTheDocument();
  expect(fetcher.mock.calls.filter(([path]) => String(path).includes('/attempts/')).map(([path]) => path)).toEqual([`/api/v1/runs/${run.run_id}/attempts/${run.setup_ref.id}`]);
  view.unmount();
});

it('state filtering retains explicit ancestor context but no invisible-parent or empty roster containers', async () => {
  const { view } = setup(`?run=${run.run_id}&agent-state=INCONCLUSIVE`);
  const roster = await screen.findByRole('list', { name: 'Spawned agents' });
  await within(roster).findByRole('button', { name: /^RECON/ });
  expect(within(roster).queryByRole('button', { name: /^BRAIN/ })).not.toBeInTheDocument();
  expect(roster).toHaveTextContent(`Ancestor context: BRAIN · ${instance.instance_id} · SUCCEEDED`);
  expect(within(roster).getAllByRole('listitem').every(item => !!item.textContent?.trim())).toBe(true);
  await userEvent.setup().selectOptions(screen.getByLabelText('Agent state'), 'FAILED');
  expect(within(roster).queryAllByRole('listitem')).toHaveLength(0);
  expect(screen.getByText('No agents match this state in the bounded summary.')).toBeVisible();
  view.unmount();
});
