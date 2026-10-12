"""Lossless durable method representation across producer/native consumer."""

import asyncio
import importlib
import json
import os
import sys
import tempfile
import time
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest

from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks import managed_composition
from omnis.modules.tasks.managed_contract import text
from test_contract_method_checks import obj as mapping
from test_contract_method_checks import rows as sequence
from test_contract_method_producer import method_graph


def missing_composer_pin(stage: dict[str, object]) -> dict[str, object]:
    """Reseal exact wrappers/refs so only the bundle payload field is invalid."""
    bad = deepcopy(stage)
    bundle = mapping(sequence(bad["record_pool"])[0])
    del mapping(bundle["payload"])["composer_revision"]
    bundle["digest"] = sha256(
        canonical({k: v for k, v in bundle.items() if k != "digest"})
    ).hexdigest()
    composition = mapping(sequence(bad["compositions"])[0])
    mapping(composition["payload"])["prompt_bundle_ref"] = records.reference(bundle)
    composition["digest"] = sha256(
        canonical({k: v for k, v in composition.items() if k != "digest"})
    ).hexdigest()
    manifest = mapping(bad["manifest"])
    entry = mapping(sequence(mapping(manifest["payload"])["entries"])[0])
    entry["composition_ref"] = records.reference(composition)
    manifest["digest"] = sha256(
        canonical({k: v for k, v in manifest.items() if k != "digest"})
    ).hexdigest()
    return bad


def test_missing_compact_composer_pin_refuses_exact_payload_before_indexing() -> None:
    method = importlib.import_module("omnis_hermes.contract_method")
    native = importlib.import_module("omnis_hermes.managed_admission_contract")

    graph = method_graph()
    stage = managed_composition.stage_payload(graph[-1], graph)
    assert native.validate_stage(stage) == graph[-1]
    bad = missing_composer_pin(stage)
    for record, kind in (
        (sequence(bad["record_pool"])[0], "prompt-bundle"),
        (sequence(bad["compositions"])[0], "prompt-composition"),
        (bad["manifest"], "launch-manifest"),
    ):
        assert native.envelope(record, kind) == record
    with pytest.raises(ValueError, match="Invalid native preparation"):
        native.validate_stage(bad)
    with pytest.raises(ValueError, match="Invalid native preparation"):
        method.assignment(canonical(bad))


@pytest.mark.asyncio
async def test_missing_compact_pin_denies_on_private_uds_and_keeps_status_channel() -> None:
    """Real existing Host IPC; no native launch or substituted transport/stop."""
    runtime = importlib.import_module("omnis_hermes.runtime_host")
    protocol = importlib.import_module("omnis_hermes.runtime_protocol")

    graph = method_graph()
    stage = managed_composition.stage_payload(graph[-1], graph)
    with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="cf-") as name:
        root = Path(name)
        socket_path = root / "runtime.sock"
        assert len(os.fsencode(socket_path)) < 108
        host = runtime.RuntimeHost(root)
        async with asyncio.timeout(3), host:
            status: dict[str, object] = {
                "version": 1,
                "id": str(uuid4()),
                "boot": host.boot,
                "capability": host.capability,
                "generation": 0,
                "epoch": 1,
                "op": "status",
            }
            valid_stage = {
                **status,
                "id": str(uuid4()),
                "op": "task_stage",
                "deadline_ns": time.monotonic_ns() + 4_000_000_000,
                "payload": stage,
            }
            # Do not put private capability-bearing frames into assertion operands.
            host._validate(valid_stage)
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            try:
                for request, expected in (
                    (status, True),
                    ({**valid_stage, "payload": missing_composer_pin(stage)}, False),
                    ({**status, "id": str(uuid4())}, True),
                ):
                    writer.write(protocol.encode(request))
                    await asyncio.wait_for(writer.drain(), 0.5)
                    reply = mapping(json.loads(await asyncio.wait_for(reader.readline(), 0.5)))
                    assert reply["id"] == request["id"] and reply["ok"] is expected
                    if not expected:
                        assert reply["error"] == "RUNTIME_DENIED"
                    assert host.process is None and host.peer is None
            finally:
                writer.close()
                await asyncio.wait_for(writer.wait_closed(), 0.5)
        assert not host.clients and host.lock_fd is None
        assert host.process is None and host.peer is None
        assert not socket_path.exists() and not (root / "runtime.boot").exists()


