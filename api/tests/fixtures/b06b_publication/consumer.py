"""Independent C01 consumer: own sources, real processes and digest oracles.

No historical fixture/helper/receipt imports; provisioning remains in conftest.
OMNIS_B06B_PYTHON + OMNIS_B06B_INSTALLED=1 selects a separately installed wheel.
"""

import hashlib
import json
import os
import pty
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(__file__).resolve().parent / "source"
PUBLICATION = "omnis.modules.settings.catalog_publication"
CANDIDATE = "omnis.modules.settings.candidate_catalog"
PACKAGE = "b06b-publish-contract"
SOURCE_FILES = (
    "SKILL.md",
    "omnis.yaml",
    "NOTICE.md",
    "references/method.md",
    "templates/procedures/publication-map.yaml",
    "templates/capture.schema.json",
    "templates/records.schema.json",
    "templates/operations.schema.json",
    "templates/surface_map.schema.json",
    "templates/empty.schema.json",
)


def mapping(value: object) -> dict[str, object]:
    assert isinstance(value, dict) and all(type(key) is str for key in value)
    return cast(dict[str, object], value)


def sequence(value: object) -> list[object]:
    assert isinstance(value, list)
    return cast(list[object], value)


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw: str) -> dict[str, object]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        assert len({key for key, _ in items}) == len(items), "duplicate response member"
        return dict(items)

    return mapping(json.loads(raw, object_pairs_hook=pairs))


def exact_ref(value: object) -> dict[str, object]:
    ref = mapping(value)
    assert set(ref) == {"kind", "id", "revision", "digest"}
    assert type(ref["id"]) is str and str(UUID(ref["id"])) == ref["id"]
    assert type(ref["revision"]) is int and ref["revision"] >= 1
    assert type(ref["kind"]) is str and ref["kind"]
    assert type(ref["digest"]) is str and re.fullmatch(r"[0-9a-f]{64}", ref["digest"])
    return ref


def envelope(value: object, reference: object) -> dict[str, object]:
    record = mapping(value)
    ref = exact_ref(reference)
    assert set(record) == {"schema_version", "kind", "id", "revision", "payload", "digest"}
    assert type(record["schema_version"]) is int and record["schema_version"] == 1
    assert {key: record[key] for key in ref} == ref
    assert (
        sha(canonical({key: val for key, val in record.items() if key != "digest"}))
        == ref["digest"]
    )
    return mapping(record["payload"])


def package_digest(package: Path) -> str:
    manifest = strict_json((package / "omnis.yaml").read_text())
    names = [
        "SKILL.md",
        "omnis.yaml",
        *sequence(manifest["procedures"]),
        *sequence(manifest["support_files"]),
    ]
    assert all(type(name) is str for name in names)
    assert len(names) == len(set(names))
    entries = []
    for name in sorted(cast(list[str], names), key=lambda item: item.encode("utf-8")):
        raw = (package / name).read_bytes()
        entries.append({"path": name, "sha256": sha(raw), "size": len(raw)})
    return sha(canonical(entries))


def material_digest(package: Path, profile: Path) -> str:
    return sha(
        canonical(
            {
                "packages": [{"package_key": PACKAGE, "digest": package_digest(package)}],
                "profile_sha256": sha(profile.read_bytes()),
            }
        )
    )


def cli_command(module: str, *args: str) -> list[str]:
    python = os.environ.get("OMNIS_B06B_PYTHON", sys.executable)
    if os.environ.get("OMNIS_B06B_INSTALLED") == "1":
        return [python, "-I", "-B", "-m", module, *args]
    source = Path(os.environ.get("OMNIS_B06B_SOURCE_ROOT", str(ROOT / "api/src")))
    return [
        python,
        "-I",
        "-B",
        "-c",
        "import runpy,sys;sys.path.insert(0,sys.argv.pop(1));runpy.run_module(sys.argv.pop(1),run_name='__main__')",
        str(source),
        module,
        *args,
    ]


def require_consumer() -> None:
    result = subprocess.run(
        cli_command(PUBLICATION, "--help"), capture_output=True, text=True, timeout=15, check=False
    )
    assert result.returncode == 0, "C01 publication CLI absent before DB acquisition"
    assert all(
        name in result.stdout for name in ("head", "confirm", "publish", "readback", "snapshot")
    )


