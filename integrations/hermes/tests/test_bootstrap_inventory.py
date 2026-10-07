"""SIMULATION: source-bound bootstrap and real transport, not live Hermes QA."""

import ast
import asyncio
import json
import os
import sys
import threading
import time
import types
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[3]
ENTRY = ROOT / "integrations/hermes/upstream/inert-source/tui_gateway/entry.py"


def source_namespace():
    tree = ast.parse(ENTRY.read_text())
    nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("_omnis_")
    ]
    namespace = {
        "os": os,
        "sys": sys,
        "json": json,
        "time": time,
        "threading": threading,
        "Path": Path,
        "types": types,
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ENTRY), "exec"), namespace)
    return namespace


def absent_inventory():
    return {
        "schema_version": 1,
        "observation": "NATIVE_BOOTSTRAP",
        "scope": "/state/active",
        "registry": {
            "status": "NOT_INITIALIZED",
            "generation": None,
            "count": None,
            "entries": None,
        },
        "plugins": {"status": "NOT_INITIALIZED", "count": None, "entries": None},
    }


def test_inert_ready_observes_absence_without_import_or_discovery():
    namespace = source_namespace()
    frames = []

    def forbidden(*args, **kwargs):
        raise AssertionError("forbidden effect/import attempted")

    namespace.update(
        {
            "server": types.SimpleNamespace(),
            "_close_rpc_stdin_on_exec": lambda: None,
            "_install_sidecar_publisher": forbidden,
            "ensure_mcp_discovery_started": forbidden,
            "_write_or_exit": lambda frame, reason: frames.append(frame),
            "resolve_skin": lambda: {},
            "replay_epoch": lambda: "simulation",
        }
    )
    tree = ast.parse(ENTRY.read_text())
    main = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    main.body = main.body[
        : next(i for i, node in enumerate(main.body) if isinstance(node, ast.While))
    ]
    exec(compile(ast.Module(body=[main], type_ignores=[]), str(ENTRY), "exec"), namespace)
    with (
        patch.dict(sys.modules, {"tools.registry": None, "hermes_cli.plugins": None}),
        patch.dict(os.environ, {"HERMES_OMNIS_INERT": "1"}, clear=True),
        patch("builtins.__import__", forbidden),
    ):
        namespace["main"]()
    assert frames[0]["params"]["payload"].get("bootstrap_inventory") == absent_inventory()


def preexisting_registry(tools=None, scoped=None, generation=3):
    # SIMULATION of the inspected pinned ToolRegistry fields, no live claim.
    registry = types.SimpleNamespace(
        _tools={} if tools is None else tools,
        _scoped_tools={} if scoped is None else scoped,
        _generation=generation,
        _lock=threading.RLock(),
    )
    return registry


def observe(modules):
    namespace = source_namespace()
    with patch.dict(sys.modules, {"tools.registry": None, "hermes_cli.plugins": None, **modules}):

        def forbidden(*args, **kwargs):
            raise AssertionError("observer attempted an import")

        with patch("builtins.__import__", forbidden):
            return namespace["_omnis_bootstrap_inventory"]()


def test_existing_registry_empty_is_not_missing():
    module = types.ModuleType("tools.registry")
    module.registry = preexisting_registry()
    assert observe({"tools.registry": module})["registry"] == {
        "status": "REGISTERED_SNAPSHOT",
        "generation": 3,
        "count": 0,
        "entries": [],
    }


def test_preexisting_registry_scope_overlay_only_projects_registration_names():
    def forbidden(*args, **kwargs):
        raise AssertionError("availability/schema probe attempted")

    def entry(name, toolset):
        return types.SimpleNamespace(
            name=name,
            toolset=toolset,
            check_fn=forbidden,
            schema=forbidden,
            handler=forbidden,
            description="excluded",
        )

    module = types.ModuleType("tools.registry")
    module.registry = preexisting_registry(
        {"z": entry("z", "global"), "a": entry("a", "global")},
        {
            "/state/active": {"z": entry("z", "scoped")},
            "/other": {"secret": entry("secret", "excluded")},
        },
    )
    module.registry.get_definitions = forbidden
    module.registry.get_all_entries = forbidden
    assert observe({"tools.registry": module})["registry"] == {
        "status": "REGISTERED_SNAPSHOT",
        "generation": 3,
        "count": 2,
        "entries": [{"name": "a", "toolset": "global"}, {"name": "z", "toolset": "scoped"}],
    }


