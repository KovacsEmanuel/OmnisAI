"""Installed SL03 pairing/open proof on the SL02-owned disposable instance.

Codes, cookies and CSRF stay in this process and the child browser's stdin; test
output/receipts contain only verdict labels. No extra issuer or session store.
"""

import hashlib
import http.client
import json
import os
import pty
import re
import select
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ObserverUncertain(RuntimeError):
    """A PTY child/family did not reach a verified normal join."""


def command(cli, args, cwd, env, *, expected):
    process = subprocess.run(
        [cli, *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=50
    )
    assert process.returncode == expected, f"Installed {args[0]} exit {process.returncode}"
    return process.stdout, process.stderr


def tty_run(cli, args, cwd, env, *, limit):
    master, slave = pty.openpty()
    process = None
    output = bytearray()
    joined = False
    try:
        process = subprocess.Popen(
            [cli, *args],
            cwd=cwd,
            env=env,
            stdin=slave,
            stdout=slave,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        os.close(slave)
        slave = -1
        deadline = time.monotonic() + (330 if not args else 50)
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                try:
                    chunk = os.read(master, 256)
                except OSError:
                    break  # PTY EOF after the child exits.
                if not chunk:
                    break
                output.extend(chunk)
                assert len(output) <= limit, "TTY output exceeded bound"
            if process.poll() is not None and not select.select([master], [], [], 0)[0]:
                break
        else:
            raise TimeoutError("Installed TTY deadline exceeded")
        _, stderr = process.communicate(timeout=2)
        joined = True
        return process.returncode, bytes(output), stderr
    except BaseException as exc:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)  # Owned, unreaped session only.
            try:
                process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=3)
        if isinstance(exc, AssertionError) and not joined:
            raise ObserverUncertain("TTY observer failed before owned-family readback") from None
        raise
    finally:
        os.close(master)
        if slave >= 0:
            os.close(slave)


CODE_LINE = rb"Cod pairing Omnis \(expir\xc4\x83 \xc3\xaen 5 minute\): ([A-Za-z0-9_-]{16,128})\r?\n"


def tty_pair(cli, cwd, env, *, expected=0):
    exit_code, output, stderr = tty_run(cli, ["pair"], cwd, env, limit=256)
    assert exit_code == expected, f"Installed pair exit {exit_code}"
    if expected:
        assert not output, "Pairing denial must not print a code"
        assert stderr, "Pairing denial must explain refusal"
        return stderr.decode("utf-8")
    assert not stderr, "Pairing success must not emit diagnostics"
    match = re.fullmatch(CODE_LINE, output)
    assert match is not None, "TTY did not receive exactly one bounded pairing code"
    return match.group(1).decode("ascii")


def tty_default(cli, cwd, env, port):
    exit_code, output, stderr = tty_run(cli, [], cwd, env, limit=512)
    # GUI absence is distinct from the successful startup and TTY issuance.
    assert exit_code in {0, 2, 3}, f"Installed implicit exit {exit_code}"
    match = re.match(CODE_LINE, output)
    assert match is not None, "Fresh TTY launch did not disclose exactly one initial code"
    code = match.group(1).decode("ascii")
    public = output[match.end() :].decode("utf-8")
    assert public.startswith(f"Omnis READY: http://127.0.0.1:{port}/ — ")
    assert code not in public + stderr.decode("utf-8"), "Code escaped TTY line"
    return code, public, exit_code


