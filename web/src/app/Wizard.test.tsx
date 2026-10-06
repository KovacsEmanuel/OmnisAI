import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Link } from 'react-router';
import { expect, it, vi } from 'vitest';
import { csrf, engagementId, payload, revision } from '../../tests/draft-fixtures';
import { App } from './App';

it('creates an inert draft and confirms exact saved data with GET before reporting saved', async () => {
  const requests: string[] = [];
  let stored = revision;
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input);
    requests.push(`${init?.method ?? 'GET'} ${path}`);
    if (path === '/api/session') return new Response(JSON.stringify({ authenticated: true, csrf_token: csrf }));
    if (path === '/api/v1/dashboard') return new Response(JSON.stringify({}));
    if (path === '/api/v1/engagements' && init?.method === 'POST') {
      expect(JSON.parse(String(init.body))).toMatchObject({ name: payload.name, objective_text: payload.objective_text });
      stored = { ...revision, payload: JSON.parse(String(init.body)) };
      return new Response(JSON.stringify(stored), { status: 201 });
    }
    if (path === `/api/v1/engagements/${engagementId}`) return new Response(JSON.stringify(stored));
    throw new Error(`Unexpected synthetic request ${path}`);
  });
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/engagements/new']}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText('Engagement name'), payload.name);
  await user.type(screen.getByLabelText('Authorization owner'), payload.authorization.owner);
  await user.type(screen.getByLabelText('Authorization statement'), payload.authorization.statement);
  await user.type(screen.getByLabelText('Valid from (UTC)'), payload.authorization.valid_from);
  await user.type(screen.getByLabelText('Valid until (UTC)'), payload.authorization.valid_until);
  await user.click(screen.getByLabelText('Test focalizat'));
  await user.type(screen.getByLabelText('Obiectiv / instrucțiuni pentru Brain'), payload.objective_text);
  await user.type(screen.getByLabelText('Scope origin'), payload.scope[0]!.origin);
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  await waitFor(() => expect(requests).toContain(`GET /api/v1/engagements/${engagementId}`));
  await waitFor(() => expect(screen.getByText(/Saved · revision 1/)).toBeVisible());
  await waitFor(() => expect(screen.getByRole('button', { name: 'Start assessment' })).toBeDisabled());
  expect(screen.getAllByText(/CATALOG_UNAVAILABLE.*NOT_SELECTED/).length).toBeGreaterThan(0);
});

it('edits structured context, business matrix and budgets, then reviews the confirmed revision', async () => {
  let stored = revision;
  let edits = 0;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input);
    if (path === '/api/session') return new Response(JSON.stringify({ authenticated: true, csrf_token: csrf }));
    if (path === `/api/v1/engagements/${engagementId}` && init?.method === 'PUT') {
      edits += 1;
      expect(init.headers).toMatchObject({ 'If-Match': `"rev-1-${revision.digest}"`, 'X-CSRF-Token': csrf });
      expect(init.headers).toHaveProperty('X-Command-ID');
      stored = { ...revision, revision: 2, digest: 'c'.repeat(64), payload: JSON.parse(String(init.body)) };
      return new Response(JSON.stringify(stored));
    }
    if (path === `/api/v1/engagements/${engagementId}`) return new Response(JSON.stringify(stored));
    throw new Error(`Unexpected synthetic request ${path}`);
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/engagements/${engagementId}/setup`]}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  await screen.findByRole('heading', { name: payload.name });
  await user.click(await screen.findByRole('button', { name: '2. Application context' }));
  await user.clear(screen.getByLabelText('Seed URLs (one per line)'));
  await user.type(screen.getByLabelText('Seed URLs (one per line)'), 'https://synthetic.invalid/new');
  await user.click(screen.getByRole('button', { name: 'Add business rule' }));
  await user.type(screen.getByLabelText('Principal 2'), 'Visitor');
  await user.type(screen.getByLabelText('Role 2'), 'Viewer');
  await user.type(screen.getByLabelText('Tenant 2'), 'Tenant A');
  await user.type(screen.getByLabelText('Object 2'), 'Invoice');
  await user.type(screen.getByLabelText('Operation 2'), 'GET');
  await user.type(screen.getByLabelText('Source 2'), 'Operator declaration');
  await user.click(screen.getByRole('button', { name: '3. Identities' }));
  expect(screen.getByText(/Anonymous is valid/)).toBeVisible();
  expect(screen.queryByLabelText(/password|secret/i)).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: '4. Rules & budgets' }));
  await user.clear(screen.getByLabelText('Maximum requests'));
  await user.type(screen.getByLabelText('Maximum requests'), '40');
  await user.clear(screen.getByLabelText('Validation reserved requests'));
  await user.type(screen.getByLabelText('Validation reserved requests'), '5');
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  await waitFor(() => expect(screen.getByText(/Saved · revision 2/)).toBeVisible());
  expect(edits).toBe(1);
  expect(stored.payload.application_context.seed_urls).toEqual(['https://synthetic.invalid/new']);
  expect(stored.payload.business_matrix[1]).toMatchObject({ principal: 'Visitor', object: 'Invoice' });
  expect(stored.payload.budgets).toMatchObject({ max_requests: 40, validation_reserved_requests: 5 });
  await user.click(screen.getByRole('button', { name: '5. Review & preflight' }));
  expect(screen.getByText(payload.objective_text, { normalizer: value => value })).toBeVisible();
  expect(screen.getByText(`2 · ${revision.id}`)).toBeVisible();
  expect(screen.getAllByText(/NOT_SELECTED/).length).toBeGreaterThan(0);
});

it('keeps the general default separate from a focused objective and edits typed constraints', async () => {
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async input => {
    if (String(input) === '/api/session') return new Response(JSON.stringify({ authenticated: true, csrf_token: csrf }));
    return new Response(JSON.stringify(revision));
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/engagements/${engagementId}/setup`]}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: '1. Target & permission' }));
  expect(screen.getByLabelText('Obiectiv / instrucțiuni pentru Brain')).toHaveValue(payload.objective_text);
  await user.click(screen.getByRole('button', { name: 'Add objective constraint' }));
  await user.type(screen.getByLabelText('Constraint text 2'), 'No account changes');
  expect(screen.getByText(/operation catalog unavailable/i)).toBeVisible();
  await user.click(screen.getByLabelText('Evaluare generală'));
  expect(screen.getByLabelText('Obiectiv / instrucțiuni pentru Brain')).toHaveValue(payload.objective_text);
  await user.click(screen.getByLabelText('Test focalizat'));
  expect(screen.getByLabelText('Obiectiv / instrucțiuni pentru Brain')).toHaveValue(payload.objective_text);
});

