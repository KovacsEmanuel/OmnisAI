"""SOURCE-only ordinary preparation scratch alias; no mounted/native proof."""

import ast
import json
import os
import shutil
import stat
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from omnis_cli.lifecycle import StartError
from omnis_cli.start import environment, validate_config
from omnis_cli.start_runtime import private_identity, settings_overlay
from omnis_cli.stop_owner import _view


@pytest.mark.parametrize("model_test", [True, False])
def test_normal_preparation_alias_and_exact_mount_attestation(
    monkeypatch: pytest.MonkeyPatch, model_test: bool
) -> None:
    from stop_owner_fixture import Fixture
    from test_start_attestation import ProductAttestationTest

    fixture = Fixture(native=True, auth=True, model_test=model_test)
    try:
        runtime = fixture.runtime
        env = environment(runtime, fixture.root, fixture.control, fixture.port)
        overlay = settings_overlay(runtime, env)
        service = overlay["services"]["runtime"]
        alias = {"type": "bind", "source": str(fixture.root / "native-ipc"), "target": "/state/tmp"}
        expected = [
            {"type": "bind", "source": str(fixture.root / "native-ipc"), "target": "/runtime"},
            {"type": "bind", "source": str(fixture.root / "provider"), "target": "/state/provider"},
        ]
        if model_test:
            expected.append(alias)
        assert service["volumes"] == expected
        assert service["read_only"] is True and service["network_mode"] == "none"
        assert service["cap_drop"] == ["ALL"]
        assert service["security_opt"] == ["no-new-privileges:true"]
        assert service["user"] == f"{os.getuid()}:{os.getgid()}"
        config = ProductAttestationTest.config(
            SimpleNamespace(
                runtime=runtime,
                env=env,
                item=lambda role: fixture.items[fixture.ids[role]],
            )
        )
        config["services"]["runtime"] = deepcopy(service)
        render = Mock(return_value=subprocess.CompletedProcess([], 0, json.dumps(config), ""))
        monkeypatch.setattr(runtime, "compose", render)
        validate_config(runtime, env)
        view = _view(runtime)
        cid = fixture.ids["runtime"]
        original = fixture.items[cid]
        assert view.attest(cid, "runtime", fixture.root, fixture.control, fixture.port) == original
        faults = (
            ["absent", "wrong-source", "extra-alias", "readonly"]
            if model_test
            else ["legacy-alias"]
        )
        for fault in faults:
            changed = deepcopy(config)
            mounts = changed["services"]["runtime"]["volumes"]
            inspected = deepcopy(original)
            observed = inspected["Mounts"]
            if fault == "absent":
                mounts.pop()
                observed[:] = [m for m in observed if m["Destination"] != "/state/tmp"]
            elif fault == "wrong-source":
                mounts[-1]["source"] = str(fixture.root / "provider")
                next(m for m in observed if m["Destination"] == "/state/tmp")["Source"] = str(
                    fixture.root / "provider"
                )
            elif fault == "readonly":
                mounts[-1]["read_only"] = True
                next(m for m in observed if m["Destination"] == "/state/tmp")["RW"] = False
            else:
                target = "/state/foreign" if model_test else "/state/tmp"
                mounts.append({**alias, "target": target})
                observed.append(
                    {
                        "Type": "bind",
                        "Source": alias["source"],
                        "Destination": target,
                        "RW": True,
                        "Propagation": "rprivate",
                    }
                )
            render.return_value.stdout = json.dumps(changed)
            with pytest.raises(StartError, match="COMPOSE_RUNTIME_INVALID"):
                validate_config(runtime, env)
            fixture.items[cid] = inspected
            with pytest.raises(StartError, match="CONTAINER_IDENTITY_MISMATCH"):
                view.attest(cid, "runtime", fixture.root, fixture.control, fixture.port)
            fixture.items[cid] = original
        assert not any(request.startswith(("POST", "DELETE")) for request in fixture.requests)
    finally:
        fixture.close()


