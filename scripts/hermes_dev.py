#!/usr/bin/env python3
"""Launch Hermes in this checkout; --check prints argv, never the environment."""
from pathlib import Path
import json
import os
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    if not (root / ".git").exists() or not (root / "AGENTS.md").is_file():
        print("Expected an Omnis git checkout with AGENTS.md", file=sys.stderr)
        return 2
    args = sys.argv[1:]
    check = bool(args and args[0] == "--check")
    if check:
        args = args[1:]
    command = ["hermes", *args]
    env = {**os.environ, "TERMINAL_CWD": str(root)}
    if check:
        print(json.dumps({"cwd": str(root), "TERMINAL_CWD": str(root), "command": command}))
        return 0
    os.chdir(root)
    try:
        os.execvpe(command[0], command, env)
    except OSError as exc:
        print(f"Cannot start Hermes: {exc}", file=sys.stderr)
        return 127
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
