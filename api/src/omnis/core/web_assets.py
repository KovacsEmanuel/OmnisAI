"""Trusted release assets only, bound to a small hashed manifest, not a file server."""

import asyncio
import hashlib
import os
import stat
import threading
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

AssetName = Annotated[
    str, Field(pattern=r"^(index\.html|assets/[A-Za-z0-9_-]+\.(js|css|woff2|txt))$")
]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class BuildManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: Literal[1]
    files: dict[AssetName, Digest] = Field(min_length=2, max_length=128)


class WebAssets:
    def __init__(self, root: str | None) -> None:
        self.root = Path(root) if root else None
        self._pending: asyncio.Future[dict[str, bytes] | None] | None = None

    async def read(self) -> dict[str, bytes] | None:
        """One outstanding read per app; request cancellation cannot enqueue another worker."""
        if self._pending is None or self._pending.done():
            loop = asyncio.get_running_loop()
            self._pending = loop.create_future()
            self._pending.add_done_callback(self._observe_failure)
            # Filesystem waits cannot be cancelled in Python. A daemon worker avoids
            # trapping interpreter shutdown; no executor queue or retry fan-out.
            threading.Thread(
                target=self._worker,
                args=(loop, self._pending),
                daemon=True,
                name="omnis-web-assets",
            ).start()
        try:
            return await asyncio.wait_for(asyncio.shield(self._pending), timeout=1)
        except TimeoutError:
            return None

    @staticmethod
    def _observe_failure(future: asyncio.Future[dict[str, bytes] | None]) -> None:
        if not future.cancelled():
            future.exception()  # Retrieve late exceptions; active awaiters still receive them.

    def _worker(
        self, loop: asyncio.AbstractEventLoop, future: asyncio.Future[dict[str, bytes] | None]
    ) -> None:
        result = None
        failure = None
        try:
            result = self.load()
        except Exception:
            failure = RuntimeError("WEB_ASSET_READ_FAILED")

        def deliver() -> None:
            if not future.done():
                if failure is not None:
                    future.set_exception(failure)
                else:
                    future.set_result(result)

        try:
            loop.call_soon_threadsafe(deliver)
        except RuntimeError:
            # The owning API event loop has already closed. No live request remains.
            return

    def _read(self, name: str, limit: int) -> bytes:
        if self.root is None or not self.root.is_absolute() or self.root.resolve() != self.root:
            raise ValueError("Unavailable build root")
        path = self.root / name
        if path.resolve() != path:
            raise ValueError("Symlink in build")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise ValueError("Not a regular asset")
            content = source.read(limit + 1)
        if len(content) > limit:
            raise ValueError("Asset exceeds build budget")
        return content

    def load(self) -> dict[str, bytes] | None:
        """Read/hash current bytes; deleted or changed assets invalidate readiness immediately."""
        try:
            manifest = BuildManifest.model_validate_json(self._read("omnis-web.json", 32768))
            if "index.html" not in manifest.files or not any(
                n.endswith(".js") for n in manifest.files
            ):
                return None
            files = {}
            total = 0
            for name, digest in manifest.files.items():
                content = self._read(name, 2 * 1024 * 1024)
                total += len(content)
                if total > 8 * 1024 * 1024 or hashlib.sha256(content).hexdigest() != digest:
                    return None
                files[name] = content
            return files
        except (OSError, ValueError):
            return None


CONTENT_TYPES = {
    ".html": "text/html",
    ".js": "text/javascript",
    ".css": "text/css",
    ".woff2": "font/woff2",
    ".txt": "text/plain",
}
WEB_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self' data:; "
        "img-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    ),
}
