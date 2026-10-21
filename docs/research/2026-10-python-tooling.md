# Python tooling for a subprocess-driven, black-box-tested monorepo (October 2026)

Researched 2026-10-21. Versions and dates come from PyPI feeds and JSON
(`https://pypi.org/pypi/<name>/<version>/json`, `https://pypi.org/rss/project/<name>/releases.xml`) and GitHub release APIs.
Claims marked **[verified locally]** were reproduced on 2026-10-21 in throw-away directories outside the repo with
`uv 0.13.1`, `ruff 0.17.1`, `coverage 7.16.2`, `pytest 9.1.1`, `mutmut 3.8.0`, `cosmic-ray 8.7.0`. Anything not confirmed is marked **unverified**.

## Summary

| Category | Recommendation | Version (date) | Status |
|---|---|---|---|
| 1. Lint + format | ruff, `select = ["ALL"]` plus a short ignore list, `extend-include = ["<adapter dir>/*"]` | 0.17.1 (2026-10-15) | Stable by PyPI classifier; pre-1.0 versioning, rules churn between minors, so pin exactly |
| 2. Types | pyright in `strict`; mypy `--strict` is the fallback | pyright 1.1.414 (2026-09-10); mypy 2.4.0 (2026-10-01) | Both Production/Stable. ty 0.0.90 is Beta (no strict mode); pyrefly 1.4.0 is stable (1.0 on 2026-05-12) |
| 3. Dead code | vulture (`--min-confidence 80` plus a whitelist), with ruff F401/F841/ARG | vulture 2.16 (2026-03-25) | Stable |
| 4. Dependency audit | `uv audit` as a separate networked target, `pip-audit` as the fallback; neither runs offline | uv 0.13.4 (2026-10-20); pip-audit 2.10.1 (2026-06-10) | `uv audit` is experimental; pip-audit stable |
| 5. Coverage | plain `coverage run -m pytest` with `[run] patch = ["subprocess"]`, `branch`, `fail_under = 100`, plus an explicit "every adapter was measured" check | coverage 7.16.2 (2026-09-27) | Stable |
| 6. Mutation | cosmic-ray on `src/` only, as a separate slow target; not mutmut | cosmic-ray 8.7.0 (2026-08-09); mutmut 3.8.0 (2026-09-12) | cosmic-ray: no PyPI status verified; mutmut: Beta |
| 7. Property-based | hypothesis (`RuleBasedStateMachine` for the core process); schemathesis only if there is an OpenAPI/JSON Schema | hypothesis 6.170.5 (2026-10-20) | Stable |
| 8. Pytest plugins | pytest 9.1 native-TOML `strict = true`, `filterwarnings = ["error"]`, pytest-timeout, pytest-asyncio, syrupy; xdist optional | pytest 9.1.1 (2026-06-19); pytest-timeout 2.4.0; pytest-asyncio 1.4.0; syrupy 6.1.1 (2026-09-13); pytest-xdist 3.8.0 | All Production/Stable |
| 9. Hook runner | plain `core.hooksPath` script calling `mise exec -- make check`; prek if staged-only semantics are wanted | prek 0.5.7 (2026-10-21); lefthook 2.2.2; hk 2.8.0; pre-commit 4.7.0 | prek calls itself "pretty new" |

## 1. Lint and format: ruff

- Current: **0.17.1**, released 2026-10-15T15:22Z, classifier `Production/Stable`. Sources: https://pypi.org/pypi/ruff/0.17.1/json , https://api.github.com/repos/astral-sh/ruff/releases/latest
- Ruff has 971 rules, 139 of them in preview **[verified locally: `ruff rule --all --output-format json`]**. Stable `ALL` does not enable preview rules unless `preview = true`.
- Docs say "Use ALL with discretion" and that Ruff auto-disables the conflicting pydocstyle pairs under `ALL`: https://docs.astral.sh/ruff/linter/#rule-selection . Locally it warned and ignored `D203` (kept `D211`) and `D213` (kept `D212`).
- Rules that conflict with the formatter and should be ignored: `COM812`, `COM819`, `Q000`-`Q004`, `D206`, `D300`, `W191`, `E111`, `E114`, `E117`, and `ISC002` in the stated configuration. Source: https://docs.astral.sh/ruff/formatter/#conflicting-lint-rules
- Under `ALL` in 0.17.1, `CPY001` (missing copyright notice) fires on every file **[verified locally]**. Ignore it.

