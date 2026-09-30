"""Test-only Python audit guard. Not a production network sandbox."""

import os
import runpy
import socket
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

url = urlsplit(
    os.environ["OMNIS_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
)
hostname = url.hostname or ""
database_socket: str | None = None
if hostname.startswith("%2F"):
    directory = unquote(hostname, errors="strict")
    if not Path(directory).is_absolute() or str(Path(directory)) != directory or "," in directory:
        raise ValueError("Invalid declared test socket")
    database_socket = str(Path(directory) / f".s.PGSQL.{url.port or 5432}")
elif hostname != "127.0.0.1" or url.port is None:
    raise ValueError("The test guard requires an explicit private fixture")
audit_fd = int(os.environ["OMNIS_TEST_AUDIT_FD"])


def record(event: str) -> None:
    data = (event + "\n").encode()
    try:
        if os.write(audit_fd, data) != len(data):
            os._exit(91)
    except OSError:
        # A caught logging error must not turn a forbidden attempt into a clean report.
        os._exit(91)


def guard(event: str, args: tuple[object, ...]) -> None:
    if event == "socket.connect":
        address = args[1]
        permitted = (
            address == database_socket
            if database_socket is not None
            else isinstance(address, tuple) and address[:2] == ("127.0.0.1", url.port)
        )
        if not permitted:
            record("EGRESS_DENIED")
            raise PermissionError("TEST_EGRESS_DENIED")
        record("CONNECT_ALLOWED")
    if event == "socket.getaddrinfo":
        if database_socket is not None or args[0] != "127.0.0.1":
            record("EGRESS_DENIED")
            raise PermissionError("TEST_EGRESS_DENIED")
        record("DNS_ALLOWED")
    if event in {"subprocess.Popen", "os.system", "os.posix_spawn"}:
        record("PROCESS_DENIED")
        raise PermissionError("TEST_PROCESS_DENIED")


sys.addaudithook(guard)
record("GUARD_READY")
if sys.argv[1] in {"negative", "negative-unix", "negative-loopback"}:
    negative_address: str | tuple[str, int] = ("192.0.2.1", 9)
    family = socket.AF_INET
    if sys.argv[1] == "negative-unix":
        assert database_socket is not None
        negative_address = database_socket + ".foreign"
        family = socket.AF_UNIX
    elif sys.argv[1] == "negative-loopback":
        negative_address = ("127.0.0.1", 5432)
    with socket.socket(family) as denied:
        try:
            denied.connect(negative_address)
        except PermissionError as exc:
            assert str(exc) == "TEST_EGRESS_DENIED"
            print("GUARD_NEGATIVE_OK")
        else:
            raise AssertionError("Guard failed before external I/O")
elif sys.argv[1] == "positive":
    with socket.socket(
        socket.AF_UNIX if database_socket is not None else socket.AF_INET
    ) as allowed:
        if database_socket is not None:
            allowed.connect(database_socket)
        else:
            allowed.connect(("127.0.0.1", url.port))
    print("GUARD_POSITIVE_OK")
else:
    module = sys.argv.pop(1)
    runpy.run_module(module, run_name="__main__")