def preexisting_plugins(discovered=True, plugins=None):
    module = types.ModuleType("hermes_cli.plugins")
    manager = types.SimpleNamespace(
        _discovery_lock=threading.RLock(),
        _discovered=discovered,
        _plugins={} if plugins is None else plugins,
    )
    module._plugin_managers_by_home = {Path("/state/active"): manager}
    module._plugin_managers_lock = threading.RLock()
    module._background_discovery_thread = None
    module.get_plugin_manager = lambda: (_ for _ in ()).throw(AssertionError("factory attempted"))
    return module, manager


def test_cached_manager_absent_is_never_constructed():
    module, _ = preexisting_plugins()
    module._plugin_managers_by_home.clear()
    assert observe({"hermes_cli.plugins": module})["plugins"] == absent_inventory()["plugins"]
    assert module._plugin_managers_by_home == {}


def test_plugin_snapshot_projects_only_cached_boolean_state():
    module, _ = preexisting_plugins(
        plugins={
            "z": types.SimpleNamespace(module=None, enabled=False, deferred=True, error=None),
            "a": types.SimpleNamespace(
                module=types.ModuleType("synthetic"),
                enabled=True,
                deferred=False,
                error="excluded synthetic text",
                config="excluded",
            ),
        }
    )
    assert observe({"hermes_cli.plugins": module})["plugins"] == {
        "status": "PLUGIN_SNAPSHOT",
        "count": 2,
        "entries": [
            {
                "name": "a",
                "loaded": True,
                "enabled": True,
                "deferred": False,
                "error_present": True,
            },
            {
                "name": "z",
                "loaded": False,
                "enabled": False,
                "deferred": True,
                "error_present": False,
            },
        ],
    }


def test_plugins_initialized_empty_requires_completed_discovery():
    module, manager = preexisting_plugins(False)
    assert (
        observe({"hermes_cli.plugins": module})["plugins"]["status"] == "NOT_OBSERVED_IN_PROGRESS"
    )
    manager._discovered = True
    assert observe({"hermes_cli.plugins": module})["plugins"] == {
        "status": "PLUGIN_SNAPSHOT",
        "count": 0,
        "entries": [],
    }


def test_discovery_lock_busy_is_not_a_completed_snapshot():
    module, manager = preexisting_plugins()
    # RLock owned by the observing thread is still in-progress, not complete.
    with manager._discovery_lock:
        assert observe({"hermes_cli.plugins": module})["plugins"]["status"] == "NOT_OBSERVED_BUSY"


def test_abandoned_loader_is_in_progress_after_discovery_flag_set():
    module, _ = preexisting_plugins()
    loader = types.ModuleType("hermes_cli.plugins_loader")
    done = threading.Event()
    worker = threading.Thread(target=done.wait)
    worker.start()
    loader._ABANDONED_LOADERS = [worker]
    loader._ABANDONED_LOADERS_LOCK = threading.Lock()
    try:
        assert (
            observe({"hermes_cli.plugins": module, "hermes_cli.plugins_loader": loader})["plugins"][
                "status"
            ]
            == "NOT_OBSERVED_IN_PROGRESS"
        )
    finally:
        done.set()
        worker.join(1)


def test_registry_and_plugin_limits_do_not_truncate():
    registry = types.ModuleType("tools.registry")
    registry.registry = preexisting_registry(
        {str(i): types.SimpleNamespace(name=str(i), toolset="set") for i in range(257)}
    )
    plugins, _ = preexisting_plugins(plugins={str(i): None for i in range(129)})
    result = observe({"tools.registry": registry, "hermes_cli.plugins": plugins})
    assert result["registry"]["status"] == "LIMIT_EXCEEDED"
    assert result["plugins"]["status"] == "LIMIT_EXCEEDED"
    assert result["registry"]["entries"] is result["plugins"]["entries"] is None


@pytest.fixture
def short_ipc(tmp_path_factory):
    # AF_UNIX names include the fixture path; parametrized test IDs can exceed 108 bytes.
    root = tmp_path_factory.mktemp("bi")
    root.chmod(0o700)
    assert len(str(root / "runtime.sock").encode()) < 108
    return root


