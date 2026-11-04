# Local component checks; P0.4 increments do not close G00 or certify assessment execution.
.PHONY: check test check-docs check-development check-api lint-api typecheck-api test-api test-migrations check-api-wheel check-cli test-cli check-cli-wheel test-cli-live check-release-install check-control-image check-installed-image check-installed-control

UV ?= uv
API_PY = api/.venv/bin/python
API_CHECK_PATHS = api/src api/tests
CLI_PY = cli/.venv/bin/python

.DEFAULT_GOAL := check
.PHONY: check-components test-db-contract test-sl04-pg
# Dry-run/touch/ignore-errors must not produce a successful verification receipt.
ifneq ($(filter check test check-components test-t1-upgrade-pg test-db-contract test-instance-drain-pg test-provider-settings-pg test-settings-remove-pg test-settings-remove-ui-pg test-settings-stop-read-ui-pg test-model-test-v2-pg test-settings-models-ui-pg test-sl04-pg test-b06b-publish-pg test-b06b-pure-probe-pg test-native-preparation-pg test-managed-admission-pg test-contract-method-pg test-contract-method-native-pg test-owned-initialization-native-pg test-model-test-prepare-native-pg test-model-test-execute-native-pg test-managed-composition-pg test-c03-pg test-model-projection-pg test-model-budget-pg test-model-admission-pg test-catalog-settings-e2e check-installed-start check-installed-pair-open check-installed-stop,$(or $(MAKECMDGOALS),check)),)
_verification_short_flags := $(filter-out --%,$(firstword $(MAKEFLAGS)))
ifneq ($(findstring n,$(_verification_short_flags))$(findstring t,$(_verification_short_flags))$(findstring q,$(_verification_short_flags))$(findstring i,$(_verification_short_flags)),)
$(error Unsafe Make flags for verification; execute the real gate)
endif
endif

check:
	$(API_PY) -I ops/run_test_db_gate.py --check --uv "$(UV)" --timeout-seconds 4800

# Active API-key release checks share the same private DB lifecycle in CI/local.
check-components: check-docs check-development check-api test-api test-migrations check-api-wheel check-web test-e2e check-cli check-release-install
	git diff --check

test-db-contract:
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS $(API_PY) -I -m pytest api/tests/test_fixture_ownership.py api/tests/test_database_url.py -v

.PHONY: test-instance-drain-pg
test-instance-drain-pg:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS $(API_PY) -I -B -m pytest -c api/pyproject.toml api/tests/test_instance.py api/tests/test_control_regressions.py::test_quiesce_owner_expiry_during_update_lock_wait_rolls_back -q --tb=short

.PHONY: test-dashboard
.PHONY: test-model-test-v2-pg
.PHONY: test-settings-models-ui-pg test-settings-remove-ui-pg test-settings-stop-read-ui-pg
test-settings-stop-read-ui-pg: build-web
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS OMNIS_SETTINGS_STOP_READ_UI=1 $(API_PY) -I -B -m pytest -c api/pyproject.toml 'api/tests/test_model_test_v2.py::test_api_pg_sdk_protocol_and_replay[entry_stop_read_ui]' -q -s --tb=short

test-settings-remove-ui-pg: build-web
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS OMNIS_SETTINGS_REMOVE_UI=1 $(API_PY) -I -B -m pytest -c api/pyproject.toml 'api/tests/test_model_test_v2.py::test_api_pg_sdk_protocol_and_replay[entry_remove_ui]' -q -s --tb=short

test-settings-models-ui-pg: build-web
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS OMNIS_SETTINGS_MODELS_UI=1 $(API_PY) -I -B -m pytest -c api/pyproject.toml 'api/tests/test_model_test_v2.py::test_api_pg_sdk_protocol_and_replay[settings_ui]' -q -s --tb=short

test-model-test-v2-pg:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS $(API_PY) -I -B -m pytest -c api/pyproject.toml api/tests/test_model_test_v2.py api/tests/test_model_test_v2_contract.py api/tests/test_model_test_v2_migration.py api/tests/test_model_relay_protocol.py api/tests/test_model_relay_scopes.py api/tests/test_model_relay_authority_pg.py -q --tb=short

