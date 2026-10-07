"""Pure host tests plus a finite installed-only H02 observer, NOT a product API.

No native imports occur on import/pytest. The CLI accepts four fixed actions,
never paths/RPC names. Run native actions only in a parent-owned network-none
OCI fixture using /opt/hermes/venv/bin/python -I. Logout is PID1-only in a
separate offline container AFTER the original runtime has drained and joined;
parent must attest exclusivity of the shared synthetic store across namespaces.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import signal
import stat
import sys
from pathlib import Path

PIN = "ee5ee84a345204a3b1d6ef6ba1ab747e602867b9"
PROVIDER = "openai-codex"
PINS = {
    "HOME": "/state/os-home",
    "HERMES_HOME": "/state/active",
    "CODEX_HOME": "/state/codex",
    "XDG_CONFIG_HOME": "/state/xdg/config",
    "XDG_CACHE_HOME": "/state/xdg/cache",
    "XDG_STATE_HOME": "/state/xdg/state",
    "XDG_DATA_HOME": "/state/xdg/data",
    "TMPDIR": "/state/tmp",
    "HERMES_MANAGED_DIR": "/state/managed-empty",
    "HERMES_DISABLE_LAZY_INSTALLS": "1",
    "HERMES_SKIP_NODE_BOOTSTRAP": "1",
    "HERMES_OMNIS_INERT": "1",
    "PATH": "/opt/hermes/venv/bin:/usr/bin:/bin",
    "LANG": "C.UTF-8",
    "PYTHONUNBUFFERED": "1",
    "PYTHONNOUSERSITE": "1",
}
CONFIG_SHA256 = "14fe19b9866da73875d1342cb3649b94204d56e3bbef091d5e181a0e9ec8ae67"
SOURCE_HASHES = {
    "hermes_cli/auth.py": "1565d014485f1316e9ed0cf213fa6049c8db3bf6f449b15bfe675219734396b1",
    "hermes_cli/auth_codex.py": "1580e163e4f29eb76303f6cac79fbe0b2dc3b07bca6215101bf78030581d0fca",
    "hermes_cli/auth_constants.py": "3d978e76f28a18f8ee8b5d2e1df20031a2486b229b9dfcdd3555d62c7bfc5dc0",
    "hermes_constants.py": "3dd95a77b1a4956280f146e3b065789ca5d82921f69e6e2cae06d49a13f82405",
    "hermes_cli/env_loader.py": "2bb251025590b17ae13cc50dd8f6961ee5b20015791225355c0f2b0d3ce8da07",
    "agent/credential_sources.py": "4ad790a30d927a68367c5fa4ba5c3f2b6d2798b272b35e7dafbc97725763df3a",
    "tui_gateway/rpc_dispatch.py": "31429f1b8e1f1185d8b05e3281da5a85939071952386c5426713c02bde676743",
}
PATHS = {
    "checkout": Path("/opt/hermes/source/.env"),
    "root": Path("/state/os-home/.hermes/auth.json"),
    "codex": Path("/state/codex/auth.json"),
    "active": Path("/state/active/auth.json"),
    "config": Path("/state/active/config.yaml"),
}
CHECKOUT_MARKER = "h02-checkout-canary-not-a-real-key"
LABELS = ("h02-active-approved", "h02-root-canary", "h02-codex-canary")
ACTIONS = frozenset({"startup", "restart", "controls", "logout"})


def _jwt(label: str) -> str:
    # Syntactically valid, long-lived UNSIGNED synthetic JWT; never a real grant.
    parts = [
        {"alg": "none", "typ": "JWT"},
        {"exp": 4102444800, "sub": label, "iss": "h02-offline-synthetic"},
    ]
    encoded = [
        base64.urlsafe_b64encode(json.dumps(p, sort_keys=True).encode()).decode().rstrip("=")
        for p in parts
    ]
    return ".".join([*encoded, "h02syntheticsignature"])


def _tokens(label: str) -> dict[str, str]:
    return {"access_token": _jwt(label), "refresh_token": f"{label}-refresh-not-real"}


def _store(label: str) -> dict:
    tokens = _tokens(label)
    return {
        "version": 1,
        "active_provider": PROVIDER,
        "providers": {PROVIDER: {"auth_mode": "chatgpt", "tokens": tokens}},
        "credential_pool": {
            PROVIDER: [{"id": label, "source": "manual", "label": label, **tokens}]
        },
    }


def fixture_payloads() -> dict[str, bytes]:
    """Parent staging recipe; pure data, performs NO filesystem writes."""
    return {
        str(PATHS["checkout"]): f"OPENAI_API_KEY={CHECKOUT_MARKER}\n".encode(),
        str(PATHS["root"]): json.dumps(_store(LABELS[1]), sort_keys=True).encode(),
        str(PATHS["codex"]): json.dumps({"tokens": _tokens(LABELS[2])}, sort_keys=True).encode(),
        str(PATHS["active"]): json.dumps(_store(LABELS[0]), sort_keys=True).encode(),
    }


def decode_store(data: bytes) -> dict:
    """Refuse ambiguous raw keys before any marker or grant projection."""

    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("H02 duplicate store key")
            result[key] = value
        return result

    store = json.loads(data, object_pairs_hook=unique_keys)
    if not isinstance(store, dict):
        raise ValueError("H02 store object required")
    return store


def grant_flags(store: dict) -> dict[str, bool]:
    """Keep the whole parsed object for marker scanning, including unknown fields."""
    serialized = json.dumps(store, sort_keys=True)
    singleton = store.get("providers", {}).get(PROVIDER)
    pool = store.get("credential_pool", {}).get(PROVIDER)
    return {
        "singleton_approved": singleton == _store(LABELS[0])["providers"][PROVIDER],
        "pool_approved": pool == _store(LABELS[0])["credential_pool"][PROVIDER],
        "provider_absent": PROVIDER not in store.get("providers", {}),
        "pool_absent": PROVIDER not in store.get("credential_pool", {}),
        "active_absent": store.get("active_provider") is None,
        "external_marker_absent": not any(
            marker in serialized
            for marker in (
                CHECKOUT_MARKER,
                *_tokens(LABELS[1]).values(),
                *_tokens(LABELS[2]).values(),
            )
        ),
    }


def require_flags(flags: dict[str, bool], *, logged_out: bool) -> None:
    expected = {
        "singleton_approved": not logged_out,
        "pool_approved": not logged_out,
        "provider_absent": logged_out,
        "pool_absent": logged_out,
        "active_absent": logged_out,
        "external_marker_absent": True,
    }
    if flags.keys() != expected.keys() or any(
        type(flags[key]) is not bool or flags[key] is not value for key, value in expected.items()
    ):
        raise ValueError("H02 grant readback failed")


def _read_fixed(path: Path) -> bytes:
    # Called only with compile-time paths; reject symlinks at every ancestor.
    for entry in (path, *path.parents):
        if entry.is_symlink():
            raise ValueError("H02 symlink refused")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > 4_194_304 or info.st_nlink != 1:
        raise ValueError("H02 file boundary refused")
    return path.read_bytes()


def _source_attestation() -> dict[str, str]:
    from importlib.metadata import version

    root = Path("/opt/hermes/source")
    manifest = json.loads(_read_fixed(Path("/opt/hermes/provenance/source-manifest.json")))
    build = json.loads(_read_fixed(Path("/opt/hermes/provenance/build-manifest.json")))
    if manifest["pin"]["commit"] != PIN or manifest["pin"]["python"] != "3.13.15":
        raise ValueError("H02 source pin mismatch")
    override = build.get("dependency_override")
    if override != manifest.get("dependency_override") or not isinstance(override, dict):
        raise ValueError("H02 security override missing")
    if override["versions"] != {
        "anyio": ["4.12.1", "4.14.2"],
        "pyjwt": ["2.13.0", "2.15.0"],
        "urllib3": ["2.7.0", "2.8.0"],
    }:
        raise ValueError("H02 rejected dependency versions")
    if any(version(name) != versions[1] for name, versions in override["versions"].items()):
        raise ValueError("H02 installed dependency mismatch")
    result = {}
    for name, expected in SOURCE_HASHES.items():
        actual = hashlib.sha256(_read_fixed(root / name)).hexdigest()
        if actual != expected or build["native_source_files"].get(name) != expected:
            raise ValueError("H02 installed source mismatch")
        result[name] = actual
    return result


def _installed_guard(action: str) -> None:
    if action not in ACTIONS:
        raise ValueError("H02 unknown action")
    if (
        not sys.flags.isolated
        or sys.executable != "/opt/hermes/venv/bin/python"
        or sys.prefix != "/opt/hermes/venv"
        or sys.version_info[:3] != (3, 13, 15)
        or os.getuid() == 0
        or not Path("/.dockerenv").is_file()
        or Path.cwd() != Path("/state/work")
    ):
        raise ValueError("H02 installed owned OCI required")
    if "PYTEST_CURRENT_TEST" in os.environ or any(os.environ.get(k) != v for k, v in PINS.items()):
        raise ValueError("H02 dedicated environment required")
    interfaces = [
        line.split(":")[0].strip()
        for line in Path("/proc/net/dev").read_text().splitlines()
        if ":" in line
    ]
    if interfaces != ["lo"]:
        raise ValueError("H02 network-none required")
    if action == "logout" and os.getpid() != 1:
        raise ValueError(
            "H02 logout requires standalone PID1 and parent-attested store exclusivity"
        )


def _census() -> list[int]:
    return sorted(int(p.name) for p in Path("/proc").iterdir() if p.name.isdigit())


def _runtime_environment() -> dict:
    candidates = []
    for pid in _census():
        if pid == os.getpid():
            continue
        argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
        if argv[:4] == [b"/opt/hermes/venv/bin/python", b"-I", b"-m", b"tui_gateway.entry"]:
            candidates.append(pid)
    if len(candidates) != 1:
        raise ValueError("H02 exactly one fixed native consumer required")
    pid = candidates[0]
    environment = dict(
        item.decode().split("=", 1)
        for item in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
        if item
    )
    if environment != PINS:
        raise ValueError("H02 native consumer roots mismatch")
    forbidden = {
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENROUTER_API_KEY",
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTEST_CURRENT_TEST",
    }
    if forbidden.intersection(environment):
        raise ValueError("H02 native ambient credentials observed")
    return {
        "pid": pid,
        "pins_exact": True,
        "forbidden_absent": True,
        "boundary": "proc-initial-launch-env-not-post-import-memory",
    }


def offline_guard(event: str, attempted: list[str]) -> None:
    if event.startswith("socket.") or event in {
        "subprocess.Popen",
        "os.system",
        "os.fork",
        "os.posix_spawn",
        "os.exec",
    }:
        attempted.append(event)  # Survives a caller catching the exception.
        raise RuntimeError("H02 offline observer I/O refused")


def _native_observation(action: str) -> dict:
    _installed_guard(action)  # MUST precede every native import.
    sys.dont_write_bytecode = True
    source = _source_attestation()
    if hashlib.sha256(_read_fixed(PATHS["config"])).hexdigest() != CONFIG_SHA256:
        raise ValueError("H02 approved inert configuration required")
    payloads = fixture_payloads()
    external_before = {}
    for key in ("checkout", "root", "codex"):
        data = _read_fixed(PATHS[key])
        if data != payloads[str(PATHS[key])]:
            raise ValueError("H02 external fixture bytes mismatch")
        external_before[key] = hashlib.sha256(data).hexdigest()
    attempted = []

    def audit(event, _args):
        offline_guard(event, attempted)

    sys.addaudithook(audit)
    from agent.credential_sources import adopt_external_logins_enabled
    from hermes_cli import auth
    from hermes_cli.env_loader import load_hermes_dotenv

    if adopt_external_logins_enabled() is not False:
        raise ValueError("H02 explicit external-login denial required")
    before = decode_store(_read_fixed(PATHS["active"]))
    result = {"action": action, "source_hashes": source, "external_before": external_before}
    if action == "controls":
        # Same pinned readers, deliberately insecure local-only controls.
        original = dict(os.environ)
        try:
            os.environ.pop("HERMES_OMNIS_INERT")
            loaded = load_hermes_dotenv(project_env=PATHS["checkout"], load_external_secrets=False)
            checkout = (
                PATHS["checkout"] in loaded and os.environ.get("OPENAI_API_KEY") == CHECKOUT_MARKER
            )
            os.environ["HERMES_HOME"] = "/state/os-home/.hermes/profiles/h02-control"
            root = auth._read_codex_tokens(_lock=False)["tokens"] == _tokens(LABELS[1])
            root_pool = (
                auth.read_credential_pool(PROVIDER)
                == _store(LABELS[1])["credential_pool"][PROVIDER]
            )
            codex = auth._import_codex_cli_tokens() == _tokens(LABELS[2])
        finally:
            os.environ.clear()
            os.environ.update(original)
        controls = {
            "checkout_reader": checkout,
            "global_root_reader": root,
            "global_root_pool_reader": root_pool,
            "codex_cli_reader": codex,
        }
        if any(v is not True for v in controls.values()):
            raise ValueError("H02 insensitive canary control")
        if _read_fixed(PATHS["active"]) != payloads[str(PATHS["active"])]:
            raise ValueError("H02 controls mutated approved store")
        result["controls"] = controls
    else:
        if action in {"startup", "restart"}:
            result["native_launch_environment"] = _runtime_environment()
        if load_hermes_dotenv(project_env=PATHS["checkout"], load_external_secrets=False) != []:
            raise ValueError("H02 inert dotenv adoption observed")
        if "OPENAI_API_KEY" in os.environ:
            raise ValueError("H02 checkout marker observed")
        if action == "logout":
            if _census() != [1]:
                raise ValueError("H02 logout writers not absent")
            require_flags(grant_flags(before), logged_out=False)
            # Positive on BOTH native singleton and persisted pool before clear.
            if auth._read_codex_tokens(_lock=False)["tokens"] != _tokens(LABELS[0]):
                raise ValueError("H02 approved singleton unreadable")
            if (
                auth.read_credential_pool(PROVIDER)
                != _store(LABELS[0])["credential_pool"][PROVIDER]
            ):
                raise ValueError("H02 approved pool unreadable")
            if auth.clear_provider_auth(PROVIDER) is not True:
                raise ValueError("H02 clear-provider seam failed")
        after_bytes = _read_fixed(PATHS["active"])
        after = decode_store(after_bytes)
        flags = grant_flags(after)
        require_flags(flags, logged_out=action in {"logout", "restart"})
        result["grant_flags"] = flags
        if action == "startup":
            resolved = auth.resolve_codex_runtime_credentials(
                read_only=True, refresh_if_expiring=False
            )
            if resolved.get("api_key") != _tokens(LABELS[0])["access_token"]:
                raise ValueError("H02 approved credential resolution failed")
        else:
            try:
                auth.resolve_codex_runtime_credentials(read_only=True, refresh_if_expiring=False)
            except auth.AuthError as exc:
                if exc.code != "codex_auth_missing":
                    raise ValueError("H02 unexpected missing-auth diagnostic") from None
            else:
                raise ValueError("H02 logged-out credential reactivated")
        # Reader must not mutate the post-clear/startup bytes.
        if _read_fixed(PATHS["active"]) != after_bytes:
            raise ValueError("H02 read-only resolver mutated store")
    external_after = {k: hashlib.sha256(_read_fixed(PATHS[k])).hexdigest() for k in external_before}
    if external_after != external_before or attempted:
        raise ValueError("H02 external mutation or attempted offline I/O")
    result.update(
        {
            "external_after": external_after,
            "attempted_python_io": attempted,
            "observer_only_native_modules": sorted(
                name
                for name, module in sys.modules.items()
                if str(getattr(module, "__file__", "")).startswith("/opt/hermes/source/")
            ),
            "runtime_loaded_tool_inventory": "NOT_OBSERVED-no-native-in-process-observer",
            "logout_scope": "native-offline-local-clear-not-Omnis-Settings-not-upstream-revocation",
        }
    )
    return result


def main() -> int:
    timed_out = False
    old_handler = signal.getsignal(signal.SIGALRM)

    def deadline(*_args):
        nonlocal timed_out
        timed_out = True  # Remains set even if native code catches TimeoutError.
        raise TimeoutError()

    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ACTIONS:
            raise ValueError("H02 fixed action required")
        signal.signal(signal.SIGALRM, deadline)
        signal.alarm(10)
        result = _native_observation(sys.argv[1])
        if timed_out:
            raise TimeoutError()
        signal.alarm(0)
        print(json.dumps({"status": "OBSERVED_SCOPED", **result}, sort_keys=True))
        return 0
    except (
        ValueError,
        OSError,
        RuntimeError,
        TimeoutError,
        KeyError,
        TypeError,
        ImportError,
    ) as exc:
        # Never render native exception strings, credential objects or traceback.
        print(json.dumps({"status": "REFUSED", "error_type": type(exc).__name__}))
        return 4
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def test_synthetic_fixtures_have_distinct_decodable_nonexpired_jwts():
    claims = [
        json.loads(base64.urlsafe_b64decode(_jwt(label).split(".")[1] + "==")) for label in LABELS
    ]
    assert {c["sub"] for c in claims} == set(LABELS)
    assert all(c["exp"] == 4102444800 for c in claims)
    assert len({_jwt(label) for label in LABELS}) == len(LABELS)
    assert set(fixture_payloads()) == {
        str(PATHS[k]) for k in ("checkout", "root", "codex", "active")
    }


def test_grant_oracle_positive_and_logout_positive_are_distinct():
    require_flags(grant_flags(_store(LABELS[0])), logged_out=False)
    require_flags(
        grant_flags({"providers": {}, "credential_pool": {}, "active_provider": None}),
        logged_out=True,
    )


def test_grant_oracle_refuses_reactivated_singleton_pool_or_active():
    import pytest

    empty = {"providers": {}, "credential_pool": {}, "active_provider": None}
    for section in empty:
        changed = {**empty, section: _store(LABELS[0])[section]}
        with pytest.raises(ValueError, match="grant readback"):
            require_flags(grant_flags(changed), logged_out=True)


def test_unknown_top_level_and_nested_marker_is_not_stripped():
    import pytest

    for extra in (
        {"unknown": _tokens(LABELS[1])["access_token"]},
        {"nested": {"unknown": CHECKOUT_MARKER}},
    ):
        flags = grant_flags({**_store(LABELS[0]), **extra})
        assert flags["external_marker_absent"] is False
        with pytest.raises(ValueError, match="grant readback"):
            require_flags(flags, logged_out=False)


def test_grant_oracle_refuses_bool_integer_alias_and_unknown_fields():
    import pytest

    flags = grant_flags(_store(LABELS[0]))
    for changed in ({**flags, "singleton_approved": 1}, {**flags, "unknown": True}):
        with pytest.raises(ValueError, match="grant readback"):
            require_flags(changed, logged_out=False)


def test_observer_refuses_host_before_native_import():
    import pytest

    before = set(sys.modules)
    with pytest.raises(ValueError, match="installed owned OCI"):
        _native_observation("startup")
    assert set(sys.modules) == before
    with pytest.raises(ValueError, match="unknown action"):
        _native_observation("session.create")


def test_caught_offline_guard_violation_remains_recorded():
    attempted = []
    for event in ("socket.connect", "subprocess.Popen"):
        try:
            offline_guard(event, attempted)
        except RuntimeError:
            pass  # Deliberate hostile caller: successful return must not erase attempt.
    assert attempted == ["socket.connect", "subprocess.Popen"]
    offline_guard("open", attempted)
    assert attempted == ["socket.connect", "subprocess.Popen"]


def test_store_decoder_refuses_duplicate_keys_before_marker_scan():
    import pytest

    marker = json.dumps(_tokens(LABELS[1])["access_token"])
    for raw in (
        '{"unknown":' + marker + ',"unknown":"clean"}',
        '{"nested":{"unknown":' + marker + ',"unknown":"clean"}}',
    ):
        with pytest.raises(ValueError, match="duplicate store key"):
            decode_store(raw.encode())
    valid = _store(LABELS[0])
    assert decode_store(json.dumps(valid).encode()) == valid


def test_caught_observer_timeout_cannot_publish_success(monkeypatch, capsys):
    def swallowed_alarm(action):
        try:
            signal.raise_signal(signal.SIGALRM)
        except TimeoutError:
            pass
        return {"action": action}

    old_handler = signal.getsignal(signal.SIGALRM)
    monkeypatch.setattr(sys, "argv", [__file__, "startup"])
    monkeypatch.setitem(globals(), "_native_observation", swallowed_alarm)
    try:
        assert main() == 4
        assert json.loads(capsys.readouterr().out) == {
            "status": "REFUSED",
            "error_type": "TimeoutError",
        }
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def test_clean_observer_return_publishes_scoped_success(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [__file__, "startup"])
    monkeypatch.setitem(globals(), "_native_observation", lambda action: {"action": action})
    old_handler = signal.getsignal(signal.SIGALRM)
    try:
        assert main() == 0
        assert json.loads(capsys.readouterr().out) == {
            "status": "OBSERVED_SCOPED",
            "action": "startup",
        }
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


if __name__ == "__main__":
    raise SystemExit(main())
