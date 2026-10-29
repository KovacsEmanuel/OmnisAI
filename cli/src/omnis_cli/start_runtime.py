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
import json
import os
import platform
import re
import selectors
import signal
import stat
import subprocess
import time
from pathlib import Path

from . import development
from .compose import ImageReceipt, _checked_socket, _one_image, _record
from .instance import private_dir, private_file
from .lifecycle import StartError, mapping, read_record, remaining
from .release import PROVIDER_SETTINGS_PROFILE, _installed_pointer, _manifest, installed_version

POSTGRES = (
    "postgres:18.6-bookworm@sha256:3725f4e2499eef5134592b3b4ab79a543ed7f8e533b05b5b637af926630f6650"
)
SAFE_PATH = "/usr/bin:/bin"
RUNTIME_COMMAND = ("/opt/hermes/venv/bin/python", "-I", "-m", "omnis_hermes.runtime_host")


def attest_runtime_image(image: dict[str, object], receipt: ImageReceipt, digest: str) -> None:
    config = mapping(image.get("Config"))
    labels = mapping(config.get("Labels"))
    if (
        image.get("Id") != receipt.runtime_image_id
        or image.get("Architecture") != "amd64"
        or image.get("Os") != "linux"
        or config.get("User") != "65532:65532"
        or config.get("Entrypoint") not in (None, [])
        or config.get("Cmd") != list(RUNTIME_COMMAND)
        or labels.get("org.omnis.project") != receipt.project
        or labels.get("org.omnis.bundle_sha256") != digest
        or labels.get("org.omnis.profile") != receipt.profile
        or labels.get("org.omnis.image-role") != "runtime"
    ):
        raise StartError("RUNTIME_IMAGE_IDENTITY_MISMATCH", 4)


def private_identity(path: Path) -> list[int]:
    private_dir(path)
    info = path.lstat()
    if stat.S_IMODE(info.st_mode) != 0o700 or info.st_gid != os.getgid():
        raise StartError("NATIVE_PATH_IDENTITY_MISMATCH", 4)
    return [info.st_dev, info.st_ino, info.st_uid, info.st_gid, 0o700]


def check_native_paths(root: Path, record: dict[str, object] | None = None) -> None:
    if record is None:
        record = read_record(root / "startup.json")
    if (
        type(record.get("format")) is not int
        or record["format"] not in (3, 4)
        or private_identity(root / "provider") != record.get("provider_identity")
        or private_identity(root / "native-ipc") != record.get("runtime_dir_identity")
        or (
            "catalog_identity" in record
            and private_identity(root / "catalog") != record["catalog_identity"]
        )
    ):
        raise StartError("NATIVE_PATH_IDENTITY_MISMATCH", 4)


def check_vault_paths(root: Path, record: dict[str, object] | None = None) -> None:
    if record is None:
        record = read_record(root / "startup.json")
    if (
        type(record.get("format")) is not int
        or record["format"] != 5
        or private_identity(root / "vault") != record.get("vault_identity")
        or private_identity(root / "vault-key") != record.get("vault_key_identity")
    ):
        raise StartError("VAULT_PATH_IDENTITY_MISMATCH", 4)


def provider_settings_overlay(runtime: "ControlRuntime", env: dict[str, str]) -> dict[str, object]:
    if not runtime.provider_settings or runtime.native or runtime.model_test:
        raise StartError("IMAGE_PROFILE_MISMATCH", 4)
    root = Path(env["OMNIS_STATE_ROOT"])
    check_vault_paths(root)
    return {
        "services": {
            "supervisor": {
                "environment": {
                    "OMNIS_VAULT_DIR": "/vault",
                    "OMNIS_VAULT_KEY_DIR": "/vault-key",
                    "OMNIS_MODEL_EGRESS_DIR": "/vault",
                },
                "volumes": [
                    *(
                        {"type": "bind", "source": str(root / name), "target": "/" + name}
                        for name in ("vault", "vault-key")
                    ),
                    *development.mounts(runtime.development_workspace, "supervisor"),
                ],
            },
            **(
                {"api": {"volumes": development.mounts(runtime.development_workspace, "api")}}
                if runtime.development_workspace is not None
                else {}
            ),
        }
    }


