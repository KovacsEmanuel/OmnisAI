"""A private test DB URI must reach the same UDS through SQLAlchemy and libpq."""

import asyncio
from urllib.parse import quote

import pytest

from omnis.core.db import database_engine, validated_database_url


def test_canonical_encoded_unix_host_is_decoded_once_for_the_engine() -> None:
    socket_directory = "/run/omnis-test-uds"
    encoded = quote(socket_directory, safe="")
    raw = f"postgresql+psycopg://omnis_test@{encoded}/omnis_test"
    url = validated_database_url(raw)
    engine = database_engine(raw)
    try:
        assert url.host == engine.url.host == socket_directory
    finally:
        asyncio.run(engine.dispose())


def test_internal_docker_tcp_host_keeps_its_existing_shape() -> None:
    raw = "postgresql+psycopg://omnis@db/omnis"
    url = validated_database_url(raw)
    engine = database_engine(raw)
    try:
        assert url.host == engine.url.host == "db"
    finally:
        asyncio.run(engine.dispose())


def test_double_encoded_unix_host_cannot_be_treated_as_a_dns_name() -> None:
    with pytest.raises(ValueError, match="Invalid private PostgreSQL socket path"):
        validated_database_url("postgresql+psycopg://omnis_test@%252Frun%252Felsewhere/omnis_test")


@pytest.mark.parametrize(
    "host",
    [
        "%2Frun%2F.%2Fsocket",
        "%2Frun%2Fsocket%2F",
        "%2Frun%2F%2Fsocket",
        "%2Frun%2Fowned%2Cforeign.invalid",
        "%2Frun%2Fowned%2C%2Frun%2Fother",
        "%2Frun%2Fowned%2C",
    ],
)
def test_unix_host_must_preserve_the_exact_canonical_path(host: str) -> None:
    with pytest.raises(ValueError, match="Invalid private PostgreSQL socket path"):
        validated_database_url(f"postgresql+psycopg://omnis_test@{host}/omnis_test")


def test_private_host_reaches_psycopg_as_a_socket_directory_not_encoded_dns() -> None:
    engine = database_engine("postgresql+psycopg://omnis_test@%2Frun%2Fomnis-test-uds/omnis_test")
    try:
        _args, kwargs = engine.sync_engine.dialect.create_connect_args(engine.url)
        assert kwargs["host"] == "/run/omnis-test-uds"
        assert kwargs["dbname"] == "omnis_test"
    finally:
        asyncio.run(engine.dispose())


def test_missing_host_cannot_fall_back_to_an_ambient_local_database() -> None:
    with pytest.raises(ValueError, match="Explicit PostgreSQL host required"):
        validated_database_url("postgresql+psycopg://omnis_test@/omnis_test")
