# Local component checks; P0.4 increments do not close G00 or certify assessment execution.
.PHONY: check test check-docs check-development check-api lint-api typecheck-api test-api test-migrations check-api-wheel check-cli test-cli check-cli-wheel test-cli-live

UV ?= uv
API_PY = api/.venv/bin/python
API_CHECK_PATHS = api/src api/tests
CLI_PY = cli/.venv/bin/python

check: check-docs check-development check-api test-api test-migrations check-api-wheel check-web test-e2e check-cli
	git diff --check

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
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS $(API_PY) -I -m pytest api/tests --ignore=api/tests/test_migrations.py --ignore=api/tests/test_web_e2e.py --ignore=api/tests/test_cli_status.py -q

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

.PHONY: test-e2e
test-e2e: build-web
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS $(API_PY) -I -m pytest api/tests/test_web_e2e.py -q -s

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
	$(CLI_PY) -I -m unittest discover -s cli/tests -v

check-cli-wheel:
	@test -n "$$TMPDIR" || { printf 'Set TMPDIR to a private scratch directory\n' >&2; exit 2; }
	$(UV) build --no-config --wheel --clear cli --out-dir "$$TMPDIR/omnis-p04-cli-wheel"
	$(UV) venv --clear --no-config --no-python-downloads --python 3.13.15 "$$TMPDIR/omnis-p04-cli-check"
	$(UV) pip install --no-config --python "$$TMPDIR/omnis-p04-cli-check/bin/python" --no-deps "$$TMPDIR/omnis-p04-cli-wheel/omnis_cli-0.1.0-py3-none-any.whl"
	@output="$$(XDG_STATE_HOME="$$TMPDIR/omnis-p04-empty-xdg" "$$TMPDIR/omnis-p04-cli-check/bin/omnis" status --json)"; code=$$?; test "$$code" -eq 3 || { printf 'Installed CLI status exited %s instead of 3\n' "$$code" >&2; exit 1; }; printf '%s' "$$output" | $(CLI_PY) -I -c 'import json,sys; x=json.load(sys.stdin); assert x["state"] == "NOT_INSTALLED" and not x["dashboard_ready"]'
	cd "$$TMPDIR" && "$$TMPDIR/omnis-p04-cli-check/bin/python" -I -m unittest discover -s "$(CURDIR)/cli/tests" -v

test-cli-live: check-cli-wheel
	@test -n "$$TMPDIR" || { printf 'Set TMPDIR to a private scratch directory\n' >&2; exit 2; }
	@test -n "$$OMNIS_TEST_DATABASE_URL" || { printf 'Set a dedicated test PostgreSQL project\n' >&2; exit 2; }
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS OMNIS_CLI_BIN="$$TMPDIR/omnis-p04-cli-check/bin/omnis" $(API_PY) -I -m pytest api/tests/test_cli_status.py -q
