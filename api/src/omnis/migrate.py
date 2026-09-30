"""Dedicated migration command for an explicitly configured PostgreSQL database."""

import argparse
import os
import re
from importlib.resources import files

from alembic import command
from alembic.config import Config


def main() -> None:
    parser = argparse.ArgumentParser(description="Explicit PostgreSQL migration")
    parser.add_argument(
        "--initialize", action="store_true", help="Only an empty, attested database; never upgrade"
    )
    args = parser.parse_args()
    config = Config()
    if args.initialize:
        identity = os.environ.get("OMNIS_EXPECTED_SYSTEM_ID", "")
        if not re.fullmatch(r"[0-9]{1,20}", identity):
            raise RuntimeError("Expected PostgreSQL cluster identity required")
        config.attributes["initialize_system_id"] = identity
    config.set_main_option("script_location", str(files("omnis.migrations")))
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()
