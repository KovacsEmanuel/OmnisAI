"""Exercise full pinned source with an overlay on the host interpreter, NOT installed proof.

Explicit source path plus fresh scratch HOME required. No AIAgent substitution.
"""

import importlib.abc
import importlib.util
import os
import runpy
import sys
import time
import unittest
from pathlib import Path

source, overlay, adapter, home = map(Path, sys.argv[1:])
if not home.is_dir() or any(home.iterdir()):
    raise ValueError("Fresh private probe home required")
os.environ.clear()
os.environ.update(
    HOME=str(home),
    HERMES_HOME=str(home / "hermes"),
    TMPDIR=str(home),
    HERMES_OMNIS_INERT="1",
    HERMES_DISABLE_LAZY_INSTALLS="1",
    HERMES_SKIP_NODE_BOOTSTRAP="1",
    PYTHONDONTWRITEBYTECODE="1",
)
sys.dont_write_bytecode = True
attempts = []


def audit(event, args):
    if event in {"socket.connect", "subprocess.Popen", "os.system"}:
        attempts.append(event)
        raise RuntimeError("Forbidden source probe effect: " + event)
    if event == "open" and isinstance(args[0], (str, bytes)):
        p = os.fsdecode(args[0])
        if p.endswith((".env", "auth.json", "credentials.json")):
            import traceback

            attempts.append(
                {
                    "event": "credential-read",
                    "stack": [
                        (f.name, Path(f.filename).name, f.lineno)
                        for f in traceback.extract_stack()[-12:]
                    ],
                }
            )
            raise RuntimeError("Forbidden credential read")


sys.addaudithook(audit)


# Source overlay loader, not an agent/method replacement. Unchanged package
# modules resolve from the read-only exported pin.
class Overlay(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        relative = Path(*fullname.split("."))
        package = overlay / relative / "__init__.py"
        if package.is_file():
            return importlib.util.spec_from_file_location(
                fullname,
                package,
                submodule_search_locations=[str(package.parent), str(source / relative)],
            )
        module = (overlay / relative).with_suffix(".py")
        if module.is_file():
            return importlib.util.spec_from_file_location(fullname, module)


sys.meta_path.insert(0, Overlay())
sys.path[:0] = [str(source), str(adapter)]
agent = importlib.import_module("agent")
agent.__path__.insert(0, str(overlay / "agent"))
started = time.monotonic()
probe = runpy.run_path(str(Path(__file__).with_name("managed_native_probe.py")))
suite = unittest.defaultTestLoader.loadTestsFromTestCase(probe["ColdLifecycle"])
result = unittest.TextTestRunner(verbosity=2).run(suite)
print(
    {
        "scope": "FULL_PINNED_SOURCE_HOST_INTERPRETER_NOT_INSTALLED",
        "seconds": time.monotonic() - started,
        "tests": result.testsRun,
        "effects": attempts,
    }
)
raise SystemExit(0 if result.wasSuccessful() and result.testsRun == 7 and not attempts else 1)
