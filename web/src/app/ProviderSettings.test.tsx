import { focusManager, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { App } from './App';
// Historical OAuth UI remains covered, but is not mounted by product Settings.
vi.mock('../features/engagement/ProviderSettings', async () => import('../features/engagement/LegacyProviderSettings'));
import { health, instance } from '../../tests/fixtures';

const selection = { provider: 'openai-codex', model: 'gpt-6.1-sol', effort: 'xhigh' };
const emptyId = '00000000-0000-0000-0000-000000000000';
function providerView(operation_id = emptyId, configured = false, status = 'CONFIRMED') {
  return { operation_id, status, selection: status === 'CONFIRMED' && configured ? selection : null,
    configured: status === 'CONFIRMED' && configured, authenticated: 'NOT_VERIFIED',
    reachable: 'NOT_VERIFIED', inference_ready: false, oauth: 'NONE', challenge: null };
}
function mountProviders() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return { client, ...render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/settings/providers']}><App /></MemoryRouter></QueryClientProvider>) };
}
async function diagnostics() {
  const details = (await screen.findByText('Diagnostic')).closest('details')!;
  if (!details.open) await userEvent.setup().click(screen.getByText('Diagnostic'));
}

it('SOURCE default exposes only Provider, Model, Connect in native tab order and connects fresh in one click', async () => {
  const commands: { operation_id: string; action: string; selection: unknown }[] = [];
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return Response.json({ authenticated: true, csrf_token: 'a'.repeat(64) });
    if (init?.method !== 'PUT') return Response.json(providerView());
    const body = JSON.parse(String(init.body)); commands.push(body);
    return Response.json(providerView(body.operation_id, body.action !== 'read', body.action === 'connect' ? 'PENDING' : 'CONFIRMED'));
  }));
  mountProviders();
  const connect = await screen.findByRole('button', { name: 'Connect Codex' });
  await waitFor(() => expect(connect).toBeEnabled());
  expect(commands).toEqual([]);
  const user = userEvent.setup();
  screen.getByRole('combobox', { name: 'Provider' }).focus();
  await user.tab(); expect(screen.getByRole('combobox', { name: 'Model' })).toHaveFocus();
  await user.tab(); expect(connect).toHaveFocus();
  await user.tab(); expect(screen.getByText('Diagnostic')).toHaveFocus();
  expect(screen.getByText('Diagnostic').closest('details')).not.toHaveAttribute('open');
  expect(screen.getByText('Read native configuration')).not.toBeVisible();
  expect(screen.queryByRole('combobox', { name: 'Effort' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Log out of Codex locally' })).not.toBeInTheDocument();
  await user.dblClick(connect);
  await waitFor(() => expect(commands.map(item => item.action)).toEqual(['read', 'save', 'connect']));
  expect(new Set(commands.map(item => item.operation_id)).size).toBe(3);
  expect(commands[1]!.selection).toEqual(selection);
  expect(screen.queryByText('Connected')).not.toBeInTheDocument();
});

it.each(['read', 'save'])('SOURCE waits for exact pending %s confirmation before advancing', async pendingAction => {
  const commands: { operation_id: string; action: string }[] = [];
  const reads: string[] = [];
  let confirm = false;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return Response.json({ authenticated: true, csrf_token: 'a'.repeat(64) });
    if (init?.method === 'PUT') {
      const body = JSON.parse(String(init.body)); commands.push(body);
      return Response.json(providerView(body.operation_id, body.action === 'save' || body.action === 'connect', body.action === pendingAction ? 'PENDING' : 'CONFIRMED'));
    }
    reads.push(String(input));
    const target = commands.find(command => command.action === pendingAction);
    return Response.json(target ? providerView(target.operation_id, pendingAction === 'save', confirm ? 'CONFIRMED' : 'PENDING') : providerView());
  }));
  const { client } = mountProviders();
  await userEvent.setup().click(await screen.findByRole('button', { name: 'Connect Codex' }));
  const before = pendingAction === 'read' ? ['read'] : ['read', 'save'];
  await waitFor(() => expect(commands.map(item => item.action)).toEqual(before));
  await client.refetchQueries({ queryKey: ['private', 'provider-operation'] });
  expect(commands.map(item => item.action)).toEqual(before);
  confirm = true;
  await client.refetchQueries({ queryKey: ['private', 'provider-operation'] });
  await waitFor(() => expect(commands.map(item => item.action)).toEqual(['read', 'save', 'connect']));
  expect(reads).toContain(`/api/v1/settings/provider/operations/${commands.find(command => command.action === pendingAction)!.operation_id}`);
});

