"""PostgreSQL acceptance prepared for parent QA; collect-only in SOURCE repair."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL

from omnis.core.db import database_engine
from omnis.modules.instance.service import InstanceService
from test_stop_fence import db_snapshot, pending_reconciliation


@pytest.mark.parametrize("restore", [False, True])
@pytest.mark.asyncio
async def test_restore_appends_inactive_heads_without_changing_history_or_refs(
    migrated_database_url: URL, restore: bool
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    try:
        request = await pending_reconciliation(service)
        instance = request.grant.instance_id
        async with engine.begin() as db:
            for provider, enabled in (("openrouter", True), ("orcarouter", False)):
                await db.execute(
                    text(
                        "INSERT INTO public.provider_connection_revision "
                        "(instance_id,connection_id,provider,revision,enabled,secret_id,credential_revision) "
                        "VALUES (:instance,:connection,:provider,1,:enabled,:secret,7)"
                    ),
                    {
                        "instance": instance,
                        "connection": uuid4(),
                        "provider": provider,
                        "enabled": enabled,
                        "secret": uuid4(),
                    },
                )
        query = text(
            "SELECT * FROM public.provider_connection_revision ORDER BY provider, revision"
        )
        async with engine.connect() as db:
            before = (await db.execute(query)).mappings().all()
        control = await db_snapshot(engine)
        assert await service.reconcile_stop(request, restore=restore) == request.model_dump(
            mode="json"
        )
        async with engine.connect() as db:
            after = (await db.execute(query)).mappings().all()
        if restore:
            assert len(after) == 3
            assert after[0] == before[0] and after[2] == before[1]
            assert dict(after[1]) == {**before[0], "revision": 2, "enabled": False}
        else:
            assert after == before
        state = await db_snapshot(engine)
        assert state[:2] == control[:2] and state[3] == control[3]
        assert await service.reconcile_stop(request, restore=restore) == request.model_dump(
            mode="json"
        )
        async with engine.connect() as db:
            assert (await db.execute(query)).mappings().all() == after
        assert await db_snapshot(engine) == state
    finally:
        await engine.dispose()
