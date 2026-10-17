import os
import sys

# Stop a ``utils/``-style package in the launch directory from shadowing Hermes's own
# top-level modules; ``hermes_bootstrap``'s name can't collide, so importing it first is safe.
import hermes_bootstrap

hermes_bootstrap.harden_import_path()

import json
import logging
import signal
import threading
import time
import traceback
import types
from contextlib import suppress
from pathlib import Path

from tui_gateway._env import env_float
from tui_gateway._stdin_recovery import handle_spurious_eof

from tui_gateway import server
from tui_gateway.event_replay import replay_epoch
from tui_gateway.server import _CRASH_LOG, _err, dispatch, resolve_skin, write_json
from tui_gateway.transport import TeeTransport

logger = logging.getLogger(__name__)

# Discovery thread spawned by THIS module; None when delegated to the shared owner in
# hermes_cli.mcp_startup (current path). The wait/in-flight/join helpers consult both.
_mcp_discovery_thread = None
# Set once MCP servers are found configured so wait_for_mcp_discovery can re-invoke the
# idempotent spawn on later builds without a config re-probe.
_mcp_discovery_enabled = False


def _close_rpc_stdin_on_exec() -> None:
    """Keep stdio RPC requests out of children launched by the gateway.

    The TUI's stdin is the Node-to-Python JSON-RPC socketpair.  Standard
    descriptors survive subprocess execution unless they are explicitly
    close-on-exec, so a dependency that launches a child without ``stdin=``
    could otherwise consume a request before this process reads it.

    Windows does not provide the POSIX FD_CLOEXEC contract used here; retain
    its existing descriptor behavior rather than changing its launch paths.
    """
    if os.name != "posix":
        return
    try:
        os.set_inheritable(sys.stdin.fileno(), False)
    except (OSError, ValueError):
        # Embedded launchers can supply a stream without an inheritable file
        # descriptor. Keep gateway startup available when no guard is possible.
        logger.debug("could not mark TUI RPC stdin close-on-exec", exc_info=True)


def _install_sidecar_publisher() -> None:
    """Mirror every dispatcher emit to the dashboard sidebar via WS when set (best-effort)."""
    url = os.environ.get("HERMES_TUI_SIDECAR_URL")
    if not url:
        return
    from tui_gateway.event_publisher import WsPublisherTransport
    server._stdio_transport = TeeTransport(server._stdio_transport, WsPublisherTransport(url))


# Grace for orderly shutdown before ``os._exit(0)`` so a worker wedged mid-flush can't
# strand the process; ``HERMES_TUI_GATEWAY_SHUTDOWN_GRACE_S`` overrides.
_DEFAULT_SHUTDOWN_GRACE_S = 1.0


def _shutdown_grace_seconds() -> float:
    value = env_float("HERMES_TUI_GATEWAY_SHUTDOWN_GRACE_S", _DEFAULT_SHUTDOWN_GRACE_S)
    return value if value > 0 else _DEFAULT_SHUTDOWN_GRACE_S


def _mcp_startup_call(name: str, *args, default=None, log=None, **kwargs):
    """Call ``hermes_cli.mcp_startup.<name>`` (lazy import); ``default`` on any failure,
    optionally logged as ``(level, message)``."""
    try:
        from hermes_cli import mcp_startup
        return getattr(mcp_startup, name)(*args, **kwargs)
    except Exception:
        if log:
            getattr(logger, log[0])(log[1], exc_info=True)
        return default


def _spawn_discovery(log: tuple) -> None:
    _mcp_startup_call(
        "start_background_mcp_discovery", logger=logger, thread_name="tui-mcp-discovery", log=log)