it('SOURCE fresh current unavailable still prepares configuration on an explicit Connect', async () => {
  const actions: string[] = [];
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return Response.json({ authenticated: true, csrf_token: 'a'.repeat(64) });
    if (init?.method !== 'PUT') return Response.json(providerView(emptyId, false, 'UNAVAILABLE'));
    const body = JSON.parse(String(init.body)); actions.push(body.action);
    return Response.json(providerView(body.operation_id, body.action !== 'read'));
  }));
  mountProviders();
  const connect = await screen.findByRole('button', { name: 'Connect Codex' });
  await waitFor(() => expect(connect).toBeEnabled());
  expect(actions).toEqual([]);
  await userEvent.setup().click(connect);
  await waitFor(() => expect(actions).toEqual(['read', 'save', 'connect']));
});

it.each(['BUSY', 'INDETERMINATE', 'UNAVAILABLE'])('SOURCE stops preparation on %s without Connect or replay', async status => {
  const commands: { action: string; operation_id: string }[] = [];
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return Response.json({ authenticated: true, csrf_token: 'a'.repeat(64) });
    if (init?.method !== 'PUT') return Response.json(commands.length ? providerView(commands[0]!.operation_id, true) : providerView());
    const body = JSON.parse(String(init.body)); commands.push(body);
    return Response.json(providerView(body.operation_id, false, status));
  }));
  const { client } = mountProviders();
  await userEvent.setup().click(await screen.findByRole('button', { name: 'Connect Codex' }));
  await screen.findByText(status === 'BUSY' ? 'Runtime busy. Stop execution before changing Settings.' : 'Outcome unknown. Do not repeat this action; recover the exact operation.');
  if (status !== 'BUSY') await userEvent.setup().click(screen.getByRole('button', { name: 'Recover exact operation' }));
  await act(async () => { await client.refetchQueries({ queryKey: ['private', 'provider-operation'] }); });
  expect(commands.map(item => item.action)).toEqual(['read']);
});

it('SOURCE reload of an unavailable known operation exposes exact recovery, not fresh Connect', async () => {
  const id = '11111111-1111-4111-8111-111111111111';
  const reads: string[] = [];
  let writes = 0;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return Response.json({ authenticated: true, csrf_token: 'a'.repeat(64) });
    if (init?.method === 'PUT') writes++;
    reads.push(String(input));
    return Response.json(providerView(id, false, 'UNAVAILABLE'));
  }));
  mountProviders();
  await screen.findByText('Outcome unknown. Do not repeat this action; recover the exact operation.');
  expect(screen.getByRole('button', { name: 'Connect Codex' })).toBeDisabled();
  await userEvent.setup().click(screen.getByRole('button', { name: 'Recover exact operation' }));
  expect(reads.at(-1)).toBe(`/api/v1/settings/provider/operations/${id}`);
  expect(writes).toBe(0);
});

it.each(['unmount', '401', 'logout'])('SOURCE fences a late save confirmation after %s', async interruption => {
  const commands: { action: string; operation_id: string }[] = [];
  let settle: ((response: Response) => void) | undefined;
  let signal: AbortSignal | null | undefined;
  let signedIn = true;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return signedIn ? Response.json({ authenticated: true, csrf_token: 'a'.repeat(64) }) : Response.json({ error: { code: 'UNAUTHENTICATED', correlation_id: emptyId } }, { status: 401 });
    if (String(input) === '/health/ready') return Response.json(health);
    if (String(input) === '/api/instance') return Response.json(instance);
    if (String(input) === '/api/logout') { signedIn = false; return new Response(null, { status: 204 }); }
    if (init?.method !== 'PUT') return Response.json(providerView());
    const body = JSON.parse(String(init.body)); commands.push(body);
    if (body.action === 'save') { signal = init.signal; return new Promise<Response>(resolve => { settle = resolve; }); }
    return Response.json(providerView(body.operation_id));
  }));
  const mounted = mountProviders();
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: 'Connect Codex' }));
  await waitFor(() => expect(settle).toBeDefined());
  if (interruption === 'unmount') mounted.unmount();
  if (interruption === 'logout') {
    await user.click(screen.getByRole('link', { name: 'Runtime & data' }));
    await user.click(await screen.findByRole('button', { name: /^Log out$/ }));
    await screen.findByText('Logged out. The server session was revoked.');
  }
  if (interruption === '401') signedIn = false;
  await act(async () => {
    settle!(interruption === '401' ? Response.json({ error: { code: 'UNAUTHENTICATED', correlation_id: emptyId } }, { status: 401 }) : Response.json(providerView(commands[1]!.operation_id, true)));
    await new Promise(resolve => setTimeout(resolve, 25));
  });
  if (interruption === '401') await screen.findByLabelText('Pairing code');
  expect(signal?.aborted).toBe(true);
  expect(commands.map(item => item.action)).toEqual(['read', 'save']);
});

