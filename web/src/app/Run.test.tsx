import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { health, session, instance } from '../../tests/fixtures';
import { draft, id } from '../../tests/projection-fixtures';
import { App } from './App';
import type { components } from '../shared/api/generated';
import { isRecord } from '../shared/api/errors';

it.each(['unchanged', 'selection', 'draft', 'context', 'generation', 'lost-preflight', 'lost-start'] as const)('SOURCE normal preflight/Start pins and invalidates %s without implicit writes', async change => {
  const publication = { kind: 'catalog-publication', id: '00000000-0000-4000-8000-000000000030', revision: 1, digest: 'c'.repeat(64) };
  const setup = { instance_id: instance.instance_id, kind: 'run-setup-v1', id: '00000000-0000-4000-8000-000000000031', revision: 1, digest: 'd'.repeat(64) };
  const runId = '00000000-0000-4000-8000-000000000032';
  const questionId = '00000000-0000-4000-8000-000000000033';
  const choice = { connection_id: '00000000-0000-4000-8000-000000000034', connection_revision: 1, model: 'fixture/pinned', output_tokens: 1024 };
  let hasRun = false, revision = 2, selectionRevision = 1, generation = 0;
  let savedDraft = draft;
  let questionState: components['schemas']['Question']['state'] = 'PENDING';
  let answerCommand: string | null = null;
  const answerRef = { ...setup, kind: 'run-answer-v1', id: '00000000-0000-4000-8000-000000000035' };
  const writes: { path: string; payload: Record<string, unknown> }[] = [];
  const receipts = new Map<string, object>();
  function run(): components['schemas']['RunView'] {
    return { schema_version: 1, instance_id: instance.instance_id, engagement_id: id, run_id: runId,
      setup_ref: { ...setup, revision: 1 }, revision, generation: 0, owner_id: instance.instance_id, owner_epoch: 1, fence: 1,
      state: 'RUNNING', reason: null, active_attempt_id: null, question_id: questionId, stagnation: 1, through_cursor: 2 };
  }
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input);
    let value: unknown = null;
    if (init?.method === 'POST') {
      if (typeof init.body !== 'string') throw new Error('Missing exact command');
      const payload: unknown = JSON.parse(init.body);
      if (!isRecord(payload) || typeof payload.command_id !== 'string') throw new Error('Invalid command');
      writes.push({ path, payload });
      expect(new TextEncoder().encode(init.body).length).toBeLessThanOrEqual(3600);
      if (path.endsWith('/run-preflight')) {
        expect(payload.synthetic_context).toBe('Synthetic chosen input');
        expect(payload.expected_generation).toBe(0);
        value = { command_id: payload.command_id, setup_ref: setup, run_id: null, revision: 1, state: 'READY' };
      } else if (path === '/api/v1/runs') {
        expect(payload.setup_ref).toEqual(setup); hasRun = true;
        value = { command_id: payload.command_id, setup_ref: null, run_id: runId, revision: 1, state: 'ADMITTED' };
      } else {
        expect(payload.action).toBe('answer'); expect(payload.question_id).toBe(questionId);
        expect(payload.expected_revision).toBe(2); questionState = 'ANSWER_ADMITTED'; revision = 3; answerCommand = payload.command_id;
        value = { command_id: payload.command_id, setup_ref: null, run_id: runId, revision, state: 'ADMITTED' };
      }
      if (typeof value !== 'object' || value === null) throw new Error('Missing receipt');
      receipts.set(payload.command_id, value);
      if ((change === 'lost-preflight' && path.endsWith('/run-preflight')) || (change === 'lost-start' && path === '/api/v1/runs')) throw new Error('Lost committed reply');
    } else if (path === '/api/session') value = session;
    else if (path === '/health/ready') value = health;
    else if (path === '/api/instance') value = { ...instance, generation, admission_open: true };
    else if (path === `/api/v1/engagements/${id}`) value = savedDraft;
    else if (path === '/api/v1/runs/publications') value = [publication];
    else if (path === '/api/v1/settings/providers') value = { schema_version: 2, command_id: null, vault_status: 'UNLOCKED', reachable: 'NOT_VERIFIED', connections: [{ connection_id: choice.connection_id, provider: 'openrouter', revision: 1, enabled: true, credential_present: true }], selection: { schema_version: 2, selection_id: choice.connection_id, revision: selectionRevision, default: choice, brain: null, recon: { ...choice, model: 'fixture/recon-override' }, investigator: null, validator: null } };
    else if (path === `/api/v1/engagements/${id}/run` || path === '/api/v1/runs/active') value = hasRun ? run() : null;
    else if (path === `/api/v1/runs/${runId}/summary`) value = { run: run(), owner_live: true, phase_active: false, attempts: [], has_more: false, as_of: '2026-11-04T12:00:00Z', question: { question_id: questionId, run_id: runId, task_id: instance.instance_id, revision: 2, kind: 'CLARIFICATION', cause: 'Clarification needed', text: 'Which synthetic part?', refs: [], state: questionState, answer_ref: questionState === 'PENDING' ? null : answerRef, command_id: answerCommand } };
    else if (path.startsWith('/api/v1/runs/commands/')) value = receipts.get(path.split('/').at(-1) ?? '');
    return new Response(JSON.stringify(value));
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const renderApp = () => render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/engagements/${id}/overview`]}><App /></MemoryRouter></QueryClientProvider>);
  let view = renderApp();
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText('Selected synthetic inert context'), 'Synthetic chosen input');
  await user.selectOptions(screen.getByLabelText('Qualified core publication'), publication.id);
  await user.click(screen.getByLabelText(/This text is synthetic and non-secret/));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Preflight inert run' })).toBeEnabled());
  await user.click(screen.getByRole('button', { name: 'Preflight inert run' }));
  if (change === 'lost-preflight') {
    await user.click(await screen.findByRole('button', { name: 'Read command receipt' }));
    await screen.findByText(/READY.*recovered preflight/);
    expect(screen.queryByRole('region', { name: 'Run preflight confirmation' })).not.toBeInTheDocument();
    expect(writes).toHaveLength(1);
    view.unmount(); client.clear(); return;
  }
  await screen.findByRole('region', { name: 'Run preflight confirmation' });
  expect(writes).toHaveLength(1);
  expect(screen.getByRole('region', { name: 'Run preflight confirmation' })).toHaveTextContent('Recon fixture/recon-override');
  await user.click(screen.getByLabelText(/Confirm model execution/));
  if (change !== 'unchanged' && change !== 'lost-start') {
    if (change === 'selection') selectionRevision = 2;
    if (change === 'draft') savedDraft = { ...draft, revision: 2, digest: 'e'.repeat(64) };
    if (change === 'generation') generation = 1;
    if (change === 'context') await user.type(screen.getByLabelText('Selected synthetic inert context'), ' changed');
    await act(async () => { await client.invalidateQueries(); });
    if (change === 'generation') {
      await waitFor(() => expect(screen.getByRole('button', { name: 'Start inert run' })).toBeDisabled());
      expect(screen.getByRole('region', { name: 'Run preflight confirmation' })).toHaveTextContent('generation 0');
    } else await waitFor(() => expect(screen.queryByRole('region', { name: 'Run preflight confirmation' })).not.toBeInTheDocument());
    expect(writes).toHaveLength(1);
    view.unmount(); client.clear(); return;
  }
  await user.click(screen.getByRole('button', { name: 'Start inert run' }));
  if (change === 'lost-start') {
    await screen.findByText(/Read the same command; no resend/);
    view.unmount(); client.clear(); view = renderApp();
    await user.click(await screen.findByRole('button', { name: 'Read command receipt' }));
    await screen.findByText(/ADMITTED.*recovered preflight/);
    expect(writes).toHaveLength(2);
  }
  await screen.findByText('Needs you · PENDING');
  await user.type(screen.getByLabelText('Non-secret clarification'), 'Only the selected synthetic part');
  await user.click(screen.getByRole('button', { name: 'Submit clarification' }));
  await screen.findByText('Needs you · ANSWER_ADMITTED');
  questionState = 'CONSUMED'; // Scripted producer transition, never performed by GET.
  await user.click(screen.getByRole('button', { name: 'Refresh run' }));
  await screen.findByText('Needs you · CONSUMED');
  view.unmount(); client.clear(); view = renderApp();
  await screen.findByText('Needs you · CONSUMED');
  expect(writes).toHaveLength(3);
  expect(screen.getByRole('region', { name: 'Needs you' })).toHaveTextContent(questionId);
  view.unmount(); client.clear();
});

const runId = '00000000-0000-4000-8000-000000000032';
const setup = { instance_id: instance.instance_id, kind: 'run-setup-v1', id: '00000000-0000-4000-8000-000000000031', revision: 1, digest: 'd'.repeat(64) };
function observedRun(): components['schemas']['RunView'] {
  return { schema_version: 1, instance_id: instance.instance_id, engagement_id: id, run_id: runId, setup_ref: { ...setup, revision: 1 }, revision: 7, generation: 3, owner_id: instance.instance_id, owner_epoch: 1, fence: 1, state: 'RUNNING', reason: null, active_attempt_id: null, question_id: null, stagnation: 0, through_cursor: 6 };
}

it('SOURCE global Stop binds the observed run, survives a lost reply and reload without stopping a newer run', async () => {
  let failRead = false;
  let current = observedRun();
  const writes: Record<string, unknown>[] = [];
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input);
    if (init?.method === 'POST') {
      const payload: unknown = JSON.parse(String(init.body));
      if (!isRecord(payload)) throw new Error('Missing command');
      writes.push(payload);
      expect(path).toBe(`/api/v1/runs/${runId}/commands`);
      throw new Error('Lost reply');
    }
    if (path === '/api/v1/runs/active' && failRead) return new Response(JSON.stringify({ error: { code: 'CONTROL_UNAVAILABLE', correlation_id: id } }), { status: 503 });
    const value = path === '/api/session' ? session : path === '/health/ready' ? health : path === '/api/instance' ? instance : path === '/api/v1/runs/active' ? current : path.startsWith('/api/v1/runs/commands/') ? { command_id: writes[0]?.command_id, setup_ref: null, run_id: runId, revision: 8, state: 'ADMITTED' } : null;
    return new Response(JSON.stringify(value));
  });
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const mount = () => render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/settings/runtime']}><App /></MemoryRouter></QueryClientProvider>);
  let view = mount();
  const user = userEvent.setup();
  const stop = await screen.findByRole('button', { name: 'Stop active run' });
  await waitFor(() => expect(stop).toBeEnabled());
  failRead = true;
  await user.click(screen.getByRole('button', { name: 'Read active run' }));
  await waitFor(() => expect(client.getQueryState(['private', 'active-run'])?.status).toBe('error'));
  current = { ...current, run_id: '00000000-0000-4000-8000-000000000099', revision: 1 };
  await user.click(stop);
  await screen.findByText(/Stop outcome unknown/);
  expect(writes).toEqual([expect.objectContaining({ action: 'stop', run_id: runId, expected_revision: 7, expected_generation: 3 })]);
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(sessionStorage.getItem('omnis-run-stop')).not.toContain(session.csrf_token);
  view.unmount(); client.clear(); failRead = false;
  current = { ...current, run_id: '00000000-0000-4000-8000-000000000099', revision: 1 };
  view = mount();
  await user.click(await screen.findByRole('button', { name: 'Read Stop receipt' }));
  await screen.findByText(/ADMITTED.*00000000-0000-4000-8000-000000000032/);
  expect(writes).toHaveLength(1);
  expect(sessionStorage.getItem('omnis-run-stop')).toBeNull();
  view.unmount(); client.clear();
});

function mountedRun(surface = 'overview') {
  sessionStorage.clear();
  const state: { run: components['schemas']['RunView']; summary: components['schemas']['RunSummary'] } = {
    run: observedRun(), summary: { run: observedRun(), owner_live: true, phase_active: false, question: null, attempts: [], has_more: false, as_of: '2026-11-04T12:00:00Z' },
  };
  const writes: Record<string, unknown>[] = [];
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input);
    if (init?.method === 'POST') {
      const payload: unknown = JSON.parse(String(init.body));
      if (!isRecord(payload)) throw new Error('Invalid command');
      writes.push(payload);
      if (payload.action === 'pause') throw new Error('Lost pause reply');
      return new Response(JSON.stringify({ command_id: payload.command_id, setup_ref: null, run_id: state.run.run_id, revision: state.run.revision + 1, state: 'ADMITTED' }));
    }
    const value = path === '/api/session' ? session : path === '/health/ready' ? health : path === '/api/instance' ? instance : path === `/api/v1/engagements/${id}` ? draft : path === '/api/v1/runs/active' || path.endsWith('/run') ? state.run : path.endsWith('/summary') ? state.summary : path === '/api/v1/runs/publications' ? [] : null;
    return new Response(JSON.stringify(value));
  });
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/engagements/${id}/${surface}`]}><App /></MemoryRouter></QueryClientProvider>);
  return { state, writes, fetcher, client, view };
}

