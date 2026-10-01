"""Opt-in acceptance of the actual installed console command, never run_probe."""

import json
import os
import select
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from installed_pair_open import command, opener_outcome, prove, tty_default, tty_pair
from omnis_cli.control import request
from omnis_cli.lifecycle import process_identity, write_record
from omnis_cli.start_runtime import ControlRuntime


def save_probe(state, data, project, root, record, *, probe, cleanup):
    path = state / "probe-receipt.json"
    write_record(
        path,
        {
            "project": project,
            "state_root": str(root),
            "data_home": str(data),
            "record": record,
            "probe": probe,
            "cleanup": cleanup,
        },
        replace=path.exists(),
    )
    print(f"INSTALLED_START_LOCATOR {path}", flush=True)


def resource_snapshot(runtime, root, control, port):
    result = {}
    for cid in runtime.ids():
        item = runtime.inspect("container", cid)
        role = item["Config"]["Labels"]["com.docker.compose.service"]
        runtime.attest(cid, role, root, control, port)
        result[cid] = {key: item["State"][key] for key in ("Running", "StartedAt", "FinishedAt")}
        result[cid]["RestartCount"] = item["RestartCount"]
    return result


class ForwarderObservation:
    """Test-only pins captured from a verified direct child, never a journal PID."""

    def __init__(self, root, port, parent):
        self.root, self.port, self.parent = root, port, parent
        self.pins = {}
        self.inodes = set()

    def pin(self, pid):
        if pid in self.pins:
            return
        pin = os.pidfd_open(pid)
        try:
            identity = process_identity(pid)
            details = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
            assert int(details[1]) == self.parent, "Unowned forwarder parent"
            assert identity["argv"][1:] == [
                "-I",
                "-m",
                "omnis_cli.forwarder",
                "--socket-dir",
                str(self.root / "http"),
                "--port",
                str(self.port),
            ], "Unowned forwarder argv"
            self.pins[pid] = pin
        except BaseException:
            os.close(pin)
            raise

    def discover(self):
        # The installed CLI creates only Docker clients and its one forwarder.
        for word in Path(f"/proc/{self.parent}/task/{self.parent}/children").read_text().split():
            pid = int(word)
            argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
            if b"omnis_cli.forwarder" in argv:
                self.pin(pid)
        self.snapshot_listener()

    def snapshot_listener(self):
        owned = set()
        for pid, pin in self.pins.items():
            if not select.select([pin], [], [], 0)[0]:
                for fd in Path(f"/proc/{pid}/fd").iterdir():
                    try:
                        link = os.readlink(fd)
                    except FileNotFoundError:
                        continue
                    if link.startswith("socket:["):
                        owned.add(int(link[8:-1]))
        for table in ("tcp", "tcp6"):
            for row in Path(f"/proc/net/{table}").read_text().splitlines()[1:]:
                fields = row.split()
                if fields[3] == "0A" and int(fields[9]) in owned:
                    self.inodes.add(int(fields[9]))

    def assert_absent(self):
        problems = []
        for pid, pin in self.pins.items():
            if not select.select([pin], [], [], 0)[0]:
                problems.append(f"forwarder {pid} alive")
        for table in ("tcp", "tcp6"):
            for row in Path(f"/proc/net/{table}").read_text().splitlines()[1:]:
                fields = row.split()
                if fields[3] == "0A" and (
                    int(fields[9]) in self.inodes or int(fields[1].split(":")[1], 16) == self.port
                ):
                    problems.append("forwarder listener alive")
        assert not problems, f"Claimed cleanup left {problems}"

    def close(self):
        for pin in self.pins.values():
            os.close(pin)
        self.pins.clear()

    def rescue(self):
        """Observer-only safety net after failed readback; never a product PASS."""
        problems = []
        for pid, pin in self.pins.items():
            try:
                if not select.select([pin], [], [], 0)[0]:
                    signal.pidfd_send_signal(pin, signal.SIGTERM)
                    if not select.select([pin], [], [], 2)[0]:
                        signal.pidfd_send_signal(pin, signal.SIGKILL)
                    if not select.select([pin], [], [], 3)[0]:
                        problems.append(f"forwarder {pid} rescue incomplete")
            except OSError as error:
                problems.append(f"forwarder {pid} rescue {type(error).__name__}")
        try:
            self.assert_absent()
        except (AssertionError, OSError) as error:
            problems.append(str(error))
        assert not problems, f"Observer rescue uncertain: {problems}"


