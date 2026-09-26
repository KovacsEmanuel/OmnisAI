# P0.1 checks certify only API/DB readiness, not the dashboard or an assessment.
.PHONY: check test check-docs check-development check-api test-api test-migrations check-api-wheel

UV ?= uv
API_PY = api/.venv/bin/python

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
	$(API_PY) -m compileall -q api/src api/tests

test-api:
	$(API_PY) -m pytest api/tests/test_health.py api/tests/test_fixture_ownership.py api/tests/test_sessions.py api/tests/test_http_security.py api/tests/test_instance.py api/tests/test_local_control.py api/tests/test_supervisor.py -q

test-migrations:
	OMNIS_UV="$(UV)" $(API_PY) -m pytest api/tests/test_migrations.py -q

check-api-wheel:
	@test -n "$$TMPDIR" || { printf 'Set TMPDIR to a scratch directory\n' >&2; exit 2; }
	$(UV) build --no-config --wheel --clear api --out-dir "$$TMPDIR/omnis-p01-wheel"
	$(API_PY) -I -c 'import glob,sys; wheels=glob.glob(sys.argv[1]+"/*.whl"); assert len(wheels)==1, "one wheel required"; sys.path.insert(0,wheels[0]); import omnis; from omnis.api import create_app; assert str(omnis.__file__).startswith(wheels[0]); assert create_app().routes; print("Wheel import + factory OK")' "$$TMPDIR/omnis-p01-wheel"
