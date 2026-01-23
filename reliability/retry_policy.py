"""Minimal retry policy helpers for tests."""


def is_http_error_retryable(status_code: int) -> bool:
    """Return True for 5xx errors, treat client errors as non-retryable for tests."""
    try:
        return 500 <= int(status_code) < 600
    except Exception:
        return False
