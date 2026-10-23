"""SOURCE lifecycle/frames: real CLI owners, synthetic Engine and namespace family."""

import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from omnis_cli.lifecycle import StartError, mapping, read_record, write_record
from omnis_cli.start_runtime import private_identity
from omnis_cli.stop_owner import _view, prepare_stop_inventory
from omnis_cli.stop_receipt import receipt_path


class ModelTestCatalogLifecycleTest(unittest.TestCase):
    def test_catalog_uses_existing_stop_restart_and_frame_consumer(self) -> None:
        for method in (
            "test_four_role_start_receipt_and_stop_inventory",
            "test_native_inventory_and_control_exact_frame_budgets",
        ):
            with self.subTest(method=method), ExitStack() as patches:
                self.catalog_uses_existing_stop_restart_and_frame_consumer(patches, method)

    def test_catalog_refused_before_lifecycle_effects(self) -> None:
        for fault in ("wrong", "missing", "swapped", "boolean"):
            with self.subTest(fault=fault):
                self.catalog_refused_before_lifecycle_effects(fault)

    def test_catalog_authority_matches_sealed_topology(self) -> None:
        for consumer in ("shared", "normal", "emergency"):
            for case in (
                "catalog",
                "legacy",
                "omitted",
                "omitted-replaced",
                "legacy-inserted",
                "unknown-metadata",
                "boolean-metadata",
                "unknown-field",
            ):
                with self.subTest(consumer=consumer, case=case), ExitStack() as patches:
                    self.catalog_authority_matches_sealed_topology(patches, consumer, case)

    def catalog_uses_existing_stop_restart_and_frame_consumer(
        self, patches: ExitStack, method: str
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

            patches.enter_context(patch.object(fixture, "close", check_then_close))
            return fixture

        patches.enter_context(patch.object(stop_owner_fixture, "Fixture", catalog_fixture))
        case = test_settings_lifecycle.SettingsTopologyTest(method)
        case.setUp()
        try:
            getattr(case, method)()
        finally:
            case.doCleanups()
        assert len(retained) == 1

    def catalog_refused_before_lifecycle_effects(self, fault: str) -> None:
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
            with self.assertRaises((StartError, OSError, ValueError)):
                prepare_stop_inventory(
                    fixture.runtime, fixture.root, fixture.control, fixture.record
                )
            assert not any(request.startswith(("POST", "DELETE")) for request in fixture.requests)
            retained = (
                catalog if fault in {"wrong", "boolean"} else fixture.root / "retained-catalog"
            )
            assert (retained / "retained-publication").read_text() == "SOURCE retained bytes"
        finally:
            fixture.close()

    def catalog_authority_matches_sealed_topology(
        self, patches: ExitStack, consumer: str, case: str
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
            patches.enter_context(patch.object(stop, "_emergency_drain", drain))

            def invoke() -> None:
                if consumer == "shared":
                    start._bound_instance(runtime, fixture.root, fixture.control, record)
                elif consumer == "normal":
                    prepare_stop_inventory(runtime, fixture.root, fixture.control, record)
                else:
                    stop._emergency_stop(runtime, fixture.root, fixture.control, record)

            if case in {"catalog", "legacy"}:
                if consumer == "emergency":
                    with self.assertRaises(EffectFrontier):
                        invoke()
                    drain.assert_called_once()
                else:
                    invoke()
            else:
                with self.assertRaises(StartError):
                    invoke()
                drain.assert_not_called()
                assert (fixture.root / "startup.json").read_bytes() == before
                assert not (fixture.root / "unreconciled.json").exists()
            assert not any(request.startswith(("POST", "DELETE")) for request in fixture.requests)
        finally:
            fixture.close()