.PHONY: test-provider-settings-pg
.PHONY: test-settings-remove-pg
test-settings-remove-pg:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS $(API_PY) -I -B -m pytest -c api/pyproject.toml api/tests/test_provider_key_api.py::test_registry_schema_empty_upgrade_backfill_and_constraints 'api/tests/test_model_test_v2.py::test_api_pg_sdk_protocol_and_replay[entry_remove]' -q --tb=short

test-provider-settings-pg:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS $(API_PY) -I -B -m pytest -c api/pyproject.toml api/tests/test_provider_key_settings.py api/tests/test_provider_key_api.py api/tests/test_provider_vault.py api/tests/test_cold_restore_pg.py -q

test-dashboard:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS $(API_PY) -I -m pytest api/tests/test_dashboard.py -q

.PHONY: test-t1-upgrade-pg
test-t1-upgrade-pg:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(API_PY) -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_t1_upgrade.py api/tests/test_health.py api/tests/test_cold_restore_reconciliation.py -q --tb=short

.PHONY: test-p1-api
test-p1-api:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS $(API_PY) -I -m pytest api/tests/test_engagements.py -q

.PHONY: test-p1-concurrency
test-p1-concurrency:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS $(API_PY) -I -m pytest api/tests/test_engagements.py -q -k 'two_editors_overlap or edit_service_rejects_noninteger'

.PHONY: test-p1-fields
test-p1-fields:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS $(API_PY) -I -m pytest api/tests/test_engagements.py -q -k 'declarative_context_and_matrix or foreign_refs_and_nested or legacy_first_save or duplicate_json_keys or escaped_unpaired_surrogate'

# Opt-in disposable PostgreSQL regression; only the shared attested DB runner admits it.
test-sl04-pg:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS $(API_PY) -I -m pytest api/tests/test_instance.py api/tests/test_stop_fence.py api/tests/test_control_regressions.py api/tests/test_local_control.py api/tests/test_supervisor.py -q

.PHONY: test-b05-case-pg
# Focused real PostgreSQL guards; invoke only through the owned private DB runner.
test-b05-case-pg:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS $(API_PY) -I -m pytest -c api/pyproject.toml api/tests/test_case_slot_service.py -q

.PHONY: test-catalog-candidates-pg
# Focused candidate persistence/restart tests through the existing owned PG lifecycle.
# No matching tests is pytest exit 5, never an empty successful product gate.
test-catalog-candidates-pg:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS $(API_PY) -I -B -m pytest -c api/pyproject.toml api/tests -k 'candidate_tracer or catalog_candidates_pg or catalog_candidate_restart' -q

.PHONY: test-b06b-publish-pg
# Independent C01 fixture/consumer; private PG lifecycle is owned by the runner.
test-b06b-publish-pg:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(API_PY) -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_b06b_publication_*.py -q

.PHONY: test-b06b-pure-probe-pg
# Published CONTRACT_PROBE -> persistent selection -> real PURE input/receipt.
# Only the existing attested runner owns disposable PostgreSQL provisioning.
test-b06b-pure-probe-pg:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(API_PY) -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_b06b_pure_probe_*.py -q

.PHONY: test-native-preparation-pg
# Persistent producer/fence/receipt controls; runtime double is not native QA.
test-native-preparation-pg:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(API_PY) -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_native_preparation*.py api/tests/test_local_control.py api/tests/test_supervisor.py -q

.PHONY: test-managed-admission-pg
.PHONY: test-contract-method-pg
.PHONY: test-contract-method-native-pg
.PHONY: test-model-test-prepare-native-pg
test-model-test-prepare-native-pg:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 OMNIS_CONTRACT_METHOD_NATIVE_PG=1 $(API_PY) -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml 'api/tests/test_contract_method_pg.py::test_contract_method_real_native_pg_owner_receipts_check_inbox[model-test-prepare]' -q --tb=no --basetemp="$$TMPDIR/mtp"

.PHONY: test-model-test-execute-native-pg
test-model-test-execute-native-pg:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 OMNIS_CONTRACT_METHOD_NATIVE_PG=1 $(API_PY) -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml 'api/tests/test_contract_method_pg.py::test_contract_method_real_native_pg_owner_receipts_check_inbox[model-test-execute]' -q --tb=no --basetemp="$$TMPDIR/mte"