it.each(['unknown', 'sending'])('SOURCE Stop remains available when Pause is %s', async phase => {
  const { writes, view, client, fetcher } = mountedRun();
  let release: (() => void) | undefined;
  if (phase === 'sending') {
    const original = fetcher.getMockImplementation()!;
    const gate = new Promise<void>(resolve => { release = resolve; });
    fetcher.mockImplementation(async (input, init) => {
      if (init?.method === 'POST' && String(init.body).includes('"action":"pause"')) {
        const result = original(input, init).catch(() => null);
        await gate;
        const response = await result;
        if (!response) throw new Error('Lost pause reply');
        return response;
      }
      return original(input, init);
    });
  }
  const user = userEvent.setup();
  const pause = await screen.findByRole('button', { name: 'Pause run' });
  await waitFor(() => expect(pause).toBeEnabled());
  await user.click(pause);
  await screen.findByRole('button', { name: 'Read command receipt' });
  const stop = screen.getByRole('button', { name: 'Stop run' });
  expect(stop).toBeEnabled();
  await user.click(stop);
  await waitFor(() => expect(writes).toHaveLength(2));
  expect(writes[1]).toMatchObject({ action: 'stop', run_id: runId, expected_revision: 7, expected_generation: 3 });
  expect(screen.getByRole('button', { name: 'Read command receipt' })).toBeVisible();
  await act(async () => { release?.(); });
  view.unmount(); client.clear(); sessionStorage.clear();
});