it('SOURCE config expiry stops preparation even when an exact recovery later confirms save', async () => {
  const commands: { action: string; operation_id: string }[] = [];
  let confirmed = false;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return Response.json({ authenticated: true, csrf_token: 'a'.repeat(64) });
    if (init?.method === 'PUT') {
      const body = JSON.parse(String(init.body)); commands.push(body);
      return Response.json(providerView(body.operation_id, false, body.action === 'save' ? 'PENDING' : 'CONFIRMED'));
    }
    return Response.json(commands.length ? providerView(commands.at(-1)!.operation_id, confirmed, confirmed ? 'CONFIRMED' : 'PENDING') : providerView());
  }));
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
  const mounted = mountProviders();
  try {
    await act(async () => { await vi.advanceTimersByTimeAsync(10); });
    fireEvent.click(screen.getByRole('button', { name: 'Connect Codex' }));
    await act(async () => { await vi.advanceTimersByTimeAsync(20); });
    expect(commands.map(item => item.action)).toEqual(['read', 'save']);
    await act(async () => { await vi.advanceTimersByTimeAsync(30001); });
    expect(screen.getByText('Outcome unknown. Do not repeat this action; recover the exact operation.')).toBeVisible();
    confirmed = true;
    fireEvent.click(screen.getByRole('button', { name: 'Recover exact operation' }));
    await act(async () => { await vi.advanceTimersByTimeAsync(10); });
    expect(screen.getByText('Selection saved; model not tested.')).toBeVisible();
    expect(commands.map(item => item.action)).toEqual(['read', 'save']);
  } finally { mounted.unmount(); mounted.client.clear(); vi.useRealTimers(); }
});

it('SOURCE lost save reply stops chain and exact recovery never resumes or replays it', async () => {
  const commands: { operation_id: string; action: string }[] = [];
  const reads: string[] = [];
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return Response.json({ authenticated: true, csrf_token: 'a'.repeat(64) });
    if (init?.method === 'PUT') {
      const body = JSON.parse(String(init.body)); commands.push(body);
      if (body.action === 'save') throw new TypeError('SOURCE lost save reply');
      return Response.json(providerView(body.operation_id));
    }
    reads.push(String(input));
    return Response.json(commands.length ? providerView(commands.at(-1)!.operation_id, true) : providerView());
  }));
  mountProviders();
  await userEvent.setup().click(await screen.findByRole('button', { name: 'Connect Codex' }));
  await screen.findByText('Outcome unknown. Do not repeat this action; recover the exact operation.');
  expect(commands.map(item => item.action)).toEqual(['read', 'save']);
  await userEvent.setup().click(screen.getByRole('button', { name: 'Recover exact operation' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Connect Codex' })).toBeEnabled());
  expect(reads.at(-1)).toBe(`/api/v1/settings/provider/operations/${commands[1]!.operation_id}`);
  expect(commands.map(item => item.action)).toEqual(['read', 'save']);
});

it('hides reload challenge on failed GET and recovers current without Connect replay', async () => {
  const id = '11111111-1111-4111-8111-111111111111';
  let fail = false;
  let terminal = false;
  const reads: string[] = [];
  let writes = 0;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return Response.json({ authenticated: true, csrf_token: 'a'.repeat(64) });
    if (init?.method === 'PUT') { writes++; throw new Error('Unexpected write'); }
    reads.push(String(input));
    if (fail) return Response.json({ error: { code: 'CONTROL_UNAVAILABLE' } }, { status: 503 });
    return Response.json({ operation_id: id, status: terminal ? 'CONFIRMED' : 'PENDING',
      selection: null, configured: false, authenticated: 'NOT_VERIFIED', reachable: 'NOT_VERIFIED',
      inference_ready: false, oauth: terminal ? 'CANCELLED' : 'CHALLENGE',
      challenge: terminal ? null : { code: 'TEST-CODE', url: 'https://auth.openai.com/codex/device' } });
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/settings/providers']}><App /></MemoryRouter></QueryClientProvider>);
  await screen.findByText('TEST-CODE');
  fail = true;
  await client.refetchQueries({ queryKey: ['private', 'provider-operation'] });
  await waitFor(() => expect(screen.queryByText('TEST-CODE')).not.toBeInTheDocument());
  expect(screen.getByText('Outcome unknown. Do not repeat this action; recover the exact operation.')).toBeInTheDocument();
  fail = false;
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: 'Recover exact operation' }));
  await screen.findByText('TEST-CODE');
  terminal = true;
  await client.refetchQueries({ queryKey: ['private', 'provider-operation'] });
  await waitFor(() => expect(screen.queryByText('TEST-CODE')).not.toBeInTheDocument());
  expect(writes).toBe(0);
  expect(new Set(reads)).toEqual(new Set(['/health/ready', '/api/v1/settings/provider/operations/current', `/api/v1/settings/provider/operations/${id}`]));
});

