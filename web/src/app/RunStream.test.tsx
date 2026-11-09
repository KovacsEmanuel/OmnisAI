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
function setup(query = '', fault = '', summaryGate?: Promise<void>, attemptGate?: Promise<void>, runGate?: Promise<void>) {
  const brain = consumingBrain();
  const worker: ReturnType<typeof inspection> = { ...inspection(), consumption: { held: false, decision_ref: brain.result_ref ?? null, consumer_attempt_id: brain.attempt_id } };
  const parent = { ...syntheticAttempt, role: 'BRAIN' as const, task_id: brain.task_id, attempt_id: brain.attempt_id, parent_task_id: null, state: 'SUCCEEDED' as const, result_ref: brain.result_ref, result_summary: brain.result_summary };
  const workerRoster = { ...syntheticAttempt };
  const summary = { ...syntheticSummary, attempts: [parent, workerRoster] };
  if (fault === 'other-active') summary.run = { ...run, state: 'LIMITED' };
  const other = { ...run, run_id: '00000000-0000-4000-8000-000000000092', engagement_id: '00000000-0000-4000-8000-000000000093' };
  if (fault === 'pending') worker.consumption = { held: false, decision_ref: null, consumer_attempt_id: null };
  if (fault === 'decision') brain.result_ref = { ...brain.result_ref!, digest: 'e'.repeat(64) };
  if (fault === 'result') brain.decision = { ...brain.decision!, consumed_refs: [{ ...syntheticAttempt.result_ref!, digest: 'e'.repeat(64) }] };
  if (fault === 'consumer' && worker.consumption) worker.consumption.consumer_attempt_id = run.setup_ref.id;
  if (fault === 'foreign') worker.instance_id = run.setup_ref.id;
  if (fault === 'roster-model') brain.configured_model = 'fixture/decoder-valid-other-model';
  if (fault === 'roster-task') brain.task_id = run.setup_ref.id;
  if (fault === 'bounded') { summary.attempts = []; summary.has_more = true; }
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input);
    if (fault === 'other-active' && init?.method === 'POST' && path === `/api/v1/runs/${other.run_id}/commands`) {
      const payload: unknown = JSON.parse(String(init.body));
      if (!payload || typeof payload !== 'object' || !('command_id' in payload)) throw new Error('Missing synthetic command');
      return Response.json({ command_id: payload.command_id, run_id: other.run_id, setup_ref: null, revision: 8, state: 'ADMITTED' });
    }
    if (init?.method && init.method !== 'GET') throw new Error('No command admitted in stream readback');
    if (fault === 'other-active' && path === '/api/v1/runs/active') return Response.json(other);
    if (fault === 'other-active' && path === `/api/v1/engagements/${other.engagement_id}`) return Response.json({ ...draft, engagement_id: other.engagement_id, payload: { ...draft.payload, name: 'Other active engagement' } });
    if (path.endsWith('/summary')) { if (summaryGate) await summaryGate; return Response.json(summary); }
    if (path.endsWith('/agents')) {
      const groups = new Map<string, typeof summary.attempts>();
      for (const item of summary.attempts) { const key = item.role === 'BRAIN' ? 'brain' : item.task_id; groups.set(key, [...groups.get(key) ?? [], item]); }
      const agents = [...groups].map(([agent_id, items]) => { const item = items[0]!; return { agent_id: fault === 'roster-agent' && item.role === 'RECON' ? run.setup_ref.id : agent_id, role: item.role, parent_agent_id: item.role === 'BRAIN' ? null : 'brain', attempt_id: item.attempt_id, state: item.state, brief: item.brief, attempts: items.length }; }).sort((a, b) => a.agent_id === 'brain' ? -1 : b.agent_id === 'brain' ? 1 : a.agent_id.localeCompare(b.agent_id));
      return Response.json({ run_id: run.run_id, revision: run.revision, agents, has_more: false, next_after: null, as_of: summary.as_of });
    }
    if (path.includes('/agents/') && path.includes('/events?')) return Response.json({ run_id: run.run_id, agent_id: path.split('/agents/')[1]!.split('/')[0], through_cursor: 0, events: [], has_more: false, as_of: summary.as_of });
    if (path.includes('/attempts/')) {
      if (attemptGate) await attemptGate;
      if (path.endsWith(worker.attempt_id) && fault !== 'missing') return Response.json(worker);
      if (path.endsWith(brain.attempt_id)) return Response.json(brain);
      return Response.json({ error: { code: 'NOT_FOUND', correlation_id: id } }, { status: 404 });
    }
    if (path.includes('/events?')) {
      const after = Number(path.split(':').at(-1));
      if (fault === 'activity' || fault === 'activity-bounded') return Response.json({ run_id: run.run_id, through_cursor: after === 0 ? 1 : run.through_cursor, has_more: after === 0 || fault === 'activity-bounded',
        events: [{ event_id: id, run_id: run.run_id, task_id: id, attempt_id: id, sequence: after === 0 ? 1 : run.through_cursor, kind: 'result', summary: after === 0 ? 'Old first-page activity' : 'Newest persisted activity', refs: [], call_id: null, created_at: summary.as_of }], as_of: summary.as_of });
      return Response.json({ run_id: run.run_id, through_cursor: after, has_more: false, events: [], as_of: summary.as_of });
    }
    if (path.endsWith('/run') && runGate) await runGate;
    if (fault === 'no-run' && (path.endsWith('/run') || path === '/api/v1/runs/active')) return Response.json(null);
    return Response.json(path === '/api/session' ? session : path === '/health/ready' ? health : path === '/api/instance' ? instance : path === `/api/v1/engagements/${id}` ? draft : path.endsWith('/run') || path === '/api/v1/runs/active' ? fault === 'other-active' ? summary.run : run : path.endsWith('/summary') ? summary : null);
  });
  vi.stubGlobal('fetch', fetcher);
  const mount = (url = `/engagements/${id}/stream${query || `?run=${run.run_id}`}${fault.startsWith('activity') ? '' : '&activity=agents'}`) => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[url]}><App /><Location /></MemoryRouter></QueryClientProvider>);
    return { client, unmount() { view.unmount(); client.clear(); } };
  };
  return { view: mount(), mount, fetcher, worker, brain, summary, parent, workerRoster };
}

