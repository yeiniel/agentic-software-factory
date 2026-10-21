# Requires mise (tools pinned in mise.toml: `mise install`); Python tools are pinned in uv.lock.
HASH = \#
SHELL_SCRIPTS = $(shell git ls-files --cached --others --exclude-standard | while read -r f; do \
	[ -f "$$f" ] && head -n 1 "$$f" | grep -q '^$(HASH)!/bin/sh' && echo "$$f"; done)
CONTAINERFILES = $(shell git ls-files --cached --others --exclude-standard | grep -E 'Containerfile$$')
UV = uv run --locked

.PHONY: check fmt format-check lint types dead shell containerfiles quadlet links test audit mutate hooks

# The quality gate (spec 0007): everything but the audit, which needs the network.
check: format-check lint types dead shell containerfiles quadlet links test

fmt:
	$(UV) ruff format .
	mise exec -- shfmt -ln posix -w $(SHELL_SCRIPTS)

format-check:
	$(UV) ruff format --check .
	mise exec -- shfmt -ln posix -d $(SHELL_SCRIPTS)

lint:
	$(UV) ruff check .

types:
	$(UV) pyright

dead:
	$(UV) vulture

shell:
	mise exec -- shellcheck -s sh $(SHELL_SCRIPTS)

containerfiles:
	mise exec -- hadolint $(CONTAINERFILES)

quadlet:
	tools/check-quadlet

links:
	mise exec -- lychee --offline --no-progress README.md GLOSSARY.md AGENTS.md 'docs/**/*.md'

# Every test runs with dev mode, strict warnings and a per-test timeout (pyproject.toml), a skip fails, and
# every Python product must be at 100% line and branch coverage measured through its seam.
test:
	rm -rf .cov
	ASF_CHECK=1 PYTHONDEVMODE=1 $(UV) coverage run -m pytest
	$(UV) coverage combine --quiet
	$(UV) coverage json --quiet --fail-under=0 -o .cov/coverage.json
	$(UV) python tools/check_adapters_measured.py
	$(UV) coverage report

# Needs the network.
audit:
	uv audit --locked --preview-features audit-command

# Slow (a full black-box run per mutant); reports surviving mutants and does not gate.
mutate:
	mkdir -p .cov/mutate
	$(UV) --group mutate cosmic-ray init cosmic-ray.toml .cov/mutate/session.sqlite
	$(UV) --group mutate cosmic-ray exec cosmic-ray.toml .cov/mutate/session.sqlite
	$(UV) --group mutate cr-report .cov/mutate/session.sqlite

hooks:
	git config core.hooksPath .githooks
