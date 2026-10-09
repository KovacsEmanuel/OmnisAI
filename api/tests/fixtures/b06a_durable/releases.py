"""Bounded private test-only qualified RELEASE fixtures; never Publish.

``external`` repeats the existing real compiler/PURE producer, not a renamed
CandidateSnapshot. ``install_fixture`` inserts immutable fixture rows only on the
shared attestor's UUID disposable migrated DB. It neither provisions nor adopts.

Installed QA may load this file with importlib.util (register in sys.modules
before exec_module), pass its installed interpreter and exact candidate_catalog
__file__ to Harness, and use its seed/external/install_fixture APIs directly.
No fixture generation imports a test module. Raw subprocess/pytest logs must
remain private; print only scenario/status/reason/count, never DSNs/tracebacks.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from uuid import UUID, uuid4

import psycopg
import yaml
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from omnis.modules.settings import candidate_catalog, skill_catalog
from omnis.modules.settings.candidate_index import index_source, resolved_index
from omnis.modules.settings.candidate_material import capture, finalize
from omnis.modules.settings.candidate_resolution import ReleasePackage
from omnis.modules.settings.candidate_store import envelope, reference

ROOT = Path(__file__).resolve().parents[4]
PURE_INPUT = {"capture": '[{"method":"GET","path":"/synthetic","status":200}]'}
MAX_FIXTURE_RELEASES = 4


def mapping(value: object) -> dict[str, object]:
    assert isinstance(value, dict) and all(type(k) is str for k in value)
    return {str(k): v for k, v in value.items()}


def sequence(value: object) -> list[object]:
    assert isinstance(value, list)
    return [v for v in value]


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def checked_record(raw: bytes) -> dict[str, object]:
    record = mapping(json.loads(raw))
    assert set(record) == {"schema_version", "kind", "id", "revision", "payload", "digest"}
    assert type(record["schema_version"]) is int and record["schema_version"] == 1
    assert type(record["revision"]) is int and record["revision"] >= 1
    assert type(record["id"]) is str and str(UUID(str(record["id"]))) == record["id"]
    assert record["digest"] == sha(canonical({k: v for k, v in record.items() if k != "digest"}))
    mapping(record["payload"])
    return record


def payload(raw: bytes) -> dict[str, object]:
    return mapping(checked_record(raw)["payload"])


def seed(directory: Path, key: str) -> tuple[Path, Path]:
    """Copy only the explicit inert seed; authored string values retain YAML types."""
    assert re.fullmatch(r"[a-z][a-z0-9_.-]{0,127}", key)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    package = directory / key
    shutil.copytree(ROOT / "skills/recon-mapping-contract", package)
    profile = directory / f"{key}.yaml"
    for path, raw in (
        (profile, (ROOT / "profiles/recon-mapping-contract.yaml").read_text()),
        (package / "omnis.yaml", (package / "omnis.yaml").read_text()),
        (package / "SKILL.md", (package / "SKILL.md").read_text()),
    ):
        path.write_text(raw.replace("recon-mapping-contract", key))
    return package, profile


def yaml_document(path: Path) -> dict[str, object]:
    return mapping(yaml.safe_load(path.read_bytes()))


def write_yaml(path: Path, document: dict[str, object]) -> None:
    """Do not normalize pins: ensure the same literal tree survives serialization."""
    raw = yaml.safe_dump(document, sort_keys=False, allow_unicode=True)
    assert yaml.safe_load(raw) == document
    path.write_text(raw)


def binding(release: ReleasePackage, kind: str, key: str) -> dict[str, object]:
    matches = [
        mapping(item["ref"])
        for value in sequence(payload(release.artifact_json)["bindings"])
        if (item := mapping(value))["entity_kind"] == kind and item["key"] == key
    ]
    assert len(matches) == 1
    return matches[0]


def select_schema(package: Path, release: ReleasePackage, field: str = "input_schema_ref") -> None:
    path = package / "omnis.yaml"
    document = yaml_document(path)
    key = "capture" if field == "input_schema_ref" else "surface_map"
    document[field] = {"kind": "RELEASE", "ref": binding(release, "schema", key)}
    write_yaml(path, document)


def select_profile(profile: Path, release: ReleasePackage) -> None:
    document = yaml_document(profile)
    recipe = mapping(sequence(document["agent_recipes"])[0])
    recipe["package_refs"] = [
        *sequence(recipe["package_refs"]),
        {
            "kind": "RELEASE",
            "ref": binding(release, "package", str(payload(release.artifact_json)["package_key"])),
        },
    ]
    for kind, key in (("technique", "capture-mapping"), ("procedure", "map-capture")):
        recipe[kind + "_refs"] = [{"kind": "RELEASE", "ref": binding(release, kind, key)}]
    document["agent_recipes"] = [recipe]
    write_yaml(profile, document)


def package_digest(package: Path) -> str:
    manifest = yaml_document(package / "omnis.yaml")
    names = ["omnis.yaml", str(manifest["skill_path"])]
    names.extend(str(n) for n in sequence(manifest["procedures"]))
    names.extend(str(n) for n in sequence(manifest["support_files"]))
    assert len(names) == len(set(names))
    entries = []
    for name in sorted(names, key=lambda n: n.encode("utf-8")):
        raw = (package / name).read_bytes()
        entries.append({"path": name, "sha256": sha(raw), "size": len(raw)})
    return sha(canonical(entries))


def check_release(release: ReleasePackage) -> None:
    """Independent envelope, namespace, byte/index and material digest oracle."""
    artifact = checked_record(release.artifact_json)
    qualification = checked_record(release.qualification_json)
    data, qualified = mapping(artifact["payload"]), mapping(qualification["payload"])
    assert artifact["kind"] == "qualified-release"
    assert qualification["kind"] == "release-qualification"
    assert data["qualification_ref"] == reference(qualification)
    directory = release.root / "candidates" / str(artifact["id"])
    paths: set[str] = set()
    for source_value in sequence(data["sources"]):
        source = mapping(source_value)
        for item_value in sequence(source["files"]):
            item = mapping(item_value)
            name = str(item["path"])
            assert not Path(name).is_absolute() and ".." not in Path(name).parts
            token = str(source["prefix"]) + "/" + name if source["prefix"] else name
            assert token not in paths
            paths.add(token)
            path = directory / token
            assert path.is_file() and not path.is_symlink()
            raw = path.read_bytes()
            assert sha(raw) == item["sha256"] and len(raw) == item["size"]
            assert path.stat().st_mode & 0o277 == 0
    assert {
        p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()
    } == paths
    assert package_digest(directory / "packages/0") == data["package_digest"]
    material = {
        "packages": [{"package_key": data["package_key"], "digest": data["package_digest"]}],
        "profile_sha256": sha((directory / "profile.yaml").read_bytes()),
    }
    assert sha(canonical(material)) == qualified["material_digest"]
    raw_index = (directory / "resolved-index.json").read_bytes()
    assert canonical(json.loads(raw_index)) == raw_index
    assert sha(raw_index) == qualified["resolved_index_digest"]
    assert (
        sha(canonical(qualified["dependency_closure_refs"]))
        == qualified["dependency_closure_digest"]
    )
    assert qualified["static_status"] == "STATIC_PASS" and qualified["pure_status"] == "PURE_PASS"
    assert qualified["resolution"] == "NO_MODEL" and qualified["effective"] is None


def external(
    root: Path, package: Path, profile: Path, dependencies: tuple[ReleasePackage, ...] = ()
) -> ReleasePackage:
    """Exact existing external producer with independent checks added, no DB effect."""
    assert len(dependencies) < MAX_FIXTURE_RELEASES
    assert root.resolve().is_relative_to(Path(os.environ["TMPDIR"]).resolve())
    material, sources, expected_material = capture([str(package)], str(profile))
    compiled = skill_catalog.compile_catalog((package,), profile, dependencies=dependencies)
    output = skill_catalog.evaluate_pure(compiled, PURE_INPUT)
    assert len(output.outputs_json) == 3
    assert compiled.material_digest == expected_material
    index = resolved_index(compiled)
    material["resolved-index.json"] = canonical(index)
    sources.append(index_source(index))
    bindings = [
        {
            "package_key": sources[0]["package_key"],
            "entity_kind": identity[0],
            "key": identity[1],
            "ref": {
                "kind": identity[0],
                "id": str(uuid4()),
                "revision": 1,
                "digest": sources[0]["package_digest"],
            },
        }
        for identity in (sequence(i) for i in sequence(sources[0]["identities"]))
    ]
    qualification = envelope(
        "release-qualification",
        {
            "material_digest": compiled.material_digest,
            "resolved_index_digest": compiled.resolved_index_digest,
            "dependency_closure_refs": list(compiled.dependency_closure_refs),
            "dependency_closure_digest": sha(canonical(list(compiled.dependency_closure_refs))),
            "compiler_revision": candidate_catalog.COMPILER_REVISION,
            "evaluator_revision": candidate_catalog.EVALUATOR_REVISION,
            "static_status": "STATIC_PASS",
            "pure_status": "PURE_PASS",
            "resolution": "NO_MODEL",
            "effective": None,
            "outputs": [raw.decode() for raw in output.outputs_json],
            "pure_input": PURE_INPUT,
        },
    )
    requested: list[dict[str, object]] = []

    def selectors(value: object) -> None:
        if isinstance(value, dict):
            if value.get("kind") == "RELEASE":
                requested.append(mapping(value["ref"]))
            for child in value.values():
                selectors(child)
        elif isinstance(value, list):
            for child in value:
                selectors(child)

    for name, raw in material.items():
        if name.endswith(".yaml"):
            selectors(yaml.safe_load(raw))
    artifact = envelope(
        "qualified-release",
        {
            "authority": "EXTERNAL_PREQUALIFIED",
            "package_key": sources[0]["package_key"],
            "package_digest": sources[0]["package_digest"],
            "sources": sources,
            "bindings": bindings,
            "qualification_ref": reference(qualification),
            "dependency_artifact_refs": [
                reference(checked_record(d.artifact_json))
                for d in dependencies
                if any(
                    mapping(b)["ref"] in requested
                    for b in sequence(payload(d.artifact_json)["bindings"])
                )
            ],
        },
    )
    finalize(root, "candidates", str(artifact["id"]), material)
    release = ReleasePackage(root, canonical(artifact), canonical(qualification))
    check_release(release)
    # Recompile the saved external bytes through the actual integrated consumer.
    skill_catalog.compile_catalog(
        (root / "candidates" / str(artifact["id"]) / "packages/0",),
        root / "candidates" / str(artifact["id"]) / "profile.yaml",
        dependencies=dependencies,
    )
    return release


@contextmanager
def fixture_connection(database_url: URL) -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    """Re-attest the parent-owned UUID migrated database before any SQL, no CREATE."""
    assert not any(n.startswith(("PG", "DOCKER_", "COMPOSE_")) for n in os.environ)
    project = os.environ.get("OMNIS_TEST_PROJECT", "")
    socket = os.environ.get("OMNIS_TEST_SOCKET_DIR", "")
    manifest = Path(os.environ.get("OMNIS_TEST_FIXTURE", ""))
    assert re.fullmatch(r"omnis-p01-[a-z0-9-]+", project)
    assert Path(socket).is_absolute() and str(Path(socket).resolve()) == socket
    assert manifest.is_absolute() and manifest.is_file()
    assert database_url.drivername == "postgresql+psycopg"
    assert database_url.host == quote(socket, safe="") and "," not in socket
    assert database_url.username == "omnis_test" and database_url.password
    assert re.fullmatch(r"omnis_p01_[0-9a-f]{32}", database_url.database or "")
    assert database_url.port in (None, 5432) and not database_url.query
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(ROOT / "ops/run_test_db_gate.py"),
            "--attest",
            str(manifest),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, "shared private DB attestation refused"
    receipt = mapping(json.loads(result.stdout))
    assert set(receipt) == {
        "schema_version",
        "project",
        "socket_directory",
        "system_identifier",
        "container_id",
    }
    assert type(receipt["schema_version"]) is int and receipt["schema_version"] == 1
    assert receipt["project"] == project and receipt["socket_directory"] == socket
    assert type(receipt["system_identifier"]) is str
    assert re.fullmatch(r"[0-9]+", str(receipt["system_identifier"]))
    assert type(receipt["container_id"]) is str and re.fullmatch(
        r"[0-9a-f]{64}", str(receipt["container_id"])
    )
    try:
        with psycopg.connect(
            host=socket,
            port=5432,
            user=database_url.username,
            password=database_url.password,
            dbname=database_url.database,
            connect_timeout=3,
            options="-c statement_timeout=3000 -c lock_timeout=3000",
        ) as connection:
            identity = connection.execute(
                "SELECT system_identifier FROM pg_control_system()"
            ).fetchone()
            assert identity is not None and str(identity[0]) == receipt["system_identifier"]
            assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [
                ("0011_managed_tasks",)
            ]
            yield connection
    except psycopg.Error:
        raise AssertionError("attested fixture SQL refused") from None


def install_fixture(
    database_url: URL,
    owner: str,
    releases: tuple[ReleasePackage, ...],
    *,
    identity_package: str | None = None,
) -> None:
    """Insert exact fixture records; invalid test records are NOT qualification claims.

    Producers qualify positives before this call. Negative tests may supply a
    rehashed malformed envelope or deliberately misbind an identity package.
    No trigger disable, UPDATE, DELETE, migration, reservation rename or Publish.
    """
    assert str(UUID(owner)) == owner and 1 <= len(releases) <= MAX_FIXTURE_RELEASES
    with fixture_connection(database_url) as connection:
        for release in releases:
            artifact = checked_record(release.artifact_json)
            qualification = checked_record(release.qualification_json)
            for record in (qualification, artifact):
                connection.execute(
                    "INSERT INTO catalog_record (id,owner_id,group_id,kind,revision,digest,envelope) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (
                        record["id"],
                        owner,
                        artifact["id"],
                        record["kind"],
                        record["revision"],
                        record["digest"],
                        Jsonb(record),
                    ),
                )
            bindings = sequence(mapping(artifact["payload"])["bindings"])
            assert 1 <= len(bindings) <= 128
            for value in bindings:
                item = mapping(value)
                ref = mapping(item["ref"])
                connection.execute(
                    "INSERT INTO catalog_identity (id,owner_id,package_key,entity_kind,entity_key) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (
                        ref["id"],
                        owner,
                        identity_package if identity_package is not None else item["package_key"],
                        item["entity_kind"],
                        item["key"],
                    ),
                )
                connection.execute(
                    "INSERT INTO catalog_reservation (id,revision,digest,draft_id) VALUES (%s,%s,%s,%s)",
                    (ref["id"], ref["revision"], ref["digest"], artifact["id"]),
                )
            stored = connection.execute(
                "SELECT envelope FROM catalog_record WHERE id=%s", (artifact["id"],)
            ).fetchone()
            assert stored is not None and stored[0] == artifact
        # Check the exact immutable inserts, rather than crediting execute() alone.
        connection.commit()
    with fixture_connection(database_url) as connection:
        for release in releases:
            artifact = checked_record(release.artifact_json)
            for record in (artifact, checked_record(release.qualification_json)):
                row = connection.execute(
                    "SELECT owner_id,envelope FROM catalog_record WHERE id=%s", (record["id"],)
                ).fetchone()
                assert row is not None and str(row[0]) == owner and row[1] == record
            bindings = sequence(mapping(artifact["payload"])["bindings"])
            assert connection.execute(
                "SELECT count(*) FROM catalog_reservation WHERE draft_id=%s", (artifact["id"],)
            ).fetchone() == (len(bindings),)
            for value in bindings:
                item = mapping(value)
                ref = mapping(item["ref"])
                row = connection.execute(
                    "SELECT i.owner_id,i.package_key,i.entity_kind,i.entity_key,"
                    "r.revision,r.digest,r.draft_id FROM catalog_identity i "
                    "JOIN catalog_reservation r ON r.id=i.id WHERE r.id=%s AND r.revision=%s",
                    (ref["id"], ref["revision"]),
                ).fetchone()
                assert row is not None
                assert (str(row[0]), *row[1:6], str(row[6])) == (
                    owner,
                    identity_package if identity_package is not None else item["package_key"],
                    item["entity_kind"],
                    item["key"],
                    ref["revision"],
                    ref["digest"],
                    artifact["id"],
                )


@dataclass(frozen=True)
class Harness:
    directory: Path
    catalog_root: Path
    owner: str
    cli_python: Path | None = None
    expected_module: Path | None = None

    def request(self, **fields: object) -> dict[str, object]:
        return {"schema_version": 1, "owner_id": self.owner, "command_id": str(uuid4()), **fields}

    def read_request(self, snapshot_ref: object) -> dict[str, object]:
        return {"schema_version": 1, "owner_id": self.owner, "snapshot_ref": snapshot_ref}

    def invoke(
        self, operation: str, request: dict[str, object], url: URL
    ) -> subprocess.CompletedProcess[str]:
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self.directory / f"request-{uuid4().hex}.json"
        path.write_bytes(canonical(request))
        path.chmod(0o600)
        if self.cli_python is None:
            expected = ROOT / "api/src/omnis/modules/settings/candidate_catalog.py"
            assert Path(candidate_catalog.__file__).resolve() == expected
            prefix = f"import sys; sys.path.insert(0, {str(ROOT / 'api/src')!r}); "
        else:
            assert self.cli_python.is_absolute() and self.expected_module is not None
            expected = self.expected_module.resolve()
            assert not expected.is_relative_to(ROOT / "api/src"), "installed QA resolved source"
            prefix = ""
        code = (
            prefix
            + "from pathlib import Path; from omnis.modules.settings import candidate_catalog as c; "
            + f"assert Path(c.__file__).resolve() == Path({str(expected)!r}); raise SystemExit(c.main())"
        )
        return subprocess.run(
            [
                str(self.cli_python or Path(sys.executable)),
                "-I",
                "-B",
                "-c",
                code,
                operation,
                "--request",
                str(path),
                "--catalog-root",
                str(self.catalog_root),
            ],
            cwd=self.directory,
            env={
                "PATH": "/usr/bin:/bin",
                "HOME": str(self.directory),
                "TMPDIR": str(self.directory),
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "OMNIS_DATABASE_URL": url.render_as_string(hide_password=False),
            },
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

    def success(self, operation: str, request: dict[str, object], url: URL) -> dict[str, object]:
        result = self.invoke(operation, request, url)
        assert result.returncode == 0, f"positive {operation} exit={result.returncode}"
        assert result.stderr == "", "positive emitted contradictory stderr"
        return mapping(json.loads(result.stdout))

    def denied(self, operation: str, request: dict[str, object], url: URL, reason: str) -> None:
        result = self.invoke(operation, request, url)
        assert result.returncode == 2 and result.stdout == "", "not a bounded catalog denial"
        assert len(result.stderr.encode()) <= 4096
        assert mapping(json.loads(result.stderr)) == {"status": "BLOCKED", "reason": reason}
        assert (
            "Traceback" not in result.stderr
            and url.render_as_string(hide_password=False) not in result.stderr
        )
