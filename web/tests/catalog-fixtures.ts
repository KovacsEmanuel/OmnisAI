import type { CatalogInspection, CatalogPin } from '../src/shared/api/catalog';
// Synthetic SOURCE/component-only metadata, never imported by the product.
export function inspectionFixture(): CatalogInspection {
  let number = 0;
  const makePin = (kind: CatalogPin['kind']): CatalogPin => ({ kind, id: `11111111-1111-4111-8111-${String(++number).padStart(12, '0')}`, revision: 1, digest: 'a'.repeat(64) });
  return { publication_ref: makePin('catalog-publication'), profile_key: 'contract-profile', generation: 2,
    owner_id: '22222222-2222-4222-8222-222222222222', profile_ref: makePin('profile'), snapshot_ref: makePin('candidate-snapshot'),
    technical_review_ref: makePin('technical-review'), static_evaluation_ref: makePin('evaluation-receipt'), pure_evaluation_ref: makePin('evaluation-receipt'), confirmation_ref: makePin('operator-confirmation'),
    source_draft_refs: [makePin('source-draft')], candidate_refs: [makePin('profile')], dependency_closure_refs: [], dependency_artifact_refs: [],
    material_digest: 'a'.repeat(64), resolved_index_digest: 'b'.repeat(64), dependency_closure_digest: 'c'.repeat(64), compiler_revision: 'sha256:' + 'd'.repeat(64), evaluator_revision: 'sha256:' + 'e'.repeat(64),
    requested: { model_key: null, effort: null, requirement: 'PREFERRED', on_unavailable: 'BLOCK' },
    review: 'RECORDED_STATIC_PASS', static: 'RECORDED_STATIC_PASS', pure: 'RECORDED_PURE_PASS', dependency_metadata: 'NO_EXTERNAL_DEPENDENCIES',
    material: 'NOT_VERIFIED', runtime: 'NOT_AVAILABLE', benchmark: 'NOT_VERIFIED', fixture: 'NOT_VERIFIED', security: 'NOT_VERIFIED', assessment_selectable: false, resolution: 'NO_MODEL' };
}