def http_request(port, path, *, method="GET", body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request(
            method,
            path,
            body=json.dumps(body) if body is not None else None,
            headers={"Content-Type": "application/json", **(headers or {})},
        )
        response = connection.getresponse()
        payload = response.read(4097)
        assert len(payload) <= 4096, "Bounded HTTP response required"
        return response.status, dict(response.getheaders()), payload
    finally:
        connection.close()


def prove(cli, cwd, env, root, control, record, runtime, port, outputs, initial_code):
    """Use current installed CLI and actual private HTTP/DB; mock only opener in unit tests."""
    origin = f"http://127.0.0.1:{port}"
    db = record["containers"]["db"]
    assert initial_code is not None
    assert runtime.psql(db, "SELECT count(*) FROM pairing_issuance") == "1"
    assert (
        runtime.psql(db, "SELECT digest FROM pairing_challenge WHERE id = 1")
        == hashlib.sha256(initial_code.encode()).hexdigest()
    )
    for path in (root / "forwarder.log", root / "startup.json", root / "instance.json"):
        assert initial_code not in path.read_text(), "Initial code escaped the TTY"
    stdout, stderr = command(cli, ["pair"], cwd, env, expected=2)
    assert not stdout and "PAIRING_TTY_REQUIRED" in stderr
    stdout, stderr = command(cli, ["pair", "--json"], cwd, env, expected=2)
    assert not stdout and "PAIRING_FORMAT_REFUSED" in stderr
    assert runtime.psql(db, "SELECT count(*) FROM pairing_issuance") == "1"
    status, headers, payload = http_request(
        port, "/api/pairing", method="POST", body={"code": initial_code}, headers={"Origin": origin}
    )
    assert status == 200 and initial_code.encode() not in payload, (
        "Initial TTY code was not consumable"
    )
    cookie = headers["set-cookie"].split(";", 1)[0]
    csrf = json.loads(payload)["csrf_token"]
    assert (
        http_request(
            port,
            "/api/logout",
            method="POST",
            headers={"Origin": origin, "Cookie": cookie, "X-CSRF-Token": csrf},
        )[0]
        == 204
    )
    code = tty_pair(cli, cwd, env)
    assert code is not None
    assert runtime.psql(db, "SELECT count(*) FROM pairing_issuance") == "2"
    digest = runtime.psql(db, "SELECT digest FROM pairing_challenge WHERE id = 1")
    assert digest == hashlib.sha256(code.encode()).hexdigest(), "Stored digest differs"
    assert code not in (root / "forwarder.log").read_text()
    assert code not in (root / "startup.json").read_text()
    assert code not in (root / "instance.json").read_text()
    status, _, _ = http_request(
        port,
        "/api/pairing",
        method="POST",
        body={"code": code},
        headers={"Origin": "http://attacker.invalid"},
    )
    assert status == 403, "Foreign Origin accepted pairing"
    status, _, _ = http_request(
        port,
        "/api/pairing",
        method="POST",
        body={"code": code},
        headers={"Host": "attacker.invalid", "Origin": origin},
    )
    assert status == 400, "Foreign Host accepted pairing"
    status, headers, payload = http_request(
        port, "/api/pairing", method="POST", body={"code": code}, headers={"Origin": origin}
    )
    assert status == 200 and code.encode() not in payload, (
        "Pairing exchange refused or reflected code"
    )
    cookie = headers["set-cookie"].split(";", 1)[0]
    assert cookie.startswith("omnis_session=") and "HttpOnly" in headers["set-cookie"]
    csrf = json.loads(payload)["csrf_token"]
    status, _, payload = http_request(port, "/api/session", headers={"Cookie": cookie})
    assert status == 200 and json.loads(payload)["csrf_token"] == csrf
    status, _, _ = http_request(
        port, "/api/pairing", method="POST", body={"code": code}, headers={"Origin": origin}
    )
    assert status == 401, "One-use code accepted twice"
    status, _, _ = http_request(
        port,
        "/api/logout",
        method="POST",
        headers={"Origin": origin, "Cookie": cookie, "X-CSRF-Token": csrf},
    )
    assert status == 204
    assert http_request(port, "/api/session", headers={"Cookie": cookie})[0] == 401
    code = tty_pair(cli, cwd, env)
    assert code is not None
    runtime.psql(
        db,
        "UPDATE pairing_challenge SET expires_at = clock_timestamp() - interval '1 second' WHERE id = 1",
    )
    assert (
        http_request(
            port, "/api/pairing", method="POST", body={"code": code}, headers={"Origin": origin}
        )[0]
        == 401
    )
    # A new issuance is used through the installed, same-origin shell in an owned browser.
    code = tty_pair(cli, cwd, env)
    assert code is not None
    runner = ROOT / "cli/integration/installed_browser.mjs"
    browser_cache = Path(
        os.environ.get("PLAYWRIGHT_BROWSERS_PATH", str(Path.home() / ".cache/ms-playwright"))
    )
    assert browser_cache.is_dir(), "Pinned development browser cache unavailable"
    browser = subprocess.run(
        ["node", str(runner)],
        cwd=cwd,
        env={
            "PATH": env["PATH"],
            "HOME": str(cwd),
            "TMPDIR": str(cwd),
            "PLAYWRIGHT_BROWSERS_PATH": str(browser_cache),
            "OMNIS_BROWSER_ORIGIN": origin,
            "OMNIS_BROWSER_INSTANCE": record["instance_id"],
        },
        input=code,
        capture_output=True,
        text=True,
        timeout=75,
    )
    if "INSTALLED_BROWSER_CLOSED" not in browser.stdout:
        raise RuntimeError("Installed browser lab cleanup unverified")
    assert browser.returncode == 0 and "INSTALLED_BROWSER_SESSION_OK" in browser.stdout, (
        "Installed browser pairing/session failed"
    )
    assert code not in browser.stdout + browser.stderr, "Browser log leaked code"
    # No browser-success claim from xdg-open; this only tests the installed command's report.
    no_display = {
        key: value
        for key, value in env.items()
        if key not in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS")
    }
    opened = subprocess.run(
        [cli, "open"], cwd=cwd, env=no_display, capture_output=True, text=True, timeout=50
    )
    stdout, stderr = opened.stdout, opened.stderr
    outcome = {
        0: "BROWSER_LAUNCH_ACCEPTED",
        2: "BROWSER_UNAVAILABLE",
        3: "BROWSER_LAUNCH_FAILED",
    }.get(opened.returncode)
    assert outcome is not None and stdout.startswith(f"Omnis READY: {origin}/ — {outcome}")
    if opened.returncode:
        assert "serviciile rămân pornite" in stderr
    outputs.append(stdout + stderr)
    return outcome  # Final verdict belongs to the caller after owned teardown/readback.
