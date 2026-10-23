"""Exact restore job attestation, reusing the existing inspect-channel fixture."""

import unittest
from unittest.mock import Mock

import test_start_attestation as fixture
from omnis_cli.lifecycle import StartError, write_record


class ColdRestoreModeTest(unittest.TestCase):
    def test_attestor_accepts_only_the_selected_fixed_argv(self):
        case = fixture.ProductAttestationTest()
        case.setUp()
        self.addCleanup(case.doCleanups)
        runtime = case.runtime
        write_record(case.root / "startup.json", {"system_id": "12345"})
        base_env = ["PATH=/usr/local/bin:/usr/bin:/bin", "OMNIS_WEB_ROOT=/opt/omnis/web"]
        item = case.item("reconcile")
        item["Mounts"] = []
        item["State"]["Running"] = False
        item["Config"].update(
            Entrypoint=None,
            OpenStdin=True,
            StdinOnce=True,
            Tty=False,
            AttachStdin=True,
            AttachStdout=True,
            AttachStderr=True,
            Env=[
                *base_env,
                "OMNIS_DATABASE_URL=" + case.env["OMNIS_DATABASE_URL"],
                "OMNIS_EXPECTED_SYSTEM_ID=12345",
            ],
        )
        item["Config"]["Labels"]["com.docker.compose.service"] = "reconcile"
        item["HostConfig"]["RestartPolicy"] = {"Name": "no", "MaximumRetryCount": 0}

        def inspect(kind, _ident):
            if kind == "network":
                return case.network
            if kind == "image":
                return {"Id": runtime.receipt.image_id, "Config": {"Env": base_env}}
            return item

        runtime.inspect = Mock(side_effect=inspect)
        for restoring in (False, True):
            for suffix in ([], ["--restore"], ["--restore", "--extra"]):
                with self.subTest(restoring=restoring, suffix=suffix):
                    item["Config"]["Cmd"] = ["python", "-I", "-m", "omnis.stop_reconcile", *suffix]
                    if suffix == (["--restore"] if restoring else []):
                        self.assertEqual(
                            runtime.attest(
                                case.cid,
                                "reconcile",
                                case.root,
                                case.control,
                                case.port,
                                restore=restoring,
                            ),
                            item,
                        )
                    else:
                        with self.assertRaises(StartError):
                            runtime.attest(
                                case.cid,
                                "reconcile",
                                case.root,
                                case.control,
                                case.port,
                                restore=restoring,
                            )