it('preserves the bound stream URL when Agents is clicked before run hydration', async () => {
  let release: (() => void) | undefined;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const { view, fetcher, worker } = setup('', '', undefined, undefined, gate);
  try {
    const user = userEvent.setup();
    await screen.findByText('Reading persisted run…');
    const url = screen.getByLabelText('View URL').textContent;
    const agents = screen.getByRole('button', { name: 'Agents' });
    await user.click(agents);
    expect(screen.getByLabelText('View URL').textContent).toBe(url);
    expect(agents).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Feed' })).toBeDisabled();
    // Feed filters also reach the shared updater while identity is pending.
    await user.selectOptions(screen.getByLabelText('Event type'), '');
    expect(screen.getByLabelText('View URL').textContent).toBe(url);
    expect(fetcher.mock.calls.filter(([path]) => String(path).startsWith('/api/v1/runs/') && !['/api/v1/runs/active', '/api/v1/runs/publications'].includes(String(path)))).toHaveLength(0);
    await act(async () => { release?.(); await gate; });
    await waitFor(() => expect(agents).toBeEnabled());
    await user.click(agents);
    await user.click(await within(await screen.findByRole('list', { name: 'Spawned agents' })).findByRole('button', { name: /^RECON/ }));
    const inspector = await screen.findByRole('region', { name: 'Agent inspector' });
    expect(inspector).toHaveAttribute('data-run-id', run.run_id);
    expect(inspector).toHaveAttribute('data-attempt-id', worker.attempt_id);
    await within(inspector).findByText(/End of observed history/);
    expect(screen.getByLabelText('View URL')).toHaveTextContent(`run=${run.run_id}`);
    expect(screen.queryByText(/Stream URL is invalid/)).not.toBeInTheDocument();
    expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
  } finally { view.unmount(); release?.(); }
});

