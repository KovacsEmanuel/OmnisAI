"""Original usage -> owned record -> normal bounded readers, SOURCE SQL seams only."""

import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.engine import IteratorResult
from sqlalchemy.engine.result import SimpleResultMetaData
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.runs import run_contract as dto
from omnis.modules.runs import run_store as store
from omnis.modules.runs.model_test_contract import Ref
from omnis.modules.settings.provider_key_models import ModelSelection
from test_run_inspection_source import actor
from test_run_owner_source import fixture_run


def reported() -> dict[str, object]:
    return {
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30,
        "input_tokens": 10,
        "output_tokens": 20,
        "cost": "0.12300",
        "prompt_tokens_details": {"cached_tokens": 4, "private": "NO_RETAIN"},
        "completion_tokens_details": {"reasoning_tokens": 5, "private": "NO_RETAIN"},
        "reasoning": "NO_RETAIN",
        "private": "NO_RETAIN",
    }


def test_usage_original_known_fields_and_components_are_not_added_twice() -> None:
    usage = dto.usage_observation({"usage": reported(), "model": "fixture/observed"})
    assert usage.measures.input_tokens == 10 and usage.measures.output_tokens == 20
    assert usage.measures.total_tokens == 30
    assert usage.measures.cached_tokens == 4 and usage.measures.reasoning_tokens == 5
    assert usage.measures.cost_observed == "0.12300"
    assert usage.reported.cost == "0.12300"
    assert usage.observed_model == "fixture/observed"
    assert "NO_RETAIN" not in usage.model_dump_json()


@pytest.mark.parametrize("value", [True, False, "4", 4.0, -1, 9007199254740992, None])
def test_counts_are_strict_and_unknown_not_zero(value: object) -> None:
    usage = dto.usage_observation({"usage": {"prompt_tokens": value}})
    assert usage.measures.input_tokens is None
    assert usage.measures.total_tokens is None and usage.measures.cost_observed is None


@pytest.mark.parametrize(
    "value", [True, "private text", "NaN", "Infinity", float("inf"), -1, "1e100000"]
)
def test_cost_is_validated_before_original_representation_is_retained(value: object) -> None:
    usage = dto.usage_observation({"usage": {"cost": value}})
    assert usage.reported.cost is None and usage.measures.cost_observed is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tamper", [None, "instance_id", "kind", "revision", "digest", "run_id", "task_id", "attempt_id"]
)
async def test_owned_usage_duplicate_is_one_record_conflict_refuses(
    monkeypatch: pytest.MonkeyPatch,
    tamper: str | None,
) -> None:
    item = actor()
    run = fixture_run().model_copy(update={"instance_id": item.instance_id, "run_id": item.run_id})
    choice = ModelSelection(
        connection_id=str(uuid4()),
        connection_revision=3,
        model=item.configured_model,
        output_tokens=128,
    )
    dispatch = str(uuid4())
    retained: dict[str, object] = {"setup_ref": run.setup_ref.model_dump()}
    saved: dict[str, object] = {}
    writes: list[str] = []
    db = object.__new__(AsyncConnection)

    async def scalar(*args: object, **kwargs: object) -> object:
        return retained

    async def execute(
        self: AsyncConnection, statement: object, parameters: dict[str, object]
    ) -> IteratorResult[tuple[object, ...]]:
        sql = str(statement)
        if sql.startswith("INSERT INTO model_record_v2"):
            writes.append("record")
            saved.update(json.loads(str(parameters["payload"])))
        elif sql.startswith("UPDATE run_dispatch"):
            writes.append("link")
            retained.update(json.loads(str(parameters["payload"])))
        elif sql.startswith("SELECT payload FROM model_record_v2"):
            return IteratorResult(SimpleResultMetaData(["payload"]), iter([(saved,)]))
        else:
            raise AssertionError(sql)
        return IteratorResult(SimpleResultMetaData([]), iter([]))

    monkeypatch.setattr(AsyncConnection, "scalar", scalar)
    monkeypatch.setattr(AsyncConnection, "execute", execute)
    observation = dto.usage_observation({"usage": reported()})
    first = await store.record_usage(db, run, item, dispatch, choice, observation)
    second = await store.record_usage(db, run, item, dispatch, choice, observation)
    assert first == second and writes == ["record", "link"]
    assert first.kind == "run-usage-v2" and first.revision == 1
    assert saved["run_id"] == run.run_id and saved["task_id"] == item.task_id
    assert saved["attempt_id"] == item.attempt_id and saved["dispatch_id"] == dispatch
    assert saved["connection_revision"] == 3
    with pytest.raises(ValueError, match="USAGE_CONFLICT"):
        await store.record_usage(
            db, run, item, dispatch, choice, dto.usage_observation({"usage": {"prompt_tokens": 99}})
        )
    assert writes == ["record", "link"]
    assert Ref.model_validate(retained["usage_ref"]) == first
    if tamper is not None:
        from omnis.modules.runs import model_test_store as records

        if tamper in {"run_id", "task_id", "attempt_id"}:
            saved[tamper] = str(uuid4())
            retained["usage_ref"] = first.model_copy(
                update={"digest": records.digest(saved)}
            ).model_dump()
        else:
            change: object = (
                2
                if tamper == "revision"
                else "run-context-v1"
                if tamper == "kind"
                else "0" * 64
                if tamper == "digest"
                else str(uuid4())
            )
            retained["usage_ref"] = first.model_copy(update={tamper: change}).model_dump()
        with pytest.raises(ValueError):
            await store.record_usage(db, run, item, dispatch, choice, observation)
        assert writes == ["record", "link"]


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [False, True])
async def test_whole_run_sql_aggregate_is_not_attempt_page_total(
    monkeypatch: pytest.MonkeyPatch,
    invalid: bool,
) -> None:
    from omnis.modules.runs import projections
    from test_run_owner_source import fixture_setup_payload

    run = fixture_run()
    snapshot = dto.Setup.model_validate(fixture_setup_payload())
    monkeypatch.setattr(store, "setup", AsyncMock(return_value=snapshot))
    columns = ["role", "dispatches", "unobserved", "invalid"]
    values: list[object] = [None, 100001, 100000, int(invalid)]
    for key in dto.UsageMeasures.model_fields:
        columns += [key, key + "_observed"]
        values += ["0.123" if key == "cost_observed" else "30", 1]
    query = AsyncMock(
        return_value=IteratorResult(SimpleResultMetaData(columns), iter([tuple(values)]))
    )
    monkeypatch.setattr(AsyncConnection, "execute", query)
    if invalid:
        with pytest.raises(ValueError, match="REF_UNAVAILABLE"):
            await projections.usage_summary(object.__new__(AsyncConnection), run)
        return
    usage = await projections.usage_summary(object.__new__(AsyncConnection), run)
    assert usage.scope == "RUN" and usage.totals.dispatches == 100001
    assert usage.totals.unobserved_dispatches == 100000
    assert usage.totals.cost_observed.state == "PARTIAL"
    assert usage.totals.cost_observed.value == "0.123"
    assert usage.totals.input_tokens.observed_dispatches == 1
    sql = str(query.call_args.args[0])
    assert "GROUPING SETS" in sql and "LEFT JOIN" in sql
    assert "LIMIT" not in sql and "FOR UPDATE" not in sql
    assert "sum(" in sql.lower() and "count(" in sql.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [1, 21])
