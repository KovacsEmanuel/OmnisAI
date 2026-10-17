"""Real process controls for the test harness, without a DB or product traffic."""

import os
import signal
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import URL

from e2e_processes import OwnedChildren, cleanup_all, owned_children, subreaper_state


def test_real_e2e_consumer_retains_first_driver_error_and_separate_cleanup_failure(
    family: OwnedChildren, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Synthetic Popen controls reach the installed pytest consumer; no DB/browser."""
    import test_web_e2e as consumer

    root = tmp_path / "root"
    (root / "web/dist").mkdir(parents=True)
    (root / "web/dist/omnis-web.json").write_text("synthetic sentinel")
    monkeypatch.setattr(consumer, "ROOT", root)
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    original_popen = subprocess.Popen
    processes: list[subprocess.Popen[str]] = []

    def synthetic_service(*, stubborn: bool) -> subprocess.Popen[str]:
        handler = "signal.SIG_IGN" if stubborn else "lambda *_: sys.exit(0)"
        script = (
            "import signal,sys,time; "
            f"signal.signal(signal.SIGTERM,{handler}); "
            "print('READY',flush=True); time.sleep(60)"
        )
        process = original_popen(
            [sys.executable, "-u", "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        processes.append(process)
        assert process.stdout is not None and process.stdout.readline().strip() == "READY"
        return process

    monkeypatch.setattr(consumer, "start_supervisor", lambda *_: synthetic_service(stubborn=False))
    monkeypatch.setattr(
        consumer, "launch_api", lambda *_, own_source=False: synthetic_service(stubborn=True)
    )
    monkeypatch.setattr(consumer, "wait_ready", lambda *_: None)
    monkeypatch.setattr(consumer, "wait_api", lambda *_: None)

    class SyntheticAssetClient:
        def __init__(self, *, base_url: str, trust_env: bool, timeout: int) -> None:
            assert base_url.startswith("http://127.0.0.1:") and not trust_env and timeout == 3

        def __enter__(self) -> "SyntheticAssetClient":
            return self

        def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
            pass

        def get(self, path: str) -> SimpleNamespace:
            assert path == "/"
            return SimpleNamespace(status_code=200)

    # This unit controls only teardown; the real browser/asset path runs in the private DB gate.
    monkeypatch.setattr(consumer, "httpx", SimpleNamespace(Client=SyntheticAssetClient))

    def driver(command: list[str], **kwargs: object) -> subprocess.Popen[str]:
        assert command[0] == "node"
        cwd, env, pass_fds = kwargs.get("cwd"), kwargs.get("env"), kwargs.get("pass_fds")
        assert isinstance(cwd, Path)
        assert isinstance(env, dict) and all(
            isinstance(k, str) and isinstance(v, str) for k, v in env.items()
        )
        assert isinstance(pass_fds, tuple) and all(isinstance(fd, int) for fd in pass_fds)
        process = original_popen(
            [
                sys.executable,
                "-c",
                "import sys; sys.stderr.write('page.goto: Timeout 30000ms exceeded\\n'); sys.exit(1)",
            ],
            cwd=cwd,
            env=env,
            pass_fds=pass_fds,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        processes.append(process)
        return process

    class DriverProxy:
        def __getitem__(self, key: object) -> type[subprocess.Popen[str]]:
            return subprocess.Popen

        def __call__(self, command: list[str], **kwargs: object) -> subprocess.Popen[str]:
            return driver(command, **kwargs)

    monkeypatch.setattr(
        consumer, "subprocess", SimpleNamespace(Popen=DriverProxy(), PIPE=subprocess.PIPE)
    )
    try:
        with pytest.raises(ExceptionGroup) as failure:
            consumer.test_built_web_against_real_control_plane(
                URL.create("postgresql+psycopg", database="unused"),
                tmp_path,
                family,
                "b04",
                monkeypatch,
            )
        reasons = [str(error) for error in failure.value.exceptions]
        assert any("page.goto: Timeout 30000ms exceeded" in reason for reason in reasons), reasons
        assert any("-9" in reason and "cleanup" in reason.lower() for reason in reasons), reasons
        assert all(process.poll() is not None for process in processes)
        assert not (tmp_path / "omnis-p03-e2e/b04/result.json").exists()
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=3)


@pytest.fixture
def family() -> Iterator[OwnedChildren]:
    previous = subreaper_state()
    with owned_children() as owner:
        yield owner
    assert subreaper_state() == previous


def test_cleanup_reaps_every_owned_process_even_if_api_exits_unexpectedly(
    family: OwnedChildren,
) -> None:
    api = subprocess.Popen(
        [sys.executable, "-c", "raise SystemExit(1)"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    supervisor = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-c",
            "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('READY'); time.sleep(60)",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert supervisor.stdout is not None and supervisor.stdout.readline().strip() == "READY"
        api.wait(timeout=3)
        outputs = cleanup_all([(api, False), (supervisor, False)], grace=0.1, ownership=family)
        assert len(outputs) == 2
        assert api.returncode == 1
        assert supervisor.returncode == -signal.SIGKILL
    finally:
        for process in (api, supervisor):
            if process.poll() is None:
                process.kill()
            process.wait(timeout=3)


def test_cleanup_kills_an_owned_driver_descendant_in_a_separate_session(
    family: OwnedChildren,
) -> None:
    script = """
import subprocess, sys, time
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
print(child.pid, flush=True)
time.sleep(60)
"""
    driver = subprocess.Popen(
        [sys.executable, "-u", "-c", script],
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    child_pid = None
    try:
        assert driver.stdout is not None
        child_pid = int(driver.stdout.readline().strip())
        cleanup_all([(driver, True)], grace=0.1, ownership=family)
        try:
            with open(f"/proc/{child_pid}/stat") as source:
                state = source.read().split(") ", 1)[1].split()[0]
            # proc_pid_stat(5): X is the transient dead state during reaping, not a live process.
            assert state in {"Z", "X"}, "Owned descendant is still running"
        except FileNotFoundError:
            pass
    finally:
        if driver.poll() is None:
            driver.kill()
        driver.wait(timeout=3)
        if child_pid is not None:
            try:
                os.kill(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_adoption_cleanup_preserves_preexisting_children_and_restores_attribute() -> None:
    before = subreaper_state()
    existing = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        with owned_children() as owner:
            spawned = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
            owner.cleanup(grace=0.1)
            assert spawned.poll() is not None
            assert existing.poll() is None
        assert subreaper_state() == before
    finally:
        existing.terminate()
        existing.wait(timeout=3)


@pytest.mark.parametrize("driver_kind", ["python", "node"])
def test_cleanup_tracks_detached_child_after_driver_already_exited(
    family: OwnedChildren,
    driver_kind: str,
) -> None:
    script = """
import subprocess, sys
child = subprocess.Popen([sys.executable, '-u', '-c',
    "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print('READY'); time.sleep(60)"],
    start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
assert child.stdout.readline().strip() == b'READY'
print(child.pid, flush=True)
raise SystemExit(1)
"""
    command = [sys.executable, "-u", "-c", script]
    if driver_kind == "node":
        command = [
            "node",
            "-e",
            """
const { spawn } = require('node:child_process');
const child = spawn(process.argv[1], ['-u', '-c',
    "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print('READY'); time.sleep(60)"],
    { detached: true, stdio: ['ignore', 'pipe', 'ignore'] });
child.stdout.once('data', () => { console.log(child.pid); process.exit(1); });
""",
            sys.executable,
        ]
    driver = subprocess.Popen(
        command,
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    child_pid = None
    try:
        stdout, _ = driver.communicate(timeout=3)
        child_pid = int(stdout.strip())
        assert driver.returncode == 1
        cleanup_all([(driver, True)], grace=0.1, ownership=family)
        try:
            with open(f"/proc/{child_pid}/stat") as source:
                state = source.read().split(") ", 1)[1].split()[0]
            assert state in {"Z", "X"}, "Early-exit driver lost its detached child"
        except FileNotFoundError:
            pass
    finally:
        if driver.poll() is None:
            driver.kill()
        driver.wait(timeout=3)
        if child_pid is not None:
            try:
                os.kill(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