**Is `ALL` plus an ignore list advisable?** Yes for a ~400-line core with a pinned ruff: every new rule is a deliberate decision, and the repo wants strictness. The cost is that each ruff bump can add rules, so pin the exact version (mise or uv lock) and treat a bump as a reviewed change. Do not use `ALL` unpinned.

Minimal config (starting ignore list, to be trimmed by running it once):

```toml
[tool.ruff]
target-version = "py312"
extend-include = ["adapters/*"]      # extension-less scripts; adjust the directory

[tool.ruff.lint]
select = ["ALL"]
ignore = ["COM812", "CPY001", "D203", "D213"]  # formatter conflict, copyright header, doc style pairs

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "S603", "S607", "PLR2004", "D"]  # assert, subprocess, magic values, docstrings
```

Commands: `ruff check .` and `ruff format --check .`.

**Extension-less scripts.**
- Default `include` is `["*.py", "*.pyi", "*.pyw", "*.ipynb", "*.md", "**/pyproject.toml", "**/ruff.toml", "**/.ruff.toml"]` (https://docs.astral.sh/ruff/settings/ ), so extension-less files are not discovered; Ruff does not sniff shebangs. The docs do not mention this case. Evidence is local.
- `ruff check adapter` with an explicit path checks the file **[verified locally]**. `extend-include = ["bin/*"]` makes `ruff check .` and `ruff format --check .` pick them up **[verified locally]**. Prefer `extend-include`, because `include` replaces the defaults (https://docs.astral.sh/ruff/configuration/ ).
- Per-file settings use `[tool.ruff.lint.per-file-ignores]` globs (https://docs.astral.sh/ruff/configuration/ ). The shebang rules `EXE001`/`EXE003` apply to adapters: files must be executable (`EXE001` fired on a non-executable shebang file locally).
- Gotcha: `*.md` is in the 0.17 default `include`, so `ruff format` rewrites Python code blocks in Markdown (`x=1` became `x = 1` locally). Add `extend-exclude = ["*.md"]` or `exclude` if that is unwanted, otherwise accept it for README/docs.
- Rule-selection guidance note: https://docs.astral.sh/ruff/faq/ recommends running Ruff next to a type checker.

## 2. Strict type checking

Facts per candidate. Extension-less handling was tested on all four with an explicit file argument.

| Checker | Version / date | Status | Strict equivalent | Extension-less scripts **[verified locally]** |
|---|---|---|---|---|
| pyright | 1.1.414, 2026-09-10 | Production/Stable | `typeCheckingMode = "strict"` or `strict = [paths]` (https://raw.githubusercontent.com/microsoft/pyright/main/docs/configuration.md ) | `pyright s1 s2` works; flags errors |
| mypy | 2.4.0, 2026-10-01 | Production/Stable | `--strict` (13 flags; list at https://mypy.readthedocs.io/en/stable/command_line.html ) | works, but two scripts both become module `__main__` and fail with "duplicate module"; `--scripts-are-modules` fixes it |
| ty | 0.0.90, 2026-10-20 | **Beta** (README: "currently in beta", "does not yet have a stable API; breaking changes, including changes to diagnostics, may occur between any two versions"; https://raw.githubusercontent.com/astral-sh/ty/main/README.md ) | none; `[tool.ty.rules] all = "error"` is accepted but did not flag an unannotated `def f(x)` | works |
| pyrefly | 1.4.0, 2026-10-15 | Stable since 1.0 (https://pyrefly.org/blog/v1.0/ ) | `preset = "strict"` (adds `implicit-any`, `missing-override-decorator`, `unused-ignore`, etc.; https://pyrefly.org/en/docs/configuration/ ); flagged the unannotated parameter locally | works with `project-includes` or explicit paths; `extra-file-extensions` is for extensions, not for extension-less names |

- Speed: ty claims 10x-100x over mypy/pyright (https://docs.astral.sh/ty/ , vendor claim, not measured here). For a ~400-line core plus a TUI this is irrelevant; type-check time will be dominated by Textual's stubs.
- mypy 2.4 made the Rust-based native parser the default and added parallel mode (needs the native parser): https://mypy.readthedocs.io/en/stable/command_line.html
- Newer entrant: Zuban 0.7.2 (2026-05-03), AGPL-3.0 with a commercial licence, PyPI classifier "Planning" (per https://simple-repository.app.cern.ch/project/zuban , mirror page; search result, not the official repo). Skip.
- uv-workspace support: all four resolve imports from the active virtualenv, and `uv sync` creates one `.venv` for the whole workspace. Per-package configuration details (pyright `executionEnvironments`, `extraPaths`) are documented for pyright (configuration.md above); I did not verify any checker against a multi-member uv workspace (**unverified**).
- Test code: pyright strict on `tests/` works with the same config; relax with per-directory `executionEnvironments` if needed.

**Pick: pyright strict.** Most complete strict set (unused, unknown-type, untyped-decorator rules all on), Stable, handles extension-less scripts by explicit path. Trade-off: the PyPI wrapper fetches a Node-based pyright, so first use needs network (**unverified** whether it can be pre-cached offline). Fallback: mypy 2.4 `--strict --scripts-are-modules`.

```toml
[tool.pyright]
typeCheckingMode = "strict"
pythonVersion = "3.12"
include = ["src", "console", "tests"]
venvPath = "."
venv = ".venv"
```

Command: `pyright . adapters/*` (explicit paths for scripts, since `include` discovery is `.py`-based; that rule is from the config docs, adapter handling is **[verified locally]** for the explicit-path form).

## 3. Dead-code detection

- **vulture 2.16** (2026-03-25, Production/Stable): https://pypi.org/pypi/vulture/2.16/json . `vulture bin/vt` reported `unused function 'unused' (60% confidence)` and exited 3 on an extension-less file **[verified locally]**. Options include `--min-confidence`, `--exclude`, `--config` (pyproject). Whitelist false positives (Textual handlers `on_*`, pytest fixtures) with a `whitelist.py`.
- Ruff covers unused imports/variables/arguments (`F401`, `F841`, `ARG`) but not unused functions or classes; it is already in the gate.
- **deadcode 2.4.1** (https://pypi.org/project/deadcode/ ): printed "Well done!" for the same extension-less file that vulture flagged **[verified locally]**, so it silently skipped it. Reject for this repo.
- skylos 4.50.1 exists on PyPI (https://pypi.org/project/skylos/ ); not evaluated (**unverified**).

Recommendation: vulture, `--min-confidence 80` as the hard gate (60% items like unused methods are advisory), run on `src console adapters/*` plus a whitelist file.

## 4. Dependency vulnerability audit

- **`uv audit` exists.** Local `uv 0.13.1` printed: "`uv audit` is experimental and may change without warning. Pass `--preview-features audit-command` to disable this warning." **[verified locally]** Options: `--locked`, `--frozen`, `--output-format text|json|sarif`, `--ignore`, `--ignore-until-fixed`, `--service-format osv`, `--service-url`, `--script`, `--no-dev`, `--only-group` ( `uv audit --help`). It reads `uv.lock` and reports "known vulnerabilities and adverse project statuses". Against a lock pinning `requests==2.19.0` it found 38 vulnerabilities in 5 packages **[verified locally]**. CLI reference: https://docs.astral.sh/uv/reference/cli/ (lists `uv audit`; the section details were beyond fetch limits).
- **Offline: no.** `uv audit --offline` fails with "Auditing requires network access and cannot be performed in offline mode" **[verified locally]**.
- **pip-audit 2.10.1** (2026-06-10, Production/Stable): `--locked` supports `pyproject.toml` and `pylock.*.toml` projects, **not documented for `uv.lock`**; services `pypi` (default) and `osv`; no `--offline`; exit 1 when vulnerabilities are found. Source: https://raw.githubusercontent.com/pypa/pip-audit/main/README.md . To use it with uv: `uv export --frozen --no-emit-project | pip-audit -r /dev/stdin --no-deps --disable-pip` (my composition, **unverified**).
- **osv-scanner 2.7.0** (2026-10-12): the only listed option with a true offline mode (`--offline` against a pre-downloaded database, `--download-offline-databases` to refresh) and lists `uv.lock` among supported lockfiles. Sources: https://google.github.io/osv-scanner/usage/offline-mode/ , https://google.github.io/osv-scanner/supported-languages-and-lockfiles/ , https://api.github.com/repos/google/osv-scanner/releases/latest . It is a Go binary installable through mise; I did not run it.

Recommendation: since `make check` runs in a pre-commit hook and must not depend on the network, keep the audit out of the hook: a `make audit` target running `uv audit --locked` (pin `uv >= 0.13.1`, accept the experimental flag), run on demand and before releases. If an offline gate is a hard requirement, use osv-scanner offline with a cached database.

## 5. Coverage

- **coverage 7.16.2** (2026-09-27, Production/Stable): https://pypi.org/pypi/coverage/7.16.2/json
- `[run] patch = ["subprocess"]` (added in 7.10) starts coverage in every child Python process created via `subprocess`, `os.system` and `exec*`/`spawn*`, and forces `parallel = true`, so `coverage combine` is required before `report`. Allowed values: `subprocess`, `fork`, `execv`, `_exit`. Source: https://coverage.readthedocs.io/en/latest/config.html and https://coverage.readthedocs.io/en/latest/subprocess.html
- The manual route (`COVERAGE_PROCESS_START` plus a `.pth` file containing `import coverage; coverage.process_startup()`) is documented as the older method. For `exec*e`/`spawn*e` with a custom environment, the env must carry `COVERAGE_PROCESS_START`. `patch = subprocess` is simpler and needs no `sitecustomize`.
- `[run] sigterm = true` writes data when a process gets SIGTERM (Linux/macOS). Needed if a test kills the core, the receiver or a TUI with `Popen.terminate()` or pytest-timeout kills it; without it those runs lose data. `[run] concurrency` must name `multiprocessing`/`thread` etc. if used.
- **pytest-cov 7.0 removed its own subprocess support**; docs say to use `patch = subprocess` instead: https://pytest-cov.readthedocs.io/en/latest/subprocess-support.html . pytest-cov 7.1.0 (2026-03-21) still exists. Recommendation: plain `coverage run -m pytest`; pytest-cov adds nothing here and a second layer of configuration.
- Verified end to end locally: an extension-less script run via `subprocess.run(["bin/adapter", ...])` from pytest, under `coverage run -m pytest -n2` (xdist), produced five `.coverage.*` files, and after `coverage combine` reported 100% line and branch coverage **[verified locally]**.
- **Critical gap [verified locally]:** coverage reports extension-less files only when something executed them. An adapter that no test ever runs does not appear in the report at all (with `source` or `source_dirs`), so `fail_under = 100` stays green. Add a check that every adapter is present in `coverage json` output (for example `coverage json -o cov.json` then a 5-line script comparing `cov.json["files"]` with the adapter list), or `coverage report --include` cannot fix it. Python files with `.py` do not have this problem.
- `source_dirs = ["bin"]` (added in 7.8) and `source = ["bin"]` both worked for the extension-less directory; `--include` is ignored when `source` is set.
- The parent pytest process emits `CoverageWarning: No data was collected` when it is outside `source`; silence with `disable_warnings = ["no-data-collected"]` or include the packages the parent runs.

```toml
[tool.coverage.run]
branch = true
patch = ["subprocess"]
sigterm = true
relative_files = true
source_pkgs = ["factory"]
source_dirs = ["adapters", "console/src"]   # adjust

[tool.coverage.report]
fail_under = 100
show_missing = true
skip_covered = true
```

Commands: `coverage erase; coverage run -m pytest; coverage combine; coverage report`. `fail_under = 100` returns exit status 2 below 100 (config docs above). `relative_files` is a documented option but its subprocess interplay is **unverified**.

## 6. Mutation testing

| Tool | Version / date | Result with a subprocess black-box suite |
|---|---|---|
| mutmut | 3.8.0, 2026-09-12, Beta | Cannot attribute subprocess-executed code to tests. **[verified locally]**: with a test that runs `python -m pkg 2 3` via subprocess, `mutmut run` ended with "Stopping early, because we could not find any test case for any mutant." It mutates only `.py` functions in `source_paths`, forks workers (no Windows), and runs a copy under `mutants/`. Source: https://github.com/boxed/mutmut and https://raw.githubusercontent.com/boxed/mutmut/master/README.rst |
| cosmic-ray | 8.7.0, 2026-08-09 | Works: it edits the file on disk and runs the configured `test-command`, so subprocesses see the mutation. **[verified locally]**: a 3-line `.py` script tested through `subprocess` gave 15 jobs, all killed. An extension-less `module-path = "adapter"` produced `total jobs: 0` **[verified locally]**. |

- cosmic-ray config (https://cosmic-ray.readthedocs.io/en/latest/tutorials/intro/index.html ): `module-path` (file or directory), `timeout`, `test-command`, `[cosmic-ray.distributor] name = "local"`; workflow `cosmic-ray init cfg session.sqlite`, `cosmic-ray exec ...`, `cr-report session.sqlite`.
- Cost: one full test-suite run per mutant; there is no per-mutant test selection comparable to mutmut's (**unverified** that none exists). With a black-box suite that spawns processes, expect minutes per hundred mutants; mutants that loop need `timeout`.
- Extension-less adapters cannot be mutated directly. Possible workaround, untested: a build step that copies each adapter to `<name>.py` and points the tests at the copy (**unverified**). Treat adapters as covered by property tests and review instead.
- Mutation testing does not belong in the pre-commit gate. Add a separate `make mutate` for `src/factory` (and `console` receiver code), run before merging significant changes.
- Other tools (mutatest, MutPy, Poodle) appear in an academic comparison but no 2026 benchmark was found (https://sol.sbc.org.br/index.php/sbqs/article/view/32948 ); not evaluated.

## 7. Property-based testing

- **hypothesis 6.170.5** (2026-10-20). The changelog (https://hypothesis.readthedocs.io/en/latest/changelog.html ) shows: 6.169.0 (2026-10-11) dropped Python 3.10; 6.165.7 added Python 3.15; 6.156.0 (2026-07-01) requires a Rust toolchain when building from source (use wheels; with `uv` this is automatic on common platforms); tags renamed to `vX.Y.Z` in 6.152.10. No pytest-plugin breaking changes in that window.
- pytest integration is built in: use `@given(...)` on test functions; `HYPOTHESIS_PROFILE`/`settings.register_profile` for CI vs local examples. Because each example may spawn a subprocess, set `deadline=None` and a small `max_examples` for those tests (general Hypothesis practice, **unverified** against the current docs here).
- Stateful: `RuleBasedStateMachine`, `@rule`, `Bundle`, `@invariant`; expose with `TestX = Machine.TestCase` (https://hypothesis.readthedocs.io/en/latest/stateful.html ). Fit: model the core process lifecycle as rules (submit, advance, kill) with invariants over the persisted state.
- Wire formats: Hypothesis has no built-in HTTP/JSON-schema strategy (the extras page lists only cli, codemods, django, numpy, lark, pytz, dateutil, dpcontracts: https://hypothesis.readthedocs.io/en/latest/extras.html ). Use `st.recursive` to build JSON values and `st.binary()`/`st.text()` for malformed payloads against the OTLP receiver. `hypothesis-jsonschema` 0.23.1 was last released 2024-02-28 (stale); `schemathesis` 4.32.2 (2026-10-20) generates tests from OpenAPI/GraphQL and is only worth it if the OTLP receiver is described by a schema (https://pypi.org/project/schemathesis/ ). Not evaluated beyond versions.

## 8. Pytest plugins and settings

- **pytest 9.1.1** (2026-06-19). Native TOML table `[tool.pytest]` has existed since 9.0 (https://docs.pytest.org/en/stable/reference/customize.html ). **[verified locally]**: `strict = true` works (and `--strict`, `--strict-markers`, `--strict-config` exist); an unregistered marker is an error. In the native table, option types are strict: `timeout = 30` raised `config option 'timeout' expects a string, got int`; write `timeout = "30"`.
- `filterwarnings = ["error"]` makes `ResourceWarning`, unclosed sockets/files and unraisable exceptions fail tests; combine with `-X dev` (`PYTHONDEVMODE=1`) for earlier ResourceWarning detection (CPython feature; not re-verified here).
- **pytest-timeout**: 2.4.0 (2025-05-05) is the usable release; **2.5.0 (2026-08-16) was yanked on 2026-08-17** ("accidental breaking change"), so pin `==2.4.0` (https://pypi.org/project/pytest-timeout/ ). It kills tests that hang on subprocesses; use `timeout_method = "thread"` or the signal method, and `sigterm = true` in coverage so killed processes still write data.
- **pytest-xdist 3.8.0** (2025-07-01, still latest): works with subprocess coverage **[verified locally]**: `coverage run -m pytest -n2` produced per-process data files that combined to 100%. Docs describe `load` distribution (https://pytest-xdist.readthedocs.io/en/latest/how-it-works.html ). Shared ports are the hazard: bind port 0 and read the assigned port, or derive a port from the `PYTEST_XDIST_WORKER` environment variable (xdist convention, **unverified** in the pages fetched). For a 400-line core with fast tests, xdist is optional.
- **Textual Pilot tests**: Textual's guide uses pytest-asyncio and `asyncio_mode = auto`, `async with app.run_test() as pilot`, and `pytest-textual-snapshot` for SVG screenshots (https://textual.textualize.io/guide/testing/ ). pytest-asyncio 1.4.0 (2026-05-26); Textual 8.2.8 (2026-06-30). The guide does not mention anyio (anyio 4.15.1 is available; pytest-textual-snapshot 1.1.0 dates from 2025-01-23).
- **Golden files for JSONL transcripts**:
  - **syrupy 6.1.1** (2026-09-13): `SingleFileSnapshotExtension` stores raw bytes, one file per test, committed under `__snapshots__`; `--snapshot-update` regenerates and deletes unused snapshots (`--snapshot-no-cleanup`, `--snapshot-update-new-only` available); `matcher=` with `path_type`/`path_value` normalises values; JSONL is not built in, so subclass the extension to write your normalised lines as bytes (inference). Source: https://syrupy-project.github.io/syrupy/
  - **pytest-regressions 2.11.0** (2026-05-25): `file_regression` / `data_regression`; first run fails and writes the expected file; `--force-regen` rewrites and still fails the test, `--regen-all` rewrites without failing. Source: https://pytest-regressions.readthedocs.io/en/latest/overview.html . `file_regression` options (`check_fn`, `extension`) **unverified**.
  - **inline-snapshot 0.36.1** (2026-10-12): `--inline-snapshot=create|fix|trim|update|review|disable`; `disable` is the default in CI; supports `external_file()`; pre-1.0. Source: https://15r10nk.github.io/inline-snapshot/latest/pytest/
  - Recommendation: syrupy with a custom single-file extension and a normalisation matcher for timestamps and IDs, because its update flag is explicit and files are plain text. The decisive requirement (an "UPDATE flag") is met by `--snapshot-update` here and by `--force-regen` in pytest-regressions.
- Other plugins seen: pytest-randomly 5.0.0 (2026-09-01) shuffles test order to expose order dependence; pytest-socket 0.8.1 (2026-08-19) blocks network access (relevant given the offline-Agent design); pytest-rerunfailures 16.7 exists but masks flakiness, so not recommended.

## 9. Git hook runner

All four need "run `make check`, always, with no file arguments."

- **Plain script** at `.githooks/pre-commit` plus `git config core.hooksPath .githooks` (set from a `make setup` or mise task). Zero dependencies, one command. Caveat: it tests the working tree, not the staged content, so unstaged edits can make an invalid commit pass. Mitigate with `git stash push --keep-index --include-untracked` inside the script (risk of losing work on failure; handle carefully) or accept the limitation.
- **pre-commit 4.7.0** (2026-10-12): stashes unstaged changes and runs hooks on staged contents (https://pre-commit.com/ ); local hook example with `repo: local`, `language: unsupported` (formerly `system`), `always_run: true`. Per the docs `pass_filenames` is documented for `.pre-commit-hooks.yaml`, not for local config in the fetched page (the option is known to work in practice but that is **unverified** here). Python-based runner outside mise's pins.
- **prek 0.5.7** (2026-10-21, Rust rewrite): "fully compatible with pre-commit configurations", supports native `prek.toml`, workspace mode, "pretty new" per its own site (https://prek.j178.dev/ ). Gives the stash behaviour of pre-commit without a Python dependency. Interaction with `core.hooksPath` **unverified**.
- **lefthook 2.2.2** (2026-10-13): YAML `pre-commit: jobs: - run: ...` (https://lefthook.dev/configuration/index.html ); does not stash by default (**unverified**).
- **hk 2.8.0** (2026-10-20): Pkl config, recommends installing with mise (https://hk.jdx.dev/ ); no maturity statement and no documented "command without file args" on the page; skip.

Recommendation: plain `core.hooksPath` script. The gate is a single `make check`, so a runner adds a second tool to pin without adding features. Switch to prek if staged-only semantics become a requirement.

## Other items a best-in-class setup would add

- **Dependency hygiene**: `deptry` 0.25.1 (2026-03-18) flags unused, missing and transitive imports against `pyproject.toml`, useful in a uv workspace (https://pypi.org/project/deptry/ ).
- **Security lint**: ruff `S` (bandit rules) is already in `ALL`; standalone bandit 1.9.4 (2026-02-25) adds little.
- **Licence check / SBOM**: `pip-licenses` is at 6.0.0b13 (beta, 2026-10-05); `cyclonedx-bom` 7.5.0 (2026-09-29) generates CycloneDX SBOMs. Both are release-time tasks, not pre-commit. I did not test them with `uv.lock`.
- **Complexity**: ruff `C901` and `PLR09xx` (in `ALL`) cover it; radon/xenon last released 2023/2024, skip.
- **Docstrings**: ruff `D` (in `ALL`) is enough; interrogate 1.7.0 dates from 2024-04-07.
- **Shell**: POSIX `sh` scripts need a separate gate (shellcheck, shfmt); versions not researched (**unverified**).
- **Type-checked tests**: include `tests/` in pyright strict; ruff `PT` and `ANN` rules apply via `ALL`.
- **Test order and network isolation**: pytest-randomly and pytest-socket (see section 8).
- **Pinning**: `mise` (2026.10.17 tag, https://api.github.com/repos/jdx/mise/releases/latest ) for uv and the hook; uv 0.13.4 (2026-10-20) with the dev dependency group locked in `uv.lock` for ruff, pyright, coverage, pytest.
