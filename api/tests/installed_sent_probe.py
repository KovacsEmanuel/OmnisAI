"""Test-only process cut; normal installed API bytes, no provider transport."""

import os
import shutil
import subprocess
from pathlib import Path
from zipfile import ZipFile


def install_probe_wheel(root: Path) -> Path:
    """Use the migration probe's locked/offline wheel installation pattern."""
    uv = os.environ.get("OMNIS_UV") or os.environ.get("UV") or shutil.which("uv")
    assert uv is not None, "Pinned uv must be available"
    api = Path(__file__).resolve().parents[1]
    wheels, requirements = root / "wheels", root / "requirements.txt"
    wheels.mkdir()
    python = root / "venv/bin/python"
    commands = (
        ["build", "--wheel", str(api), "--out-dir", str(wheels)],
        [
            "export",
            "--locked",
            "--directory",
            str(api),
            "--no-dev",
            "--no-emit-project",
            "--format",
            "requirements-txt",
            "--output-file",
            str(requirements),
        ],
        ["venv", "--no-python-downloads", "--python", "3.13.15", str(root / "venv")],
        ["pip", "sync", "--python", str(python), "--require-hashes", str(requirements)],
        [
            "pip",
            "install",
            "--python",
            str(python),
            "--no-deps",
            str(wheels / "omnis_api-0.1.1-py3-none-any.whl"),
        ],
        ["pip", "check", "--python", str(python)],
    )
    for command in commands:
        result = subprocess.run(
            [uv, "--offline", "--no-config", *command],
            cwd=root,
            env={name: os.environ[name] for name in ("PATH", "HOME", "TMPDIR")},
            capture_output=True,
            timeout=120,
        )
        assert result.returncode == 0, f"Offline wheel {command[0]} failed: {result.returncode}"
    with ZipFile(wheels / "omnis_api-0.1.1-py3-none-any.whl") as wheel:
        modules = {
            name for name in wheel.namelist() if name.startswith("omnis/") and name.endswith(".py")
        }
        assert modules == {
            str(p.relative_to(api / "src")) for p in (api / "src/omnis").rglob("*.py")
        }
        assert all(wheel.read(name) == (api / "src" / name).read_bytes() for name in modules)
    return python


