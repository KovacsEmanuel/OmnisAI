"""Independent durable-catalog consumer and normative digest oracles.

Only listed first-party source bytes are copied. No repository doubles, product
hash helpers, DB provisioning, release publication, or inferred denial reasons.
"""

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from fixtures.b06a.consumer import mapping, sequence, strict_json

ROOT = Path(__file__).resolve().parents[4]
MODULE = "omnis.modules.settings.candidate_catalog"
PACKAGE_KEY = "recon-mapping-contract"
SOURCE_PATHS = (
    "SKILL.md",
    "omnis.yaml",
    "NOTICE.md",
    "references/methodology.md",
    "templates/procedures/map-capture.yaml",
    "templates/schemas/capture.schema.json",
    "templates/schemas/records.schema.json",
    "templates/schemas/operations.schema.json",
    "templates/schemas/surface_map.schema.json",
    "templates/schemas/empty.schema.json",
)


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def scratch_directory() -> Path:
    """Retain readonly/tampered material; no shared fixture teardown/adoption."""
    return Path(tempfile.mkdtemp(prefix="b06a-devb-", dir=os.environ["TMPDIR"]))


def require_consumer() -> None:
    # An absent feature is a positive assertion failure, never a denial PASS.
    assert importlib.util.find_spec(MODULE) is not None, (
        "durable capture -> review -> freeze -> readback consumer is absent"
    )


def exact_ref(value: object) -> dict[str, object]:
    ref = mapping(value)
    assert set(ref) == {"kind", "id", "revision", "digest"}
    assert type(ref["kind"]) is str and ref["kind"]
    identifier = ref["id"]
    assert type(identifier) is str and str(UUID(identifier)) == identifier
    assert type(ref["revision"]) is int and ref["revision"] >= 1
    digest = ref["digest"]
    assert type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest)
    return ref


def envelope(value: object, expected_ref: object) -> dict[str, object]:
    record = mapping(value)
    assert set(record) == {"schema_version", "kind", "id", "revision", "payload", "digest"}
    assert type(record["schema_version"]) is int and record["schema_version"] == 1
    ref = exact_ref(expected_ref)
    assert {key: record[key] for key in ref} == ref
    mapping(record["payload"])
    assert (
        sha(canonical({key: val for key, val in record.items() if key != "digest"}))
        == (record["digest"])
    ), "RecordEnvelope must hash its independent non-self-referential preimage"
    return mapping(record["payload"])


def package_digest(package: Path) -> str:
    import yaml

    manifest = mapping(yaml.safe_load((package / "omnis.yaml").read_bytes()))
    declared = ["SKILL.md", "omnis.yaml", *sequence(manifest["procedures"])]
    declared += sequence(manifest["support_files"])
    assert all(type(name) is str for name in declared)
    names = [str(name) for name in declared]
    assert len(names) == len(set(names))
    entries = []
    for name in sorted(names, key=lambda item: item.encode("utf-8")):
        data = (package / name).read_bytes()
        entries.append({"path": name, "sha256": sha(data), "size": len(data)})
    return sha(canonical(entries))


def material_digest(packages: tuple[Path, ...], profile: Path) -> str:
    import yaml

    entries = [
        {
            "package_key": mapping(yaml.safe_load((p / "omnis.yaml").read_bytes()))["package_key"],
            "digest": package_digest(p),
        }
        for p in packages
    ]
    entries.sort(key=lambda item: str(item["package_key"]))
    return sha(canonical({"packages": entries, "profile_sha256": sha(profile.read_bytes())}))


@dataclass(frozen=True)
class DurableSeed:
    directory: Path
    package: Path
    profile: Path
    catalog_root: Path
    owner_id: str

    def request(self, **fields: object) -> dict[str, object]:
        return {"schema_version": 1, "owner_id": self.owner_id, **fields}

    def write_request(self, **fields: object) -> dict[str, object]:
        return self.request(command_id=str(uuid4()), **fields)

    def capture_request(self) -> dict[str, object]:
        return self.write_request(
            author_kind="OPERATOR", packages=[str(self.package)], profile=str(self.profile)
        )

    def invoke(
        self, operation: str, request: dict[str, object], database_url: str
    ) -> subprocess.CompletedProcess[str]:
        path = self.directory / f"request-{uuid4().hex}.json"
        path.write_bytes(canonical(request))
        return subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-m",
                MODULE,
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
                "OMNIS_DATABASE_URL": database_url,
            },
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

    def success(
        self, operation: str, request: dict[str, object], database_url: str
    ) -> dict[str, object]:
        result = self.invoke(operation, request, database_url)
        # Do not print a raw diagnostic that might disclose DSN/input bytes.
        assert result.returncode == 0, f"positive {operation} failed: exit={result.returncode}"
        assert result.stderr == "", "success emitted contradictory stderr"
        return strict_json(result.stdout)

    def denied(
        self, operation: str, request: dict[str, object], database_url: str, reason: str
    ) -> None:
        result = self.invoke(operation, request, database_url)
        assert result.returncode == 2, "not a bounded catalog denial"
        assert result.stdout == "", "denial emitted success data"
        assert len(result.stderr.encode()) <= 4096
        assert strict_json(result.stderr) == {"status": "BLOCKED", "reason": reason}
        assert database_url not in result.stderr and str(self.directory) not in result.stderr
        assert "Traceback" not in result.stderr and "ImportError" not in result.stderr


