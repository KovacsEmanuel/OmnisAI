"""Installed checker/registry/validation closure, not prompt or native authority."""

import re
from hashlib import sha256
from pathlib import Path

from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical

KEY = "managed.contract-pure.v2"
SEMANTICS = (
    "Verify bound native read/action receipts and artifact schemas; no method recomputation."
)
SOURCES = (
    "tasks/method_checker_identity.py",
    "tasks/method_checks.py",
    "tasks/managed_contract.py",
    "tasks/managed_composition.py",
    "tasks/criterion_checks.py",
    "tasks/contract_case_input.py",
    "settings/candidate_catalog.py",
    "settings/candidate_store.py",
    "settings/candidate_material.py",
    "settings/catalog_models.py",
    "settings/catalog_schema.py",
    "settings/publication_models.py",
    "settings/skill_catalog.py",
)
# Exact producer source identities from integrated pre-C10 revisions, paired
# with their immutable composer scope. These are NOT new-admission identities.
HISTORICAL = {
    "9b87dc17293895299fa5088991afa16a0d73639e4bd400c28e4a80544dfe80e3": {
        "717549a613365ec95c40276903a92bf9b603092232947e0ee79bf5e1745854ed",
    },
    "125c9f79457f2e1437d7de7b31a81eb659062ee4a8e398a25ec670fb503aa611": {
        "1d32db3dcd15ee65d9d479d0401675d255a856b36beaca1bde1093ed0fb0b00a",
        "2cec176a5e622df2751e069b2a676c7e64578bea33b768aab63b09c78698f473",
    },
}
FULL_PREDICATE_HISTORICAL = {
    "388fe9da680951249202045b10e10245d42352a0c194413d221d647b54a085db": "4a3606b8e0354bceb8066f6de536932ee420d1147aa9311084ceafb4afbea850",
}


PARTIAL_PREDICATE_HISTORICAL = {
    "36738cfb398f63d969160c08b7b6b54e91f0ab35818d62fe03ee5528b1d83227": "4a3606b8e0354bceb8066f6de536932ee420d1147aa9311084ceafb4afbea850",
}


# Exact applicability/UNKNOWN producer at 0aeb328: receive-only.
APPLICABILITY_HISTORICAL = {
    "32b3621379b10d20415a09ebb3e7cdda4c6754f5135ff943e639711a44de9036": "bcc1cdbf7b3546e1269e22875bbec2670504e73f25a3e198f65990fb56f31d99",
}


def descriptor() -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    closure = [{"path": p, "sha256": sha256((root / p).read_bytes()).hexdigest()} for p in SOURCES]
    return {
        "key": KEY,
        "code_digest": sha256(canonical(closure)).hexdigest(),
        "semantics": SEMANTICS,
    }


def verify(
    checker: object, *, pin: str, receive_only: bool, zero_predicates: bool
) -> dict[str, object]:
    from omnis.modules.tasks import managed_contract as contract

    record = contract.record(checker, "method-checker")
    try:
        body = contract.exact(record["payload"], {"key", "code_digest", "semantics"})
        key = contract.text(body["key"], 128)
        digest = contract.text(body["code_digest"], 64)
        contract.text(body["semantics"])
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise CatalogError("METHOD_CHECKER_INVALID")
    except (CatalogError, TypeError, ValueError, RecursionError):
        raise CatalogError("METHOD_CHECKER_INVALID") from None
    if canonical(body) == canonical(descriptor()):
        return record
    if (
        receive_only is True
        and zero_predicates is False
        and key == KEY
        and (
            FULL_PREDICATE_HISTORICAL.get(digest) == pin
            or PARTIAL_PREDICATE_HISTORICAL.get(digest) == pin
            or APPLICABILITY_HISTORICAL.get(digest) == pin
        )
        and body["semantics"] == SEMANTICS
    ):
        return record  # Retained current-C10 COMPLETE is regenerated/equal by its caller.
    if (
        receive_only is True
        and zero_predicates is True
        and key == "managed.contract-pure"
        and digest in HISTORICAL
        and pin in HISTORICAL[digest]
        and body["semantics"] == SEMANTICS
    ):
        return record  # Existing check payload must still be independently regenerated/equal.
    raise CatalogError("METHOD_CHECKER_UNAVAILABLE")
