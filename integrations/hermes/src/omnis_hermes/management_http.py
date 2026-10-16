"""Fixed loopback native config client. No URL/profile/path passthrough or retries."""

import asyncio
import json
from contextlib import suppress

from .management_contract import selection
from .native_preparation_contract import loads


async def request(
    port: int, token: str, method: str, path: str, payload: dict[str, object] | None = None
) -> object:
    if (
        method not in {"GET", "PUT"}
        or path not in {"/api/health", "/api/config", "/api/config?include_defaults=false"}
        or type(port) is not int
        or not 1 <= port <= 65535
    ):
        raise ValueError("Management endpoint denied")
    raw = b"" if payload is None else json.dumps(payload, separators=(",", ":")).encode()
    async with asyncio.timeout(2):
        reader, writer = await asyncio.open_connection("127.0.0.1", port, limit=8192)
        try:
            writer.write(
                (
                    f"{method} {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
                    f"X-Hermes-Session-Token: {token}\r\nContent-Type: application/json\r\n"
                    f"Content-Length: {len(raw)}\r\nConnection: close\r\n\r\n"
                ).encode()
                + raw
            )
            await writer.drain()
            header = await reader.readuntil(b"\r\n\r\n")
            lines = header.decode("ascii").split("\r\n")
            if lines[0] != "HTTP/1.1 200 OK":
                raise ValueError("Management refused")
            lengths = [
                line.split(":", 1)[1].strip()
                for line in lines[1:]
                if line.lower().startswith("content-length:")
            ]
            if len(lengths) != 1 or not lengths[0].isdigit() or int(lengths[0]) > 4096:
                raise ValueError("Management response limit")
            return loads(await reader.readexactly(int(lengths[0])), 4096)
        finally:
            writer.close()
            with suppress(OSError, TimeoutError):
                await asyncio.wait_for(writer.wait_closed(), 0.2)


async def configure(
    port: int, token: str, action: str, selected: object
) -> dict[str, object] | None:
    checked = selection(selected)
    if action == "save":
        if checked is None:
            raise ValueError("Missing selection")
        result = await request(
            port,
            token,
            "PUT",
            "/api/config",
            {
                "config": {
                    "model": {"provider": checked["provider"], "default": checked["model"]},
                    "agent": {
                        "reasoning_effort": checked["effort"],
                        "reasoning_overrides": {"gpt-6.1-sol": checked["effort"]},
                    },
                    "auth": {"adopt_external_logins": False},
                }
            },
        )
        if type(result) is not dict or set(result) != {"ok"} or result["ok"] is not True:
            raise ValueError("Unconfirmed native save")
    elif action != "read":
        raise ValueError("Invalid action")
    value = await request(port, token, "GET", "/api/config?include_defaults=false")
    result = selection(value)
    if action == "save" and result != checked:
        raise ValueError("Native readback mismatch")
    return result
