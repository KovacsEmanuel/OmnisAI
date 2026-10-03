"""Review regressions on real private files and a synthetic Engine, not Docker."""

import subprocess
import unittest
from copy import deepcopy
from unittest.mock import patch

from omnis_cli.lifecycle import StartError, lifecycle_lock, read_record, write_record
from omnis_cli.stop import STOP_STAGES
from omnis_cli.stop_owner import prepare_stop_inventory, run_stop_owner, verify_stop_completion
from omnis_cli.stop_receipt import receipt_path
from stop_owner_fixture import Fixture, owner_test_argv


class StopOwnerReviewTests(unittest.TestCase):
    def complete(self, fixture, data_fd, state_fd):
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
                lock_fds=(data_fd, state_fd),
            )
        self.assertEqual(
            read_record(receipt_path(fixture.root, fixture.record))["state"], "COMPLETED"
        )

    def test_offline_stop_journal_strict_before_engine(self):
        fixture = Fixture()
        try:
            with (
                lifecycle_lock(fixture.data / "omnis", fixture.runtime.deadline) as data_fd,
                lifecycle_lock(fixture.root, fixture.runtime.deadline) as state_fd,
            ):
                self.complete(fixture, data_fd, state_fd)
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
