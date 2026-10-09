"""Finite installed document loader. Never constructs an agent or provider client.

The real loader's readiness calls load_env on the absent *fresh* home/.env;
preprocess=False does not imply that the credential reader was never invoked.
"""

import importlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Protocol, cast
from uuid import UUID

from .native_preparation_contract import (
    BASE_COMMIT,
    LIMITS,
    PATCH_SHA256,
    SKILLS_SHA256,
    BundleFile,
    canonical,
    digest,
    loads,
    obj,
    reject,
    validate_payload,
    validate_result,
)

PATHS = {
    "HOME": "os-home",
    "HERMES_HOME": "home",
    "CODEX_HOME": "codex",
    "XDG_CONFIG_HOME": "xdg/config",
    "XDG_CACHE_HOME": "xdg/cache",
    "XDG_STATE_HOME": "xdg/state",
    "XDG_DATA_HOME": "xdg/data",
    "TMPDIR": "tmp",
    "HERMES_MANAGED_DIR": "managed-empty",
    "TERMINAL_CWD": "work",
}


class NativeLoader(Protocol):
    __file__: str

    def _skill_search_dirs(self) -> tuple[list[Path], list[Path], Path]: ...

    def skill_view(
        self,
        name: str,
        file_path: str | None = None,
        task_id: str | None = None,
        preprocess: bool = True,
    ) -> str: ...


def regular_bytes(path: Path, maximum: int) -> bytes:
    for parent in path.parents:
        if parent.is_symlink():
            raise reject()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > maximum:
            raise reject()
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
        fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if len(raw) > maximum or any(getattr(info, k) != getattr(after, k) for k in fields):
            raise reject()
        return raw


def isolated_root() -> Path:
    if (
        not sys.flags.isolated
        or not sys.dont_write_bytecode
        or len(sys.argv) != 1
        or sys.executable != "/opt/hermes/venv/bin/python"
        or os.getuid() == 0
    ):
        raise reject()
    home = Path(os.environ.get("HERMES_HOME", ""))
    root = home.parent
    if root.parent != Path("/state/tmp") or not root.name.startswith("native-prep-"):
        raise reject()
    token = root.name.removeprefix("native-prep-")
    if str(UUID(token)) != token or home != root / "home" or root.resolve() != root:
        raise reject()
    for key, relative in PATHS.items():
        path = root / relative
        info = path.lstat()
        if (
            os.environ.get(key) != str(path)
            or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700
            or path.resolve() != path
            or any(path.iterdir())
        ):
            raise reject()
    if Path.cwd() != root / "work":
        raise reject()
    return root


def stage(skills: Path, files: tuple[BundleFile, ...]) -> None:
    # Caller owns an exclusive empty home. Neither filenames nor content are code.
    skills.mkdir(mode=0o700)
    directories = {skills}
    for file in files:
        target = skills / file.native_name / file.path
        for directory in reversed(target.parents):
            if directory == skills or directory.is_relative_to(skills):
                if directory not in directories:
                    directory.mkdir(mode=0o700)
                    directories.add(directory)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
        with os.fdopen(fd, "wb") as output:
            output.write(file.raw)
        target.chmod(0o400)
    for directory in directories:
        directory.chmod(0o500)
    verify_tree(skills, files)


