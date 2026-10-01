"""Pair/open command boundaries; live installed evidence is a separate gate."""

import contextlib
import hashlib
import io
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from omnis_cli.main import main


class TtyOutput(io.StringIO):
    def isatty(self) -> bool:
        return True


class PairTest(unittest.TestCase):
    def test_redirected_output_refuses_before_issuer_or_state_lookup(self):
        output = io.StringIO()
        with (
            patch("omnis_cli.pairing.verified_instance") as verify,
            patch("omnis_cli.pairing.request") as issuer,
            patch("sys.stdin", TtyOutput()),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(io.StringIO()) as error,
        ):
            self.assertEqual(main(["pair"]), 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("PAIRING_TTY_REQUIRED", error.getvalue())
        verify.assert_not_called()
        issuer.assert_not_called()

    def test_machine_readable_format_refuses_before_issuer_even_with_tty(self):
        with (
            patch("omnis_cli.pairing.verified_instance") as verify,
            patch("omnis_cli.pairing.request") as issuer,
            patch("sys.stdin", TtyOutput()),
            contextlib.redirect_stdout(TtyOutput()),
            contextlib.redirect_stderr(io.StringIO()) as error,
        ):
            self.assertEqual(main(["pair", "--json"]), 2)
        self.assertIn("PAIRING_FORMAT_REFUSED", error.getvalue())
        verify.assert_not_called()
        issuer.assert_not_called()

    def test_piped_stdin_refuses_even_when_output_is_tty(self):
        output = TtyOutput()
        with (
            patch("omnis_cli.pairing.verified_instance") as verify,
            patch("omnis_cli.pairing.request") as issuer,
            patch("sys.stdin", io.StringIO()),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(io.StringIO()) as error,
        ):
            self.assertEqual(main(["pair"]), 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("PAIRING_TTY_REQUIRED", error.getvalue())
        verify.assert_not_called()
        issuer.assert_not_called()

    def test_unreadable_tty_probe_refuses_before_issuer(self):
        class BrokenTty(TtyOutput):
            def isatty(self) -> bool:
                raise OSError("synthetic TTY error")

        for input_stream, output_stream in (
            (BrokenTty(), TtyOutput()),
            (TtyOutput(), BrokenTty()),
        ):
            with (
                self.subTest(stream="stdin" if isinstance(input_stream, BrokenTty) else "stdout"),
                patch("omnis_cli.pairing.verified_instance") as verify,
                patch("omnis_cli.pairing.request") as issuer,
                patch("sys.stdin", input_stream),
                contextlib.redirect_stdout(output_stream),
                contextlib.redirect_stderr(io.StringIO()) as error,
            ):
                self.assertEqual(main(["pair"]), 2)
                self.assertIn("PAIRING_TTY_REQUIRED", error.getvalue())
                verify.assert_not_called()
                issuer.assert_not_called()

    def test_interactive_pair_sends_digest_only_after_verification(self):
        from omnis_cli import pairing

        output = TtyOutput()
        events = []

        @contextlib.contextmanager
        def verified():
            events.append("verified")
            yield (
                {
                    "instance_id": "00000000-0000-0000-0000-000000000001",
                    "generation": 1,
                    "supervisor_epoch": 1,
                },
                Path("/private"),
            )

        def issue(_directory, command):
            events.append("issued")
            self.assertEqual(command["op"], "pairing")
            UUID(command["issuance_id"])
            self.assertNotIn("code", command)
            return {
                "instance_id": command["instance_id"],
                "generation": 1,
                "supervisor_epoch": 1,
                "admission_open": True,
                "shutdown_command_id": None,
            }

        with (
            patch.object(pairing, "verified_instance", side_effect=verified),
            patch.object(pairing, "request", side_effect=issue) as request,
            patch("sys.stdin", TtyOutput()),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(io.StringIO()) as error,
        ):
            self.assertEqual(main(["pair"]), 0)
        code = output.getvalue().strip().rsplit(" ", 1)[-1]
        self.assertTrue(16 <= len(code) <= 128)
        self.assertTrue(code.isascii() and all(c.isalnum() or c in "_-" for c in code))
        self.assertTrue(
            hashlib.sha256(code.encode()).hexdigest() == request.call_args.args[1]["digest"]
        )
        self.assertEqual(events, ["verified", "issued"])
        self.assertEqual(error.getvalue(), "")

    def test_failed_private_issuance_never_prints_code(self):
        from omnis_cli import pairing
        from omnis_cli.control import ControlUnavailable

        @contextlib.contextmanager
        def verified():
            yield ({"instance_id": "00000000-0000-0000-0000-000000000001"}, Path("/private"))

        output = TtyOutput()
        with (
            patch.object(pairing, "verified_instance", side_effect=verified),
            patch.object(pairing, "request", side_effect=ControlUnavailable),
            patch("sys.stdin", TtyOutput()),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(io.StringIO()) as error,
        ):
            self.assertEqual(main(["pair"]), 3)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("PAIRING_UNAVAILABLE", error.getvalue())

    def test_changed_control_generation_never_discloses_issued_code(self):
        from omnis_cli import pairing

        @contextlib.contextmanager
        def verified():
            yield (
                {
                    "instance_id": "00000000-0000-0000-0000-000000000001",
                    "generation": 1,
                    "supervisor_epoch": 1,
                },
                Path("/private"),
            )

        output = TtyOutput()
        with (
            patch.object(pairing, "verified_instance", side_effect=verified),
            patch.object(
                pairing,
                "request",
                return_value={
                    "instance_id": "00000000-0000-0000-0000-000000000001",
                    "generation": 2,
                    "supervisor_epoch": 1,
                    "admission_open": False,
                    "shutdown_command_id": None,
                },
            ),
            patch("sys.stdin", TtyOutput()),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(io.StringIO()) as error,
        ):
            self.assertEqual(main(["pair"]), 4)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("PAIRING_STATE_CHANGED", error.getvalue())

    def test_tty_write_after_code_before_newline_reports_uncertain_disclosure(self):
        from omnis_cli import pairing

        class InterruptedTty(TtyOutput):
            def write(self, value):
                if value.startswith("Cod pairing Omnis") and value.endswith("\n"):
                    super().write(value[:-1])
                    raise OSError("synthetic TTY disconnect")
                if value == "\n":
                    raise OSError("synthetic TTY disconnect")
                return super().write(value)

        @contextlib.contextmanager
        def verified():
            yield (
                {
                    "instance_id": "00000000-0000-0000-0000-000000000001",
                    "generation": 1,
                    "supervisor_epoch": 1,
                },
                Path("/private"),
            )

        reply = {
            "instance_id": "00000000-0000-0000-0000-000000000001",
            "generation": 1,
            "supervisor_epoch": 1,
            "admission_open": True,
            "shutdown_command_id": None,
        }
        output = InterruptedTty()
        with (
            patch.object(pairing, "verified_instance", side_effect=verified),
            patch.object(pairing, "request", return_value=reply),
            patch("sys.stdin", TtyOutput()),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(io.StringIO()) as error,
        ):
            self.assertEqual(main(["pair"]), 4)
        self.assertIn("Cod pairing Omnis", output.getvalue())
        self.assertIn("PAIRING_DISPLAY_UNCERTAIN", error.getvalue())
        self.assertNotIn("codul nu a fost afișat", error.getvalue())