it.each([['DATA_DENIED', 'acknowledged'], ['DATA_DENIED', 'lost'], ['CONNECTION_UNAVAILABLE', 'acknowledged'], ['MODEL_NOT_REGISTERED', 'acknowledged'], ['OPERATION_FINISHED', 'acknowledged'], ['ANSWER_DENIED', 'acknowledged']])('SOURCE definite command refusal %s allows a corrected explicit command with %s reply', async (code, reply) => {
  const { state, writes, fetcher, view, client } = mountedRun();
  state.run = { ...state.run, question_id: id };
  state.summary = { ...state.summary, run: state.run, question: { question_id: id, run_id: runId, task_id: id, revision: 1, kind: 'CLARIFICATION', cause: 'Inert detail', text: 'Which part?', refs: [], state: 'PENDING', answer_ref: null, command_id: null } };
  const original = fetcher.getMockImplementation()!;
  fetcher.mockImplementation(async (input, init) => {
    if (init?.method === 'POST' && writes.length === 0) {
      const payload: unknown = JSON.parse(String(init.body));
      if (!isRecord(payload)) throw new Error('Invalid command');
      writes.push(payload);
      return new Response(JSON.stringify({ error: { code, correlation_id: id } }), { status: 409 });
    }
    if (String(input).startsWith('/api/v1/runs/commands/')) return new Response(JSON.stringify({ error: { code: 'NOT_FOUND', correlation_id: id } }), { status: 404 });
    const response = await original(input, init);
    if (init?.method === 'POST' && reply === 'lost') throw new Error('Lost corrected answer acknowledgement');
    return response;
  });
  const user = userEvent.setup();
  const field = await screen.findByLabelText('Non-secret clarification');
  await user.type(field, 'First synthetic answer');
  const submit = screen.getByRole('button', { name: 'Submit clarification' });
  await user.click(submit);
  await screen.findByText(/Refused; refresh and give fresh explicit consent/);
  expect(sessionStorage.getItem(`omnis-run-command-${id}`)).toBeNull();
  expect(screen.queryByRole('button', { name: 'Read command receipt' })).not.toBeInTheDocument();
  if (code === 'DATA_DENIED') expect(screen.getByText(/Selected data was refused/)).toBeVisible();
  state.run = { ...state.run, revision: 8 };
  state.summary = { ...state.summary, run: state.run };
  await user.click(screen.getByRole('button', { name: 'Refresh run' }));
  await waitFor(() => expect(field).toHaveValue(''));
  await user.clear(field); await user.type(field, 'Corrected synthetic answer');
  expect(submit).toBeEnabled();
  expect(writes).toHaveLength(1);
  await user.click(submit);
  if (reply === 'lost') {
    await screen.findByText(/Read the same command; no resend/);
    await user.click(screen.getByRole('button', { name: 'Read command receipt' }));
    await screen.findByText(/Receipt unavailable; command remains unknown/);
    await user.click(screen.getByRole('button', { name: 'Refresh run' }));
    expect(submit).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Stop run' })).toBeEnabled();
    expect(sessionStorage.getItem(`omnis-run-command-${id}`)).toContain(writes[1]?.command_id);
  } else await screen.findByText(/ADMITTED ·/);
  expect(writes).toHaveLength(2);
  expect(writes[1]).toMatchObject({ action: 'answer', run_id: runId, question_id: id, expected_revision: 8, expected_generation: 3, answer: 'Corrected synthetic answer' });
  expect(writes[1]?.command_id).not.toBe(writes[0]?.command_id);
  view.unmount(); client.clear(); sessionStorage.clear();
});

