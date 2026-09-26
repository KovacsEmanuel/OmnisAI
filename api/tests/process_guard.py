"""Test-only Python audit guard. Not a production network sandbox."""

import os
import runpy
import socket
import sys
from urllib.parse import urlsplit

url = urlsplit(os.environ["OMNIS_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1))


def guard(event, args):
    if event == "socket.connect":
        address = args[1]
        if not isinstance(address, tuple) or address[:2] != ("127.0.0.1", url.port):
            raise PermissionError("TEST_EGRESS_DENIED")
    if event == "socket.getaddrinfo" and args[0] != "127.0.0.1":
        raise PermissionError("TEST_EGRESS_DENIED")
    if event in {"subprocess.Popen", "os.system", "os.posix_spawn"}:
        raise PermissionError("TEST_PROCESS_DENIED")


sys.addaudithook(guard)
if sys.argv[1] == "negative":
    with socket.socket() as denied:
        try:
            denied.connect(("192.0.2.1", 9))
        except PermissionError as exc:
            assert str(exc) == "TEST_EGRESS_DENIED"
            print("GUARD_NEGATIVE_OK")
        else:
            raise AssertionError("Guard failed before external I/O")
else:
    module = sys.argv.pop(1)
    runpy.run_module(module, run_name="__main__")