def simulation_peer(tmp_path, inventory):
    # Existing peer implementation, with only the explicit new ready fixture.
    fixture = Path(__file__).with_name("peer_fixture.py").read_text()
    tree = ast.parse(fixture)
    ready = next(
        node
        for node in tree.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "emit"
        and ast.literal_eval(node.value.args[0])["params"]["type"] == "gateway.ready"
    )
    frame = {
        "jsonrpc": "2.0",
        "method": "event",
        "params": {
            "type": "gateway.ready",
            "payload": {"bootstrap_inventory": inventory, "unknown_native_metadata": "excluded"},
        },
    }
    lines = fixture.splitlines(keepends=True)
    lines[ready.lineno - 1 : ready.end_lineno] = ["emit(" + repr(frame) + ")\n"]
    target = tmp_path / "inventory_peer.py"
    target.write_text("".join(lines))
    return target


@pytest.mark.asyncio
async def test_real_peer_to_stock_client_inventory_projection_and_stopped_retention(
    tmp_path, short_ipc
):
    from omnis_hermes.runtime_host import RuntimeHost
    from omnis_hermes.runtime_host import TestLaunch as LaunchFixture

    from omnis.modules.instance.service import RuntimeAuthority
    from omnis.supervisor.runtime_client import RuntimeClient

    class Authority:
        async def runtime_authority(self, owner, epoch, generation, *, inert_probe):
            assert inert_probe is True
            return RuntimeAuthority(generation, epoch, time.monotonic_ns() + 1_000_000_000)

    peer_path = simulation_peer(tmp_path, absent_inventory())
    ipc = short_ipc
    async with RuntimeHost(
        ipc, _test_launch=LaunchFixture((sys.executable, str(peer_path)), tmp_path)
    ) as host:
        client = RuntimeClient(ipc, generation=2, epoch=3)
        await client.connect()
        try:
            assert (await client.status())["bootstrap_inventory"] is None
            ready = await client.launch_inert(Authority(), uuid4())
            assert ready["bootstrap_inventory"] == absent_inventory()
            assert "unknown_native_metadata" not in ready
            assert host.peer.bootstrap_inventory == absent_inventory()
            assert await host.peer.call("ping", {}) == {"pong": True}
            await host.stop()
            # Uncontained fixture cannot claim physical STOPPED; projection only.
            assert host.snapshot()["bootstrap_inventory"] == absent_inventory()
            host.state = "STOPPED"
            assert (await client.status())["bootstrap_inventory"] == absent_inventory()
        finally:
            await client.close()


def invalid_inventories():
    values = [None, {}, {**absent_inventory(), "extra": "excluded"}]
    for key, value in [("schema_version", True), ("scope", "/wrong"), ("observation", "wrong")]:
        values.append({**absent_inventory(), key: value})
    for part in ("registry", "plugins"):
        for key, value in [
            ("status", "unknown"),
            ("count", 0),
            ("entries", []),
            ("extra", "excluded"),
        ]:
            item = absent_inventory()
            item[part] = {**item[part], key: value}
            values.append(item)
    good = absent_inventory()
    good["registry"] = {
        "status": "REGISTERED_SNAPSHOT",
        "generation": 0,
        "count": 1,
        "entries": [{"name": "a", "toolset": "set"}],
    }
    for key, value in [
        ("generation", True),
        ("count", 0),
        ("count", True),
        ("generation", -1),
        ("entries", [{"name": "a", "toolset": "set", "schema": "excluded"}]),
        ("entries", [{"name": "a\n", "toolset": "set"}]),
        ("entries", [{"name": "a" * 129, "toolset": "set"}]),
    ]:
        item = {**good, "registry": {**good["registry"], key: value}}
        values.append(item)
    for entries in [
        [{"name": "a", "toolset": "set"}] * 2,
        [{"name": "z", "toolset": "set"}, {"name": "a", "toolset": "set"}],
    ]:
        values.append({**good, "registry": {**good["registry"], "count": 2, "entries": entries}})
    plugin = {
        "name": "a",
        "loaded": False,
        "enabled": True,
        "deferred": False,
        "error_present": False,
    }
    for key in ("loaded", "enabled", "deferred", "error_present"):
        values.append(
            {
                **good,
                "plugins": {
                    "status": "PLUGIN_SNAPSHOT",
                    "count": 1,
                    "entries": [{**plugin, key: 0}],
                },
            }
        )
    return values


@pytest.mark.parametrize("value", invalid_inventories())
def test_both_dependency_boundaries_reject_invalid_inventory(value):
    from omnis_hermes import runtime_protocol

    from omnis.supervisor import runtime_client

    assert hasattr(runtime_protocol, "validate_bootstrap_inventory")
    assert hasattr(runtime_client, "validate_bootstrap_inventory")
    with pytest.raises(runtime_protocol.ProtocolError):
        runtime_protocol.validate_bootstrap_inventory(value)
    with pytest.raises(runtime_client.RuntimeUnavailable):
        runtime_client.validate_bootstrap_inventory(value)


