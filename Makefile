# P0.1/P0.2 checks certify local API/control, not the dashboard or an assessment.
.PHONY: check test check-docs check-development check-api lint-api typecheck-api test-api test-migrations check-api-wheel

UV ?= uv
API_PY = api/.venv/bin/python
API_CHECK_PATHS = api/src api/tests

check: check-docs check-development check-api test-api test-migrations check-api-wheel
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
	env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS $(API_PY) -I -m pytest api/tests --ignore=api/tests/test_migrations.py -q

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
	$(API_PY) -I scripts/export_contracts.py --check
	npm --prefix web run check:contracts
	npm --prefix web run test:tooling
