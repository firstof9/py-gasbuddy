# AGENTS.md

A short orientation for AI coding agents (Claude, Codex, Copilot, etc.)
working in this repo. For human contributor guidelines see
[CONTRIBUTING.md](CONTRIBUTING.md).

## What this repo is

A Python wrapper around GasBuddy's GraphQL API. Used by
[ha-gasbuddy](https://github.com/firstof9/ha-gasbuddy) as the upstream
client; designed to be usable standalone too. The library handles the
Cloudflare CSRF dance, optional FlareSolverr proxying, and a small
on-disk token cache.

```
py_gasbuddy/
├── __init__.py        # GasBuddy class + process_request retry loop
├── consts.py          # GraphQL queries + constants (FUEL_*, EV_*, headers)
├── exceptions.py      # LibraryError, APIError, CSRFTokenMissing, MissingSearchData
├── cache.py           # GasBuddyCache (aiofiles-backed)
├── parsers.py         # GraphQL response → TypedDict shaping
└── models.py          # TypedDict types
```

## Environment + toolchain

- **Python**: `requires-python = ">=3.13"`. CI matrix is 3.13 + 3.14.
- **Linting**: ruff (pinned in `.pre-commit-config.yaml`). Match the
  pre-commit version locally — newer ruff often emits noise warnings
  that aren't gated by CI.
- **Type checking**: `mypy` (strict mode via `tox -e mypy`). The
  codebase is fully typed, including TypedDicts for GraphQL responses.
- **Tests**: `pytest` + `pytest-asyncio` + `aioresponses`. The full
  suite is ~49 tests and runs in under 0.3s.

```bash
uv venv --python 3.13
uv pip install -e ".[test]"
.venv/bin/python -m pytest -q
.venv/bin/python -m mypy py_gasbuddy
```

## Architectural notes that won't be obvious from the code

### The CSRF/Cloudflare flow

GasBuddy's GraphQL endpoint requires a `gbcsrf` HTTP header. The value
is extracted from a `window.gbcsrf = "..."` JS snippet on
`https://www.gasbuddy.com/home`. Three things to know:

1. **Cloudflare often blocks the GET /home.** The optional `solver_url`
   lets users proxy through [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr)
   to bypass.
2. **Tokens are cached on disk** so we don't refetch on every call.
   `GasBuddyCache` persists `{"token": "..."}` JSON to a path chosen
   by the caller (or `~/.cache/py_gasbuddy/token` by default).
3. **`_get_headers` is the entry point** for the CSRF dance. It reads
   the cache, falls back to fetching if `_cf_last` says the cached
   token is stale, and raises `CSRFTokenMissing` when the fetch
   returns HTML without a token.

### `_cf_last` is the auth sentinel

Three states, all meaningful:

- `None` — never made a request yet
- `True` — last GraphQL POST succeeded with a 200 + valid JSON
- `False` — last attempt failed in a way that suggests the token is
  bad (403, non-JSON 200, CSRF fetch failure)

Subsequent calls inspect this to decide whether to refresh the token.
Downstream callers (e.g. ha-gasbuddy) inspect it to distinguish
"CSRF/Cloudflare block" from "GasBuddy returned an error". A public
`CloudflareBlocked` exception is being added to make this
distinguishability official — see #258.

### `process_request` error envelope

`process_request` always returns a `dict`. On failure it returns a
single-key dict:

```python
{"error": "Missing Token"}       # CSRF fetch failed
{"error": "Timeout while updating"}  # aiohttp timeout
{"error": <body_str>}             # non-JSON 200 (Cloudflare interstitial)
{"error": <ContentTypeError>}     # aiohttp ContentTypeError
{"error": <parsed_json>}          # 4xx/5xx with JSON body
```

Callers (`price_lookup`, `location_search`, etc.) check
`"error" in response` and raise `LibraryError(message)` (or
`CloudflareBlocked(message)` for the `"Missing Token"` case, once
#258 lands). Callers check `"errors" in response` for GraphQL-level
errors and raise `APIError`.

### Retry / backoff

`process_request` is decorated with `@backoff.on_exception` against
`aiohttp.ClientError`. Network errors retry with exponential delay.
Currently a 403 from the GraphQL endpoint **doesn't trigger backoff**
because the code returns the response normally instead of raising —
PR #257 is in flight to fix that.

When you add tests that exercise the retry path, patch
`backoff._async.asyncio.sleep` with `AsyncMock()`, otherwise the test
takes 30+ seconds because backoff sleeps for real:

```python
from unittest.mock import AsyncMock, patch
with patch("backoff._async.asyncio.sleep", new=AsyncMock()):
    ...
```

### Test mocking convention

Tests use `aioresponses` to mock the HTTP layer — both the GET on
`gasbuddy.com/home` (for CSRF) and the POST on `/graphql`. **Do not
mock at the `GasBuddy.method` level** unless you have a reason; the
HTTP-level mocks exercise more of the real code path.

Common helpers: `tests/common.py` has `load_fixture()`; fixtures are
plain JSON / HTML files under `tests/fixtures/`.

### Public API surface

`__all__` in `__init__.py` is the source of truth for what's public.
Currently:

- `GasBuddy` (the main class)
- The four exceptions: `APIError`, `CSRFTokenMissing`, `LibraryError`,
  `MissingSearchData` (and `CloudflareBlocked` once #258 lands)
- The TypedDict models: `EvStation`, `EvStationResult`, `GraphQLQuery`,
  `LocationSearchResult`, `PriceServiceResult`, `StationPrice`,
  `StationSummary`

Importing from `py_gasbuddy.consts` is technically internal but used
by callers who need access to the GraphQL query strings. Treat as a
soft public API and avoid breaking changes there.

## Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Tests hang for 30+ seconds | Backoff is actually sleeping | Patch `backoff._async.asyncio.sleep` |
| `S105: hardcoded password` on `ERROR_MISSING_TOKEN = "Missing Token"` | Ruff thinks "token" is a secret | `# noqa: S105` is the convention |
| `unused-ignore` mypy errors | An old `# type: ignore[...]` is no longer needed | Just remove the ignore |
| Test fails with `"data"` KeyError | `response["data"]["..."]["..."]` chain assumes well-formed GraphQL | Use `.get()` chains; partial GraphQL responses are valid |
| Cache file gets corrupted under concurrent writes | `write_cache` isn't atomic | PR #256 in flight: tempfile + `os.replace` |
| 403 from GraphQL doesn't trigger retry | `process_request` returns the response instead of raising | PR #257 in flight: raise `aiohttp.ClientResponseError` to trigger backoff |

## When you change the public surface

- **New exception**: define in `exceptions.py`, import + export via
  `__all__` in `__init__.py`. Inherit from `LibraryError` if it's a
  refinement of "library failure" so existing `except LibraryError`
  handlers keep working.
- **New GraphQL query**: define in `consts.py` as a module constant.
  Add a corresponding method to `GasBuddy`. Add response-shape tests
  with a fixture file under `tests/fixtures/`.
- **New TypedDict**: define in `models.py`. If it's user-facing, add
  to `__all__`.
- **Behavior change in `process_request`**: this is the highest-risk
  area. Update tests in `tests/test_init.py` and write new ones
  covering the changed branches. Confirm `_cf_last` ends in the
  semantically-correct state for each path.

## Releases

The maintainer publishes releases via GitHub Releases with
auto-drafted release notes. `setuptools-scm` computes the version
from the latest tag.
