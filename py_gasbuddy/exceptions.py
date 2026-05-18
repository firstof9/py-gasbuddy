"""Exceptions for library."""


class MissingSearchData(Exception):
    """Exception for missing search data variable."""


class LibraryError(Exception):
    """Exception for a general library failure."""


class APIError(Exception):
    """Exception for a GraphQL API error returned by the server."""


class CSRFTokenMissing(Exception):
    """Exception for missing CSRF token."""
