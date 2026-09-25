# Development tooling only: this does not certify the unimplemented application.
.PHONY: check test check-docs check-development

check: check-docs check-development
	git diff --check

test: check

check-docs:
	python scripts/render_docs.py --check
	python -m unittest discover -s tests/documentation -v

check-development:
	python -m unittest discover -s tests/development -v
	npm --prefix tools/development/anti-slop test
