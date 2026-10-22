"""Owner-only AEAD revisions. Files become durable before callers publish DB refs."""

import fcntl
import hmac
import json
import os
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from omnis.core.paths import check_private_file, private_directory
from omnis.security.host_origin import reject_json_constant, unique_json_object


class VaultLocked(ValueError):
    def __init__(self) -> None:
        super().__init__("VAULT_LOCKED")


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


@dataclass(frozen=True)
class CredentialRef:
    instance_id: str
    secret_id: str
    revision: int
    namespace: Literal["openrouter", "orcarouter"]

    def __post_init__(self) -> None:
        if (
            str(UUID(self.instance_id)) != self.instance_id
            or str(UUID(self.secret_id)) != self.secret_id
            or type(self.revision) is not int
            or not 1 <= self.revision <= 9223372036854775807
            or self.namespace not in {"openrouter", "orcarouter"}
        ):
            raise ValueError("Invalid credential reference")


def _read(path: Path, maximum: int) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as source:
        check_private_file(os.fstat(source.fileno()))
        data = source.read(maximum + 1)
        if len(data) > maximum:
            raise VaultLocked()
        return data


def _durable(path: Path, value: bytes) -> None:
    temporary = path.with_name(".vault-" + secrets.token_hex(16))
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(value)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        temporary.unlink(missing_ok=True)


def _secret(value: object) -> str:
    if (
        type(value) is not str
        or not 1 <= len(value) <= 512
        or any(not 33 <= ord(character) <= 126 for character in value)
    ):
        raise ValueError("Invalid credential")
    return value


class ProviderVault:
    def __init__(self, directory: Path, key_directory: Path, instance_id: str) -> None:
        if str(UUID(instance_id)) != instance_id or directory == key_directory:
            raise ValueError("Distinct private vault/key directories required")
        self.directory = directory
        self.key_directory = key_directory
        self.instance_id = instance_id

    def _paths(self) -> tuple[Path, Path]:
        private_directory(self.directory)
        private_directory(self.key_directory)
        return self.directory / "vault.json", self.key_directory / "master.key"

    def _aad(self, reference: object) -> bytes:
        return b"omnis-vault-v1:" + canonical(reference)

    @contextmanager
    def _writer(self) -> Iterator[None]:
        descriptor = None
        try:
            self._paths()
            descriptor = os.open(
                self.directory / "vault.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600
            )
            check_private_file(os.fstat(descriptor))
            fcntl.flock(descriptor, fcntl.LOCK_EX)
        except (OSError, ValueError):
            if descriptor is not None:
                os.close(descriptor)
            raise VaultLocked() from None
        try:
            yield
        finally:
            os.close(descriptor)

    def _encrypt(self, key: bytes, value: bytes, reference: object) -> str:
        nonce = secrets.token_bytes(12)
        return (nonce + AESGCM(key).encrypt(nonce, value, self._aad(reference))).hex()

    def _decrypt(self, key: bytes, value: object, reference: object) -> bytes:
        if type(value) is not str:
            raise VaultLocked()
        raw = bytes.fromhex(value)
        return AESGCM(key).decrypt(raw[:12], raw[12:], self._aad(reference))

    def _load(self) -> tuple[bytes, dict[str, object], list[dict[str, object]]]:
        try:
            path, key_path = self._paths()
            key = _read(key_path, 32)
            if len(key) != 32:
                raise VaultLocked()
            data = json.loads(
                _read(path, 8 * 1024 * 1024),
                object_pairs_hook=unique_json_object,
                parse_constant=reject_json_constant,
            )
            if (
                type(data) is not dict
                or set(data) != {"version", "instance_id", "verifier", "entries"}
                or type(data["version"]) is not int
                or data["version"] != 1
                or data["instance_id"] != self.instance_id
                or type(data["entries"]) is not list
                or self._decrypt(key, data["verifier"], self.instance_id) != b"omnis-vault-v1"
            ):
                raise VaultLocked()
            entries: list[dict[str, object]] = []
            identities: set[bytes] = set()
            for entry in data["entries"]:
                if type(entry) is not dict or set(entry) != {"ref", "ciphertext"}:
                    raise VaultLocked()
                ref = entry["ref"]
                if type(ref) is not dict or set(ref) != {
                    "instance_id",
                    "secret_id",
                    "revision",
                    "namespace",
                }:
                    raise VaultLocked()
                # Read untrusted associations through the same strict schema as new refs.
                reference = CredentialRef(**ref)
                identity = canonical(asdict(reference))
                if reference.instance_id != self.instance_id or identity in identities:
                    raise VaultLocked()
                identities.add(identity)
                _secret(self._decrypt(key, entry["ciphertext"], ref).decode("ascii"))
                entries.append(entry)
            return key, data, entries
        except (OSError, ValueError, TypeError, KeyError, InvalidTag, RecursionError):
            raise VaultLocked() from None

    @property
    def locked(self) -> bool:
        try:
            self._load()
        except VaultLocked:
            return True
        return False

    def bootstrap(self) -> None:
        """Explicit first Save only; an orphan key or existing ciphertext is never replaced."""
        with self._writer():
            self._bootstrap()

    def _bootstrap(self) -> None:
        try:
            path, key_path = self._paths()
            if path.exists() or path.is_symlink() or key_path.exists() or key_path.is_symlink():
                self._load()
                return
            key = secrets.token_bytes(32)
            fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as output:
                output.write(key)
                output.flush()
                os.fsync(output.fileno())
            parent = os.open(self.key_directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
            _durable(
                path,
                canonical(
                    {
                        "version": 1,
                        "instance_id": self.instance_id,
                        "verifier": self._encrypt(key, b"omnis-vault-v1", self.instance_id),
                        "entries": [],
                    }
                ),
            )
        except (OSError, ValueError):
            raise VaultLocked() from None

    def put(self, reference: CredentialRef, secret: str) -> None:
        # A fenced-out process can still finish a syscall: never lose a successor's refs.
        with self._writer():
            self._put(reference, secret)

    def _put(self, reference: CredentialRef, secret: str) -> None:
        secret = _secret(secret)
        key, data, entries = self._load()
        ref = asdict(reference)
        if reference.instance_id != self.instance_id:
            raise VaultLocked()
        if any(entry["ref"] == ref for entry in entries):
            raise ValueError("Credential revision already exists")
        entries.append({"ref": ref, "ciphertext": self._encrypt(key, secret.encode("ascii"), ref)})
        data["entries"] = entries
        encoded = canonical(data)
        if len(encoded) > 8 * 1024 * 1024:
            raise VaultLocked()
        try:
            _durable(self.directory / "vault.json", encoded)
        except OSError:
            raise VaultLocked() from None

    def get(self, reference: CredentialRef) -> str:
        key, _, entries = self._load()
        for entry in entries:
            if entry["ref"] == asdict(reference):
                return self._decrypt(key, entry["ciphertext"], entry["ref"]).decode("ascii")
        raise VaultLocked()

    def command_digest(self, command_id: str, payload: object) -> str:
        key, _, _ = self._load()
        return hmac.new(
            key,
            b"omnis-secret-command-v1:" + command_id.encode("ascii") + canonical(payload),
            sha256,
        ).hexdigest()
