"""SOURCE transaction/control-flow checks with DB doubles; not PostgreSQL proof."""

import contextlib
import io
import sys
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

import omnis.stop_reconcile as job
from omnis.modules.instance.domain import ControlConflict
from omnis.modules.instance.service import InstanceService
from omnis.modules.instance.stop_contract import StopReconciliation
from test_stop_reconcile import reconciliation_payload


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "restore,replay,enabled",
    [(True, False, False), (False, False, True), (True, True, False), (True, True, True)],
)
async def test_restore_deactivates_under_closed_lock_and_checks_after_commit(
    restore: bool, replay: bool, enabled: bool
) -> None:
    request = StopReconciliation.model_validate(reconciliation_payload())
    service = InstanceService(Mock(spec=AsyncEngine))
    db = Mock(spec=AsyncConnection)
    events: list[str] = []
    statements: list[str] = []

    async def execute(statement: object, parameters: object = None) -> Mock:
        sql = str(statement)
        statements.append(sql)
        result = Mock()
        if "INSERT INTO public.provider_connection_revision" in sql:
            events.append("deactivate")
            assert parameters == {"instance": request.grant.instance_id}
            assert "revision + 1" in sql and "FALSE" in sql
            assert "connection_id" in sql and "secret_id" in sql and "credential_revision" in sql
            assert "DISTINCT ON (provider)" in sql and "WHERE enabled" in sql
        result.scalar_one_or_none.return_value = 1
        result.scalar_one.return_value = enabled
        return result

    db.execute = AsyncMock(side_effect=execute)

    @contextlib.asynccontextmanager
    async def locked() -> AsyncIterator[tuple[AsyncConnection, Mock, Mock]]:
        events.append("lock")
        yield db, Mock(), Mock()
        events.append("commit")

    with (
        patch.object(service, "_locked", side_effect=locked),
        patch.object(service, "_reconciliation_context", new=AsyncMock()),
        patch.object(service, "_closed_stop", new=AsyncMock()),
        patch.object(
            service, "_reconciliation_receipt", new=AsyncMock(side_effect=[replay, True, True])
        ),
        patch.object(
            service,
            "_grant",
            new=AsyncMock(side_effect=([None, None] if replay else [request.grant, None, None])),
        ),
    ):
        if restore and enabled:
            with pytest.raises(ControlConflict):
                await service.reconcile_stop(request, restore=restore)
        else:
            assert await service.reconcile_stop(request, restore=restore) == request.model_dump(
                mode="json"
            )
            assert events == (
                ["lock", "deactivate", "commit", "lock", "commit"]
                if restore and not replay
                else ["lock", "commit", "lock", "commit"]
            )
    assert sum(
        "INSERT INTO public.provider_connection_revision" in sql for sql in statements
    ) == int(restore and not replay)
    assert sum("SELECT EXISTS" in sql for sql in statements) == (
        1 if restore and enabled else 2 if restore else 0
    )
    assert not any(
        "UPDATE public.provider" in sql or "DELETE FROM public.provider" in sql
        for sql in statements
    )


@pytest.mark.parametrize(
    "args,accepted",
    [
        ([], True),
        (["--restore"], True),
        (["--restore", "--restore"], False),
        (["--restore=true"], False),
        (["--sql", "x"], False),
    ],
)
def test_receiver_allows_only_exact_restore_mode_before_read_or_db(
    args: list[str], accepted: bool
) -> None:
    request = StopReconciliation.model_validate(reconciliation_payload())
    execute = AsyncMock(return_value=request.model_dump(mode="json"))
    with (
        patch.object(sys, "argv", ["stop_reconcile", *args]),
        patch.object(job, "read_request", return_value=request) as read,
        patch.object(job, "execute", execute),
        contextlib.redirect_stdout(io.StringIO()),
    ):
        assert job.main() == (0 if accepted else 4)
    assert read.call_count == int(accepted)
    if accepted:
        execute.assert_awaited_once_with(request, restore=bool(args))
    else:
        execute.assert_not_called()
