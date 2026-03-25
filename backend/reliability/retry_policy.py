"""Retry policy helpers for HTTP error classification.

Provides utilities to determine whether HTTP errors are transient
(and thus retryable) vs permanent.
"""


def is_http_error_retryable(status_code: int) -> bool:
    """Return True for transient HTTP errors that should be retried.

    Retryable status codes:
    - 429: Too Many Requests (rate limited)
    - 500: Internal Server Error
    - 502: Bad Gateway
    - 503: Service Unavailable
    - 504: Gateway Timeout

    Args:
        status_code: HTTP status code to check

    Returns:
        True if the error is transient and should be retried
    """
    try:
        code = int(status_code)
        return code == 429 or 500 <= code < 600
    except (ValueError, TypeError):
        return False
