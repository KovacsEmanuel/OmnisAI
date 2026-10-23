"""Public OpenAI SDK on a finite public HTTPX/httpcore seam, guarded at every write."""

import asyncio
import json
import ssl
from collections.abc import AsyncIterable, AsyncIterator, Callable, Iterable
from contextlib import AbstractAsyncContextManager
from contextvars import ContextVar
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpcore
import httpx
from openai import APIConnectionError, APIStatusError, AsyncOpenAI
from openai.types.chat import ChatCompletion
from pydantic import ValidationError

from omnis.modules.runs.model_test_contract import ACK, ENDPOINTS, Projection
from omnis.modules.runs.model_test_store import digest


class SendDenied(ValueError):
    pass


@dataclass(frozen=True)
class Permit:
    url: str
    body: dict[str, object] | None
    secret: str = field(repr=False)
    guard: Callable[[], AbstractAsyncContextManager[None]]
    response_limit: int


CURRENT: ContextVar[Permit] = ContextVar("omnis-model-write-permit")


class Stream(httpcore.AsyncNetworkStream):
    def __init__(self, stream: httpcore.AsyncNetworkStream) -> None:
        self.stream = stream

    async def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        return await self.stream.read(max_bytes, timeout)

    async def write(self, buffer: bytes, timeout: float | None = None) -> None:
        # Includes reused TLS streams and each headers/body write; no response wait under SQL locks.
        async with CURRENT.get().guard(), asyncio.timeout(0.5):
            await self.stream.write(buffer, timeout)

    async def start_tls(
        self,
        ssl_context: ssl.SSLContext,
        server_hostname: str | None = None,
        timeout: float | None = None,
    ) -> httpcore.AsyncNetworkStream:
        if server_hostname not in {httpx.URL(v).host for v in ENDPOINTS.values()}:
            raise SendDenied("ENDPOINT_DENIED")
        async with CURRENT.get().guard():
            pass  # Validate before TLS too; do not hold SQL authority while waiting for its response.
        return Stream(await self.stream.start_tls(ssl_context, server_hostname, timeout))

    async def aclose(self) -> None:
        await self.stream.aclose()

    def get_extra_info(self, info: str) -> object:
        value: object = self.stream.get_extra_info(info)
        return value


class Backend(httpcore.AsyncNetworkBackend):
    def __init__(self, path: Path) -> None:
        if not path.is_absolute() or len(bytes(path)) > 107:
            raise ValueError("Explicit bounded private egress socket required")
        self.path = path
        backend = httpcore.AnyIOBackend()
        if not isinstance(backend, httpcore.AsyncNetworkBackend):
            raise ValueError("Public network backend unavailable")
        self.backend = backend

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        if (
            host not in {httpx.URL(v).host for v in ENDPOINTS.values()}
            or port != 443
            or local_address is not None
        ):
            raise SendDenied("ENDPOINT_DENIED")
        async with CURRENT.get().guard():
            pass  # Private relay only; it receives TLS, never a caller-controlled CONNECT.
        return Stream(
            await self.backend.connect_unix_socket(str(self.path), timeout, socket_options)
        )

    async def sleep(self, seconds: float) -> None:
        raise SendDenied("RETRY_DENIED")


class ResponseStream(httpx.AsyncByteStream):
    def __init__(self, response: httpcore.Response, limit: int) -> None:
        self.response, self.limit = response, limit

    async def __aiter__(self) -> AsyncIterator[bytes]:
        size = 0
        async for part in self.response.aiter_stream():
            size += len(part)
            if size > self.limit:
                raise SendDenied("RESPONSE_LIMIT")
            yield part

    async def aclose(self) -> None:
        await self.response.aclose()


