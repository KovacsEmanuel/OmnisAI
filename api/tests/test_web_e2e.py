"""Browser acceptance with a real owned PostgreSQL, supervisor and HTTP-served build."""

import asyncio
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from psycopg import sql
from pydantic import TypeAdapter
from sqlalchemy.engine import URL

from conftest import connect_test_database
from e2e_processes import OwnedChildren, cleanup_all, owned_children
from e2e_secrets import assert_secret_free, decode_markers
from fixtures.b06b_publication.consumer import (
    Qualified,
    cli_command,
    confirmed,
    mapping,
    publish_request,
)
from fixtures.c03_records import PACKAGE, qualify_records
from omnis.core.db import database_engine
from omnis.core.run_schema import RUN_COLUMNS
from omnis.modules.settings.catalog_inspection import inspect_publication, published_page
from omnis.modules.settings.catalog_inspection_models import CatalogInspection, CatalogPage
from test_local_control import request as control_request
from test_supervisor import start_supervisor, wait_ready

ROOT = Path(__file__).resolve().parents[2]
CATALOG_TABLES = (
    "catalog_record",
    "catalog_identity",
    "catalog_reservation",
    "catalog_command",
    "catalog_publication_head",
)


def catalog_census(database_url: URL) -> dict[str, list[tuple[object, ...]]]:
    """Exact catalog rows + xmin; pairing/session activity is deliberately separate."""
    with connect_test_database(database_url) as connection:
        return {
            table: connection.execute(
                sql.SQL(
                    "SELECT xmin::text, to_jsonb(t) FROM {} t ORDER BY to_jsonb(t)::text"
                ).format(sql.Identifier(table))
            ).fetchall()
            for table in CATALOG_TABLES
        }


def assert_catalog_unchanged(
    before: dict[str, list[tuple[object, ...]]], database_url: URL
) -> None:
    # Do not render row contents or a credential-bearing URL on a pytest failure.
    if catalog_census(database_url) != before:
        pytest.fail("Read-only catalog journey changed a catalog ledger", pytrace=False)


def prepare_catalog(
    directory: Path, database_url: URL, monkeypatch: pytest.MonkeyPatch
) -> tuple[Qualified, CatalogInspection]:
    """One authentic records-v3 producer, trusted synthetic operator TTY and Publish."""
    dsn = database_url.render_as_string(hide_password=False)
    qualified, admitted = qualify_records(directory, dsn)
    assert mapping(admitted["input_ref"])["kind"] == "contract-case-records"
    assert mapping(mapping(qualified.pure["evaluation"])["payload"])["protocol"] == (
        "c03-static-pure-records-v3"
    )
    seed = qualified.seed
    confirmation = confirmed(qualified, dsn)
    published = seed.success("publish", publish_request(qualified, confirmation), dsn)
    publication_ref = mapping(published["publication_ref"])
    body = mapping(mapping(published["publication"])["payload"])
    before = catalog_census(database_url)

    # Direct PG reader control, NOT a process observer for the HTTP server.
    # Patch the defining PURE/compiler module AND the producer's imported aliases.
    from omnis.modules.settings import candidate_catalog, candidate_index, skill_catalog

    attempts: list[str] = []

    def forbidden(*args: object, **kwargs: object) -> None:
        attempts.append("qualification_or_compile_or_pure")
        raise AssertionError("Catalog read attempted fresh qualification")

    async def read() -> CatalogInspection:
        engine = database_engine(dsn)
        try:
            async with engine.connect() as connection:
                page = await published_page(connection, None)
                assert len(page.items) == 1 and not page.has_more
                assert page.items[0].publication_ref.model_dump() == publication_ref
                return await inspect_publication(
                    connection, str(publication_ref["id"]), str(publication_ref["digest"])
                )
        finally:
            await engine.dispose()

    with monkeypatch.context() as guard:
        for module, name in (
            (skill_catalog, "compile_catalog"),
            (skill_catalog, "evaluate_pure"),
            (candidate_index, "compile_catalog"),
            (candidate_catalog, "evaluate_pure"),
            (candidate_catalog.CandidateCatalog, "dispatch"),
        ):
            guard.setattr(module, name, forbidden)
        view = asyncio.run(read())
        assert not attempts, "Direct reader attempted fresh qualification"
    assert_catalog_unchanged(before, database_url)
    # Expected browser identities originate from real producer records, not an INSERT/demo.
    assert view.publication_ref.model_dump() == publication_ref
    for field in (
        "profile_key",
        "generation",
        "snapshot_ref",
        "technical_review_ref",
        "static_evaluation_ref",
        "pure_evaluation_ref",
        "profile_ref",
        "confirmation_ref",
        "material_digest",
        "resolved_index_digest",
        "dependency_closure_digest",
        "compiler_revision",
        "evaluator_revision",
        "source_draft_refs",
        "candidate_refs",
        "dependency_closure_refs",
        "dependency_artifact_refs",
    ):
        assert view.model_dump(mode="json")[field] == body[field]
    assert any(
        b.package_key == PACKAGE and b.entity_kind == "package" for b in view.catalog_bindings
    )
    return qualified, view