def assert_resources_absent(runtime, root, control, record, *, observer=None):
    if observer is not None:
        observer.assert_absent()
    assert runtime.ids() == [], "Claimed cleanup left containers"
    assert runtime.network(set()) is None, "Claimed cleanup left network"
    for cid in record.get("containers", {}).values():
        assert runtime.inspect("container", cid) is None, "Claimed cleanup left exact CID"
    for path in (root / "http/api.sock", control / "control.sock", control / "control.cap"):
        assert not os.path.lexists(path), "Claimed cleanup left IPC"


def teardown(runtime, root, control, port, record, *, uncertain=False):
    """Test-owned teardown, not an implementation or acceptance of omnis stop."""
    if (
        uncertain
        or runtime.uncertain
        or not runtime.family_drained
        or record.get("phase") == "UNCERTAIN"
    ):
        raise AssertionError("Unreconciled daemon/writers: retain DB and recovery locator")
    runtime.deadline = time.monotonic() + 110
    runtime.attempt = record["attempt"]
    if record.get("phase") == "FAILED_CLEANED":
        assert record.get("cleanup") == []
        assert_resources_absent(runtime, root, control, record)
        return
    problems = []
    if record.get("forwarder"):
        identity = record["forwarder"]
        try:
            pidfd = os.pidfd_open(identity["pid"])
            try:
                assert process_identity(identity["pid"]) == identity
                signal.pidfd_send_signal(pidfd, signal.SIGTERM)
                assert select.select([pidfd], [], [], 25)[0], "forwarder survived"
            finally:
                os.close(pidfd)
        except (OSError, AssertionError, ValueError):
            problems.append("forwarder")
    # Attest every CID independently; never stop a DB under surviving writers.
    rows = []
    for cid in runtime.ids():
        try:
            item = runtime.inspect("container", cid)
            role = item["Config"]["Labels"]["com.docker.compose.service"]
            runtime.attest(cid, role, root, control, port)
            rows.append((role, cid))
        except (OSError, AssertionError, ValueError, KeyError):
            problems.append("identity")
    for role, cid in sorted(rows, key=lambda pair: pair[0] == "db"):
        if role == "db" and problems:
            continue
        try:
            runtime.attest(cid, role, root, control, port)
            runtime.run("stop", "--time", "15", cid, cap=25, effect=True)
            stopped = runtime.inspect("container", cid)
            assert stopped["State"]["Running"] is False
            runtime.run("container", "rm", cid, effect=True)
            assert runtime.inspect("container", cid) is None
        except (OSError, AssertionError, ValueError):
            problems.append("container cleanup")
    if not runtime.ids():
        net = runtime.network(set())
        if net:
            runtime.run("network", "rm", net, effect=True)
        assert runtime.network(set()) is None
    else:
        problems.append("containers remain")
    for name in (root / "http/api.sock", control / "control.sock", control / "control.cap"):
        if os.path.lexists(name):
            problems.append("IPC remains")
    if record.get("listener_inode"):
        for table in ("tcp", "tcp6"):
            for row in Path(f"/proc/net/{table}").read_text().splitlines()[1:]:
                if row.split()[3] == "0A" and row.split()[9] == str(record["listener_inode"]):
                    problems.append("listener remains")
    assert (root / "postgres").is_dir(), "data must be retained"
    assert not problems, f"Owned teardown uncertain: {problems}"
    print(
        f"INSTALLED_START_CLEANUP project={runtime.receipt.project} data_retained={root}",
        flush=True,
    )


def run_reused_default(cli, cwd, env, port, *, on_joined=None):
    """Observe the installed reused implicit command, not just its READY prefix."""
    result = subprocess.run([cli], cwd=cwd, env=env, capture_output=True, text=True, timeout=50)
    if result.returncode in {0, 2, 3} and on_joined is not None:
        on_joined()
    opener_outcome(result.returncode, result.stdout, f"http://127.0.0.1:{port}", result.stderr)
    return result


