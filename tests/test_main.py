from unittest.mock import MagicMock, patch

import pytest

from loader.api.exceptions import FetchError
from loader.main import run


class TestRunHappyPath:
    @patch("loader.main.insert_astros_raw")
    @patch("loader.main.get_clickhouse_client")
    @patch("loader.main.fetch_raw_astros")
    def test_fetches_creates_client_and_inserts_in_order(
        self, mock_fetch, mock_get_client, mock_insert
    ):
        mock_fetch.return_value = '{"people": []}'
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        run()

        mock_fetch.assert_called_once()
        mock_get_client.assert_called_once()
        mock_insert.assert_called_once_with(mock_client, '{"people": []}')


class TestRunFetchFailure:
    @patch("loader.main.get_clickhouse_client")
    @patch("loader.main.fetch_raw_astros")
    def test_propagates_fetch_error_and_skips_clickhouse(
        self, mock_fetch, mock_get_client
    ):
        mock_fetch.side_effect = FetchError("all retries exhausted")

        with pytest.raises(FetchError):
            run()

        mock_get_client.assert_not_called()
