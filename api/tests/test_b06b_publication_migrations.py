"""Empty and 0009 -> 0010 upgrade; old ledger bytes remain immutable.

Only the common attestor may acquire CREATE/DROP ownership. The inserted old
row is a new migration sentinel, NOT an accepted qualification or old receipt.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import URL

from conftest import connect_test_database, verify_test_database
from fixtures.b06b_publication.consumer import (
    canonical,
    confirmed,
    new_seed,
    publish_request,
    qualify,
    require_consumer,
    sha,
)

ROOT = Path(__file__).resolve().parents[2]


def migrate(url: URL, revision: str) -> None:
    verify_test_database(url.set(database="omnis_test"))
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-m", "alembic", "-c", "alembic.ini", "upgrade", revision],
        cwd=ROOT / "api",
        env={**os.environ, "OMNIS_DATABASE_URL": url.render_as_string(hide_password=False)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, f"migration {revision}: exit={result.returncode}"


@pytest.mark.parametrize("previous", [None, "0009_catalog_candidates"])
def test_empty_and_0009_upgrade_preserve_rows_then_publish(
    request: pytest.FixtureRequest, previous: str | None
) -> None:
    require_consumer()
    url = cast(URL, request.getfixturevalue("empty_database_url"))
    sentinel = None
    identifier = str(uuid4())
    if previous:
        migrate(url, previous)
        owner, group, identifier = str(uuid4()), str(uuid4()), str(uuid4())
        record: dict[str, object] = {
            "schema_version": 1,
            "kind": "b06b-upgrade-sentinel",
            "id": identifier,
            "revision": 1,
            "payload": {"note": "new synthetic migration sentinel, no qualification"},
        }
        record["digest"] = sha(canonical(record))
        with connect_test_database(url) as connection:
            connection.execute(
                "INSERT INTO catalog_record (id,owner_id,group_id,kind,revision,digest,envelope) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)",
                (
                    identifier,
                    owner,
                    group,
                    record["kind"],
                    1,
                    record["digest"],
                    canonical(record).decode(),
                ),
            )
            sentinel = connection.execute(
                "SELECT envelope FROM catalog_record WHERE id=%s", (identifier,)
            ).fetchone()
            assert sentinel is not None
            connection.commit()
    migrate(url, "0010_catalog_publications")
    with connect_test_database(url) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0010_catalog_publications",
        )
        assert connection.execute("SELECT count(*) FROM catalog_publication_head").fetchone() == (
            0,
        )
        if previous:
            assert (
                connection.execute(
                    "SELECT envelope FROM catalog_record WHERE id=%s", (identifier,)
                ).fetchone()
                == sentinel
            )
    dsn = url.render_as_string(hide_password=False)
    q = qualify(new_seed(), dsn)
    publication = q.seed.success("publish", publish_request(q, confirmed(q, dsn)), dsn)
    assert (
        q.seed.success(
            "readback", q.seed.request(publication_ref=publication["publication_ref"]), dsn
        )["publication"]
        == publication["publication"]
    )
