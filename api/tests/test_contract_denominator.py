"""Real private CLI and producers; persistence/material SQL seams are SOURCE doubles."""

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from omnis.modules.runs import contract_inputs
from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_models import Manifest, Procedure
from omnis.modules.settings.catalog_schema import canonical, dto
from omnis.modules.tasks import managed_contract as contract
from omnis.modules.tasks.contract_case_input import produce_input
from omnis.modules.tasks.mission_revisions import append
from test_c03_managed_capture import capture_source
from test_mission_revisions import Result, SQLDouble

Data = dict[str, object]


class DenominatorSQLDouble(SQLDouble):
    """Existing query-shape double plus transaction-local public namespace."""

    async def execute(self, statement: object, args: Data | None = None) -> Result:
        if str(statement) == "SET LOCAL search_path = pg_catalog, public, pg_temp":
            return Result([])
        assert args is not None
        return await super().execute(statement, args)


def fixture() -> tuple[SQLDouble, Data, bytes]:
    """Real context/records/M2 producer, declared catalog identities only."""
    from tempfile import TemporaryDirectory

    from fixtures.c03_records import records_seed

    # SOURCE material bytes only; no compile/evaluate/native/DB.
    with TemporaryDirectory(prefix="denominator-", dir=os.environ["TMPDIR"]) as directory:
        seed = records_seed(Path(directory) / "seed")
        raw = (seed.package / "templates/schemas/records.schema.json").read_bytes()
        procedure = dto(
            (seed.package / "templates/procedures/map-records.yaml").read_bytes(), Procedure
        )
        manifest = dto((seed.package / "omnis.yaml").read_bytes(), Manifest)
    source = capture_source()
    source = type(source)(
        source.selection,
        source.preparation_ref,
        source.procedure_ref,
        procedure,
        source.bindings,
        source.package,
        source.role,
        procedure.limits,
        source.packages,
        source.files,
        manifest,
    )
    graph = source.build(context_only=True, method_execution=True)
    run = next(r for r in graph if r["kind"] == "managed-run")
    body = contract.mapping(run["payload"])
    schema_ref = next(
        contract.ref(b["ref"]) for b in source.bindings if b["entity_kind"] == "schema"
    )
    # Doubled reservation identities belong to the same retained package digest.
    schema_ref = {**schema_ref, "digest": source.procedure_ref["digest"]}
    owner = str(uuid4())
    context = records.envelope(
        "contract-input-context",
        {
            "version": 2,
            "namespace": "RUN",
            "owner_id": owner,
            "basis_ref": records.reference(run),
            "snapshot_ref": body["snapshot_ref"],
            "procedure_ref": source.procedure_ref,
            "schema_ref": schema_ref,
            "selection_ref": body["selection_ref"],
            "mission_ref": body["mission_ref"],
            "focus_ref": body["focus_ref"],
        },
    )
    item = produce_input(
        context,
        {
            "records": [
                {"method": "GET", "path": "/synthetic", "status": 404},
                {"method": "GET", "path": "/synthetic", "status": 200},
                {"method": "GET", "path": "/synthetic", "status": 200},
            ]
        },
        raw,
        str(uuid4()),
    )
    m1 = next(r for r in graph if r["kind"] == "mission")
    m2 = append(m1, str(uuid4()))
    graph.extend([context, item, m2])
    conn = DenominatorSQLDouble(owner, contract.text(run["id"]), graph)
    request: Data = {
        "schema_version": 1,
        "owner_id": owner,
        "command_id": str(uuid4()),
        "context_ref": records.reference(context),
        "mission_ref": records.reference(m2),
        "input_ref": records.reference(item),
    }
    return conn, request, raw


