"""Test-only Python audit guard. Not a production network sandbox."""

import os
import runpy
import socket
import sys
from urllib.parse import urlsplit

url = urlsplit(
    os.environ["OMNIS_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
)
audit_fd = int(os.environ["OMNIS_TEST_AUDIT_FD"])


def record(event):
    data = (event + "\n").encode()
    try:
        if os.write(audit_fd, data) != len(data):
            os._exit(91)
    except OSError:
        # A caught logging error must not turn a forbidden attempt into a clean report.
        os._exit(91)


def guard(event, args):
    if event == "socket.connect":
        address = args[1]
        if not isinstance(address, tuple) or address[:2] != ("127.0.0.1", url.port):
            record("EGRESS_DENIED")
            raise PermissionError("TEST_EGRESS_DENIED")
        record("CONNECT_ALLOWED")
    if event == "socket.getaddrinfo":
        if args[0] != "127.0.0.1":
            record("EGRESS_DENIED")
            raise PermissionError("TEST_EGRESS_DENIED")
        record("DNS_ALLOWED")
    if event in {"subprocess.Popen", "os.system", "os.posix_spawn"}:
        record("PROCESS_DENIED")
        raise PermissionError("TEST_PROCESS_DENIED")


sys.addaudithook(guard)
record("GUARD_READY")
if sys.argv[1] == "negative":
    with socket.socket() as denied:
        try:
            denied.connect(("192.0.2.1", 9))
        except PermissionError as exc:
            assert str(exc) == "TEST_EGRESS_DENIED"
            print("GUARD_NEGATIVE_OK")
        else:
            raise AssertionError("Guard failed before external I/O")
elif sys.argv[1] == "positive":
    with socket.socket() as allowed:
        allowed.connect(("127.0.0.1", url.port))
    print("GUARD_POSITIVE_OK")
else:
    module = sys.argv.pop(1)
    runpy.run_module(module, run_name="__main__")
