"""Explicit, host-only image installation from the verified release bundle."""

import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .instance import private_dir, private_file, unique_pairs
from .release import _installed_pointer, _manifest, publish_directory

_BASE = "python:3.13.15-slim-bookworm@sha256:3e2de9c40ca4e3d73240059f9d48baff27908f10293e985a2f382a0378e6df4a"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_PROJECT = re.compile(r"omnis-local-[0-9a-f]{32}\Z")


class ImageInstallError(ValueError):
    """No image is adopted or declared installed without local ownership readback."""


@dataclass(frozen=True)
class ImageReceipt:
    project: str
    tag: str
    image_id: str
    manifest_sha256: str
    docker_host: str
    docker_id: str


def _run(
    *args: str, cwd: Path, timeout: int = 15, host: str | None = None
) -> subprocess.CompletedProcess[str]:
    command = ["docker"]
    if host is not None:
        command.extend(["--host", host])
    command.extend(args)
    return subprocess.run(
        command,
        cwd=cwd,
        env={"PATH": os.environ.get("PATH", "")},
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _one_image(output: str) -> dict[str, object]:
    raw: object = json.loads(output, object_pairs_hook=unique_pairs)
    if not isinstance(raw, list) or len(raw) != 1 or not isinstance(raw[0], dict):
        raise ImageInstallError("Unexpected image inspect response")
    result: dict[str, object] = {}
    for key, value in raw[0].items():
        if not isinstance(key, str):
            raise ImageInstallError("Invalid image inspect key")
        result[key] = value
    return result


def _image(tag: str, bundle: Path, host: str) -> dict[str, object] | None:
    response = _run("image", "inspect", tag, cwd=bundle, host=host)
    if response.returncode:
        if "No such image" in response.stderr or "No such object" in response.stderr:
            return None
        raise ImageInstallError("Cannot verify local image")
    return _one_image(response.stdout)


def _validate_image(
    tag: str, bundle: Path, project: str, manifest_sha: str, *, host: str
) -> str | None:
    result = _image(tag, bundle, host)
    if result is None:
        return None
    config = result.get("Config")
    if not isinstance(config, dict) or not isinstance(config.get("Labels"), dict):
        raise ImageInstallError("Invalid image metadata")
    labels = config["Labels"]
    image_id = result.get("Id")
    if (
        not isinstance(image_id, str)
        or not _DIGEST.fullmatch(image_id)
        or result.get("Architecture") != "amd64"
        or config.get("User") != "65532:65532"
        or labels.get("org.omnis.project") != project
        or labels.get("org.omnis.bundle_sha256") != manifest_sha
    ):
        raise ImageInstallError("Image identity mismatch")
    return image_id


def _record(path: Path, manifest_sha: str, *, complete: bool) -> ImageReceipt | None:
    try:
        raw: object = json.loads(private_file(path, limit=1024), object_pairs_hook=unique_pairs)
    except FileNotFoundError:
        return None
    if not isinstance(raw, dict) or set(raw) != (
        {
            "format",
            "release",
            "project",
            "tag",
            "manifest_sha256",
            "image_id",
            "docker_host",
            "docker_id",
        }
        if complete
        else {"format", "release", "project", "tag", "manifest_sha256", "docker_host", "docker_id"}
    ):
        raise ImageInstallError("Invalid image receipt")
    project = raw["project"]
    tag = raw["tag"]
    digest = raw["manifest_sha256"]
    image_id = raw.get("image_id", "")
    docker_host = raw["docker_host"]
    docker_id = raw["docker_id"]
    if (
        type(raw["format"]) is not int
        or raw["format"] != 1
        or raw["release"] != "0.1.0"
        or not isinstance(project, str)
        or not _PROJECT.fullmatch(project)
        or tag != f"omnis-control-{project.removeprefix('omnis-local-')}:0.1.0"
        or not isinstance(digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", digest)
        or not isinstance(image_id, str)
        or complete
        and not _DIGEST.fullmatch(image_id)
        or not isinstance(docker_host, str)
        or not docker_host.startswith("unix://")
        or not docker_host[7:].startswith("/")
        or not isinstance(docker_id, str)
        or not re.fullmatch(r"[A-Za-z0-9-]{8,128}", docker_id)
        or digest != manifest_sha
    ):
        raise ImageInstallError("Image receipt/release mismatch")
    _sync_parent(path)
    return ImageReceipt(project, tag, image_id, digest, docker_host, docker_id)


def _sync_parent(path: Path) -> None:
    parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def _put_record(path: Path, receipt: ImageReceipt, *, complete: bool) -> None:
    record: dict[str, object] = {
        "format": 1,
        "release": "0.1.0",
        "project": receipt.project,
        "tag": receipt.tag,
        "manifest_sha256": receipt.manifest_sha256,
        "docker_host": receipt.docker_host,
        "docker_id": receipt.docker_id,
    }
    if complete:
        record["image_id"] = receipt.image_id
    fd, temporary = tempfile.mkstemp(prefix=".image-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write((json.dumps(record, sort_keys=True) + "\n").encode())
            output.flush()
            os.fsync(output.fileno())
        publish_directory(Path(temporary), path)  # Atomic no-replace rename, one link.
    finally:
        Path(temporary).unlink(missing_ok=True)
    _sync_parent(path)  # The new name must survive a power loss before build/ACK.


def _checked_socket(endpoint: str) -> str:
    if not endpoint.startswith("unix://"):
        raise ImageInstallError("Only a local Docker Unix socket is permitted")
    path = Path(endpoint[7:])
    if not path.is_absolute() or str(path) != os.path.normpath(path):
        raise ImageInstallError("Noncanonical Docker socket")
    # /var/run may be a root-owned link to /run, but a same-UID link is mutable.
    protected = False
    for ancestor in (*reversed(path.parents), path):
        info = ancestor.lstat()
        if stat.S_ISLNK(info.st_mode):
            if info.st_uid != 0 or not stat.S_ISDIR(ancestor.parent.stat().st_mode):
                raise ImageInstallError("Replaceable Docker socket link")
        elif ancestor != path and (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid not in {0, os.getuid()}
            or info.st_mode & 0o002
            or info.st_mode & 0o020
            and not protected
        ):
            raise ImageInstallError("Replaceable Docker socket ancestor")
        if info.st_uid == os.getuid() and info.st_mode & 0o077 == 0:
            protected = True
    resolved = path.resolve(strict=True)
    if resolved != path:
        # Check the resolved path as well, not just the link chain.
        protected = False
        for ancestor in (*reversed(resolved.parents), resolved):
            info = ancestor.lstat()
            if ancestor != resolved and (
                not stat.S_ISDIR(info.st_mode)
                or info.st_uid not in {0, os.getuid()}
                or info.st_mode & 0o002
                or info.st_mode & 0o020
                and not protected
            ):
                raise ImageInstallError("Replaceable Docker socket target")
            if info.st_uid == os.getuid() and info.st_mode & 0o077 == 0:
                protected = True
    info = resolved.lstat()
    if (
        not stat.S_ISSOCK(info.st_mode)
        or info.st_uid not in {0, os.getuid()}
        or info.st_mode & 0o002
    ):
        raise ImageInstallError("Unsafe Docker socket")
    return f"unix://{resolved}"


def _docker_id(bundle: Path, host: str) -> str:
    response = _run("info", "--format", "{{.ID}}", cwd=bundle, host=host)
    value = response.stdout.strip()
    if response.returncode or not re.fullmatch(r"[A-Za-z0-9-]{8,128}", value):
        raise ImageInstallError("Docker daemon identity unavailable")
    return value


def _preflight(bundle: Path) -> str:
    if any(key.startswith("DOCKER_") for key in os.environ):
        raise ImageInstallError("Ambient Docker overrides are forbidden")
    context = _run("context", "show", cwd=bundle)
    if context.returncode or not context.stdout.strip():
        raise ImageInstallError("Local Docker context unavailable")
    endpoint = _run(
        "context",
        "inspect",
        context.stdout.strip(),
        "--format",
        '{{(index .Endpoints "docker").Host}}',
        cwd=bundle,
    )
    if endpoint.returncode:
        raise ImageInstallError("Only a local Docker Unix socket is permitted")
    return _checked_socket(endpoint.stdout.strip())


def _base_image(bundle: Path, host: str) -> None:
    base = _run("image", "inspect", _BASE, cwd=bundle, host=host)
    if base.returncode:
        raise ImageInstallError("Pull the pinned Python image explicitly before image install")
    info = _one_image(base.stdout)
    digests = info.get("RepoDigests")
    if (
        info.get("Architecture") != "amd64"
        or not isinstance(digests, list)
        or "python@sha256:3e2de9c40ca4e3d73240059f9d48baff27908f10293e985a2f382a0378e6df4a"
        not in digests
    ):
        raise ImageInstallError("Pinned Python base identity mismatch")


def install_control_image(data_home: Path) -> ImageReceipt:
    """Build only on explicit operator action; reconcile one recorded intent on retry."""
    try:
        root = data_home / "omnis"
        private_dir(root)
        if not _installed_pointer(root / "installed.json"):
            raise ImageInstallError("Install the release bundle first")
        bundle = root / "releases/0.1.0"
        manifest, _ = _manifest(bundle)
        manifest_sha = hashlib.sha256(manifest).hexdigest()
        fd = os.open(root / "install.lock", os.O_RDWR | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_nlink != 1
            ):
                raise ImageInstallError("Unsafe install lock")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return _install_locked(root, bundle, manifest_sha)
        finally:
            os.close(fd)
    except (OSError, ValueError, UnicodeError, RecursionError, subprocess.SubprocessError) as exc:
        raise ImageInstallError("Image installation refused") from exc


def _install_locked(root: Path, bundle: Path, manifest_sha: str) -> ImageReceipt:
    host = _preflight(bundle)
    docker_id = _docker_id(bundle, host)
    receipt_path = root / "image.json"
    intent_path = root / "image-installing.json"
    prior = _record(receipt_path, manifest_sha, complete=True)
    if prior is not None:
        if prior.docker_host != host or prior.docker_id != docker_id:
            raise ImageInstallError("Installed image belongs to another Docker endpoint")
        if (
            _validate_image(prior.tag, bundle, prior.project, manifest_sha, host=host)
            != prior.image_id
        ):
            raise ImageInstallError("Installed image unavailable")
        if _docker_id(bundle, host) != docker_id:
            raise ImageInstallError("Docker daemon changed during image verification")
        return prior
    intent = _record(intent_path, manifest_sha, complete=False)
    if intent is not None:
        # An absent tag does not prove a timed-out daemon build will not publish it later.
        raise ImageInstallError("Interrupted image install requires manual recovery")
    _base_image(bundle, host)
    project = f"omnis-local-{uuid4().hex}"
    intent = ImageReceipt(
        project,
        f"omnis-control-{project.removeprefix('omnis-local-')}:0.1.0",
        "",
        manifest_sha,
        host,
        docker_id,
    )
    if _validate_image(intent.tag, bundle, intent.project, manifest_sha, host=host) is not None:
        raise ImageInstallError("Image tag already exists")
    if _docker_id(bundle, host) != docker_id:
        raise ImageInstallError("Docker daemon changed before image build")
    _put_record(intent_path, intent, complete=False)
    result = _run(
        "build",
        "--platform",
        "linux/amd64",
        "--pull=false",
        "--label",
        f"org.omnis.project={intent.project}",
        "--label",
        f"org.omnis.bundle_sha256={manifest_sha}",
        "-f",
        str(bundle / "ops/Dockerfile"),
        "-t",
        intent.tag,
        str(bundle),
        cwd=bundle,
        timeout=300,
        host=host,
    )
    if result.returncode:
        # A failed build can still leave a tag. Never turn it into success.
        candidate = _validate_image(intent.tag, bundle, intent.project, manifest_sha, host=host)
        if candidate is not None:
            raise ImageInstallError("Control image build outcome uncertain; recovery required")
        raise ImageInstallError("Control image build failed")
    image_id = _validate_image(intent.tag, bundle, intent.project, manifest_sha, host=host)
    if image_id is None:
        raise ImageInstallError("Build acknowledged without image readback")
    if _docker_id(bundle, host) != docker_id:
        raise ImageInstallError("Docker daemon changed during image build")
    final = ImageReceipt(intent.project, intent.tag, image_id, manifest_sha, host, docker_id)
    _put_record(receipt_path, final, complete=True)
    if _record(receipt_path, manifest_sha, complete=True) != final:
        raise ImageInstallError("Image receipt not durable")
    intent_path.unlink()
    return final
