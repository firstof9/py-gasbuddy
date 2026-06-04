"""Provide common pytest fixtures."""

import json
import os
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch

import aiohttp
import pytest
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

TEST_URL = "https://www.gasbuddy.com/graphql"

_DEFAULT_CACHE = Path.home() / ".cache" / "py_gasbuddy" / "token"


class MockRequestCall:
    """Represent a recorded mock request call."""

    def __init__(self, args, kwargs):
        self.args = args
        self.kwargs = kwargs


class MockResponse:
    """Represent a queued mocked response."""

    def __init__(
        self,
        method,
        url,
        status=200,
        body=None,
        exception=None,
        repeat=False,
        headers=None,
    ):
        self.method = method.upper()
        self.url = URL(url)
        self.status = status
        self.body = body
        self.exception = exception
        self.repeat = repeat
        self.headers = headers or {}

    def matches(self, method, url):
        """Check if request method and url match the mocked response."""
        return self.method == method.upper() and self.url == URL(url)


class MockClientResponse:
    """Mock aiohttp.ClientResponse."""

    def __init__(self, method, url, status, body, headers=None):
        self.status = status
        self.headers = CIMultiDictProxy(CIMultiDict(headers or {}))
        self.request_info = aiohttp.RequestInfo(
            url=URL(url),
            method=method.upper(),
            headers=self.headers,
            real_url=URL(url),
        )
        self.history = ()
        if isinstance(body, bytes):
            self._body_bytes = body
        elif isinstance(body, str):
            self._body_bytes = body.encode("utf-8")
        elif body is not None:
            self._body_bytes = json.dumps(body).encode("utf-8")
        else:
            self._body_bytes = b""

    async def text(self, encoding="utf-8", errors="strict"):
        """Return body as text."""
        return self._body_bytes.decode(encoding=encoding, errors=errors)

    async def read(self):
        """Return body as bytes."""
        return self._body_bytes

    async def json(
        self, encoding="utf-8", loads=json.loads, content_type="application/json"
    ):
        """Return body parsed as JSON."""
        return json.loads(self._body_bytes.decode(encoding))

    async def __aenter__(self):
        """Enter response context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit response context manager."""
        pass

    def release(self):
        """Release response resource."""
        pass

    def close(self):
        """Close response."""
        pass


class AiohttpClientMock:
    """Mock aiohttp ClientSession calls."""

    def __init__(self):
        self.requests = defaultdict(list)
        self.mocked_responses = []
        self._patchers = []

    def get(
        self, url, status=200, body=None, exception=None, repeat=False, headers=None
    ):
        """Queue a mocked GET response."""
        self.mocked_responses.append(
            MockResponse(
                "GET",
                url,
                status=status,
                body=body,
                exception=exception,
                repeat=repeat,
                headers=headers,
            )
        )

    def post(
        self, url, status=200, body=None, exception=None, repeat=False, headers=None
    ):
        """Queue a mocked POST response."""
        self.mocked_responses.append(
            MockResponse(
                "POST",
                url,
                status=status,
                body=body,
                exception=exception,
                repeat=repeat,
                headers=headers,
            )
        )

    def __enter__(self):
        """Enter client mock context manager patching ClientSession._request."""
        patcher = patch.object(aiohttp.ClientSession, "_request", new=self._request)
        patcher.start()
        self._patchers.append(patcher)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit client mock context manager restoring original ClientSession._request."""
        for patcher in reversed(self._patchers):
            patcher.stop()
        self._patchers.clear()

    async def _request(self, method, url, *args, **kwargs):
        method = method.upper()
        url_obj = URL(url)

        # Record the request
        req_call = MockRequestCall(args, kwargs)
        self.requests[(method, url_obj)].append(req_call)

        # Find matching mocked response
        matched = None
        for r in self.mocked_responses:
            if r.matches(method, url_obj):
                matched = r
                break

        if matched is None:
            raise AssertionError(f"No mocked response found for {method} {url_obj}")

        if not matched.repeat:
            self.mocked_responses.remove(matched)

        if matched.exception:
            if isinstance(matched.exception, type) and issubclass(
                matched.exception, BaseException
            ):
                if matched.exception is aiohttp.ClientResponseError:
                    raise aiohttp.ClientResponseError(
                        request_info=aiohttp.RequestInfo(url_obj, method, {}, url_obj),
                        history=(),
                        status=matched.status or 500,
                    )
                else:
                    raise matched.exception()
            else:
                raise matched.exception

        return MockClientResponse(
            method=method,
            url=url_obj,
            status=matched.status,
            body=matched.body,
            headers=matched.headers,
        )


@pytest.fixture(autouse=True)
def clear_default_cache():
    """Move real cache aside before each test and restore it afterwards."""
    had_cache = _DEFAULT_CACHE.exists()
    backup: str | None = None
    if had_cache:
        fd, backup = tempfile.mkstemp(dir=_DEFAULT_CACHE.parent, prefix="token_bak_")
        os.close(fd)
        os.unlink(backup)
        shutil.move(str(_DEFAULT_CACHE), backup)
    else:
        _DEFAULT_CACHE.unlink(missing_ok=True)
    yield
    _DEFAULT_CACHE.unlink(missing_ok=True)
    if had_cache and backup and Path(backup).exists():
        shutil.move(backup, str(_DEFAULT_CACHE))


@pytest.fixture
def mock_aioclient():
    """Fixture to mock aioclient calls."""
    with AiohttpClientMock() as m:
        yield m
