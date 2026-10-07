"""Deterministic subprocess peer, never imports Hermes."""

import json
import sys
import time


def emit(value):
    sys.stdout.write(json.dumps(value) + "\n")
    sys.stdout.flush()


mode = sys.argv[1] if len(sys.argv) > 1 else "normal"
if mode == "ready_stall":
    time.sleep(10)
    sys.exit()
if mode in {"ready_delay", "slow_ready"}:
    time.sleep(0.2 if mode == "ready_delay" else 2.1)
emit({"jsonrpc": "2.0", "method": "event", "params": {"type": "gateway.ready", "payload": {}}})
reverse_count = 0
reverse_ping = None
for raw in sys.stdin:
    frame = json.loads(raw)
    if "method" not in frame:
        emit(
            {
                "jsonrpc": "2.0",
                "method": "event",
                "params": {"type": "fixture.response", "payload": frame},
            }
        )
        if reverse_ping is not None:
            emit(
                {
                    "jsonrpc": "2.0",
                    "id": reverse_ping,
                    "result": {"pong": True, "reverse_reply": frame},
                }
            )
            reverse_ping = None
        continue
    method = frame["method"]
    if method == "client.capabilities":
        result = {"server_requests": ["approval"]}
    elif method == "gateway.capabilities":
        result = {"per_session_exclusive_submit": True}
    elif method == "ping":
        if mode.startswith("reverse_sequential_"):
            reverse_count += 1
            reverse_ping = frame["id"]
            emit(
                {
                    "jsonrpc": "2.0",
                    "id": f"srq-{reverse_count}",
                    "method": "approval" if mode.endswith("approval") else "untrusted.method",
                    "params": {},
                }
            )
            continue
        if mode == "stall":
            continue
        if mode == "eof":
            sys.exit()
        if mode == "oversized":
            sys.stdout.write("x" * 65537 + "\n")
            sys.stdout.flush()
            continue
        if mode == "stderr":
            sys.stderr.write("synthetic_sensitive_marker" * 100000)
            sys.stderr.flush()
        if mode == "reverse":
            emit({"jsonrpc": "2.0", "id": "srq-approval", "method": "approval", "params": {}})
            emit(
                {"jsonrpc": "2.0", "id": "srq-unknown", "method": "untrusted.method", "params": {}}
            )
            emit(
                {
                    "jsonrpc": "2.0",
                    "method": "event",
                    "params": {
                        "type": "request.cancel",
                        "payload": {
                            "id": "srq-approval",
                            "method": "approval",
                            "reason": "timeout",
                        },
                    },
                }
            )
        if mode == "detached":
            import subprocess

            child = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(10)",
                ],
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            result = {"child_pid": child.pid}
        elif mode == "environment":
            import os

            result = {"pong": True, "env": dict(os.environ), "cwd": os.getcwd()}
        else:
            result = {"pong": True}
    else:
        emit(
            {
                "jsonrpc": "2.0",
                "id": frame["id"],
                "error": {"code": -32601, "message": "Unknown method"},
            }
        )
        continue
    emit({"jsonrpc": "2.0", "id": frame["id"], "result": result})
