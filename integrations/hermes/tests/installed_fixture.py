"""Exercise the installed wheel's inert listener; never launch native Hermes."""

import json
import os
import select
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"], prefix="b05-installed-") as name:
    root = Path(name)
    root.chmod(0o700)
    process = subprocess.Popen(
        [sys.argv[1], "-I", "-m", "omnis_hermes.runtime_host"],
        cwd=root,
        env={"OMNIS_RUNTIME_DIR": str(root), "LANG": "C.UTF-8"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert process.stdout is not None
        assert select.select([process.stdout], [], [], 3)[0], "Installed owner startup deadline"
        assert process.stdout.readline() == b"RUNTIME_HOST_READY\n"
        metadata = json.loads((root / "runtime.boot").read_text())
        with socket.socket(socket.AF_UNIX) as channel:
            channel.settimeout(2)
            channel.connect(str(root / "runtime.sock"))
            stream = channel.makefile("rb")

            def request(op):
                correlation = str(uuid4())
                channel.sendall(
                    json.dumps(
                        {
                            "version": 1,
                            "id": correlation,
                            "boot": metadata["boot"],
                            "capability": metadata["capability"],
                            "generation": 0,
                            "epoch": 1,
                            "op": op,
                        }
                    ).encode()
                    + b"\n"
                )
                response = json.loads(stream.readline(65537))
                assert response["id"] == correlation and response["boot"] == metadata["boot"]
                assert response["ok"] is True
                return response

            assert request("status")["state"] == "IDLE"
            assert request("stop")["drained"] is True
            assert request("status")["state"] == "IDLE"
            stream.close()
        process.terminate()
        output, error = process.communicate(timeout=3)
        assert process.returncode == 0 and output == error == b""
        assert not (root / "runtime.sock").exists() and not (root / "runtime.boot").exists()
        print(json.dumps({"installed_host": "PASS", "native_launch": "NOT_RUN", "cleanup": True}))
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)
