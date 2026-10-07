#!/usr/bin/env python3
"""Prepare the exact native pin without launching Hermes or importing its modules.

The source archive, exported core lock, reviewed inert overlay and adapter wheel
are independent inputs. Network is opt-in (--build) and restricted to lockfile
wheel URLs on files.pythonhosted.org. No source builds of dependencies occur.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tomllib
from urllib.parse import urlparse
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "integrations/hermes"
UPSTREAM = INTEGRATION / "upstream"
DEPENDENCY_PROJECT = INTEGRATION / "runtime-override"
PIN = json.loads((INTEGRATION / "pin.json").read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    with path.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256")
    return digest.hexdigest()


def require_hash(path: Path, expected: str, label: str) -> None:
    if sha256(path) != expected:
        raise ValueError(f"{label} SHA256 mismatch: {path.name}")


def dependency_inputs() -> dict:
    """Explicit three-package security override, never an upstream pin rewrite."""
    manifest = json.loads((DEPENDENCY_PROJECT / "provenance.json").read_text())
    fixes = {"anyio": ["4.12.1", "4.14.2"], "pyjwt": ["2.13.0", "2.15.0"],
             "urllib3": ["2.7.0", "2.8.0"]}
    original = {k: PIN[k] for k in ("commit", "source_archive_sha256", "pyproject_sha256",
                                   "uv_lock_sha256", "requirements_sha256")}
    if manifest["original"] != original or manifest["versions"] != fixes:
        raise ValueError("dependency override provenance mismatch")
    if set(manifest["files"]) != {"pyproject.toml", "uv.lock", "requirements-native.txt"}:
        raise ValueError("dependency override inputs mismatch")
    for name, digest in manifest["files"].items():
        require_hash(DEPENDENCY_PROJECT / name, digest, "dependency override")
    old = {p["name"]: p["version"] for p in tomllib.loads((UPSTREAM / "uv.lock").read_text())["package"]}
    selected = tomllib.loads((DEPENDENCY_PROJECT / "uv.lock").read_text())["package"]
    observed = {}
    for package in selected:
        if package.get("source", {}).get("registry"):
            name = package["name"]
            expected = fixes[name][1] if name in fixes else old.get(name)
            if package["version"] != expected:
                raise ValueError("dependency override contains unrelated version change")
            observed[name] = package["version"]
    if any(observed.get(name) != versions[1] for name, versions in fixes.items()):
        raise ValueError("dependency override omitted a security fix")
    return manifest


def apply_inert_overlay(source: Path) -> None:
    require_hash(UPSTREAM / "patch-manifest.json", PIN["patch_manifest_sha256"], "patch manifest")
    manifest = json.loads((UPSTREAM / "patch-manifest.json").read_text(encoding="utf-8"))
    require_hash(UPSTREAM / "omnis-inert.patch", PIN["patch_sha256"], "patch")
    # Verify ALL originals before the first alteration (no partial trusted overlay).
    for name, hashes in manifest["files"].items():
        require_hash(source / name, hashes["original_sha256"], "original")
        require_hash(UPSTREAM / "inert-source" / name, hashes["patched_sha256"], "patched")
    for name in manifest["files"]:
        shutil.copyfile(UPSTREAM / "inert-source" / name, source / name)


def prepare(archive: Path, output: Path) -> dict:
    require_hash(archive, PIN["source_archive_sha256"], "archive")
    require_hash(INTEGRATION / "requirements-native.txt", PIN["requirements_sha256"], "requirements")
    require_hash(UPSTREAM / "uv.lock", PIN["uv_lock_sha256"], "lock")
    dependencies = dependency_inputs()
    if output.exists():
        raise ValueError("output must be a new directory; no overwrite/adoption")
    # Pin verification precedes filesystem writes, and extraction never permits links/devices.
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        for member in members:
            if not (member.isfile() or member.isdir()) or member.name.startswith("/") or ".." in Path(member.name).parts:
                raise ValueError("unsafe source archive member")
        source = output / "source"
        source.mkdir(parents=True, mode=0o700)
        tar.extractall(source, members=members, filter="data")
    for name, field in [("uv.lock", "uv_lock_sha256"), ("pyproject.toml", "pyproject_sha256"), ("LICENSE", "license_sha256")]:
        require_hash(source / name, PIN[field], name)
    original_files = {str(p.relative_to(source)): sha256(p) for p in sorted(source.rglob("*")) if p.is_file()}
    apply_inert_overlay(source)
    selected_dependencies = output / "dependency-override"
    shutil.copytree(DEPENDENCY_PROJECT, selected_dependencies)
    shutil.copyfile(selected_dependencies / "requirements-native.txt", output / "requirements-native.txt")
    shutil.copyfile(UPSTREAM / "LICENSE", output / "LICENSE.hermes")
    manifest = {"schema_version": 1, "pin": PIN, "original_files": original_files,
                "patched_files": json.loads((UPSTREAM / "patch-manifest.json").read_text(encoding="utf-8"))["files"],
                "dependency_override": dependencies,
                "native_started": False, "provider_calls": "NOT_RUN", "assessment_ready": False}
    (output / "source-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def run(argv: list[str], output: Path, *, cwd: Path | None = None, python: Path | None = None) -> subprocess.CompletedProcess:
    # Never inherit provider keys, personal Hermes paths, config or package-index overrides.
    env = {"PATH": "/usr/bin:/bin", "HOME": str(output / "build-home"), "TMPDIR": str(output / "tmp"),
           "UV_CACHE_DIR": str(output / "uv-cache"), "UV_PYTHON_DOWNLOADS": "never",
           "SOURCE_DATE_EPOCH": str(PIN["source_date_epoch"]), "PYTHONHASHSEED": "0"}
    if python is not None:
        env["UV_PYTHON"] = str(python)
    for name in ["build-home", "tmp", "uv-cache"]:
        (output / name).mkdir(exist_ok=True, mode=0o700)
    result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=300)
    receipt = {"argv": argv, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    with (output / "commands.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(receipt) + "\n")
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {argv[0]}\n{result.stderr}")
    return result


SELECT_WHEELS = r'''
import json,sys,tomllib
from packaging.requirements import Requirement
from packaging.tags import sys_tags
from packaging.utils import parse_wheel_filename,canonicalize_name
spec=json.load(sys.stdin)
tags=list(sys_tags()); rank={t:i for i,t in enumerate(tags)}
lock=tomllib.loads(open(spec['lock'],encoding='utf-8').read())
packages={canonicalize_name(p['name']):p for p in lock['package']}
reqs=[]
for line in open(spec['requirements'],encoding='utf-8'):
 if line and not line[0].isspace() and not line.startswith('#'):
  req=Requirement(line.strip().rstrip('\\').strip())
  if req.marker is None or req.marker.evaluate(): reqs.append(req)
selected=[]
for req in reqs:
 package=packages[canonicalize_name(req.name)]
 if package['version'] not in req.specifier: raise ValueError('lock/export version mismatch')
 candidates=[]
 for wheel in package.get('wheels',[]):
  filename=wheel['url'].rsplit('/',1)[1]
  _,_,_,wtags=parse_wheel_filename(filename)
  score=min((rank[t] for t in wtags if t in rank),default=None)
  if score is not None: candidates.append((score,filename,wheel))
 if not candidates: raise ValueError('no compatible locked wheel for '+req.name)
 selected.append(min(candidates,key=lambda c:(c[0],c[1]))[2])
print(json.dumps(selected))
'''


def build_native(output: Path, python: Path, uv: Path) -> dict:
    require_hash(uv, PIN["uv_sha256"] if sha256(uv) == PIN["uv_sha256"] else PIN["reviewed_uv_helper_sha256"], "uv tool")
    # Executing the chosen interpreter is a prerequisite, not an implicit 3.14 fallback.
    actual = run([str(python), "-I", "-c", "import platform;print(platform.python_version())"], output).stdout.strip()
    if actual != PIN["python"]:
        raise ValueError("native build requires Python " + PIN["python"])
    build = output / "build-venv"
    run([str(uv), "venv", "--python", str(python), str(build)], output, python=python)
    lock = tomllib.loads((UPSTREAM / "uv.lock").read_text(encoding="utf-8"))
    # setuptools 83 includes its own bdist_wheel. No unpinned `wheel` build dependency is resolved.
    specs = []
    for name in ["setuptools", "packaging"]:
        package = next(p for p in lock["package"] if p["name"] == name)
        specs.append(f"{name}=={package['version']} --hash={package['wheels'][0]['hash']}\n")
    build_req = output / "requirements-build.txt"
    build_req.write_text("".join(specs), encoding="utf-8")
    bp = build / "bin/python"
    run([str(uv), "pip", "install", "--python", str(bp), "--no-deps", "--only-binary", ":all:", "--require-hashes", "-r", str(build_req)], output, python=python)
    dependencies = dependency_inputs()
    selected_lock = output / "dependency-override/uv.lock"
    require_hash(selected_lock, dependencies["files"]["uv.lock"], "selected dependency lock")
    require_hash(output / "requirements-native.txt", dependencies["files"]["requirements-native.txt"], "selected requirements")
    payload = {"lock": str(selected_lock), "requirements": str(output / "requirements-native.txt")}
    # stdin carries only reviewed file locations, never credentials.
    selection = subprocess.run([str(bp), "-I", "-c", SELECT_WHEELS], input=json.dumps(payload), capture_output=True, text=True, timeout=30, env={"PATH": "/usr/bin:/bin"})
    if selection.returncode:
        raise RuntimeError(selection.stderr)
    wheels = json.loads(selection.stdout)
    wheelhouse = output / "wheelhouse"
    wheelhouse.mkdir(mode=0o700)
    for wheel in wheels:
        url = wheel["url"]
        if urlparse(url).scheme != "https" or urlparse(url).hostname != "files.pythonhosted.org":
            raise ValueError("dependency URL is not official PyPI")
        target = wheelhouse / url.rsplit("/", 1)[1]
        with urlopen(url, timeout=60) as response, target.open("wb") as file:
            if urlparse(response.url).hostname != "files.pythonhosted.org":
                raise ValueError("dependency redirected outside official PyPI")
            shutil.copyfileobj(response, file)
        require_hash(target, wheel["hash"].removeprefix("sha256:"), "dependency wheel")
    np = output / "native-venv/bin/python"
    run([str(uv), "venv", "--python", str(python), str(output / "native-venv")], output, python=python)
    run([str(uv), "pip", "install", "--python", str(np), "--no-index", "--find-links", str(wheelhouse), "--no-deps", "--only-binary", ":all:", "--require-hashes", "-r", str(output / "requirements-native.txt")], output, python=python)
    # Upstream setup.py explicitly prohibits non-Nix native wheels. Preserve its
    # supported source layout; only the independently authored Omnis adapter is a wheel.
    runtime_source = output / "runtime-source"
    runtime_source.mkdir(mode=0o700)
    packages = ["agent", "tools", "hermes_cli", "gateway", "tui_gateway", "cron", "acp_adapter", "plugins", "providers", "hermes_platform"]
    assets = ["locales", "skills", "optional-skills", "optional-mcps", "web_dist", "tui_dist"]
    for name in packages + assets:
        source = output / "source" / name
        if source.is_dir():
            shutil.copytree(source, runtime_source / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for source in (output / "source").iterdir():
        if source.is_file() and (source.suffix == ".py" or source.name in ["pyproject.toml", "LICENSE"]):
            shutil.copyfile(source, runtime_source / source.name)
    site = output / "native-venv/lib/python3.13/site-packages"
    (site / "omnis-native-source.pth").write_text(str(runtime_source) + "\n", encoding="utf-8")
    (output / "requirements-artifacts.txt").write_text("# Separate Omnis adapter input required for OCI.\n", encoding="utf-8")
    files = {str(p.relative_to(runtime_source)): sha256(p) for p in sorted(runtime_source.rglob("*")) if p.is_file()}
    result = {"schema_version": 1, "python": actual, "dependency_wheels": wheels,
              "native_source_files": files, "native_distribution": "supported source layout (not a Nix wheel)",
              "dependency_override": dependencies,
              "native_started": False, "adapter_injected": False}
    (output / "build-manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def inject_adapter(output: Path, wheel: Path, expected_sha256: str) -> None:
    require_hash(wheel, expected_sha256, "adapter")
    if not wheel.name.startswith("omnis_hermes-") or wheel.suffix != ".whl":
        raise ValueError("expected the separate omnis_hermes wheel")
    with zipfile.ZipFile(wheel) as file:
        if "omnis_hermes/runtime_host.py" not in file.namelist():
            raise ValueError("adapter runtime_host absent")
    target = output / "wheelhouse" / wheel.name
    shutil.copyfile(wheel, target)
    with (output / "requirements-artifacts.txt").open("a", encoding="utf-8") as file:
        file.write(f"{target.name} --hash=sha256:{expected_sha256}\n")
    manifest = json.loads((output / "build-manifest.json").read_text(encoding="utf-8"))
    manifest.update(adapter_injected=True, adapter_wheel={"name": target.name, "sha256": expected_sha256})
    (output / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--python", type=Path)
    parser.add_argument("--uv", type=Path)
    parser.add_argument("--adapter-wheel", type=Path)
    parser.add_argument("--adapter-sha256")
    args = parser.parse_args()
    if args.build and (not args.python or not args.uv):
        parser.error("--build requires explicit --python and --uv")
    if args.adapter_wheel and (not args.build or not args.adapter_sha256):
        parser.error("adapter input requires --build and explicit --adapter-sha256")
    prepare(args.source_archive, args.output)
    if args.build:
        build_native(args.output, args.python, args.uv)
    if args.adapter_wheel:
        inject_adapter(args.output, args.adapter_wheel, args.adapter_sha256)
    print(json.dumps({"prepared": str(args.output), "native_started": False, "adapter_injected": bool(args.adapter_wheel)}))


if __name__ == "__main__":
    main()
