"""Real positive/negative controls for the pinned Python quality tools."""

import json
import os
import subprocess
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path
from typing import Literal

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "api/pyproject.toml"
type Tool = Literal["lint", "format", "type"]

GOOD = """from pydantic import BaseModel


class Payload(BaseModel):
    count: int


def checked(value: int) -> int:
    return Payload(count=value).count
"""


def run_tool(tool: Tool, source: Path) -> subprocess.CompletedProcess[str]:
    if tool == "type":
        command = [
            sys.executable,
            "-I",
            "-m",
            "mypy",
            "--config-file",
            str(CONFIG),
            "--no-incremental",
            "--cache-dir",
            str(source.parent / "mypy-cache"),
            "--output=json",
            str(source),
        ]
    else:
        command = [
            sys.executable,
            "-I",
            "-m",
            "ruff",
            "check" if tool == "lint" else "format",
            "--config",
            str(CONFIG),
            "--no-cache",
            "--output-format",
            "json",
        ]
        if tool == "format":
            command.append("--check")
        else:
            command.append("--no-fix")
        command.append(str(source))
    environment = {
        key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "MYPYPATH"}
    }
    return subprocess.run(
        command, cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30
    )


def diagnostics(output: str, tool: Tool) -> list[tuple[str, str, str]]:
    decoded: object = (
        [json.loads(line) for line in output.splitlines() if line]
        if tool == "type"
        else json.loads(output)
    )
    assert isinstance(decoded, list)
    found: list[tuple[str, str, str]] = []
    for item in decoded:
        assert isinstance(item, dict)
        filename = item.get("file" if tool == "type" else "filename")
        code, severity = item.get("code"), item.get("severity")
        assert isinstance(filename, str) and isinstance(code, str) and isinstance(severity, str)
        found.append((filename, code, severity))
    return found


@pytest.mark.parametrize(("package", "pin"), [("ruff", "0.16.9"), ("mypy", "2.3.1")])
def test_quality_tools_are_exact_dev_pins(package: str, pin: str) -> None:
    config = tomllib.loads(CONFIG.read_text())
    assert f"{package}=={pin}" in config["dependency-groups"]["dev"]
    assert not any(item.split("==")[0] == package for item in config["project"]["dependencies"])
    assert version(package) == pin


def test_application_import_belongs_to_this_checkout() -> None:
    import omnis

    assert omnis.__file__ is not None
    assert Path(omnis.__file__).resolve() == ROOT / "api/src/omnis/__init__.py"


@pytest.mark.parametrize(
    ("tool", "bad_source", "code"),
    [
        ("lint", "def checked(value: int) -> int:\n    return missing_name\n", "F821"),
        ("format", "def checked( value:int )->int:\n return value+1\n", "unformatted"),
        ("type", "def checked(value: int) -> int:\n    return 'not-an-int'\n", "return-value"),
        ("type", "def checked(value):\n    return value\n", "no-untyped-def"),
        (
            "type",
            "from typing import Any\n\ndef checked(value: Any) -> Any:\n    return value\n",
            "explicit-any",
        ),
    ],
)
def test_quality_tools_require_the_expected_diagnostic(
    tmp_path: Path, tool: Tool, bad_source: str, code: str
) -> None:
    good = tmp_path / "quality_good.py"
    good.write_text(GOOD)
    accepted = run_tool(tool, good)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert diagnostics(accepted.stdout, tool) == []
    bad = tmp_path / "quality_bad.py"
    bad.write_text(bad_source)
    denied = run_tool(tool, bad)
    assert denied.returncode == 1, denied.stdout + denied.stderr
    errors = diagnostics(denied.stdout, tool)
    assert errors and all(error == (str(bad), code, "error") for error in errors)
    # Check mode must not rewrite the fixture to make the negative disappear.
    assert bad.read_text() == bad_source
