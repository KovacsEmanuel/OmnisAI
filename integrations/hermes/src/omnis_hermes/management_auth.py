"""Local-only native Codex credential projection; never refresh or adopt a grant.

Called only inside the exclusive management child. No native module is imported
at adapter/API startup. This module does not connect an account or infer readiness.
"""

import importlib
import logging
import math
import os
import time


def private_home() -> None:
    if any(
        os.environ.get(key) != value
        for key, value in {
            "HERMES_OMNIS_MANAGEMENT": "1",
            "HERMES_HOME": "/state/provider",
            "HOME": "/state/provider/os-home",
            "CODEX_HOME": "/state/provider/codex",
        }.items()
    ):
        raise ValueError("Private management authentication required")


def local_auth(method: str) -> str:
    private_home()
    if method not in {"GET", "DELETE"}:
        raise ValueError("Invalid local authentication method")
    # Native diagnostics can include paths, tokens or provider errors. Disable
    # their source logger before imports, not merely the parent's stderr reader.
    logging.getLogger("hermes_cli.auth").disabled = True
    native = importlib.import_module("hermes_cli.auth")
    resolve: object = getattr(native, "resolve_codex_runtime_credentials", None)
    clear: object = getattr(native, "clear_provider_auth", None)
    if not callable(resolve) or not callable(clear):
        raise ValueError("Pinned native authentication API missing")
    if method == "DELETE":
        try:
            clear("openai-codex")
        except Exception:
            raise ValueError("Local logout unconfirmed") from None
    try:
        credentials: object = resolve(read_only=True)
    except Exception as exc:
        state = "ABSENT" if getattr(exc, "code", None) == "codex_auth_missing" else "LOCAL_UNKNOWN"
    else:
        if type(credentials) is not dict or type(credentials.get("api_key")) is not str:
            state = "LOCAL_UNKNOWN"
        else:
            constants = importlib.import_module("hermes_cli.auth_constants")
            decode: object = getattr(constants, "_decode_jwt_claims", None)
            if not callable(decode):
                raise ValueError("Pinned native claims reader missing")
            claims: object = decode(credentials["api_key"])
            expiry: object = claims.get("exp") if type(claims) is dict else None
            # Local JWT claims are not an authenticated provider assertion.
            if (
                not isinstance(expiry, (int, float))
                or isinstance(expiry, bool)
                or not 0 <= expiry <= 253402300799
                or not math.isfinite(expiry)
            ):
                state = "LOCAL_UNKNOWN"
            else:
                state = "LOCAL_EXPIRED" if expiry <= time.time() else "LOCAL_PRESENT"
    if method == "DELETE" and state != "ABSENT":
        raise ValueError("Local logout readback unconfirmed")
    return state