def run_installed_start(data, receipt, scratch, cli, *, pair_open=False):
    state = Path(tempfile.mkdtemp(prefix="s2-", dir=os.environ["TMPDIR"]))
    root, control = state / "s/omnis", state / "r/omnis"
    cwd = state / "cwd"
    cwd.mkdir(mode=0o700)
    (cwd / ".env").write_text("OMNIS_DATABASE_URL=synthetic-cwd-secret\nOMNIS_HTTP_PORT=1\n")
    (cwd / "compose.yaml").write_text("invalid: must-not-be-used\n")
    (cwd / "config.toml").write_text("invalid configuration trap")
    (cwd / "docker").write_text("#!/bin/sh\nexit 97\n")
    (cwd / "docker").chmod(0o700)
    env = {
        "PATH": f"{cwd}:/usr/bin:/bin",
        "HOME": str(state),
        "XDG_DATA_HOME": str(data),
        "XDG_STATE_HOME": str(state / "s"),
        "XDG_RUNTIME_DIR": str(state / "r"),
    }
    with socket.socket() as selected:
        # No-subcommand omnis has the documented default 8765 until M22;
        # an occupied default is a precondition conflict, not a test rebind.
        selected.bind(("127.0.0.1", 8765 if pair_open else 0))
        port = selected.getsockname()[1]
    runtime = ControlRuntime(data, time.monotonic() + 30)
    assert runtime.receipt.image_id == receipt["image_id"]
    record = {}
    probe_ok = cleanup_ok = driver_uncertain = False
    browser_outcome = None
    save_probe(state, data, receipt["project"], root, record, probe="PREPARED", cleanup="NOT_RUN")
    outputs = []
    sink = socket.socket()
    sink.bind(("127.0.0.1", 0))
    sink.listen(8)
    sentinel = f"http://127.0.0.1:{sink.getsockname()[1]}"
    env.update(
        HTTP_PROXY=sentinel,
        HTTPS_PROXY=sentinel,
        ALL_PROXY=sentinel,
        OPENAI_BASE_URL=sentinel,
        OPENAI_API_KEY="synthetic-sl02-provider-marker",
    )

    def invoke(args, expected=0, override=None):
        nonlocal driver_uncertain
        prior_uncertainty = driver_uncertain
        driver_uncertain = True
        p = subprocess.run(
            [cli, *args],
            cwd=cwd,
            env=override or env,
            capture_output=True,
            text=True,
            timeout=330,
        )
        outputs.append(p.stdout + p.stderr)
        assert p.returncode == expected, (
            f"Installed command exit={p.returncode}, expected={expected}: {p.stdout}"
        )
        result = json.loads(p.stdout)
        driver_uncertain = prior_uncertainty
        return result

    def snapshot():
        result = {}
        runtime.deadline = time.monotonic() + 30
        for role, cid in record["containers"].items():
            item = runtime.attest(cid, role, root, control, port)
            result[cid] = (item["State"]["StartedAt"], item["RestartCount"])
            assert item["State"]["Running"] is True
        return result

    try:
        # Preflight refusals use the installed command and restore only our synthetic artifacts.
        asset = data / "omnis/releases/0.1.0/web/index.html"
        original_asset = asset.read_bytes()
        asset.write_bytes(b"synthetic corrupted release asset")
        try:
            denied = invoke(["start", "--no-open", "--json"], 2)
            assert denied["reason"] == "RELEASE_OR_IMAGE_INVALID"
            assert not root.exists()
        finally:
            asset.write_bytes(original_asset)
        image_path = data / "omnis/image.json"
        original_receipt = image_path.read_bytes()
        for field, value, reason in (
            ("docker_id", "00000000-0000-0000-0000-000000000000", "DOCKER_IDENTITY_MISMATCH"),
            ("image_id", "sha256:" + "0" * 64, "IMAGE_REQUIRED"),
        ):
            changed = json.loads(original_receipt)
            changed[field] = value
            image_path.write_text(json.dumps(changed))
            try:
                assert invoke(["start", "--no-open", "--json"], 2)["reason"] == reason
                assert not root.exists()
            finally:
                image_path.write_bytes(original_receipt)
        assert (
            invoke(["start", "--no-open", "--json"], 2, {**env, "XDG_STATE_HOME": "relative-trap"})[
                "reason"
            ]
            == "PRIVATE_PATH_INVALID"
        )
        # Test bound-only and LISTEN conflicts on the product command before provisioning.
        for listen in (False, True):
            with socket.socket() as foreign:
                foreign.bind(("127.0.0.1", 0))
                if listen:
                    foreign.listen(1)
                occupied = foreign.getsockname()[1]
                denied = invoke(["start", "--no-open", "--port", str(occupied), "--json"], 2)
                assert denied["reason"] == "PORT_CONFLICT"
                assert not (root / "startup.json").exists()
                assert not runtime.ids()
        initial_code = initial_public = None

        def joined_implicit_cli():
            nonlocal driver_uncertain
            driver_uncertain = runtime.uncertain or not runtime.family_drained

        if pair_open:
            # Exercise the actual no-subcommand console entry on a NEW instance.
            # An unavailable desktop affects opener exit, never startup readiness.
            driver_uncertain = True
            initial_code, initial_public, _ = tty_default(
                cli, cwd, env, port, on_joined=joined_implicit_cli
            )
            outputs.append(initial_public)  # Never persist the captured code.
            assert (root / "startup.json").exists()
        # Two fresh concurrent console commands, not two calls to an in-process harness.
        driver_uncertain = True
        processes = [
            subprocess.Popen(
                [cli, "start", "--no-open", "--port", str(port), "--json"],
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for _ in range(2)
        ]
        replies = []
        try:
            for p in processes:
                out, err = p.communicate(timeout=330)
                outputs.append(out + err)
                assert p.returncode == 0, f"Concurrent installed start: exit={p.returncode}: {out}"
                replies.append(json.loads(out))
        finally:
            for p in processes:
                if p.poll() is None:
                    p.terminate()
                    try:
                        p.wait(timeout=125)
                    except subprocess.TimeoutExpired:
                        driver_uncertain = True
                        raise
                if p.returncode not in {0, 2, 3}:
                    driver_uncertain = True
        if all(p.returncode in {0, 2, 3} for p in processes):
            driver_uncertain = False  # All direct CLI outcomes settled; assertions can still fail.
        assert {r["reused"] for r in replies} == ({True} if pair_open else {False, True})
        assert len({r["instance_id"] for r in replies}) == 1
        assert all(
            r["dashboard_ready"] and r["assessment_ready"] is False and r["browser_opened"] is False
            for r in replies
        )
        record = json.loads((root / "startup.json").read_text())
        assert set(record["containers"]) == {"db", "api", "supervisor"}
        if pair_open:
            assert initial_code is not None and initial_public is not None
            assert f"Omnis READY: http://127.0.0.1:{port}/" in initial_public
        runtime.attempt = record["attempt"]
        before = snapshot()
        driver_uncertain = False
        metadata_before = {
            str(p): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in (root / "startup.json", root / "instance.json", data / "omnis/image.json")
        }
        status = invoke(["status", "--json"])
        assert status["instance_id"] == record["instance_id"] and status["dashboard_ready"]
        assert metadata_before == {
            p: (Path(p).read_bytes(), Path(p).stat().st_mtime_ns) for p in metadata_before
        }
        repeated = invoke(["start", "--no-open", "--json"])
        assert repeated["reused"] is True
        assert snapshot() == before
        if pair_open:
            driver_uncertain = True
            default_reuse = run_reused_default(cli, cwd, env, port, on_joined=joined_implicit_cli)
            outputs.append(default_reuse.stdout + default_reuse.stderr)
            assert snapshot() == before
        assert status["generation"] == repeated["generation"] == 1
        assert status["supervisor_epoch"] == repeated["supervisor_epoch"] == 1
        assert not status["assessment_ready"] and not status["browser_opened"]
        assert runtime.psql(
            record["containers"]["db"], "SELECT count(*) FROM pairing_issuance"
        ) == ("1" if pair_open else "0")
        assert (
            runtime.psql(record["containers"]["db"], "SELECT count(*) FROM instance_command") == "1"
        )
        if pair_open:
            # Until the installed child and browser return, never promote teardown
            # after a timeout or an unknown process-family outcome.
            driver_uncertain = True
            try:
                browser_outcome = prove(
                    cli, cwd, env, root, control, record, runtime, port, outputs, initial_code
                )
            except AssertionError:
                # Every assertion in the observer follows a joined CLI/browser
                # child; timeouts, I/O faults and missing close receipts do not.
                driver_uncertain = runtime.uncertain or not runtime.family_drained
                raise
            driver_uncertain = False
            assert snapshot() == before
        # A stale crash/start intent cannot adopt even otherwise healthy resources.
        journal = root / "startup.json"
        original_journal = journal.read_bytes()
        stale = json.loads(original_journal)
        stale["phase"] = "VERIFYING"
        journal.write_text(json.dumps(stale))
        try:
            assert invoke(["start", "--no-open", "--json"], 4)["reason"] == "RECOVERY_REQUIRED"
            if pair_open:
                assert "RECOVERY_REQUIRED" in (tty_pair(cli, cwd, env, expected=4) or "")
                assert "RECOVERY_REQUIRED" in command(cli, ["open"], cwd, env, expected=4)[1]
            assert snapshot() == before
        finally:
            journal.write_bytes(original_journal)
        if pair_open:
            # Mutate the same installed READY receipt channel consumed by all
            # four product commands, not an in-memory parser substitute.
            db = record["containers"]["db"]
            issuance_before = runtime.psql(db, "SELECT count(*) FROM pairing_issuance")
            for label, change in (
                ("format-bool", {"format": True}),
                ("generation-bool", {"generation": True}),
                ("epoch-bool", {"supervisor_epoch": True}),
                ("unknown-field", {"ignored_admin": "synthetic-marker"}),
                ("socket-bool", {"api_socket": [True, 123]}),
                ("socket-length", {"control_socket": [2049]}),
            ):
                changed = json.loads(original_journal)
                changed.update(change)
                journal.write_text(json.dumps(changed))
                try:
                    assert (
                        invoke(["start", "--no-open", "--json"], 4)["reason"] == "RECOVERY_REQUIRED"
                    ), label
                    assert invoke(["status", "--json"], 4)["reason"] == "RECOVERY_REQUIRED", label
                    assert "RECOVERY_REQUIRED" in (tty_pair(cli, cwd, env, expected=4) or ""), label
                    assert "RECOVERY_REQUIRED" in command(cli, ["open"], cwd, env, expected=4)[1], (
                        label
                    )
                    assert (
                        runtime.psql(db, "SELECT count(*) FROM pairing_issuance") == issuance_before
                    )
                    assert snapshot() == before
                finally:
                    journal.write_bytes(original_journal)
        # Mismatched metadata never restarts or adopts anything.
        path = root / "instance.json"
        original = path.read_bytes()
        changed = json.loads(original)
        changed["instance_id"] = "00000000-0000-0000-0000-000000000001"
        path.write_text(json.dumps(changed))
        try:
            assert invoke(["start", "--no-open", "--json"], 4)["reason"] == "RECOVERY_REQUIRED"
            if pair_open:
                assert "RECOVERY_REQUIRED" in (tty_pair(cli, cwd, env, expected=4) or "")
                assert "RECOVERY_REQUIRED" in command(cli, ["open"], cwd, env, expected=4)[1]
        finally:
            path.write_bytes(original)
        if pair_open:
            with socket.socket() as foreign:
                foreign.bind(("127.0.0.1", 0))
                foreign.listen(1)
                foreign.settimeout(0.2)
                changed = json.loads(original)
                changed["origin"] = f"http://127.0.0.1:{foreign.getsockname()[1]}"
                path.write_text(json.dumps(changed))
                try:
                    assert "RECOVERY_REQUIRED" in (tty_pair(cli, cwd, env, expected=4) or "")
                    assert "RECOVERY_REQUIRED" in command(cli, ["open"], cwd, env, expected=4)[1]
                    try:
                        foreign.accept()
                    except TimeoutError:
                        pass
                    else:
                        raise AssertionError("Pair/open contacted foreign listener")
                finally:
                    path.write_bytes(original)
        assert snapshot() == before
        # Incomplete durable shutdown is not undone by another start.
        current = request(control, {"op": "status"})
        from uuid import uuid4

        stopped = request(
            control,
            {
                "op": "shutdown",
                "instance_id": record["instance_id"],
                "command_id": str(uuid4()),
                "expected_generation": current["generation"],
            },
        )
        denied = invoke(["start", "--no-open", "--json"], 3)
        assert denied["reason"] == "INSTANCE_CONTROL_MISMATCH"
        if pair_open:
            assert "INSTANCE_CONTROL_MISMATCH" in (tty_pair(cli, cwd, env, expected=3) or "")
            assert "INSTANCE_CONTROL_MISMATCH" in command(cli, ["open"], cwd, env, expected=3)[1]
        after = request(control, {"op": "status"})
        assert after["admission_open"] is False and after["generation"] == stopped["generation"]
        assert snapshot() == before
        private_values = [
            (root / "db-password").read_text().strip(),
            (control / "control.cap").read_text(),
        ]
        for secret in private_values:
            assert all(secret not in out for out in outputs)
            assert secret not in json.dumps(record)
            assert secret not in (root / "forwarder.log").read_text()
        # A real incompatible schema is refused without remigration.
        db = record["containers"]["db"]
        runtime.psql(db, "UPDATE alembic_version SET version_num='synthetic_incompatible'")
        try:
            assert invoke(["start", "--no-open", "--json"], 3)["reason"] == "SCHEMA_UPDATE_REQUIRED"
            assert (
                runtime.psql(db, "SELECT version_num FROM alembic_version")
                == "synthetic_incompatible"
            )
        finally:
            runtime.psql(db, "UPDATE alembic_version SET version_num='0004_pairing_receipts'")
        assert not select.select([sink], [], [], 0)[0], (
            "Startup/status contacted the provider/proxy sentinel"
        )
        assert all("synthetic-sl02-provider-marker" not in output for output in outputs)
        probe_ok = True
        print(
            f"INSTALLED_START_VERIFIED project={receipt['project']} instance={record['instance_id']} concurrent=2 reused=true headless=true",
            flush=True,
        )
    finally:
        sink.close()
        try:
            if driver_uncertain:
                raise AssertionError("Unreconciled CLI outcome: retain DB and recovery locator")
            runtime.deadline = time.monotonic() + 110
            if (root / "startup.json").exists():
                record = json.loads((root / "startup.json").read_text())
                teardown(runtime, root, control, port, record, uncertain=driver_uncertain)
                assert_resources_absent(runtime, root, control, record)
            else:
                assert not runtime.ids(), "Resources without startup intent"
            cleanup_ok = True
        finally:
            save_probe(
                state,
                data,
                receipt["project"],
                root,
                record,
                probe="PASS" if probe_ok else "FAIL",
                cleanup="VERIFIED" if cleanup_ok else "UNCERTAIN",
            )
    if pair_open and probe_ok and cleanup_ok:
        assert browser_outcome is not None
        print(
            "INSTALLED_PAIR_OPEN_VERIFIED tty=true one_use=true expiry=database "
            f"browser_session=lab opener={browser_outcome} cleanup=verified",
            flush=True,
        )


def run_installed_non_tty_default(data, receipt, cli):
    """Fresh installed omnis with pipes must not create any pairing issuance."""
    # A prior owned forwarder may leave TIME_WAIT. No port rebind/config trick:
    # wait for exclusive bind on the documented default, never contact a peer.
    end = time.monotonic() + 70
    while True:
        with socket.socket() as candidate:
            try:
                candidate.bind(("127.0.0.1", 8765))
                break
            except OSError:
                if time.monotonic() >= end:
                    raise AssertionError(
                        "Default port unavailable for installed non-TTY proof"
                    ) from None
        time.sleep(0.2)

    state = Path(tempfile.mkdtemp(prefix="s3h-", dir=os.environ["TMPDIR"]))
    root, control = state / "s/omnis", state / "r/omnis"
    cwd = state / "cwd"
    cwd.mkdir(mode=0o700)
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(state),
        "XDG_DATA_HOME": str(data),
        "XDG_STATE_HOME": str(state / "s"),
        "XDG_RUNTIME_DIR": str(state / "r"),
    }
    runtime = ControlRuntime(data, time.monotonic() + 30)
    assert runtime.receipt.image_id == receipt["image_id"]
    record = {}
    probe_ok = cleanup_ok = False
    driver_uncertain = True
    save_probe(state, data, receipt["project"], root, record, probe="PREPARED", cleanup="NOT_RUN")
    try:
        launched = subprocess.run(
            [cli], cwd=cwd, env=env, input="", capture_output=True, text=True, timeout=330
        )
        assert launched.returncode in {0, 2, 3}, "Unreconciled implicit CLI outcome"
        record = json.loads((root / "startup.json").read_text())
        assert record["phase"] == "READY" and record["port"] == 8765
        runtime.attempt = record["attempt"]
        # Attestation has its own finite budget after the CLI has joined; the
        # initial runtime preflight deadline must not expire during startup.
        runtime.deadline = time.monotonic() + 30
        assert set(record["containers"]) == {"db", "api", "supervisor"}
        assert set(runtime.ids()) == set(record["containers"].values())
        for role, cid in record["containers"].items():
            runtime.attest(cid, role, root, control, 8765)
        driver_uncertain = runtime.uncertain or not runtime.family_drained
        assert not driver_uncertain
        opener_outcome(
            launched.returncode, launched.stdout, "http://127.0.0.1:8765", launched.stderr
        )
        assert "Cod pairing Omnis" not in launched.stdout + launched.stderr, (
            "Non-TTY implicit launch disclosed a pairing code"
        )
        assert (
            runtime.psql(record["containers"]["db"], "SELECT count(*) FROM pairing_issuance") == "0"
        )
        status = subprocess.run(
            [cli, "status", "--json"], cwd=cwd, env=env, capture_output=True, text=True, timeout=50
        )
        assert status.returncode == 0
        view = json.loads(status.stdout)
        assert view["instance_id"] == record["instance_id"] and view["dashboard_ready"] is True
        assert view["assessment_ready"] is False and view["browser_opened"] is False
        probe_ok = True
    finally:
        try:
            if driver_uncertain:
                raise AssertionError("Unreconciled implicit CLI family: retain DB and locator")
            runtime.deadline = time.monotonic() + 110
            if (root / "startup.json").exists():
                record = json.loads((root / "startup.json").read_text())
                teardown(runtime, root, control, 8765, record)
                assert_resources_absent(runtime, root, control, record)
            else:
                assert runtime.ids() == []
            cleanup_ok = True
        finally:
            save_probe(
                state,
                data,
                receipt["project"],
                root,
                record,
                probe="PASS" if probe_ok else "FAIL",
                cleanup="VERIFIED" if cleanup_ok else "UNCERTAIN",
            )
    if probe_ok and cleanup_ok:
        print("INSTALLED_DEFAULT_NON_TTY_VERIFIED issuance=0 cleanup=verified", flush=True)