def catalog_history_after_browser(
    qualified: Qualified,
    expected: CatalogInspection,
    database_url: URL,
    directory: Path,
    origin: str,
    marker_fd: int,
) -> None:
    """Joined browser, fresh LocalControl pairing, real D2 capture and immutable GET."""

    def remember(value: str) -> None:
        record = f"SECRET {value}\n".encode("ascii")
        if os.write(marker_fd, record) != len(record):
            pytest.fail("Incomplete parent secret marker evidence", pytrace=False)

    capability = (directory / "control.cap").read_text()
    code = secrets.token_urlsafe(24)
    remember(capability)
    remember(code)

    async def issue() -> None:
        async with asyncio.timeout(5):
            status = await control_request(directory, capability, {"op": "status"})
            assert status["ok"]
            reply = await control_request(
                directory,
                capability,
                {
                    "op": "pairing",
                    "instance_id": status["status"]["instance_id"],
                    "issuance_id": str(uuid4()),
                    "digest": sha256(code.encode()).hexdigest(),
                },
            )
            assert reply["ok"]

    asyncio.run(issue())
    with httpx.Client(base_url=origin, trust_env=False, timeout=3) as client:
        response = client.post("/api/pairing", headers={"Origin": origin}, json={"code": code})
        if response.status_code != 200:
            pytest.fail("Historical reader pairing refused", pytrace=False)
        remember(str(client.cookies["omnis_session"]))
        remember(str(response.json()["csrf_token"]))
        pin = expected.publication_ref
        path = f"/api/v1/settings/catalog/publications/{pin.id}/{pin.digest}"

        def read_exact() -> None:
            reply = client.get(path)
            if reply.status_code != 200:
                pytest.fail("Exact historical publication GET refused", pytrace=False)
            actual = CatalogInspection.model_validate_json(reply.content, strict=True)
            assert actual == expected

        before_reads = catalog_census(database_url)
        read_exact()
        assert_catalog_unchanged(before_reads, database_url)
        # Capture through the same legitimate owner, never SQL head mutation.
        seed = qualified.seed
        dsn = database_url.render_as_string(hide_password=False)
        head_before = seed.success(
            "head", seed.request(draft_ref=qualified.capture["draft_ref"]), dsn
        )
        assert head_before["publication_ref"] == expected.publication_ref.model_dump()
        generation = head_before["generation"]
        assert type(generation) is int
        seed.profile.write_text(seed.profile.read_text() + "\n# Owned unpublished D2\n")
        captured = seed.success("capture", seed.capture(), dsn, candidate=True)
        head_after = seed.success("head", seed.request(draft_ref=captured["draft_ref"]), dsn)
        assert captured["draft_ref"] != qualified.capture["draft_ref"]
        assert head_after["generation"] == generation + 1
        assert head_after["publication_ref"] is None
        after_capture = catalog_census(database_url)
        listed = client.get("/api/v1/settings/catalog")
        assert listed.status_code == 200
        page = CatalogPage.model_validate_json(listed.content, strict=True)
        assert page.items == [] and not page.has_more and page.next_after is None
        read_exact()
        assert_catalog_unchanged(after_capture, database_url)


