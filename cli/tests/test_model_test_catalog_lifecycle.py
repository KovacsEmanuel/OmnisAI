"""SOURCE lifecycle/frames: real CLI owners, synthetic Engine and namespace family."""

from pathlib import Path

import pytest
from omnis_cli.lifecycle import StartError, mapping, read_record, write_record
from omnis_cli.start_runtime import private_identity
from omnis_cli.stop_owner import _view, prepare_stop_inventory
from omnis_cli.stop_receipt import receipt_path


@pytest.mark.parametrize(
    "method",
    [
        "test_four_role_start_receipt_and_stop_inventory",
        "test_native_inventory_and_control_exact_frame_budgets",
    ],
)
def test_catalog_uses_existing_stop_restart_and_frame_consumer(
    monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    import stop_owner_fixture
    import test_settings_lifecycle

    original = stop_owner_fixture.Fixture
    retained: list[Path] = []

    def catalog_fixture(**kwargs: bool) -> stop_owner_fixture.Fixture:
        fixture = original(**kwargs, model_test=True)
        inventory = prepare_stop_inventory(
            fixture.runtime, fixture.root, fixture.control, fixture.record
        )
        assert inventory["catalog"] == fixture.record["catalog_identity"]
        assert _view(fixture.runtime).model_test is True
        marker = fixture.root / "catalog" / "retained-publication"
        marker.write_text("SOURCE sentinel, not a publication receipt")
        close = fixture.close

        def check_then_close() -> None:
            try:
                assert marker.read_text() == "SOURCE sentinel, not a publication receipt"
                if method == "test_four_role_start_receipt_and_stop_inventory":
                    receipt = read_record(receipt_path(fixture.root, fixture.record))
                    assert (
                        mapping(mapping(receipt["grant"])["inventory"])["catalog"]
                        == (fixture.record["catalog_identity"])
                    )
                retained.append(marker)
            finally:
                close()

        monkeypatch.setattr(fixture, "close", check_then_close)
        return fixture

    monkeypatch.setattr(stop_owner_fixture, "Fixture", catalog_fixture)
    case = test_settings_lifecycle.SettingsTopologyTest(method)
    case.setUp()
    try:
        getattr(case, method)()
    finally:
        case.doCleanups()
    assert len(retained) == 1


@pytest.mark.parametrize("fault", ["wrong", "missing", "swapped", "boolean"])
def test_catalog_refused_before_lifecycle_effects(fault: str) -> None:
    from stop_owner_fixture import Fixture

    fixture = Fixture(native=True, auth=True, model_test=True)
    try:
        catalog = fixture.root / "catalog"
        marker = catalog / "retained-publication"
        marker.write_text("SOURCE retained bytes")
        expected = private_identity(catalog)
        if fault == "wrong":
            fixture.record["catalog_identity"] = [0, 1, 1000, 1000, 448]
            write_record(fixture.root / "startup.json", fixture.record, replace=True)
        elif fault == "boolean":
            fixture.record["catalog_identity"] = [True, *expected[1:]]
            write_record(fixture.root / "startup.json", fixture.record, replace=True)
        else:
            catalog.rename(fixture.root / "retained-catalog")
            if fault == "swapped":
                catalog.mkdir(mode=0o700)
        with pytest.raises((StartError, OSError, ValueError)):
            prepare_stop_inventory(fixture.runtime, fixture.root, fixture.control, fixture.record)
        assert not any(request.startswith(("POST", "DELETE")) for request in fixture.requests)
        retained = catalog if fault in {"wrong", "boolean"} else fixture.root / "retained-catalog"
        assert (retained / "retained-publication").read_text() == "SOURCE retained bytes"
    finally:
        fixture.close()


@pytest.mark.parametrize("consumer", ["shared", "normal", "emergency"])
@pytest.mark.parametrize(
    "case",
    [
        "catalog",
        "legacy",
        "omitted",
        "omitted-replaced",
        "legacy-inserted",
        "unknown-metadata",
        "boolean-metadata",
        "unknown-field",
    ],
)
def test_catalog_authority_matches_sealed_topology(
    monkeypatch: pytest.MonkeyPatch, consumer: str, case: str
) -> None:
    import importlib
    from unittest.mock import Mock

    from stop_owner_fixture import Fixture

    start = importlib.import_module("omnis_cli.start")
    stop = importlib.import_module("omnis_cli.stop")
    fixture = Fixture(native=True, auth=True, model_test=not case.startswith("legacy"))
    try:
        # Actual sealed-release constructor; read-only Engine uses the SOURCE fixture.
        runtime = _view(fixture.runtime)
        record = fixture.record
        if consumer == "emergency":
            record.update(stop_generation=None, finalized_generation=None)
        if case.startswith("omitted"):
            del record["catalog_identity"]
            if case == "omitted-replaced":
                (fixture.root / "catalog").rename(fixture.root / "retained-catalog")
                (fixture.root / "catalog").mkdir(mode=0o700)
        elif case == "legacy-inserted":
            (fixture.root / "catalog").mkdir(mode=0o700)
            record["catalog_identity"] = private_identity(fixture.root / "catalog")
        elif case == "unknown-metadata":
            del runtime.model_test
        elif case == "boolean-metadata":
            runtime.__dict__["model_test"] = 1
        elif case == "unknown-field":
            record["untrusted_catalog"] = True
        write_record(fixture.root / "startup.json", record, replace=True)
        before = (fixture.root / "startup.json").read_bytes()

        class EffectFrontier(Exception):
            pass

        drain = Mock(side_effect=EffectFrontier)
        monkeypatch.setattr(stop, "_emergency_drain", drain)

        def invoke() -> None:
            if consumer == "shared":
                start._bound_instance(runtime, fixture.root, fixture.control, record)
            elif consumer == "normal":
                prepare_stop_inventory(runtime, fixture.root, fixture.control, record)
            else:
                stop._emergency_stop(runtime, fixture.root, fixture.control, record)

        if case in {"catalog", "legacy"}:
            if consumer == "emergency":
                with pytest.raises(EffectFrontier):
                    invoke()
                drain.assert_called_once()
            else:
                invoke()
        else:
            with pytest.raises(StartError):
                invoke()
            drain.assert_not_called()
            assert (fixture.root / "startup.json").read_bytes() == before
            assert not (fixture.root / "unreconciled.json").exists()
        assert not any(request.startswith(("POST", "DELETE")) for request in fixture.requests)
    finally:
        fixture.close()
