import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { App } from './App';
import { session, instance, health } from '../../tests/fixtures';
import { draft, id } from '../../tests/projection-fixtures';
import { syntheticRun as run, syntheticSummary, syntheticAttempt, inspection } from '../../tests/run-fixtures';

it('SOURCE reads whole-run metrics and every logical agent/history page without dispatch', async () => {
  const worker = '00000000-0000-4000-8000-000000000099';
  const actor = { ...syntheticAttempt, task_id: worker, attempt_id: worker };
  let revision = run.revision;
  const earlier = "00000000-0000-4000-8000-000000000001";
  const anchor = "00000000-0000-4000-8000-000000000050";
  const summary = { ...syntheticSummary, metrics: { ...syntheticSummary.metrics, agents: 26, attempts: 50 } };
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input), url = new URL(path, 'http://localhost');
    if (init?.method && init.method !== 'GET') throw new Error('Receive-only journey');
    if (url.pathname.endsWith('/agents')) {
      const more = !url.searchParams.has('after');
      return Response.json({ run_id: run.run_id, revision, agents: more ? [{ agent_id: 'brain', role: 'BRAIN', parent_agent_id: null, attempt_id: id, state: 'SUCCEEDED', brief: 'One Brain', attempts: 25 }, ...(revision > run.revision ? [{ agent_id: earlier, role: 'RECON', parent_agent_id: 'brain', attempt_id: earlier, state: 'RUNNING', brief: 'New earlier agent', attempts: 1 }] : []), { agent_id: anchor, role: 'RECON', parent_agent_id: 'brain', attempt_id: anchor, state: 'SUCCEEDED', brief: 'First page anchor', attempts: 1 }] : [{ agent_id: worker, role: 'RECON', parent_agent_id: 'brain', attempt_id: worker, state: 'INCONCLUSIVE', brief: 'Worker beyond first page', attempts: 1 }], has_more: more, next_after: more ? `${run.run_id}:${revision}:${anchor}` : null, as_of: summary.as_of });
    }
    if (url.pathname.includes('/agents/') && url.pathname.endsWith('/events')) {
      const after = Number(url.searchParams.get('after')?.split(':').at(-1) ?? 0);
      return Response.json({ run_id: run.run_id, agent_id: worker, through_cursor: after ? 22 : 21, events: [{ event_id: id, run_id: run.run_id, task_id: worker, attempt_id: worker, sequence: after ? 22 : 21, kind: after ? 'tool_result' : 'tool_called', summary: after ? 'Retained result after page boundary' : 'read_context', refs: [], call_id: 'pair', created_at: summary.as_of, pairing: 'MATCHED', paired_sequence: after ? 21 : 22 }], has_more: !after, as_of: summary.as_of });
    }
    if (url.pathname.endsWith(`/attempts/${worker}`)) return Response.json(inspection(actor));
    if (url.pathname.endsWith('/events')) { const after = Number(url.searchParams.get('after')?.split(':').at(-1) ?? 0); return Response.json({ run_id: run.run_id, through_cursor: after, events: [], has_more: false, as_of: summary.as_of }); }
    return Response.json(path === '/api/session' ? session : path === '/health/ready' ? health : path === '/api/instance' ? instance : path === `/api/v1/engagements/${id}` ? draft : path.endsWith('/summary') ? summary : path.endsWith('/run') || path === '/api/v1/runs/active' ? run : null);
  });
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const user = userEvent.setup();
  const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/engagements/${id}/overview`]}><App /></MemoryRouter></QueryClientProvider>);
  try {
    const accounting = await screen.findByRole('region', { name: 'Run accounting' });
    expect(within(accounting).getByText('26')).toBeVisible();
    expect(within(accounting).getByText('1h 0m 0s')).toBeVisible();
    expect(within(accounting).getByText(/LLM requests/)).toBeVisible();
    expect(within(accounting).getByText(/Cached.*0/)).toBeVisible();
    await user.click(screen.getByRole('link', { name: 'Activity' }));
    expect(screen.queryByRole('list', { name: 'Spawned agents' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Agents' }));
    expect(await screen.findByText(/25 recorded attempts/)).toBeVisible();
    expect(within(screen.getByRole('list', { name: 'Spawned agents' })).getAllByRole('button')).toHaveLength(2);
    revision += 1; // Retained fixture: activity and a new UUID behind the cursor.
    await user.click(screen.getByRole('button', { name: 'Next agents' }));
    const trigger = await screen.findByRole('button', { name: /Worker beyond first page/ });
    expect(screen.getByText(/New agents may precede this page/)).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Refresh run' }));
    expect(await screen.findByRole('button', { name: /Worker beyond first page/ })).toBeVisible();
    await user.click(trigger);
    const inspector = await screen.findByRole('region', { name: 'Agent inspector' });
    expect(await within(inspector).findByText(/MATCHED.*22/)).toBeVisible();
    await user.click(within(inspector).getByRole('button', { name: 'Next agent events' }));
    expect(await within(inspector).findByText('tool_result · Retained result after page boundary')).toBeVisible();
    expect(within(inspector).getByText('Composed instructions and pinned skills', { selector: 'summary' }).parentElement).not.toHaveAttribute('open');
    await user.keyboard('{Escape}');
    expect(trigger).toHaveFocus();
    await user.click(screen.getByRole('button', { name: 'Refresh agents from first page' }));
    expect(await screen.findByRole('button', { name: /New earlier agent/ })).toBeVisible();
    await waitFor(() => expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true));
  } finally { view.unmount(); client.clear(); }
});