.PHONY: test-owned-initialization-native-pg
test-owned-initialization-native-pg:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 OMNIS_CONTRACT_METHOD_NATIVE_PG=1 $(API_PY) -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml 'api/tests/test_contract_method_pg.py::test_contract_method_real_native_pg_owner_receipts_check_inbox[owned-initialization]' -q --tb=no --basetemp="$$TMPDIR/oi"

test-contract-method-native-pg:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 OMNIS_CONTRACT_METHOD_NATIVE_PG=1 $(API_PY) -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_contract_method_pg.py -q --tb=line

test-contract-method-pg:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(API_PY) -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_contract_method_migration.py api/tests/test_contract_method_producer.py api/tests/test_health.py api/tests/test_mission_revision_schema.py api/tests/test_catalog_candidates_pg_compatibility.py -m 'not legacy_native' -q --tb=line

test-managed-admission-pg:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(API_PY) -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_managed_*.py api/tests/test_native_task*.py -q

.PHONY: test-managed-composition-pg
test-managed-composition-pg:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(API_PY) -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_managed_composition_pg.py -q

# Integration SOURCE data/owner plus accounting; synthetic native transport only.
.PHONY: test-model-admission-pg
test-model-admission-pg:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(API_PY) -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_model_admission.py api/tests/test_model_admission_pg.py api/tests/test_model_budget.py api/tests/test_model_budget_pg.py -q --tb=line

# B06m accounting-only persistence; not native/model integration certification.
.PHONY: test-model-budget-pg
test-model-budget-pg:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(API_PY) -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_model_budget.py api/tests/test_model_budget_pg.py -q

.PHONY: test-b06a-pure
# C03 and affected legacy seams, using the same attested PostgreSQL owner.
.PHONY: test-c03-pg
test-c03-pg:
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(API_PY) -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_c03*pg.py api/tests/test_candidate_tracer_fingerprints.py api/tests/test_managed_lifecycle.py::test_pg_result_before_check_reconcile_once_restart -q

# Reuse the existing owned DB/family/cleanup owner; no new lifecycle runner.
# Prepare the fresh copy-installed origin manifest in TMPDIR before provisioning.
.PHONY: test-model-projection-pg
test-model-projection-pg:
	@test -f "$$TMPDIR/installed-origin.json" || { printf 'Fresh copy-installed projection preflight required\n' >&2; exit 2; }
	@if test -z "$$OMNIS_TEST_FIXTURE"; then \
		$(API_PY) -I -B -c 'import runpy,signal,sys; r=runpy.run_path("ops/run_test_db_gate.py"); signal.signal(signal.SIGINT,r["_request_stop"]); signal.signal(signal.SIGTERM,r["_request_stop"]); raise SystemExit(r["prove_private_fixture"]("test-model-projection-pg",sys.argv[1],600))' "$(UV)"; \
	else \
		env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 OMNIS_TEST_MODEL_PROJECTION_INSTALLED=1 $(API_PY) -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_model_projection_pg.py -q --tb=short; \
	fi

# Bounded source compiler/CLI tests; no DB, native child, model or target qualification.
# Canonical check still runs all API tests plus the original full component gate.
test-b06a-pure:
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(API_PY) -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_b06a_*.py -q

