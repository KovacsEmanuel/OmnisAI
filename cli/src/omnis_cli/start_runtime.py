"""Host-only lifecycle of the installed, fixed P0 Compose topology.

No Docker socket is passed to a service. No pull/build, cwd config or shell.

Owner contract: the standalone CLI exclusively owns child waits continuously
from spawn through pidfd acquisition and reap. Concurrent library reapers/child
producers or signal-policy replacement in that interval are unsupported; a
SIGCHLD snapshot does not impose that exclusivity on an arbitrary embedding.
WNOWAIT's observed exit status authorizes ACK, not a claim that every later
ECHILD is detected. Error stop pins only the leader and never certifies family
drainage or daemon completion.
"""

import hashlib
import os
import platform
import re
import selectors
import signal
import stat
import subprocess
import time
from pathlib import Path

from .compose import ImageReceipt, _checked_socket, _one_image, _record
from .instance import private_dir, private_file
from .lifecycle import StartError, mapping, read_record, remaining
from .release import _installed_pointer, _manifest

POSTGRES = (
    "postgres:18.6-bookworm@sha256:3725f4e2499eef5134592b3b4ab79a543ed7f8e533b05b5b637af926630f6650"
)
SAFE_PATH = "/usr/bin:/bin"


class ControlRuntime:
    def __init__(self, data_home: Path, deadline: float) -> None:
        self.deadline = deadline
        self.uncertain = False
        self.family_drained = True
        self.attempt: str | None = None
        self.release = data_home / "omnis/releases/0.1.0"
        try:
            private_dir(data_home / "omnis")
            if not _installed_pointer(data_home / "omnis/installed.json"):
                raise FileNotFoundError()
            manifest, self.files = _manifest(self.release)
        except FileNotFoundError:
            raise StartError("RELEASE_REQUIRED") from None
        self.digest = hashlib.sha256(manifest).hexdigest()
        receipt = _record(data_home / "omnis/image.json", self.digest, complete=True)
        if receipt is None:
            raise StartError("IMAGE_REQUIRED")
        self.receipt: ImageReceipt = receipt
        if (
            platform.system() != "Linux"
            or platform.machine() != "x86_64"
            or os.getuid() == 0
            or os.getgid() == 0
        ):
            raise StartError("PLATFORM_UNSUPPORTED")
        if any(k.startswith(("DOCKER_", "COMPOSE_", "PG")) for k in os.environ):
            raise StartError("AMBIENT_OVERRIDE_REFUSED")
        # Fixed system executable and system Compose plugin; no PATH/cwd/user config lookup.
        self.docker = Path("/usr/bin/docker").resolve(strict=True)
        info = self.docker.stat()
        if info.st_uid != 0 or info.st_mode & 0o022 or not stat.S_ISREG(info.st_mode):
            raise StartError("UNTRUSTED_DOCKER_EXECUTABLE")
        self.host = _checked_socket(receipt.docker_host)
        if self.host != receipt.docker_host:
            raise StartError("DOCKER_ENDPOINT_MISMATCH")
        self.check_daemon()
        image = self.inspect("image", receipt.image_id)
        if image is None:
            raise StartError("IMAGE_REQUIRED")
        config = mapping(image.get("Config"))
        labels = mapping(config.get("Labels"))
        if (
            image.get("Id") != receipt.image_id
            or image.get("Architecture") != "amd64"
            or image.get("Os") != "linux"
            or config.get("User") != "65532:65532"
            or config.get("Entrypoint") not in (None, [])
            or config.get("Cmd") != ["python", "-I", "-m", "omnis.serve"]
            or labels.get("org.omnis.project") != receipt.project
            or labels.get("org.omnis.bundle_sha256") != self.digest
        ):
            raise StartError("IMAGE_IDENTITY_MISMATCH")
        tagged = self.inspect("image", receipt.tag)
        if tagged is None or tagged.get("Id") != receipt.image_id:
            raise StartError("IMAGE_RECEIPT_MISMATCH")
        pg = self.inspect("image", POSTGRES)
        pg_digests = pg.get("RepoDigests") if pg else None
        if (
            pg is None
            or pg.get("Architecture") != "amd64"
            or not isinstance(pg.get("Id"), str)
            or not isinstance(pg_digests, list)
            or POSTGRES.replace(":18.6-bookworm", "") not in pg_digests
        ):
            raise StartError("POSTGRES_IMAGE_REQUIRED")
        self.pg_image = str(pg["Id"])
        if not self.run("compose", "version", "--short").stdout.strip().startswith("2."):
            raise StartError("COMPOSE_V2_REQUIRED")
        self.check_daemon()

    def run(
        self,
        *args: str,
        env: dict[str, str] | None = None,
        cap: float = 15,
        success: bool = True,
        effect: bool = False,
        stdin: bytes | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if stdin is not None and (type(stdin) is not bytes or len(stdin) > 16384):
            raise StartError("COMMAND_INPUT_LIMIT", 4)
        end = time.monotonic() + remaining(self.deadline, cap)  # Check BEFORE spawn.
        # Library callers retain their signal policy. Auto-reap and SIGCHLD
        # handlers invalidate the declared owner contract; refuse before effects.
        if signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL:
            raise StartError("CHILD_SIGNAL_POLICY_UNSUPPORTED")
        argv = [str(self.docker), "--config", str(self.release / "ops"), "--host", self.host, *args]
        previous_uncertain, previous_drained = self.uncertain, self.family_drained
        # Fail closed before spawn, through wait, decoding and fallible pipe cleanup.
        if effect:
            self.uncertain = True
        self.family_drained = False
        reaping = False
        process = subprocess.Popen(
            argv,
            cwd=self.release,
            env={"PATH": SAFE_PATH, **(env or {})},
            stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        buffers = [bytearray(), bytearray()]
        pidfd = -1
        try:
            try:
                pidfd = os.pidfd_open(process.pid)
            except OSError:
                raise StartError("CHILD_OWNERSHIP_UNAVAILABLE", 4) from None
            assert process.stdout is not None and process.stderr is not None
            with selectors.DefaultSelector() as reader:
                reader.register(process.stdout, selectors.EVENT_READ, 0)
                reader.register(process.stderr, selectors.EVENT_READ, 1)
                sent = 0
                if process.stdin is not None:
                    os.set_blocking(process.stdin.fileno(), False)
                    if stdin:
                        reader.register(process.stdin, selectors.EVENT_WRITE, 2)
                    else:
                        process.stdin.close()
                total = 0
                while reader.get_map():
                    events = reader.select(remaining(end, cap))
                    if not events:
                        raise StartError("STARTUP_TIMEOUT", 3)
                    for key, _ in events:
                        if key.data == 2:
                            assert stdin is not None and process.stdin is not None
                            try:
                                sent += os.write(key.fd, stdin[sent:])
                            except BlockingIOError:
                                continue
                            if sent == len(stdin):
                                reader.unregister(key.fd)
                                process.stdin.close()  # Real EOF, not a JSON delimiter.
                            continue
                        part = os.read(key.fd, min(65536, 4 * 1024 * 1024 + 1 - total))
                        if not part:
                            reader.unregister(key.fd)
                            continue
                        total += len(part)
                        if total > 4 * 1024 * 1024:
                            raise StartError("DOCKER_OUTPUT_LIMIT", 3)
                        buffers[key.data].extend(part)
            # EOF is not exit. ECHILD is not a successful acknowledgement.
            while (
                exited := os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            ) is None:
                time.sleep(min(0.01, remaining(end, cap)))
            # Popen.wait hides ECHILD as exit 0. Preserve the observed status so
            # a competing reaper cannot turn a nonzero/signal exit into an ACK.
            expected = exited.si_status if exited.si_code == os.CLD_EXITED else -exited.si_status
            # Entering wait can reap before Popen publishes returncode; an
            # interrupted reap never restores stop authority.
            reaping = True
            if process.wait(timeout=remaining(end, cap)) != expected:
                raise StartError("CHILD_OWNERSHIP_LOST", 4)
        except BaseException as exc:
            if effect:
                self.uncertain = True  # Killing a CLI cannot settle a daemon-side operation.
            # Leader stop/reap does not attest descendants, including its old group.
            self.family_drained = False
            if isinstance(exc, ChildProcessError):
                raise StartError("CHILD_OWNERSHIP_LOST", 4) from None
            if not reaping:
                # Numeric PGIDs cannot be pinned across an unexpected reaper or
                # a policy change during timeout/flood. Stop only the pinned leader;
                # leave family/daemon uncertainty sticky. Never fall back to killpg.
                if pidfd >= 0:
                    for sig in (signal.SIGTERM, signal.SIGKILL):
                        try:
                            signal.pidfd_send_signal(pidfd, sig)
                        except OSError:
                            pass  # Still attempt the other signal and bounded reap.
                try:
                    reaping = True
                    process.wait(timeout=max(0, min(5, self.deadline - time.monotonic())))
                except (OSError, subprocess.SubprocessError):
                    pass  # Preserve the original error and conservative family state.
            raise
        finally:
            try:
                if pidfd >= 0:
                    os.close(pidfd)
            finally:
                try:
                    if process.stdout is not None:
                        process.stdout.close()
                finally:
                    try:
                        if process.stderr is not None:
                            process.stderr.close()
                    finally:
                        if process.stdin is not None:
                            process.stdin.close()
        result = subprocess.CompletedProcess(
            argv, process.returncode, buffers[0].decode(), buffers[1].decode()
        )
        if result.returncode >= 0:
            self.family_drained = previous_drained  # Trusted CLI's ordinary completed path.
        if result.returncode == 0 or not effect:
            self.uncertain = previous_uncertain
        # A generic nonzero effect is not a known refusal. Negative returncode
        # never proves family drainage, even for a read-only command.
        if success and result.returncode:
            raise StartError("LOCAL_SERVICE_COMMAND_FAILED", 3)
        return result  # Never print raw Docker output or environment (may contain DSN).

    def check_daemon(self) -> None:
        if (
            _checked_socket(self.host) != self.host
            or self.run("info", "--format", "{{.ID}}").stdout.strip() != self.receipt.docker_id
        ):
            raise StartError("DOCKER_IDENTITY_MISMATCH")

    def inspect(self, kind: str, ident: str) -> dict[str, object] | None:
        response = self.run(kind, "inspect", ident, success=False)
        if response.returncode:
            if "No such" in response.stderr or (
                kind == "network" and "not found" in response.stderr
            ):
                return None
            raise StartError("DOCKER_READBACK_UNAVAILABLE", 3)
        return _one_image(response.stdout)

    def ids(self) -> list[str]:
        rows = self.run(
            "ps",
            "-a",
            "--no-trunc",
            "--filter",
            f"label=com.docker.compose.project={self.receipt.project}",
            "--format",
            "{{.ID}}",
        ).stdout.splitlines()
        if any(not re.fullmatch(r"[0-9a-f]{64}", row) for row in rows):
            raise StartError("CONTAINER_ID_INVALID", 3)
        return rows

    def compose(
        self, env: dict[str, str], *args: str, effect: bool = False
    ) -> subprocess.CompletedProcess[str]:
        return self.run(
            "compose",
            "--project-name",
            self.receipt.project,
            "--project-directory",
            str(self.release),
            "--env-file",
            "/dev/null",
            "-f",
            str(self.release / "ops/compose.yaml"),
            *args,
            env=env,
            cap=45,
            effect=effect,
        )

    def network(self, allowed: set[str]) -> str | None:
        self.check_daemon()
        item = self.inspect("network", f"{self.receipt.project}_control")
        if item is None:
            return None
        if (
            self.attempt is None
            or mapping(item.get("Labels")).get("org.omnis.start-attempt") != self.attempt
        ):
            raise StartError("ATTEMPT_IDENTITY_MISMATCH", 4)
        if (
            mapping(item.get("Labels")).get("com.docker.compose.project") != self.receipt.project
            or item.get("Internal") is not True
            or item.get("Driver") != "bridge"
            or set(mapping(item.get("Containers"))) - allowed
        ):
            raise StartError("NETWORK_IDENTITY_MISMATCH", 3)
        ident = item.get("Id")
        if not isinstance(ident, str) or not re.fullmatch(r"[0-9a-f]{64}", ident):
            raise StartError("NETWORK_IDENTITY_MISMATCH", 3)
        return ident

    def attest(
        self, ident: str, role: str, root: Path, control: Path, port: int
    ) -> dict[str, object]:
        self.check_daemon()
        item = self.inspect("container", ident)
        if item is None:
            raise StartError("OWNED_CONTAINER_MISSING", 3)
        config, host = mapping(item.get("Config")), mapping(item.get("HostConfig"))
        labels, net = mapping(config.get("Labels")), mapping(item.get("NetworkSettings"))
        if self.attempt is None or labels.get("org.omnis.start-attempt") != self.attempt:
            raise StartError("ATTEMPT_IDENTITY_MISMATCH", 4)
        mounts = item.get("Mounts")
        if not isinstance(mounts, list):
            raise StartError("CONTAINER_MOUNTS_INVALID", 3)
        actual = {
            (m.get("Type"), m.get("Source"), m.get("Destination"), m.get("RW"))
            for raw in mounts
            for m in [mapping(raw)]
        }
        expected: set[tuple[object, object, object, object]] = set()
        if role == "db":
            expected = {
                ("bind", str(root / "postgres"), "/var/lib/postgresql", True),
                ("bind", str(root / "db-password"), "/run/secrets/db_password", False),
            }
        elif role in {"api", "supervisor"}:
            expected = {("bind", str(control), "/run/omnis-control", role == "supervisor")}
            if role == "api":
                expected.add(("bind", str(root / "http"), "/run/omnis-http", True))
        elif role not in {"migrate", "reconcile"}:
            raise StartError("CONTAINER_ROLE_INVALID", 3)
        expected_command = {
            "db": ["postgres"],
            "api": ["python", "-I", "-m", "omnis.serve"],
            "supervisor": ["python", "-I", "-m", "omnis.supervisor"],
            "migrate": ["python", "-I", "-m", "omnis.migrate", "--initialize"],
            "reconcile": ["python", "-I", "-m", "omnis.stop_reconcile"],
        }[role]
        running = mapping(item.get("State")).get("Running") is True
        if (
            item.get("Id") != ident
            or labels.get("com.docker.compose.project") != self.receipt.project
            or labels.get("com.docker.compose.service") != role
            or item.get("Image") != (self.pg_image if role == "db" else self.receipt.image_id)
            or config.get("Cmd") != expected_command
            or (
                config.get("Entrypoint") != ["docker-entrypoint.sh"]
                if role == "db"
                else config.get("Entrypoint") not in (None, [])
            )
            or host.get("Privileged") is not False
            or host.get("PublishAllPorts") is not False
            or host.get("PortBindings") not in (None, {})
            or (
                net.get("Ports") is not None
                and any(value not in (None, []) for value in mapping(net["Ports"]).values())
            )
            or host.get("NetworkMode") != f"{self.receipt.project}_control"
            or (
                (running or role == "reconcile")
                and set(mapping(net.get("Networks"))) != {f"{self.receipt.project}_control"}
            )
            or host.get("PidMode")
            or host.get("IpcMode") == "host"
            or host.get("CapAdd")
            or host.get("Devices")
            or actual != expected
            or len(mounts) != len(expected)
        ):
            raise StartError("CONTAINER_IDENTITY_MISMATCH", 3)
        if role != "db" and (
            config.get("User") != f"{os.getuid()}:{os.getgid()}"
            or host.get("ReadonlyRootfs") is not True
            or host.get("CapDrop") != ["ALL"]
            or host.get("SecurityOpt") != ["no-new-privileges:true"]
        ):
            raise StartError("CONTROL_CONFINEMENT_MISMATCH", 3)
        image_id = self.pg_image if role == "db" else self.receipt.image_id
        image = self.inspect("image", image_id)
        if image is None or image.get("Id") != image_id:
            raise StartError("IMAGE_IDENTITY_MISMATCH", 4)
        inherited = mapping(image.get("Config")).get("Env")
        environment = config.get("Env")
        if (
            not isinstance(inherited, list)
            or not isinstance(environment, list)
            or any(
                not isinstance(value, str) or "=" not in value or not value.split("=", 1)[0]
                for value in [*inherited, *environment]
            )
        ):
            raise StartError("CONTROL_ENV_INVALID", 4)
        expected_env = dict(value.split("=", 1) for value in inherited)
        actual_env = dict(value.split("=", 1) for value in environment)
        if len(expected_env) != len(inherited) or len(actual_env) != len(environment):
            raise StartError("CONTROL_ENV_INVALID", 4)
        # Image defaults are read by verified content ID, never copied from a fixture.
        # Only the overrides actually emitted by Compose/create belong here.
        if role == "db":
            expected_env.update(
                POSTGRES_USER="omnis",
                POSTGRES_DB="omnis",
                POSTGRES_PASSWORD_FILE="/run/secrets/db_password",
                POSTGRES_INITDB_ARGS="--auth-host=scram-sha-256",
            )
        else:
            password = private_file(root / "db-password", limit=64).strip()
            if not re.fullmatch(r"[0-9a-f]{48}", password):
                raise StartError("DATABASE_SECRET_INVALID")
            expected_env["OMNIS_DATABASE_URL"] = (
                f"postgresql+psycopg://omnis:{password}@db:5432/omnis"
            )
            if role in {"migrate", "reconcile"}:
                system_id = read_record(root / "startup.json").get("system_id")
                if not isinstance(system_id, str) or not system_id.isdecimal():
                    raise StartError("DATABASE_IDENTITY_INVALID", 4)
                expected_env["OMNIS_EXPECTED_SYSTEM_ID"] = system_id
            else:
                expected_env["OMNIS_CONTROL_DIR"] = "/run/omnis-control"
            if role == "api":
                expected_env.update(OMNIS_HTTP_DIR="/run/omnis-http", OMNIS_HTTP_PORT=str(port))
        if actual_env != expected_env:
            raise StartError("CONTROL_CONFIGURATION_MISMATCH", 4)
        if role == "reconcile" and (
            config.get("Volumes")
            or config.get("Tty") is not False
            or any(
                config.get(key) is not True
                for key in ("OpenStdin", "StdinOnce", "AttachStdin", "AttachStdout", "AttachStderr")
            )
            or host.get("Binds")
            or host.get("Tmpfs")
            or host.get("RestartPolicy") != {"Name": "no", "MaximumRetryCount": 0}
        ):
            raise StartError("RECONCILIATION_CONFINEMENT_MISMATCH", 4)
        return item

    def psql(self, ident: str, query: str) -> str:
        return self.run(
            "exec", ident, "psql", "-U", "omnis", "-d", "omnis", "-Atc", query
        ).stdout.strip()

    def wait_container(self, ident: str, *, healthy: bool = False) -> dict[str, object]:
        until = min(self.deadline, time.monotonic() + 45)
        while time.monotonic() < until:
            item = self.inspect("container", ident)
            state = mapping(item.get("State")) if item else {}
            if healthy:
                if mapping(state.get("Health", {})).get("Status") == "healthy":
                    return state
                if state.get("Status") in {"exited", "dead"}:
                    break
            elif state.get("Status") == "exited":
                return state
            time.sleep(0.2)
        raise StartError("SERVICE_READINESS_FAILED", 3)
