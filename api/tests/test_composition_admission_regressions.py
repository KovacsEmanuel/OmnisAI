"""Source-authored composition refusals before durable reservation (C05-R1-F1)."""

from datetime import UTC, datetime

import pytest

from omnis.modules.settings.catalog_models import CatalogError, Procedure
from omnis.modules.settings.catalog_schema import canonical, dto
from omnis.modules.tasks import managed_contract as contract
from test_managed_composition import inputs
from test_managed_contract import ref

CASES = (
    "empty_signal",
    "empty_requirement",
    "bom_requirement",
    "bom_objective",
    "empty_cleanup_reason",
    "empty_false_positive",
    "empty_nonapplicable_reason",
)


def authored_case(value: dict[str, object], case: str) -> dict[str, object]:
    result = dict(value)
    if case == "empty_signal":
        result["predicted_signal"] = ""
    elif case in {"empty_requirement", "bom_requirement"}:
        requirements = [
            contract.mapping(r) for r in contract.sequence(result["method_requirements"])
        ]
        requirements[0]["description"] = (
            "" if case == "empty_requirement" else "\ufeffAuthored text"
        )
        result["method_requirements"] = requirements
    elif case == "bom_objective":
        result["objective"] = "\ufeffAuthored objective"
    elif case == "empty_cleanup_reason":
        result["cleanup_not_needed_reason"] = ""
    elif case == "empty_false_positive":
        result["false_positives"] = [""]
    elif case == "empty_nonapplicable_reason":
        groups = [contract.mapping(g) for g in contract.sequence(result["non_applicable_groups"])]
        assert groups
        groups[0]["reason"] = ""
        result["non_applicable_groups"] = groups
    else:
        raise AssertionError("Unknown regression case")
    return result


@pytest.mark.parametrize("case", CASES)
def test_native_incompatible_authored_text_refuses_at_producer(case: str) -> None:
    selection, bindings, packages, original = inputs(two=True)
    with pytest.raises(CatalogError):
        procedure = dto(canonical(authored_case(original.model_dump(mode="json"), case)), Procedure)
        contract.build_records(
            selection,
            ref("native-preparation-receipt"),
            contract.mapping(next(b["ref"] for b in bindings if b["entity_kind"] == "procedure")),
            procedure,
            bindings,
            "b06b-publish-contract",
            "RECON",
            1,
            datetime.now(UTC),
            composition_packages=packages,
        )