it.each([['CONTROL_UNAVAILABLE', 503], ['HTTP_ERROR', 409], ['NOT_FOUND', 404]] as const)('SOURCE uncertain command %s and receipt NOT_FOUND never release pending or resend', async (code, status) => {
  const { writes, fetcher, view, client } = mountedRun();
  const original = fetcher.getMockImplementation()!;
  fetcher.mockImplementation(async (input, init) => {
    if (init?.method === 'POST') {
      const payload: unknown = JSON.parse(String(init.body));
      if (!isRecord(payload)) throw new Error('Invalid command');
      writes.push(payload);
      return new Response(JSON.stringify({ error: { code, correlation_id: id } }), { status });
    }
    if (String(input).startsWith('/api/v1/runs/commands/')) return new Response(JSON.stringify({ error: { code: 'NOT_FOUND', correlation_id: id } }), { status: 404 });
    return original(input, init);
  });
  const user = userEvent.setup();
  const pause = await screen.findByRole('button', { name: 'Pause run' });
  await waitFor(() => expect(pause).toBeEnabled());
  await user.click(pause);
  await screen.findByText(/Read the same command; no resend/);
  const stored = sessionStorage.getItem(`omnis-run-command-${id}`);
  expect(stored).toContain(writes[0]?.command_id);
  await user.click(screen.getByRole('button', { name: 'Read command receipt' }));
  await screen.findByText(/Receipt unavailable; command remains unknown/);
  await user.click(screen.getByRole('button', { name: 'Refresh run' }));
  expect(pause).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Stop run' })).toBeEnabled();
  expect(sessionStorage.getItem(`omnis-run-command-${id}`)).toBe(stored);
  expect(writes).toHaveLength(1);
  view.unmount(); client.clear(); sessionStorage.clear();
});

