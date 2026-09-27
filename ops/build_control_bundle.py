"""Assemble a local P0 bundle from explicit locked wheels and hashed web assets."""

import argparse
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import is_zipfile

from omnis_cli.instance import private_dir, unique_pairs
from omnis_cli.release import _bytes, _manifest, _put, publish_directory


class BundleError(ValueError):
    """Input did not match the locked release boundary."""


def _canonical_file(path: Path) -> bytes:
    if not path.is_absolute() or path.resolve() != path:
        raise BundleError("Noncanonical input")
    return _bytes(path)


def build_bundle(
    api_wheel: Path,
    cli_wheel: Path,
    requirements: Path,
    web_root: Path,
    output: Path,
) -> None:
    if not output.is_absolute() or output.exists() or output.is_symlink():
        raise BundleError("Output must be a new absolute directory")
    private_dir(output.parent)
    if not web_root.is_absolute() or web_root.resolve() != web_root:
        raise BundleError("Noncanonical web root")
    root_info = web_root.lstat()
    if not stat.S_ISDIR(root_info.st_mode):
        raise BundleError("Missing web build")
    expected_api = "omnis_api-0.1.0-py3-none-any.whl"
    expected_cli = "omnis_cli-0.1.0-py3-none-any.whl"
    if api_wheel.name != expected_api or cli_wheel.name != expected_cli:
        raise BundleError("Wrong pinned wheel version")
    api_content = _canonical_file(api_wheel)
    cli_content = _canonical_file(cli_wheel)
    if not is_zipfile(io.BytesIO(api_content)) or not is_zipfile(io.BytesIO(cli_content)):
        raise BundleError("Missing wheel archive")
    locked = _canonical_file(requirements)
    uv = os.environ.get("OMNIS_UV")
    if not uv or not Path(uv).is_absolute() or Path(uv).resolve() != Path(uv):
        raise BundleError("Explicit pinned uv is required")
    version = subprocess.run(
        [uv, "--version"],
        env={"PATH": os.environ.get("PATH", "")},
        capture_output=True,
        timeout=5,
        check=True,
    )
    if version.stdout.strip() != b"uv 0.12.19 (x86_64-unknown-linux-gnu)":
        raise BundleError("Wrong uv release")
    export = subprocess.run(
        [
            uv,
            "export",
            "--locked",
            "--no-config",
            "--directory",
            str(Path(__file__).resolve().parents[1] / "api"),
            "--no-dev",
            "--no-emit-project",
            "--no-header",
            "--no-annotate",
            "--format",
            "requirements-txt",
        ],
        env={"PATH": os.environ.get("PATH", "")},
        capture_output=True,
        timeout=30,
        check=True,
    )
    if locked != export.stdout or b"--hash=sha256:" not in locked:
        raise BundleError("Requirements do not match the locked API export")
    source = _canonical_file(web_root / "omnis-web.json")
    raw: object = json.loads(source, object_pairs_hook=unique_pairs)
    if not isinstance(raw, dict) or set(raw) != {"version", "files"}:
        raise BundleError("Invalid web manifest")
    if type(raw["version"]) is not int or raw["version"] != 1 or not isinstance(raw["files"], dict):
        raise BundleError("Unsupported web manifest")
    web_files = raw["files"]
    if (
        "index.html" not in web_files
        or not 2 <= len(web_files) <= 127
        or not any(name.endswith(".js") for name in web_files)
    ):
        raise BundleError("Incomplete web build")
    payloads = {
        f"api/{expected_api}": api_content,
        f"cli/{expected_cli}": cli_content,
        "api/requirements.txt": locked,
        "web/omnis-web.json": source,
    }
    for name, digest in web_files.items():
        if not isinstance(name, str) or (name != "index.html" and not name.startswith("assets/")):
            raise BundleError("Unexpected asset name")
        if not isinstance(digest, str) or len(digest) != 64:
            raise BundleError("Invalid web checksum")
        asset = _canonical_file(web_root / name)
        if hashlib.sha256(asset).hexdigest() != digest:
            raise BundleError("Web checksum mismatch")
        payloads[f"web/{name}"] = asset
    actual = {
        path.relative_to(web_root).as_posix()
        for path in web_root.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if actual != {"omnis-web.json", *web_files}:
        raise BundleError("Web build contains unlisted files")
    manifest = {
        "format": 1,
        "release": "0.1.0",
        "schema": "0004_pairing_receipts",
        "platform": "linux/amd64",
        "files": {name: hashlib.sha256(content).hexdigest() for name, content in payloads.items()},
    }
    stage = Path(tempfile.mkdtemp(prefix=".bundle-", dir=output.parent))
    try:
        for name, content in payloads.items():
            dest = stage / name
            dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            _put(dest, content)
        _put(stage / "release.json", (json.dumps(manifest, sort_keys=True) + "\n").encode())
        _manifest(stage)  # Cross-check the exact installer contract before publishing.
        publish_directory(stage, output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local P0 release from pinned artifacts")
    for option in ("api-wheel", "cli-wheel", "requirements", "web-root", "output"):
        parser.add_argument(f"--{option}", type=Path, required=True)
    args = parser.parse_args()
    try:
        build_bundle(args.api_wheel, args.cli_wheel, args.requirements, args.web_root, args.output)
    except (OSError, ValueError, UnicodeError, RecursionError, subprocess.SubprocessError):
        print("BUNDLE_REFUSED", file=sys.stderr)
        return 2
    print("BUNDLE_READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
