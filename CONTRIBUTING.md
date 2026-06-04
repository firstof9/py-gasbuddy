# Contributing to py-gasbuddy

Thanks for considering a contribution! This library is a thin async
wrapper around GasBuddy's GraphQL API and is used as the upstream
client for [ha-gasbuddy](https://github.com/firstof9/ha-gasbuddy)
(among others).

> AI coding agents: also read [AGENTS.md](AGENTS.md), which covers
> repo-specific conventions in more detail than this file.

## Getting started

```bash
git clone https://github.com/firstof9/py-gasbuddy
cd py-gasbuddy

# Python 3.13 or 3.14
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e ".[test]"

# Install pre-commit hooks
pre-commit install
```

## Running tests

```bash
# Full suite (~0.3s)
pytest -q

# With coverage
pytest --cov=py_gasbuddy --cov-report=term-missing

# Across both supported Python versions
tox
```

`tox` also runs the `lint` and `mypy` environments — useful before
opening a PR.

## Linting + formatting + types

```bash
pre-commit run --all-files
.venv/bin/python -m mypy py_gasbuddy
```

The project uses **ruff** for linting + formatting (config in
`pyproject.toml`) and **mypy** for type checking. The codebase is
fully typed; new code should be too. If you're adding a TypedDict for
a GraphQL response, define it in `models.py`.

### A note on tests + backoff

Anything that exercises the retry path will, by default, actually
sleep through backoff's exponential delays. Patch
`backoff._async.asyncio.sleep` to keep the test fast:

```python
from unittest.mock import AsyncMock, patch
with patch("backoff._async.asyncio.sleep", new=AsyncMock()):
    await manager.price_lookup()
```

## Pull requests

1. **Branch from `main`** (`git checkout -b fix/short-description`).
2. **Keep PRs small and focused.** Big "polish bundles" are harder to
   review and revert. The retry path (`process_request` +
   `_get_headers` + `_cf_last`) in particular has subtle invariants —
   touch it in small steps with thorough tests.
3. **Run the full suite + mypy + ruff before pushing.** CI runs all
   three.
4. **Add tests** for new behavior. Mock the HTTP layer with the
   custom `mock_aioclient` fixture, not the `GasBuddy.method` level. Use
   `tests/common.py:load_fixture()` for JSON/HTML responses; put new
   fixtures under `tests/fixtures/`.
5. **Document any public API changes**: `__all__` in `__init__.py` is
   the source of truth for what's public. Adding a new exception?
   Inherit from `LibraryError` if it's a refinement so existing
   handlers keep working.
6. **Reference the issue** if there is one (`Fixes #123`).

## Backward compatibility

This library is consumed by ha-gasbuddy and any other GasBuddy
clients out there. Be deliberate about:

- **Renaming or removing public functions / classes / TypedDict
  fields.** Add deprecations + a release before removing.
- **Changing exception types raised by public methods.** A subclass
  of the existing type is fine (`except LibraryError` still catches
  a `CloudflareBlocked`); a sibling is a breaking change.
- **Changing the error-envelope dict shape returned by
  `process_request`.** Callers may pattern-match the keys.

When in doubt, open an issue first to discuss.

## Reporting bugs

Use the [issue tracker](https://github.com/firstof9/py-gasbuddy/issues).
Useful information:

- py-gasbuddy version (`pip show py_gasbuddy`)
- Python version
- Whether you're using FlareSolverr (and if so, the version)
- A minimal reproducer if possible
- Debug-level logs (set `py_gasbuddy` to debug)

## Releases

The maintainer publishes releases via GitHub Releases.
`setuptools-scm` computes the version from the latest git tag, and
release notes are auto-drafted by Release Drafter.

## License

By contributing you agree your changes are licensed under the
project's existing license (see `LICENSE`).
