"""One management-owned native Codex worker, fixed verified TLS over private UDS.

The relay fixes the TCP destination; this trusted client enforces encrypted L7.
Neither alone claims confinement against arbitrary code execution in the TCB.
"""

import contextlib
import fcntl
import importlib
import os
import re
import secrets
import select
import stat
import struct
import threading
import time
from collections.abc import Callable, Iterator
from types import ModuleType
from typing import Self
from uuid import UUID

import httpx

URLS = frozenset(
    "https://auth.openai.com" + path
    for path in (
        "/api/accounts/deviceauth/usercode",
        "/api/accounts/deviceauth/token",
        "/oauth/token",
    )
)
DEVICE_URL = "https://auth.openai.com/codex/device"
_context = threading.local()


class AuthAdmissionDenied(ValueError):
    """Trusted guard denial before this request could send; not transport loss."""


class FixedClient:
    def __init__(self, guard: Callable[[], None]):
        self.guard = guard
        self._trace = self.trace
        self._headers_started = False
        self.client = httpx.Client(
            transport=httpx.HTTPTransport(
                uds="/runtime/auth-egress.sock", retries=0, trust_env=False
            ),
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(15),
            event_hooks={"request": [self.before_send], "response": [self.body]},
        )

    def before_send(self, request: httpx.Request) -> None:
        if (
            request.method != "POST"
            or str(request.url) not in URLS
            or request.headers.get("host") != "auth.openai.com"
            or set(request.extensions) - {"timeout", "trace"}
            or request.extensions.get("trace") is not self._trace
        ):
            raise ValueError("Auth request denied")
        self.guard()

    def trace(self, event: str, info: dict[str, object]) -> None:
        # Synchronous httpcore hook also runs after connect/TLS, immediately
        # before header/body writes. HTTPX request hooks alone precede connect.
        if event.endswith(".started"):
            try:
                self.guard()
            except AuthAdmissionDenied:
                if self._headers_started:
                    raise ValueError("Auth in-flight outcome unknown") from None
                raise
            if event.endswith(".send_request_headers.started"):
                self._headers_started = True

    @staticmethod
    def body(response: httpx.Response) -> None:
        # Read decoded bytes incrementally before HTTPX materializes the body.
        if response.is_redirect:
            response.close()
            raise ValueError("Auth redirect denied")
        data = bytearray()
        for chunk in response.iter_bytes(65536):
            data.extend(chunk)
            if len(data) > 1024 * 1024:
                response.close()
                raise ValueError("Auth body limit")
        response._content = bytes(data)

    def post(self, url: str, **kwargs: object) -> httpx.Response:
        self._headers_started = False
        if url not in URLS or set(kwargs) - {"json", "data", "headers"}:
            raise ValueError("Auth request denied")
        headers = kwargs.get("headers", {})
        if (
            type(headers) is not dict
            or any(k != "Content-Type" for k in headers)
            or any(
                v not in {"application/json", "application/x-www-form-urlencoded"}
                for v in headers.values()
            )
        ):
            raise ValueError("Auth headers denied")
        self.guard()
        # No caller client/transport/proxy/redirect/extension/Host or SNI seam.
        data = kwargs.get("data")
        if data is not None and (
            type(data) is not dict
            or any(type(k) is not str or type(v) is not str for k, v in data.items())
        ):
            raise ValueError("Auth form denied")
        return self.client.post(
            url,
            json=kwargs.get("json"),
            data=data,
            headers=headers,
            extensions={"trace": self._trace},
        )

    def __enter__(self) -> Self:
        self.client.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        self.client.close()


def client_factory() -> FixedClient:
    owner = getattr(_context, "owner", None)
    if not isinstance(owner, NativeOAuth):
        raise ValueError("Native auth context missing")
    return FixedClient(owner.guard)


@contextlib.contextmanager
def profile_scope(profile: object) -> Iterator[None]:
    if profile is not None:
        raise ValueError("Caller profile denied")
    owner = getattr(_context, "owner", None)
    if not isinstance(owner, NativeOAuth):
        raise ValueError("Native auth context missing")
    owner.guard()
    yield


