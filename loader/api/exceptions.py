class RateLimitedException(Exception):
    """HTTP 429 — signal for tenacity to retry."""


class FetchError(Exception):
    """Raised when all retry attempts to fetch the data have failed."""
