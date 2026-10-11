"""Real existing owner/producer/reader SOURCE; native identities/storage are doubles.

No provider-config/turn/warm grants are seeded or inferred from this cold receipt.
"""

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.instance.schemas import NativeTaskCommand
from omnis.modules.tasks import managed_store
from omnis.modules.tasks.managed_contract import mapping, ref
from omnis.supervisor.native_tasks import NativeTaskOwner
from test_model_admission import (
    test_qualified_projection_reaches_cold_admission_without_model_reservation as journey,
)


@pytest.mark.asyncio
async def test_existing_owner_persists_then_reads_actual_configuration_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = NativeTaskOwner.handle
    seen = []

    async def capture(self: NativeTaskOwner, command: NativeTaskCommand) -> dict[str, object]:
        answer = await original(self, command)
        admission = mapping(answer["model_admission"])
        assert "configuration_receipt_ref" in admission, (
            "existing owner omits native configuration producer/reader"
        )
        context = mapping(admission["model_context"])
        pin = ref(admission["configuration_receipt_ref"], "model-configuration-receipt")
        # Read what production really persisted, not a test-created config/grant.
        from unittest.mock import Mock

        item = await managed_store.get(
            Mock(spec=AsyncConnection), command.owner_id, str(context["run_id"]), pin
        )
        body = mapping(item["payload"])
        source = mapping(body["source_configuration"])
        assert body["owner_id"] == command.owner_id and body["run_id"] == context["run_id"]
        assert body["binding_ref"] == admission["binding_ref"]
        assert (
            source["mode"] == "NO_MODEL"
            and source["provider"] is None
            and source["model_id"] is None
        )
        assert admission["native_turn"] is None and admission["model_calls"] == 0
        assert "provider_config_ref" not in admission  # cold observation never READY authority
        seen.append(pin)
        return answer

    monkeypatch.setattr(NativeTaskOwner, "handle", capture)
    await journey(tmp_path, monkeypatch)
    assert len(seen) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value",
    [
        ("provider", "UNTRUSTED"),
        ("mode", "READY"),
        ("version", True),
        ("native_child_id", "OTHER_CHILD"),
    ],
)
async def test_configuration_reply_forgery_refused_before_receipt_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    from omnis.modules.runs.model_dispatch import ModelDispatch
    from omnis.modules.settings.catalog_models import CatalogError
    from omnis.modules.settings.catalog_schema import canonical

    original = ModelDispatch.persist_configuration

    async def poisoned(
        self: ModelDispatch,
        conn: AsyncConnection,
        owner: str,
        prepared: dict[str, object],
        result: object,
    ) -> dict[str, object]:
        from copy import deepcopy

        changed = deepcopy(mapping(result))
        source = mapping(changed["source_configuration"])
        source[field] = value
        changed["source_configuration"] = source
        run = str(mapping(prepared["payload"])["run_id"])
        before = canonical(await managed_store.graph(conn, owner, run))
        with pytest.raises(CatalogError):
            await original(self, conn, owner, prepared, changed)
        assert canonical(await managed_store.graph(conn, owner, run)) == before
        raise CatalogError("MODEL_CONFIGURATION_REJECTED")

    monkeypatch.setattr(ModelDispatch, "persist_configuration", poisoned)
    with pytest.raises(CatalogError, match="MODEL_CONFIGURATION_REJECTED"):
        await journey(tmp_path, monkeypatch)


@pytest.mark.parametrize("inventory_field", ["tools", "enabled_toolsets"])
def test_native_configuration_producer_reads_and_rejects_state_mutation(
    inventory_field: str,
) -> None:
    """Pure actual producer with SOURCE state/actor doubles, not installed-native proof."""
    import sys
    from types import ModuleType, SimpleNamespace

    path = (
        Path(__file__).resolve().parents[2]
        / "integrations/hermes/upstream/managed-source/agent/cold_admission.py"
    )
    cold = ModuleType("source_configuration_probe")
    previous = sys.modules.get(cold.__name__)
    sys.modules[cold.__name__] = cold
    try:
        exec(path.read_text(), cold.__dict__)
        state = cold.ColdState("SOURCE_SESSION", "SOURCE_CHILD", "SOURCE_PARENT")
        actor = SimpleNamespace(
            _cold_state=state,
            session_id=state.session_id,
            _subagent_id=state.native_id,
            _parent_session_id=state.parent_session_id,
            provider=None,
            model=None,
            tools=(),
            enabled_toolsets=(),
        )
        result = cold.configuration_snapshot(actor)
        assert (
            result["provider"] is None
            and result["model_id"] is None
            and result["mode"] == "NO_MODEL"
        )

        class ForgedNonemptyInventory(tuple[str, ...]):
            def __eq__(self, other: object) -> bool:
                return other == ()

            def __ne__(self, other: object) -> bool:
                return not self.__eq__(other)

        forged = ForgedNonemptyInventory(("SOURCE_MUTATED_INVENTORY",))
        assert len(forged) == 1 and type(forged) is not tuple
        setattr(actor, inventory_field, forged)
        with pytest.raises(cold.ColdAdmissionDenied):
            cold.configuration_snapshot(actor)
        setattr(actor, inventory_field, ())
        actor.provider = "UNTRUSTED_CONFIGURATION_MUTATION"
        with pytest.raises(cold.ColdAdmissionDenied):
            cold.configuration_snapshot(actor)
        actor.provider = None
        state.closed = True
        with pytest.raises(cold.ColdAdmissionDenied):
            cold.configuration_snapshot(actor)
    finally:
        if previous is None:
            del sys.modules[cold.__name__]
        else:
            sys.modules[cold.__name__] = previous
