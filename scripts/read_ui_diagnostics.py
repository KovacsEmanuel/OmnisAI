"""Read only validated UI diagnostic records from an explicitly owned API container.

Run with api/.venv/bin/python -I. Capture is bounded/current-container, never durable history.
"""

import argparse
import http.client
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api/src"))

from omnis.modules.diagnostics.reader import read_docker  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True, help="Explicit local unix:// Docker endpoint")
    parser.add_argument("--container", required=True, help="Exact64hex API container ID")
    parser.add_argument("--project", required=True)
    parser.add_argument("--start-attempt", required=True)
    args = parser.parse_args()
    try:
        records = read_docker(args.endpoint, args.container, args.project, args.start_attempt)
    except (OSError, ValueError, TimeoutError, http.client.HTTPException, RecursionError):
        print('{"state":"UNAVAILABLE","complete":false}', file=sys.stderr)
        return 2
    print(json.dumps({"records": [record.model_dump(mode="json") for record in records],
                      "complete": False, "loss_after_last_record": "UNKNOWN",
                      "busy_drops": "UNKNOWN", "retention": "current container only"}, separators=(",", ":")))
    return 0 if records else 2


if __name__ == "__main__":
    raise SystemExit(main())
