"""Export only the local Omnis OpenAPI, without starting services or reading a DB."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api/src"))

from omnis.api import create_app  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "contracts/omnis.openapi.json")
    args = parser.parse_args()
    content = json.dumps(create_app().openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not args.output.is_file() or args.output.read_text() != content:
            print("OpenAPI drift: run make generate-contracts", file=sys.stderr)
            return 1
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
