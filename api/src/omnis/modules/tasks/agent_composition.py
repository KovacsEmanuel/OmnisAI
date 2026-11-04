"""S1 immutable instructions from an exact reviewed/evaluated/published core.

Ordered dedupe adapted from usestrix/strix prompt.py:69–75 at
6b7ae2ebe4d47037a927aade23265ff4e4f27e84 (Apache-2.0).
Modifications: exact owner-bound refs, no implicit skills, missing refs deny.
Full-file/excerpt hashes and license: skills/omnis-agent-core/NOTICE.md and LICENSE.
No model, runtime, target, filesystem discovery or tool authority is granted.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.settings.candidate_material import digest
from omnis.modules.settings.catalog_models import CatalogError, ExactRef, ExcerptProvenance
from omnis.modules.settings.catalog_publication import PublicationCatalog
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.settings.skill_catalog import CORE_ROLES, read_file

CoreRole = Literal["BRAIN", "RECON", "INVESTIGATOR", "VALIDATOR"]
COMPOSER_REVISION = "sha256:" + digest(read_file(Path(__file__)))
MAX_CONTEXT_BYTES = 8192  # Conservative UTF-8 byte/token upper bound, not SDK wire allowance.


@dataclass(frozen=True, slots=True)
class AgentComposition:
    text: str
    text_digest: str
    publication_ref: ExactRef
    material_digest: str
    resolved_index_digest: str
    base_ref: ExactRef
    role_ref: ExactRef
    skill_refs: tuple[ExactRef, ...]
    provenance: tuple[ExcerptProvenance, ...]
    composer_revision: str


async def compose_publication(
    catalog: PublicationCatalog,
    connection: AsyncConnection,
    owner_id: str,
    publication_ref: ExactRef,
    *,
    role: CoreRole,
    brief: str,
    selected_skill_refs: tuple[ExactRef, ...] | None = None,
) -> AgentComposition:
    """Owner supplies projected brief, role and publication; no parent-history input.

    None selects the exact package pinned by that role's published recipe.
    An explicit empty selection is denied, not an inheritance/default request.
    """
    if role not in CORE_ROLES or not isinstance(brief, str) or not brief.strip() or "\x00" in brief:
        raise CatalogError("COMPOSITION_REJECTED")
    profile, compiled = await catalog.load_core(
        connection, owner_id, publication_ref.model_dump(mode="json")
    )
    recipes = [recipe for recipe in profile.agent_recipes if recipe.role == role]
    if len(recipes) != 1:
        raise CatalogError("COMPOSITION_REJECTED")

    def bound(kind: str, key: str) -> ExactRef:
        matches = [
            b
            for b in compiled.catalog_bindings
            if b["package_key"] == "omnis-agent-core"
            and b["entity_kind"] == kind
            and b["key"] == key
        ]
        if len(matches) != 1:
            raise CatalogError("COMPOSITION_REF_MISMATCH")
        return ExactRef.model_validate(matches[0]["ref"], strict=True)

    package_ref = bound("package", "omnis-agent-core")
    base_ref, role_ref = bound("prompt", "base"), bound("prompt", role.lower())
    requested = (package_ref,) if selected_skill_refs is None else selected_skill_refs
    if not requested or len(requested) > 128:
        raise CatalogError("COMPOSITION_REF_MISMATCH")
    deduped: list[ExactRef] = []
    seen: set[bytes] = set()
    for skill in requested:
        if skill != package_ref:
            raise CatalogError("COMPOSITION_REF_MISMATCH")
        token = canonical(skill.model_dump(mode="json"))
        if token not in seen:
            deduped.append(skill)
            seen.add(token)
    texts = dict(compiled.core_text)
    if len(texts) != len(compiled.core_text):
        raise CatalogError("COMPOSITION_REF_MISMATCH")
    sections = [
        {"section": "base", "ref": base_ref.model_dump(mode="json"), "text": texts["base"]},
        {"section": "role", "ref": role_ref.model_dump(mode="json"), "text": texts[role.lower()]},
        {"section": "brief", "text": brief},
        *[
            {"section": "skill", "ref": ref.model_dump(mode="json"), "text": texts["skill"]}
            for ref in deduped
        ],
    ]
    raw = canonical(sections)
    if len(raw) > MAX_CONTEXT_BYTES:
        raise CatalogError("COMPOSITION_LIMIT")
    return AgentComposition(
        raw.decode("utf-8"),
        digest(raw),
        publication_ref,
        compiled.material_digest,
        compiled.resolved_index_digest,
        base_ref,
        role_ref,
        tuple(deduped),
        compiled.core_provenance,
        COMPOSER_REVISION,
    )
