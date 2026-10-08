"""Independent B06a CLI consumer; never imports mutable production handlers.

The subprocess loads only this checkout's source, not the shared editable install.
Golden data is evaluator-only. This is not an OS/network sandbox or a DB receipt.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[4]
FIXTURES = Path(__file__).resolve().parent
PACKAGE_KEY = "recon-mapping-contract"
MODULE = "omnis.modules.settings.skill_catalog"
BOOTSTRAP = (
    "import pathlib,runpy,sys;sys.path.insert(0,sys.argv.pop(1));"
    "audit_path=pathlib.Path(sys.argv.pop(1));"
    'exec("def deny_effect(event,args):\\n'
    " if event in ('socket.connect','socket.bind','socket.getaddrinfo',"
    "'subprocess.Popen','os.system'):\\n"
    "  with audit_path.open('a',encoding='utf-8') as sink: sink.write(event+'\\\\n')\\n"
    "  raise RuntimeError('B06A_EFFECT_DENIED')\");"
    "sys.addaudithook(deny_effect);"
    f"runpy.run_module({MODULE!r},run_name='__main__')"
)
MARKER = "B06A_SYNTHETIC_PRIVATE_MARKER"


def mapping(value: object) -> dict[str, object]:
    assert isinstance(value, dict), "Expected an object in the normative seed"
    assert all(type(key) is str for key in value)
    return {key: item for key, item in value.items()}


def sequence(value: object) -> list[object]:
    assert isinstance(value, list), "Expected a list in the normative seed"
    return list(value)


def yaml_object(path: Path) -> dict[str, object]:
    value: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    return mapping(value)


def write_yaml(path: Path, value: dict[str, object]) -> None:
    path.write_text(yaml.safe_dump(value, sort_keys=False, allow_unicode=True), encoding="utf-8")


def reject_constant(value: str) -> object:
    raise ValueError(f"Non-JSON constant: {value}")


def unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON diagnostic key")
        result[key] = value
    return result


def strict_json(text: str) -> dict[str, object]:
    assert len(text.encode("utf-8")) <= 1048576, "Unbounded CLI response"
    value: object = json.loads(text, object_pairs_hook=unique_keys, parse_constant=reject_constant)
    return mapping(value)


@dataclass(frozen=True)
class CatalogSeed:
    directory: Path
    package: Path
    profile: Path

    @property
    def manifest(self) -> Path:
        return self.package / "omnis.yaml"

    def cli(
        self, verb: str, *extra: str, packages: tuple[Path, ...] = ()
    ) -> subprocess.CompletedProcess[str]:
        roots = packages or (self.package,)
        args = [verb]
        for root in roots:
            args.extend(("--package", str(root)))
        args.extend(("--profile", str(self.profile), *extra))
        return invoke(self.directory, *args)

    def compile(self) -> dict[str, object]:
        return success(self.cli("compile"), "STATIC_PASS")

    def input(self, value: object) -> Path:
        path = self.directory / "synthetic-input.json"
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def evaluate(self, value: object) -> dict[str, object]:
        path = self.input(value)
        return success(self.cli("evaluate", "--input", str(path)), "PURE_PASS")


def invoke(directory: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    home = directory / "home"
    home.mkdir(exist_ok=True)
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(home),
        "TMPDIR": str(directory),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONPATH": str(ROOT / "api/src"),
    }
    audit_path = directory / "attempted-effects.log"
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            BOOTSTRAP,
            str(ROOT / "api/src"),
            str(audit_path),
            *arguments,
        ],
        cwd=directory,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert not audit_path.exists() or audit_path.read_text(encoding="utf-8") == "", (
        "PURE consumer attempted a Python-audited network/process effect"
    )
    return result


def success(result: subprocess.CompletedProcess[str], status: str) -> dict[str, object]:
    assert result.returncode == 0, f"CLI failed ({result.returncode}): {result.stderr}"
    assert result.stderr == "", "Success must not conceal a failure diagnostic"
    payload = strict_json(result.stdout)
    assert payload["status"] == status
    assert payload["resolution"] == "NO_MODEL"
    for name in ("material_digest", "resolved_index_digest"):
        digest = payload[name]
        assert type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest)
    if "effective" in payload:
        assert payload["effective"] is None
    return payload


def blocked(result: subprocess.CompletedProcess[str]) -> str:
    assert result.returncode == 2, f"Not a contract refusal: {result.returncode}, {result.stderr}"
    assert result.stdout == "", "Blocked consumer emitted successful data"
    assert len(result.stderr.encode("utf-8")) <= 4096
    payload = strict_json(result.stderr)
    assert set(payload) == {"status", "reason"}
    assert payload["status"] == "BLOCKED"
    reason = payload["reason"]
    assert type(reason) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{2,95}", reason)
    assert reason not in {"ERROR", "UNKNOWN", "INTERNAL_ERROR", "EXCEPTION"}
    assert MARKER not in result.stderr
    assert "Traceback" not in result.stderr
    return reason


def stable_block(
    seed: CatalogSeed, verb: str = "compile", *extra: str, packages: tuple[Path, ...] = ()
) -> None:
    first = blocked(seed.cli(verb, *extra, packages=packages))
    second = blocked(seed.cli(verb, *extra, packages=packages))
    assert first == second, "Same invalid bytes must produce the same stable reason code"


@pytest.fixture
def seed() -> Iterator[CatalogSeed]:
    scratch = Path(os.environ["TMPDIR"])
    assert scratch.is_absolute() and scratch.is_dir()
    source = ROOT / "skills" / PACKAGE_KEY
    profile = ROOT / "profiles" / f"{PACKAGE_KEY}.yaml"
    assert source.is_dir(), "B06a seed missing: integrate DevA before GREEN"
    assert profile.is_file(), "B06a profile missing: integrate DevA before GREEN"
    with tempfile.TemporaryDirectory(prefix="b06a-consumer-", dir=scratch) as name:
        directory = Path(name)
        package = directory / PACKAGE_KEY
        shutil.copytree(source, package, symlinks=True)
        copied_profile = directory / "profile.yaml"
        shutil.copyfile(profile, copied_profile)
        yield CatalogSeed(directory, package, copied_profile)


def declared_paths(seed: CatalogSeed) -> list[str]:
    manifest = yaml_object(seed.manifest)
    items = ["SKILL.md", "omnis.yaml"]
    for field in ("procedures", "support_files"):
        for path in sequence(manifest[field]):
            assert type(path) is str
            items.append(path)
    assert len(items) == len(set(items)), "Seed has duplicate declared paths"
    return sorted(items, key=lambda item: item.encode("utf-8"))


def release_digest(seed: CatalogSeed) -> str:
    """Normative independent §9.4 preimage, for integration's public index check."""
    entries: list[dict[str, object]] = []
    for path in declared_paths(seed):
        data = (seed.package / path).read_bytes()
        entries.append(
            {"path": path, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
        )
    preimage = json.dumps(entries, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


def source_bytes(seed: CatalogSeed) -> dict[str, str]:
    paths = declared_paths(seed)
    hashes = {
        path: hashlib.sha256((seed.package / path).read_bytes()).hexdigest() for path in paths
    }
    hashes["@profile"] = hashlib.sha256(seed.profile.read_bytes()).hexdigest()
    return hashes


def procedure(seed: CatalogSeed) -> tuple[Path, dict[str, object]]:
    manifest = yaml_object(seed.manifest)
    paths = sequence(manifest["procedures"])
    assert len(paths) == 1 and type(paths[0]) is str, "Expected the single CONTRACT seed"
    path = seed.package / paths[0]
    return path, yaml_object(path)


def schema_path(seed: CatalogSeed) -> Path:
    manifest = yaml_object(seed.manifest)
    for value in sequence(manifest["file_bindings"]):
        binding = mapping(value)
        if binding["entity_kind"] == "schema":
            path = binding["path"]
            assert type(path) is str
            return seed.package / path
    raise AssertionError("Normative seed has no explicit schema binding")
