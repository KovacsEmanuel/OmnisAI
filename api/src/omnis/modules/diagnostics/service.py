"""One atomic nonblocking stderr write, no worker, queue, IPC file or retry."""

import os
import stat
import threading
import time
from datetime import UTC, datetime
from uuid import uuid4

from omnis.modules.diagnostics.schemas import Delivery, UiEvent, UiRecord

ATTEMPTS = 256
BURST = 8
WINDOW_SECONDS = 60
RECORD_BYTES = 1024
TOTAL_BYTES = ATTEMPTS * RECORD_BYTES


def stderr_fd() -> int:
    # Reopen, not dup/set_blocking: do not change operational stderr's shared OFD flags.
    return os.open("/proc/self/fd/2", os.O_WRONLY | os.O_NONBLOCK | os.O_CLOEXEC)


def write_record(data: bytes) -> Delivery:
    fd = stderr_fd()
    try:
        if (
            not stat.S_ISFIFO(os.fstat(fd).st_mode)
            or os.get_blocking(fd)
            or len(data) > os.fpathconf(fd, "PC_PIPE_BUF")
        ):
            return "UNAVAILABLE"
        return "RECORDED" if os.write(fd, data) == len(data) else "UNAVAILABLE"
    finally:
        os.close(fd)


class DiagnosticSink:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.capture = str(uuid4())
        self.attempts = 0
        self.dropped = 0
        self.bytes = 0
        self.window = time.monotonic()
        self.burst = 0

    def emit(self, event: UiEvent, correlation: str) -> Delivery:
        if not self.lock.acquire(blocking=False):
            return "BUSY"
        try:
            if self.attempts >= ATTEMPTS:
                return "BUDGET_EXHAUSTED"
            self.attempts += 1
            now = time.monotonic()
            if now - self.window >= WINDOW_SECONDS:
                self.window, self.burst = now, 0
            if self.burst >= BURST:
                self.dropped += 1
                return "RATE_LIMITED"
            self.burst += 1
            record = UiRecord(
                marker="OMNIS_UI_DIAGNOSTIC_V1",
                source="browser_untrusted",
                capture_id=self.capture,
                received_at=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
                request_correlation_id=correlation,
                attempt=self.attempts,
                remaining=ATTEMPTS - self.attempts,
                dropped_before=self.dropped,
                event=event,
            )
            data = record.model_dump_json().encode("utf-8") + b"\n"
            if len(data) > RECORD_BYTES or self.bytes + len(data) > TOTAL_BYTES:
                self.dropped += 1
                return "BUDGET_EXHAUSTED"
            # Charge attempts even on failure: an outage cannot create endless write work.
            self.bytes += len(data)
            state = write_record(data)
            if state != "RECORDED":
                self.dropped += 1
            return state
        except BlockingIOError:
            self.dropped += 1
            return "BACKPRESSURED"
        except OSError:
            self.dropped += 1
            return "UNAVAILABLE"
        finally:
            self.lock.release()