@dataclass(frozen=True)
class Seed:
    directory: Path
    package: Path
    profile: Path
    root: Path
    owner: str

    def request(self, **fields: object) -> dict[str, object]:
        return {"schema_version": 1, "owner_id": self.owner, **fields}

    def write(self, **fields: object) -> dict[str, object]:
        return self.request(command_id=str(uuid4()), **fields)

    def capture(self, author: str = "OPERATOR") -> dict[str, object]:
        return self.write(
            author_kind=author, packages=[str(self.package)], profile=str(self.profile)
        )

    def command(
        self,
        operation: str,
        request: dict[str, object],
        candidate: bool = False,
        raw: bytes | None = None,
    ) -> list[str]:
        path = self.directory / f"request-{uuid4().hex}.json"
        path.write_bytes(canonical(request) if raw is None else raw)
        path.chmod(0o600)
        return cli_command(
            CANDIDATE if candidate else PUBLICATION,
            operation,
            "--request",
            str(path),
            "--catalog-root",
            str(self.root),
        )

    def environment(self, database_url: str) -> dict[str, str]:
        return {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.directory),
            "TMPDIR": str(self.directory),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "OMNIS_DATABASE_URL": database_url,
        }

    def invoke(
        self,
        operation: str,
        request: dict[str, object],
        database_url: str,
        *,
        candidate: bool = False,
        raw: bytes | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            self.command(operation, request, candidate, raw),
            cwd=self.directory,
            env=self.environment(database_url),
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )

    def success(
        self,
        operation: str,
        request: dict[str, object],
        database_url: str,
        *,
        candidate: bool = False,
    ) -> dict[str, object]:
        result = self.invoke(operation, request, database_url, candidate=candidate)
        assert result.returncode == 0, f"positive {operation}: exit={result.returncode}"
        assert result.stderr == "", "positive emitted contradictory diagnostic"
        return strict_json(result.stdout)

    def denied(
        self,
        operation: str,
        request: dict[str, object],
        database_url: str,
        reason: str | None = None,
        *,
        raw: bytes | None = None,
    ) -> str:
        result = self.invoke(operation, request, database_url, raw=raw)
        assert result.returncode == 2, f"not a bounded {operation} refusal"
        assert result.stdout == "" and 0 < len(result.stderr.encode()) <= 4096
        diagnostic = strict_json(result.stderr)
        assert set(diagnostic) == {"status", "reason"} and diagnostic["status"] == "BLOCKED"
        actual = diagnostic["reason"]
        assert type(actual) is str and re.fullmatch(r"[A-Z][A-Z0-9_]+", actual)
        assert actual not in ("DATABASE_UNAVAILABLE", "INPUT_UNAVAILABLE", "INVALID_ARGUMENTS"), (
            "unrelated infrastructure failure is not a denial proof"
        )
        assert database_url not in result.stderr and str(self.directory) not in result.stderr
        assert "Traceback" not in result.stderr and "ImportError" not in result.stderr
        if reason is not None:
            assert actual == reason
        return actual

    def confirm(
        self, request: dict[str, object], database_url: str, answer: str = "yes"
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        """stdin/stderr are a real PTY; stdout remains a separate JSON pipe."""
        master, slave = pty.openpty()
        assert os.isatty(slave)
        process = subprocess.Popen(
            self.command("confirm", request),
            cwd=self.directory,
            env=self.environment(database_url),
            stdin=slave,
            stderr=slave,
            stdout=subprocess.PIPE,
            text=True,
        )
        os.close(slave)
        transcript = bytearray()
        sent = False
        deadline = time.monotonic() + 25
        try:
            while process.poll() is None:
                assert time.monotonic() < deadline, "trusted TTY confirmation timed out"
                if select.select([master], [], [], 0.05)[0]:
                    try:
                        chunk = os.read(master, 8192)
                    except OSError:
                        break
                    transcript.extend(chunk)
                    assert len(transcript) <= 65536, "unbounded TTY review output"
                    # Do not pre-approve before the operator has received exact selection.
                    if not sent and b"yes" in transcript.lower():
                        for name in (
                            "material_digest",
                            "resolved_index_digest",
                            "dependency_closure_digest",
                        ):
                            assert str(request[name]).encode() in transcript
                        for field in (
                            "draft_ref",
                            "snapshot_ref",
                            "technical_review_ref",
                            "static_evaluation_ref",
                            "pure_evaluation_ref",
                        ):
                            ref = exact_ref(request[field])
                            assert str(ref["id"]).encode() in transcript
                            assert str(ref["digest"]).encode() in transcript
                        for selected in sequence(request["source_draft_refs"]):
                            ref = exact_ref(selected)
                            assert str(ref["id"]).encode() in transcript
                            assert str(ref["digest"]).encode() in transcript
                        assert b"STATIC_PASS" in transcript and b"PURE_PASS" in transcript
                        os.write(master, (answer + "\n").encode())
                        sent = True
            stdout, _ = process.communicate(timeout=max(0.1, deadline - time.monotonic()))
            assert sent or process.returncode == 2
            return subprocess.CompletedProcess(
                process.args, process.returncode, stdout, ""
            ), transcript.decode("utf-8")
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
            os.close(master)


def new_seed() -> Seed:
    directory = Path(tempfile.mkdtemp(prefix="b06b-", dir=os.environ["TMPDIR"]))
    directory.chmod(0o700)
    package = directory / PACKAGE
    for name in SOURCE_FILES:
        source = SOURCE / PACKAGE / name
        assert source.is_file() and not source.is_symlink()
        target = package / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    profile = directory / "profile.yaml"
    shutil.copyfile(SOURCE / "profile.yaml", profile)
    shutil.copyfile(SOURCE / "input.json", directory / "input.json")
    assert {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()} == set(
        SOURCE_FILES
    )
    return Seed(directory, package, profile, directory / "catalog", str(uuid4()))


@dataclass(frozen=True)
class Qualified:
    seed: Seed
    capture: dict[str, object]
    capture_command: dict[str, object]
    review: dict[str, object]
    frozen: dict[str, object]
    static: dict[str, object]
    pure: dict[str, object]
    selection: dict[str, object]


def qualify(seed: Seed, database_url: str, author: str = "OPERATOR") -> Qualified:
    capture_command = seed.capture(author)
    captured = seed.success("capture", capture_command, database_url, candidate=True)
    assert captured["material_digest"] == material_digest(seed.package, seed.profile)
    selected = {
        "draft_ref": captured["draft_ref"],
        "source_draft_refs": captured["source_draft_refs"],
    }
    review = seed.success("review", seed.write(**selected), database_url, candidate=True)
    frozen = seed.success(
        "freeze",
        seed.write(**selected, technical_review_ref=review["technical_review_ref"]),
        database_url,
        candidate=True,
    )
    body = envelope(frozen["snapshot"], frozen["snapshot_ref"])
    back = seed.success(
        "readback", seed.request(snapshot_ref=frozen["snapshot_ref"]), database_url, candidate=True
    )
    assert sha(canonical(back["resolved_index"])) == body["resolved_index_digest"]
    evaluations = []
    for kind in ("STATIC", "PURE"):
        result = seed.success(
            "evaluate",
            seed.write(
                snapshot_ref=frozen["snapshot_ref"],
                evaluation_kind=kind,
                input=None
                if kind == "STATIC"
                else strict_json((seed.directory / "input.json").read_text()),
            ),
            database_url,
            candidate=True,
        )
        assert result["status"] == kind + "_PASS"
        receipt = envelope(result["evaluation"], result["evaluation_ref"])
        assert receipt["snapshot_ref"] == frozen["snapshot_ref"]
        assert receipt["material_digest"] == body["material_digest"]
        assert receipt["resolved_index_digest"] == body["resolved_index_digest"]
        assert receipt["dependency_closure_digest"] == sha(
            canonical(body["dependency_closure_refs"])
        )
        assert receipt["resolution"] == "NO_MODEL" and receipt["effective"] is None
        evaluations.append(result)
    head = seed.success("head", seed.request(draft_ref=captured["draft_ref"]), database_url)
    assert type(head["generation"]) is int and head["generation"] >= 1
    assert head["draft_ref"] == captured["draft_ref"] and head["publication_ref"] is None
    selection = {
        **selected,
        "expected_head_generation": head["generation"],
        "snapshot_ref": frozen["snapshot_ref"],
        "technical_review_ref": review["technical_review_ref"],
        "static_evaluation_ref": evaluations[0]["evaluation_ref"],
        "pure_evaluation_ref": evaluations[1]["evaluation_ref"],
        "material_digest": body["material_digest"],
        "resolved_index_digest": body["resolved_index_digest"],
        "dependency_closure_digest": sha(canonical(body["dependency_closure_refs"])),
    }
    return Qualified(
        seed, captured, capture_command, review, frozen, evaluations[0], evaluations[1], selection
    )


def confirmed(qualified: Qualified, database_url: str) -> dict[str, object]:
    result, transcript = qualified.seed.confirm(
        qualified.seed.write(**qualified.selection), database_url
    )
    assert result.returncode == 0, f"trusted confirmation failed: exit={result.returncode}"
    assert "local-operator" in transcript or "operator" in transcript.lower()
    confirmation = strict_json(result.stdout)
    body = envelope(confirmation["confirmation"], confirmation["confirmation_ref"])
    assert set(body) == {"selection", "actor", "author_kind", "created_by"}
    assert body["author_kind"] == "OPERATOR"
    assert body["actor"] == f"local-operator:{os.getuid()}"
    assert body["created_by"] == qualified.seed.owner
    assert mapping(body["selection"]) == qualified.selection
    return confirmation


def publish_request(qualified: Qualified, confirmation: dict[str, object]) -> dict[str, object]:
    return qualified.seed.write(
        **qualified.selection, confirmation_ref=confirmation["confirmation_ref"]
    )