class Transport(httpx.AsyncBaseTransport):
    def __init__(self, path: Path, context: ssl.SSLContext) -> None:
        if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
            raise ValueError("Verified provider TLS required")
        self.pool = httpcore.AsyncConnectionPool(
            network_backend=Backend(path),
            ssl_context=context,
            retries=0,
            max_connections=1,
            max_keepalive_connections=1,
            http2=False,
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        permit = CURRENT.get()
        body = await request.aread()
        if (
            str(request.url) != permit.url
            or request.headers.get("authorization") != "Bearer " + permit.secret
            or request.headers.get("openai-organization")
            or request.headers.get("openai-project")
            or request.headers.get("x-stainless-retry-count", "0") != "0"
            or len(body) > 32768
            or (permit.body is None and (request.method != "GET" or body))
            or (
                permit.body is not None
                and (request.method != "POST" or digest(json.loads(body)) != digest(permit.body))
            )
        ):
            raise SendDenied("FINAL_DATA_DENIED")
        response = await self.pool.handle_async_request(
            httpcore.Request(
                method=request.method,
                url=httpcore.URL(
                    scheme=request.url.raw_scheme,
                    host=request.url.raw_host,
                    port=request.url.port,
                    target=request.url.raw_path,
                ),
                headers=request.headers.raw,
                content=body,
                extensions=request.extensions,
            )
        )
        encoding = dict(response.headers).get(b"content-encoding", b"identity")
        if encoding != b"identity":
            await response.aclose()
            raise SendDenied("ENCODED_RESPONSE_DENIED")
        if not isinstance(response.stream, AsyncIterable):
            await response.aclose()
            raise SendDenied("RESPONSE_UNAVAILABLE")
        return httpx.Response(
            status_code=response.status,
            headers=response.headers,
            stream=ResponseStream(response, permit.response_limit),
            extensions=response.extensions,
        )

    async def aclose(self) -> None:
        await self.pool.aclose()


@dataclass(frozen=True)
class Reply:
    result_state: str
    reason: str | None
    provider_status: str | None = None
    model: str | None = None
    response_id: str | None = None
    text: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    cost: str | None = None
    usage_invalid: bool = False


def failure_code(status: int, body: object) -> str:
    code: object = None
    if isinstance(body, dict):
        error: object = body.get("error", body)
        if isinstance(error, dict):
            code = error.get("code")
    if code == "insufficient_user_quota":
        return "PROVIDER_CREDIT"
    if code == "free_quota_exhausted":
        return "PROVIDER_QUOTA"
    return {
        401: "PROVIDER_AUTH",
        402: "PROVIDER_CREDIT_OR_KEY_LIMIT",
        429: "PROVIDER_RATE_OR_QUOTA",
    }.get(status, "PROVIDER_UNKNOWN")


class ModelSender:
    def __init__(self, path: Path, context: ssl.SSLContext | None = None) -> None:
        self.transport = Transport(path, context or ssl.create_default_context())
        self.http = httpx.AsyncClient(
            transport=self.transport,
            trust_env=False,
            follow_redirects=False,
            timeout=15,
            headers={"Accept-Encoding": "identity"},
        )

    async def metadata(
        self, endpoint: str, secret: str, guard: Callable[[], AbstractAsyncContextManager[None]]
    ) -> object:
        permit = Permit(endpoint + "/models", None, secret, guard, 2097152)
        token = CURRENT.set(permit)
        try:
            response = await self.http.get(
                permit.url, headers={"Authorization": "Bearer " + secret}
            )
            if response.status_code != 200:
                raise SendDenied("METADATA_PROVIDER_REJECTED")
            value: object = response.json()
            return value
        finally:
            CURRENT.reset(token)

    async def send(
        self,
        endpoint: str,
        secret: str,
        projection: Projection,
        guard: Callable[[], AbstractAsyncContextManager[None]],
    ) -> Reply:
        permit = Permit(
            endpoint + "/chat/completions", projection.request_body(), secret, guard, 131072
        )
        token = CURRENT.set(permit)
        try:
            sdk = AsyncOpenAI(
                api_key=secret,
                organization="",
                project="",
                base_url=endpoint,
                max_retries=0,
                timeout=300,
                http_client=self.http,
                default_headers={},
            )
            async with sdk.chat.completions.with_streaming_response.create(
                model=projection.model,
                messages=[
                    {"role": "system", "content": projection.system},
                    {"role": "user", "content": projection.user},
                ],
                max_tokens=projection.output_tokens,
                stream=False,
                extra_body={"provider": {"allow_fallbacks": False, "require_parameters": True}},
            ) as response:
                raw = b"".join([part async for part in response.iter_bytes()])
                parsed: object = json.loads(raw)
                if isinstance(parsed, dict) and "error" in parsed:
                    return Reply("FAILED", failure_code(200, parsed), "200")
                # Usage is optional evidence; SDK coercion must not turn invalid originals into facts.
                raw_usage = parsed.pop("usage", None) if isinstance(parsed, dict) else None
                usage = raw_usage if isinstance(raw_usage, dict) else {}
                details = usage.get("completion_tokens_details")
                original = [
                    usage.get("prompt_tokens"),
                    usage.get("completion_tokens"),
                    details.get("reasoning_tokens") if isinstance(details, dict) else None,
                ]
                counts = [
                    v if type(v) is int and 0 <= v <= 9007199254740991 else None for v in original
                ]
                invalid_usage = (
                    (raw_usage is not None and not isinstance(raw_usage, dict))
                    or (details is not None and not isinstance(details, dict))
                    or any(
                        v is not None and n is None for v, n in zip(original, counts, strict=True)
                    )
                )
                completion = ChatCompletion.model_validate_json(json.dumps(parsed))
                if not completion.choices:
                    return Reply("INCOMPLETE", "RESPONSE_INCOMPLETE", "200")
                choice = completion.choices[0]
                content = choice.message.content
                state = (
                    "COMPLETED"
                    if choice.finish_reason == "stop"
                    and content is not None
                    and content.strip() == ACK
                    else "INCOMPLETE"
                )
                extra: object = usage
                cost = None
                if isinstance(extra, dict) and type(extra.get("cost")) in (int, float, str):
                    try:
                        amount = Decimal(str(extra["cost"]))
                        if amount.is_finite() and amount >= 0 and len(str(amount)) <= 128:
                            cost = str(amount)
                    except InvalidOperation:
                        cost = None
                return Reply(
                    state,
                    ("USAGE_INVALID" if invalid_usage else None)
                    if state == "COMPLETED"
                    else "ACK_OR_COMPLETION_UNVERIFIED",
                    "200",
                    completion.model.replace(secret, "[REDACTED]")[:256],
                    completion.id.replace(secret, "[REDACTED]")[:256],
                    content.replace(secret, "[REDACTED]") if content is not None else None,
                    counts[0],
                    counts[1],
                    counts[2],
                    cost,
                    invalid_usage,
                )
        except APIStatusError as error:
            return Reply(
                "FAILED", failure_code(error.status_code, error.body), str(error.status_code)
            )
        except (APIConnectionError, httpx.HTTPError, SendDenied, ValidationError, ValueError):
            return Reply("UNKNOWN", "RESULT_UNKNOWN")
        finally:
            CURRENT.reset(token)

    async def drain(self) -> None:
        await self.transport.aclose()

    async def close(self) -> None:
        await self.http.aclose()