it('does not erase authored focused text that happens to equal the General default', async () => {
  const defaultText = 'Evaluează suprafața Web/API autorizată în limitele profilului selectat.';
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async input => new Response(JSON.stringify(
    String(input) === '/api/session' ? { authenticated: true, csrf_token: csrf } : {},
  ))));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/engagements/new']}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  const objective = await screen.findByLabelText('Obiectiv / instrucțiuni pentru Brain');
  expect(objective).toHaveValue(defaultText);
  await user.click(screen.getByLabelText('Test focalizat'));
  expect(objective).toHaveValue('');
  await user.type(objective, defaultText);
  await user.click(screen.getByLabelText('Evaluare generală'));
  await user.click(screen.getByLabelText('Test focalizat'));
  expect(objective).toHaveValue(defaultText);
});

it('keeps a nested 422 near its field and links the accessible error summary to focus', async () => {
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return new Response(JSON.stringify({ authenticated: true, csrf_token: csrf }));
    if (init?.method === 'PUT') return new Response(JSON.stringify({ error: { code: 'INVALID_INPUT', correlation_id: engagementId,
      field_errors: [{ field: 'application_context.seed_urls.0', code: 'INVALID_VALUE' }] } }), { status: 422 });
    return new Response(JSON.stringify(revision));
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/engagements/${engagementId}/setup`]}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: '2. Application context' }));
  await user.clear(screen.getByLabelText('Seed URLs (one per line)'));
  await user.type(screen.getByLabelText('Seed URLs (one per line)'), 'ftp://invalid');
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  const jump = await screen.findByRole('button', { name: 'application_context.seed_urls.0: Invalid value.' });
  expect(screen.getByLabelText('Seed URLs (one per line)')).toHaveAttribute('aria-invalid', 'true');
  await user.click(jump);
  await waitFor(() => expect(screen.getByLabelText('Seed URLs (one per line)')).toHaveFocus());
  expect(screen.getByLabelText('Seed URLs (one per line)')).toHaveValue('ftp://invalid');
});

it('shows an aggregate body 422 as a global error without a broken focus link', async () => {
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return new Response(JSON.stringify({ authenticated: true, csrf_token: csrf }));
    if (init?.method === 'PUT') return new Response(JSON.stringify({ error: { code: 'INVALID_INPUT', correlation_id: engagementId,
      field_errors: [{ field: 'body', code: 'TOO_LONG' }] } }), { status: 422 });
    return new Response(JSON.stringify(revision));
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/engagements/${engagementId}/setup`]}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  const name = await screen.findByLabelText('Engagement name');
  await waitFor(() => expect(name).toHaveValue(payload.name));
  await user.clear(name);
  await user.type(name, 'Still my local draft');
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  expect(await screen.findByText(/Draft exceeds the 1,000,000-byte aggregate limit/)).toBeVisible();
  expect(screen.queryByRole('button', { name: /body: Exceeds/ })).not.toBeInTheDocument();
  expect(name).toHaveValue('Still my local draft');
});