def launch_api(
    listener: socket.socket, database_url: URL, ipc_directory: Path, *, own_source: bool = False
) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            *(cli_command("uvicorn") if own_source else [sys.executable, "-I", "-m", "uvicorn"]),
            "omnis.api:create_app",
            "--factory",
            "--fd",
            str(listener.fileno()),
            "--no-access-log",
            "--no-proxy-headers",
            "--log-level",
            "warning",
            "--timeout-graceful-shutdown",
            "3",
        ],
        cwd=ipc_directory,
        env={
            "PATH": os.environ["PATH"],
            "OMNIS_HTTP_PORT": str(listener.getsockname()[1]),
            "OMNIS_DATABASE_URL": database_url.render_as_string(hide_password=False),
            "OMNIS_CONTROL_DIR": str(ipc_directory),
            "OMNIS_WEB_ROOT": str(ROOT / "web/dist"),
        },
        pass_fds=(listener.fileno(),),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def wait_api(api: subprocess.Popen[str], origin: str) -> None:
    deadline = time.monotonic() + 10
    with httpx.Client(base_url=origin, trust_env=False, timeout=0.5) as client:
        while time.monotonic() < deadline:
            assert api.poll() is None, "Owned API exited during startup"
            try:
                response = client.get("/health/ready")
                if response.status_code == 200 and response.json()["dashboard_ready"]:
                    return
            except httpx.TransportError:
                pass
            time.sleep(0.05)
    pytest.fail("Built dashboard/control failed real readiness")


async def settings_models_browser(
    database_url: URL, control_dir: Path, output: Path, *, scenario: str = "settings-models"
) -> None:
    """Reuse the existing API/JS/family with the model test's real owner and TLS peer."""
    assert (ROOT / "web/dist/omnis-web.json").is_file(), "Build current web assets first"
    tables = (
        "provider_connection_revision",
        "provider_settings_command",
        "provider_selection_revision",
        "provider_model_entry",
        "provider_model_entry_revision",
        "provider_model_registry_revision",
        "provider_model_command",
        "model_record_v2",
        "model_command_v2",
        "system_operation",
        "system_operation_event",
        "model_dispatch_v2",
        "model_dispatch_event_v2",
    )
    engine = database_engine(database_url.render_as_string(hide_password=False))

    async def census() -> dict[str, list[str]]:
        async with engine.connect() as db:
            from sqlalchemy import text

            return {
                table: list(
                    (
                        await db.execute(
                            text(
                                f"SELECT row_to_json(t)::text FROM public.{table} t ORDER BY row_to_json(t)::text"
                            )
                        )
                    ).scalars()
                )
                for table in (
                    (
                        *tables,
                        *RUN_COLUMNS,
                        "engagement",
                        "engagement_revision",
                        "model_relay_authority",
                    )
                    if scenario == "s1-run"
                    else tables
                )
            }

    with owned_children() as family, socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(16)
        origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
        resources: list[tuple[subprocess.Popen[str], bool]] = []
        observations: list[str] = []
        try:
            before: dict[str, list[str]] | None = None
            diagnostic = scenario == "settings-cancel-probe"
            finite_cancel = scenario in {"settings-cancel-probe", "settings-cancel-current"}
            for stage in (
                ("before",)
                if finite_cancel or scenario == "settings-stop-read"
                else ("before", "after")
            ):
                api = launch_api(listener, database_url, control_dir, own_source=True)
                resources.append((api, False))
                await asyncio.to_thread(wait_api, api, origin)
                marker_read, marker_write = os.pipe()
                os.set_blocking(marker_read, False)
                os.set_blocking(marker_write, False)
                try:
                    driver = subprocess.Popen(
                        ["node", str(ROOT / "web/tests/e2e/run.mjs"), scenario],
                        cwd=ROOT / "web",
                        env={
                            **os.environ,
                            "OMNIS_E2E_ORIGIN": origin,
                            "OMNIS_E2E_CONTROL": str(control_dir),
                            "OMNIS_E2E_DATABASE_URL": database_url.render_as_string(
                                hide_password=False
                            ),
                            "OMNIS_E2E_PYTHON": sys.executable,
                            "OMNIS_E2E_OUTPUT": str(output),
                            "OMNIS_E2E_STAGE": stage,
                            "OMNIS_E2E_MARKER_FD": str(marker_write),
                        },
                        pass_fds=(marker_write,),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        start_new_session=True,
                    )
                    resources.append((driver, True))
                    stdout, stderr = await asyncio.to_thread(driver.communicate, timeout=120)
                    os.close(marker_write)
                    marker_write = -1
                    markers = decode_markers(os.read(marker_read, 16385))
                    assert_secret_free(markers + ["synthetic-not-provider-key"], [stdout, stderr])
                    observations.extend((stdout, stderr))
                    label = "DIAGNOSTIC" if diagnostic else "PASS"
                    assert driver.returncode == 0 and f"E2E {label} {scenario}" in stdout, (
                        "Settings browser journey failed; inspect owned sanitized output"
                    )
                finally:
                    if marker_write >= 0:
                        os.close(marker_write)
                    os.close(marker_read)
                snapshot = await census()
                if before is None:
                    before = snapshot
                else:
                    assert snapshot == before, (
                        "API restart/readback changed Settings or model history"
                    )
                api.terminate()
                api_stdout, api_stderr = await asyncio.to_thread(api.communicate, timeout=5)
                assert api.returncode == -signal.SIGTERM
                observations.extend((api_stdout, api_stderr))
            print(
                "SETTINGS_CANCEL_ONE_OPERATION_DIAGNOSTIC"
                if diagnostic
                else "SETTINGS_CANCEL_CURRENT_ONE_OPERATION_PASS"
                if finite_cancel
                else "SETTINGS_STOP_READ_ONE_OPERATION_PASS"
                if scenario == "settings-stop-read"
                else "SETTINGS_UI_REAL_API_PG_TLS_API_RESTART_PASS",
                flush=True,
            )
        finally:
            try:
                cleanup_all(resources, ownership=family)
            finally:
                await engine.dispose()
                (output / "settings-browser.log").write_text("\n".join(observations))