it('hides reload challenge at the finite UI validity limit even without a refetch', async () => {
  let holdRecovery = false;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return Response.json({ authenticated: true, csrf_token: 'a'.repeat(64) });
    if (holdRecovery) return new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
    });
    return Response.json({ operation_id: '11111111-1111-4111-8111-111111111111', status: 'PENDING', selection: null,
      configured: false, authenticated: 'NOT_VERIFIED', reachable: 'NOT_VERIFIED', inference_ready: false,
      oauth: 'CHALLENGE', challenge: { code: 'TEST-CODE', url: 'https://auth.openai.com/codex/device' } });
  }));
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] });
  try {
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={['/settings/providers']}><App /></MemoryRouter></QueryClientProvider>);
    await act(async () => { await vi.advanceTimersByTimeAsync(10); });
    expect(screen.getByText('TEST-CODE')).toBeInTheDocument();
    holdRecovery = true;
    fireEvent.click(screen.getByRole('button', { name: 'Recover exact operation' }));
    await act(async () => { await vi.advanceTimersByTimeAsync(900001); });
    expect(screen.queryByText('TEST-CODE')).not.toBeInTheDocument();
  } finally { vi.useRealTimers(); }
});

it('connects once, displays only fixed challenge, cancels same operation and clears code', async () => {
  const actions: string[] = [];
  const ids: string[] = [];
  let current = { operation_id: '00000000-0000-0000-0000-000000000000', action: 'current' };
  const selected = { provider: 'openai-codex', model: 'gpt-6.1-sol', effort: 'xhigh' };
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return Response.json({ authenticated: true, csrf_token: 'a'.repeat(64) });
    const body = init?.method === 'PUT' ? JSON.parse(String(init.body)) : current;
    current = body;
    if (init?.method === 'PUT') { actions.push(body.action); ids.push(body.operation_id); }
    const pending = body.action === 'connect';
    return Response.json({ operation_id: body.operation_id, status: pending ? 'PENDING' : 'CONFIRMED',
      selection: pending ? null : selected, configured: !pending, authenticated: pending ? 'NOT_VERIFIED' : 'ABSENT',
      reachable: 'NOT_VERIFIED', inference_ready: false, oauth: pending ? 'CHALLENGE' : body.action === 'cancel' ? 'CANCELLED' : 'NONE',
      challenge: pending ? { code: 'ABCD-EFGH', url: 'https://auth.openai.com/codex/device' } : null });
  }));
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={['/settings/providers']}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  await diagnostics();
  await user.click(await screen.findByRole('button', { name: 'Read native configuration' }));
  await user.click(await screen.findByRole('button', { name: 'Connect Codex' }));
  await screen.findByText('ABCD-EFGH');
  expect(screen.getByText('Model and effort compatibility are not verified. No inference is performed here.')).toBeVisible();
  expect(screen.getByText('Local reads never refresh credentials.')).toBeVisible();
  expect(screen.getByText('Cancel does not log out. Local logout does not revoke upstream access.')).toBeVisible();
  expect(screen.getByText('Diagnostic').closest('details')).toHaveAttribute('open');
  expect(screen.getByText('ABCD-EFGH')).toBeVisible();
  expect(screen.getByText('Native operation pending; no success yet.')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Cancel connection' })).toBeVisible();
  expect(screen.getByRole('link', { name: 'Open Codex device authorization' })).toHaveAttribute('href', 'https://auth.openai.com/codex/device');
  await user.click(screen.getByRole('button', { name: 'Cancel connection' }));
  await waitFor(() => expect(screen.queryByText('ABCD-EFGH')).not.toBeInTheDocument());
  expect(actions).toEqual(['read', 'connect', 'cancel']);
  expect(ids[1]).toBe(ids[2]);
  expect(screen.getByText('Inference ready: no')).toBeInTheDocument();
});