it('switches between cached engagement IDs without exposing the previous editable draft or accepting its delayed GET', async () => {
  const otherId = '00000000-0000-4000-8000-000000000030';
  const other = { ...revision, engagement_id: otherId, payload: { ...payload, name: 'Other authorized draft' } };
  const changed = { ...revision, revision: 2, digest: 'c'.repeat(64), payload: { ...payload, name: 'Local change on A' } };
  let releaseOldRead!: (response: Response) => void;
  const oldRead = new Promise<Response>(resolve => { releaseOldRead = resolve; });
  let oldReads = 0;
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input);
    if (path === '/api/session') return new Response(JSON.stringify({ authenticated: true, csrf_token: csrf }));
    if (path === `/api/v1/engagements/${engagementId}`) {
      if (init?.method === 'PUT') return new Response(JSON.stringify(changed));
      oldReads++;
      return oldReads > 2 ? oldRead : new Response(JSON.stringify(revision));
    }
    if (path === `/api/v1/engagements/${otherId}`) return new Response(JSON.stringify(other));
    throw new Error(`Unexpected synthetic request ${path}`);
  });
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(['private', 'engagement', otherId], other);
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/engagements/${engagementId}/setup`]}>
    <Link to={`/engagements/${otherId}/setup`}>Switch to other draft</Link><App />
  </MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  const name = await screen.findByLabelText('Engagement name');
  await waitFor(() => expect(name).toHaveValue(payload.name));
  await user.clear(name);
  await user.type(name, 'Local change on A');
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  await waitFor(() => expect(oldReads).toBeGreaterThan(2));
  await user.click(screen.getByRole('link', { name: 'Switch to other draft' }));
  expect(screen.queryByDisplayValue('Local change on A')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Save draft' })).toBeDisabled();
  releaseOldRead(new Response(JSON.stringify(changed)));
  await waitFor(() => expect(screen.getByLabelText('Engagement name')).toHaveValue('Other authorized draft'));
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(1);
  expect(screen.getByRole('button', { name: 'Start assessment' })).toBeDisabled();
});

it('refuses focused whitespace before PUT, then preserves exact Unicode edits on a 409 without retry', async () => {
  let writes = 0;
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return new Response(JSON.stringify({ authenticated: true, csrf_token: csrf }));
    if (init?.method === 'PUT') {
      writes++;
      return new Response(JSON.stringify({ error: { code: 'ENGAGEMENT_CONFLICT', correlation_id: engagementId, field_errors: [] } }), { status: 409 });
    }
    return new Response(JSON.stringify(revision));
  });
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/engagements/${engagementId}/setup`]}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  const objective = await screen.findByLabelText('Obiectiv / instrucțiuni pentru Brain');
  await waitFor(() => expect(objective).toHaveValue(payload.objective_text));
  await user.clear(objective);
  await user.type(objective, '   ');
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  expect(writes).toBe(0);
  expect(screen.getByText('Required value.')).toBeVisible();
  await user.clear(objective);
  await user.type(objective, '  🧪 Δ  ');
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  await waitFor(() => expect(screen.getByText(/Conflict · local edits preserved/)).toBeVisible());
  expect(objective).toHaveValue('  🧪 Δ  ');
  expect(writes).toBe(1);
  expect(screen.getByRole('button', { name: 'Save draft' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Start assessment' })).toBeDisabled();
});

it('requires an exact GET after a write receipt and retries only the readback', async () => {
  let written: typeof revision | null = null;
  let readbacks = 0;
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return new Response(JSON.stringify({ authenticated: true, csrf_token: csrf }));
    if (init?.method === 'PUT') {
      written = { ...revision, revision: 2, digest: 'c'.repeat(64), payload: JSON.parse(String(init.body)) };
      return new Response(JSON.stringify(written));
    }
    if (written) {
      readbacks++;
      return new Response(JSON.stringify(readbacks === 1 ? revision : written));
    }
    return new Response(JSON.stringify(revision));
  });
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/engagements/${engagementId}/setup`]}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  const objective = await screen.findByLabelText('Obiectiv / instrucțiuni pentru Brain');
  await waitFor(() => expect(objective).toHaveValue(payload.objective_text));
  await user.clear(objective);
  await user.type(objective, '  🧪 Δ  ');
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  await waitFor(() => expect(screen.getByText('Unconfirmed readback')).toBeVisible());
  expect(objective).toHaveValue('  🧪 Δ  ');
  expect(screen.queryByText(/Saved · revision 2/)).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Retry exact GET readback' }));
  await waitFor(() => expect(screen.getByText(/Saved · revision 2/)).toBeVisible());
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(1);
});

it('blocks edits while an explicit GET reconciliation is pending and never replays the PUT', async () => {
  let written: typeof revision | null = null;
  let readbacks = 0;
  let release!: (value: Response) => void;
  const held = new Promise<Response>(resolve => { release = resolve; });
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return new Response(JSON.stringify({ authenticated: true, csrf_token: csrf }));
    if (init?.method === 'PUT') {
      written = { ...revision, revision: 2, digest: 'c'.repeat(64), payload: JSON.parse(String(init.body)) };
      return new Response(JSON.stringify(written));
    }
    if (written) {
      readbacks++;
      return readbacks === 1 ? new Response(JSON.stringify(revision)) :
        readbacks === 2 ? held : new Response(JSON.stringify(written));
    }
    return new Response(JSON.stringify(revision));
  });
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/engagements/${engagementId}/setup`]}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  const objective = await screen.findByLabelText('Obiectiv / instrucțiuni pentru Brain');
  await waitFor(() => expect(objective).toHaveValue(payload.objective_text));
  await user.clear(objective);
  await user.type(objective, 'Readback must keep this exact edit');
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  await waitFor(() => expect(screen.getByText('Unconfirmed readback')).toBeVisible());
  await user.click(screen.getByRole('button', { name: 'Retry exact GET readback' }));
  try {
    await waitFor(() => expect(readbacks).toBe(2));
    expect(objective).toBeDisabled();
    expect(screen.getByRole('region', { name: 'Draft setup' })).toHaveAttribute('aria-busy', 'true');
  } finally { release(new Response(JSON.stringify(written))); }
  await waitFor(() => expect(screen.getByText('Saved · revision 2')).toBeVisible());
  expect(objective).toHaveValue('Readback must keep this exact edit');
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(1);
});