def test_payload_overflow_is_explicit_not_truncated():
    module = types.ModuleType("tools.registry")
    module.registry = preexisting_registry(
        {f"n{i:03}": types.SimpleNamespace(name=f"n{i:03}", toolset="t" * 128) for i in range(256)}
    )
    result = observe({"tools.registry": module})
    assert result["registry"] == {
        "status": "LIMIT_EXCEEDED",
        "generation": None,
        "count": None,
        "entries": None,
    }
    assert len(json.dumps(result, ensure_ascii=False).encode()) <= 24 * 1024


def test_total_lock_wait_budget_is_shared():
    registry = types.ModuleType("tools.registry")
    registry.registry = preexisting_registry()
    plugins, manager = preexisting_plugins()
    done, held = threading.Event(), threading.Event()

    def worker():
        with registry.registry._lock, manager._discovery_lock:
            held.set()
            done.wait()

    thread = threading.Thread(target=worker)
    thread.start()
    assert held.wait(1)
    try:
        before = time.monotonic()
        result = observe({"tools.registry": registry, "hermes_cli.plugins": plugins})
        elapsed = time.monotonic() - before
        assert result["registry"]["status"] == result["plugins"]["status"] == "NOT_OBSERVED_BUSY"
        assert elapsed < 0.12  # Scheduling slack, not a second 50ms grant per lock.
    finally:
        done.set()
        thread.join(1)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload", [{}, {"bootstrap_inventory": {}}, {"bootstrap_inventory": invalid_inventories()[7]}]
)
async def test_real_peer_rejects_missing_and_malformed_ready(tmp_path, payload):
    from omnis_hermes.runtime_protocol import NativePeer, ProtocolError

    frame = {
        "jsonrpc": "2.0",
        "method": "event",
        "params": {"type": "gateway.ready", "payload": payload},
    }
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        "-c",
        "import time; print(" + repr(json.dumps(frame)) + ",flush=True); time.sleep(5)",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    peer = NativePeer(process, timeout=0.1)
    try:
        with pytest.raises(ProtocolError):
            await peer.handshake()
        assert peer.bootstrap_inventory is None
    finally:
        process.kill()
        await process.wait()
        await peer.close()


@pytest.mark.asyncio
async def test_late_duplicate_ready_refused_and_rpc_allowlist_preserved(tmp_path):
    from omnis_hermes.runtime_protocol import SAFE_UNKNOWN, NativePeer, ProtocolError, RPCError

    target = simulation_peer(tmp_path, absent_inventory())
    source = target.read_text()
    source = source.replace(
        'if mode.startswith("reverse_sequential_"):',
        'if mode == "duplicate":\n            emit({"jsonrpc":"2.0","method":"event","params":{"type":"gateway.ready","payload":{"bootstrap_inventory":'
        + repr(absent_inventory())
        + '}}})\n        if mode.startswith("reverse_sequential_"):',
    )
    target.write_text(source)
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        str(target),
        "duplicate",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    peer = NativePeer(process)
    try:
        await peer.handshake()
        with pytest.raises(ProtocolError):
            await peer.call("session.create", {})
        with pytest.raises(RPCError) as refused:
            await peer.call(SAFE_UNKNOWN, {})
        assert refused.value.code == -32601
        with pytest.raises(ProtocolError):
            await peer.call("ping", {})
        assert peer.failure is not None
    finally:
        process.kill()
        await process.wait()
        await peer.close()


def test_raw_duplicate_json_inventory_keys_are_denied():
    from omnis_hermes.runtime_protocol import ProtocolError, decode

    from omnis.supervisor.runtime_client import RuntimeUnavailable, _object

    raw = b'{"jsonrpc":"2.0","method":"event","params":{"type":"gateway.ready","payload":{"bootstrap_inventory":{"schema_version":1,"schema_version":1}}}}\n'
    with pytest.raises(ProtocolError):
        decode(raw)
    with pytest.raises(RuntimeUnavailable):
        _object(raw)


