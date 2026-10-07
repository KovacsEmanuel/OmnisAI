"""No-I/O control of the actual pinned startup AST, not a gateway replacement.

Set HERMES_NATIVE_SOURCE to compare the same sink with original/patched sources.
Only startup prefixes and admission functions run; all effect sinks are recorders.
"""
from __future__ import annotations

import ast
import contextlib
import io
import os
from pathlib import Path
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(os.environ.get("HERMES_NATIVE_SOURCE", ROOT / "integrations/hermes/upstream/inert-source"))


def function(relative: str, name: str):
    tree = ast.parse((SOURCE / relative).read_text(encoding="utf-8"))
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


def run_node(node, namespace):
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), "native-seam", "exec"), namespace)


class NativeInertSeam(unittest.TestCase):
    def test_startup_prefix_has_no_background_or_catalog_effects(self):
        effects = []
        def sink(name):
            return lambda *a, **k: effects.append(name)
        srv = types.SimpleNamespace(**{n: sink(n) for n in (
            "_start_backend_heartbeat_refresher", "_schedule_startup_orphan_sweep", "_ensure_skin_watcher")})
        prefix = function("tui_gateway/entry.py", "main")
        prefix.body = prefix.body[:next(i for i, n in enumerate(prefix.body) if isinstance(n, ast.While))]
        namespace = {"os": os, "server": srv, "logger": types.SimpleNamespace(warning=sink("warning"), debug=sink("debug")),
                     "_close_rpc_stdin_on_exec": lambda: None, "_install_sidecar_publisher": sink("sidecar"),
                     "ensure_mcp_discovery_started": sink("mcp"), "_write_or_exit": lambda *a: None,
                     "resolve_skin": lambda: {}, "replay_epoch": lambda: "epoch"}
        module = types.ModuleType("hermes_cli.model_switch_providers")
        module.prewarm_picker_cache_async = sink("provider-catalog")
        with patch.dict(os.environ, {"HERMES_OMNIS_INERT": "1"}, clear=True), patch.dict("sys.modules", {"hermes_cli": types.ModuleType("hermes_cli"), "hermes_cli.model_switch_providers": module}):
            run_node(prefix, namespace)
            namespace["main"]()
        self.assertEqual(effects, [], "native startup attempted incidental effects")

    def test_import_update_prefetch_is_inert(self):
        tree = ast.parse((SOURCE / "tui_gateway/server.py").read_text(encoding="utf-8"))
        node = next(n for n in tree.body if isinstance(n, (ast.With, ast.If)) and "prefetch_update_check()" in ast.unparse(n))
        effects = []
        module = types.ModuleType("hermes_cli.banner")
        module.prefetch_update_check = lambda: effects.append("update")
        with patch.dict(os.environ, {"HERMES_OMNIS_INERT": "1"}, clear=True), patch.dict("sys.modules", {"hermes_cli": types.ModuleType("hermes_cli"), "hermes_cli.banner": module}):
            run_node(node, {"os": os, "contextlib": contextlib})
        self.assertEqual(effects, [], "import prefetch attempted updater effect")

    def test_dotenv_does_not_read_any_credential_source(self):
        node = function("hermes_cli/env_loader.py", "load_hermes_dotenv")
        # An import is already unsafe at this boundary: the inert path must return before discovery.
        def forbidden_import(*args, **kwargs):
            raise AssertionError("credential fallback/discovery attempted")
        ns = {"os": os, "Path": Path, "__builtins__": dict(vars(__import__("builtins")), __import__=forbidden_import)}
        with patch.dict(os.environ, {"HERMES_OMNIS_INERT": "1"}, clear=True):
            run_node(node, ns)
            self.assertEqual(ns["load_hermes_dotenv"](hermes_home="/synthetic", project_env="/synthetic/.env"), [])

    def test_unsafe_native_management_is_denied_before_handler(self):
        node = function("tui_gateway/rpc_dispatch.py", "_handle_admitted_request")
        calls = []
        ns = {"os": os, "_normalize_request": lambda r: (r["id"], r["method"], r.get("params", {})),
              "_methods": {"session.create": lambda *a: calls.append("created")},
              "_contracts": types.SimpleNamespace(METHODS={}),
              "_current_rpc_method": __import__("contextvars").ContextVar("method", default=""),
              "ProfileUnavailableError": RuntimeError,
              "_err": lambda rid, code, message: {"id": rid, "error": {"code": code, "message": message}}}
        with patch.dict(os.environ, {"HERMES_OMNIS_INERT": "1"}, clear=True):
            run_node(node, ns)
            reply = ns["_handle_admitted_request"]({"id": 7, "method": "session.create"})
        self.assertEqual(calls, [], "management handler reached under inert flag")
        self.assertEqual(reply["error"]["code"], -32601)

    def test_lazy_install_is_hard_disabled_even_with_writable_target(self):
        node = function("tools/lazy_deps.py", "_allow_lazy_installs")
        cfg = types.ModuleType("hermes_cli.config")
        cfg.load_config = lambda: {}
        ns = {"os": os, "contextlib": contextlib, "_lazy_install_target": lambda: "/synthetic/writable"}
        with patch.dict(os.environ, {"HERMES_OMNIS_INERT": "1", "HERMES_DISABLE_LAZY_INSTALLS": "1"}, clear=True), patch.dict("sys.modules", {"hermes_cli": types.ModuleType("hermes_cli"), "hermes_cli.config": cfg}):
            run_node(node, ns)
            self.assertFalse(ns["_allow_lazy_installs"]())


if __name__ == "__main__":
    unittest.main()
