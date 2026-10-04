"""Docker Mounts is an unordered inventory; all mount metadata remains authority."""

import subprocess
import unittest
from copy import deepcopy
from unittest.mock import patch

from omnis_cli.lifecycle import read_record
from omnis_cli.stop_owner import (
    _container_fingerprint,
    prepare_stop_inventory,
    run_stop_owner,
    verify_stop_completion,
)
from omnis_cli.stop_receipt import receipt_path
from stop_owner_fixture import Fixture, owner_test_argv


class StopMountOrderTest(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)

    def test_fingerprint_ignores_only_mount_order_not_mount_contents(self):
        fixture = self.fixture
        item = deepcopy(fixture.items[fixture.ids["api"]])
        self.assertEqual(len(item["Mounts"]), 2)
        expected = _container_fingerprint(item)
        reordered = deepcopy(item)
        reordered["Mounts"].reverse()
        self.assertEqual(_container_fingerprint(reordered), expected)
        for field, value in (
            ("Source", "/foreign"),
            ("Destination", "/foreign"),
            ("RW", False),
            ("Propagation", "rshared"),
            ("extra", "not-discarded"),
        ):
            with self.subTest(field=field):
                changed = deepcopy(item)
                changed["Mounts"][-1][field] = value
                self.assertNotEqual(_container_fingerprint(changed), expected)
        changed = deepcopy(item)
        changed["Mounts"].append(deepcopy(changed["Mounts"][0]))
        self.assertNotEqual(_container_fingerprint(changed), expected)
        changed = deepcopy(item)
        changed["Config"]["Cmd"].reverse()
        self.assertNotEqual(_container_fingerprint(changed), expected)

    def test_mount_reordering_after_grant_keeps_real_owner_handoff_valid(self):
        fixture = self.fixture
        spawn = subprocess.Popen

        def launch(argv, **kwargs):
            return spawn(owner_test_argv(argv), **kwargs)

        with fixture.original_locks() as (locks, guards):
            inventory = prepare_stop_inventory(
                fixture.runtime, fixture.root, fixture.control, fixture.record
            )
            grant = fixture.grant(inventory)
            for role in ("api", "db"):
                fixture.items[fixture.ids[role]]["Mounts"].reverse()
            with patch("subprocess.Popen", side_effect=launch):
                run_stop_owner(
                    fixture.runtime,
                    fixture.root,
                    fixture.control,
                    fixture.record,
                    grant,
                    lock_fds=locks,
                    guard_fds=guards,
                )
            verify_stop_completion(
                fixture.runtime, fixture.root, fixture.control, fixture.record, grant
            )
            receipt = read_record(receipt_path(fixture.root, fixture.record))
            self.assertEqual(receipt["state"], "COMPLETED")
            self.assertEqual(fixture.items, {})