# shortcut: metadata is synthetic and the cut precedes SDK entry; live transport needs separate consent.
PROBE = r"""
import asyncio
import hashlib
import importlib
import json
import os
from pathlib import Path
import signal
import socket
import sys
import sysconfig
from unittest.mock import patch
from uuid import uuid4

from omnis.core.db import database_engine
from omnis.modules.instance.service import InstanceService
from omnis.modules.runs.model_test_models import ModelTestControl
from omnis.modules.runs.model_test_runtime import ApiKeyModelTest
from omnis.modules.runs.model_test_store import ModelConflict
from omnis.modules.settings.provider_key_models import KeySettingsControl
from omnis.modules.settings.provider_key_service import ProviderSettingsOwner
from omnis.modules.settings.provider_vault import ProviderVault
from omnis.supervisor.model_sender import ModelSender

config = json.loads(sys.stdin.buffer.read())
mode = config["mode"]
package = Path(sysconfig.get_path("purelib")) / "omnis"
assert package.is_relative_to(Path(sys.prefix))
assert {
    str(p.relative_to(package.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in package.rglob("*.py")
} == config["modules"]
for name in (
    "core.db", "modules.instance.service", "modules.runs.model_test_runtime",
    "modules.runs.model_test_store", "modules.settings.provider_key_service",
    "modules.settings.provider_vault", "supervisor.model_sender", "supervisor.model_relay",
):
    module = importlib.import_module("omnis." + name)
    assert Path(module.__file__).resolve() == package / (name.replace(".", "/") + ".py")
print(json.dumps({"stage": "installed", "pid": os.getpid(), "prefix": sys.prefix}), flush=True)

# The test never permits DNS or an IP socket, even if the send-entry tripwire regresses.
def no_network(event, args):
    if event.startswith("socket.getaddrinfo") or (
        event == "socket.__new__" and args[1] != socket.AF_UNIX
    ):
        os._exit(81)
sys.addaudithook(no_network)

def sender_entry(code, offset):
    if code is ModelSender.send.__code__:
        if mode == "produce":
            print(json.dumps({"stage": "send_entry"}), flush=True)
            os.kill(os.getpid(), signal.SIGKILL)
        print(json.dumps({"stage": "send_denied"}), flush=True)
        os._exit(79)
    if code is ModelSender.metadata.__code__:
        os._exit(80)

monitor = sys.monitoring.PROFILER_ID
sys.monitoring.use_tool_id(monitor, "installed-sent-cut")
sys.monitoring.register_callback(monitor, sys.monitoring.events.PY_START, sender_entry)
for code in (ModelSender.send.__code__, ModelSender.metadata.__code__):
    sys.monitoring.set_local_events(monitor, code, sys.monitoring.events.PY_START)

async def main():
    sender = ModelSender(Path(config["socket"]))
    if mode == "deny_send":
        # Enter the actual method; the tripwire must fire before arguments or SDK are used.
        await sender.send(None, None, None, None)
        raise AssertionError("send tripwire missed")
    if mode == "origin":
        await sender.close()
        return
    engine = database_engine(config["database"])
    service = InstanceService(engine)
    owner = uuid4()
    epoch = await service.acquire(owner)
    status = await service.owned_status(owner, epoch)
    settings = ProviderSettingsOwner(
        service, owner, epoch,
        ProviderVault(Path(config["vault"]), Path(config["keys"]), str(status.instance_id)),
    )
    runtime = ApiKeyModelTest(settings, sender)
    start = ModelTestControl(
        op="model_test", action="start", operation_id=config["operation"],
        expected_selection_revision=1, consent=True,
    )
    refresh = ModelTestControl(
        op="model_test", action="refresh", command_id=config["refresh"],
        expected_selection_revision=1,
    )
    try:
        if mode == "produce":
            await service.open(uuid4(), status.generation, owner, epoch)
            connection = str(uuid4())
            for request in (
                {
                    "action": "save_connection", "command_id": str(uuid4()),
                    "connection_id": connection, "expected_revision": 0,
                    "provider": "openrouter", "secret": "synthetic-not-provider-key",
                },
                {
                    "action": "save_selection", "command_id": str(uuid4()),
                    "expected_revision": 0,
                    "default": {"connection_id": connection, "connection_revision": 1,
                                "model": "fixture/model", "output_tokens": 64},
                    "brain": None, "investigator": None, "validator": None,
                },
            ):
                if request["action"] == "save_selection":
                    from omnis.modules.settings.provider_model_models import ModelRegistryControl
                    await settings.handle(ModelRegistryControl.model_validate({"op": "provider_models", "request": {
                        "action": "save_models", "command_id": str(uuid4()), "expected_registry_revision": 0,
                        "connection_id": connection, "connection_revision": 1,
                        "models": [{"entry_id": str(uuid4()), "expected_revision": 0, "model": "fixture/model", "output_tokens": 128}],
                    }}))
                await settings.handle(KeySettingsControl.model_validate({"op": "provider_settings", "request": request}))
            try:
                await runtime.handle(start)
            except ModelConflict as error:
                assert error.code == "CAPABILITIES_REQUIRED"
            else:
                raise AssertionError("start admitted before refresh")

            async def synthetic_metadata(endpoint, secret, guard):
                assert endpoint == "https://openrouter.ai/api/v1"
                assert secret == "synthetic-not-provider-key"
                async with guard():
                    return {"data": [{"id": "fixture/model", "supported_parameters": ["max_tokens"],
                                      "top_provider": {"max_completion_tokens": 128}}]}

            with patch.object(sender, "metadata", synthetic_metadata):
                await runtime.handle(refresh)
                async with asyncio.timeout(5):
                    while runtime.tasks:
                        await asyncio.sleep(0.01)
            assert not runtime.settlement_failed
            receipt = await runtime.handle(ModelTestControl(op="model_test", action="read", command_id=config["refresh"]))
            assert receipt["metadata_state"] == "READY"
            print(json.dumps({"stage": "ready", "receipt": receipt, "owner": str(owner), "epoch": epoch}), flush=True)
            await runtime.handle(start)
            async with asyncio.timeout(5):
                while runtime.tasks:
                    await asyncio.sleep(0.01)
            raise AssertionError("process survived the SENT cut")
        assert mode == "recover"
        assert not status.admission_open
        await runtime.reconcile()
        view = await runtime.handle(ModelTestControl(op="model_test", action="read", operation_id=config["operation"]))
        assert view["state"] == "FINISHED" and view["state_revision"] == 3
        assert view["result_state"] == "UNKNOWN"
        assert view["reason"] == view["finish_reason"] == "OWNER_LOST"
        assert view["usage_state"] == "UNKNOWN" and view["output_state"] == "ABSENT"
        for field in ("cost_observed", "input_tokens", "output_tokens", "reasoning_tokens", "observed_model", "response_text", "provider_status"):
            assert view[field] is None
        assert await runtime.handle(start) == view
        assert await runtime.handle(refresh) == config["receipt"]
        assert await runtime.handle(ModelTestControl(op="model_test", action="read", command_id=config["refresh"])) == config["receipt"]
        try:
            await runtime.handle(start.model_copy(update={"expected_selection_revision": 2}))
        except ModelConflict as error:
            assert error.code == "COMMAND_CONFLICT"
        else:
            raise AssertionError("changed replay accepted")
        await runtime.reconcile()
        assert await runtime.handle(start) == view
        assert not runtime.tasks and not runtime.settlement_failed
        print(json.dumps({"stage": "recovered", "view": view, "owner": str(owner), "epoch": epoch}), flush=True)
    finally:
        await sender.close()
        await service.release(owner, epoch)
        await engine.dispose()
asyncio.run(main())
"""