class NativeOAuth:
    """Retain handle before start; cancel and native save share the native lock."""

    def __init__(self) -> None:
        self.thread: threading.Thread | None = None
        self.native: ModuleType | None = None
        self.sid: str | None = None
        self.session: dict[str, object] | None = None
        self.binding: tuple[object, ...] | None = None
        self.deadline_ns = 0
        self.expires_ns = 0
        self.terminal: str | None = None
        self.owner_fd: int | None = None
        self.owner_identity: tuple[int, int] | None = None
        self.owner_deadline_ns = 0

    @classmethod
    def from_owner_fd(cls, fd: int) -> Self:
        """Direct-spawn stdin only; never an env/browser-supplied grant.

        The Host owns the sole writer. The child receives only the read end;
        bootstrap binds its kernel identity before any worker may be admitted.
        """
        info = os.fstat(fd)
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        if (
            not stat.S_ISFIFO(info.st_mode)
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_uid != os.getuid()
            or flags & os.O_ACCMODE != os.O_RDONLY
            or not flags & os.O_NONBLOCK
        ):
            raise ValueError("Invalid management lifeline")
        bootstrap = os.read(fd, 24)
        if len(bootstrap) != 24 or bootstrap[:16] != struct.pack("!QQ", info.st_dev, info.st_ino):
            raise ValueError("Invalid management bootstrap")
        os.set_inheritable(fd, False)
        owner = cls()
        owner.owner_fd = fd
        owner.owner_identity = (info.st_dev, info.st_ino)
        owner.owner_deadline_ns = struct.unpack("!Q", bootstrap[16:])[0]
        owner._owner_alive()
        return owner

    def _owner_alive(self) -> None:
        try:
            if self.owner_fd is None:
                raise ValueError("Auth owner missing")
            info = os.fstat(self.owner_fd)
            if (info.st_dev, info.st_ino) != self.owner_identity:
                raise ValueError("Auth owner changed")
            poll = select.poll()
            poll.register(self.owner_fd, select.POLLIN | select.POLLHUP | select.POLLERR)
            for _, events in poll.poll(0):
                if events & (select.POLLHUP | select.POLLERR | select.POLLNVAL):
                    raise ValueError("Auth owner revoked")
                try:
                    updates = os.read(self.owner_fd, 4096)
                except BlockingIOError:
                    updates = b""
                if not updates or len(updates) % 8:
                    raise ValueError("Invalid owner renewal")
                self.owner_deadline_ns = struct.unpack("!Q", updates[-8:])[0]
            now = time.monotonic_ns()
            if not now < self.owner_deadline_ns <= now + 5_000_000_000:
                raise ValueError("Auth owner expired")
        except OSError:
            raise ValueError("Auth owner unavailable") from None

    def guard(self) -> None:
        try:
            self._owner_alive()
        except ValueError:
            raise AuthAdmissionDenied("Auth owner revoked") from None
        if (
            self.session is None
            or self.session.get("cancelled")
            or time.monotonic_ns() >= min(self.deadline_ns, self.expires_ns)
        ):
            raise AuthAdmissionDenied("Auth authority expired")

    def revoke(self) -> None:
        if self.native is not None:
            with self.native._oauth_sessions_lock:
                if self.session is not None:
                    self.session["cancelled"] = True

    @property
    def active(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def operate(self, action: str, lease: object) -> dict[str, object]:
        if type(lease) is not dict or set(lease) != {
            "operation_id",
            "boot",
            "generation",
            "epoch",
            "deadline_ns",
        }:
            raise ValueError("Invalid auth lease")
        for key in ("operation_id", "boot"):
            if type(lease[key]) is not str or str(UUID(lease[key])) != lease[key]:
                raise ValueError("Invalid auth binding")
        if any(
            type(lease[k]) is not int or lease[k] <= 0
            for k in ("generation", "epoch", "deadline_ns")
        ):
            raise ValueError("Invalid auth authority")
        binding = tuple(lease[k] for k in ("operation_id", "boot", "generation", "epoch"))
        if lease["deadline_ns"] > time.monotonic_ns() + 5_000_000_000:
            raise ValueError("Auth lease exceeds native owner grant")
        if action not in {"connect", "status", "cancel"}:
            raise ValueError("Invalid auth action")
        if action == "connect" and self.binding != binding:
            self._owner_alive()
            if self.active or (self.session is not None and self.terminal is None):
                raise ValueError("Auth worker busy")
            if lease["deadline_ns"] <= time.monotonic_ns():
                raise ValueError("Auth authority expired")
            self.native = importlib.import_module("hermes_cli.web_routers.oauth")
            self.binding, self.deadline_ns = binding, lease["deadline_ns"]
            self.expires_ns = time.monotonic_ns() + 900_000_000_000
            self.sid = secrets.token_urlsafe(16)
            self.session = {"profile": None, "status": "pending", "cancelled": False}
            self.terminal = None
            with self.native._oauth_sessions_lock:
                self.native._oauth_sessions[self.sid] = self.session
            native, sid = self.native, self.sid

            def work() -> None:
                _context.owner = self
                try:
                    native._codex_full_login_worker(sid)
                finally:
                    del _context.owner

            self.thread = threading.Thread(target=work, daemon=True, name="omnis-codex-auth")
            self.thread.start()
        if self.binding != binding or self.native is None or self.session is None:
            raise ValueError("Auth binding mismatch")
        with self.native._oauth_sessions_lock:
            # Renewal is supplied by the same trusted Host, never the browser.
            self.deadline_ns = lease["deadline_ns"]
            if action == "cancel":
                self.session["cancelled"] = True
            expired = time.monotonic_ns() >= min(self.deadline_ns, self.expires_ns)
            if expired:
                self.session["cancelled"] = True
            if self.active:
                if self.session.get("cancelled"):
                    return {"oauth": "CANCELLING", "challenge": None}
                code = self.session.get("user_code")
                if code is not None:
                    if (
                        type(code) is not str
                        or re.fullmatch(r"[A-Z0-9-]{4,32}", code) is None
                        or self.session.get("verification_url") != DEVICE_URL
                    ):
                        self.session["cancelled"] = True
                        return {"oauth": "CANCELLING", "challenge": None}
                    return {"oauth": "CHALLENGE", "challenge": {"code": code, "url": DEVICE_URL}}
                return {"oauth": "STARTING", "challenge": None}
            if self.terminal is None:
                status = self.session.get("status")
                self.terminal = (
                    "SAVED"
                    if status == "approved"
                    else "INDETERMINATE"
                    if status == "error"
                    else "EXPIRED"
                    if expired or status == "expired"
                    else "CANCELLED"
                    if self.session.get("cancelled") or status == "cancelled"
                    else "INDETERMINATE"
                )
                self.native._oauth_sessions.pop(self.sid, None)
                self.session.clear()  # No challenge/identifiers in terminal projections.
            return {"oauth": self.terminal, "challenge": None}