def test_private_cli_first_m2_denominator_read_and_replay(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    conn, request, raw = fixture()
    # RED must reach the real parser before importing the missing producer.
    path = tmp_path / "request.json"
    path.write_bytes(canonical(request))
    monkeypatch.setattr(contract_inputs, "database_engine", lambda url: cast(AsyncEngine, conn))
    monkeypatch.setenv("OMNIS_DATABASE_URL", "source-double-not-a-dsn")
    if hasattr(contract_inputs.ContractInputs, "create_denominator"):
        from omnis.modules.coverage import denominator

        async def material(*args: object) -> tuple[bytes, list[Data], str]:
            return raw, [], "templates/schemas/records.schema.json"

        monkeypatch.setattr(denominator, "retained_material", material)
    before = deepcopy(conn.graph)
    assert contract_inputs.main(["create-denominator", "--request", str(path)]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    created = contract.mapping(json.loads(output.out))
    assert created["created"] is True
    read_request = {k: request[k] for k in ("schema_version", "owner_id", "command_id")}
    path.write_bytes(canonical(read_request))
    assert contract_inputs.main(["read-denominator", "--request", str(path)]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    back = contract.mapping(json.loads(output.out))
    body = contract.mapping(contract.mapping(back["denominator"])["payload"])
    assert body["denominator_revision"] == 1 and contract.ref(body["mission_ref"])["revision"] == 2
    assert body["universe"] == "DECLARED_CONTRACT_INPUT"
    assert (
        body["identity_state"]
        == body["applicability_state"]
        == body["precondition_state"]
        == "UNKNOWN"
    )
    assert body["operations"] == [{"method": "GET", "path": "/synthetic", "statuses": [200, 404]}]
    persisted = canonical(conn.graph)
    for value in (request, {**request, "command_id": str(uuid4())}):
        path.write_bytes(canonical(value))
        assert contract_inputs.main(["create-denominator", "--request", str(path)]) == 0
        output = capsys.readouterr()
        replay = contract.mapping(json.loads(output.out))
        assert output.err == "" and replay["created"] is False
        assert replay["denominator_ref"] == created["denominator_ref"]
    # New command gets its receipt, never another denominator/revision.
    assert [
        r
        for r in conn.graph
        if r["kind"] != "contract-input-command" and r["kind"] != "coverage-denominator"
    ] == before
    assert len([r for r in conn.graph if r["kind"] == "coverage-denominator"]) == 1
    assert persisted != canonical(conn.graph)


@pytest.mark.parametrize(
    "attack,reason",
    [
        ("owner", "REF_UNAVAILABLE"),
        ("digest", "REF_MISMATCH"),
        ("bool-ref", "INVALID_REQUEST"),
        ("wrong-kind", "MANAGED_REJECTED"),
        ("caller-revision", "MANAGED_REJECTED"),
        ("purpose-claim", "MANAGED_REJECTED"),
        ("changed-request", "COMMAND_CONFLICT"),
        ("wrong-read", "COMMAND_CONFLICT"),
        ("resealed-operations", "DENOMINATOR_INVALID"),
        ("resealed-unknown", "DENOMINATOR_INVALID"),
        ("resealed-revision", "MANAGED_REJECTED"),
        ("resealed-input-provenance", "INVALID_CASE_INPUT"),
        ("wrong-purpose", "MISSION_REVISION_UNSUPPORTED"),
    ],
)
def test_cli_denials_revalidate_semantics_before_effects(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    attack: str,
    reason: str,
) -> None:
    from omnis.modules.coverage import denominator

    conn, request, raw = fixture()

    async def material(*args: object) -> tuple[bytes, list[Data], str]:
        return raw, [], "templates/schemas/records.schema.json"

    monkeypatch.setattr(denominator, "retained_material", material)
    monkeypatch.setattr(contract_inputs, "database_engine", lambda url: cast(AsyncEngine, conn))
    monkeypatch.setenv("OMNIS_DATABASE_URL", "source-double-not-a-dsn")
    path = tmp_path / "request.json"
    path.write_bytes(canonical(request))
    assert contract_inputs.main(["create-denominator", "--request", str(path)]) == 0
    capsys.readouterr()
    bad = deepcopy(request)
    operation = "create-denominator"
    if attack == "owner":
        bad["owner_id"] = str(uuid4())
    elif attack in {"digest", "bool-ref", "wrong-kind"}:
        field, value = {
            "digest": ("digest", "0" * 64),
            "bool-ref": ("revision", True),
            "wrong-kind": ("kind", "mission"),
        }[attack]
        bad["input_ref"] = {**contract.ref(bad["input_ref"]), field: value}
    elif attack == "caller-revision":
        bad["denominator_revision"] = 1
    elif attack == "purpose-claim":
        bad["purpose"] = "ASSESSMENT"
    elif attack == "changed-request":
        bad["mission_ref"] = next(
            records.reference(r)
            for r in conn.graph
            if r["kind"] == "mission" and r["revision"] == 1
        )
    elif attack == "wrong-read":
        operation = "read-mission"
        bad = {k: request[k] for k in ("schema_version", "owner_id", "command_id")}
    else:
        kind = (
            "contract-case-records"
            if attack == "resealed-input-provenance"
            else "managed-run"
            if attack == "wrong-purpose"
            else denominator.KIND
        )
        index = next(i for i, r in enumerate(conn.graph) if r["kind"] == kind)
        item = conn.graph[index]
        body = contract.mapping(item["payload"])
        if attack == "resealed-operations":
            body["operations"] = []
        elif attack == "resealed-unknown":
            body["identity_state"] = "KNOWN"
        elif attack == "resealed-revision":
            body["denominator_revision"] = True
        elif attack == "resealed-input-provenance":
            body["provenance"] = {**contract.mapping(body["provenance"]), "source_kind": "OBSERVED"}
        else:
            body["purpose"] = "ASSESSMENT"
        # Reseal every ref transitively: selfdigest/dictionary equality is not the guard.
        old_ref = records.reference(item)
        from hashlib import sha256

        item = {**item, "payload": body}
        item["digest"] = sha256(
            canonical({k: v for k, v in item.items() if k != "digest"})
        ).hexdigest()
        conn.graph[index] = item
        new_ref = records.reference(item)
        replacements = {canonical(old_ref): new_ref}

        def replace(value: object) -> object:
            if isinstance(value, dict):
                replacement = replacements.get(canonical(value))
                if replacement is not None:
                    return replacement
                return {k: replace(v) for k, v in value.items()}
            if isinstance(value, list):
                return [replace(v) for v in value]
            return value

        for _ in range(len(conn.graph)):
            changed_count = 0
            for i, other in enumerate(conn.graph):
                changed = contract.mapping(replace(other["payload"]))
                if canonical(changed) != canonical(other["payload"]):
                    updated = {**other, "payload": changed}
                    updated["digest"] = sha256(
                        canonical({k: v for k, v in updated.items() if k != "digest"})
                    ).hexdigest()
                    replacements[canonical(records.reference(other))] = records.reference(updated)
                    conn.graph[i] = updated
                    changed_count += 1
            if changed_count == 0:
                break
        bad = contract.mapping(replace(bad))
        if attack.startswith("resealed-"):
            operation = "read-denominator"
            bad = {k: request[k] for k in ("schema_version", "owner_id", "command_id")}
    before = canonical(conn.graph)
    writes = len(conn.writes)
    path.write_bytes(canonical(bad))
    code = contract_inputs.main([operation, "--request", str(path)])
    output = capsys.readouterr()
    assert (code, output.out, output.err) == (
        2,
        "",
        canonical({"status": "BLOCKED", "reason": reason}).decode() + "\n",
    )
    assert canonical(conn.graph) == before and len(conn.writes) == writes


@pytest.mark.asyncio
@pytest.mark.parametrize("unavailable", [None, "procedure", "schema"])
async def test_retained_catalog_reader_public_pins_no_execution(
    monkeypatch: pytest.MonkeyPatch,
    unavailable: str | None,
) -> None:
    import base64

    from sqlalchemy.ext.asyncio import AsyncConnection

    from fixtures.c03_records import PACKAGE, PATHS, ROOT
    from omnis.modules.coverage import denominator
    from omnis.modules.runs import native_preparation
    from omnis.modules.settings.catalog_models import CatalogError

    conn, request, raw = fixture()
    context = next(r for r in conn.graph if r["kind"] == "contract-input-context")
    ctx = contract.mapping(context["payload"])
    run = next(r for r in conn.graph if r["kind"] == "managed-run")
    preparation_ref = contract.mapping(run["payload"])["preparation_receipt_ref"]
    package_ref = {**contract.ref(ctx["procedure_ref"]), "kind": "package"}
    package = {
        "package_key": PACKAGE,
        "package_ref": package_ref,
        "files": [
            {
                "path": path,
                "content_b64": base64.b64encode(
                    (ROOT / "skills" / PACKAGE / path).read_bytes()
                ).decode(),
            }
            for path in PATHS
        ],
    }
    bundle = records.envelope(
        "native-preparation-bundle",
        {
            "selection_ref": ctx["selection_ref"],
            "snapshot_ref": ctx["snapshot_ref"],
            "packages": [package],
        },
    )
    receipt = records.envelope(
        "native-preparation-receipt", {"bundle_ref": records.reference(bundle)}
    )

    # Preparation/catalog ownership seams explicitly doubled; the material reader is real.
    async def catalog_get(*args: object) -> tuple[str, Data]:
        return str(uuid4()), receipt

    async def preparation(*args: object) -> Data:
        return {"receipt_ref": preparation_ref, "bundle": bundle}

    monkeypatch.setattr(records, "get", catalog_get)
    monkeypatch.setattr(native_preparation, "read_receipt", preparation)

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("DENOMINATOR_REEXECUTED_PURE")

    monkeypatch.setattr("omnis.modules.tasks.module_registry.run_handler", forbidden)
    monkeypatch.setattr("omnis.modules.settings.skill_catalog.evaluate_pure", forbidden)

    queries: list[str] = []

    class Reader:
        async def execute(self, statement: object, args: Data | None = None) -> Result:
            query = str(statement)
            queries.append(query)
            if query == "SET LOCAL search_path = pg_catalog, public, pg_temp":
                return Result([])
            assert args is not None
            assert "public.catalog_identity" in query and "public.catalog_reservation" in query
            assert args["owner"] == conn.owner
            if args["kind"] == unavailable:
                return Result([])
            return Result(
                [
                    {
                        "package_key": PACKAGE,
                        "entity_key": "map-records" if args["kind"] == "procedure" else "records",
                    }
                ]
            )

    reader = cast(AsyncConnection, Reader())
    if unavailable is not None:
        with pytest.raises(CatalogError, match="REF_UNAVAILABLE"):
            await denominator.retained_material(reader, conn.owner, context, conn.graph)
    else:
        material = await denominator.retained_material(reader, conn.owner, context, conn.graph)
        assert material == (raw, [package_ref], "templates/schemas/records.schema.json")
    assert queries[0] == "SET LOCAL search_path = pg_catalog, public, pg_temp"


@pytest.mark.parametrize("count", [0, 128])
def test_material_change_allocates_next_revision_empty_stays_unknown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    count: int,
) -> None:
    from omnis.modules.coverage import denominator
    from omnis.modules.settings.catalog_models import CatalogError

    conn, request, raw = fixture()

    async def material(*args: object) -> tuple[bytes, list[Data], str]:
        return raw, [], "templates/schemas/records.schema.json"

    monkeypatch.setattr(denominator, "retained_material", material)
    monkeypatch.setattr(contract_inputs, "database_engine", lambda url: cast(AsyncEngine, conn))
    monkeypatch.setenv("OMNIS_DATABASE_URL", "source-double-not-a-dsn")
    path = tmp_path / "request.json"
    path.write_bytes(canonical(request))
    assert contract_inputs.main(["create-denominator", "--request", str(path)]) == 0
    capsys.readouterr()
    context = next(r for r in conn.graph if r["kind"] == "contract-input-context")
    values = [{"method": "GET", "path": "/", "status": 100 + i} for i in range(count)]
    item = produce_input(context, {"records": values}, raw, str(uuid4()))
    conn.graph.append(item)
    changed = {**request, "command_id": str(uuid4()), "input_ref": records.reference(item)}
    path.write_bytes(canonical(changed))
    assert contract_inputs.main(["create-denominator", "--request", str(path)]) == 0
    output = capsys.readouterr()
    assert output.err == "" and contract.mapping(json.loads(output.out))["created"] is True
    path.write_bytes(
        canonical({k: changed[k] for k in ("schema_version", "owner_id", "command_id")})
    )
    assert contract_inputs.main(["read-denominator", "--request", str(path)]) == 0
    body = contract.mapping(contract.mapping(json.loads(capsys.readouterr().out))["denominator"])[
        "payload"
    ]
    body = contract.mapping(body)
    assert body["denominator_revision"] == 2 and body["identity_state"] == "UNKNOWN"
    assert body["operations"] == (
        [] if count == 0 else [{"method": "GET", "path": "/", "statuses": list(range(100, 228))}]
    )
    with pytest.raises(CatalogError, match="COUNT_LIMIT"):
        produce_input(
            context,
            {"records": [{"method": "GET", "path": "/", "status": 200}] * 129},
            raw,
            str(uuid4()),
        )
