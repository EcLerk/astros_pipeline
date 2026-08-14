import logging

import requests
from requests import Response, RequestException
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log, \
    retry_if_exception_type

from loader.api.exceptions import RateLimitedException, FetchError
from loader.settings import settings


logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(settings.api_settings.max_retries),
    wait=wait_exponential(multiplier=1, min=1, max=32),
    retry=retry_if_exception_type((RateLimitedException, RequestException)),
    before_sleep=before_sleep_log(logger=logger, log_level=logging.WARNING),
    reraise=True,
)
def _get(url: str, timeout: float) -> Response:
    response = requests.get(url=url, timeout=timeout)

    if response.status_code == 429:
        raise RateLimitedException("429 too many requests")

    response.raise_for_status()
    return response


def fetch_raw_astros(url: str, timeout: float = 10.0) -> str:
    try:
        return _get(url=url, timeout=timeout).text
    except (RateLimitedException, requests.RequestException) as e:
        raise FetchError(
            f"Failed to fetch data after {settings.api_settings.max_retries} attempts"
        ) from e