async def test_unobserved_dispatch_details_survive_readback(
    monkeypatch: pytest.MonkeyPatch,
    count: int,
) -> None:
    from omnis.modules.runs import projections

    item = actor()
    dispatch = str(uuid4())
    from test_run_owner_source import fixture_setup_payload

    run = fixture_run().model_copy(update={"instance_id": item.instance_id, "run_id": item.run_id})
    monkeypatch.setattr(
        store, "setup", AsyncMock(return_value=dto.Setup.model_validate(fixture_setup_payload()))
    )
    rows: list[tuple[object, ...]] = [
        (dispatch, "UNKNOWN", {}, None, None, None, False, None)
    ] * count
    execute = AsyncMock(
        return_value=IteratorResult(
            SimpleResultMetaData(
                [
                    "dispatch_id",
                    "state",
                    "payload",
                    "reserved_at",
                    "sent_at",
                    "settled_at",
                    "invalid",
                    "usage_id",
                ]
            ),
            iter(rows),
        )
    )
    monkeypatch.setattr(AsyncConnection, "execute", execute)
    values, more = await projections.dispatch_usage(object.__new__(AsyncConnection), run, item)
    assert len(values) == min(count, 20) and more == (count > 20)
    assert values[0].usage is None and values[0].state == "UNKNOWN"
    assert values[0].usage_ref is None


@pytest.mark.asyncio
async def test_legacy_usage_receipt_is_read_only_and_cost_remains_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime

    from omnis.modules.runs import model_test_store as records
    from omnis.modules.runs import projections
    from test_run_owner_source import fixture_setup_payload

    item = actor()
    run = fixture_run().model_copy(update={"instance_id": item.instance_id, "run_id": item.run_id})
    snapshot = dto.Setup.model_validate(fixture_setup_payload())
    monkeypatch.setattr(store, "setup", AsyncMock(return_value=snapshot))
    dispatch = str(uuid4())
    payload = {
        "dispatch_id": dispatch,
        "state": "OBSERVED",
        "prompt_tokens": 10,
        "completion_tokens": 20,
    }
    ref = Ref(
        instance_id=item.instance_id,
        kind="run-usage-v1",
        id=str(uuid4()),
        digest=records.digest(payload),
    )
    row = {
        "dispatch_id": dispatch,
        "state": "SETTLED",
        "invalid": False,
        "usage_id": ref.id,
        "usage_kind": ref.kind,
        "usage_digest": ref.digest,
        "choice": snapshot.recon.choice.model_dump(),
        "observed_at": datetime.now(UTC),
        "reserved_at": None,
        "sent_at": None,
        "settled_at": None,
    }
    execute = AsyncMock(
        side_effect=[
            IteratorResult(SimpleResultMetaData(list(row)), iter([tuple(row.values())])),
            IteratorResult(SimpleResultMetaData(["payload"]), iter([(payload,)])),
        ]
    )
    monkeypatch.setattr(AsyncConnection, "execute", execute)
    values, more = await projections.dispatch_usage(object.__new__(AsyncConnection), run, item)
    assert not more and values[0].usage_ref == ref
    value = values[0].usage
    assert value is not None and value.measures.total_tokens == 30
    assert value.measures.cost_observed is None and value.observed_model is None
    assert value.reported.prompt_tokens == 10 and value.reported.completion_tokens == 20
    assert all(
        "INSERT" not in str(call.args[0]) and "UPDATE" not in str(call.args[0])
        for call in execute.call_args_list
    )
