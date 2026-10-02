"""No-DB revision/contract checks; physical PostgreSQL gates remain separate."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from omnis.core.db import SCHEMA_REVISION
from omnis.core.schema import AUTHORITY_TABLES


def test_stop_reconciliation_is_new_schema_authority() -> None:
    script = ScriptDirectory.from_config(
        Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    )
    assert script.get_current_head() == SCHEMA_REVISION == "0006_stop_reconciliation"
    assert "instance_stop_reconciliation" in AUTHORITY_TABLES
    assert AUTHORITY_TABLES["instance_stop_fence"][0]["owner_uuid"] == ("uuid", False, None)
