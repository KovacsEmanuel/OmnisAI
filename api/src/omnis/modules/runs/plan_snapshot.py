"""Backend-owned CONTRACT_PROBE snapshot of an exact checked publication."""

from copy import deepcopy

from omnis.modules.settings import candidate_store as store
from omnis.modules.settings.candidate_catalog import payload
from omnis.modules.settings.catalog_models import CatalogError


def snapshot_payload(publication: dict[str, object]) -> dict[str, object]:
    if publication.get("kind") != "catalog-publication":
        raise CatalogError("PUBLICATION_MISMATCH")
    body = payload(publication)
    refs = body.get("candidate_refs")
    if not isinstance(refs, list) or not all(isinstance(ref, dict) for ref in refs):
        raise CatalogError("PUBLICATION_MISMATCH")
    result: dict[str, object] = {
        "publication_ref": store.reference(publication),
        "execution_purpose": "CONTRACT_PROBE",
        "method_review_policy": "CHECK_ONLY",
        "resolution": "NO_MODEL",
        "effective": None,
        "assessment_selectable": False,
        "package_refs": [ref for ref in refs if ref.get("kind") == "package"],
    }
    for key in (
        "snapshot_ref",
        "profile_ref",
        "candidate_refs",
        "dependency_closure_refs",
        "dependency_artifact_refs",
        "material_digest",
        "resolved_index_digest",
        "dependency_closure_digest",
        "created_by",
    ):
        if key not in body:
            raise CatalogError("PUBLICATION_MISMATCH")
        result[key] = body[key]
    return deepcopy(result)
