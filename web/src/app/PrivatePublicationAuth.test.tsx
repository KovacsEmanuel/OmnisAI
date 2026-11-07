import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router';
import { expect, it, vi } from 'vitest';
import * as browserSession from '../features/bootstrap/BrowserSession';

import { ApiError, isRecord } from '../shared/api/errors';
import { isFullDraft } from '../shared/api/drafts';
import { revision } from '../../tests/draft-fixtures';
import { session } from '../../tests/fixtures';
import { configured, settingsBackend, entryId, entry } from '../../tests/settings-fixtures';
import { pendingStorage, remember, sessionScope, testStorage } from '../features/engagement/SettingsModels';
import type { ModelEntry } from '../features/engagement/SettingsModels';
import type { EntryTestView } from '../shared/api/modelTest';
import { App } from './App';

const useRealSession = browserSession.useSession;
function Location() { return <output aria-label="Current path">{useLocation().pathname}</output>; }

it.each(['wizard-save', 'wizard-reconcile', 'models-reload', 'models-recover', 'models-mutate'].flatMap(consumer => ['healthy', 'expire', '401', 'expired-before'].map(schedule => ({ consumer, schedule }))))('fences $consumer publication at the real owner $schedule boundary', async ({ consumer, schedule }) => {
  sessionStorage.clear();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const stalePublications: unknown[][] = [];
  const unsubscribe = client.getQueryCache().subscribe(event => {
    if (event.type === 'updated' && event.action.type === 'success' && event.query.queryKey[0] === 'private' && client.getQueryData(['session']) === null) stalePublications.push([...event.query.queryKey]);
  });
  let expire: (() => void) | undefined;
  let armed = false, cutovers = 0, revisions = 0;
  const wizard = consumer.startsWith('wizard');
  vi.spyOn(browserSession, 'useSession').mockImplementation(() => {
    const owner = useRealSession(); expire = owner.expire;
    return { ...owner, readPrivate: async <T,>(read: () => Promise<T>, signal: AbortSignal): Promise<T> => {
      const value = await owner.readPrivate(read, signal);
      const match = wizard ? isRecord(value) && 'payload' in value && ++revisions === (consumer === 'wizard-reconcile' ? 3 : 2) : isRecord(value) && 'library' in value;
      if (armed && match && schedule !== 'healthy' && schedule !== 'expired-before') {
        armed = false; cutovers++;
        if (schedule === '401') await owner.readPrivate(() => Promise.reject(new ApiError('UNAUTHENTICATED')), signal).catch((error: unknown) => { expect(error).toMatchObject({ code: 'UNAUTHENTICATED' }); });
        else owner.expire();
        expect(client.getQueryData(['session'])).toBeNull();
        expect(owner.commitPrivate(() => {}, signal)).toBe(false);
      }
      return value;
    } };
  });
  const { state, hook } = settingsBackend(configured);
  let stored = revision, confirms = 0, draftWrites = 0;
  if (wizard) hook.intercept = (path, body, method) => {
    if (path === '/api/v1/engagements' && method === 'POST') {
      if (!isFullDraft(body)) throw new Error('Invalid synthetic draft');
      stored = { ...revision, payload: body }; draftWrites++;
      return Response.json(stored, { status: 201 });
    }
    if (path === `/api/v1/engagements/${revision.engagement_id}`) {
      confirms++;
      if (consumer === 'wizard-reconcile' && confirms === 1) throw new Error('Synthetic lost confirmation');
      return Response.json(stored);
    }
    return undefined;
  };
  const pointer = '44444444-4444-4444-8444-444444444444';
  if (consumer === 'models-recover') {
    remember(pendingStorage, await sessionScope(session.csrf_token), { kind: 'keys', id: pointer });
    state.receipts.set(pointer, { ...state.keys, command_id: pointer });
  }
  const removed = vi.spyOn(Storage.prototype, 'removeItem');
  const app = <QueryClientProvider client={client}><MemoryRouter initialEntries={[wizard ? '/engagements/new' : '/settings/providers']}><App /><Location /></MemoryRouter></QueryClientProvider>;
  const view = render(wizard && schedule === 'healthy' ? <StrictMode>{app}</StrictMode> : app);
  const user = userEvent.setup();
  let action: HTMLElement;
  if (wizard) {
    fireEvent.change(await screen.findByLabelText('Engagement name'), { target: { value: 'Synthetic auth control' } });
    fireEvent.change(screen.getByLabelText('Authorization owner'), { target: { value: 'Synthetic operator' } });
    fireEvent.change(screen.getByLabelText('Authorization statement'), { target: { value: 'Synthetic local authorization' } });
    fireEvent.change(screen.getByLabelText('Scope origin'), { target: { value: 'https://fixture.invalid' } });
    action = screen.getByRole('button', { name: 'Next' });
  } else {
    await screen.findByRole('region', { name: 'Configured models' });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toHaveAttribute('aria-disabled', 'false'));
    if (consumer === 'models-mutate') {
      await user.click(screen.getByRole('button', { name: 'Details for Exact/Model via OpenRouter' }));
      await user.click(screen.getByRole('button', { name: 'Remove Exact/Model via OpenRouter' }));
      action = screen.getByRole('button', { name: 'Remove' });
    } else action = screen.getByRole('button', { name: consumer === 'models-recover' ? 'Recover exact receipt' : 'Reload current settings' });
  }
  armed = true;
  removed.mockClear();
  if (schedule === 'expired-before') {
    action.addEventListener('click', () => { if (!expire) throw new Error('Missing owner'); expire(); }, { once: true });
    act(() => { fireEvent.click(action); });
  } else await user.click(action);
  if (consumer === 'wizard-reconcile' && schedule !== 'expired-before') await user.click(await screen.findByRole('button', { name: 'Retry exact GET readback' }));
  if (schedule === 'healthy') {
    if (wizard) {
      await screen.findByText('Saved · revision 1');
      await waitFor(() => expect(screen.getByLabelText('Current path')).toHaveTextContent(`/engagements/${revision.engagement_id}/setup`));
      expect(client.getQueryData(['private', 'engagement', revision.engagement_id])).toBeDefined();
      expect(client.getQueryData(['private', 'draft', revision.engagement_id])).toBeDefined();
    } else {
      await screen.findByText(consumer === 'models-reload' ? 'Settings reloaded.' : consumer === 'models-recover' ? 'Settings recovered.' : 'Model removed.');
      expect(client.getQueryCache().findAll({ queryKey: ['private', 'settings-model-library'] }).some(query => query.state.data !== undefined)).toBe(true);
      expect(sessionStorage.getItem(pendingStorage)).toBeNull();
    }
  } else {
    await screen.findByLabelText('Pairing code');
    expect(stalePublications).toEqual([]);
    expect(client.getQueryCache().findAll({ queryKey: ['private'] }).filter(query => query.state.data !== undefined)).toEqual([]);
    if (wizard) expect(screen.getByLabelText('Current path')).toHaveTextContent('/engagements/new');
    expect(removed.mock.calls.filter(([key]) => key === pendingStorage)).toEqual([]);
    if (consumer === 'models-recover') expect(sessionStorage.getItem(pendingStorage)).toContain(pointer);
    else if (schedule === 'expired-before') expect(sessionStorage.getItem(pendingStorage)).toBeNull();
    if (schedule !== 'expired-before') expect(cutovers).toBe(1);
  }
  expect(draftWrites).toBe(wizard && schedule !== 'expired-before' ? 1 : 0);
  expect(state.writes).toHaveLength(consumer === 'models-mutate' && schedule !== 'expired-before' ? 1 : 0);
  expect(state.writes.every(write => write.path !== '/api/v1/model-test/entries')).toBe(true);
  expect(state.entries.some(item => item.entry_id === entryId)).toBe(consumer !== 'models-mutate' || schedule === 'expired-before');
  view.unmount(); client.clear(); unsubscribe(); sessionStorage.clear();
});

