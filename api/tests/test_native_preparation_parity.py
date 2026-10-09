"""Producer/runtime parity; source validators only unless the attested PG test runs."""

import base64
import importlib.util
import sys
from pathlib import Path
from typing import Protocol, cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import URL

from omnis.modules.runs import native_preparation_models as api
from omnis.modules.settings import candidate_store as store
from omnis.modules.settings.candidate_material import digest
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical, load_json
from test_native_preparation import bundle_fixture

DESCRIPTION = "description: Use when testing inert C01 exact publication."


class LoadedFile(Protocol):
    def loaded(self) -> dict[str, object]: ...


class RuntimeContract(Protocol):
    LIMITS: dict[str, int]

    def validate_payload(
        self, value: object
    ) -> tuple[dict[str, object], tuple[LoadedFile, ...]]: ...


@pytest.fixture
def runtime_contract(monkeypatch: pytest.MonkeyPatch) -> RuntimeContract:
    # Load the real stdlib contract from THIS checkout, not the native runtime or a double.
    root = Path(__file__).resolve().parents[2]
    path = root / "integrations/hermes/src/omnis_hermes/native_preparation_contract.py"
    spec = importlib.util.spec_from_file_location("native_parity_runtime_contract", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return cast(RuntimeContract, module)


def wire_case(
    metadata: str | None = None,
    support_path: str | None = None,
    support_raw: bytes | None = None,
) -> tuple[dict[str, object], dict[str, bytes], list[tuple[dict[str, object], dict[str, object]]]]:
    # Reseal validator inputs independently of prepare_packages so its new denials cannot
    # prevent the same negative bytes from exercising the real downstream validator.
    seed = bundle_fixture()
    body = api.mapping(seed["payload"])
    package = api.mapping(api.sequence(body["packages"])[0])
    files = {
        api.text(row["path"]): base64.b64decode(api.text(row["content_b64"]), validate=True)
        for item in api.sequence(package["files"])
        for row in [api.mapping(item)]
    }
    if metadata is not None:
        files["SKILL.md"] = files["SKILL.md"].replace(DESCRIPTION.encode(), metadata.encode())
    if support_raw is not None:
        files["NOTICE.md"] = support_raw
    if support_path is not None:
        files[support_path] = files.pop("NOTICE.md")
        manifest = api.mapping(load_json(files["omnis.yaml"]))
        manifest["support_files"] = [
            support_path if path == "NOTICE.md" else path
            for path in api.sequence(manifest["support_files"])
        ]
        files["omnis.yaml"] = canonical(manifest)
    assert len(files) == 10
    listing: list[dict[str, object]] = [
        {"path": path, "size": len(raw), "sha256": digest(raw)}
        for path, raw in sorted(files.items(), key=lambda pair: pair[0].encode())
    ]
    ref = {**api.mapping(package["package_ref"]), "digest": digest(canonical(listing))}
    package = {
        **package,
        "package_ref": ref,
        "files": [
            {**row, "content_b64": base64.b64encode(files[api.text(row["path"])]).decode()}
            for row in listing
        ],
    }
    bundle = store.envelope("native-preparation-bundle", {**body, "packages": [package]})
    material = {"packages/0/" + path: raw for path, raw in files.items()}
    source = {
        "prefix": "packages/0",
        "package_key": package["package_key"],
        "files": listing,
        "package_digest": ref["digest"],
    }
    return bundle, material, [(ref, source)]


def assert_parity(
    runtime: RuntimeContract,
    case: tuple[
        dict[str, object], dict[str, bytes], list[tuple[dict[str, object], dict[str, object]]]
    ],
    accepted: bool,
) -> None:
    bundle, material, selected = case
    before = canonical(bundle), dict(material), canonical(selected)
    reference = store.reference(bundle)
    payload = {"bundle_ref": reference, "bundle": bundle}
    if accepted:
        packages = api.prepare_packages(material, selected)
        assert packages == api.mapping(bundle["payload"])["packages"]
        assert api.validate_bundle(reference, bundle) == bundle
        runtime_ref, loaded = runtime.validate_payload(payload)
        assert runtime_ref == reference
        assert len(loaded) == len(material)
        assert [row.loaded() for row in loaded] == [
            {"package_ref": package["package_ref"], "native_name": package["native_name"], **file}
            for package in packages
            for item in api.sequence(package["files"])
            for file in [api.mapping(item)]
        ]
    else:
        with pytest.raises(ValueError, match="Invalid native preparation"):
            runtime.validate_payload(payload)
        with pytest.raises(CatalogError):
            api.prepare_packages(material, selected)
        with pytest.raises(CatalogError):
            api.validate_bundle(reference, bundle)
    assert (canonical(bundle), material, canonical(selected)) == before


@pytest.mark.parametrize(
    "metadata,accepted",
    [
        pytest.param(None, True, id="real-ten-file-seed"),
        pytest.param("description: |\n  inert", False, id="block-description"),
        pytest.param("description: |-\n  inert", False, id="block-chomping"),
        pytest.param(DESCRIPTION + " # comment", False, id="inline-comment"),
        pytest.param(DESCRIPTION + "\n# comment", False, id="standalone-comment"),
        pytest.param("description: " + "x" * 1024, True, id="plain-1024"),
        pytest.param("description: " + "x" * 1025, False, id="plain-1025"),
        pytest.param("description: " + "x" * 2048, False, id="plain-2048"),
        pytest.param("description: " + "é" * 512, True, id="unicode-1024-bytes"),
        pytest.param("description: " + "é" * 512 + "x", False, id="unicode-1025-bytes"),
        pytest.param('description: "' + "é" * 512 + '"', True, id="double-quoted-unicode"),
        pytest.param('description: "' + "é" * 513 + '"', False, id="quoted-byte-overflow"),
        pytest.param('description: "' + r"\u0061" * 341 + '"', True, id="json-wire-2048"),
        pytest.param('description: "' + r"\u0061" * 342 + '"', False, id="json-wire-overflow"),
        pytest.param("description: 'It''s inert: # literal'", True, id="single-quoted"),
        pytest.param('description: "inert: # literal"', True, id="double-quoted"),
        pytest.param('description: "line\\nbreak"', False, id="escaped-newline"),
        pytest.param('description: "inert\\ttext"', False, id="escaped-tab"),
        pytest.param('description: "\\u0080"', False, id="escaped-c1"),
        pytest.param('description: "\\u2028"', False, id="escaped-line-separator"),
        pytest.param('description: "\\u2029"', False, id="escaped-paragraph-separator"),
        pytest.param('description: "\\e"', False, id="yaml-only-escape"),
        pytest.param(DESCRIPTION + "\nauthor: " + "é" * 513, False, id="author-byte-limit"),
        pytest.param(DESCRIPTION + "\ntags: [inert, 'portable']", True, id="inline-list"),
        pytest.param(DESCRIPTION + "\ntags:\n  - inert\n  - portable", True, id="block-list"),
        pytest.param(DESCRIPTION + "\ntags:\n- inert", False, id="unindented-list"),
        pytest.param(DESCRIPTION + '\ntags: ["a,b"]', False, id="comma-in-quoted-list"),
        pytest.param(DESCRIPTION + "\ntags: [" + "x," * 31 + "x]", True, id="32-items"),
        pytest.param(DESCRIPTION + "\ntags: [" + "x," * 32 + "x]", False, id="33-items"),
        pytest.param(DESCRIPTION + "\ntags: [" + "é" * 513 + "]", False, id="list-byte-limit"),
        pytest.param(DESCRIPTION + "\ndescription: duplicate", False, id="duplicate-key"),
        *[
            pytest.param(DESCRIPTION + f"\n{key}: forbidden", False, id="unsafe-" + key)
            for key in ("metadata", "requirements", "credentials", "setup", "preprocess")
        ],
        pytest.param("description: &anchor inert", False, id="yaml-anchor"),
        pytest.param("description: !!str inert", False, id="yaml-tag"),
    ],
)
def test_frontmatter_parity(
    runtime_contract: RuntimeContract, metadata: str | None, accepted: bool
) -> None:
    assert api.LIMITS == runtime_contract.LIMITS
    assert_parity(runtime_contract, wire_case(metadata=metadata), accepted)


@pytest.mark.parametrize(
    "path,accepted",
    [
        ("references/portable-01_A.txt", True),
        ("assets/" + "a" * 233, True),  # Preserve the producer's stricter 240-byte path cap.
        ("references/café.txt", False),
        ("assets/has space.txt", False),
        ("assets/-leading.txt", False),
        ("assets/colon:name.txt", False),
        ("references/SKILL.md", False),
        ("references/SKILL.md/child.txt", False),
        ("assets/" + "a" * 250, False),  # Beyond runtime's 256 bytes too.
    ],
)
def test_portable_path_parity(runtime_contract: RuntimeContract, path: str, accepted: bool) -> None:
    assert_parity(runtime_contract, wire_case(support_path=path), accepted)


@pytest.mark.parametrize("codepoint", [0x7F, *range(0x80, 0xA0)])
def test_raw_text_control_parity(runtime_contract: RuntimeContract, codepoint: int) -> None:
    assert_parity(
        runtime_contract, wire_case(support_raw=("inert" + chr(codepoint)).encode()), False
    )


def test_raw_text_preserves_unicode_newlines_tabs(runtime_contract: RuntimeContract) -> None:
    assert_parity(runtime_contract, wire_case(support_raw="é\n\ttext\u2028body".encode()), True)


def test_producer_keeps_stricter_path_limit(runtime_contract: RuntimeContract) -> None:
    for size in (241, 256):
        bundle, material, selected = wire_case(support_path="assets/" + "a" * (size - 7))
        runtime_contract.validate_payload({"bundle_ref": store.reference(bundle), "bundle": bundle})
        with pytest.raises(CatalogError, match="INVALID_PATH"):
            api.prepare_packages(material, selected)


@pytest.mark.parametrize("duplicate", [False, True])
def test_duplicate_package_key_refused_before_bundle_commit(
    runtime_contract: RuntimeContract, duplicate: bool
) -> None:
    bundle, original, _ = wire_case()
    packages: list[dict[str, object]] = []
    material: dict[str, bytes] = {}
    selected: list[tuple[dict[str, object], dict[str, object]]] = []
    # Distinct names/refs; duplicate key is the only difference from the control.
    # Strip inert support bytes and unused support declarations to stay at 16 files.
    manifest = api.mapping(load_json(original["packages/0/omnis.yaml"]))
    manifest["support_files"] = api.sequence(manifest["support_files"])[:5]
    expected = [
        "omnis.yaml",
        "SKILL.md",
        *api.sequence(manifest["procedures"]),
        *api.sequence(manifest["support_files"]),
    ]
    for index, name in enumerate(("parity-a", "parity-b")):
        prefix = f"packages/{index}"
        raw_files = {api.text(path): b"" for path in expected}
        key = manifest["package_key"] if index == 0 or duplicate else "parity-other"
        raw_files["omnis.yaml"] = canonical({**manifest, "package_key": key, "native_name": name})
        raw_files["SKILL.md"] = f"---\nname: {name}\ndescription: inert\n---\nbody\n".encode()
        listing: list[dict[str, object]] = [
            {"path": path, "size": len(raw), "sha256": digest(raw)}
            for path, raw in sorted(raw_files.items())
        ]
        ref = {
            "kind": "package",
            "id": str(uuid4()),
            "revision": 1,
            "digest": digest(canonical(listing)),
        }
        source = {
            "prefix": prefix,
            "package_key": key,
            "files": listing,
            "package_digest": ref["digest"],
        }
        material.update({prefix + "/" + path: raw for path, raw in raw_files.items()})
        selected.append((ref, source))
        packages.extend(api.prepare_packages(material, [(ref, source)]))
    bundle = store.envelope(
        "native-preparation-bundle", {**api.mapping(bundle["payload"]), "packages": packages}
    )
    assert len(material) == api.LIMITS["max_files"]
    assert sum(map(len, material.values())) <= api.LIMITS["max_total_raw_bytes"]
    assert_parity(runtime_contract, (bundle, material, selected), not duplicate)


def test_pg_published_block_description_refused_before_t1(
    migrated_database_url: "URL", monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real qualification/publication/selection; never provisioned outside conftest."""
    import asyncio
    from unittest.mock import AsyncMock

    from fixtures.b06b_publication.consumer import confirmed, new_seed, publish_request, qualify
    from fixtures.b06b_pure_probe.consumer import Probe
    from omnis.core.db import database_engine
    from omnis.modules.instance.schemas import NativePrepareCommand
    from omnis.modules.instance.service import InstanceService
    from omnis.modules.runs.native_preparation import NativePreparation
    from omnis.supervisor.runtime_client import RuntimeClient
    from test_b06b_pure_probe_pg import Published, ledger
    from test_native_preparation import command

    dsn = migrated_database_url.render_as_string(hide_password=False)
    seed = new_seed()
    skill = seed.package / "SKILL.md"
    raw = skill.read_bytes().replace(
        DESCRIPTION.encode(),
        b"description: |-\n  Use when testing inert C01 exact publication.",
    )
    skill.write_bytes(raw)
    qualified = qualify(seed, dsn)
    publication = seed.success(
        "publish", publish_request(qualified, confirmed(qualified, dsn)), dsn
    )
    snapshot = seed.success(
        "snapshot", seed.write(publication_ref=publication["publication_ref"]), dsn
    )
    probe = Probe(seed.directory, seed.package, seed.profile, seed.root, seed.owner)
    published = Published(qualified, probe, migrated_database_url, snapshot)
    _, selected = published.selected()
    before = ledger(migrated_database_url)

    async def run() -> None:
        engine = database_engine(dsn)
        service, owner = InstanceService(engine), uuid4()
        try:
            epoch = await service.acquire(owner)
            status = await service.owned_status(owner, epoch)
            runtime = RuntimeClient(seed.directory, generation=status.generation, epoch=epoch)
            consumer = NativePreparation(engine, seed.root, service, owner, epoch, runtime)
            cmd = NativePrepareCommand.model_validate(
                {
                    **command(),
                    "owner_id": seed.owner,
                    "instance_id": str(status.instance_id),
                    "expected_epoch": epoch,
                    "expected_generation": status.generation,
                    "selection_ref": selected["selection_ref"],
                }
            )
            put = AsyncMock(side_effect=AssertionError("T1 store.put reached"))
            complete = AsyncMock(side_effect=AssertionError("T1 store.complete reached"))
            dispatch = AsyncMock(side_effect=AssertionError("runtime dispatch reached"))
            with monkeypatch.context() as patch:
                patch.setattr(store, "put", put)
                patch.setattr(store, "complete", complete)
                patch.setattr(runtime, "prepare", dispatch)
                async with engine.connect() as connection:
                    with pytest.raises(CatalogError, match="PREPARATION_REJECTED"):
                        await consumer.build(connection, cmd)
                # Same command can be refused repeatedly: no INDETERMINATE reservation.
                for _ in range(2):
                    with pytest.raises(CatalogError, match="PREPARATION_REJECTED"):
                        await consumer.prepare(cmd)
                put.assert_not_awaited()
                complete.assert_not_awaited()
                dispatch.assert_not_awaited()
            await service.release(owner, epoch)
        finally:
            await engine.dispose()

    asyncio.run(run())
    assert ledger(migrated_database_url) == before
    assert skill.read_bytes() == raw
