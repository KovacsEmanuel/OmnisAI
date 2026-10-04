"""Review regressions on real private files and a synthetic Engine, not Docker."""

import subprocess
import time
import unittest
from copy import deepcopy
from unittest.mock import patch

from omnis_cli.lifecycle import StartError, read_record, write_record
from omnis_cli.stop import STOP_STAGES
from omnis_cli.stop_engine import StopEngine
from omnis_cli.stop_owner import prepare_stop_inventory, run_stop_owner, verify_stop_completion
from omnis_cli.stop_receipt import receipt_path
from stop_owner_fixture import Fixture, owner_test_argv


class StopOwnerReviewTests(unittest.TestCase):
    def test_inspect_null_is_not_absence_in_decoder_or_offline_consumer(self):
        fixture = Fixture()
        try:
            with fixture.original_locks() as (locks, guards):
                self.complete(fixture, locks, guards)
                original = fixture.response
                effects = [x for x in fixture.requests if x.startswith(("POST", "DELETE"))]
                for method, ident, target in (
                    ("container", fixture.ids["api"], f"/containers/{fixture.ids['api']}/json"),
                    ("network", fixture.network_id, f"/networks/{fixture.network_id}"),
                ):
                    for status, value in (
                        (404, {}),
                        (200, {}),
                        (200, None),
                        (200, []),
                        (200, False),
                    ):

                        def response(verb, path, *, wanted=target, status=status, value=value):
                            if verb == "GET" and path == wanted:
                                return status, value
                            return original(verb, path)

                        with patch.object(fixture, "response", side_effect=response):
                            engine = StopEngine(
                                fixture.runtime.host,
                                fixture.runtime.receipt.docker_id,
                                time.monotonic() + 2,
                            )
                            with self.subTest(
                                method=method, status=status, value=value, consumer="decoder"
                            ):
                                if status == 404:
                                    self.assertIsNone(getattr(engine, method)(ident))
                                elif isinstance(value, dict):
                                    self.assertEqual(getattr(engine, method)(ident), value)
                                else:
                                    with self.assertRaisesRegex(
                                        StartError, "STOP_ENGINE_RESPONSE_INVALID"
                                    ):
                                        getattr(engine, method)(ident)
                            with self.subTest(
                                method=method, status=status, value=value, consumer="offline"
                            ):
                                before = len(fixture.requests)
                                if status == 404:
                                    verify_stop_completion(
                                        fixture.runtime,
                                        fixture.root,
                                        fixture.control,
                                        fixture.record,
                                    )
                                else:
                                    reason = (
                                        "STOP_RESOURCES_REMAIN"
                                        if isinstance(value, dict)
                                        else "STOP_ENGINE_RESPONSE_INVALID"
                                    )
                                    with self.assertRaisesRegex(StartError, reason):
                                        verify_stop_completion(
                                            fixture.runtime,
                                            fixture.root,
                                            fixture.control,
                                            fixture.record,
                                        )
                                self.assertIn(f"GET {target} HTTP/1.1", fixture.requests[before:])
                self.assertEqual(
                    effects, [x for x in fixture.requests if x.startswith(("POST", "DELETE"))]
                )
                self.assertEqual(
                    read_record(receipt_path(fixture.root, fixture.record))["state"], "COMPLETED"
                )
        finally:
            fixture.close()

    def complete(self, fixture, locks, guards):
        inventory = prepare_stop_inventory(
            fixture.runtime, fixture.root, fixture.control, fixture.record
        )
        real_popen = subprocess.Popen
        with patch(
            "omnis_cli.stop_owner.subprocess.Popen",
            side_effect=lambda argv, **kwargs: real_popen(owner_test_argv(argv), **kwargs),
        ):
            run_stop_owner(
                fixture.runtime,
                fixture.root,
                fixture.control,
                fixture.record,
                fixture.grant(inventory),
                lock_fds=locks,
                guard_fds=guards,
            )
        self.assertEqual(
            read_record(receipt_path(fixture.root, fixture.record))["state"], "COMPLETED"
        )

    def test_offline_stop_journal_strict_before_engine(self):
        fixture = Fixture()
        try:
            with fixture.original_locks() as (locks, guards):
                self.complete(fixture, locks, guards)
                clean = deepcopy(fixture.record)
                effects = [x for x in fixture.requests if x.startswith(("POST", "DELETE"))]
                self.assertEqual(len(effects), 7)
                for phase, stages in (("STOPPING", []), ("STOPPED", list(STOP_STAGES))):
                    with self.subTest(positive=phase):
                        valid = {**clean, "phase": phase, "teardown_completed": stages}
                        write_record(fixture.root / "startup.json", valid, replace=True)
                        verify_stop_completion(
                            fixture.runtime, fixture.root, fixture.control, valid
                        )
                for changes in (
                    {"phase": "STOPPED", "teardown_completed": {"not": "a stage list"}},
                    {"phase": "STOPPED", "teardown_completed": []},
                    {"phase": "STOPPED", "teardown_completed": list(STOP_STAGES[:-1])},
                    {"teardown_completed": False},
                    {"teardown_completed": ["api", "forwarder"]},
                    {"teardown_completed": ["unknown"]},
                    {"teardown_completed": list(STOP_STAGES) + ["ipc"]},
                    {"generation": 77},
                    {"generation": True},
                    {"phase": []},
                    {"unexpected": 1},
                ):
                    for consumer in (verify_stop_completion, prepare_stop_inventory):
                        with self.subTest(changes=changes, consumer=consumer.__name__):
                            invalid = {**clean, **changes}
                            write_record(fixture.root / "startup.json", invalid, replace=True)
                            before = len(fixture.requests)
                            with self.assertRaises(StartError) as caught:
                                consumer(fixture.runtime, fixture.root, fixture.control, invalid)
                            self.assertEqual(caught.exception.reason, "RECOVERY_REQUIRED")
                            self.assertEqual(caught.exception.code, 4)
                            self.assertEqual(len(fixture.requests), before)
                            self.assertEqual(read_record(fixture.root / "startup.json"), invalid)
                self.assertEqual(
                    effects, [x for x in fixture.requests if x.startswith(("POST", "DELETE"))]
                )
        finally:
            fixture.close()