def copy_seed(directory: Path) -> DurableSeed:
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    package = directory / PACKAGE_KEY
    for relative in SOURCE_PATHS:
        source = ROOT / "skills" / PACKAGE_KEY / relative
        assert source.is_file() and not source.is_symlink()
        destination = package / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    profile = directory / "profile.yaml"
    shutil.copyfile(ROOT / "profiles" / f"{PACKAGE_KEY}.yaml", profile)
    shutil.copyfile(ROOT / "api/tests/fixtures/b06a/golden.json", directory / "golden.json")
    assert set(p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()) == (
        set(SOURCE_PATHS)
    )
    assert Path(os.environ["TMPDIR"]).resolve() in directory.resolve().parents
    return DurableSeed(directory, package, profile, directory / "catalog", str(uuid4()))


def reviewed(seed: DurableSeed, database_url: str) -> tuple[dict[str, object], dict[str, object]]:
    expected = material_digest((seed.package,), seed.profile)
    capture = seed.success("capture", seed.capture_request(), database_url)
    primary = exact_ref(capture["draft_ref"])
    sources = [exact_ref(ref) for ref in sequence(capture["source_draft_refs"])]
    assert len(sources) == 2 and primary in sources
    assert len({canonical(ref) for ref in sources}) == 2
    assert capture["material_digest"] == expected
    review = seed.success(
        "review", seed.write_request(draft_ref=primary, source_draft_refs=sources), database_url
    )
    exact_ref(review["technical_review_ref"])
    assert review["source_draft_refs"] == sources
    assert review["material_digest"] == expected
    refs = [exact_ref(ref) for ref in sequence(review["candidate_refs"])]
    package_refs = [ref for ref in refs if ref["kind"] != "profile"]
    assert package_refs and all(
        ref["digest"] == package_digest(seed.package) for ref in package_refs
    )
    profile_refs = [ref for ref in refs if ref["kind"] == "profile"]
    assert len(profile_refs) == 1 and profile_refs[0]["digest"] == primary["digest"]
    assert sequence(review["reservations"])
    return capture, review


def freeze_request(
    seed: DurableSeed, capture: dict[str, object], review: dict[str, object]
) -> dict[str, object]:
    return seed.write_request(
        draft_ref=capture["draft_ref"],
        source_draft_refs=capture["source_draft_refs"],
        technical_review_ref=review["technical_review_ref"],
    )


def freeze(seed: DurableSeed, database_url: str) -> dict[str, object]:
    capture, review = reviewed(seed, database_url)
    result = seed.success("freeze", freeze_request(seed, capture, review), database_url)
    payload = envelope(result["snapshot"], result["snapshot_ref"])
    assert payload["draft_ref"] == capture["draft_ref"]
    assert payload["source_draft_refs"] == capture["source_draft_refs"]
    assert payload["technical_review_ref"] == review["technical_review_ref"]
    assert payload["material_digest"] == capture["material_digest"]
    assert payload["candidate_refs"] == review["candidate_refs"]
    for name in (
        "resolved_index_digest",
        "dependency_closure_refs",
        "profile_ref",
        "compiler_revision",
        "created_by",
    ):
        assert name in payload
    return result


def readback(seed: DurableSeed, database_url: str, frozen: dict[str, object]) -> dict[str, object]:
    result = seed.success(
        "readback", seed.request(snapshot_ref=frozen["snapshot_ref"]), database_url
    )
    assert result["snapshot_ref"] == frozen["snapshot_ref"]
    assert result["snapshot"] == frozen["snapshot"]
    payload = envelope(result["snapshot"], result["snapshot_ref"])
    assert sha(canonical(result["resolved_index"])) == payload["resolved_index_digest"]
    assert result["publication"] == "UNPUBLISHED" and result["assessment_selectable"] is False
    assert "technical_review" in result and type(result["evaluations"]) is list
    return result