def verify_tree(skills: Path, files: tuple[BundleFile, ...]) -> None:
    expected = {skills / file.native_name / file.path: file.raw for file in files}
    directories = {skills}
    for path in expected:
        directories.update(p for p in path.parents if p.is_relative_to(skills))
    actual: set[Path] = set()
    pending = [skills]
    while pending:
        directory = pending.pop()
        info = directory.lstat()
        if (
            directory not in directories
            or not stat.S_ISDIR(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o500
        ):
            raise reject()
        actual.add(directory)
        for entry in directory.iterdir():
            info = entry.lstat()
            if stat.S_ISDIR(info.st_mode):
                pending.append(entry)
            elif (
                entry not in expected
                or not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o400
                or regular_bytes(entry, LIMITS["max_file_bytes"]) != expected[entry]
            ):
                raise reject()
            else:
                actual.add(entry)
    if actual != directories | set(expected):
        raise reject()


def provenance() -> dict[str, str]:
    manifest = json.loads(
        regular_bytes(Path("/opt/hermes/provenance/source-manifest.json"), 4_194_304)
    )
    if manifest["pin"]["commit"] != BASE_COMMIT or manifest["pin"]["patch_sha256"] != PATCH_SHA256:
        raise reject()
    actual = digest(regular_bytes(Path("/opt/hermes/source/tools/skills_tool.py"), 131072))
    if actual != SKILLS_SHA256:
        raise reject()
    return {
        "base_commit": BASE_COMMIT,
        "patch_sha256": PATCH_SHA256,
        "skills_tool_sha256": actual,
        "worker_revision": digest(regular_bytes(Path(__file__), 131072)),
    }


def checked_native(raw: str, file: BundleFile, skills: Path) -> None:
    value = loads(raw, LIMITS["max_worker_result_bytes"])
    main = file.path == "SKILL.md"
    keys = {"success", "name", "content", "_source_path"}
    keys |= (
        {
            "description",
            "tags",
            "related_skills",
            "path",
            "skill_dir",
            "org_provenance",
            "linked_files",
            "usage_hint",
            "required_environment_variables",
            "required_commands",
            "missing_required_environment_variables",
            "missing_credential_files",
            "missing_required_commands",
            "setup_needed",
            "setup_skipped",
            "readiness_status",
        }
        if main
        else {"file", "file_type"}
    )
    value = obj(value, keys)
    target = skills / file.native_name / file.path
    if (
        value["success"] is not True
        or value["name"] != file.native_name
        or value["_source_path"] != str(target)
        or type(value["content"]) is not str
        or value["content"].encode("utf-8") != file.raw
    ):
        raise reject()
    if main:
        if (
            value["path"] != f"{file.native_name}/SKILL.md"
            or value["skill_dir"] != str(target.parent)
            or value["org_provenance"] is not None
            or value["readiness_status"] != "available"
            or value["setup_needed"] is not False
            or value["setup_skipped"] is not False
            or any(
                value[key] != []
                for key in (
                    "required_environment_variables",
                    "required_commands",
                    "missing_required_environment_variables",
                    "missing_credential_files",
                    "missing_required_commands",
                )
            )
        ):
            raise reject()
    elif value["file"] != file.path or value["file_type"] != target.suffix:
        raise reject()


def prepare(payload: object, root: Path) -> dict[str, object]:
    ref, files = validate_payload(payload)
    skills = root / "home" / "skills"
    stage(skills, files)
    native = provenance()
    # These imports occur only after installed/env guards, validation and staging.
    loader = cast(NativeLoader, importlib.import_module("tools.skills_tool"))
    if Path(loader.__file__) != Path("/opt/hermes/source/tools/skills_tool.py"):
        raise reject()
    for file in files:
        if loader._skill_search_dirs() != ([], [skills], skills):
            raise reject()
        raw = loader.skill_view(
            file.native_name,
            file_path=None if file.path == "SKILL.md" else file.path,
            task_id=None,
            preprocess=False,
        )
        checked_native(raw, file, skills)
    verify_tree(skills, files)
    # Reader invocation is expected; successful persistence of a secret/config is not.
    if any((root / "home" / name).exists() for name in (".env", "auth.json", "config.yaml")):
        raise reject()
    result = {
        "schema_version": 1,
        "status": "PREPARED",
        "bundle_ref": ref,
        "loader": "tools.skills_tool.skill_view",
        "preprocess": False,
        "loaded": [file.loaded() for file in files],
        "native": native,
    }
    return validate_result(result, payload, native["worker_revision"])


def main() -> int:
    try:
        root = isolated_root()
        raw = sys.stdin.buffer.readline(LIMITS["max_runtime_request_bytes"] + 1)
        if not raw.endswith(b"\n") or sys.stdin.buffer.read(1):
            raise reject()
        payload = loads(raw, LIMITS["max_runtime_request_bytes"])
        result = prepare(payload, root)
        sys.stdout.buffer.write(canonical(result) + b"\n")
        sys.stdout.buffer.flush()
        return 0
    except Exception:
        # Final process boundary: never expose imported exceptions, paths or payload.
        print("NATIVE_PREPARATION_DENIED", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
