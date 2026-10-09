"""NO_MODEL selection from an already pinned, revalidated CONTRACT_PROBE."""

from copy import deepcopy

from omnis.modules.settings.candidate_catalog import valid_ref
from omnis.modules.settings.catalog_models import CatalogError, CompiledCatalog, Profile, ReleaseRef
from omnis.modules.settings.catalog_schema import canonical


def selection_payload(
    snapshot_ref: dict[str, object],
    recipe_key: str,
    profile: Profile,
    compiled: CompiledCatalog,
) -> dict[str, object]:
    if valid_ref(snapshot_ref)["kind"] != "run-snapshot":
        raise CatalogError("SNAPSHOT_MISMATCH")
    if len(profile.agent_recipes) != 1:
        raise CatalogError("UNSUPPORTED_RECIPE_COUNT")
    recipe = profile.agent_recipes[0]
    if recipe.key != recipe_key:
        raise CatalogError("RECIPE_UNAVAILABLE")
    if (
        recipe.role == "REVIEWER"
        or len(recipe.procedure_refs) != 1
        or not recipe.package_refs
        or recipe.requested_capabilities
        or compiled.verification_kind != "CONTRACT"
        or compiled.slots
        or compiled.resolution != "NO_MODEL"
        or compiled.requested.model_key is not None
        or compiled.requested.effort is not None
    ):
        raise CatalogError("UNSUPPORTED_RECIPE")
    selected: list[dict[str, object]] = []
    for source in recipe.package_refs:
        if isinstance(source, ReleaseRef):
            exact = valid_ref(source.ref.model_dump(mode="json"))
            matches = [b for b in compiled.catalog_bindings if b.get("ref") == exact]
        else:
            matches = [
                b
                for b in compiled.catalog_bindings
                if b.get("package_key") == source.package_key
                and b.get("entity_kind") == source.entity_kind == "package"
                and b.get("key") == source.key == source.package_key
            ]
        if len(matches) != 1:
            raise CatalogError("REF_MISMATCH")
        ref = valid_ref(matches[0].get("ref"))
        if ref["kind"] != "package" or any(canonical(ref) == canonical(r) for r in selected):
            raise CatalogError("REF_MISMATCH")
        selected.append(ref)
    return deepcopy(
        {
            "snapshot_ref": snapshot_ref,
            "recipe_key": recipe_key,
            "selected_package_refs": selected,
            "requested": compiled.requested.model_dump(mode="json"),
            "effective": None,
            "resolution": "NO_MODEL",
            "reason": "CONTRACT_PROBE_PURE",
            "compatibility_receipt_refs": [],
        }
    )