def test_default_preparation_owner_removes_only_its_child(tmp_path: Path) -> None:
    """Exact extracted bodies; only container Path locator maps to its declared bind source."""
    from omnis_cli.lifecycle import write_record

    repository = Path(__file__).resolve().parents[2]
    source = repository / "integrations/hermes/src/omnis_hermes"
    host_tree = ast.parse((source / "runtime_host.py").read_bytes())
    private_tree = ast.parse((source / "private_paths.py").read_bytes())
    worker_tree = ast.parse((source / "native_preparation_worker.py").read_bytes())
    cls = next(n for n in host_tree.body if isinstance(n, ast.ClassDef) and n.name == "RuntimeHost")
    names = {"_preparation_home", "_remove_preparation_home"}
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    directory = next(
        n for n in private_tree.body if isinstance(n, ast.FunctionDef) and n.name == "directory"
    )
    native_env = next(
        ast.literal_eval(n.value)
        for n in host_tree.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "NATIVE_ENV" for t in n.targets)
    )
    paths = next(
        ast.literal_eval(n.value)
        for n in worker_tree.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "PATHS" for t in n.targets)
    )
    root = tmp_path / "instance"
    root.mkdir(mode=0o700)
    for leaf in ("native-ipc", "provider", "catalog"):
        (root / leaf).mkdir(mode=0o700)
    write_record(
        root / "startup.json",
        {
            "format": 4,
            "provider_identity": private_identity(root / "provider"),
            "runtime_dir_identity": private_identity(root / "native-ipc"),
            "catalog_identity": private_identity(root / "catalog"),
        },
    )
    runtime = SimpleNamespace(
        model_test=True,
        receipt=SimpleNamespace(runtime_image_id="sha256:" + "a" * 64),
        attempt="SOURCE",
    )
    mounts = settings_overlay(runtime, {"OMNIS_STATE_ROOT": str(root)})["services"]["runtime"][
        "volumes"
    ]
    scratch = Path(next(m["source"] for m in mounts if m["target"] == "/state/tmp"))
    assert scratch == root / "native-ipc"
    (scratch / "runtime.lock").touch(mode=0o600)
    write_record(scratch / "runtime.boot", {"SOURCE": "synthetic boot sentinel, not a grant"})
    before = {
        p.name: (p.stat().st_dev, p.stat().st_ino, p.stat().st_mode, p.read_bytes())
        for p in scratch.iterdir()
    }
    parent_identity = private_identity(scratch)
    selected: list[str] = []

    def mounted_path(value: str) -> Path:
        selected.append(value)
        assert value == "/state/tmp"
        return scratch

    namespace = {"Path": Path, "os": os, "stat": stat}
    exec(
        compile(
            ast.Module(body=[directory], type_ignores=[]), str(source / "private_paths.py"), "exec"
        ),
        namespace,
    )
    namespace.update(
        Path=mounted_path,
        private_paths=SimpleNamespace(directory=namespace["directory"]),
        uuid4=uuid4,
        NATIVE_ENV=native_env,
        PATHS=paths,
        shutil=shutil,
    )
    exec(
        compile(ast.Module(body=methods, type_ignores=[]), str(source / "runtime_host.py"), "exec"),
        namespace,
    )
    subject = SimpleNamespace(preparation_spec=None, preparation_root=None)
    scratch.chmod(0o755)
    with pytest.raises(ValueError, match="Private directory required"):
        namespace["_preparation_home"](subject)
    scratch.chmod(0o700)
    child, env = namespace["_preparation_home"](subject)
    assert selected == ["/state/tmp", "/state/tmp"]
    assert child.parent == scratch and child.name.startswith("native-prep-")
    assert Path(env["TMPDIR"]).is_relative_to(child)
    (child / "work" / "readonly-record").write_text("SOURCE staged document")
    (child / "work").chmod(0o500)
    child.chmod(0o500)
    namespace["_remove_preparation_home"](subject)
    assert subject.preparation_root is None and not child.exists()
    assert private_identity(scratch) == parent_identity
    assert {
        p.name: (p.stat().st_dev, p.stat().st_ino, p.stat().st_mode, p.read_bytes())
        for p in scratch.iterdir()
    } == before
    leftover = scratch / "native-prep-unowned"
    leftover.mkdir(mode=0o700)
    with pytest.raises(ValueError, match="Preparation crash leftover"):
        namespace["_preparation_home"](subject)
    leftover.rmdir()
    assert "omnis_hermes.runtime_host" not in sys.modules