def settings_overlay(runtime: "ControlRuntime", env: dict[str, str]) -> dict[str, object]:
    """Finite installed-wheel template, selected only by the sealed image profile."""
    root = Path(env["OMNIS_STATE_ROOT"])
    check_native_paths(root)
    ipc: dict[str, object] = {
        "type": "bind",
        "source": str(root / "native-ipc"),
        "target": "/runtime",
    }
    model_test = getattr(runtime, "model_test", False) is True
    supervisor_env = {"OMNIS_RUNTIME_DIR": "/runtime"}
    supervisor_volumes: list[dict[str, object]] = [ipc]
    if model_test:
        record = read_record(root / "startup.json")
        if private_identity(root / "catalog") != record.get("catalog_identity"):
            raise StartError("NATIVE_PATH_IDENTITY_MISMATCH", 4)
        supervisor_env.update(
            OMNIS_NATIVE_PREPARATION_CATALOG_ROOT="/catalog",
            OMNIS_MANAGED_TASKS="1",
            OMNIS_MODEL_TEST_SOURCE_ROOT="/opt/omnis/model-test",
        )
        supervisor_volumes.append(
            {"type": "bind", "source": str(root / "catalog"), "target": "/catalog"}
        )
    return {
        "services": {
            "supervisor": {"environment": supervisor_env, "volumes": supervisor_volumes},
            "runtime": {
                "image": runtime.receipt.runtime_image_id,
                "pull_policy": "never",
                "platform": "linux/amd64",
                "restart": "no",
                "labels": {"org.omnis.start-attempt": runtime.attempt},
                "entrypoint": None,  # Match Compose's rendered default; image is attested separately.
                "command": list(RUNTIME_COMMAND),
                "user": f"{os.getuid()}:{os.getgid()}",
                "read_only": True,
                "cap_drop": ["ALL"],
                "security_opt": ["no-new-privileges:true"],
                "network_mode": "none",
                "environment": {"OMNIS_RUNTIME_DIR": "/runtime"},
                "volumes": [
                    ipc,
                    {"type": "bind", "source": str(root / "provider"), "target": "/state/provider"},
                    *([{**ipc, "target": "/state/tmp"}] if model_test else []),
                ],
            },
        }
    }


def _network_identity(
    item: dict[str, object], project: str, attempt: str | None, allowed: set[str]
) -> str:
    """One pure policy for CLI inspect and the typed Stop Engine view."""
    if attempt is None or mapping(item.get("Labels")).get("org.omnis.start-attempt") != attempt:
        raise StartError("ATTEMPT_IDENTITY_MISMATCH", 4)
    members = item.get("Containers")
    if (
        mapping(item.get("Labels")).get("com.docker.compose.project") != project
        or item.get("Name") != project + "_control"
        or item.get("Internal") is not True
        or item.get("Driver") != "bridge"
        or item.get("Options") not in (None, {})
        or (members is not None and set(mapping(members)) - allowed)
    ):
        raise StartError("NETWORK_IDENTITY_MISMATCH", 3)
    ident = item.get("Id")
    if not isinstance(ident, str) or not re.fullmatch(r"[0-9a-f]{64}", ident):
        raise StartError("NETWORK_IDENTITY_MISMATCH", 3)
    return ident


def refuse_upgrade(root: Path, upgrade_id: str | None = None) -> None:
    if os.path.lexists(root / "upgrade.json"):
        intent = read_record(root / "upgrade.json")
        if intent.get("state") not in {"COMPLETE", "ROLLED_BACK", "REFUSED"} and (
            upgrade_id is None or intent.get("upgrade_id") != upgrade_id
        ):
            raise StartError("UPGRADE_RECOVERY_REQUIRED", 4)


