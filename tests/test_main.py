from unittest.mock import patch

import pytest
from clickhouse_connect.driver.exceptions import OperationalError

from loader.api.exceptions import FetchError
from loader.main import run
from loader.settings import settings


class TestRunHappyPath:
    @patch("loader.main.load_astros_raw")
    @patch("loader.main.fetch_raw_astros")
    def test_fetches_then_loads_payload_into_clickhouse(self, mock_fetch, mock_load):
        mock_fetch.return_value = '{"people": []}'

        run()

        mock_fetch.assert_called_once()
        mock_load.assert_called_once_with(settings, '{"people": []}')


class TestRunFetchFailure:
    @patch("loader.main.load_astros_raw")
    @patch("loader.main.fetch_raw_astros")
    def test_propagates_fetch_error_and_skips_clickhouse(self, mock_fetch, mock_load):
        mock_fetch.side_effect = FetchError("all retries exhausted")

        with pytest.raises(FetchError):
            run()

        mock_load.assert_not_called()


class TestRunLoadFailure:
    @patch("loader.main.load_astros_raw")
    @patch("loader.main.fetch_raw_astros")
    def test_propagates_clickhouse_error_uncaught(self, mock_fetch, mock_load):
        mock_fetch.return_value = '{"people": []}'
        error = OperationalError("clickhouse unreachable")
        mock_load.side_effect = error

        with pytest.raises(OperationalError) as exc_info:
            run()

        assert exc_info.value is error
