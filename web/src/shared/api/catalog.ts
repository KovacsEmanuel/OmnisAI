import type { components } from './generated';
import { ApiError, isRecord, isUuid } from './errors';

export type CatalogPin = components['schemas']['CatalogPin'];
export type CatalogPage = components['schemas']['CatalogPage'];
export type CatalogInspection = components['schemas']['CatalogInspection'];
const kinds = ['source-draft', 'candidate-snapshot', 'technical-review', 'evaluation-receipt', 'operator-confirmation', 'catalog-publication', 'evaluation-input', 'contract-case-input', 'contract-case-records', 'qualified-release', 'release-qualification', 'package', 'profile', 'technique', 'procedure', 'schema', 'method', 'prompt', 'template', 'overlay', 'asset'];
const digest = (v: unknown): v is string => typeof v === 'string' && /^[0-9a-f]{64}$/.test(v);
const key = (v: unknown): v is string => typeof v === 'string' && /^[a-z][a-z0-9_.-]{0,127}$/.test(v);
const positive = (v: unknown): v is number => typeof v === 'number' && Number.isSafeInteger(v) && v >= 1;
function exact(value: Record<string, unknown>, keys: string[]) {
  return Object.keys(value).length === keys.length && keys.every(k => Object.hasOwn(value, k));
}
function isPin(value: unknown): value is CatalogPin {
  return isRecord(value) && exact(value, ['kind', 'id', 'revision', 'digest']) && kinds.includes(String(value.kind)) &&
    typeof value.id === 'string' && isUuid(value.id) && positive(value.revision) && value.revision < 2147483647 && digest(value.digest);
}
function isPins(value: unknown): value is CatalogPin[] {
  return Array.isArray(value) && value.length <= 128 && value.every(isPin) && new Set(value.map(v => JSON.stringify(v))).size === value.length;
}
function isPage(value: unknown): value is CatalogPage {
  if (!isRecord(value) || !exact(value, ['items', 'has_more', 'next_after']) || !Array.isArray(value.items) || value.items.length > 20 || typeof value.has_more !== 'boolean') return false;
  if (!value.items.every(v => isRecord(v) && exact(v, ['publication_ref', 'profile_key', 'generation']) && isPin(v.publication_ref) && v.publication_ref.kind === 'catalog-publication' && key(v.profile_key) && positive(v.generation))) return false;
  return value.has_more ? value.items.length === 20 && isRecord(value.items[19]) && isPin(value.items[19].publication_ref) && value.next_after === value.items[19].publication_ref.id : value.next_after === null;
}
export function decodeCatalogPage(value: unknown): CatalogPage {
  if (!isPage(value)) throw new ApiError('INVALID_RESPONSE');
  return value;
}
const pinFields = ['profile_ref', 'snapshot_ref', 'technical_review_ref', 'static_evaluation_ref', 'pure_evaluation_ref', 'confirmation_ref'];
const collectionFields = ['source_draft_refs', 'candidate_refs', 'dependency_closure_refs', 'dependency_artifact_refs'];
const digestFields = ['material_digest', 'resolved_index_digest', 'dependency_closure_digest', 'compiler_revision', 'evaluator_revision'];
function isInspection(value: unknown, id: string, sha: string): value is CatalogInspection {
  if (!isRecord(value) || !exact(value, ['publication_ref', 'profile_key', 'generation', 'owner_id', ...pinFields, ...collectionFields, ...digestFields, 'requested', 'review', 'static', 'pure', 'dependency_metadata', 'material', 'runtime', 'benchmark', 'fixture', 'security', 'assessment_selectable', 'resolution'])) return false;
  if (!isPin(value.publication_ref) || value.publication_ref.kind !== 'catalog-publication' || value.publication_ref.id !== id || value.publication_ref.digest !== sha || !key(value.profile_key) || !positive(value.generation) || typeof value.owner_id !== 'string' || !isUuid(value.owner_id)) return false;
  if (!pinFields.every(k => isPin(value[k])) || !collectionFields.every(k => isPins(value[k])) || !digestFields.every(k => digest(value[k]))) return false;
  const requested = value.requested;
  if (!isRecord(requested) || !exact(requested, ['model_key', 'effort', 'requirement', 'on_unavailable']) || (requested.model_key !== null && !key(requested.model_key)) || (requested.effort !== null && (typeof requested.effort !== 'string' || requested.effort.length > 4096)) || !['REQUIRED', 'PREFERRED'].includes(String(requested.requirement)) || !['BLOCK', 'USE_RUN_DEFAULT'].includes(String(requested.on_unavailable))) return false;
  return value.review === 'RECORDED_STATIC_PASS' && value.static === 'RECORDED_STATIC_PASS' && value.pure === 'RECORDED_PURE_PASS' && ['NO_EXTERNAL_DEPENDENCIES', 'NOT_VERIFIED'].includes(String(value.dependency_metadata)) && value.material === 'NOT_VERIFIED' && value.runtime === 'NOT_AVAILABLE' && value.benchmark === 'NOT_VERIFIED' && value.fixture === 'NOT_VERIFIED' && value.security === 'NOT_VERIFIED' && value.assessment_selectable === false && value.resolution === 'NO_MODEL';
}
export function decodeCatalogInspection(value: unknown, id: string, sha: string): CatalogInspection {
  if (!isInspection(value, id, sha)) throw new ApiError('INVALID_RESPONSE');
  return value;
}
export function catalogSelection(id: string | null, sha: string | null): boolean {
  return id !== null && isUuid(id) && digest(sha);
}
