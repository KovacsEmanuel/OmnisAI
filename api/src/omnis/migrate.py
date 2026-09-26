"""Dedicated migration command for an explicitly configured PostgreSQL database."""

from importlib.resources import files

from alembic import command
from alembic.config import Config


def main() -> None:
    config = Config()
    config.set_main_option("script_location", str(files("omnis.migrations")))
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()
