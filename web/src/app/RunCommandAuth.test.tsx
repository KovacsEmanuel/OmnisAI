import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import * as browserSession from '../features/bootstrap/BrowserSession';
import { App } from './App';
import { health, instance, session } from '../../tests/fixtures';
import { draft, id } from '../../tests/projection-fixtures';
import { isRecord } from '../shared/api/errors';

const useRealSession = browserSession.useSession;

it.each(['healthy', 'preflight-gap', 'receipt-gap', 'start-gap', 'stale-admission', 'preview-gap'] as const)('fences RunPanel command recovery at the actual %s caller commit', async schedule => {
  sessionStorage.clear();
  const publication = { kind: 'catalog-publication', id: '00000000-0000-4000-8000-000000000030', revision: 1, digest: 'c'.repeat(64) };
  const setup = { ...publication, instance_id: instance.instance_id, kind: 'run-setup-v1' };
  const choice = { connection_id: instance.instance_id, connection_revision: 1, model: 'fixture/pinned', output_tokens: 1024 };
  let expire: (() => void) | undefined;
  let armed = schedule === 'preflight-gap';
  const order: string[] = [];
  vi.spyOn(browserSession, 'useSession').mockImplementation(() => {
    const owner = useRealSession();
    expire = owner.expire;
    return { ...owner, readPrivate: async <T,>(read: () => Promise<T>, signal: AbortSignal): Promise<T> => {
      const value = await owner.readPrivate(read, signal);
      if (armed && isRecord(value) && typeof value.command_id === 'string' && ['READY', 'ADMITTED'].includes(String(value.state))) {
        armed = false;
        order.push('real readPrivate returned successfully');
        owner.expire(); // Deliberate seam: after the owner's final check, before the caller continuation.
        order.push('owner expired before RunPanel commit');
      }
      return value;
    } };
  });
  const writes: { command: string; path: string }[] = [];
  const receipts = new Map<string, object>();
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input);
    if (init?.method === 'POST') {
      const payload: unknown = JSON.parse(String(init.body));
      if (!isRecord(payload) || typeof payload.command_id !== 'string') throw new Error('Missing command');
      writes.push({ command: payload.command_id, path });
      const receipt = path.endsWith('/run-preflight') ? { command_id: payload.command_id, setup_ref: setup, run_id: null, revision: 1, state: 'READY' } : { command_id: payload.command_id, setup_ref: null, run_id: instance.instance_id, revision: 1, state: 'ADMITTED' };
      receipts.set(payload.command_id, receipt);
      if (schedule === 'receipt-gap' && path.endsWith('/run-preflight')) throw new Error('Lost admitted preflight reply');
      return Response.json(receipt, { status: receipt.state === 'READY' ? 200 : 202 });
    }
    return Response.json(path === '/api/session' ? session : path === '/health/ready' ? health : path === '/api/instance' ? { ...instance, admission_open: true } : path === `/api/v1/engagements/${id}` ? draft : path === '/api/v1/runs/publications' ? [publication] : path === '/api/v1/settings/providers' ? { schema_version: 2, command_id: null, vault_status: 'UNLOCKED', reachable: 'NOT_VERIFIED', connections: [{ connection_id: instance.instance_id, provider: 'openrouter', revision: 1, enabled: true, credential_present: true }], selection: { schema_version: 2, selection_id: instance.instance_id, revision: 1, default: choice, brain: null, recon: null, investigator: null, validator: null } } : path.startsWith('/api/v1/runs/commands/') ? receipts.get(path.split('/').at(-1) ?? '') : null);
  }));
  const removed = vi.spyOn(Storage.prototype, 'removeItem');
  const stored = vi.spyOn(Storage.prototype, 'setItem');
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = client.invalidateQueries.bind(client);
  vi.spyOn(client, 'invalidateQueries').mockImplementation(async (filters, options) => {
    await invalidate(filters, options);
    if (schedule === 'preview-gap' && writes.length === 1 && order.length === 0) {
      if (!expire) throw new Error('Missing owner');
      expire();
      order.push('owner expired after execute settlement, before preview promotion');
    }
  });
  const ids = vi.spyOn(crypto, 'randomUUID');
  const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/engagements/${id}/overview`]}><App /></MemoryRouter></QueryClientProvider>);
  const pointer = `omnis-run-command-${id}`;
  const user = userEvent.setup();
  await user.click(await screen.findByText('Prepare inert run', { selector: 'summary' }));
  await user.type(await screen.findByLabelText('Selected synthetic inert context'), 'Synthetic unsent context');
  await user.selectOptions(screen.getByLabelText('Qualified core publication'), publication.id);
  await user.click(screen.getByLabelText(/This text is synthetic and non-secret/));
  const preflight = screen.getByRole('button', { name: 'Preflight inert run' });
  await waitFor(() => expect(preflight).toBeEnabled());
  ids.mockClear();
  if (schedule === 'stale-admission') {
    preflight.addEventListener('click', () => { if (!expire) throw new Error('Missing owner'); expire(); order.push('owner expired before retained React click handler'); }, { once: true });
    act(() => { fireEvent.click(preflight); });
  } else await user.click(preflight);
  if (schedule === 'healthy' || schedule === 'start-gap') {
    await screen.findByRole('region', { name: 'Run preflight confirmation' });
    expect(ids).toHaveBeenCalledTimes(2); // Preflight command plus the actually promoted Start preview.
    expect(sessionStorage.getItem(pointer)).toBeNull();
    await user.click(screen.getByLabelText(/Confirm model execution/));
    armed = schedule === 'start-gap';
    removed.mockClear();
    await user.click(screen.getByRole('button', { name: 'Start inert run' }));
  }
  if (schedule === 'receipt-gap') {
    const receipt = await screen.findByRole('button', { name: 'Read command receipt' });
    expect(sessionStorage.getItem(pointer)).toContain(writes[0]?.command);
    armed = true;
    await user.click(receipt);
  }
  if (schedule === 'healthy') {
    await waitFor(() => expect(sessionStorage.getItem(pointer)).toBeNull());
    expect(writes.map(item => item.path)).toEqual([`/api/v1/engagements/${id}/run-preflight`, '/api/v1/runs']);
    expect(order).toEqual([]);
  } else {
    await screen.findByLabelText('Pairing code');
    expect(screen.queryByRole('region', { name: 'Run preflight confirmation' })).not.toBeInTheDocument();
    if (schedule === 'stale-admission') {
      expect(writes).toHaveLength(0);
      expect(stored.mock.calls.filter(([key]) => key === pointer)).toHaveLength(0);
    } else if (schedule === 'preview-gap') {
      expect(order).toEqual(['owner expired after execute settlement, before preview promotion']);
      expect(ids).toHaveBeenCalledTimes(1); // No stale Start identity/preview was constructed.
      expect(writes).toHaveLength(1);
      expect(sessionStorage.getItem(pointer)).toBeNull(); // Settlement preceded the deliberate expiry.
    } else {
      expect(order).toEqual(['real readPrivate returned successfully', 'owner expired before RunPanel commit']);
      expect(writes).toHaveLength(schedule === 'start-gap' ? 2 : 1);
      expect(sessionStorage.getItem(pointer)).toContain(writes.at(-1)?.command);
      expect(removed.mock.calls.filter(([key]) => key === pointer)).toHaveLength(0);
    }
  }
  view.unmount(); client.clear(); sessionStorage.clear();
});
