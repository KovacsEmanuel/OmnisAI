"""Source-prefix controls, NOT installed-native execution evidence.

HERMES_NATIVE_SOURCE selects original versus reviewed overlay. Real installed
coverage lives in managed_native_probe.py and must run in an isolated fixture.
"""

import ast
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get("HERMES_NATIVE_SOURCE", ROOT / "upstream/managed-source"))


def test_real_constructor_recognizes_cold_mode_before_init():
    tree = ast.parse((SOURCE / "run_agent.py").read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "AIAgent")
    init = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
    assert "cold_admission" in [n.arg for n in init.args.args], (
        "cold admission missing from real AIAgent"
    )
    code = ast.unparse(init)
    assert code.index("initialize_cold") < code.index("from agent.agent_init import init_agent")


def test_native_lifecycle_has_stage_release_and_blocks_stock_cold_launch():
    tree = ast.parse((SOURCE / "agent/subagent_lifecycle.py").read_text())
    cls = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SubagentLifecycleService"
    )
    names = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
    assert {"stage", "release", "readback"} <= names
    launch = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "launch")
    code = ast.unparse(launch)
    assert code.index("require_warm_parent") < code.index("_validate_request")


def test_inert_provider_home_lookup_never_loads_plugins(monkeypatch):
    import types

    node = next(
        n
        for n in ast.parse((SOURCE / "providers/__init__.py").read_text()).body
        if isinstance(n, ast.FunctionDef) and n.name == "_home_layer"
    )
    attempts = []

    def sink():
        attempts.append("home-lookup")
        return types.SimpleNamespace(), None, "test"

    namespace = {
        "os": os,
        "_HomeLayer": types.SimpleNamespace,
        "_bound_home_layer": sink,
        "_refresh_home_layer": lambda *a, **k: None,
    }
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), "provider-source-prefix", "exec"),
        namespace,
    )
    monkeypatch.setenv("HERMES_OMNIS_INERT", "1")
    namespace["_home_layer"]()
    assert attempts == [], "inert provider home discovery attempted"
    monkeypatch.delenv("HERMES_OMNIS_INERT")
    namespace["_home_layer"]()
    assert attempts == ["home-lookup"], "ordinary provider discovery must remain unchanged"


def test_no_optin_constructor_forwards_stock_options(monkeypatch):
    import sys
    import types
    import warnings

    tree = ast.parse((SOURCE / "run_agent.py").read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "AIAgent")
    init = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
    # Prefix control, not an AIAgent replacement or installed-native evidence.
    cls.bases = []
    cls.body = [init]
    prefix = ast.Module(
        body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
            cls,
        ],
        type_ignores=[],
    )
    calls = []
    module = types.ModuleType("agent.agent_init")
    module.init_agent = lambda agent, **kwargs: calls.append(kwargs)
    monkeypatch.setitem(sys.modules, "agent.agent_init", module)
    namespace = {"sys": sys, "warnings": warnings}
    exec(compile(ast.fix_missing_locations(prefix), "constructor-prefix", "exec"), namespace)
    namespace["AIAgent"](model="stock-model", quiet_mode=True)
    assert len(calls) == 1
    assert calls[0]["model"] == "stock-model" and calls[0]["quiet_mode"] is True
    assert "cold_admission" not in calls[0]
