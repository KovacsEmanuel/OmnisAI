"""Exact local Stop receipt schema; no DB grant issuance."""

import importlib.util
import unittest
from uuid import uuid4

from omnis_cli.lifecycle import StartError


class StopReceiptTests(unittest.TestCase):
    def test_grant_is_exact_discrete_and_command_bound(self) -> None:
        self.assertIsNotNone(
            importlib.util.find_spec("omnis_cli.stop_receipt"), "missing strict receipt"
        )
        from omnis_cli.stop_receipt import validate_grant

        record = {
            "instance_id": str(uuid4()),
            "stop_command": str(uuid4()),
            "finalize_command": str(uuid4()),
            "stop_generation": 2,
            "finalized_generation": 2,
            "stop_expected": 1,
            "supervisor_epoch": 1,
            "docker_id": "synthetic-daemon",
        }
        inventory = {"version": 1, "fingerprint": "a" * 64}
        grant = {
            "version": 1,
            "state": "STOP_PENDING",
            "instance_id": record["instance_id"],
            "command_id": record["stop_command"],
            "finalize_command_id": record["finalize_command"],
            "generation": 2,
            "owner_epoch": 1,
            "owner_uuid": str(uuid4()),
            "daemon_id": record["docker_id"],
            "inventory": inventory,
        }
        validate_grant(grant, record, inventory)
        with self.assertRaises(StartError):
            validate_grant(
                {key: value for key, value in grant.items() if key != "owner_uuid"},
                record,
                inventory,
            )
        for key, value in (
            ("version", True),
            ("generation", 2.0),
            ("state", "STOP_UNCERTAIN"),
            ("command_id", str(uuid4())),
            ("owner_uuid", None),
            ("owner_uuid", True),
            ("owner_uuid", "not-a-uuid"),
            ("owner_uuid", "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"),
            ("extra", 1),
        ):
            with self.subTest(key=key), self.assertRaises(StartError):
                validate_grant({**grant, key: value}, record, inventory)
        with self.assertRaises(StartError):
            validate_grant({**grant, "inventory": {"bad": 1.5}}, record, {"bad": 1.5})
