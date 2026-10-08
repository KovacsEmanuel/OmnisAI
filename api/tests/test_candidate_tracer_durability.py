"""Real filesystem durability boundary; no claim of physical power-loss coverage."""

from pathlib import Path
from uuid import uuid4

import pytest

from omnis.modules.settings import candidate_material as material


def test_candidate_tracer_new_root_links_synced_before_finalization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    synced: list[Path] = []
    actual_sync = material.sync_directory

    def observe(path: Path) -> None:
        actual_sync(path)  # Keep every real fsync, observe its successful completion.
        synced.append(path)

    monkeypatch.setattr(material, "sync_directory", observe)
    root = material.private_root(tmp_path / "catalog")
    expected = {root.parent, root, *(root / name for name in ("drafts", "candidates", "staging"))}
    assert expected <= set(synced), "new catalog namespace links lack successful parent fsync"
    before = list(synced)
    finalized = material.finalize(root, "drafts", str(uuid4()), {"source.txt": b"exact source"})
    assert (finalized / "source.txt").read_bytes() == b"exact source"
    assert finalized.stat().st_mode & 0o222 == 0
    assert (finalized / "source.txt").stat().st_mode & 0o222 == 0
    assert synced[: len(before)] == before
    # Reopening existing private namespaces must remain supported.
    assert material.private_root(root) == root