.PHONY: check-runtime
# Explicit historical Hermes adapter/AST controls, not an API-key release prerequisite.
# OAuth AST requires HERMES_NATIVE_SOURCE from prepare_hermes_runtime.py (MANAGEMENT).
check-runtime:
	$(API_PY) -I -B -c 'import runpy,sys; sys.path.insert(0,"integrations/hermes/src"); sys.argv=["integrations/hermes/tests/test_native_build.py","-v"]; runpy.run_path(sys.argv[0],run_name="__main__")'
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS $(API_PY) -I -B -m pytest -c api/pyproject.toml api/tests/test_contract_method_pg.py api/tests/test_contract_method_producer.py -m legacy_native -q
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS $(API_PY) -I -c 'import sys,pytest; sys.path.insert(0,"integrations/hermes/src"); raise SystemExit(pytest.main(["-c","api/pyproject.toml","integrations/hermes/tests/test_protocol.py","integrations/hermes/tests/test_client.py","integrations/hermes/tests/test_host.py","integrations/hermes/tests/test_startup_budget.py","integrations/hermes/tests/test_native_h02.py","integrations/hermes/tests/test_bootstrap_inventory.py","integrations/hermes/tests/test_native_preparation.py","integrations/hermes/tests/test_managed_admission.py","integrations/hermes/tests/test_managed_build.py","integrations/hermes/tests/test_model_prepare_lifecycle.py","integrations/hermes/tests/test_managed_native_source.py","integrations/hermes/tests/test_model_terminal.py","integrations/hermes/tests/test_prompt_bundle.py","integrations/hermes/tests/test_managed_composition.py","integrations/hermes/tests/test_c03_case_input.py","integrations/hermes/tests/test_c03_records.py","integrations/hermes/tests/test_contract_method.py","api/tests/test_runtime_service.py","api/tests/test_runtime_supervisor.py","-q"]))'
	$(API_PY) -I -m ruff check --config api/pyproject.toml --no-fix integrations/hermes/src integrations/hermes/tests
	$(API_PY) -I -m ruff format --config api/pyproject.toml --check integrations/hermes/src integrations/hermes/tests
	env -u PYTHONPATH MYPYPATH=api/src $(API_PY) -I -m mypy --config-file api/pyproject.toml --no-incremental integrations/hermes/src

test: check

check-docs:
	python scripts/render_docs.py --check
	python -m unittest discover -s tests/documentation -v

check-development:
	python -m unittest discover -s tests/development -v
	npm --prefix tools/development/anti-slop test

check-api:
	@test "$$($(UV) --version)" = "uv 0.12.19 (x86_64-unknown-linux-gnu)"
	@$(API_PY) -c 'import sys; assert sys.version_info[:3] == (3, 13, 15), "Python 3.13.15 required"'
	$(UV) lock --check --no-config --directory api
	$(UV) pip check --no-config --python $(API_PY)
	$(UV) audit --preview-features audit-command --locked --no-config --directory api --python-version 3.13 --python-platform linux
	$(API_PY) -I -m compileall -q api/src api/tests
	$(MAKE) --no-print-directory lint-api typecheck-api

# JSON diagnostics let the gate controls verify exact failures, not generic exits.
lint-api:
	@env -u PYTHONPATH -u MYPYPATH $(API_PY) -I -m ruff check --config api/pyproject.toml --no-fix --output-format json $(API_CHECK_PATHS)
	@env -u PYTHONPATH -u MYPYPATH $(API_PY) -I -m ruff format --config api/pyproject.toml --check --output-format json $(API_CHECK_PATHS)

typecheck-api:
	@$(API_PY) -I -c 'from importlib.metadata import version; assert version("mypy") == "2.3.1", "mypy 2.3.1 required"'
	@env -u PYTHONPATH -u MYPYPATH $(API_PY) -I -m mypy --config-file api/pyproject.toml --no-incremental --output=json $(API_CHECK_PATHS)

test-api:
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS $(API_PY) -I -m pytest api/tests --ignore=api/tests/test_migrations.py --ignore=api/tests/test_web_e2e.py --ignore=api/tests/test_cli_status.py -q -m 'not legacy_native'

test-migrations:
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS OMNIS_UV="$(UV)" $(API_PY) -I -m pytest api/tests/test_migrations.py -q

check-api-wheel:
	@test -n "$$TMPDIR" || { printf 'Set TMPDIR to a scratch directory\n' >&2; exit 2; }
	$(UV) build --no-config --wheel --clear api --out-dir "$$TMPDIR/omnis-p01-wheel"
	$(API_PY) -I -c 'import glob,sys; wheels=glob.glob(sys.argv[1]+"/*.whl"); assert len(wheels)==1, "one wheel required"; sys.path.insert(0,wheels[0]); import omnis; from omnis.api import create_app; assert str(omnis.__file__).startswith(wheels[0]); assert create_app().routes; print("Wheel import + factory OK")' "$$TMPDIR/omnis-p01-wheel"

.PHONY: generate-contracts test-contracts
generate-contracts:
	$(API_PY) -I scripts/export_contracts.py
	npm --prefix web run generate:contracts