it.each([
  ['LOCAL_PRESENT', 'NONE', true],
  ['LOCAL_EXPIRED', 'NONE', true],
  ['LOCAL_UNKNOWN', 'SAVED', true],
  ['ABSENT', 'NONE', false],
  ['NOT_VERIFIED', 'NONE', false],
  ['LOCAL_UNKNOWN', 'NONE', false],
])('SOURCE NORM-F01 Logout requires affirmative grant evidence: %s/%s', async (authenticated, oauth, available) => {
  let effects = 0;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (init?.method && init.method !== 'GET') { effects++; throw new Error('Unexpected SOURCE effect'); }
    if (String(input) === '/api/session') return Response.json({ authenticated: true, csrf_token: 'a'.repeat(64) });
    if (String(input) === '/health/ready') return Response.json(health);
    return Response.json({ ...providerView('11111111-1111-4111-8111-111111111111', true), authenticated, oauth });
  }));
  mountProviders();
  await diagnostics();
  await screen.findByText('Configured: yes — native readback');
  const logout = screen.queryByRole('button', { name: 'Log out of Codex locally' });
  if (available) { expect(logout).toBeVisible(); expect(logout).toBeEnabled(); }
  else expect(logout).not.toBeInTheDocument();
  if (authenticated === 'LOCAL_UNKNOWN' && oauth === 'NONE') {
    expect(screen.getByText('Local authorization unknown; model not tested.')).toBeVisible();
    expect(screen.getByText('Local grant: unknown — no refresh attempted')).toBeVisible();
  }
  expect(effects).toBe(0);
});

it('reads a local grant and logs out once without claiming provider readiness', async () => {
  const actions: string[] = [];
  const selected = { provider: 'openai-codex', model: 'gpt-6.1-sol', effort: 'xhigh' };
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return Response.json({ authenticated: true, csrf_token: 'a'.repeat(64) });
    if (init?.method === 'PUT') {
      const body = JSON.parse(String(init.body));
      actions.push(body.action);
      return Response.json({ operation_id: body.operation_id, status: 'CONFIRMED', selection: selected,
        configured: true, authenticated: body.action === 'auth_read' ? 'LOCAL_PRESENT' : body.action === 'logout' ? 'ABSENT' : 'NOT_VERIFIED',
        reachable: 'NOT_VERIFIED', inference_ready: false });
    }
    throw new TypeError('Unexpected synthetic endpoint');
  }));
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={['/settings/providers']}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  await diagnostics();
  await user.click(await screen.findByRole('button', { name: 'Read native configuration' }));
  await user.click(await screen.findByRole('button', { name: 'Read local Codex grant' }));
  await screen.findByText('Local grant: present — not provider-verified');
  expect(screen.getByText('Provider reachable: not verified')).toBeInTheDocument();
  expect(screen.getByText('Inference ready: no')).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Log out of Codex locally' }));
  await screen.findByText('Local grant: absent — native readback');
  expect(actions).toEqual(['read', 'auth_read', 'logout']);
  expect(screen.queryByRole('button', { name: 'Log out of Codex locally' })).not.toBeInTheDocument();
});