def test_compact_method_retains_exact_records_and_native_context() -> None:
    graph = method_graph()
    composition = next(r for r in graph if r["kind"] == "prompt-composition")
    body = mapping(composition["payload"])
    assert body.get("format") == "record-refs-v1"
    assert "text" not in body and "prompt_bundle" not in body
    stage = managed_composition.stage_payload(graph[-1], graph)
    pool = sequence(stage["record_pool"])
    assert len(pool) == 7 and all(r in graph for r in pool)
    entry = mapping(sequence(mapping(graph[-1]["payload"])["entries"])[0])
    path = str(Path(__file__).resolve().parents[2] / "integrations/hermes/src")
    sys.path.insert(0, path)
    try:
        native = importlib.import_module("omnis_hermes.managed_admission_contract")
        composer = importlib.import_module("omnis_hermes.prompt_bundle")
        assert native.validate_stage(stage) == graph[-1]
        raw = composer.validate_composition(composition, graph[-1], entry, record_pool=pool)
        sections = sequence(json.loads(raw))
        for index, kind in enumerate(
            ("prompt-content", "prompt-content", "task-brief", "bound-procedure")
        ):
            item = mapping(mapping(sections[index])["record"])
            assert item in graph and item["kind"] == kind
        assert mapping(sections[4])["context"] in graph
        assert mapping(sections[4])["input"] in graph
        assert body["byte_count"] == body["token_upper_bound"] == len(raw)
        expanded = managed_composition.expanded_payload(body, pool)
        assert expanded == composer.expanded_payload(body, pool)
        assert text(expanded["text"], 32768).encode() == raw
        brief = mapping(mapping(sections[2])["record"])
        assert records.reference(brief) == entry["brief_ref"]
        assert len(canonical(stage)) <= 32768 and len(raw) <= 32768
        for attack in (
            "missing",
            "duplicate",
            "foreign",
            "altered",
            "resealed",
            "bool-ref",
            "missing-ref",
            "foreign-header",
            "unknown-format",
            "extra",
            "context-overflow",
            "wire-overflow",
        ):
            bad = deepcopy(stage)
            bad_pool = sequence(bad["record_pool"])
            compact = mapping(sequence(bad["compositions"])[0])
            compact_body = mapping(compact["payload"])
            compact_parts = sequence(compact_body["sections"])
            manifest = mapping(bad["manifest"])
            bad_entry = mapping(sequence(mapping(manifest["payload"])["entries"])[0])
            if attack == "missing":
                bad_pool.pop()
            elif attack == "duplicate":
                bad_pool.append(deepcopy(bad_pool[-1]))
            elif attack == "foreign":
                bad_pool[-1] = deepcopy(method_graph()[-2])
            elif attack in ("altered", "resealed"):
                item = mapping(bad_pool[-1])
                mapping(item["payload"])["value"] = {"capture": "changed"}
                if attack == "resealed":
                    item.update(records.envelope("contract-case-input", mapping(item["payload"])))
            elif attack == "bool-ref":
                mapping(mapping(compact_parts[0])["record_ref"])["revision"] = True
            elif attack == "missing-ref":
                del mapping(compact_parts[0])["record_ref"]
            elif attack == "foreign-header":
                bad_entry["attempt_id"] = str(uuid4())
            elif attack == "unknown-format":
                compact_body["format"] = "record-refs-v2"
            elif attack == "extra":
                bad_pool.reverse()
            elif attack == "context-overflow":
                compact_body["byte_count"] = 32769
            else:
                content = mapping(sequence(mapping(compact_parts[-1])["content"])[0])
                content["text"] = "x" * 32768
            compact.update(records.envelope("prompt-composition", compact_body))
            bad_entry["composition_ref"] = records.reference(compact)
            manifest.update(records.envelope("launch-manifest", mapping(manifest["payload"])))
            try:
                native.validate_stage(bad)
            except ValueError:
                pass
            else:
                pytest.fail("accepted compact mutation: " + attack)
        inline = records.envelope("prompt-composition", expanded)
        legacy = deepcopy(stage)
        legacy["compositions"] = [inline]
        legacy_manifest = mapping(legacy["manifest"])
        legacy_entry = mapping(sequence(mapping(legacy_manifest["payload"])["entries"])[0])
        legacy_entry["composition_ref"] = records.reference(inline)
        legacy_manifest.update(
            records.envelope("launch-manifest", mapping(legacy_manifest["payload"]))
        )
        del legacy["record_pool"]
        assert native.validate_stage(legacy) == legacy_manifest
        legacy["record_pool"] = None
        with pytest.raises(ValueError):
            native.validate_stage(legacy)
    finally:
        sys.path.remove(path)