it('fences a late old-session Save GET after expiry and re-pair before accepting the new session revision', async () => {
  const newCsrf = 'd'.repeat(64);
  const oldReceipt = { ...revision, revision: 2, digest: 'c'.repeat(64), payload: { ...payload, name: 'Old session edit' } };
  const current = { ...revision, revision: 3, digest: 'e'.repeat(64), payload: { ...payload, name: 'Fresh session version' } };
  let releaseOld!: (response: Response) => void;
  const oldGet = new Promise<Response>(resolve => { releaseOld = resolve; });
  let posted = false;
  let paired = false;
  let oldGetStarted = false;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input);
    if (path === '/api/session') return new Response(JSON.stringify({ authenticated: true, csrf_token: paired ? newCsrf : csrf }));
    if (path === '/api/pairing') {
      paired = true;
      return new Response(JSON.stringify({ authenticated: true, csrf_token: newCsrf }));
    }
    if (path === `/api/v1/engagements/${engagementId}` && init?.method === 'PUT') {
      posted = true;
      return new Response(JSON.stringify(oldReceipt));
    }
    if (path === `/api/v1/engagements/${engagementId}`) {
      if (posted && !paired) { oldGetStarted = true; return oldGet; }
      return new Response(JSON.stringify(paired ? current : revision));
    }
    return new Response('{}');
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/engagements/${engagementId}/setup`]}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  const name = await screen.findByLabelText('Engagement name');
  await waitFor(() => expect(name).toHaveValue(payload.name));
  await user.clear(name);
  await user.type(name, 'Old session edit');
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  await waitFor(() => expect(oldGetStarted).toBe(true));
  client.setQueryData(['session'], null);
  await screen.findByLabelText('Pairing code');
  await user.type(screen.getByLabelText('Pairing code'), 'syntheticcode0001');
  await user.click(screen.getByRole('button', { name: /Pair browser/ }));
  await waitFor(() => expect(screen.getByLabelText('Engagement name')).toHaveValue('Fresh session version'));
  releaseOld(new Response(JSON.stringify(oldReceipt)));
  await waitFor(() => expect(screen.getByText(/Saved · revision 3/)).toBeVisible());
  expect(screen.queryByDisplayValue('Old session edit')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Start assessment' })).toBeDisabled();
});

it('rehydrates the confirmed revision after leaving Setup and returning in the same session', async () => {
  let stored = revision;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input) === '/api/session') return new Response(JSON.stringify({ authenticated: true, csrf_token: csrf }));
    if (init?.method === 'PUT') {
      stored = { ...revision, revision: 2, digest: 'c'.repeat(64), payload: JSON.parse(String(init.body)) };
      return new Response(JSON.stringify(stored));
    }
    return new Response(JSON.stringify(stored));
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/engagements/${engagementId}/setup`]}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  const objective = await screen.findByLabelText('Obiectiv / instrucțiuni pentru Brain');
  await waitFor(() => expect(objective).toHaveValue(payload.objective_text));
  await user.clear(objective);
  await user.type(objective, 'Edited on this tab');
  await user.click(screen.getByRole('button', { name: 'Save draft' }));
  await waitFor(() => expect(screen.getByText('Saved · revision 2')).toBeVisible());
  await user.click(screen.getByRole('link', { name: 'Overview' }));
  await user.click(screen.getByRole('link', { name: 'Setup' }));
  await waitFor(() => expect(screen.getByLabelText('Obiectiv / instrucțiuni pentru Brain')).toHaveValue('Edited on this tab'));
  expect(screen.getByText('Saved · revision 2')).toBeVisible();
});