it('saves exact requested selection and keeps lost responses unconfirmed without retry', async () => {
  const writes: unknown[] = [];
  const commands: { operation_id: string; action: string }[] = [];
  const reads: string[] = [];
  let lose = false;
  let selected: unknown = null;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return Response.json({ authenticated: true, csrf_token: 'a'.repeat(64) });
    if (init?.method === 'PUT') {
      const body = JSON.parse(String(init.body));
      commands.push(body);
      if (body.action === 'save') { writes.push(body.selection); selected = body.selection; }
      if (lose) throw new TypeError('Synthetic lost response');
      return Response.json({ operation_id: body.operation_id, status: 'CONFIRMED', selection: selected,
        configured: selected !== null, authenticated: 'NOT_VERIFIED', reachable: 'NOT_VERIFIED', inference_ready: false });
    }
    reads.push(String(input));
    return Response.json({ operation_id: String(input).split('/').at(-1), status: 'CONFIRMED', selection: selected,
      configured: selected !== null, authenticated: 'NOT_VERIFIED', reachable: 'NOT_VERIFIED', inference_ready: false });
  }));
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={['/settings/providers']}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  await diagnostics();
  await user.click(await screen.findByRole('button', { name: 'Read native configuration' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Save selection' })).toBeEnabled());
  lose = true;
  await user.click(screen.getByRole('button', { name: 'Save selection' }));
  await screen.findByText('Outcome unknown. Do not repeat this action; recover the exact operation.');
  expect(writes).toEqual([{ provider: 'openai-codex', model: 'gpt-6.1-sol', effort: 'xhigh' }]);
  expect(screen.getByRole('button', { name: 'Save selection' })).toBeDisabled();
  const lostId = commands.at(-1)!.operation_id;
  await user.click(screen.getByRole('button', { name: 'Read native configuration' }));
  expect(commands.map(command => command.action)).toEqual(['read', 'save']);
  expect(screen.getByRole('button', { name: 'Read native configuration' })).toBeDisabled();
  await user.click(screen.getByRole('button', { name: 'Recover exact operation' }));
  await screen.findByText('Selection saved; model not tested.');
  expect(reads.at(-1)).toBe(`/api/v1/settings/provider/operations/${lostId}`);
  expect(screen.getByText('Inference ready: no')).toBeInTheDocument();
});

it('polls the exact pending connection while unfocused without replaying Connect', async () => {
  const actions: string[] = [];
  const reads: string[] = [];
  const id = '11111111-1111-4111-8111-111111111111';
  let connected = false;
  let polls = 0;
  const view = (operation_id: string, oauth: 'NONE' | 'STARTING' | 'CHALLENGE' | 'SAVED') => ({ operation_id,
    status: oauth === 'STARTING' || oauth === 'CHALLENGE' ? 'PENDING' : 'CONFIRMED',
    selection: oauth === 'STARTING' || oauth === 'CHALLENGE' ? null : { provider: 'openai-codex', model: 'gpt-6.1-sol', effort: 'xhigh' },
    configured: oauth === 'NONE' || oauth === 'SAVED', authenticated: 'NOT_VERIFIED', reachable: 'NOT_VERIFIED', inference_ready: false,
    oauth, challenge: oauth === 'CHALLENGE' ? { code: 'BACKGROUND-CODE', url: 'https://auth.openai.com/codex/device' } : null });
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return Response.json({ authenticated: true, csrf_token: 'a'.repeat(64) });
    if (String(input) === '/health/ready') throw new Error('No health fixture needed');
    if (init?.method === 'PUT') {
      const body = JSON.parse(String(init.body));
      actions.push(body.action);
      connected = true;
      return Response.json(view(body.operation_id, 'STARTING'));
    }
    if (!connected) return Response.json(view(id, 'NONE'));
    reads.push(String(input));
    polls++;
    return Response.json(view(String(input).split('/').at(-1)!, polls === 1 ? 'STARTING' : polls === 2 ? 'CHALLENGE' : 'SAVED'));
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const mounted = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/settings/providers']}><App /></MemoryRouter></QueryClientProvider>);
  await diagnostics();
  await screen.findByText('Configured: yes — native readback');
  const user = userEvent.setup();
  screen.getByRole('combobox', { name: 'Provider' }).focus();
  await user.tab();
  expect(screen.getByRole('combobox', { name: 'Model' })).toHaveFocus();
  await user.tab();
  expect(screen.getByRole('button', { name: 'Connect Codex' })).toHaveFocus();
  await user.tab();
  expect(screen.getByText('Diagnostic')).toHaveFocus();
  await user.tab();
  expect(screen.getByRole('button', { name: 'Read native configuration' })).toHaveFocus();
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
  try {
    focusManager.setFocused(false);
    fireEvent.click(screen.getByRole('button', { name: 'Connect Codex' }));
    await act(async () => { await vi.advanceTimersByTimeAsync(10); });
    expect(polls).toBe(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(500); });
    expect(polls).toBe(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(screen.getByText('BACKGROUND-CODE')).toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(500); });
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(screen.queryByText('BACKGROUND-CODE')).not.toBeInTheDocument();
    expect(screen.getByText('Authorization saved locally; model not tested.')).toBeVisible();
    const settledReads = reads.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    expect(reads).toHaveLength(settledReads);
    expect(actions).toEqual(['connect']);
    expect(new Set(reads).size).toBe(1);
    expect(reads[0]).not.toBe('/api/v1/settings/provider/operations/current');
    expect(screen.getByText('Authenticated: not verified')).toBeInTheDocument();
    expect(screen.getByText('Inference ready: no')).toBeInTheDocument();
  } finally {
    mounted.unmount(); client.clear(); focusManager.setFocused(undefined); vi.useRealTimers();
  }
});

