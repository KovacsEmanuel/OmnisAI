"""Source-prefix controls, NOT installed-native execution evidence.

HERMES_NATIVE_SOURCE selects original versus reviewed overlay. Real installed
coverage lives in managed_native_probe.py and must run in an isolated fixture.
"""

import ast
import os
from pathlib import Path

import pytest

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


def test_composition_bytes_are_retained_before_native_child_construction():
    tree = ast.parse((SOURCE / "agent/subagent_lifecycle.py").read_text())
    cls = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SubagentLifecycleService"
    )
    stage = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "stage")
    code = ast.unparse(stage)
    assert "composition_material" in code, "validated v2 material is not consumed/retained"
    assert (
        code.index("validate_stage")
        < code.index("composition_material")
        < code.index("child = AIAgent")
    )
    assert "protocol=payload['protocol']" in code
    batch = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_cold_batch")
    assert "'protocol'" in ast.unparse(batch), "batch replay permits protocol downgrade"


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


def test_inert_runner_import_does_not_load_the_stock_inventory(monkeypatch):
    """SOURCE import prefix; ordinary stock lookup remains unchanged."""
    import builtins
    import types
    import typing

    tree = ast.parse((SOURCE / "run_agent.py").read_text())
    prefix = ast.Module(
        body=[
            node
            for node in tree.body
            if any(
                isinstance(child, ast.ImportFrom) and child.module == "model_tools"
                for child in ast.walk(node)
            )
            and not isinstance(node, (ast.FunctionDef, ast.ClassDef))
        ],
        type_ignores=[],
    )
    calls = []
    original = builtins.__import__

    def imported(name, *args, **kwargs):
        if name == "model_tools":
            calls.append(name)
            return types.SimpleNamespace(get_toolset_for_tool=lambda value: ("stock", value))
        return original(name, *args, **kwargs)

    namespace = {
        "os": os,
        "Optional": typing.Optional,
        "__builtins__": {**vars(builtins), "__import__": imported},
    }
    monkeypatch.delenv("HERMES_OMNIS_INERT", raising=False)
    exec(compile(ast.fix_missing_locations(prefix), "runner-import-prefix", "exec"), namespace)
    assert namespace["get_toolset_for_tool"]("tool") == ("stock", "tool")
    assert calls == ["model_tools"]
    calls.clear()
    monkeypatch.setenv("HERMES_OMNIS_INERT", "1")
    exec(compile(ast.fix_missing_locations(prefix), "runner-import-prefix", "exec"), namespace)
    assert calls == [], "inert import loaded the unrelated stock inventory"


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


@pytest.mark.parametrize("hostname", ["api.openai.com", "api.githubcopilot.com"])
def test_owned_configuration_can_resolve_token_cap_without_opening_warm_surfaces(hostname):
    """Exact native method bodies; SOURCE, not a constructor or provider proof."""
    tree = ast.parse((SOURCE / "run_agent.py").read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "AIAgent")
    methods = {
        "__getattribute__",
        "_hostname_for",
        "_is_direct_openai_url",
        "_is_azure_openai_url",
        "_is_github_copilot_url",
        "_max_tokens_param",
    }
    cls.bases = []
    cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in methods]
    assert {n.name for n in cls.body} == methods
    prefix = ast.Module(
        body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
            cls,
        ],
        type_ignores=[],
    )
    namespace = {"base_url_host_matches": lambda *_a: False}
    exec(
        compile(ast.fix_missing_locations(prefix), "owned-configuration-prefix", "exec"), namespace
    )
    actor = namespace["AIAgent"]()
    actor.__dict__.update(
        _owned_initialization=object(),  # Denial marker only, never initialization authority.
        _base_url_hostname=hostname,
        _base_url_lower=f"https://{hostname}/v1",
    )
    assert actor._max_tokens_param(16) == {"max_completion_tokens": 16}
    for surface in ("run_conversation", "make_client"):
        with pytest.raises(ValueError, match="DEFERRED_NO_CREDENTIAL"):
            getattr(actor, surface)