it('SOURCE binds clarification to the displayed question revision and bounds complete escaped JSON', async () => {
  const { state, writes, view, client } = mountedRun();
  const question = { question_id: id, run_id: runId, task_id: id, revision: 1, kind: 'CLARIFICATION', cause: 'Inert detail', text: 'Which part?', refs: [], state: 'PENDING', answer_ref: null, command_id: null } as const;
  state.run.question_id = id;
  state.summary = { ...state.summary, run: state.run, question: { ...question, refs: [] } };
  const field = await screen.findByLabelText('Non-secret clarification');
  fireEvent.change(field, { target: { value: '\\'.repeat(1800) } });
  expect(screen.getByRole('button', { name: 'Submit clarification' })).toBeDisabled();
  fireEvent.change(field, { target: { value: 'Only the selected part' } });
  expect(screen.getByRole('button', { name: 'Submit clarification' })).toBeEnabled();
  state.run = { ...state.run, revision: 8 };
  state.summary = { ...state.summary, run: state.run, question: { ...question, revision: 2, text: 'New clarification', refs: [] } };
  await userEvent.setup().click(screen.getByRole('button', { name: 'Refresh run' }));
  await screen.findByText('New clarification');
  expect(screen.getByLabelText('Non-secret clarification')).toHaveValue('');
  expect(screen.getByRole('button', { name: 'Submit clarification' })).toBeDisabled();
  expect(writes).toHaveLength(0);
  view.unmount(); client.clear();
});