@pytest.fixture
def e2e_family(migrated_database_url: URL) -> Iterator[OwnedChildren]:
    # Depend on the DB fixture so adoption cleanup precedes disposable DB deletion.
    with owned_children() as family:
        yield family


@pytest.mark.parametrize(
    "case",
    [
        "flow",
        "expiry",
        "control",
        "database",
        "api",
        "offline",
        "accessibility",
        "b03",
        "b04",
        "catalog",
    ],
)
def test_built_web_against_real_control_plane(
    migrated_database_url: URL,
    ipc_directory: Path,
    e2e_family: OwnedChildren,
    case: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert (ROOT / "web/dist/omnis-web.json").is_file(), "Run make build-web before E2E"
    catalog: tuple[Qualified, CatalogInspection] | None = None
    if case == "catalog":
        assert Path(os.environ["TMPDIR"]).resolve() in ipc_directory.resolve().parents
        assert len(os.fsencode(ipc_directory / "control.sock")) < 108
        monkeypatch.delenv("OMNIS_B06B_INSTALLED", raising=False)
        monkeypatch.setenv("OMNIS_B06B_SOURCE_ROOT", str(ROOT / "api/src"))
        monkeypatch.setenv("OMNIS_B06B_PYTHON", sys.executable)
        catalog = prepare_catalog(
            ipc_directory / "records-seed", migrated_database_url, monkeypatch
        )
        supervisor = subprocess.Popen(
            cli_command("omnis.supervisor"),
            cwd=ipc_directory,
            env={
                "PATH": os.environ["PATH"],
                "OMNIS_DATABASE_URL": migrated_database_url.render_as_string(hide_password=False),
                "OMNIS_CONTROL_DIR": str(ipc_directory),
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    else:
        supervisor = start_supervisor(migrated_database_url, ipc_directory)
    api: subprocess.Popen[str] | None = None
    driver: subprocess.Popen[str] | None = None
    first_api: subprocess.Popen[str] | None = None
    first_driver: subprocess.Popen[str] | None = None
    restart_listener: socket.socket | None = None
    prior_output = ""
    diagnostic_api_logs: dict[int, str] = {}
    output = Path(os.environ["TMPDIR"]) / "omnis-p03-e2e" / case
    output.mkdir(parents=True, exist_ok=True)
    (output / "result.json").unlink(missing_ok=True)
    (output / "browser-result.json").unlink(missing_ok=True)
    marker_read, marker_write = os.pipe()
    os.set_blocking(marker_read, False)
    os.set_blocking(marker_write, False)
    catalog_before = None
    try:
        if catalog is not None:
            (output / "catalog-fixture.json").write_text(
                catalog[1].model_dump_json(indent=2) + "\n"
            )
            catalog_before = catalog_census(migrated_database_url)
        wait_ready(supervisor)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(16)
            origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
            if case == "b04":
                # dup() can reset the shared OFD to blocking. Reserve before uvicorn makes it nonblocking.
                restart_listener = listener.dup()
            api = launch_api(
                listener, migrated_database_url, ipc_directory, own_source=case == "catalog"
            )
            wait_api(api, origin)

        # Except for B04 restart, the API is now the only owner of its reserved listener.
        if case == "b04":
            with httpx.Client(base_url=origin, trust_env=False, timeout=3) as client:
                asset = client.get("/")
            assert asset.status_code == 200, (
                "B04 listener stopped serving before browser navigation"
            )
            print("B04_ASSET_AFTER_DUP status=200", flush=True)

        def launch_driver(stage: str, current_api: subprocess.Popen[str]) -> subprocess.Popen[str]:
            return subprocess.Popen(
                ["node", str(ROOT / "web/tests/e2e/run.mjs"), case],
                cwd=ROOT / "web",
                env={
                    **os.environ,
                    "OMNIS_E2E_ORIGIN": origin,
                    "OMNIS_E2E_CONTROL": str(ipc_directory),
                    "OMNIS_E2E_DATABASE_URL": migrated_database_url.render_as_string(
                        hide_password=False
                    ),
                    "OMNIS_E2E_PYTHON": sys.executable,
                    "OMNIS_E2E_API_PID": str(current_api.pid),
                    "OMNIS_E2E_SUPERVISOR_PID": str(supervisor.pid),
                    "OMNIS_E2E_OUTPUT": str(output),
                    "OMNIS_E2E_MARKER_FD": str(marker_write),
                    "OMNIS_E2E_STAGE": stage,
                },
                pass_fds=(marker_write,),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )

        driver = launch_driver("before" if case == "b04" else "single", api)
        stdout, stderr = driver.communicate(timeout=120)
        prior_output += stdout + stderr
        assert driver.returncode == 0, stdout + stderr
        assert f"E2E PASS {case}" in stdout
        print(stdout.strip())
        if catalog is not None:
            assert catalog_before is not None
            assert_catalog_unchanged(catalog_before, migrated_database_url)
            catalog_history_after_browser(
                *catalog, migrated_database_url, ipc_directory, origin, marker_write
            )
        if case == "b04":
            before = TypeAdapter(dict[str, object]).validate_json(
                (output / "browser-result.json").read_text(), strict=True
            )
            assert before["passed"] is True and before["stage"] == "before"
            assert restart_listener is not None
            first_api, first_driver = api, driver
            first_api.terminate()
            first_stdout, first_stderr = first_api.communicate(timeout=5)
            diagnostic_api_logs[first_api.pid] = first_stderr
            prior_output += first_stdout + first_stderr
            assert first_api.returncode == -signal.SIGTERM, "Old API did not exit for restart"
            api = launch_api(restart_listener, migrated_database_url, ipc_directory)
            assert api.pid != first_api.pid, "Restart must use a new backend process"
            wait_api(api, origin)
            driver = launch_driver("after", api)
            stdout, stderr = driver.communicate(timeout=120)
            prior_output += stdout + stderr
            assert driver.returncode == 0, stdout + stderr
            assert "B04_G01_RESTART_PASS" in stdout and "E2E PASS b04" in stdout
            print(stdout.strip())
    finally:
        primary = sys.exception()
        cleanup_issues: list[Exception] = []
        resources = []
        if driver is not None:
            resources.append((driver, True))
        if first_driver is not None:
            resources.append((first_driver, True))
        if api is not None:
            resources.append((api, False))
        if first_api is not None:
            resources.append((first_api, False))
        resources.append((supervisor, False))
        outputs: list[tuple[str, str]] = []
        try:
            outputs = cleanup_all(resources, ownership=e2e_family)
            for (process, _), (_, captured_stderr) in zip(resources, outputs, strict=True):
                if process is api or process is first_api:
                    diagnostic_api_logs[process.pid] = captured_stderr
        except Exception as exc:
            cleanup_issues.append(exc)
        try:
            if restart_listener is not None:
                restart_listener.close()
        except Exception as exc:
            cleanup_issues.append(exc)
        marker_evidence = b""
        try:
            os.close(marker_write)
            marker_evidence = os.read(marker_read, 16385)
        except Exception as exc:
            cleanup_issues.append(exc)
        finally:
            try:
                os.close(marker_read)
            except Exception as exc:
                cleanup_issues.append(exc)
        # Verdicts come only after every owned process has received teardown.
        for label, process, allowed in (
            ("api", api, {-signal.SIGTERM}),
            ("first_api", first_api, {-signal.SIGTERM}),
            ("supervisor", supervisor, {0, 3}),
        ):
            if process is not None and process.returncode not in allowed:
                cleanup_issues.append(
                    AssertionError(
                        f"E2E cleanup {label} PID {process.pid} exited {process.returncode}; expected {sorted(allowed)}"
                    )
                )
        combined = prior_output + "".join(part for output_pair in outputs for part in output_pair)
        markers: list[str] = []
        try:
            markers = decode_markers(marker_evidence)
            assert_secret_free(markers, [combined])
            assert "Traceback" not in combined
            # Independent parent channel checks unlabelled raw values in every process's logs too.
            assert "omnis_session=" not in combined and "csrf_token" not in combined
            if primary is None and case != "accessibility":
                assert len(markers) >= 4, "Expected code/capability/session/CSRF evidence"
        except Exception as exc:
            cleanup_issues.append(exc)
        if primary is None and not cleanup_issues and driver is not None and driver.returncode == 0:
            record = TypeAdapter(dict[str, object]).validate_json(
                (output / "browser-result.json").read_text(), strict=True
            )
            assert record["passed"] is True and record["scenario"] == case
            if case == "b04":
                assert record["stage"] == "after" and first_api is not None and api is not None
                record["backend_restart_verified"] = first_api.pid != api.pid
                from omnis.modules.diagnostics.reader import read_records

                observed_captures: set[str] = set()
                for stage, owned_api in (("before", first_api), ("after", api)):
                    retained = read_records(diagnostic_api_logs[owned_api.pid].encode("utf-8"))
                    expected: object = json.loads((output / f"ui-diagnostics-{stage}.json").read_text())
                    assert isinstance(expected, dict) and isinstance(expected.get("receipts"), list)
                    recorded = []
                    for item in expected["receipts"]:
                        assert isinstance(item, dict)
                        if item.get("state") != "RECORDED":
                            continue
                        matches = [entry for entry in retained if entry.event.model_dump(mode="json") == item.get("event")]
                        assert len(matches) == 1, "Accepted browser observation missing or duplicated in owned API stderr"
                        assert matches[0].request_correlation_id == item.get("request_correlation_id")
                        recorded.append(matches[0])
                    assert recorded, "No recorded browser observation in this API generation"
                    captures = {entry.capture_id for entry in recorded}
                    assert len(captures) == 1 and not observed_captures.intersection(captures)
                    observed_captures.update(captures)
                    if stage == "before":
                        assert any(entry.event.correlation_id == expected.get("probe_correlation") and entry.event.action == "ERROR" for entry in recorded)
                    assert_secret_free(markers, [entry.model_dump_json() for entry in retained])
                record["ui_diagnostic_sink_reader_verified"] = True
                record["ui_diagnostic_complete_history"] = False
            if catalog is not None:
                assert_secret_free(markers, [(output / "catalog-network.json").read_text()])
                record["catalog_ledger_tables"] = list(CATALOG_TABLES)
                record["catalog_get_census_unchanged"] = True
                record["unpublished_d2_excluded"] = True
                record["immutable_detail_after_d2"] = True
                record["no_rerun_scope"] = (
                    "direct PG defining-module/alias guards, not HTTP process observation"
                )
            assert_secret_free(markers, [json.dumps(record)])
            record.update(server_log_secret_check=True, cleanup_verified=True)
            (output / "result.json").write_text(json.dumps(record, indent=2) + "\n")
        if cleanup_issues:
            if isinstance(primary, Exception):
                raise ExceptionGroup(
                    "E2E primary failure and separate teardown failures", [primary, *cleanup_issues]
                )
            if primary is not None:
                raise BaseExceptionGroup(
                    "E2E primary failure and separate teardown failures", [primary, *cleanup_issues]
                )
            raise ExceptionGroup("E2E teardown failures", cleanup_issues)
