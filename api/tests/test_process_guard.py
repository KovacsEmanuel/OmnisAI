"""The test observer must retain denials even when the child catches them."""

import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from process_probe import assert_clean_guard_report


@pytest.mark.parametrize(
    "mode, expected", [("negative", "EGRESS_DENIED"), ("positive", "CONNECT_ALLOWED")]
)
def test_guard_records_independent_events_when_application_catches(
    mode: str, expected: str
) -> None:
    guard = Path(__file__).with_name("process_guard.py")
    with (
        socket.socket() as owned_listener,
        tempfile.TemporaryFile(dir=os.environ["TMPDIR"]) as audit,
    ):
        owned_listener.bind(("127.0.0.1", 0))
        owned_listener.listen(1)
        port = owned_listener.getsockname()[1]
        result = subprocess.run(
            [sys.executable, "-I", str(guard), mode],
            env={
                "PATH": os.environ.get("PATH", ""),
                "OMNIS_TEST_AUDIT_FD": str(audit.fileno()),
                "OMNIS_DATABASE_URL": f"postgresql+psycopg://127.0.0.1:{port}/guard_fixture",
            },
            pass_fds=(audit.fileno(),),
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert result.returncode == 0
        audit.seek(0)
        events = audit.read().decode().splitlines()
    assert events == ["GUARD_READY", expected]
    if mode == "negative":
        with pytest.raises(AssertionError, match="forbidden"):
            assert_clean_guard_report(events)
    else:
        assert_clean_guard_report(events)


@pytest.mark.parametrize(
    "mode, expected",
    [
        ("positive", "CONNECT_ALLOWED"),
        ("negative", "EGRESS_DENIED"),
        ("negative-unix", "EGRESS_DENIED"),
        ("negative-loopback", "EGRESS_DENIED"),
    ],
)
def test_private_database_guard_allows_only_the_exact_unix_socket(mode: str, expected: str) -> None:
    from urllib.parse import quote

    guard = Path(__file__).with_name("process_guard.py")
    with tempfile.TemporaryDirectory(prefix="Omnis-UPPER-", dir=os.environ["TMPDIR"]) as name:
        address = str(Path(name) / ".s.PGSQL.5432")
        with socket.socket(socket.AF_UNIX) as listener, tempfile.TemporaryFile(dir=name) as audit:
            listener.bind(address)
            listener.listen(1)
            result = subprocess.run(
                [sys.executable, "-I", str(guard), mode],
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "OMNIS_TEST_AUDIT_FD": str(audit.fileno()),
                    "OMNIS_DATABASE_URL": f"postgresql+psycopg://omnis_test@{quote(name, safe='')}/guard_fixture",
                },
                pass_fds=(audit.fileno(),),
                capture_output=True,
                text=True,
                timeout=5,
            )
            assert result.returncode == 0
            audit.seek(0)
            events = audit.read().decode().splitlines()
            assert events == ["GUARD_READY", expected]
            if expected == "EGRESS_DENIED":
                with pytest.raises(AssertionError, match="forbidden"):
                    assert_clean_guard_report(events)
            else:
                assert_clean_guard_report(events)


@pytest.mark.parametrize(
    "events",
    [
        [],
        ["OTHER"],
        ["GUARD_READY", "PROCESS_DENIED"],
        ["GUARD_READY", "UNKNOWN"],
        ["GUARD_READY", "GUARD_READY"],
    ],
)
def test_missing_or_invalid_observer_evidence_is_not_clean(events: list[str]) -> None:
    with pytest.raises(AssertionError):
        assert_clean_guard_report(events)