def _append_crash_log(header: str, dump=None) -> None:
    """Best-effort ``=== header ===`` entry in the crash log; ``dump(f)`` adds detail."""
    with suppress(Exception):
        os.makedirs(os.path.dirname(_CRASH_LOG), exist_ok=True)
        with open(_CRASH_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n=== {header} ===\n")
            if dump is not None:
                dump(f)


def _hard_exit() -> None:
    """The grace timer's ``os._exit``. The flush runs first and the graceful foreground kill
    (TERM, wait, KILL) after it, so a SIGTERM-ignoring command is usually still alive here:
    SIGKILL its tree now or it outlives us, reparented to init."""
    with suppress(Exception):
        from tools.environments.base import kill_live_foreground_processes
        kill_live_foreground_processes(now=True)
    os._exit(0)


def _close_model_test_preparations():
    owner = sys.modules.get("agent.managed_admission_rpc")
    if owner is not None:
        owner.close_preparations()


def _log_signal(signum: int, frame) -> None:
    """Capture WHICH thread and WHERE a termination signal hit us, then exit. ``sys.exit(0)``
    alone raced the worker pool (a thread holding ``_stdout_lock`` mid-flush blocks interpreter
    shutdown), so: log all thread stacks, give the configured grace to drain, then ``os._exit``."""
    _close_model_test_preparations()
    # SIGPIPE/SIGHUP don't exist on Windows — only look up attributes present.
    names = {int(sig): attr for attr in ("SIGPIPE", "SIGTERM", "SIGHUP", "SIGINT", "SIGBREAK")
             if (sig := getattr(signal, attr, None)) is not None}
    name = names.get(signum, f"signal {signum}")

    def _dump(f):
        if frame is not None:
            f.write("main-thread stack at signal delivery:\n")
            traceback.print_stack(frame, file=f)
        # All live threads — the signal may have come from a background writer.
        for tid, th in threading._active.items():
            f.write(f"\n--- thread {th.name} (id={tid}) ---\n")
            f.write("".join(traceback.format_stack(sys._current_frames().get(tid))))

    _append_crash_log(f"{name} received · {time.strftime('%Y-%m-%d %H:%M:%S')}", _dump)
    print(f"[gateway-signal] {name}", file=sys.stderr, flush=True)
    # ``os._exit`` skips atexit but breaks the mid-flush deadlock; the crash log is the trail.
    timer = threading.Timer(_shutdown_grace_seconds(), _hard_exit)
    timer.daemon = True
    timer.start()
    # atexit (_shutdown_sessions) can be blocked past the grace window by a worker holding
    # the GIL/_stdout_lock; finalize explicitly so unpersisted messages reach state.db first.
    with suppress(Exception):
        from tui_gateway.server import _shutdown_sessions
        _shutdown_sessions()
    # Unwind the main thread so atexit + finalisers run; the daemon timer is the safety net.
    sys.exit(0)


def _install_signal(signame, handler):
    """Install a signal handler if legal here: signal.signal() raises off the main thread
    (Desktop build path imports entry from a worker) and Windows lacks SIGPIPE/SIGHUP."""
    sig = getattr(signal, signame, None)
    if sig is None or threading.current_thread() is not threading.main_thread():
        return
    with suppress(ValueError, OSError, RuntimeError):  # platform rejected the handler
        signal.signal(sig, handler)


# SIGPIPE: ignore, don't exit — SIG_DFL killed the process silently whenever a background
# thread wrote to a pipe the TUI had gone quiet on; ignoring lets write_json see
# BrokenPipeError and exit via _log_exit. Terminal signals route through _log_signal so
# kills/hangups are diagnosable (SIGBREAK = Windows SIGHUP).
_install_signal("SIGPIPE", signal.SIG_IGN)
_install_signal("SIGTERM", _log_signal)
if hasattr(signal, "SIGHUP"):
    _install_signal("SIGHUP", _log_signal)
elif hasattr(signal, "SIGBREAK"):
    _install_signal("SIGBREAK", _log_signal)
_install_signal("SIGINT", signal.SIG_IGN)


def _log_exit(reason: str) -> None:
    """Record why the gateway exits (every path is a silent sys.exit(0) otherwise)."""
    _close_model_test_preparations()
    _append_crash_log(f"gateway exit · {time.strftime('%Y-%m-%d %H:%M:%S')} · reason={reason}")
    print(f"[gateway-exit] {reason}", file=sys.stderr, flush=True)


def wait_for_mcp_discovery(timeout: "float | None" = None) -> None:
    """Block until background MCP discovery finishes, up to the resolved bound (config
    ``mcp_discovery_timeout``; ``timeout`` overrides). The agent snapshots its tool list ONCE
    at build time, so this bounded join lets already-spawning servers land."""
    thread = _mcp_discovery_thread
    if thread is not None and thread.is_alive():
        fallback = timeout if timeout is not None else 0.75
        bound = _mcp_startup_call("_resolve_discovery_timeout", timeout, default=fallback)
        thread.join(timeout=bound)
        return
    # Shared-owner path: re-invoke the idempotent spawn first so a zero-connected run gets
    # its retry instead of latching the process MCP-less (runs under the CALLER's profile).
    # Discovery is spawned via the shared owner (ensure_mcp_discovery_started → hermes_cli.mcp_startup);
    # wait on it so the first agent build still catches fast servers. Re-invoke the idempotent spawn first:
    # if the previous run finished with zero connected servers, start_background_mcp_discovery's
    # retry-after-zero-connected allowance kicks off a fresh discovery run here instead of leaving the
    # process latched MCP-less for the session. In multi-profile processes this retry runs under the
    # CALLER's profile context (agent build binds the session profile's HERMES_HOME first), so a launch
    # profile with no mcp_servers no longer starves selected profiles of discovery (#67605). Gated on
    # _mcp_discovery_enabled so non-MCP sessions never pay the tools.mcp_tool import on the per-agent-build
    # wait path.
    if not _mcp_discovery_enabled:
        return
    _spawn_discovery(("debug", "TUI MCP discovery retry-spawn failed"))
    _mcp_startup_call("wait_for_mcp_discovery", timeout)


def mcp_discovery_in_flight() -> bool:
    """True if ANY background MCP discovery thread is still running: the late-refresh
    scheduler calls this regardless of surface, so it MUST consult both owners.

    There are two independent discovery-thread owners by surface: the stdio ``hermes --tui`` path spawns ITS
    thread here (``_mcp_discovery_thread``), while the desktop app + dashboard WebSocket sidecar
    (``tui_gateway/ws.py``) and ``hermes dashboard`` spawn theirs via
    ``hermes_cli.mcp_startup.start_background_mcp_discovery``. The late-refresh scheduler imports this
    function regardless of surface, so it MUST consult both — checking only the entry thread left the
    desktop/dashboard surfaces with no late refresh, so a slow MCP server's tools never surfaced for the
    whole session (#51587).
    """
    thread = _mcp_discovery_thread
    if thread is not None and thread.is_alive():
        return True
    return _mcp_startup_call("mcp_discovery_in_flight", default=False)


def join_mcp_discovery(timeout: float | None = None) -> bool:
    """Join both discovery owners; True once neither is alive. Accepts an unbounded wait
    (off-critical-path late-refresh waiter); ``timeout`` bounds EACH join, entry thread first.

    Joins both discovery-thread owners (see ``mcp_discovery_in_flight``): the entry thread first, then the
    ``hermes_cli.mcp_startup`` thread used by the desktop/dashboard surfaces. See #51587.
    """
    entry_done = True
    thread = _mcp_discovery_thread
    if thread is not None:
        thread.join(timeout=timeout)
        entry_done = not thread.is_alive()
    return entry_done and _mcp_startup_call("join_mcp_discovery", timeout=timeout, default=True)


# Spurious stdin-EOF recovery tracker (shared open-file-description O_NONBLOCK flip).
_recovery_times: list[float] = []


def _has_configured_mcp_servers() -> bool:
    """Delegate to the shared native and portable MCP startup gate."""
    from hermes_cli.mcp_startup import _has_configured_mcp_servers as configured
    return configured()


def ensure_mcp_discovery_started() -> None:
    """Start background MCP discovery for the current profile context, once per profile home.
    ``main()`` calls this for stdio; ``server._start_agent_build`` also calls it AFTER binding the
    session profile's HERMES_HOME.

    WebSocket/Desktop entrypoints can accept sessions without running ``main()``, so the agent-build path
    (``server._start_agent_build``) also calls it AFTER binding the session profile's HERMES_HOME override —
    the shared owner in ``hermes_cli.mcp_startup`` captures the caller's context-local override and
    propagates it into the discovery thread, so discovery reads the SELECTED profile's ``mcp_servers``, not
    the launch profile's. The discovery slot in ``hermes_cli.mcp_startup`` is keyed by profile home, so
    every profile a shared backend serves discovers its own ``mcp_servers`` (#67605).
    """
    global _mcp_discovery_enabled
    if not _has_configured_mcp_servers():
        return
    _mcp_discovery_enabled = True
    _spawn_discovery(("warning", "Background MCP tool discovery failed to start"))


def _write_or_exit(payload: dict, reason: str) -> None:
    if not write_json(payload):
        _log_exit(reason)
        sys.exit(0)


def _omnis_name(value):
    return (type(value) is str and 0 < len(value) <= 128
            and not any(ord(c) < 32 or 127 <= ord(c) <= 159
                        or 0xD800 <= ord(c) <= 0xDFFF or c in "/\\" for c in value))


def _omnis_unobserved(status, registry=False):
    result = {"status": status, "count": None, "entries": None}
    if registry:
        result["generation"] = None
    return result


def _omnis_acquire(lock, deadline):
    # RLock re-entry is not proof that discovery/mutation has completed.
    if not isinstance(lock, (type(threading.Lock()), type(threading.RLock()))):
        raise ValueError("invalid observation lock")
    if hasattr(lock, "_is_owned") and lock._is_owned():
        return False
    return lock.acquire(timeout=max(0.0, deadline - time.monotonic()))


def _omnis_registry_snapshot(deadline):
    module = sys.modules.get("tools.registry")
    registry = vars(module).get("registry") if module is not None else None
    if registry is None:
        return _omnis_unobserved("NOT_INITIALIZED", True)
    lock = None
    acquired = False
    try:
        state = vars(registry)
        lock = state.get("_lock")
        acquired = _omnis_acquire(lock, deadline)
        if not acquired:
            return _omnis_unobserved("NOT_OBSERVED_BUSY", True)
        tools, scopes, generation = (state.get(k) for k in ("_tools", "_scoped_tools", "_generation"))
        if type(tools) is not dict or type(scopes) is not dict or type(generation) is not int or generation < 0:
            raise ValueError("invalid registry state")
        json.dumps(generation, allow_nan=False)  # Unserializable internal state is not a snapshot.
        scoped = scopes.get("/state/active", {})
        if type(scoped) is not dict:
            raise ValueError("invalid scoped state")
        # Bound input work too; never create a giant merged copy just to reject it.
        if len(tools) > 256 or len(scoped) > 256:
            return _omnis_unobserved("LIMIT_EXCEEDED", True)
        merged = {**tools, **scoped}
        if len(merged) > 256:
            return _omnis_unobserved("LIMIT_EXCEEDED", True)
        entries = []
        for name, entry in merged.items():
            try:
                fields = vars(entry)
            except TypeError:
                # Pinned ToolEntry uses slots. Read only native member descriptors,
                # never a property, schema factory, handler or availability probe.
                descriptors = vars(type(entry))
                if any(type(descriptors.get(k)) is not types.MemberDescriptorType for k in ("name", "toolset")):
                    raise ValueError("invalid slotted entry") from None
                fields = {k: descriptors[k].__get__(entry, type(entry)) for k in ("name", "toolset")}
            toolset = fields.get("toolset")
            if not _omnis_name(name) or fields.get("name") != name or not _omnis_name(toolset):
                raise ValueError("invalid registry entry")
            entries.append({"name": name, "toolset": toolset})
        entries.sort(key=lambda row: row["name"])
        return {"status": "REGISTERED_SNAPSHOT", "generation": generation,
                "count": len(entries), "entries": entries}
    except (TypeError, ValueError, RuntimeError):
        return _omnis_unobserved("NOT_OBSERVED_INVALID", True)
    finally:
        if acquired:
            lock.release()


def _omnis_plugins_snapshot(deadline):
    module = sys.modules.get("hermes_cli.plugins")
    if module is None:
        return _omnis_unobserved("NOT_INITIALIZED")
    held = []
    try:
        fields = vars(module)
        cache = fields.get("_plugin_managers_by_home")
        if cache is None:
            return _omnis_unobserved("NOT_INITIALIZED")
        if type(cache) is not dict:
            raise ValueError("invalid manager cache")
        lock = fields.get("_plugin_managers_lock")
        if not _omnis_acquire(lock, deadline):
            return _omnis_unobserved("NOT_OBSERVED_BUSY")
        held.append(lock)
        manager = cache.get(Path("/state/active"))
        if manager is None:
            return _omnis_unobserved("NOT_INITIALIZED")
        state = vars(manager)
        lock = state.get("_discovery_lock")
        if not _omnis_acquire(lock, deadline):
            return _omnis_unobserved("NOT_OBSERVED_BUSY")
        held.append(lock)
        discovered = state.get("_discovered")
        if type(discovered) is not bool:
            raise ValueError("invalid discovery state")
        if not discovered:
            return _omnis_unobserved("NOT_OBSERVED_IN_PROGRESS")
        thread = fields.get("_background_discovery_thread")
        if thread is not None:
            if type(thread) is not threading.Thread:
                raise ValueError("invalid discovery thread")
            if thread.is_alive():
                return _omnis_unobserved("NOT_OBSERVED_IN_PROGRESS")
        # The pinned loader can abandon a still-running register() worker even
        # after discover_and_load releases its lock. Never call that complete.
        loader = sys.modules.get("hermes_cli.plugins_loader")
        if loader is not None:
            loader_state = vars(loader)
            lock = loader_state.get("_ABANDONED_LOADERS_LOCK")
            if not _omnis_acquire(lock, deadline):
                return _omnis_unobserved("NOT_OBSERVED_BUSY")
            held.append(lock)
            workers = loader_state.get("_ABANDONED_LOADERS")
            if type(workers) is not list or len(workers) > 8:
                raise ValueError("invalid loader state")
            if any(type(t) is not threading.Thread for t in workers):
                raise ValueError("invalid loader thread")
            if any(t.is_alive() for t in workers):
                return _omnis_unobserved("NOT_OBSERVED_IN_PROGRESS")
        plugins = state.get("_plugins")
        if type(plugins) is not dict:
            raise ValueError("invalid plugin state")
        if len(plugins) > 128:
            return _omnis_unobserved("LIMIT_EXCEEDED")
        entries = []
        for name, plugin in plugins.items():
            row = vars(plugin)
            if (not _omnis_name(name) or type(row.get("enabled")) is not bool
                    or type(row.get("deferred")) is not bool or "module" not in row
                    or "error" not in row
                    or (row["module"] is not None and not isinstance(row["module"], types.ModuleType))
                    or (row["error"] is not None and type(row["error"]) is not str)):
                raise ValueError("invalid plugin entry")
            entries.append({"name": name, "loaded": row["module"] is not None,
                            "enabled": row["enabled"], "deferred": row["deferred"],
                            "error_present": row["error"] is not None})
        entries.sort(key=lambda row: row["name"])
        return {"status": "PLUGIN_SNAPSHOT", "count": len(entries), "entries": entries}
    except (TypeError, ValueError, RuntimeError):
        return _omnis_unobserved("NOT_OBSERVED_INVALID")
    finally:
        for lock in reversed(held):
            lock.release()


def _omnis_bootstrap_inventory():
    """Read existing objects only. This is registered, not enabled/model-facing."""
    deadline = time.monotonic() + 0.050
    result = {
        "schema_version": 1, "observation": "NATIVE_BOOTSTRAP", "scope": "/state/active",
        "registry": _omnis_registry_snapshot(deadline),
        "plugins": _omnis_plugins_snapshot(deadline),
    }
    if len(json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")) > 24 * 1024:
        # No partial/truncated snapshot can claim completeness. Preserve absent/busy.
        if result["registry"]["status"] == "REGISTERED_SNAPSHOT":
            result["registry"] = _omnis_unobserved("LIMIT_EXCEEDED", True)
        if result["plugins"]["status"] == "PLUGIN_SNAPSHOT":
            result["plugins"] = _omnis_unobserved("LIMIT_EXCEEDED")
    return result


def main():
    # stdout is this process's JSON-RPC client channel: peer-less global broadcasts belong on it.
    server._stdio_is_rpc_channel = True
    _close_rpc_stdin_on_exec()
    if os.environ.get("HERMES_OMNIS_INERT") != "1":
        _install_sidecar_publisher()

    if os.environ.get("HERMES_OMNIS_INERT") != "1":
        # The heartbeat row lets the orphan sweep tell "live but idle" from "truly orphaned",
        # so it must start BEFORE the sweep.
        for start, what in (
                (server._start_backend_heartbeat_refresher, "backend heartbeat refresher start"),
                (server._schedule_startup_orphan_sweep, "startup orphan sweep scheduling")):
            try:
                start()
            except Exception:
                logger.warning("%s failed", what, exc_info=True)

        # Backgrounded so a dead MCP server can't freeze startup; _make_agent briefly joins it.
        ensure_mcp_discovery_started()

    # change_events: clients demote legacy polls; replay_epoch: WS restart detection.
    ready_payload = {"skin": resolve_skin(), "change_events": True, "replay_epoch": replay_epoch()}
    if os.environ.get("HERMES_OMNIS_INERT") == "1":
        ready_payload["bootstrap_inventory"] = _omnis_bootstrap_inventory()
    _write_or_exit({
        "jsonrpc": "2.0", "method": "event",
        "params": {"type": "gateway.ready", "payload": ready_payload}},
        "startup write failed (broken stdout pipe before first event)")

    if os.environ.get("HERMES_OMNIS_INERT") != "1":
        # Live-apply skins Hermes activates mid-conversation.
        server._ensure_skin_watcher()

        # Warm the /model picker's provider-models cache in this idle window (fire-and-forget).
        try:
            from hermes_cli.model_switch_providers import prewarm_picker_cache_async
            prewarm_picker_cache_async()
        except Exception:
            logger.debug("picker cache prewarm (tui) failed to start", exc_info=True)

    while True:
        raw = sys.stdin.readline()
        if not raw:
            # Spurious (child flipped O_NONBLOCK on the shared description) or genuine EOF?
            if not handle_spurious_eof(_recovery_times, _log_exit):
                break
            continue
        line = raw.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            _write_or_exit(
                {"jsonrpc": "2.0", "error": {"code": -32700, "message": "parse error"}, "id": None},
                "parse-error-response write failed (broken stdout pipe)")
            continue

        method = req.get("method") if isinstance(req, dict) else None
        try:
            resp = dispatch(req)
        except Exception as exc:
            # Pool-routed handlers already turn failures into this response; keep an
            # inline handler from taking down the stdio reader before it can reply.
            rid = req.get("id") if isinstance(req, dict) else None
            logger.exception("inline RPC handler failed for method=%r id=%r", method, rid)
            # The crash log is where "gateway exited" forensics start; a survived crash
            # must leave the same trail or the degraded reply looks like a client bug.
            _append_crash_log(
                f"inline dispatch crash · {time.strftime('%Y-%m-%d %H:%M:%S')} · method={method!r}",
                lambda f: f.write(traceback.format_exc()))
            resp = _err(rid, -32000, f"handler error: {exc}")
        if resp is not None:
            _write_or_exit(
                resp, f"response write failed for method={method!r} (broken stdout pipe)")


if __name__ == "__main__":
    main()
