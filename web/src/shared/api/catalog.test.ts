import { expect, it } from 'vitest';
import { decodeCatalogInspection, decodeCatalogPage } from './catalog';
import { inspectionFixture } from '../../../tests/catalog-fixtures';

it('decodes only exact bounded non-authoritative metadata and refuses stale-green or extra fields', () => {
  const view = inspectionFixture(), ref = view.publication_ref;
  expect(decodeCatalogInspection(view, ref.id, ref.digest)).toEqual(view);
  for (const bad of [{ ...view, compiler_revision: 'd'.repeat(64) }, { ...view, evaluator_revision: 'SHA256:' + 'e'.repeat(64) }, { ...view, runtime: 'READY' }, { ...view, assessment_selectable: true }, { ...view, extra: true }, { ...view, publication_ref: { ...ref, revision: true } }]) {
    expect(() => decodeCatalogInspection(bad, ref.id, ref.digest)).toThrow();
  }
  expect(() => decodeCatalogInspection(view, '33333333-3333-4333-8333-333333333333', ref.digest)).toThrow();
  expect(() => decodeCatalogPage({ items: [], has_more: true, next_after: ref.id })).toThrow();
});

it('accepts named retained bindings only with bounded exact matching pins', () => {
  const view = inspectionFixture(), ref = view.publication_ref, binding = view.catalog_bindings[0]!;
  for (const bindings of [
    [{ ...binding, extra: true }], [{ ...binding, package_key: 'wrong-package' }],
    [{ ...binding, entity_kind: 'schema' }], [{ ...binding, entity_kind: 'unknown' }],
    [{ ...binding, ref: { ...binding.ref, digest: 'f'.repeat(64) } }],
    [binding, binding], Array.from({ length: 129 }, () => binding),
    [{ ...binding, key: '../unsafe' }], [view.catalog_bindings[1]],
  ]) expect(() => decodeCatalogInspection({ ...view, catalog_bindings: bindings }, ref.id, ref.digest)).toThrow();
  expect(decodeCatalogInspection(view, ref.id, ref.digest).catalog_bindings).toEqual(view.catalog_bindings);
  const procedure = view.catalog_bindings[1]!;
  const aliased = { ...procedure, ref: { ...procedure.ref, id: binding.ref.id } };
  expect(() => decodeCatalogInspection({ ...view, catalog_bindings: [binding, aliased],
    candidate_refs: [view.profile_ref, binding.ref, aliased.ref] }, ref.id, ref.digest)).toThrow();
  const bindings = Array.from({ length: 127 }, (_, i) => {
    const name = `package-${i}`, pin = { ...binding.ref, id: `44444444-4444-4444-8444-${String(i).padStart(12, '0')}` };
    return { ...binding, package_key: name, key: name, ref: pin };
  });
  const maximum = { ...view, candidate_refs: [...bindings.map(b => b.ref), view.profile_ref],
    catalog_bindings: [...bindings, { package_key: '@profile', entity_kind: 'profile', key: view.profile_key, ref: view.profile_ref }] };
  expect(decodeCatalogInspection(maximum, ref.id, ref.digest).catalog_bindings).toHaveLength(128);
  expect(() => decodeCatalogInspection({ ...maximum, catalog_bindings: [...maximum.catalog_bindings, binding] }, ref.id, ref.digest)).toThrow();
});
