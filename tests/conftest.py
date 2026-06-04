"""Provide common pytest fixtures."""

import json
import os
import shutil
import tempfile
from collections import defaultdict
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import aiohttp
import pytest
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

TEST_URL = "https://www.gasbuddy.com/graphql"

_DEFAULT_CACHE = Path.home() / ".cache" / "py_gasbuddy" / "token"


class MockRequestCall:
    """Represent a recorded mock request call."""

    def __init__(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        self.args: tuple[Any, ...] = args
        self.kwargs: dict[str, Any] = kwargs


class MockResponse:
    """Represent a queued mocked response."""

    def __init__(
        self,
        method: str,
        url: str | URL,
        status: int = 200,
        body: str | bytes | dict[str, Any] | None = None,
        exception: type[BaseException] | BaseException | None = None,
        repeat: bool = False,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.method: str = method.upper()
        self.url: URL = URL(url)
        self.status: int = status
        self.body: str | bytes | dict[str, Any] | None = body
        self.exception: type[BaseException] | BaseException | None = exception
        self.repeat: bool = repeat
        self.headers: dict[str, str] = headers or {}

    def matches(self, method: str, url: str | URL) -> bool:
        """Check if request method and url match the mocked response."""
        return self.method == method.upper() and self.url == URL(url)


class MockClientResponse:
    """Mock aiohttp.ClientResponse."""

    def __init__(
        self,
        method: str,
        url: str | URL,
        status: int,
        body: str | bytes | dict[str, Any] | None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status: int = status
        self.headers: CIMultiDictProxy[str] = CIMultiDictProxy(
            CIMultiDict(headers or {})
        )
        self.request_info: aiohttp.RequestInfo = aiohttp.RequestInfo(
            url=URL(url),
            method=method.upper(),
            headers=self.headers,
            real_url=URL(url),
        )
        self.history: tuple[aiohttp.ClientResponse, ...] = ()
        self._body_bytes: bytes
        if isinstance(body, bytes):
            self._body_bytes = body
        elif isinstance(body, str):
            self._body_bytes = body.encode("utf-8")
        elif body is not None:
            self._body_bytes = json.dumps(body).encode("utf-8")
        else:
            self._body_bytes = b""

    async def text(self, encoding: str = "utf-8", errors: str = "strict") -> str:
        """Return body as text."""
        return self._body_bytes.decode(encoding=encoding, errors=errors)

    async def read(self) -> bytes:
        """Return body as bytes."""
        return self._body_bytes

    async def json(
        self,
        encoding: str = "utf-8",
        loads: Callable[[str], Any] = json.loads,
        content_type: str = "application/json",
    ) -> Any:
        """Return body parsed as JSON."""
        return loads(self._body_bytes.decode(encoding))

    async def __aenter__(self) -> "MockClientResponse":
        """Enter response context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        """Exit response context manager."""
        pass

    def release(self) -> None:
        """Release response resource."""
        pass

    def close(self) -> None:
        """Close response."""
        pass


class AiohttpClientMock:
    """Mock aiohttp ClientSession calls."""

    def __init__(self) -> None:
        self.requests: defaultdict[tuple[str, URL], list[MockRequestCall]] = (
            defaultdict(list)
        )
        self.mocked_responses: list[MockResponse] = []
        self._patchers: list[Any] = []

    def get(
        self,
        url: str | URL,
        status: int = 200,
        body: str | bytes | dict[str, Any] | None = None,
        exception: type[BaseException] | BaseException | None = None,
        repeat: bool = False,
        headers: dict[str, str] | None = None,
    ) -> None:
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
        self,
        url: str | URL,
        status: int = 200,
        body: str | bytes | dict[str, Any] | None = None,
        exception: type[BaseException] | BaseException | None = None,
        repeat: bool = False,
        headers: dict[str, str] | None = None,
    ) -> None:
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

    def __enter__(self) -> "AiohttpClientMock":
        """Enter client mock context manager patching ClientSession._request."""
        patcher = patch.object(aiohttp.ClientSession, "_request", new=self._request)
        patcher.start()
        self._patchers.append(patcher)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        """Exit client mock context manager restoring original ClientSession._request."""
        for patcher in reversed(self._patchers):
            patcher.stop()
        self._patchers.clear()

    async def _request(
        self,
        method: str,
        url: str | URL,
        *args: Any,
        **kwargs: Any,
    ) -> MockClientResponse:
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
                        request_info=aiohttp.RequestInfo(
                            url_obj,
                            method,
                            CIMultiDictProxy(CIMultiDict()),
                            url_obj,
                        ),
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
def clear_default_cache() -> Generator[None]:
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
def mock_aioclient() -> Generator[AiohttpClientMock]:
    """Fixture to mock aioclient calls."""
    with AiohttpClientMock() as m:
        yield m