it('SOURCE pages actual spawn events, inspects only selected attempts and resets identity on a new run', async () => {
  const { state, writes, fetcher, view, client } = mountedRun('stream');
  const attempt: components['schemas']['Attempt'] = { instance_id: instance.instance_id, run_id: runId, task_id: id, attempt_id: id, role: 'RECON', parent_task_id: instance.instance_id, state: 'SUCCEEDED', brief: 'Actual delegated task', input_refs: [], input_text: 'Allowed synthetic input', instructions: 'Pinned composed instructions', configured_model: 'fixture/recon-override', observed_model: 'fixture/observed', skill_refs: [], result_summary: 'Bounded result', result_ref: { ...setup, revision: 1 }, read_receipt_ref: null, call_id: 'call-1', tool_arguments: 'read_context', tool_output: 'Persisted synthetic output', correction_count: 0 };
  const brain: components['schemas']['Attempt'] = { ...attempt, role: 'BRAIN', task_id: instance.instance_id, attempt_id: instance.instance_id, parent_task_id: null };
  state.summary = { ...state.summary, attempts: [attempt, brain], has_more: true };
  const original = fetcher.getMockImplementation()!;
  fetcher.mockImplementation(async (input, init) => {
    const path = String(input);
    if (path.includes('/events?')) {
      const cursor = Number(path.split(':').at(-1));
      const next = cursor + 1;
      return new Response(JSON.stringify({ run_id: state.run.run_id, through_cursor: next, has_more: cursor === 0, as_of: state.summary.as_of, events: [{ event_id: next === 1 ? id : instance.instance_id, run_id: state.run.run_id, task_id: id, attempt_id: id, sequence: next, kind: 'result', summary: `Persisted event ${next}`, refs: [], call_id: 'call-1', created_at: state.summary.as_of }] }));
    }
    if (path.includes('/attempts/')) return new Response(JSON.stringify(attempt));
    return original(input, init);
  });
  await screen.findByRole('button', { name: /RECON/ });
  expect(fetcher.mock.calls.some(([path]) => String(path).includes('/attempts/'))).toBe(false);
  expect(screen.getByText(/Some attempts are omitted/)).toBeVisible();
  expect(screen.getByRole('button', { name: /RECON/ }).closest('li')?.parentElement?.closest('li')).toHaveTextContent('BRAIN');
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: /RECON/ }));
  const inspector = await screen.findByRole('region', { name: 'Agent inspector' });
  expect(inspector).toHaveTextContent('Allowed synthetic input');
  expect(inspector).toHaveTextContent('fixture/recon-override');
  expect(inspector).toHaveTextContent('Persisted synthetic output');
  expect(screen.getByRole('button', { name: /RECON/ })).toHaveAttribute('aria-pressed', 'true');
  await user.click(screen.getByRole('button', { name: 'Next events' }));
  await screen.findByRole('button', { name: 'result · Persisted event 2' });
  await user.click(screen.getByRole('button', { name: 'First events' }));
  await screen.findByRole('button', { name: 'result · Persisted event 1' });
  await user.click(screen.getByRole('button', { name: 'Next events' }));
  await screen.findByRole('button', { name: 'result · Persisted event 2' });
  const newRun = '00000000-0000-4000-8000-000000000099';
  state.run = { ...state.run, run_id: newRun, revision: 1, through_cursor: 1 };
  state.summary = { ...state.summary, run: state.run, attempts: [], has_more: false };
  await user.click(screen.getByRole('button', { name: 'Refresh run' }));
  await waitFor(() => expect(within(screen.getByRole('region', { name: 'Inert run' })).getByText(new RegExp(`Run ${newRun}`))).toBeVisible());
  await waitFor(() => expect(screen.queryByRole('region', { name: 'Agent inspector' })).not.toBeInTheDocument());
  expect(fetcher.mock.calls.some(([path]) => String(path) === `/api/v1/runs/${newRun}/events?after=${newRun}:0`)).toBe(true);
  expect(fetcher.mock.calls.some(([path]) => String(path).startsWith(`/api/v1/runs/${newRun}/attempts/`))).toBe(false);
  expect(writes).toHaveLength(0);
  view.unmount(); client.clear();
});