test-contracts:
	$(API_PY) -I -m ruff check --config api/pyproject.toml scripts/export_contracts.py
	$(API_PY) -I -m ruff format --config api/pyproject.toml --check scripts/export_contracts.py
	$(API_PY) -I scripts/export_contracts.py --check
	npm --prefix web run check:contracts
	npm --prefix web run test:tooling
	npm --prefix web run typecheck

.PHONY: check-web lint-web typecheck-web test-web build-web
check-web: test-contracts lint-web test-web build-web
	@test "$$(node --version)" = "v24.21.0"
	@test "$$(npm --version)" = "11.19.0"
	npm --prefix web audit --include=dev

lint-web:
	npm --prefix web run lint

typecheck-web:
	npm --prefix web run typecheck

test-web:
	npm --prefix web test

build-web:
	npm --prefix web run build

.PHONY: test-b03-e2e
test-b03-e2e: build-web
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS $(API_PY) -I -m pytest api/tests/test_web_e2e.py -q -s -k b03

.PHONY: test-b04-e2e
test-b04-e2e: build-web
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS $(API_PY) -I -m pytest api/tests/test_web_e2e.py -q -s -k b04

.PHONY: test-e2e
test-e2e: build-web test-settings-models-ui-pg test-settings-remove-ui-pg
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS $(API_PY) -I -m pytest api/tests/test_web_e2e.py -q -s

