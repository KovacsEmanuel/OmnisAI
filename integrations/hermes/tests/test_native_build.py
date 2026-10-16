"""No-I/O control of the actual pinned startup AST, not a gateway replacement.

Set HERMES_NATIVE_SOURCE to compare the same sink with original/patched sources.
Only startup prefixes and admission functions run; all effect sinks are recorders.
"""

from __future__ import annotations

import ast
import contextlib
import json
import os
import sys
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(
    os.environ.get("HERMES_NATIVE_SOURCE", ROOT / "integrations/hermes/upstream/inert-source")
)


def function(relative: str, name: str):
    tree = ast.parse((SOURCE / relative).read_text(encoding="utf-8"))
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


def run_node(node, namespace):
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
            "native-seam",
            "exec",
        ),
        namespace,
    )


class NativeInertSeam(unittest.TestCase):
    def test_native_error_precedence_over_cancel_and_expiry(self):
        import importlib
        import logging
        from uuid import uuid4

        import httpx
        from omnis_hermes.management_oauth import NativeOAuth
        from omnis_hermes.runtime_host import RuntimeHost

        for case in ("error", "cancel", "expiry", "ordinary_cancel", "guard_denial", "saved"):
            with self.subTest(case=case):
                entered, release = threading.Event(), threading.Event()
                native = types.ModuleType("synthetic_native")
                native._oauth_sessions = {}
                native._oauth_sessions_lock = threading.RLock()
                native._omnis_managed = True
                native._log = logging.getLogger("synthetic-native-precedence")
                native._log.disabled = True
                native._CODEX_ISSUER = "https://auth.openai.com"
                native._CODEX_EXPIRES_IN = 900
                native.time = time
                native._CANCELLED = object()
                native._profile_scope = lambda _: contextlib.nullcontext()
                native._codex_cancelled = lambda *args: False
                native._codex_exchange_tokens = lambda *args: {}
                native._codex_poll_authorization = lambda *args, native=native, case=case: (
                    native._CANCELLED if case == "ordinary_cancel" else {}
                )

                host = RuntimeHost(Path("unused"))
                reader = host._open_management_lifeline()
                owner = NativeOAuth.from_owner_fd(reader)

                def request(_httpx, entered=entered, release=release, case=case, owner=owner):
                    entered.set()
                    assert release.wait(2)
                    if case == "guard_denial":
                        owner.guard()
                    if case in {"error", "cancel", "expiry"}:
                        raise httpx.ReadError("synthetic reply loss")
                    return {"user_code": "TEST-CODE", "device_auth_id": "synthetic", "interval": 3}

                native._codex_request_user_code = request
                run_node(
                    function("hermes_cli/web_routers/oauth.py", "_codex_full_login_worker"),
                    native.__dict__,
                )
                lease = {
                    "operation_id": str(uuid4()),
                    "boot": str(uuid4()),
                    "generation": 1,
                    "epoch": 1,
                    "deadline_ns": time.monotonic_ns() + 4_000_000_000,
                }
                auth = types.ModuleType("hermes_cli.auth")
                saves = []
                auth._save_codex_tokens = lambda tokens, saves=saves: saves.append(True)
                original = importlib.import_module
                try:
                    with (
                        patch.object(
                            importlib,
                            "import_module",
                            lambda name, native=native, original=original: (
                                native if name == "hermes_cli.web_routers.oauth" else original(name)
                            ),
                        ),
                        patch.dict(sys.modules, {"hermes_cli.auth": auth}),
                    ):
                        owner.operate("connect", lease)
                        self.assertTrue(entered.wait(1))
                        if case in {"cancel", "ordinary_cancel", "guard_denial"}:
                            owner.operate("cancel", lease)
                        if case == "expiry":
                            owner.expires_ns = 1
                        release.set()
                        owner.thread.join(1)
                        self.assertFalse(owner.active)
                        result = owner.operate("cancel" if case == "saved" else "status", lease)
                    self.assertEqual(
                        result["oauth"],
                        "SAVED"
                        if case == "saved"
                        else "CANCELLED"
                        if case in {"ordinary_cancel", "guard_denial"}
                        else "INDETERMINATE",
                    )
                    self.assertEqual(saves, [True] if case == "saved" else [])
                    self.assertEqual(native._oauth_sessions, {})
                finally:
                    release.set()
                    if owner.thread:
                        owner.thread.join(2)
                    host._revoke_management_lifeline()
                    os.close(reader)

    @unittest.skipUnless((SOURCE / "hermes_cli/auth.py").is_file(), "full pinned source required")
    def test_managed_auth_import_does_not_discover_plugins(self):
        tree = ast.parse((SOURCE / "hermes_cli/auth.py").read_text())
        node = next(
            n
            for n in tree.body
            if isinstance(n, (ast.Expr, ast.If))
            and "sync_plugin_provider_registry()" in ast.unparse(n)
        )
        calls = []
        ns = {"os": os, "sync_plugin_provider_registry": lambda: calls.append("discover")}
        with patch.dict(os.environ, {"HERMES_OMNIS_MANAGEMENT": "1"}, clear=True):
            run_node(node, ns)
        self.assertEqual(calls, [])
        with patch.dict(os.environ, {}, clear=True):
            run_node(node, ns)
        self.assertEqual(calls, ["discover"])

    @unittest.skipUnless((SOURCE / "hermes_cli/auth.py").is_file(), "full pinned source required")
    def test_managed_auth_corruption_does_not_backup_log_or_claim_absence(self):
        effects = []
        node = function("hermes_cli/auth.py", "_load_auth_store")
        node.returns = None
        for arg in node.args.args:
            arg.annotation = None
        path = types.SimpleNamespace(
            exists=lambda: True,
            read_text=lambda **kw: "{broken",
            with_suffix=lambda suffix: "synthetic-corrupt-copy",
        )
        ns = {
            "os": os,
            "json": json,
            "shutil": types.SimpleNamespace(copy2=lambda *a: effects.append("backup")),
            "logger": types.SimpleNamespace(warning=lambda *a, **kw: effects.append("log")),
            "_empty_auth_store": lambda: {},
        }
        run_node(node, ns)
        with patch.dict(os.environ, {"HERMES_OMNIS_MANAGEMENT": "1"}, clear=True):
            with self.assertRaises(ValueError):
                ns["_load_auth_store"](path)
        self.assertEqual(effects, [])
        # Nonmanaged stock behavior is intentionally unchanged.
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(ns["_load_auth_store"](path), {})
        self.assertEqual(effects, ["backup", "log"])

    def test_startup_prefix_has_no_background_or_catalog_effects(self):
        effects = []

        def sink(name):
            return lambda *a, **k: effects.append(name)

        srv = types.SimpleNamespace(
            **{
                n: sink(n)
                for n in (
                    "_start_backend_heartbeat_refresher",
                    "_schedule_startup_orphan_sweep",
                    "_ensure_skin_watcher",
                )
            }
        )
        prefix = function("tui_gateway/entry.py", "main")
        prefix.body = prefix.body[
            : next(i for i, n in enumerate(prefix.body) if isinstance(n, ast.While))
        ]
        namespace = {
            "json": json,
            "sys": sys,
            "threading": threading,
            "time": time,
            "types": types,
            "Path": Path,
            "os": os,
            "server": srv,
            "logger": types.SimpleNamespace(warning=sink("warning"), debug=sink("debug")),
            "_close_rpc_stdin_on_exec": lambda: None,
            "_install_sidecar_publisher": sink("sidecar"),
            "ensure_mcp_discovery_started": sink("mcp"),
            "_write_or_exit": lambda *a: None,
            "resolve_skin": lambda: {},
            "replay_epoch": lambda: "epoch",
        }
        module = types.ModuleType("hermes_cli.model_switch_providers")
        module.prewarm_picker_cache_async = sink("provider-catalog")
        with (
            patch.dict(os.environ, {"HERMES_OMNIS_INERT": "1"}, clear=True),
            patch.dict(
                "sys.modules",
                {
                    "hermes_cli": types.ModuleType("hermes_cli"),
                    "hermes_cli.model_switch_providers": module,
                },
            ),
        ):
            tree = ast.parse((SOURCE / "tui_gateway/entry.py").read_text())
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and node.name.startswith("_omnis_"):
                    run_node(node, namespace)
            run_node(prefix, namespace)
            namespace["main"]()
        self.assertEqual(effects, [], "native startup attempted incidental effects")

    def test_import_update_prefetch_is_inert(self):
        tree = ast.parse((SOURCE / "tui_gateway/server.py").read_text(encoding="utf-8"))
        node = next(
            n
            for n in tree.body
            if isinstance(n, (ast.With, ast.If)) and "prefetch_update_check()" in ast.unparse(n)
        )
        effects = []
        module = types.ModuleType("hermes_cli.banner")
        module.prefetch_update_check = lambda: effects.append("update")
        with (
            patch.dict(os.environ, {"HERMES_OMNIS_INERT": "1"}, clear=True),
            patch.dict(
                "sys.modules",
                {"hermes_cli": types.ModuleType("hermes_cli"), "hermes_cli.banner": module},
            ),
        ):
            run_node(node, {"os": os, "contextlib": contextlib})
        self.assertEqual(effects, [], "import prefetch attempted updater effect")

    def test_dotenv_does_not_read_any_credential_source(self):
        node = function("hermes_cli/env_loader.py", "load_hermes_dotenv")

        # An import is already unsafe at this boundary: the inert path must return before discovery.
        def forbidden_import(*args, **kwargs):
            raise AssertionError("credential fallback/discovery attempted")

        ns = {
            "os": os,
            "Path": Path,
            "__builtins__": dict(vars(__import__("builtins")), __import__=forbidden_import),
        }
        with patch.dict(os.environ, {"HERMES_OMNIS_INERT": "1"}, clear=True):
            run_node(node, ns)
            self.assertEqual(
                ns["load_hermes_dotenv"](hermes_home="/synthetic", project_env="/synthetic/.env"),
                [],
            )

    def test_unsafe_native_management_is_denied_before_handler(self):
        node = function("tui_gateway/rpc_dispatch.py", "_handle_admitted_request")
        calls = []
        ns = {
            "os": os,
            "_normalize_request": lambda r: (r["id"], r["method"], r.get("params", {})),
            "_methods": {"session.create": lambda *a: calls.append("created")},
            "_contracts": types.SimpleNamespace(METHODS={}),
            "_current_rpc_method": __import__("contextvars").ContextVar("method", default=""),
            "ProfileUnavailableError": RuntimeError,
            "_err": lambda rid, code, message: {
                "id": rid,
                "error": {"code": code, "message": message},
            },
        }
        with patch.dict(os.environ, {"HERMES_OMNIS_INERT": "1"}, clear=True):
            run_node(node, ns)
            reply = ns["_handle_admitted_request"]({"id": 7, "method": "session.create"})
        self.assertEqual(calls, [], "management handler reached under inert flag")
        self.assertEqual(reply["error"]["code"], -32601)

    def test_inert_handshake_observations_reach_native_handlers(self):
        node = function("tui_gateway/rpc_dispatch.py", "_handle_admitted_request")
        for method in ("client.capabilities", "gateway.capabilities", "ping"):
            with self.subTest(method=method):
                calls = []

                def handler(rid, params, *, calls=calls, method=method):
                    calls.append(method)
                    return {"id": rid, "result": {"observed": True}}

                ns = {
                    "os": os,
                    "_normalize_request": lambda r: (r["id"], r["method"], r.get("params", {})),
                    "_methods": {method: handler},
                    "_contracts": types.SimpleNamespace(METHODS={}),
                    "_current_rpc_method": __import__("contextvars").ContextVar(
                        "method", default=""
                    ),
                    "ProfileUnavailableError": RuntimeError,
                    "_err": lambda rid, code, message: {"id": rid, "error": {"code": code}},
                }
                with patch.dict(os.environ, {"HERMES_OMNIS_INERT": "1"}, clear=True):
                    run_node(node, ns)
                    reply = ns["_handle_admitted_request"]({"id": 7, "method": method})
                self.assertEqual(calls, [method], "safe handshake observation was denied")
                self.assertEqual(reply, {"id": 7, "result": {"observed": True}})

    def test_lazy_install_is_hard_disabled_even_with_writable_target(self):
        node = function("tools/lazy_deps.py", "_allow_lazy_installs")
        cfg = types.ModuleType("hermes_cli.config")
        cfg.load_config = lambda: {}
        ns = {
            "os": os,
            "contextlib": contextlib,
            "_lazy_install_target": lambda: "/synthetic/writable",
        }
        with (
            patch.dict(
                os.environ,
                {"HERMES_OMNIS_INERT": "1", "HERMES_DISABLE_LAZY_INSTALLS": "1"},
                clear=True,
            ),
            patch.dict(
                "sys.modules",
                {"hermes_cli": types.ModuleType("hermes_cli"), "hermes_cli.config": cfg},
            ),
        ):
            run_node(node, ns)
            self.assertFalse(ns["_allow_lazy_installs"]())


if __name__ == "__main__":
    unittest.main()