def run_interrupted_start(data, receipt, cli, *, phase="VERIFYING", expire_dashboard=False):
    """Interrupt VERIFYING or post-spawn FORWARDING; only the pinned CLI is paused.

    Its real child reaches a listener before TERM/CONT, without a product bypass.
    """
    assert phase in {"VERIFYING", "FORWARDING"}
    assert not expire_dashboard or phase == "VERIFYING"
    state = Path(tempfile.mkdtemp(prefix="s2i-", dir=os.environ["TMPDIR"]))
    root, control = state / "s/omnis", state / "r/omnis"
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(state),
        "XDG_DATA_HOME": str(data),
        "XDG_STATE_HOME": str(state / "s"),
        "XDG_RUNTIME_DIR": str(state / "r"),
    }
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    record = {}
    probe_ok = cleanup_ok = False
    driver_uncertain = True
    save_probe(state, data, receipt["project"], root, record, probe="PREPARED", cleanup="NOT_RUN")
    runtime = ControlRuntime(data, time.monotonic() + 180)
    process = None
    pidfd = -1
    observer = None
    paused = False
    begin = time.monotonic()
    stage_observed = None
    fault_resumed = None
    try:
        process = subprocess.Popen(
            [cli, "start", "--no-open", "--port", str(port), "--json"],
            cwd=state,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        pidfd = os.pidfd_open(process.pid)
        observer = ForwarderObservation(root, port, process.pid)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if (root / "startup.json").exists():
                record = json.loads((root / "startup.json").read_text())
                if record.get("phase") == phase:
                    stage_observed = time.monotonic()
                    if phase == "FORWARDING":
                        observer.discover()
                        if not observer.pins:
                            continue
                        signal.pidfd_send_signal(pidfd, signal.SIGSTOP)
                        paused = True
                        until = time.monotonic() + 8
                        while not observer.inodes and time.monotonic() < until:
                            observer.snapshot_listener()
                            time.sleep(0.002)
                        assert observer.inodes, "Forwarder produced no observed listener"
                    break
            assert process.poll() is None, "Startup exited before the read-only interruption stage"
            time.sleep(0.005)
        else:
            raise AssertionError("Startup did not reach read-only VERIFYING")
        if expire_dashboard:
            signal.pidfd_send_signal(pidfd, signal.SIGSTOP)
            paused = True
            runtime.attempt = record["attempt"]
            cid = record["containers"]["api"]
            runtime.attest(cid, "api", root, control, port)
            runtime.run("container", "stop", "--time", "15", cid, cap=22, effect=True)
            assert runtime.attest(cid, "api", root, control, port)["State"]["Running"] is False
        else:
            signal.pidfd_send_signal(pidfd, signal.SIGTERM)
        if paused:
            signal.pidfd_send_signal(pidfd, signal.SIGCONT)
            paused = False
        if expire_dashboard:
            fault_resumed = time.monotonic()
        out, err = process.communicate(timeout=125)
        record = json.loads((root / "startup.json").read_text())
        runtime.attempt = record["attempt"]
        assert process.returncode == 3, "Unreconciled interruption: preserve DB, not a cleanup PASS"
        assert record["phase"] == "FAILED_CLEANED" and record["cleanup"] == []
        assert record["failed_phase"] == phase, "Interruption missed the selected stage"
        assert not json.loads(out)["dashboard_ready"]
        elapsed = time.monotonic() - begin
        if expire_dashboard:
            assert json.loads(out)["reason"] == "DASHBOARD_READINESS_FAILED"
            assert fault_resumed is not None
            assert stage_observed is not None
            fault_elapsed = time.monotonic() - fault_resumed
            expiry_elapsed = time.monotonic() - stage_observed
            # The product's 30s wait starts at VERIFYING, before the API stop.
            # Pausing the CLI does not pause that monotonic deadline.
            assert 29 <= expiry_elapsed < 30 + 100, "Readiness expiry outside declared budgets"
            assert 0 <= fault_elapsed < 30 + 100, "Post-resume cleanup allowance exceeded"
            assert elapsed < 180 + 100, "Startup plus cleanup allowance exceeded"
            print(
                f"INSTALLED_READINESS_EXPIRY stage_elapsed={expiry_elapsed:.3f}s post_resume={fault_elapsed:.3f}s wait_budget=30s cleanup_allowance=100s",
                flush=True,
            )
        runtime.deadline = time.monotonic() + 30
        # The product must have removed its own resources BEFORE any test rescue.
        assert_resources_absent(runtime, root, control, record, observer=observer)
        driver_uncertain = False
        before = resource_snapshot(runtime, root, control, port)
        journal_before_retry = (root / "startup.json").read_bytes()
        driver_uncertain = True
        repeated = subprocess.run(
            [cli, "start", "--no-open", "--json"],
            cwd=state,
            env=env,
            capture_output=True,
            text=True,
            timeout=40,
        )
        assert repeated.returncode == 4
        assert json.loads(repeated.stdout)["reason"] == "RECOVERY_REQUIRED"
        assert resource_snapshot(runtime, root, control, port) == before, (
            "Retry changed resource state"
        )
        assert (root / "startup.json").read_bytes() == journal_before_retry
        driver_uncertain = False
        secret = (root / "db-password").read_text().strip()
        assert secret not in out + err + repeated.stdout + repeated.stderr
        assert (root / "postgres").is_dir()
        probe_ok = True
        print(
            f"INSTALLED_START_INTERRUPT project={receipt['project']} interrupted={phase} expiry={expire_dashboard} elapsed={elapsed:.3f}s phase=FAILED_CLEANED exit=3",
            flush=True,
        )
    finally:
        original_failure = sys.exception()
        try:
            if paused and pidfd >= 0:
                signal.pidfd_send_signal(pidfd, signal.SIGCONT)
            if process is not None and process.poll() is None:
                if pidfd >= 0:
                    signal.pidfd_send_signal(pidfd, signal.SIGTERM)
                else:
                    process.terminate()  # Direct unreaped test child, never a metadata PID.
                process.wait(timeout=125)
            if process is not None and process.returncode == 0:
                driver_uncertain = (
                    False  # A missed stage may leave a normally READY owned instance.
                )
            runtime.deadline = time.monotonic() + 110
            if (root / "startup.json").exists():
                record = json.loads((root / "startup.json").read_text())
                runtime.attempt = record["attempt"]
                if driver_uncertain or record.get("phase") == "UNCERTAIN":
                    if original_failure is None:
                        raise AssertionError(
                            "Unreconciled interruption: DB retained at recovery locator"
                        )
                else:
                    if runtime.ids() or record.get("forwarder"):
                        teardown(runtime, root, control, port, record)
                    assert_resources_absent(runtime, root, control, record, observer=observer)
                    cleanup_ok = True
        finally:
            if process is not None:
                for stream in (process.stdout, process.stderr):
                    if stream is not None:
                        stream.close()
            if pidfd >= 0:
                os.close(pidfd)
            try:
                if observer is not None:
                    try:
                        observer.rescue()
                    finally:
                        observer.close()
            finally:
                save_probe(
                    state,
                    data,
                    receipt["project"],
                    root,
                    record,
                    probe="PASS" if probe_ok else "FAIL",
                    cleanup="VERIFIED" if cleanup_ok else "UNCERTAIN",
                )
        print(f"INSTALLED_START_INTERRUPT_CLEANUP data_retained={root}", flush=True)