it('adopts a newer server revision on explicit Refresh when the Setup form is clean', async () => {
  let remote = revision;
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async input => {
    if (String(input) === '/api/session') return new Response(JSON.stringify({ authenticated: true, csrf_token: csrf }));
    return new Response(JSON.stringify(remote));
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/engagements/${engagementId}/setup`]}><App /></MemoryRouter></QueryClientProvider>);
  await waitFor(() => expect(screen.getByLabelText('Obiectiv / instrucțiuni pentru Brain')).toHaveValue(payload.objective_text));
  remote = { ...revision, id: '00000000-0000-4000-8000-000000000022', revision: 2, digest: 'c'.repeat(64),
    payload: { ...payload, objective_text: 'Remote revision 2' } };
  await userEvent.setup().click(screen.getByRole('button', { name: 'Refresh engagement' }));
  await waitFor(() => expect(screen.getByLabelText('Obiectiv / instrucțiuni pentru Brain')).toHaveValue('Remote revision 2'));
  expect(screen.getByText('Saved · revision 2')).toBeVisible();
});

it('keeps dirty edits and exposes a newer server revision on Refresh without an automatic PUT', async () => {
  let remote = revision;
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async input => {
    if (String(input) === '/api/session') return new Response(JSON.stringify({ authenticated: true, csrf_token: csrf }));
    return new Response(JSON.stringify(remote));
  });
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/engagements/${engagementId}/setup`]}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  const objective = await screen.findByLabelText('Obiectiv / instrucțiuni pentru Brain');
  await waitFor(() => expect(objective).toHaveValue(payload.objective_text));
  await user.clear(objective);
  await user.type(objective, 'My unsaved text');
  remote = { ...revision, id: '00000000-0000-4000-8000-000000000022', revision: 2, digest: 'c'.repeat(64),
    payload: { ...payload, objective_text: 'Other editor text' } };
  await user.click(screen.getByRole('button', { name: 'Refresh engagement' }));
  await waitFor(() => expect(screen.getByText('Conflict · local edits preserved')).toBeVisible());
  expect(objective).toHaveValue('My unsaved text');
  expect(screen.getByText(/Server revision 2/)).toBeVisible();
  expect(screen.getByRole('button', { name: 'Save draft' })).toBeDisabled();
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(0);
});

it('revalidates the complete clean draft when polling observes a newer selected revision', async () => {
  let remote = revision;
  const fetcher = vi.fn<typeof fetch>().mockImplementation(async input => {
    if (String(input) === '/api/session') return new Response(JSON.stringify({ authenticated: true, csrf_token: csrf }));
    return new Response(JSON.stringify(remote));
  });
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/engagements/${engagementId}/setup`]}><App /></MemoryRouter></QueryClientProvider>);
  await waitFor(() => expect(screen.getByText('Saved · revision 1')).toBeVisible());
  remote = { ...revision, id: '00000000-0000-4000-8000-000000000022', revision: 2, digest: 'c'.repeat(64),
    payload: { ...payload, objective_text: 'Polled revision 2' } };
  client.setQueryData(['private', 'engagement', engagementId], remote);
  await waitFor(() => expect(screen.getByLabelText('Obiectiv / instrucțiuni pentru Brain')).toHaveValue('Polled revision 2'));
  expect(screen.getByText('Saved · revision 2')).toBeVisible();
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(0);
});
