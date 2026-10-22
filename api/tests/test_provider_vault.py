"""SOURCE: real AEAD/private files, synthetic secrets; no DB/provider IO."""

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest

from omnis.modules.settings import provider_vault
from omnis.modules.settings.provider_vault import CredentialRef, ProviderVault, VaultLocked

CANARY = "synthetic-secret-canary-not-a-provider-key"


def vault_paths(root: Path) -> tuple[Path, Path]:
    data, keys = root / "vault", root / "keys"
    data.mkdir(mode=0o700)
    keys.mkdir(mode=0o700)
    return data, keys


def test_explicit_bootstrap_durable_revision_and_autounlock(tmp_path: Path) -> None:
    data, keys = vault_paths(tmp_path)
    instance = str(uuid4())
    vault = ProviderVault(data, keys, instance)
    assert vault.locked
    vault.bootstrap()
    reference = CredentialRef(instance, str(uuid4()), 1, "openrouter")
    vault.put(reference, CANARY)
    assert ProviderVault(data, keys, instance).get(reference) == CANARY
    assert CANARY not in (data / "vault.json").read_text()
    assert str(reference.secret_id) in (data / "vault.json").read_text()
    for path in (data / "vault.json", keys / "master.key"):
        assert path.stat().st_mode & 0o777 == 0o600
    # Rotation keeps referenced ciphertexts; replay cannot overwrite an immutable ref.
    second = CredentialRef(instance, reference.secret_id, 2, "openrouter")
    vault.put(second, CANARY + "-rotated")
    assert vault.get(reference) == CANARY
    with pytest.raises(ValueError, match="already exists"):
        vault.put(reference, "replacement")
    assert CANARY not in repr(vault)


@pytest.mark.parametrize("damage", ["missing", "wrong", "mode", "symlink", "ciphertext"])
def test_existing_data_never_recreates_a_missing_or_wrong_key(tmp_path: Path, damage: str) -> None:
    data, keys = vault_paths(tmp_path)
    instance = str(uuid4())
    vault = ProviderVault(data, keys, instance)
    vault.bootstrap()
    reference = CredentialRef(instance, str(uuid4()), 1, "orcarouter")
    vault.put(reference, CANARY)
    before = (data / "vault.json").read_bytes()
    key = keys / "master.key"
    if damage == "missing":
        key.unlink()
    elif damage == "wrong":
        key.write_bytes(os.urandom(32))
    elif damage == "mode":
        key.chmod(0o644)
    elif damage == "symlink":
        key.rename(keys / "original")
        key.symlink_to(keys / "original")
    else:
        payload = json.loads(before)
        payload["entries"][0]["ciphertext"] = "00" * 32
        (data / "vault.json").write_text(json.dumps(payload))
    locked = ProviderVault(data, keys, instance)
    assert locked.locked
    with pytest.raises(VaultLocked, match="VAULT_LOCKED"):
        locked.get(reference)
    with pytest.raises(VaultLocked):
        locked.bootstrap()
    if damage != "ciphertext":
        assert (data / "vault.json").read_bytes() == before


def test_aead_binds_instance_namespace_id_and_revision(tmp_path: Path) -> None:
    data, keys = vault_paths(tmp_path)
    instance = str(uuid4())
    vault = ProviderVault(data, keys, instance)
    vault.bootstrap()
    reference = CredentialRef(instance, str(uuid4()), 1, "openrouter")
    vault.put(reference, CANARY)
    payload = json.loads((data / "vault.json").read_text())
    payload["entries"][0]["ref"]["namespace"] = "orcarouter"
    (data / "vault.json").write_text(json.dumps(payload))
    assert ProviderVault(data, keys, instance).locked
    assert ProviderVault(data, keys, str(uuid4())).locked


def test_secret_bearing_digest_is_keyed_and_command_bound(tmp_path: Path) -> None:
    data, keys = vault_paths(tmp_path)
    vault = ProviderVault(data, keys, str(uuid4()))
    vault.bootstrap()
    command = str(uuid4())
    first = vault.command_digest(command, {"secret": CANARY})
    assert first == vault.command_digest(command, {"secret": CANARY})
    assert first != vault.command_digest(str(uuid4()), {"secret": CANARY})
    assert first != vault.command_digest(command, {"secret": CANARY + "x"})


def test_failed_replace_keeps_old_revision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data, keys = vault_paths(tmp_path)
    instance = str(uuid4())
    vault = ProviderVault(data, keys, instance)
    vault.bootstrap()
    reference = CredentialRef(instance, str(uuid4()), 1, "openrouter")
    vault.put(reference, CANARY)
    previous = (data / "vault.json").read_bytes()

    def failed_replace(source: object, destination: object) -> None:
        raise OSError("synthetic interrupted write")

    monkeypatch.setattr(os, "replace", failed_replace)
    with pytest.raises(VaultLocked):
        vault.put(CredentialRef(instance, reference.secret_id, 2, "openrouter"), CANARY + "2")
    assert (data / "vault.json").read_bytes() == previous
    assert ProviderVault(data, keys, instance).get(reference) == CANARY


def test_separate_vault_owners_serialize_complete_read_modify_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data, keys = vault_paths(tmp_path)
    instance = str(uuid4())
    first = ProviderVault(data, keys, instance)
    second = ProviderVault(data, keys, instance)
    first.bootstrap()
    one = CredentialRef(instance, str(uuid4()), 1, "openrouter")
    two = CredentialRef(instance, str(uuid4()), 1, "orcarouter")
    entered, release = threading.Event(), threading.Event()
    original = provider_vault._durable

    def blocked(path: Path, value: bytes) -> None:
        if not entered.is_set():
            entered.set()
            assert release.wait(3)
        original(path, value)

    monkeypatch.setattr(provider_vault, "_durable", blocked)
    with ThreadPoolExecutor(max_workers=2) as workers:
        left = workers.submit(first.put, one, CANARY)
        assert entered.wait(2)
        right = workers.submit(second.put, two, CANARY + "2")
        try:
            threading.Event().wait(0.1)
            assert not right.done()
        finally:
            release.set()
        left.result(timeout=3)
        right.result(timeout=3)
    assert first.get(one) == CANARY
    assert second.get(two) == CANARY + "2"
