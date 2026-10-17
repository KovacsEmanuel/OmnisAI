import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router';
import { api } from '../../shared/api/client';
import { catalogSelection } from '../../shared/api/catalog';
import type { CatalogPin } from '../../shared/api/catalog';
import { useSession } from '../bootstrap/BrowserSession';
import styles from './Engagement.module.css';

function Pin({ value }: { value: CatalogPin }) {
  return <span>{value.kind} · {value.id} · revision {value.revision} · <code>{value.digest}</code></span>;
}
export function CatalogSettings() {
  const { session, transition, readPrivate } = useSession();
  const [params, setParams] = useSearchParams();
  const id = params.get('publication'), digest = params.get('digest'), after = params.get('after');
  const selected = catalogSelection(id, digest);
  const invalid = (!selected && (id !== null || digest !== null)) || [...params.keys()].some(k => !['publication', 'digest', 'after'].includes(k)) || ['publication', 'digest', 'after'].some(k => params.getAll(k).length > 1);
  const enabled = !!session.data && !session.isError && transition === 'idle';
  const page = useQuery({ queryKey: ['private', 'catalog', after],
    queryFn: ({ signal }) => readPrivate(() => api.catalog(after, signal), signal),
    enabled, retry: false, gcTime: 0, networkMode: 'always' });
  const detail = useQuery({ queryKey: ['private', 'catalog-publication', id, digest],
    queryFn: ({ signal }) => readPrivate(() => api.catalogPublication(id!, digest!, signal), signal),
    enabled: enabled && selected && !invalid, retry: false, gcTime: 0, networkMode: 'always' });
  const view = enabled && !invalid && !detail.isError && detail.fetchStatus === 'idle' ? detail.data : undefined;
  return <section className={`${styles.core} ${styles.objective}`} aria-labelledby="catalog-heading">
    <h2 id="catalog-heading">Published catalog</h2>
    <p>Read-only inspection. Applies to new runs; this selection does not configure a run. Assessment and model execution are not enabled.</p>
    <p>Recorded STATIC/PURE qualification is not BENCHMARK, FIXTURE or SECURITY validation. Metadata presence does not mean installed or execution-ready.</p>
    {!enabled ? <p>Authenticated catalog read unavailable.</p> : <>
      {page.isError || page.fetchStatus === 'paused' ? <p role="alert">Published heads unavailable. No readiness is confirmed.</p> : page.isPending || page.isFetching ? <output>Reading published heads…</output> : page.data && <>
        {page.data.items.length === 0 ? <p>No current published entries.</p> : <ul>{page.data.items.map(entry => <li key={entry.publication_ref.id}>
          <button type="button" onClick={() => setParams({ ...(after ? { after } : {}), publication: entry.publication_ref.id, digest: entry.publication_ref.digest })}>Inspect {entry.profile_key}</button>
          <p><Pin value={entry.publication_ref} /></p>
        </li>)}</ul>}
        {page.data.has_more && page.data.next_after && <button type="button" onClick={() => setParams({ ...(id && digest ? { publication: id, digest } : {}), after: page.data!.next_after! })}>Next published page</button>}
        {after && <button type="button" onClick={() => setParams(id && digest ? { publication: id, digest } : {})}>First published page</button>}
      </>}
      <button type="button" onClick={() => { void page.refetch(); if (selected) void detail.refetch(); }} disabled={page.isFetching || detail.isFetching}>Reload read-only catalog</button>
      {invalid ? <p role="alert">Invalid exact publication selection.</p> : selected && <section aria-label="Exact publication">
        <h3>Exact publication</h3><p>{id} · <code>{digest}</code></p>
        {detail.isError || detail.fetchStatus === 'paused' ? <p role="alert">Exact publication unavailable or unsupported. No readiness is confirmed.</p> : detail.isPending || detail.isFetching ? <output>Reading exact immutable publication…</output> : view && <>
          <p>Profile: {view.profile_key} · publication generation {view.generation}</p>
          <p>Review: {view.review} · STATIC: {view.static} · PURE: {view.pure}</p>
          <p>Dependency metadata: {view.dependency_metadata} · Material: {view.material} · Runtime: {view.runtime}</p>
          <p>BENCHMARK: {view.benchmark} · FIXTURE: {view.fixture} · SECURITY: {view.security}</p>
          <p>Resolution: NO_MODEL · Assessment selectable: no</p>
          <p>Requested model: {view.requested.model_key ?? 'none'} · effort: {view.requested.effort ?? 'none'} · {view.requested.requirement} / {view.requested.on_unavailable}. Effective model: not available.</p>
          <section aria-label="Named packages and index identities">
            <h4>Named packages and index identities</h4>
            {view.catalog_bindings.some(binding => binding.entity_kind === 'package') ? <ul>{view.catalog_bindings.filter(binding => binding.entity_kind === 'package').map(binding => <li key={binding.package_key}>
              <h5>{binding.package_key}</h5><p><Pin value={binding.ref} /></p>
              <ul>{view.catalog_bindings.filter(entity => entity.package_key === binding.package_key && entity.entity_kind !== 'package').map(entity => <li key={`${entity.entity_kind}/${entity.key}`}>
                <span>{entity.entity_kind}: {entity.key}</span><p><Pin value={entity.ref} /></p>
              </li>)}</ul>
            </li>)}</ul> : <p>No named package metadata recorded.</p>}
          </section>
          <dl>{(['material_digest', 'resolved_index_digest', 'dependency_closure_digest', 'compiler_revision', 'evaluator_revision'] as const).map(field => <div key={field}><dt>{field}</dt><dd><code>{view[field]}</code></dd></div>)}</dl>
          <ul>{[view.profile_ref, view.snapshot_ref, view.technical_review_ref, view.static_evaluation_ref, view.pure_evaluation_ref, view.confirmation_ref].map(pin => <li key={pin.id}><Pin value={pin} /></li>)}</ul>
          {(['source_draft_refs', 'candidate_refs', 'dependency_closure_refs', 'dependency_artifact_refs'] as const).map(field => <div key={field}><h4>{field}</h4>{view[field].length ? <ul>{view[field].map(pin => <li key={pin.id}><Pin value={pin} /></li>)}</ul> : <p>None recorded.</p>}</div>)}
        </>}
      </section>}
    </>}
  </section>;
}
