from unittest.mock import MagicMock, patch

from loader.clickhouse_client import get_clickhouse_client, insert_astros_raw
from loader.settings import Settings


class TestGetClickhouseClient:
    @patch("loader.clickhouse_client.clickhouse_connect.get_client")
    def test_builds_client_with_settings_values(self, mock_get_client):
        settings = Settings()
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        client = get_clickhouse_client(settings)

        mock_get_client.assert_called_once_with(
            host=settings.clickhouse_settings.host,
            port=settings.clickhouse_settings.port,
            username=settings.clickhouse_settings.user,
            password=settings.clickhouse_settings.password,
            database=settings.clickhouse_settings.db,
        )
        assert client is mock_client


class TestInsertAstrosRaw:
    def test_inserts_payload_as_single_row_into_astros_raw(self):
        mock_client = MagicMock()
        payload = '{"people": [], "number": 0, "message": "success"}'

        insert_astros_raw(mock_client, payload)

        mock_client.insert.assert_called_once_with(
            "astros_raw",
            [[payload]],
            column_names=["payload"],
        )

    def test_only_calls_insert_no_other_client_methods(self):
        mock_client = MagicMock()

        insert_astros_raw(mock_client, "{}")

        called_methods = [call[0] for call in mock_client.method_calls]
        assert called_methods == ["insert"]
