"""Real catalog pipeline with an explicit SOURCE-only storage seam, plus PG acceptance.

The source seam does not prove transactions, durability, reservations or human consent.
The PG test uses the existing attested fixture and must run only after parent review.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Self
from uuid import uuid4

import pytest
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.core.db import database_engine
from omnis.modules.settings import candidate_catalog as candidates
from omnis.modules.settings import candidate_store as store
from omnis.modules.settings import publication_store as heads
from omnis.modules.settings.candidate_material import digest
from omnis.modules.settings.catalog_models import CatalogError, ExactRef
from omnis.modules.settings.catalog_publication import PublicationCatalog
from omnis.modules.settings.catalog_schema import canonical, load_json
from test_agent_core_catalog import PACKAGE, PROFILE


class Rows:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def scalars(self) -> Self:
        return self

    def all(self) -> list[dict[str, object]]:
        return self.rows

    def mappings(self) -> Self:
        return self

    def one_or_none(self) -> dict[str, object] | None:
        assert len(self.rows) <= 1
        return self.rows[0] if self.rows else None


@pytest.fixture
def storage_seam(monkeypatch: pytest.MonkeyPatch) -> AsyncEngine:
    """Replace only storage, not capture/review/freeze/eval/publication/composition."""
    rows: dict[str, tuple[str, str, dict[str, object]]] = {}
    commands: dict[tuple[str, str, str], tuple[bytes, dict[str, object]]] = {}
    bindings: list[dict[str, object]] = []
    current: dict[str, object] = {}
    connection = object.__new__(AsyncConnection)
    engine = object.__new__(AsyncEngine)

    @asynccontextmanager
    async def begin(self: AsyncEngine) -> AsyncIterator[AsyncConnection]:
        yield connection

    async def lock(connection: AsyncConnection, key: str) -> None:
        return None

    async def put(
        connection: AsyncConnection, owner: str, group: str, record: dict[str, object]
    ) -> None:
        checked = store.checked(load_json(canonical(record)))
        identifier = str(checked["id"])
        assert identifier not in rows
        rows[identifier] = (owner, group, checked)

    async def get(
        connection: AsyncConnection, owner: str, ref: dict[str, object]
    ) -> tuple[str, dict[str, object]]:
        found = rows.get(str(ref["id"]))
        if found is None or found[0] != owner:
            raise CatalogError("REF_UNAVAILABLE")
        record = store.checked(found[2])
        if store.reference(record) != ref:
            raise CatalogError("REF_MISMATCH")
        return found[1], record

    async def replay(
        connection: AsyncConnection,
        owner: str,
        command: str,
        operation: str,
        request: dict[str, object],
    ) -> dict[str, object] | None:
        prior = commands.get((owner, command, operation))
        if prior is not None:
            assert prior[0] == canonical(request)
            return prior[1]
        return None

    async def complete(
        connection: AsyncConnection,
        owner: str,
        command: str,
        operation: str,
        request: dict[str, object],
        result: dict[str, object],
    ) -> None:
        commands[(owner, command, operation)] = (canonical(request), result)

    async def reserve(
        connection: AsyncConnection,
        owner: str,
        draft: str,
        identities: list[tuple[str, str, str, str]],
    ) -> list[dict[str, object]]:
        assert not bindings
        for package, kind, key, sha in identities:
            bindings.append(
                {
                    "package_key": package,
                    "entity_kind": kind,
                    "key": key,
                    "ref": {"kind": kind, "id": str(uuid4()), "revision": 1, "digest": sha},
                }
            )
        return [candidates.valid_ref(b["ref"]) for b in bindings]

    async def reservation_bindings(
        connection: AsyncConnection,
        owner: str,
        refs: list[dict[str, object]],
        records: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        assert {canonical(r) for r in refs} == {canonical(b["ref"]) for b in bindings}
        return bindings

    async def execute(
        self: AsyncConnection,
        statement: object,
        parameters: dict[str, object],
    ) -> Rows:
        sql = str(statement)
        if sql == "SELECT owner_id, group_id, envelope FROM catalog_record WHERE id=:id":
            found = rows.get(str(parameters["id"]))
            return Rows(
                []
                if found is None
                else [{"owner_id": found[0], "group_id": found[1], "envelope": found[2]}]
            )
        if (
            sql
            == "SELECT operation, result FROM catalog_command WHERE owner_id=:owner AND command_id=:command"
        ):
            return Rows(
                [
                    {"operation": operation, "result": result}
                    for (owner, command, operation), (_, result) in commands.items()
                    if (owner, command) == (parameters["owner"], parameters["command"])
                ]
            )
        kind = next(
            k
            for k in ("source-draft", "candidate-snapshot", "evaluation-receipt")
            if "kind='" + k + "'" in sql
        )
        return Rows(
            sorted(
                [
                    r
                    for who, group, r in rows.values()
                    if who == parameters["owner"]
                    and group == parameters["group"]
                    and r["kind"] == kind
                ],
                key=lambda r: str(r["id"]),
            )
        )

    async def scalar(
        self: AsyncConnection,
        statement: object,
        parameters: dict[str, object],
    ) -> None:
        assert "candidate-rejection" in str(statement)
        return None

    async def capture_head(
        connection: AsyncConnection, owner: str, draft: dict[str, object]
    ) -> None:
        current.update(
            generation=1,
            profile_key=heads.profile_key(draft),
            draft_ref=store.reference(draft),
            publication_ref=None,
        )

    async def head(
        connection: AsyncConnection, owner: str, draft: dict[str, object]
    ) -> dict[str, object]:
        return dict(current)

    async def promote(
        connection: AsyncConnection,
        owner: str,
        key: str,
        value: dict[str, object],
        publication: dict[str, object],
    ) -> int:
        heads.check_head(current, value)
        generation = current["generation"]
        assert isinstance(generation, int)
        current.update(generation=generation + 1, publication_ref=store.reference(publication))
        return generation + 1

    for name, implementation in (
        ("get", get),
        ("put", put),
        ("lock", lock),
        ("replay", replay),
        ("complete", complete),
        ("reserve", reserve),
        ("reservation_bindings", reservation_bindings),
    ):
        monkeypatch.setattr(store, name, implementation)
    for name, head_implementation in (
        ("capture_head", capture_head),
        ("head", head),
        ("promote", promote),
    ):
        monkeypatch.setattr(heads, name, head_implementation)
    monkeypatch.setattr(AsyncEngine, "begin", begin)
    monkeypatch.setattr(AsyncEngine, "connect", begin)
    monkeypatch.setattr(AsyncConnection, "execute", execute)
    monkeypatch.setattr(AsyncConnection, "scalar", scalar)
    return engine


async def publish_core(
    engine: AsyncEngine,
    root: Path,
    *,
    package: Path = PACKAGE,
    profile: Path = PROFILE,
    pure_input: dict[str, object] | None = None,
) -> tuple[PublicationCatalog, str, dict[str, object]]:
    owner = str(uuid4())
    catalog = PublicationCatalog(engine, root)

    def command(**values: object) -> dict[str, object]:
        return {"schema_version": 1, "owner_id": owner, "command_id": str(uuid4()), **values}

    captured = await catalog.candidates.dispatch(
        "capture", command(author_kind="IMPORT", packages=[str(package)], profile=str(profile))
    )
    source = {key: captured[key] for key in ("draft_ref", "source_draft_refs")}
    review = await catalog.candidates.dispatch("review", command(**source))
    assert review["status"] == "STATIC_PASS"
    frozen = await catalog.candidates.dispatch(
        "freeze", command(**source, technical_review_ref=review["technical_review_ref"])
    )
    snapshot_ref = candidates.valid_ref(frozen["snapshot_ref"])
    back = await catalog.candidates.dispatch(
        "readback", {"schema_version": 1, "owner_id": owner, "snapshot_ref": snapshot_ref}
    )
    assert back["publication"] == "UNPUBLISHED" and back["assessment_selectable"] is False
    with pytest.raises(CatalogError):
        await catalog.dispatch(
            "readback", {"schema_version": 1, "owner_id": owner, "publication_ref": snapshot_ref}
        )
    evaluations = []
    for kind in ("STATIC", "PURE"):
        evaluation = await catalog.candidates.dispatch(
            "evaluate",
            command(
                snapshot_ref=snapshot_ref,
                evaluation_kind=kind,
                input=None
                if kind == "STATIC"
                else (
                    {"context": "owner-selected synthetic context"}
                    if pure_input is None
                    else pure_input
                ),
            ),
        )
        assert evaluation["status"] == kind + "_PASS"
        evaluations.append(evaluation)
    selection = {
        **source,
        "snapshot_ref": snapshot_ref,
        "technical_review_ref": review["technical_review_ref"],
        "material_digest": captured["material_digest"],
        "resolved_index_digest": review["resolved_index_digest"],
        "dependency_closure_digest": digest(canonical([])),
        "static_evaluation_ref": evaluations[0]["evaluation_ref"],
        "pure_evaluation_ref": evaluations[1]["evaluation_ref"],
        "expected_head_generation": 1,
    }
    with pytest.raises(CatalogError, match="OPERATOR_CONFIRMATION_REQUIRED"):
        await catalog.dispatch("confirm", command(**selection))
    # Trusted fixture only: production confirm remains the existing human TTY channel.
    confirmed = await catalog._dispatch("confirm", command(**selection))
    published = await catalog.dispatch(
        "publish", command(**selection, confirmation_ref=confirmed["confirmation_ref"])
    )
    ref = candidates.valid_ref(published["publication_ref"])
    back = await catalog.dispatch(
        "readback", {"schema_version": 1, "owner_id": owner, "publication_ref": ref}
    )
    assert back["publication"] == published["publication"]
    return catalog, owner, ref


async def core_consumer(engine: AsyncEngine, root: Path) -> None:
    catalog, owner, publication_ref = await publish_core(engine, root)
    from omnis.modules.tasks import agent_composition

    async with engine.connect() as connection:
        composition = await agent_composition.compose_publication(
            catalog,
            connection,
            owner,
            ExactRef.model_validate(publication_ref),
            role="BRAIN",
            brief="Read the selected synthetic context; report gaps.",
        )
    from agents import Agent

    agent = Agent[None](name="S1 inert core", instructions=composition.text, tools=[], handoffs=[])
    assert isinstance(agent.instructions, str)
    assert agent.instructions == composition.text
    assert "YOU ARE THE ROOT AGENT" in composition.text
    assert composition.text_digest == digest(composition.text.encode())
    assert composition.publication_ref.model_dump(mode="json") == publication_ref
    print(
        canonical(
            {
                "consumer": "agents.Agent.instructions",
                "sdk": "openai-agents==0.19.0",
                "role": "BRAIN",
                "instruction_bytes": len(agent.instructions.encode()),
                "text_digest": composition.text_digest,
                "material_digest": composition.material_digest,
                "resolved_index_digest": composition.resolved_index_digest,
                "composer_revision": composition.composer_revision,
                "inference": "NOT_RUN",
                "scope": "STATIC_PURE_CONSTRUCTION_ONLY",
            }
        ).decode()
    )


@pytest.mark.asyncio
async def test_core_publication_composition_source(
    storage_seam: AsyncEngine, tmp_path: Path
) -> None:
    await core_consumer(storage_seam, tmp_path / "catalog")


@pytest.mark.asyncio
async def test_core_composition_is_exact_bounded_and_role_specific(
    storage_seam: AsyncEngine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import FrozenInstanceError

    from omnis.modules.tasks.agent_composition import MAX_CONTEXT_BYTES, compose_publication

    catalog, owner, ref = await publish_core(storage_seam, tmp_path / "catalog")
    publication_ref = ExactRef.model_validate(ref)

    def no_evaluation(*args: object, **kwargs: object) -> None:
        raise AssertionError("publication readback must not reexecute PURE")

    monkeypatch.setattr(candidates, "evaluate_pure", no_evaluation)
    async with storage_seam.connect() as connection:
        original = await compose_publication(
            catalog, connection, owner, publication_ref, role="RECON", brief="x"
        )
        assert "YOU ARE THE ROOT AGENT" not in original.text
        sections = load_json(original.text)
        assert isinstance(sections, list)
        assert [s["section"] for s in sections if isinstance(s, dict)] == [
            "base",
            "role",
            "brief",
            "skill",
        ]
        assert original.provenance and len(original.skill_refs) == 1
        with pytest.raises(FrozenInstanceError):
            original.__setattr__("text", "replacement")
        deduped = await compose_publication(
            catalog,
            connection,
            owner,
            publication_ref,
            role="RECON",
            brief="x",
            selected_skill_refs=(*original.skill_refs, *original.skill_refs),
        )
        assert deduped == original
        for selection in (
            (),
            (original.skill_refs[0].model_copy(update={"digest": "0" * 64}),),
            (original.role_ref,),
        ):
            with pytest.raises(CatalogError, match="COMPOSITION_REF_MISMATCH"):
                await compose_publication(
                    catalog,
                    connection,
                    owner,
                    publication_ref,
                    role="RECON",
                    brief="x",
                    selected_skill_refs=selection,
                )
        remaining = MAX_CONTEXT_BYTES - len(original.text.encode()) + 1
        exact = await compose_publication(
            catalog, connection, owner, publication_ref, role="RECON", brief="x" * remaining
        )
        assert len(exact.text.encode()) == MAX_CONTEXT_BYTES
        with pytest.raises(CatalogError, match="COMPOSITION_LIMIT"):
            await compose_publication(
                catalog,
                connection,
                owner,
                publication_ref,
                role="RECON",
                brief="x" * (remaining + 1),
            )
        with pytest.raises(CatalogError, match="REF_UNAVAILABLE"):
            await compose_publication(
                catalog, connection, str(uuid4()), publication_ref, role="RECON", brief="x"
            )
        with pytest.raises(CatalogError, match="REF_MISMATCH"):
            await compose_publication(
                catalog,
                connection,
                owner,
                publication_ref.model_copy(update={"digest": "0" * 64}),
                role="RECON",
                brief="x",
            )
        for role in ("INVESTIGATOR", "VALIDATOR"):
            composed = await compose_publication(
                catalog,
                connection,
                owner,
                publication_ref,
                role=role,
                brief="independent assignment",
            )
            assert "YOU ARE THE ROOT AGENT" not in composed.text
        paths = list((catalog.root / "candidates").rglob("SKILL.md"))
        assert len(paths) == 1
        paths[0].chmod(0o600)
        paths[0].write_bytes(paths[0].read_bytes() + b"\ntampered\n")
        paths[0].chmod(0o400)
        with pytest.raises(CatalogError, match="FROZEN_MATERIAL_MISMATCH"):
            await compose_publication(
                catalog, connection, owner, publication_ref, role="RECON", brief="x"
            )


@pytest.mark.asyncio
async def test_failed_core_evaluation_cannot_be_confirmed(
    storage_seam: AsyncEngine,
    tmp_path: Path,
) -> None:
    from omnis.modules.settings.publication_models import selection

    catalog, owner, ref = await publish_core(storage_seam, tmp_path / "catalog")
    back = await catalog.dispatch(
        "readback", {"schema_version": 1, "owner_id": owner, "publication_ref": ref}
    )
    published = back["publication"]
    assert isinstance(published, dict)
    selected = selection(candidates.payload(published))
    failed = await catalog.candidates._dispatch(
        "evaluate",
        {
            "schema_version": 1,
            "owner_id": owner,
            "command_id": str(uuid4()),
            "snapshot_ref": selected["snapshot_ref"],
            "evaluation_kind": "PURE",
            "input": {"context": "synthetic", "grant": "shell"},
        },
    )
    assert failed["status"] == "BLOCKED" and failed["reason"] == "SCHEMA_VALIDATION"
    with pytest.raises(CatalogError, match="EVALUATION_MISMATCH"):
        await catalog._dispatch(
            "confirm",
            {
                "schema_version": 1,
                "owner_id": owner,
                "command_id": str(uuid4()),
                **selected,
                "pure_evaluation_ref": failed["evaluation_ref"],
            },
        )


@pytest.mark.asyncio
async def test_core_cannot_enter_legacy_run_snapshot(
    storage_seam: AsyncEngine,
    tmp_path: Path,
) -> None:
    catalog, owner, ref = await publish_core(storage_seam, tmp_path / "catalog")
    with pytest.raises(CatalogError, match="CORE_SNAPSHOT_OWNER_REQUIRED"):
        await catalog.dispatch(
            "snapshot",
            {
                "schema_version": 1,
                "owner_id": owner,
                "command_id": str(uuid4()),
                "publication_ref": ref,
            },
        )


def test_missing_evaluator_revision_is_not_compiler_only() -> None:
    assert not candidates.readable_revisions(candidates.COMPILER_REVISION, None)


@pytest.mark.asyncio
async def test_retained_v1_publication_readback_preserves_original_revisions(
    storage_seam: AsyncEngine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from omnis.modules.settings import catalog_publication as publication

    source = Path(__file__).parent / "fixtures/b06b_publication/source"
    old_compiler = "sha256:7958c3676989ca829d80ceac99284118ad6b08af7994f0e43211a8b06ad8733b"
    old_evaluator = "sha256:47fddea827616d5fe1779e653c71e487d072b9c11ccde3d4598bc2ec8715b6d9"
    with monkeypatch.context() as legacy:
        for module in (candidates, publication):
            legacy.setattr(module, "COMPILER_REVISION", old_compiler)
        legacy.setattr(candidates, "EVALUATOR_REVISION", old_evaluator)
        catalog, owner, ref = await publish_core(
            storage_seam,
            tmp_path / "legacy",
            package=source / "b06b-publish-contract",
            profile=source / "profile.yaml",
            pure_input={"capture": "[]"},
        )
        before = await catalog.dispatch(
            "readback", {"schema_version": 1, "owner_id": owner, "publication_ref": ref}
        )
    after = await catalog.dispatch(
        "readback", {"schema_version": 1, "owner_id": owner, "publication_ref": ref}
    )
    assert canonical(before) == canonical(after)
    assert candidates.COMPILER_REVISION != old_compiler
    async with storage_seam.connect() as connection:
        with pytest.raises(CatalogError, match="CORE_PUBLICATION_REQUIRED"):
            await catalog.load_core(connection, owner, ref)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation", ["snapshot", "select", "execute", "native-build", "managed-source"]
)
@pytest.mark.parametrize("legacy", [False, True])
async def test_probe_legacy_is_read_only_at_each_new_admission(
    storage_seam: AsyncEngine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    legacy: bool,
) -> None:
    from omnis.modules.instance.schemas import NativePrepareCommand
    from omnis.modules.runs import native_preparation, pure_probe
    from omnis.modules.runs.managed_admission import ManagedAdmission
    from omnis.modules.settings import catalog_publication as publication
    from test_native_preparation import command as native_command
    from test_native_preparation import worker_fixture

    source = Path(__file__).parent / "fixtures/b06b_publication/source"
    with monkeypatch.context() as revisions:
        if legacy:
            for module in (candidates, publication):
                revisions.setattr(module, "COMPILER_REVISION", candidates.LEGACY_COMPILER_REVISION)
            revisions.setattr(
                candidates, "EVALUATOR_REVISION", candidates.LEGACY_EVALUATOR_REVISION
            )
            revisions.setattr(
                pure_probe,
                "EXECUTOR_REVISION",
                "sha256:8a2772da2182682eee14e275bf84529939e4575d418bccd3d42a66d59e026e9e",
            )
        catalog, owner, ref = await publish_core(
            storage_seam,
            tmp_path / "catalog",
            package=source / "b06b-publish-contract",
            profile=source / "profile.yaml",
            pure_input={"capture": "[]"},
        )

        def command(**values: object) -> dict[str, object]:
            return {"schema_version": 1, "owner_id": owner, "command_id": str(uuid4()), **values}

        probe = pure_probe.PureProbe(storage_seam, catalog.root)
        snapshot_request = command(publication_ref=ref)
        snapshot = await catalog.dispatch("snapshot", snapshot_request)
        async with storage_seam.connect() as connection:
            _, _, profile, _ = await catalog.load_probe(
                connection, owner, candidates.valid_ref(snapshot["snapshot_ref"])
            )
        select_request = command(
            snapshot_ref=snapshot["snapshot_ref"], recipe_key=profile.agent_recipes[0].key
        )
        selected = await probe.dispatch("select", select_request)
        execute_request = command(selection_ref=selected["selection_ref"], input={"capture": "[]"})
        executed = await probe.dispatch("execute", execute_request)
        before = await catalog.dispatch(
            "readback", {"schema_version": 1, "owner_id": owner, "publication_ref": ref}
        )
        builder = object.__new__(native_preparation.NativePreparation)
        builder.engine, builder.root, builder.publications = storage_seam, catalog.root, catalog
        native_request = NativePrepareCommand.model_validate(
            {**native_command(), "owner_id": owner, "selection_ref": selected["selection_ref"]}
        )
        async with storage_seam.connect() as connection:
            group, bundle = await builder.build(connection, native_request)
            # Synthetic retained worker receipt, not native execution or historical PG data.
            receipt = store.envelope(
                "native-preparation-receipt",
                {
                    "bundle_ref": store.reference(bundle),
                    "selection_ref": selected["selection_ref"],
                    "status": "PREPARED",
                    "loader_result": worker_fixture(bundle),
                    "authority": {
                        "instance_id": native_request.instance_id,
                        "supervisor_owner": str(uuid4()),
                        "epoch": 1,
                        "generation": 0,
                        "runtime_boot": str(uuid4()),
                    },
                },
            )
            receipt["id"] = native_preparation.receipt_id(bundle)
            receipt["digest"] = digest(
                canonical({k: v for k, v in receipt.items() if k != "digest"})
            )
            await store.put(connection, owner, group, bundle)
            await store.put(connection, owner, group, receipt)
            await store.complete(
                connection,
                owner,
                native_request.command_id,
                native_preparation.OPERATION,
                native_request.model_dump(mode="json", exclude={"op"}),
                {"bundle_ref": store.reference(bundle)},
            )
            prepared = await native_preparation.read_receipt(
                connection, owner, store.reference(bundle)
            )
    before_bytes = canonical(before)
    files_before = {str(p): p.read_bytes() for p in catalog.root.rglob("*") if p.is_file()}

    def no_effect(*args: object, **kwargs: object) -> None:
        raise AssertionError("read/replay or legacy admission reached a write/execution sink")

    with monkeypatch.context() as sinks:
        sinks.setattr(store, "put", no_effect)
        sinks.setattr(store, "complete", no_effect)
        sinks.setattr(pure_probe, "execute_outputs", no_effect)
        sinks.setattr(candidates, "evaluate_pure", no_effect)
        # Already retained snapshots/selections remain readable, not executable authority.
        assert await catalog.dispatch("snapshot", snapshot_request) == snapshot
        assert await probe.dispatch("select", select_request) == selected
        assert await probe.dispatch("execute", execute_request) == executed
        probe_back = await probe.dispatch(
            "readback",
            {"schema_version": 1, "owner_id": owner, "receipt_ref": executed["receipt_ref"]},
        )
        assert probe_back["receipt"] == executed["receipt"]
        after = await catalog.dispatch(
            "readback", {"schema_version": 1, "owner_id": owner, "publication_ref": ref}
        )
        assert before_bytes == canonical(after)
        published = before["publication"]
        assert isinstance(published, dict)
        from omnis.modules.settings.publication_models import selection

        async with storage_seam.connect() as connection:
            confirmation_ref = candidates.valid_ref(
                candidates.payload(published)["confirmation_ref"]
            )
            _, confirmation = await store.get(connection, owner, confirmation_ref)
            await catalog._revalidate(
                connection,
                owner,
                "confirm",
                command(**selection(candidates.payload(published))),
                {"confirmation_ref": confirmation_ref, "confirmation": confirmation},
            )
        native_back = await native_preparation.readback(
            storage_seam,
            {"schema_version": 1, "owner_id": owner, "command_id": native_request.command_id},
        )
        assert canonical(native_back) == canonical(prepared)
        # Replay has no service/runtime object to fall back to.
        assert await builder.prepare(native_request) == native_preparation.success(prepared)
        if operation in {"native-build", "managed-source"}:
            managed = ManagedAdmission(storage_seam, catalog.root)
            async with storage_seam.connect() as connection:
                if legacy:
                    with pytest.raises(CatalogError, match="^LEGACY_READ_ONLY$"):
                        if operation == "native-build":
                            await builder.build(
                                connection,
                                native_request.model_copy(update={"command_id": str(uuid4())}),
                            )
                        else:
                            await managed._source(
                                connection,
                                owner,
                                {"selection_ref": selected["selection_ref"]},
                                preparation_ref=store.reference(receipt),
                            )
                elif operation == "native-build":
                    _, fresh_bundle = await builder.build(
                        connection, native_request.model_copy(update={"command_id": str(uuid4())})
                    )
                    assert fresh_bundle["kind"] == "native-preparation-bundle"
                    assert (
                        candidates.payload(fresh_bundle)["selection_ref"]
                        == selected["selection_ref"]
                    )
                    packages = candidates.payload(fresh_bundle)["packages"]
                    assert isinstance(packages, list) and len(packages) == 1
                else:
                    build_source = await managed._source(
                        connection,
                        owner,
                        {"selection_ref": selected["selection_ref"]},
                        preparation_ref=store.reference(receipt),
                    )
                    assert build_source.selection == selected["selection"]
                    assert build_source.preparation_bundle == bundle
            assert files_before == {
                str(p): p.read_bytes() for p in catalog.root.rglob("*") if p.is_file()
            }
            return
        request = {
            "snapshot": snapshot_request,
            "select": select_request,
            "execute": execute_request,
        }[operation]
        consumer = catalog if operation == "snapshot" else probe
        if legacy:
            with pytest.raises(CatalogError, match="^LEGACY_READ_ONLY$"):
                await consumer.dispatch(operation, {**request, "command_id": str(uuid4())})
    if not legacy:
        fresh = await consumer.dispatch(operation, {**request, "command_id": str(uuid4())})
        assert fresh != {"snapshot": snapshot, "select": selected, "execute": executed}[operation]
    else:
        assert files_before == {
            str(p): p.read_bytes() for p in catalog.root.rglob("*") if p.is_file()
        }


@pytest.mark.asyncio
async def test_catalog_candidates_pg_core_publication_composition(
    migrated_database_url: URL,
    tmp_path: Path,
) -> None:
    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    try:
        await core_consumer(engine, tmp_path / "catalog")
    finally:
        await engine.dispose()
