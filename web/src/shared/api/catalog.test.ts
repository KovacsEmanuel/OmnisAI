import { expect, it } from 'vitest';
import { decodeCatalogInspection, decodeCatalogPage } from './catalog';
import { inspectionFixture } from '../../../tests/catalog-fixtures';

it('decodes only exact bounded non-authoritative metadata and refuses stale-green or extra fields', () => {
  const view = inspectionFixture(), ref = view.publication_ref;
  expect(decodeCatalogInspection(view, ref.id, ref.digest)).toEqual(view);
  for (const bad of [{ ...view, runtime: 'READY' }, { ...view, assessment_selectable: true }, { ...view, extra: true }, { ...view, publication_ref: { ...ref, revision: true } }]) {
    expect(() => decodeCatalogInspection(bad, ref.id, ref.digest)).toThrow();
  }
  expect(() => decodeCatalogInspection(view, '33333333-3333-4333-8333-333333333333', ref.digest)).toThrow();
  expect(() => decodeCatalogPage({ items: [], has_more: true, next_after: ref.id })).toThrow();
});
