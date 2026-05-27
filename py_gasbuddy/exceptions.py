"""Exceptions for library."""


class MissingSearchData(Exception):
    """Exception for missing search data variable."""


class LibraryError(Exception):
    """Exception for a general library failure."""


class CloudflareBlocked(LibraryError):
    """Cloudflare blocked the CSRF/token-fetch round-trip.

    Subclass of :class:`LibraryError`, so existing ``except LibraryError``
    clauses still match. Catch this directly to distinguish a
    CSRF/Cloudflare block (typically remedied by configuring
    FlareSolverr) from other library failures such as invalid station
    IDs or GraphQL errors returned by the server.
    """


class APIError(Exception):
    """Exception for a GraphQL API error returned by the server."""


class CSRFTokenMissing(Exception):
    """Exception for missing CSRF token."""
