import secrets

import pytest

from e2e_secrets import assert_secret_free, decode_markers


def test_secret_channel_requires_ready_and_preserves_every_marker() -> None:
    marker = secrets.token_urlsafe(24)
    assert decode_markers(f"READY\nSECRET {marker}\n".encode()) == [marker]
    for payload in (
        b"",
        b"SECRET missing-ready\n",
        b"READY\nUNKNOWN event\n",
        b"READY\nSECRET short\n",
    ):
        with pytest.raises(ValueError):
            decode_markers(payload)


def test_unlabelled_secret_in_process_output_is_rejected_without_reflecting_it() -> None:
    marker = secrets.token_urlsafe(24)
    assert_secret_free([marker], ["sanitized output"])
    with pytest.raises(AssertionError, match="Synthetic secret leaked") as raised:
        assert_secret_free([marker], ["unlabelled output: " + marker])
    assert marker not in str(raised.value)