it('keeps cancellation intent above cached and late challenges until exact recovery settles', async () => {
  const id = '11111111-1111-4111-8111-111111111111';
  const challenge = { operation_id: id, status: 'PENDING', selection: null, configured: false,
    authenticated: 'NOT_VERIFIED', reachable: 'NOT_VERIFIED', inference_ready: false,
    oauth: 'CHALLENGE', challenge: { code: 'CANCEL-CODE', url: 'https://auth.openai.com/codex/device' } };
  const writes: unknown[] = [];
  const reads: string[] = [];
  let cancelReply: ((value: Response) => void) | undefined;
  let oldRead: ((value: Response) => void) | undefined;
  let hold = false;
  let cancelled = false;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return Response.json({ authenticated: true, csrf_token: 'a'.repeat(64) });
    if (String(input) === '/health/ready') throw new Error('No health fixture needed');
    if (init?.method === 'PUT') {
      writes.push(JSON.parse(String(init.body)));
      return new Promise<Response>(resolve => { cancelReply = resolve; });
    }
    reads.push(String(input));
    if (hold) return new Promise<Response>(resolve => { oldRead = resolve; });
    return Response.json(cancelled ? { ...challenge, status: 'CONFIRMED', oauth: 'CANCELLED', challenge: null } : challenge);
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const mounted = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/settings/providers']}><App /></MemoryRouter></QueryClientProvider>);
  try {
    await screen.findByText('CANCEL-CODE');
    hold = true;
    const reading = client.refetchQueries({ queryKey: ['private', 'provider-operation'] });
    await waitFor(() => expect(oldRead).toBeDefined());
    fireEvent.click(screen.getByRole('button', { name: 'Cancel connection' }));
    expect(screen.queryByText('CANCEL-CODE')).not.toBeInTheDocument();
    await act(async () => { oldRead!(Response.json(challenge)); await reading; });
    expect(screen.queryByText('CANCEL-CODE')).not.toBeInTheDocument();
    hold = false;
    await act(async () => { cancelReply!(Response.json({ ...challenge, oauth: 'CANCELLING', challenge: null })); });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Recover exact operation' })).toBeEnabled());
    await act(async () => {
      client.setQueryData(['private', 'provider-operation', id], challenge);
    });
    expect(screen.queryByText('CANCEL-CODE')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancel connection' })).toBeDisabled();
    cancelled = true;
    await userEvent.setup().click(screen.getByRole('button', { name: 'Recover exact operation' }));
    await screen.findByText('Connection cancelled and worker settled. Existing grants were not deleted.');
    expect(writes).toEqual([{ operation_id: id, action: 'cancel', selection: null }]);
    expect(reads.at(-1)).toBe(`/api/v1/settings/provider/operations/${id}`);
    expect(screen.getByText('Inference ready: no')).toBeInTheDocument();
  } finally { mounted.unmount(); client.clear(); }
});
