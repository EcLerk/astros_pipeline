import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from loader.api.api import _get, fetch_raw_astros
from loader.api.exceptions import FetchError
from loader.settings import settings

SAMPLE_PAYLOAD = json.dumps(
    {
        "people": [{"craft": "ISS", "name": "Oleg Kononenko"}],
        "number": 1,
        "message": "success",
    }
)


def _make_response(status_code: int, text: str = "") -> MagicMock:
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    response.text = text
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(
            f"{status_code} error"
        )
    else:
        response.raise_for_status.return_value = None
    return response


class TestFetchRawAstrosSuccess:
    @patch("loader.api.api.requests.get")
    def test_returns_response_text_on_first_success(self, mock_get):
        mock_get.return_value = _make_response(200, SAMPLE_PAYLOAD)

        result = fetch_raw_astros(url="http://fake-url")

        assert result == SAMPLE_PAYLOAD
        assert mock_get.call_count == 1

    @patch("loader.api.api.requests.get")
    def test_passes_url_and_timeout_to_requests(self, mock_get):
        mock_get.return_value = _make_response(200, SAMPLE_PAYLOAD)

        fetch_raw_astros(url="http://fake-url", timeout=5.0)

        args, kwargs = mock_get.call_args
        assert kwargs["url"] == "http://fake-url"
        assert kwargs["timeout"] == 5.0


class TestFetchRawAstrosRetries:
    @patch("loader.api.api.requests.get")
    def test_retries_on_429_then_succeeds(self, mock_get):
        mock_get.side_effect = [
            _make_response(429),
            _make_response(429),
            _make_response(200, SAMPLE_PAYLOAD),
        ]

        result = fetch_raw_astros(url="http://fake-url")

        assert result == SAMPLE_PAYLOAD
        assert mock_get.call_count == 3

    @patch("loader.api.api.requests.get")
    def test_retries_on_connection_error_then_succeeds(self, mock_get):
        mock_get.side_effect = [
            requests.ConnectionError("network down"),
            _make_response(200, SAMPLE_PAYLOAD),
        ]

        result = fetch_raw_astros(url="http://fake-url")

        assert result == SAMPLE_PAYLOAD
        assert mock_get.call_count == 2

    @patch("loader.api.api.requests.get")
    def test_does_not_retry_on_success(self, mock_get):
        mock_get.return_value = _make_response(200, SAMPLE_PAYLOAD)

        fetch_raw_astros(url="http://fake-url")

        assert mock_get.call_count == 1


class TestFetchRawAstrosExhaustedRetries:
    @patch("loader.api.api.requests.get")
    def test_raises_fetch_error_after_max_attempts_all_429(self, mock_get):
        mock_get.return_value = _make_response(429)

        with pytest.raises(FetchError):
            fetch_raw_astros(url="http://fake-url")

        assert mock_get.call_count == settings.api_settings.max_retries

    @patch("loader.api.api.requests.get")
    def test_raises_fetch_error_after_max_attempts_connection_errors(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("network down")

        with pytest.raises(FetchError):
            fetch_raw_astros(url="http://fake-url")

        assert mock_get.call_count == settings.api_settings.max_retries

    @patch("loader.api.api.requests.get")
    def test_original_exception_is_chained(self, mock_get):
        mock_get.return_value = _make_response(429)

        with pytest.raises(FetchError) as exc_info:
            fetch_raw_astros(url="http://fake-url")

        assert exc_info.value.__cause__ is not None


class TestRetryConfiguration:

    def test_stop_after_configured_max_retries(self):
        assert _get.retry.stop.max_attempt_number == settings.api_settings.max_retries

    def test_wait_strategy_is_exponential_with_expected_bounds(self):
        wait = _get.retry.wait
        assert wait.multiplier == 1
        assert wait.min == 1
        assert wait.max == 32