it('SOURCE retains the newer run revision when a delayed read regresses', async () => {
  const { state, client, view } = mountedRun();
  await screen.findByRole('button', { name: 'Pause run' });
  await waitFor(() => expect(client.getQueryData(['private', 'run-summary', runId])).toBeTruthy());
  state.run = { ...state.run, revision: 6, through_cursor: 5, state: 'PAUSED' };
  state.summary = { ...state.summary, run: state.run };
  await userEvent.setup().click(screen.getByRole('button', { name: 'Refresh run' }));
  await screen.findByText('Run readback unavailable or stale; no state or effects are inferred.');
  expect(screen.getByRole('region', { name: 'Inert run' })).toHaveTextContent('RUNNING · revision 7');
  expect(screen.getByRole('button', { name: 'Resume run' })).toBeDisabled();
  view.unmount(); client.clear();
});

it('SOURCE does not combine newer run state with older owner or phase claims', async () => {
  const { state, client, view } = mountedRun();
  await waitFor(() => expect(client.getQueryData(['private', 'run-summary', runId])).toBeTruthy());
  state.run = { ...state.run, revision: 8 };
  await act(async () => { await client.invalidateQueries({ queryKey: ['private', 'engagement-run', id] }); });
  await waitFor(() => expect(screen.getByRole('region', { name: 'Inert run' })).toHaveTextContent('RUNNING · revision 8'));
  expect(screen.getByRole('region', { name: 'Inert run' })).toHaveTextContent('owner unverified · phase unknown');
  view.unmount(); client.clear();
});

it('SOURCE HOLD is read-only until an explicit Resume and stays HOLD until persisted readback', async () => {
  const { state, writes, view, client } = mountedRun();
  state.run = { ...state.run, state: 'HOLD', reason: 'Provider funding requires operator review' };
  state.summary = { ...state.summary, run: state.run };
  const user = userEvent.setup();
  const resume = await screen.findByRole('button', { name: 'Resume run' });
  await waitFor(() => expect(resume).toBeEnabled());
  await user.click(screen.getByRole('button', { name: 'Refresh run' }));
  expect(writes).toHaveLength(0);
  await user.click(resume);
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0]).toMatchObject({ action: 'resume', run_id: runId, expected_revision: 7, expected_generation: 3 });
  expect(screen.getByRole('region', { name: 'Inert run' })).toHaveTextContent('HOLD · revision 7');
  state.run = { ...state.run, state: 'RUNNING', reason: null, revision: 8 };
  state.summary = { ...state.summary, run: state.run };
  await user.click(screen.getByRole('button', { name: 'Refresh run' }));
  await waitFor(() => expect(screen.getByRole('region', { name: 'Inert run' })).toHaveTextContent('RUNNING · revision 8'));
  expect(writes).toHaveLength(1);
  view.unmount(); client.clear();
});

it('SOURCE expires the run reader on a private 401 without repopulating its cache', async () => {
  const { fetcher, client, view } = mountedRun();
  const original = fetcher.getMockImplementation()!;
  fetcher.mockImplementation(async (input, init) => String(input).endsWith('/summary') ? new Response(JSON.stringify({ error: { code: 'UNAUTHENTICATED', correlation_id: id } }), { status: 401 }) : original(input, init));
  await screen.findByLabelText('Pairing code');
  await waitFor(() => expect(client.getQueryCache().findAll({ queryKey: ['private'] })).toHaveLength(0));
  expect(screen.queryByRole('region', { name: 'Inert run' })).not.toBeInTheDocument();
  expect(screen.queryByRole('region', { name: 'Global run control' })).not.toBeInTheDocument();
  expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
  view.unmount(); client.clear();
});

it('SOURCE exposes selected inert input and does not start from a read or reload', async () => {
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async input => {
    const path = String(input);
    return new Response(JSON.stringify(path === '/api/session' ? session : path === '/health/ready' ? health : path === '/api/instance' ? { ...instance, admission_open: true } : path === `/api/v1/engagements/${id}` ? draft : path === '/api/v1/runs/publications' ? [] : null));
  });
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/engagements/${id}/overview`]}><App /></MemoryRouter></QueryClientProvider>);
  const input = await screen.findByLabelText('Selected synthetic inert context');
  await userEvent.setup().type(input, 'Synthetic context chosen by the operator');
  expect(input).toHaveValue('Synthetic context chosen by the operator');
  expect(screen.getByRole('button', { name: 'Preflight inert run' })).toBeDisabled();
  expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
  expect(screen.getByRole('button', { name: 'Stop active run' })).toBeVisible();
});
