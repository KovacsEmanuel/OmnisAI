"""Storage error regression on the real projection service with driver failure double."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.modules.runs.managed_admission import ManagedAdmission
from omnis.modules.runs.model_projection import ModelProjections
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.tasks import managed_store
from test_model_projection import source_graph
from test_model_projection_denials import MARKER, approval_for


def test_storage_failure_does_not_expose_driver_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    owner, graph, launch, composition = source_graph(tmp_path)
    approval = approval_for(owner, launch, composition)
    binding = next(r for r in graph if r["kind"] == "runtime-binding")
    managed = ManagedAdmission(Mock(spec=AsyncEngine))
    monkeypatch.setattr(managed_store, "state", AsyncMock(side_effect=SQLAlchemyError(MARKER)))
    with pytest.raises(CatalogError, match="MODEL_PROJECTION_REJECTED") as error:
        asyncio.run(
            ModelProjections(managed).prepare(
                AsyncMock(spec=AsyncConnection),
                owner,
                records.reference(launch),
                records.reference(binding),
                records.reference(composition),
                approval,
            )
        )
    assert MARKER not in str(error.value) + caplog.text
