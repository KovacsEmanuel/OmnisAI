#!/usr/bin/env python3
"""Run the pinned Reticle fixture in disposable scratch with loopback-only egress."""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", required=True, help="Existing Chromium/headless-shell executable")
    args = parser.parse_args()
    browser = Path(args.browser).expanduser().resolve()
    if not browser.is_file() or not os.access(browser, os.X_OK):
        parser.error("Browser executable not found or not executable")
    root = Path(__file__).resolve().parent
    package = root / "node_modules/@reticlehq/server/package.json"
    if not package.is_file() or json.loads(package.read_text()).get("version") != "3.2.0":
        parser.error("Install the pinned Reticle package using npm ci; no automatic installer is run")
    if not shutil.which("unshare") or not shutil.which("ip") or not shutil.which("node"):
        parser.error("Linux unshare, ip and node are required; no unsandboxed fallback")
    try:
        import playwright.async_api  # noqa: F401 -- prerequisite only, no browser launch
    except ImportError:
        parser.error("Use a Python environment with the pinned requirements.txt installed")
    scratch_value = os.environ.get("TMPDIR")
    if not scratch_value:
        parser.error("Set TMPDIR to an owned scratch directory; system temporary defaults are not used")
    scratch = Path(scratch_value).expanduser().resolve()
    if not scratch.is_dir():
        parser.error("TMPDIR does not exist")
    run = Path(tempfile.mkdtemp(prefix="omnis-reticle-", dir=scratch))
    for name in ("raw", "fixture", "home", "tmp"):
        (run / name).mkdir()
    for name in ("smoke_probe.py", "verdicts.py", "server-entry.mjs", "fixture/index.html"):
        shutil.copyfile(root / name, run / name)
    (run / "node_modules").symlink_to(root / "node_modules", target_is_directory=True)
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(run / "home"), "TMPDIR": str(run / "tmp"),
        "RETICLE_PROBE_BROWSER": str(browser), "PYTHONDONTWRITEBYTECODE": "1",
    }
    command = [
        "unshare", "--user", "--map-root-user", "--net", "--pid", "--fork",
        "--mount-proc", "--kill-child=SIGKILL", "/bin/sh", "-c",
        'ip link set lo up && exec "$1" "$2"', "reticle-probe",
        sys.executable, str(run / "smoke_probe.py"),
    ]
    print(f"RUN_DIR={run}", flush=True)
    try:
        result = subprocess.run(command, cwd=run, env=environment, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        print("Reticle fixture timed out; run directory retained for diagnosis", file=sys.stderr)
        return 1
    (run / "raw/runner.stdout").write_text(result.stdout)
    (run / "raw/runner.stderr").write_text(result.stderr)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
