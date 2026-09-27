"""Test-only DB fault injection; requires the same attested disposable cluster as pytest."""

import os
import re
import select
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import connect_test_database  # noqa: E402


def main() -> None:
    url = make_url(os.environ["OMNIS_E2E_DATABASE_URL"])
    if not re.fullmatch(r"omnis_p01_[0-9a-f]{32}", url.database or ""):
        raise RuntimeError("Only the UUID-named E2E fixture database is allowed")
    with connect_test_database(url) as connection:
        operation = sys.argv[1]
        if operation == "expire-code":
            connection.execute(
                "UPDATE pairing_challenge SET expires_at = clock_timestamp() - interval '1 second'"
            )
        elif operation == "expire-session":
            connection.execute(
                "UPDATE ui_session SET expires_at = clock_timestamp() - interval '1 second'"
            )
        elif operation == "block-db":
            connection.execute("LOCK TABLE instance_control IN ACCESS EXCLUSIVE MODE")
            print("DB_LOCKED", flush=True)
            select.select([sys.stdin], [], [], 25)
        else:
            raise RuntimeError("Unknown test-only fault")


if __name__ == "__main__":
    main()