it('keeps activity controls inert without a current run', async () => {
  const { view, fetcher } = setup('', 'no-run');
  try {
    const user = userEvent.setup();
    await screen.findByText('No run observed.');
    const url = screen.getByLabelText('View URL').textContent;
    await user.click(screen.getByRole('button', { name: 'Agents' }));
    expect(screen.getByLabelText('View URL').textContent).toBe(url);
    expect(screen.getByRole('button', { name: 'Agents' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Feed' })).toBeDisabled();
    await user.selectOptions(screen.getByLabelText('Event type'), '');
    expect(screen.getByLabelText('View URL').textContent).toBe(url);
    expect(fetcher.mock.calls.filter(([path]) => String(path).startsWith('/api/v1/runs/') && !['/api/v1/runs/active', '/api/v1/runs/publications'].includes(String(path)))).toHaveLength(0);
    expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
  } finally { view.unmount(); }
});

it('shows latest observed activity independently of an older ascending event page', async () => {
  const { view, fetcher } = setup('', 'activity');
  const activity = await screen.findByRole('region', { name: 'Current activity' });
  expect(await within(activity).findByText('Newest persisted activity')).toBeVisible();
  expect(activity).not.toHaveTextContent('Old first-page activity');
  expect(await within(screen.getByRole('list', { name: 'Run events' })).findByText(/Old first-page activity/)).toBeVisible();
  expect(fetcher.mock.calls.some(([path]) => String(path).endsWith(`:${run.through_cursor - 1}`))).toBe(true);
  view.unmount();
});

it('does not promote a bounded activity page to a latest-event claim', async () => {
  const { view } = setup('', 'activity-bounded');
  const activity = await screen.findByRole('region', { name: 'Current activity' });
  expect(await within(activity).findByText('Newer activity is not yet available in this bounded read.')).toBeVisible();
  expect(activity).not.toHaveTextContent('Newest persisted activity');
  view.unmount();
});

it('refuses a decoder-valid regressing tail instead of presenting older activity as current', async () => {
  const { view, fetcher } = setup('', 'activity');
  const original = fetcher.getMockImplementation();
  if (!original) throw new Error('Missing read mock');
  let sequence = 7;
  fetcher.mockImplementation(async (input, init) => String(input).endsWith(`:${run.through_cursor - 1}`) ? Response.json({ run_id: run.run_id, through_cursor: sequence, has_more: false, as_of: syntheticSummary.as_of,
    events: [{ event_id: id, run_id: run.run_id, task_id: id, attempt_id: id, sequence, kind: 'result', summary: `Observed event ${sequence}`, refs: [], call_id: null, created_at: syntheticSummary.as_of }] }) : original(input, init));
  const activity = await screen.findByRole('region', { name: 'Current activity' });
  expect(await within(activity).findByText('Observed event 7')).toBeVisible();
  sequence = 6;
  await act(async () => { await view.client.invalidateQueries({ queryKey: ['private', 'run-activity'] }); });
  expect(await within(activity).findByText('Current activity unavailable; no activity inferred.')).toBeVisible();
  expect(activity).not.toHaveTextContent('Observed event 6');
  view.unmount();
});

it('keeps current global Stop bound to another engagement while a historical inspector stays read-only', async () => {
  const { view, fetcher } = setup(`?run=${run.run_id}&attempt=${id}`, 'other-active');
  const user = userEvent.setup();
  const inspector = await screen.findByRole('region', { name: 'Agent inspector' });
  expect(inspector).toHaveAttribute('data-run-id', run.run_id);
  expect(within(inspector).queryByRole('textbox')).not.toBeInTheDocument();
  expect(within(inspector).queryByRole('button', { name: /Send|Execute|Resume|Pause/i })).not.toBeInTheDocument();
  const global = within(screen.getByRole('region', { name: 'Global run control' }));
  expect(await global.findByRole('link', { name: /Other active engagement/ })).toHaveAttribute('title', 'Run 00000000-0000-4000-8000-000000000092');
  const identity = global.getByText('Identity', { selector: 'summary' });
  identity.focus(); expect(identity).toHaveFocus();
  // user-event's space activation does not implement native summary; browser journey covers keys.
  await user.click(identity);
  expect(global.getByText('Run 00000000-0000-4000-8000-000000000092')).toBeVisible();
  expect(global.getByText('Engagement 00000000-0000-4000-8000-000000000093')).toBeVisible();
  await user.click(identity);
  const stop = global.getByRole('button', { name: 'Stop active run' });
  expect(stop.closest('[inert]')).toBeNull();
  await waitFor(() => expect(stop).toBeEnabled());
  await user.click(stop);
  await waitFor(() => expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1));
  const sent = fetcher.mock.calls.find(([, init]) => init?.method === 'POST');
  expect(sent?.[0]).toBe('/api/v1/runs/00000000-0000-4000-8000-000000000092/commands');
  expect(JSON.parse(String(sent?.[1]?.body))).toMatchObject({ action: 'stop', run_id: '00000000-0000-4000-8000-000000000092', expected_revision: 7, expected_generation: 3 });
  expect(screen.getByRole('dialog', { name: 'Recorded agent activity' })).not.toHaveAttribute('aria-modal', 'true');
  expect(screen.queryByRole('button', { name: 'Confirm Stop' })).not.toBeInTheDocument();
  // Global Stop keeps native focus; Escape inside the selected record closes only that record.
  within(inspector).getByRole('heading', { level: 3 }).focus();
  await user.keyboard('{Escape}');
  expect(screen.queryByRole('dialog', { name: 'Recorded agent activity' })).not.toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Activity' })).toHaveFocus();
  view.unmount();
});

it('groups repeated Brain attempts as one actual task rather than several resident agents', async () => {
  const { view, summary, parent } = setup();
  summary.attempts.push({ ...parent, task_id: run.setup_ref.id, attempt_id: run.setup_ref.id });
  const roster = await screen.findByRole('list', { name: 'Spawned agents' });
  expect(await within(roster).findByText(/2 recorded attempts/)).toBeVisible();
  expect(within(roster).getAllByRole('listitem')).toHaveLength(2);
  expect(within(roster).getAllByRole('button', { name: /^BRAIN/ })).toHaveLength(1);
  view.unmount();
});

it.each(['healthy', 'roster-model', 'roster-task', 'roster-agent'])('waits for delayed run summary before accepting decoder-valid %s inspection', async fault => {
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
  expect(screen.getByRole('region', { name: 'Agent inspector' })).toHaveAttribute('data-attempt-id', brain.attempt_id);
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

it.each(['loaded', 'pending', 'error'])('reactivates the already selected agent by keyboard during %s readback', async state => {
  let release: (() => void) | undefined;
  const gate = state === 'pending' ? new Promise<void>(resolve => { release = resolve; }) : undefined;
  const { view, fetcher } = setup(`?run=${run.run_id}&attempt=${id}`, state === 'error' ? 'missing' : '', undefined, gate);
  try {
    const user = userEvent.setup();
    if (state === 'pending') await screen.findByText('Loading selected agent…');
    else if (state === 'error') await screen.findByText('Selected record unavailable or inconsistent. No linked result was accepted.');
    else await screen.findByRole('region', { name: 'Agent inspector' });
    const popup = screen.getByRole('dialog', { name: 'Recorded agent activity' });
    const target = state === 'loaded' ? within(popup).getByRole('heading', { level: 3 }) : within(popup).getByRole('button', { name: 'Close inspector' });
    await waitFor(() => expect(target).toHaveFocus());
    const trigger = await screen.findByRole('button', { name: /^RECON/ });
    const url = screen.getByLabelText('View URL').textContent;
    const reads = fetcher.mock.calls.filter(([path]) => String(path).includes('/attempts/')).length;
    trigger.focus(); expect(trigger).toHaveFocus();
    await user.keyboard('{Enter}');
    await waitFor(() => expect(target).toHaveFocus());
    expect(screen.getByLabelText('View URL').textContent).toBe(url);
    expect(fetcher.mock.calls.filter(([path]) => String(path).includes('/attempts/'))).toHaveLength(reads);
    expect(popup).not.toHaveAttribute('aria-modal', 'true');
    expect(screen.getByRole('button', { name: 'Stop active run' }).closest('[inert]')).toBeNull();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Recorded agent activity' })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
    expect(screen.getByLabelText('View URL')).not.toHaveTextContent('attempt=');
    expect(screen.getByLabelText('View URL')).not.toHaveTextContent('source=');
    expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
  } finally { view.unmount(); release?.(); }
});

it('reactivates the already selected event actor by keyboard and restores its event trigger', async () => {
  const { view, fetcher } = setup(`?run=${run.run_id}&attempt=${id}`, 'activity');
  try {
    const user = userEvent.setup();
    const inspector = await screen.findByRole('region', { name: 'Agent inspector' });
    const heading = within(inspector).getByRole('heading', { level: 3 });
    await waitFor(() => expect(heading).toHaveFocus());
    const trigger = await within(screen.getByRole('list', { name: 'Run events' })).findByRole('button', { name: /Old first-page activity/ });
    const url = screen.getByLabelText('View URL').textContent;
    const reads = fetcher.mock.calls.filter(([path]) => String(path).includes('/attempts/')).length;
    trigger.focus(); expect(trigger).toHaveFocus();
    await user.keyboard('{Enter}');
    await waitFor(() => expect(heading).toHaveFocus());
    expect(screen.getByLabelText('View URL').textContent).toBe(url);
    expect(fetcher.mock.calls.filter(([path]) => String(path).includes('/attempts/'))).toHaveLength(reads);
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Recorded agent activity' })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
    expect(screen.getByLabelText('View URL')).not.toHaveTextContent('attempt=');
    expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
  } finally { view.unmount(); }
});

it('keeps keyboard causal selection on the validated consumer rather than the previous worker', async () => {
  const { view, fetcher, worker, brain } = setup();
  try {
    const user = userEvent.setup();
    const trigger = await screen.findByRole('button', { name: /^RECON/ });
    trigger.focus(); await user.keyboard('{Enter}');
    const inspector = await screen.findByRole('region', { name: 'Agent inspector' });
    await waitFor(() => expect(within(inspector).getByRole('heading', { level: 3 })).toHaveFocus());
    const link = within(screen.getByRole('dialog', { name: 'Recorded agent activity' })).getByRole('button', { name: /Inspect consuming Brain/ });
    link.focus(); await user.keyboard('{Enter}');
    await waitFor(() => expect(screen.getByRole('region', { name: 'Agent inspector' })).toHaveAttribute('data-attempt-id', brain.attempt_id));
    const consumer = screen.getByRole('region', { name: 'Agent inspector' });
    await waitFor(() => expect(within(consumer).getByRole('heading', { level: 3 })).toHaveFocus());
    expect(consumer).toHaveTextContent(brain.decision!.summary);
    for (const ref of [brain.result_ref!, worker.result_ref!]) expect(consumer).toHaveTextContent(ref.digest);
    expect(screen.getByLabelText('View URL')).toHaveTextContent(`attempt=${brain.attempt_id}`);
    expect(screen.getByLabelText('View URL')).toHaveTextContent(`source=${worker.attempt_id}`);
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Recorded agent activity' })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
    expect(screen.getByLabelText('View URL')).not.toHaveTextContent('source=');
    expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
  } finally { view.unmount(); }
});

it.each(['trigger', 'deep-link'])('closes the nonmodal inspector to a visible %s focus target', async entry => {
  const { view } = setup(entry === 'deep-link' ? `?run=${run.run_id}&attempt=${id}` : '');
  const user = userEvent.setup();
  const trigger = await screen.findByRole('button', { name: /^RECON/ });
  if (entry === 'trigger') { trigger.focus(); await user.keyboard('{Enter}'); }
  const inspector = await screen.findByRole('region', { name: 'Agent inspector' });
  expect(screen.getByRole('dialog', { name: 'Recorded agent activity' })).not.toHaveAttribute('aria-modal', 'true');
  expect(inspector.closest('[inert]')).toBeNull();
  expect(screen.getByRole('button', { name: 'Stop run' })).toBeVisible();
  await user.click(within(inspector).getByRole('button', { name: 'Close inspector' }));
  expect(screen.queryByRole('region', { name: 'Agent inspector' })).not.toBeInTheDocument();
  expect(entry === 'trigger' ? trigger : screen.getByRole('heading', { name: 'Activity' })).toHaveFocus();
  view.unmount();
});

it.each(['trigger', 'deep-link'].flatMap(entry => ['pending', 'error', 'loaded'].map(state => ({ entry, state }))))('focuses the $entry inspector during $state readback and closes with Escape', async ({ entry, state }) => {
    let release: (() => void) | undefined;
    const gate = state === 'pending' ? new Promise<void>(resolve => { release = resolve; }) : undefined;
    const { view, fetcher } = setup(entry === 'deep-link' ? `?run=${run.run_id}&attempt=${id}` : '', state === 'error' ? 'missing' : '', undefined, gate);
    const user = userEvent.setup();
    const trigger = await screen.findByRole('button', { name: /^RECON/ });
    if (entry === 'trigger') { trigger.focus(); await user.keyboard('{Enter}'); }
    if (state === 'pending') await screen.findByText('Loading selected agent…');
    else if (state === 'error') await screen.findByText('Selected record unavailable or inconsistent. No linked result was accepted.');
    else await screen.findByRole('region', { name: 'Agent inspector' });
    const popup = screen.getByRole('dialog', { name: 'Recorded agent activity' });
    await waitFor(() => expect(popup.contains(document.activeElement)).toBe(true));
    expect(state === 'loaded' ? within(popup).getByRole('heading', { level: 3 }) : within(popup).getByRole('button', { name: 'Close inspector' })).toHaveFocus();
    expect(popup).not.toHaveAttribute('aria-modal', 'true');
    expect(screen.getByRole('button', { name: 'Stop active run' }).closest('[inert]')).toBeNull();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Recorded agent activity' })).not.toBeInTheDocument();
    expect(entry === 'trigger' ? trigger : screen.getByRole('heading', { name: 'Activity' })).toHaveFocus();
    expect(screen.getByLabelText('View URL')).not.toHaveTextContent('attempt=');
    expect(screen.getByLabelText('View URL')).not.toHaveTextContent('source=');
    expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
    view.unmount();
    release?.();
});

it('does not steal focus from Stop when a pending inspection settles or its retained detail refetches', async () => {
  let release: (() => void) | undefined;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const { view, fetcher, worker } = setup('', '', undefined, gate);
  const user = userEvent.setup();
  const trigger = await screen.findByRole('button', { name: /^RECON/ });
  trigger.focus(); await user.keyboard('{Enter}');
  await screen.findByText('Loading selected agent…');
  const stop = screen.getByRole('button', { name: 'Stop active run' });
  await waitFor(() => expect(stop).toBeEnabled());
  stop.focus(); expect(stop).toHaveFocus();
  await act(async () => { release?.(); await gate; });
  const inspector = await screen.findByRole('region', { name: 'Agent inspector' });
  expect(stop).toHaveFocus();
  worker.brief = 'Updated retained brief';
  await act(async () => { await view.client.invalidateQueries({ queryKey: ['private', 'run-attempt'] }); });
  expect(await within(inspector).findByRole('heading', { name: /Updated retained brief/ })).toBeVisible();
  expect(stop).toHaveFocus();
  expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
  view.unmount();
});

it.each(['503', 'roster'].flatMap(fault => ['inside', 'stop'].flatMap(focus => ['trigger', 'deep-link'].map(entry => ({ fault, focus, entry })))) )('keeps $focus focus usable when loaded $entry causal detail is withdrawn by $fault', async ({ fault, focus, entry }) => {
  const { view, fetcher, brain, parent } = setup(entry === 'deep-link' ? `?run=${run.run_id}&attempt=${instance.instance_id}&source=${id}` : '');
  const user = userEvent.setup();
  const trigger = await screen.findByRole('button', { name: /^RECON/ });
  if (entry === 'trigger') {
    trigger.focus(); await user.keyboard('{Enter}');
    await user.click(await screen.findByRole('button', { name: /Inspect consuming Brain/ }));
  }
  const inspector = await screen.findByRole('region', { name: 'Agent inspector' });
  await waitFor(() => expect(inspector).toHaveAttribute('data-attempt-id', brain.attempt_id));
  const stop = screen.getByRole('button', { name: 'Stop active run' });
  await waitFor(() => expect(stop).toBeEnabled());
  if (focus === 'stop') stop.focus(); else within(inspector).getByRole('heading', { level: 3 }).focus();
  if (fault === '503') {
    const original = fetcher.getMockImplementation();
    if (!original) throw new Error('Missing SOURCE fetch');
    fetcher.mockImplementation(async (input, init) => String(input) === `/api/v1/runs/${run.run_id}/attempts/${brain.attempt_id}`
      ? Response.json({ error: { code: 'API_UNAVAILABLE', correlation_id: id } }, { status: 503 }) : original(input, init));
    await act(async () => { await view.client.refetchQueries({ queryKey: ['private', 'run-attempt'] }); });
  } else {
    parent.configured_model = 'fixture/changed-roster-model';
    await act(async () => { await view.client.refetchQueries({ queryKey: ['private', 'run-summary'] }); });
  }
  await screen.findByText('Selected record unavailable or inconsistent. No linked result was accepted.');
  expect(screen.queryByRole('region', { name: 'Agent inspector' })).not.toBeInTheDocument();
  const popup = screen.getByRole('dialog', { name: 'Recorded agent activity' });
  const close = within(popup).getByRole('button', { name: 'Close inspector' });
  expect(popup).not.toHaveAttribute('aria-modal', 'true');
  expect(stop.closest('[inert]')).toBeNull();
  if (focus === 'stop') {
    expect(stop).toHaveFocus();
    await user.keyboard('{Escape}');
    expect(popup).toBeVisible();
    close.focus();
  } else await waitFor(() => expect(close).toHaveFocus());
  await user.keyboard('{Escape}');
  expect(screen.queryByRole('dialog', { name: 'Recorded agent activity' })).not.toBeInTheDocument();
  expect(entry === 'trigger' ? trigger : screen.getByRole('heading', { name: 'Activity' })).toHaveFocus();
  expect(screen.getByLabelText('View URL')).not.toHaveTextContent('attempt=');
  expect(screen.getByLabelText('View URL')).not.toHaveTextContent('source=');
  expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
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
  expect(screen.getByRole('dialog', { name: 'Recorded agent activity' })).not.toHaveAttribute('aria-modal', 'true');
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
  expect(roster).toHaveTextContent('parent brain');
  expect(within(roster).getAllByRole('listitem').every(item => !!item.textContent?.trim())).toBe(true);
  await userEvent.setup().selectOptions(screen.getByLabelText('Agent state'), 'FAILED');
  expect(within(roster).queryAllByRole('listitem')).toHaveLength(0);
  expect(screen.getByText('No agents match this state on this page.')).toBeVisible();
  view.unmount();
});
