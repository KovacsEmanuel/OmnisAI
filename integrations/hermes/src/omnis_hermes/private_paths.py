"""Strict Linux private files; inode-safe cleanup, no foreign adoption."""

import fcntl
import os
import stat
from pathlib import Path


def directory(path: Path) -> None:
    if not path.is_absolute() or path.resolve() != path:
        raise ValueError("Noncanonical private directory")
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise ValueError("Private directory required")
    protected = False
    for parent in reversed(path.parents):
        info = parent.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid not in {0, os.getuid()}
            or info.st_mode & 0o002
            or (info.st_mode & 0o020 and not protected)
        ):
            raise ValueError("Replaceable ancestor")
        if info.st_uid == os.getuid() and not info.st_mode & 0o077:
            protected = True


def file(info: os.stat_result) -> None:
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
    ):
        raise ValueError("Private file required")


def lock(path: Path) -> int:
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        file(os.fstat(fd))
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BaseException:
        os.close(fd)
        raise


def unlink(path: Path, identity: tuple[int, int] | None) -> None:
    try:
        info = path.lstat()
        if identity == (info.st_dev, info.st_ino):
            path.unlink()
    except FileNotFoundError:
        pass
