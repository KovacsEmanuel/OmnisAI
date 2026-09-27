"""Parent-owned, non-log evidence channel for synthetic E2E secret markers."""

import re


def decode_markers(channel: bytes) -> list[str]:
    if len(channel) > 16384:
        raise ValueError("Oversized secret marker evidence")
    lines = channel.decode("ascii").splitlines()
    if not lines or lines[0] != "READY":
        raise ValueError("Missing secret observer readiness")
    markers = []
    for line in lines[1:]:
        if not line.startswith("SECRET ") or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", line[7:]):
            raise ValueError("Invalid secret marker evidence")
        markers.append(line[7:])
    return markers


def assert_secret_free(markers: list[str], observations: list[str]) -> None:
    if any(marker in observation for marker in markers for observation in observations):
        raise AssertionError("Synthetic secret leaked")