class ControlRuntime:
    development_workspace: str | None = None
    upgrading: bool = False

    def __init__(
        self,
        data_home: Path,
        deadline: float,
        *,
        upgrade_id: str | None = None,
        binding: Path | None = None,
        version: str | None = None,
    ) -> None:
        self.deadline = deadline
        self.uncertain = False
        self.family_drained = True
        self.attempt: str | None = None
        data_root = data_home / "omnis"
        refuse_upgrade(data_root, upgrade_id)
        try:
            private_dir(data_home / "omnis")
            if not _installed_pointer(data_home / "omnis/installed.json"):
                raise FileNotFoundError()
            self.release = data_root / "releases" / (version or installed_version(data_root))
            manifest, self.files = _manifest(self.release)
        except FileNotFoundError:
            raise StartError("RELEASE_REQUIRED") from None
        self.digest = hashlib.sha256(manifest).hexdigest()
        self.schema = str(json.loads(manifest)["schema"])
        self.model_test = "model-test/profile.yaml" in self.files
        receipt = _record((binding or data_root) / "image.json", self.digest, complete=True)
        if receipt is None:
            raise StartError("IMAGE_REQUIRED")
        self.receipt: ImageReceipt = receipt
        if receipt.release != self.release.name:
            raise StartError("IMAGE_RELEASE_MISMATCH", 4)
        if ("native/source-manifest.json" in self.files) != (self.native) or json.loads(
            manifest
        ).get("profile") != receipt.profile:
            raise StartError("IMAGE_PROFILE_MISMATCH")
        # The finite profile below selects both the four-role template and its
        # independently installed runtime image. No ambient configuration opts in.
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
            or self.provider_settings
            and labels.get("org.omnis.profile") != PROVIDER_SETTINGS_PROFILE
        ):
            raise StartError("IMAGE_IDENTITY_MISMATCH")
        if self.native:
            native_image = self.inspect("image", str(receipt.runtime_image_id))
            native_tag = self.inspect("image", str(receipt.runtime_tag))
            if (
                native_image is None
                or native_tag is None
                or native_tag.get("Id") != receipt.runtime_image_id
            ):
                raise StartError("RUNTIME_IMAGE_REQUIRED")
            attest_runtime_image(native_image, receipt, self.digest)
        tagged = self.inspect("image", receipt.tag)
        if tagged is None or tagged.get("Id") != receipt.image_id:
            raise StartError("IMAGE_RECEIPT_MISMATCH")
        pg = self.inspect("image", POSTGRES)
        pg_digests = pg.get("RepoDigests") if pg else None
        if (
            pg is None
            or pg.get("Architecture") != "amd64"
            or pg.get("Os") != "linux"
            or not isinstance(pg.get("Id"), str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", str(pg.get("Id"))) is None
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
        stdin_fd: int | None = None,
        stdout_fd: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if stdin is not None and (type(stdin) is not bytes or len(stdin) > 16384):
            raise StartError("COMMAND_INPUT_LIMIT", 4)
        if stdin is not None and stdin_fd is not None:
            raise StartError("COMMAND_INPUT_LIMIT", 4)
        for fd in (stdin_fd, stdout_fd):
            if fd is not None:
                info = os.fstat(fd)
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600
                    or info.st_nlink != 1
                    or info.st_size > 1024**3
                ):
                    raise StartError("COMMAND_BINARY_FD_INVALID", 4)
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
            stdin=stdin_fd
            if stdin_fd is not None
            else subprocess.PIPE
            if stdin is not None
            else subprocess.DEVNULL,
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
                binary_total = 0
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
                        if key.data == 0 and stdout_fd is not None:
                            binary_total += len(part)
                            if binary_total > 1024**3:
                                raise StartError("COLD_ARCHIVE_LIMIT", 4)
                            view = memoryview(part)
                            while view:
                                view = view[os.write(stdout_fd, view) :]
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

    @property
    def provider_settings(self) -> bool:
        return getattr(self.receipt, "profile", None) == PROVIDER_SETTINGS_PROFILE

    @property
    def native(self) -> bool:
        return getattr(self.receipt, "profile", None) in {"p4a-settings-offline", "p4a-codex-auth"}

    def compose(
        self, env: dict[str, str], *args: str, effect: bool = False
    ) -> subprocess.CompletedProcess[str]:
        overlay = (
            provider_settings_overlay(self, env)
            if self.provider_settings
            else settings_overlay(self, env)
            if self.native
            else None
        )
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
            *(["-f", "-"] if overlay is not None else []),
            *args,
            env=env,
            cap=45,
            effect=effect,
            # Overlay paths are literal, not Compose environment expressions.
            stdin=json.dumps(overlay).replace("$", "$$").encode() if overlay is not None else None,
        )

    def network(self, allowed: set[str]) -> str | None:
        self.check_daemon()
        item = self.inspect("network", f"{self.receipt.project}_control")
        if item is None:
            return None
        return _network_identity(item, self.receipt.project, self.attempt, allowed)

    def attest(
        self, ident: str, role: str, root: Path, control: Path, port: int, *, restore: bool = False
    ) -> dict[str, object]:
        if restore and role != "reconcile":
            raise StartError("CONTAINER_ROLE_INVALID", 3)
        self.check_daemon()
        item = self.inspect("container", ident)
        if item is None:
            raise StartError("OWNED_CONTAINER_MISSING", 3)
        config, host = mapping(item.get("Config")), mapping(item.get("HostConfig"))
        labels, net = mapping(config.get("Labels")), mapping(item.get("NetworkSettings"))
        if self.attempt is None or labels.get("org.omnis.start-attempt") != self.attempt:
            raise StartError("ATTEMPT_IDENTITY_MISMATCH", 4)
        mounts = item.get("Mounts")
        if self.native:
            check_native_paths(root)
        if self.provider_settings:
            check_vault_paths(root)
        if not isinstance(mounts, list):
            raise StartError("CONTAINER_MOUNTS_INVALID", 3)
        actual: set[tuple[object, object, object, object]] = set()
        for raw in mounts:
            mount = mapping(raw)
            if (
                any(
                    not isinstance(mount.get(key), str) for key in ("Type", "Source", "Destination")
                )
                or type(mount.get("RW")) is not bool
                or mount.get("Propagation") != "rprivate"
            ):
                raise StartError("CONTAINER_MOUNTS_INVALID", 3)
            actual.add((mount["Type"], mount["Source"], mount["Destination"], mount["RW"]))
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
            elif self.provider_settings:
                expected.update(
                    ("bind", str(root / name), "/" + name, True) for name in ("vault", "vault-key")
                )
            elif self.native:
                expected.add(("bind", str(root / "native-ipc"), "/runtime", True))
                if self.model_test:
                    expected.add(("bind", str(root / "catalog"), "/catalog", True))
        elif role == "runtime" and self.native:
            expected = {
                ("bind", str(root / "native-ipc"), "/runtime", True),
                ("bind", str(root / "provider"), "/state/provider", True),
            }
            if self.model_test:
                expected.add(("bind", str(root / "native-ipc"), "/state/tmp", True))
        elif role not in {"migrate", "reconcile"}:
            raise StartError("CONTAINER_ROLE_INVALID", 3)
        expected.update(
            ("bind", mount["source"], mount["target"], False)
            for mount in development.mounts(self.development_workspace, role)
        )
        expected_command = {
            "runtime": list(RUNTIME_COMMAND),
            "db": ["postgres"],
            "api": ["python", "-I", "-m", "omnis.serve"],
            "supervisor": ["python", "-I", "-m", "omnis.supervisor"],
            "migrate": [
                "python",
                "-I",
                "-m",
                "omnis.migrate",
                "--upgrade-t1" if getattr(self, "upgrading", False) else "--initialize",
            ],
            "reconcile": ["python", "-I", "-m", "omnis.stop_reconcile"],
        }[role]
        if restore:
            expected_command.append("--restore")
        state = mapping(item.get("State"))
        networks = mapping(net.get("Networks"))
        network_name = "none" if role == "runtime" else self.receipt.project + "_control"
        image_id = (
            self.pg_image
            if role == "db"
            else self.receipt.runtime_image_id
            if role == "runtime"
            else self.receipt.image_id
        )
        exited = state.get("Status") == "exited" and state.get("Running") is False
        if (
            item.get("Id") != ident
            or labels.get("com.docker.compose.project") != self.receipt.project
            or labels.get("com.docker.compose.service") != role
            or item.get("Image") != image_id
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
            or host.get("NetworkMode") != network_name
            or (
                role == "runtime" and host.get("Init") is not None and host.get("Init") is not False
            )
            or (set(networks) != {network_name} and not (exited and networks == {}))
            or host.get("PidMode") not in (None, "")
            or host.get("IpcMode") != "private"
            or any(
                host.get(key) not in (None, [])
                for key in ("CapAdd", "Devices", "DeviceRequests", "DeviceCgroupRules")
            )
            or host.get("Tmpfs") not in (None, {})
            or host.get("RestartPolicy") != {"Name": "no", "MaximumRetryCount": 0}
            or type(mapping(host.get("RestartPolicy")).get("MaximumRetryCount")) is not int
            or (
                role in {"migrate", "reconcile"}
                and (host.get("Binds") not in (None, []) or config.get("Volumes") not in (None, {}))
            )
            or actual != expected
            or len(mounts) != len(expected)
        ):
            raise StartError("CONTAINER_IDENTITY_MISMATCH", 3)
        control_ids = set(self.ids())
        if self.native:
            for cid in list(control_ids):
                candidate = self.inspect("container", cid)
                if (
                    candidate is not None
                    and mapping(mapping(candidate.get("Config")).get("Labels")).get(
                        "com.docker.compose.service"
                    )
                    == "runtime"
                ):
                    control_ids.remove(cid)
        network_id = self.network(control_ids)
        if networks and role != "runtime":
            endpoint = mapping(networks[network_name])
            # Created/exited endpoints can have no allocated NetworkID. In that
            # case bind the exact requested name/NetworkMode to the attested
            # network object; a running endpoint must carry that object's ID.
            unallocated = (
                state.get("Status") in ("created", "exited")
                and state.get("Running") is False
                and endpoint.get("NetworkID") == ""
            )
            if (
                network_id is None
                or (endpoint.get("NetworkID") != network_id and not unallocated)
                or endpoint.get("DriverOpts") not in (None, {})
                or endpoint.get("IPAMConfig") not in (None, {})
                or endpoint.get("Links") not in (None, [])
            ):
                raise StartError("NETWORK_IDENTITY_MISMATCH", 3)
            name = item.get("Name")
            if not isinstance(name, str) or not name.startswith("/") or len(name) < 2:
                raise StartError("CONTAINER_IDENTITY_MISMATCH", 3)
            aliases = {name[1:], ident, ident[:12]}
            if role in {"db", "api", "supervisor"}:
                aliases.add(role)  # Compose's service alias, not a custom alias.
            for key in ("Aliases", "DNSNames"):
                values = endpoint.get(key)
                if values is not None and (
                    not isinstance(values, list)
                    or any(not isinstance(value, str) or value not in aliases for value in values)
                ):
                    raise StartError("NETWORK_IDENTITY_MISMATCH", 3)
        if role != "db" and (
            config.get("User") != f"{os.getuid()}:{os.getgid()}"
            or host.get("ReadonlyRootfs") is not True
            or host.get("CapDrop") != ["ALL"]
            or host.get("SecurityOpt") != ["no-new-privileges:true"]
        ):
            raise StartError("CONTROL_CONFINEMENT_MISMATCH", 3)
        if not isinstance(image_id, str):
            raise StartError("IMAGE_IDENTITY_MISMATCH", 4)
        image = self.inspect("image", image_id)
        if image is None or image.get("Id") != image_id:
            raise StartError("IMAGE_IDENTITY_MISMATCH", 4)
        image_config = mapping(image.get("Config"))
        if role == "db" and (
            not isinstance(image_config.get("User"), str)
            or config.get("User") != image_config["User"]
            or host.get("ReadonlyRootfs") is not False
            or host.get("CapDrop") not in (None, [])
            or host.get("SecurityOpt") not in (None, [])
        ):
            raise StartError("DATABASE_CONFINEMENT_MISMATCH", 3)
        inherited = image_config.get("Env")
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
        elif role == "runtime":
            expected_env["OMNIS_RUNTIME_DIR"] = "/runtime"
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
        if role == "supervisor" and self.provider_settings:
            expected_env.update(
                OMNIS_VAULT_DIR="/vault",
                OMNIS_VAULT_KEY_DIR="/vault-key",
                OMNIS_MODEL_EGRESS_DIR="/vault",
            )
        if role == "supervisor" and self.native:
            expected_env["OMNIS_RUNTIME_DIR"] = "/runtime"
            if self.model_test:
                expected_env.update(
                    OMNIS_NATIVE_PREPARATION_CATALOG_ROOT="/catalog",
                    OMNIS_MANAGED_TASKS="1",
                    OMNIS_MODEL_TEST_SOURCE_ROOT="/opt/omnis/model-test",
                )
        if actual_env != expected_env:
            raise StartError("CONTROL_CONFIGURATION_MISMATCH", 4)
        if role == "reconcile" and (
            config.get("Tty") is not False
            or any(
                config.get(key) is not True
                for key in ("OpenStdin", "StdinOnce", "AttachStdin", "AttachStdout", "AttachStderr")
            )
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