# The existing PG/browser family owns this one authentic records-v3 journey.
# Explicit source selection also permits a read-only borrowed API interpreter.
.PHONY: test-catalog-settings-e2e
test-catalog-settings-e2e: build-web
	@test -n "$$OMNIS_TEST_FIXTURE" || { printf 'Dedicated PostgreSQL fixture required\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(API_PY) -I -B -c 'import pathlib,sys,pytest; r=pathlib.Path.cwd(); sys.path[:0]=[str(r/"api/src"),str(r/"api/tests")]; raise SystemExit(pytest.main(["-p","pytest_asyncio.plugin","-p","no:cacheprovider","-c","api/pyproject.toml","api/tests/test_web_e2e.py::test_built_web_against_real_control_plane[catalog]","-q","-s","--tb=line"]))'

# The CLI wheel is independent of the API checkout and of the operator's profile.
check-cli: test-cli test-cli-live
	@test "$$($(UV) --version)" = "uv 0.12.19 (x86_64-unknown-linux-gnu)"
	$(UV) lock --check --no-config --directory cli
	$(UV) pip check --no-config --python $(CLI_PY)
	$(API_PY) -I -m ruff check --config api/pyproject.toml --no-fix cli/src cli/tests
	$(API_PY) -I -m ruff format --config api/pyproject.toml --check cli/src cli/tests
	@env -u PYTHONPATH -u MYPYPATH $(API_PY) -I -m mypy --config-file api/pyproject.toml --no-incremental --output=json cli/src

test-cli:
	@test -n "$$TMPDIR" || { printf 'Set TMPDIR to a private scratch directory\n' >&2; exit 2; }
	XDG_CONFIG_HOME="$$TMPDIR/omnis-p04-empty-config" $(CLI_PY) -I -m unittest discover -s cli/tests -v

check-cli-wheel:
	@test -n "$$TMPDIR" || { printf 'Set TMPDIR to a private scratch directory\n' >&2; exit 2; }
	$(UV) build --no-config --wheel --clear cli --out-dir "$$TMPDIR/omnis-p04-cli-wheel"
	$(UV) venv --clear --no-config --no-python-downloads --python 3.13.15 "$$TMPDIR/omnis-p04-cli-check"
	$(UV) pip install --no-config --python "$$TMPDIR/omnis-p04-cli-check/bin/python" --no-deps "$$TMPDIR/omnis-p04-cli-wheel/omnis_cli-0.1.1-py3-none-any.whl"
	@output="$$(XDG_CONFIG_HOME="$$TMPDIR/omnis-p04-empty-config" XDG_STATE_HOME="$$TMPDIR/omnis-p04-empty-xdg" "$$TMPDIR/omnis-p04-cli-check/bin/omnis" status --json)"; code=$$?; test "$$code" -eq 3 || { printf 'Installed CLI status exited %s instead of 3\n' "$$code" >&2; exit 1; }; printf '%s' "$$output" | $(CLI_PY) -I -c 'import json,sys; x=json.load(sys.stdin); assert x["state"] == "NOT_INSTALLED" and not x["dashboard_ready"]'
	cd "$$TMPDIR" && XDG_CONFIG_HOME="$$TMPDIR/omnis-p04-empty-config" "$$TMPDIR/omnis-p04-cli-check/bin/python" -I -m unittest discover -s "$(CURDIR)/cli/tests" -v

test-cli-live: check-cli-wheel
	@test -n "$$TMPDIR" || { printf 'Set TMPDIR to a private scratch directory\n' >&2; exit 2; }
	@test -n "$$OMNIS_TEST_DATABASE_URL" || { printf 'Set a dedicated test PostgreSQL project\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS OMNIS_CLI_BIN="$$TMPDIR/omnis-p04-cli-check/bin/omnis" $(API_PY) -I -m pytest api/tests/test_cli_status.py -q

# Build a real release from both wheels, lock-exported hashes and trusted web assets.
check-release-install: check-cli-wheel build-web
	$(API_PY) -I -m ruff check --config api/pyproject.toml --no-fix ops/build_control_bundle.py cli/integration
	$(API_PY) -I -m ruff format --config api/pyproject.toml --check ops/build_control_bundle.py cli/integration
	@env -u PYTHONPATH MYPYPATH=cli/src $(API_PY) -I -m mypy --config-file api/pyproject.toml --no-incremental --output=json ops/build_control_bundle.py
	env -u PYTHONPATH -u MYPYPATH -u OMNIS_IMAGE_PROBE -u OMNIS_INSTALL_IMAGE_PROBE -u OMNIS_INSTALLED_START_PROBE -u OMNIS_INSTALLED_PAIR_OPEN_PROBE -u OMNIS_INSTALLED_STOP_PROBE -u OMNIS_INSTALLED_CONTROL_PROBE OMNIS_UV="$(UV)" OMNIS_CLI_BIN="$$TMPDIR/omnis-p04-cli-check/bin/omnis" $(CLI_PY) -I -m unittest discover -s cli/integration -v

# Explicit OCI proof only: the base must already be pulled by its platform digest.
check-control-image: check-release-install
	@$(CLI_PY) -I -c 'import os; assert not any(k.startswith("DOCKER_") for k in os.environ), "Ambient Docker override"'
	@docker context inspect "$$(docker context show)" --format '{{(index .Endpoints "docker").Host}}' | $(CLI_PY) -I -c 'import pathlib,sys; h=sys.stdin.read().strip(); assert h.startswith("unix://") and pathlib.Path(h[7:]).is_socket()'
	docker image inspect 'python:3.13.15-slim-bookworm@sha256:3e2de9c40ca4e3d73240059f9d48baff27908f10293e985a2f382a0378e6df4a' --format '{{.Id}} {{.Architecture}}'
	env -u PYTHONPATH -u MYPYPATH -u OMNIS_INSTALL_IMAGE_PROBE -u OMNIS_INSTALLED_START_PROBE -u OMNIS_INSTALLED_CONTROL_PROBE OMNIS_IMAGE_PROBE=1 OMNIS_UV="$(UV)" OMNIS_CLI_BIN="$$TMPDIR/omnis-p04-cli-check/bin/omnis" $(CLI_PY) -I -m unittest discover -s cli/integration -v

# Explicit image install/readback in disposable XDG data; never at normal startup.
check-installed-image: check-release-install
	@$(CLI_PY) -I -c 'import os; assert not any(k.startswith("DOCKER_") for k in os.environ), "Ambient Docker override"'
	@docker context inspect "$$(docker context show)" --format '{{(index .Endpoints "docker").Host}}' | $(CLI_PY) -I -c 'import pathlib,sys; h=sys.stdin.read().strip(); assert h.startswith("unix://") and pathlib.Path(h[7:]).is_socket()'
	docker image inspect 'python:3.13.15-slim-bookworm@sha256:3e2de9c40ca4e3d73240059f9d48baff27908f10293e985a2f382a0378e6df4a' --format '{{.Id}} {{.Architecture}}'
	env -u PYTHONPATH -u MYPYPATH -u OMNIS_IMAGE_PROBE -u OMNIS_INSTALLED_START_PROBE -u OMNIS_INSTALLED_CONTROL_PROBE OMNIS_INSTALL_IMAGE_PROBE=1 OMNIS_UV="$(UV)" OMNIS_CLI_BIN="$$TMPDIR/omnis-p04-cli-check/bin/omnis" $(CLI_PY) -I -m unittest discover -s cli/integration -v

# Opt-in installed product command. Explicit image preparation precedes startup.
.PHONY: check-installed-start
check-installed-start: check-release-install
	env -u PYTHONPATH -u MYPYPATH -u OMNIS_IMAGE_PROBE -u OMNIS_INSTALLED_CONTROL_PROBE -u OMNIS_INSTALLED_PAIR_OPEN_PROBE OMNIS_INSTALL_IMAGE_PROBE=1 OMNIS_INSTALLED_START_PROBE=1 OMNIS_UV="$(UV)" OMNIS_CLI_BIN="$$TMPDIR/omnis-p04-cli-check/bin/omnis" $(CLI_PY) -I -m unittest discover -s cli/integration -p test_release.py -k test_real_api_web_and_cli_bundle_is_checkout_independent -v

# Distinct installed L05-control gate: same current wheel, real PTY/API/shell/browser.
.PHONY: check-installed-pair-open
check-installed-pair-open: check-release-install
	env -u PYTHONPATH -u MYPYPATH -u OMNIS_IMAGE_PROBE -u OMNIS_INSTALLED_CONTROL_PROBE -u OMNIS_INSTALLED_START_PROBE OMNIS_INSTALL_IMAGE_PROBE=1 OMNIS_INSTALLED_PAIR_OPEN_PROBE=1 OMNIS_UV="$(UV)" OMNIS_CLI_BIN="$$TMPDIR/omnis-p04-cli-check/bin/omnis" $(CLI_PY) -I -m unittest discover -s cli/integration -p test_release.py -k test_real_api_web_and_cli_bundle_is_checkout_independent -v

# Distinct installed SL04 gate: fresh XDG, actual console Start/Stop and exact owned readback.
.PHONY: check-installed-stop
check-installed-stop: check-release-install
	env -u PYTHONPATH -u MYPYPATH -u OMNIS_IMAGE_PROBE -u OMNIS_INSTALLED_CONTROL_PROBE -u OMNIS_INSTALLED_START_PROBE -u OMNIS_INSTALLED_PAIR_OPEN_PROBE OMNIS_INSTALL_IMAGE_PROBE=1 OMNIS_INSTALLED_STOP_PROBE=1 OMNIS_UV="$(UV)" OMNIS_CLI_BIN="$$TMPDIR/omnis-p04-cli-check/bin/omnis" $(CLI_PY) -I -m unittest discover -s cli/integration -p test_release.py -k test_real_api_web_and_cli_bundle_is_checkout_independent -v

# Opt-in real P0 topology only, isolated bind data and owned teardown; not omnis start.
check-installed-control: check-release-install
	@$(CLI_PY) -I -c 'import os; assert not any(k.startswith(("DOCKER_", "COMPOSE_", "PG")) for k in os.environ), "Ambient Docker/Compose/libpq override"'
	@docker context inspect "$$(docker context show)" --format '{{(index .Endpoints "docker").Host}}' | $(CLI_PY) -I -c 'import pathlib,sys; h=sys.stdin.read().strip(); assert h.startswith("unix://") and pathlib.Path(h[7:]).is_socket()'
	docker image inspect 'postgres:18.6-bookworm@sha256:3725f4e2499eef5134592b3b4ab79a543ed7f8e533b05b5b637af926630f6650' --format '{{.Id}} {{.Architecture}}'
	docker image inspect 'python:3.13.15-slim-bookworm@sha256:3e2de9c40ca4e3d73240059f9d48baff27908f10293e985a2f382a0378e6df4a' --format '{{.Id}} {{.Architecture}}'
	env -u PYTHONPATH -u MYPYPATH -u OMNIS_IMAGE_PROBE -u OMNIS_INSTALLED_START_PROBE OMNIS_INSTALL_IMAGE_PROBE=1 OMNIS_INSTALLED_CONTROL_PROBE=1 OMNIS_UV="$(UV)" OMNIS_CLI_BIN="$$TMPDIR/omnis-p04-cli-check/bin/omnis" $(CLI_PY) -I -m unittest discover -s cli/integration -v
