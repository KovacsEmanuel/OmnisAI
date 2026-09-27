"""Owned, private IPC paths. Never follow symlinks or adopt foreign files."""

import errno
import os
import socket
import stat
from pathlib import Path


def private_directory(path: Path) -> None:
    if not path.is_absolute() or path.resolve() != path:
        raise ValueError("Control directory must be canonical and private")
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise ValueError("Control directory must be owned and private (0700)")
    protected = False
    for parent in reversed(path.parents):
        ancestor = parent.lstat()
        if (
            not stat.S_ISDIR(ancestor.st_mode)
            or ancestor.st_uid not in {0, os.getuid()}
            or ancestor.st_mode & 0o002
            or (ancestor.st_mode & 0o020 and not protected)
        ):
            raise ValueError("Control directory has a replaceable ancestor")
        if ancestor.st_uid == os.getuid() and ancestor.st_mode & 0o077 == 0:
            protected = True


def check_private_file(info) -> None:
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
    ):
        raise ValueError("Control file must be private and owned (0600)")


def remove_stale_socket(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if (
        not stat.S_ISSOCK(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        raise ValueError("Control socket is not an owned private socket")
    with socket.socket(socket.AF_UNIX) as probe:
        probe.settimeout(0.2)
        try:
            probe.connect(str(path))
        except OSError as exc:
            if exc.errno != errno.ECONNREFUSED:
                raise ValueError("Control socket ownership is uncertain") from None
        else:
            raise ValueError("Control socket is already active")
    path.unlink()


def unlink_owned_inode(path: Path, inode: int | None) -> None:
    if inode is None:
        return
    try:
        if path.lstat().st_ino == inode:
            path.unlink()
    except FileNotFoundError:
        return
