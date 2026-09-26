"""Test-only guard before creating or dropping any PostgreSQL database."""

import os

import pytest
from sqlalchemy.engine import make_url

from conftest import verify_test_database


def test_rejects_a_different_compose_project(monkeypatch):
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"])
    monkeypatch.setenv("OMNIS_TEST_PROJECT", "omnis-p01-unowned")
    with pytest.raises(RuntimeError, match="dedicated test project"):
        verify_test_database(url)


def test_rejects_a_mismatched_published_port():
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"]).set(port=1)
    with pytest.raises(RuntimeError, match="dedicated test project"):
        verify_test_database(url)


def test_accepts_only_its_own_running_compose_database():
    url = make_url(os.environ["OMNIS_TEST_DATABASE_URL"])
    verify_test_database(url)