@pytest.mark.asyncio
async def test_stock_client_rejects_inventory_before_native_ready(short_ipc):
    from omnis_hermes.runtime_host import RuntimeHost

    from omnis.supervisor.runtime_client import RuntimeClient, RuntimeUnavailable

    ipc = short_ipc
    async with RuntimeHost(ipc) as host:
        original = host.snapshot
        host.snapshot = lambda: {**original(), "bootstrap_inventory": absent_inventory()}
        client = RuntimeClient(ipc, generation=0, epoch=1)
        await client.connect()
        try:
            with pytest.raises(RuntimeUnavailable):
                await client.status()
        finally:
            await client.close()


def test_invalid_internal_generation_has_explicit_non_observed_status():
    module = types.ModuleType("tools.registry")
    module.registry = preexisting_registry(generation=10**5000)
    result = observe({"tools.registry": module})
    assert result["registry"]["status"] == "NOT_OBSERVED_INVALID"
    assert result["registry"]["entries"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("inventory", invalid_inventories() + [None])
async def test_uds_invalid_ready(short_ipc, inventory):
    from omnis_hermes.runtime_host import RuntimeHost

    from omnis.supervisor.runtime_client import RuntimeClient, RuntimeUnavailable

    ipc = short_ipc
    async with RuntimeHost(ipc) as host:
        original = host.snapshot
        # SIMULATION at the IPC boundary; no native boot or lifecycle claim.
        host.state, host.generation, host.epoch = "READY", 0, 1
        host.snapshot = lambda: {**original(), "bootstrap_inventory": inventory}
        client = RuntimeClient(ipc, generation=0, epoch=1)
        await client.connect()
        try:
            with pytest.raises(RuntimeUnavailable):
                await client.status()
        finally:
            await client.close()
            host.state = "IDLE"


def test_both_validators_agree_on_all_declared_statuses_and_do_not_alias_input():
    from omnis_hermes.runtime_protocol import validate_bootstrap_inventory as native

    from omnis.supervisor.runtime_client import validate_bootstrap_inventory as stock

    for status in (
        "NOT_INITIALIZED",
        "NOT_OBSERVED_BUSY",
        "LIMIT_EXCEEDED",
        "NOT_OBSERVED_INVALID",
    ):
        value = absent_inventory()
        value["registry"]["status"] = value["plugins"]["status"] = status
        assert native(value) == stock(value) == value
        assert native(value)["registry"] is not value["registry"]
    value["plugins"]["status"] = "NOT_OBSERVED_IN_PROGRESS"
    assert native(value) == stock(value)
    value["registry"] = {
        "status": "REGISTERED_SNAPSHOT",
        "generation": 0,
        "count": 0,
        "entries": [],
    }
    value["plugins"] = {"status": "PLUGIN_SNAPSHOT", "count": 0, "entries": []}
    assert native(value) == stock(value) == value


def test_source_helper_cannot_import_or_call_forbidden_effect_sinks():
    tree = ast.parse(ENTRY.read_text())
    helpers = [
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("_omnis_")
    ]
    assert helpers
    forbidden = {
        "get_definitions",
        "get_all_entries",
        "get_plugin_manager",
        "discover_plugins",
        "discover_builtin_tools",
        "check_fn",
        "dynamic_schema",
        "_get_db",
        "prewarm_picker_cache_async",
        "Agent",
    }
    for helper in helpers:
        for node in ast.walk(helper):
            assert not isinstance(node, (ast.Import, ast.ImportFrom))
            if isinstance(node, ast.Call):
                name = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else getattr(node.func, "id", "")
                )
                assert name not in forbidden


def test_module_present_but_manager_cache_not_initialized_is_absent():
    module = types.ModuleType("hermes_cli.plugins")
    assert observe({"hermes_cli.plugins": module})["plugins"] == absent_inventory()["plugins"]


def test_pinned_slotted_tool_entry_projects_without_schema_or_handler():
    # Pinned ToolEntry is @dataclass(eq=False, slots=True), not a __dict__ row.
    @dataclass(eq=False, slots=True)
    class Entry:
        name: str
        toolset: str
        check_fn: object
        dynamic_schema_overrides: object

    def forbidden(*args, **kwargs):
        raise AssertionError("availability or dynamic schema attempted")

    module = types.ModuleType("tools.registry")
    module.registry = preexisting_registry({"a": Entry("a", "set", forbidden, forbidden)})
    assert observe({"tools.registry": module})["registry"] == {
        "status": "REGISTERED_SNAPSHOT",
        "generation": 3,
        "count": 1,
        "entries": [{"name": "a", "toolset": "set"}],
    }
