"""Gate an exec'd API worker on its exact parent and private pipe."""

import argparse
import ctypes
import fcntl
import os
import signal
import stat
from collections.abc import Callable

_PR_SET_PDEATHSIG = 1


def bootstrap(gate_fd: int, owner_pid: int, app: Callable[[], int]) -> int:
    """Never enter application code until the owner can pin and release this worker."""
    try:
        if gate_fd < 3 or owner_pid < 1:
            return 4
        info = os.fstat(gate_fd)
        if (
            not stat.S_ISFIFO(info.st_mode)
            or fcntl.fcntl(gate_fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY
            or os.readlink(f"/proc/self/fd/{gate_fd}") != f"pipe:[{info.st_ino}]"
        ):
            return 4
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(_PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0) != 0:
            return 4
        if os.getppid() != owner_pid:
            return 4
        if os.read(gate_fd, 1) != b"1" or os.getppid() != owner_pid:
            return 4
    except (OSError, ValueError):
        return 4
    finally:
        try:
            os.close(gate_fd)
        except OSError:
            pass
    return app()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omnis-api-worker")
    parser.add_argument("--gate-fd", required=True, type=int)
    parser.add_argument("--owner-pid", required=True, type=int)
    args = parser.parse_args(argv)

    def run_api() -> int:
        from omnis.serve import _child_main

        return _child_main()

    return bootstrap(args.gate_fd, args.owner_pid, run_api)


if __name__ == "__main__":
    raise SystemExit(main())
