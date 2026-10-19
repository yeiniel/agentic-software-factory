# Requires uv (pinned in mise.toml: `mise install`).
.PHONY: test
test:
	uv run --locked pytest