function completed(id: string, target: ModelEntry): EntryTestView {
  return {
    schema_version: 2, operation_id: id, state: 'FINISHED', state_revision: 3, finish_reason: 'COMPLETED', selection_revision: null,
    metadata_command_id: null, metadata_state: 'NOT_REQUESTED', reason: null, requested_provider: 'openrouter', requested_model: target.model, requested_output_tokens: target.output_tokens,
    observed_model: target.model, provider_status: null, result_state: 'COMPLETED', output_state: 'COMPLETE', response_text: 'OMNIS_MODEL_TEST_OK', usage_state: 'UNKNOWN', input_tokens: null, output_tokens: null, reasoning_tokens: null, cost_observed: null,
    system_message: 'Respond only with OMNIS_MODEL_TEST_OK. Use no tools.', user_message: 'This is a synthetic local settings test. Reply with OMNIS_MODEL_TEST_OK.', calls_limit: 1, wall_seconds: 300,
    entry_id: target.entry_id, entry_revision: target.revision, connection_id: target.connection_id, connection_revision: target.connection_revision, current: true,
  };
}

it.each(['start', 'read', 'connect-read', 'connect-latest'].flatMap(consumer => ['healthy', 'expire', '401'].map(schedule => ({ consumer, schedule }))))('fences Models $consumer sibling and unsent continuation after $schedule', async ({ consumer, schedule }) => {
  sessionStorage.clear();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const stale: unknown[][] = [];
  const unsubscribe = client.getQueryCache().subscribe(event => {
    if (event.type === 'updated' && event.action.type === 'success' && event.query.queryKey[0] === 'private' && client.getQueryData(['session']) === null) stale.push([...event.query.queryKey]);
  });
  let armed = false, matches = 0, cuts = 0;
  vi.spyOn(browserSession, 'useSession').mockImplementation(() => {
    const owner = useRealSession();
    return { ...owner, readPrivate: async <T,>(read: () => Promise<T>, signal: AbortSignal): Promise<T> => {
      const value = await owner.readPrivate(read, signal);
      if (armed && isRecord(value) && typeof value.operation_id === 'string') {
        matches++;
        const wanted = consumer === 'connect-read' ? 2 : consumer === 'connect-latest' ? 3 : 1;
        if (matches === wanted && schedule !== 'healthy') {
          armed = false; cuts++;
          if (schedule === '401') await owner.readPrivate(() => Promise.reject(new ApiError('UNAUTHENTICATED')), signal).catch((error: unknown) => { expect(error).toMatchObject({ code: 'UNAUTHENTICATED' }); });
          else owner.expire();
          expect(owner.commitPrivate(() => {}, signal)).toBe(false);
        }
      }
      return value;
    } };
  });
  const connecting = consumer.startsWith('connect');
  const { state, hook } = settingsBackend(configured, connecting ? [] : [entry], connecting ? [0, 1].map(i => ({ model: `Catalog/0${i}`, name: `Catalog/0${i}`, max_output_tokens: 1024, supports_max_tokens: true, reason: null })) : undefined);
  const operations = new Map<string, EntryTestView>();
  const seeded = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
  if (consumer === 'read') {
    operations.set(seeded, { ...completed(seeded, entry), state: 'RUNNING', state_revision: 2, finish_reason: null, result_state: null, response_text: null, output_state: 'ABSENT' });
    remember(testStorage, await sessionScope(session.csrf_token), seeded);
  }
  hook.intercept = (path, body, method) => {
    if (path === '/api/v1/model-test/entries' && method === 'PUT') {
      const target = state.entries.find(item => item.entry_id === body.entry_id);
      if (!target || typeof body.operation_id !== 'string') throw new Error('Missing synthetic entry');
      const value = completed(body.operation_id, target); operations.set(body.operation_id, value);
      return Response.json(value, { status: 202 });
    }
    if (path.includes('/entries/latest/')) {
      const value = [...operations.values()].find(item => path.endsWith('/' + item.entry_id));
      if (value) return Response.json(value);
    }
    if (path.startsWith('/api/v1/model-test/entries/')) {
      const value = operations.get(path.split('/').at(-1) ?? '');
      if (value) return Response.json(value);
    }
    return undefined;
  };
  const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/settings/providers']}><App /></MemoryRouter></QueryClientProvider>);
  const user = userEvent.setup();
  await screen.findByRole('region', { name: 'Configured models' });
  let action: HTMLElement;
  if (connecting) {
    await waitFor(() => expect(screen.getByRole('button', { name: 'Add models' })).toBeEnabled());
    await user.click(screen.getByRole('button', { name: 'Add models' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(await screen.findByRole('button', { name: 'Add Catalog/00' }));
    await user.click(screen.getByRole('button', { name: 'Add Catalog/01' }));
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('checkbox'));
    action = screen.getByRole('button', { name: 'Save & connect' });
  } else if (consumer === 'start') {
    const test = screen.getByRole('button', { name: 'Test Exact/Model via OpenRouter' });
    await waitFor(() => expect(test).toBeEnabled()); await user.click(test);
    await user.click(screen.getByRole('checkbox', { name: 'I approve using this model.' }));
    action = screen.getByRole('button', { name: 'Send model test' });
  } else {
    action = await screen.findByRole('button', { name: 'Read test status' });
    operations.set(seeded, completed(seeded, entry));
  }
  armed = true;
  await user.click(action);
  if (schedule === 'healthy') {
    if (connecting) await screen.findByText('Models connected.');
    else await waitFor(() => expect(client.getQueryCache().findAll({ queryKey: ['private', 'settings-entry-test'] }).some(query => isRecord(query.state.data) && query.state.data.state === 'FINISHED')).toBe(true));
  } else {
    await screen.findByLabelText('Pairing code');
    expect(cuts).toBe(1); expect(stale).toEqual([]);
    expect(client.getQueryCache().findAll({ queryKey: ['private'] }).filter(query => query.state.data !== undefined)).toEqual([]);
    expect(sessionStorage.getItem(testStorage)).toContain([...operations.keys()][0]);
  }
  expect(state.writes.filter(write => write.path === '/api/v1/model-test/entries')).toHaveLength(consumer === 'read' ? 0 : connecting && schedule === 'healthy' ? 2 : 1);
  expect(state.writes.every(write => write.body.expected_generation === undefined || write.body.expected_generation === 1)).toBe(true);
  view.unmount(); client.clear(); unsubscribe(); sessionStorage.clear();
});
