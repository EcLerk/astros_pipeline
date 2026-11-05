import logging
from unittest.mock import MagicMock, patch

import pytest
from clickhouse_connect.driver.exceptions import (
    DatabaseError,
    DataError,
    OperationalError,
    ProgrammingError,
)

from loader.clickhouse_client import get_clickhouse_client, insert_astros_raw, load_astros_raw
from loader.settings import ClickhouseSettings, Settings

PAYLOAD = '{"people": [], "number": 0, "message": "success"}'
CLIENT_LOGGER = "loader.clickhouse_client"


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


class FakeClient:
    """Minimal stand-in for the driver ``Client``: records every method called on it.

    Only the methods the loader is allowed to use exist, so any other call fails with
    ``AttributeError`` instead of passing silently like a ``MagicMock`` would.
    """

    def __init__(self, insert_error: Exception | None = None) -> None:
        self.insert_error = insert_error
        self.calls: list[str] = []
        self.inserted_rows: list[tuple] = []

    def insert(self, table, data, column_names=None) -> None:
        self.calls.append("insert")
        if self.insert_error is not None:
            raise self.insert_error
        self.inserted_rows.append((table, data, column_names))

    def close(self) -> None:
        self.calls.append("close")

    def __enter__(self) -> "FakeClient":
        self.calls.append("__enter__")
        return self

    def __exit__(self, *exc_info) -> None:
        self.calls.append("__exit__")
        self.close()

    @property
    def close_count(self) -> int:
        return self.calls.count("close")


class FakeClickhouseServer:
    """Replaces ``clickhouse_connect.get_client``; fails attempts from scripted error queues.

    ``connect_errors`` are raised by successive ``get_client`` calls; ``insert_errors`` are
    handed to successive created clients. Once a queue is empty, that step succeeds.
    """

    def __init__(self, connect_errors=(), insert_errors=()) -> None:
        self._connect_errors = list(connect_errors)
        self._insert_errors = list(insert_errors)
        self.connect_attempts = 0
        self.clients: list[FakeClient] = []

    def get_client(self, **_connection_kwargs) -> FakeClient:
        self.connect_attempts += 1
        if self._connect_errors:
            raise self._connect_errors.pop(0)
        insert_error = self._insert_errors.pop(0) if self._insert_errors else None
        client = FakeClient(insert_error=insert_error)
        self.clients.append(client)
        return client

    @property
    def inserted_rows(self) -> list[tuple]:
        return [row for client in self.clients for row in client.inserted_rows]


def make_settings(max_retries: int) -> Settings:
    return Settings(
        clickhouse_settings=ClickhouseSettings(
            host="clickhouse-test",
            port=8123,
            db="astros_test",
            user="test-user",
            password="test-pass",
            max_retries=max_retries,
        )
    )


def install_server(monkeypatch, server: FakeClickhouseServer) -> FakeClickhouseServer:
    monkeypatch.setattr("loader.clickhouse_client.clickhouse_connect.get_client", server.get_client)
    return server


@pytest.fixture
def sleeps(monkeypatch) -> list[float]:
    recorded: list[float] = []
    monkeypatch.setattr("time.sleep", recorded.append)
    return recorded


def client_records(caplog, level: int) -> list[logging.LogRecord]:
    return [
        record
        for record in caplog.records
        if record.name == CLIENT_LOGGER and record.levelno == level
    ]


def error_records(caplog) -> list[logging.LogRecord]:
    return client_records(caplog, logging.ERROR)


EXPECTED_ROW = ("astros_raw", [[PAYLOAD]], ["payload"])

NON_RETRYABLE_ERRORS = [
    pytest.param(lambda: DatabaseError("authentication failed", code=516), id="database-error-516"),
    pytest.param(lambda: DataError("bad value"), id="data-error"),
    pytest.param(lambda: ProgrammingError("unknown table"), id="programming-error"),
]


class TestLoadAstrosRaw:
    def test_success_uses_one_client_one_insert_and_closes_it(self, monkeypatch, sleeps):
        server = install_server(monkeypatch, FakeClickhouseServer())

        load_astros_raw(make_settings(max_retries=3), PAYLOAD)

        assert server.connect_attempts == 1
        assert server.inserted_rows == [EXPECTED_ROW]
        assert server.clients[0].close_count == 1
        assert sleeps == []

    def test_retries_when_client_creation_fails_transiently(self, monkeypatch, sleeps):
        server = install_server(
            monkeypatch, FakeClickhouseServer(connect_errors=[OperationalError("refused")])
        )

        load_astros_raw(make_settings(max_retries=3), PAYLOAD)

        assert server.connect_attempts == 2
        assert server.inserted_rows == [EXPECTED_ROW]
        assert [client.close_count for client in server.clients] == [1]
        assert len(sleeps) == 1

    def test_retries_when_insert_fails_transiently(self, monkeypatch, sleeps):
        server = install_server(
            monkeypatch, FakeClickhouseServer(insert_errors=[OperationalError("reset")])
        )

        load_astros_raw(make_settings(max_retries=3), PAYLOAD)

        assert server.connect_attempts == 2
        assert server.inserted_rows == [EXPECTED_ROW]
        assert [client.close_count for client in server.clients] == [1, 1]
        assert len(sleeps) == 1

    @pytest.mark.parametrize(
        ("max_retries", "expected_sleeps"),
        [
            pytest.param(1, [], id="single-attempt-no-backoff"),
            pytest.param(2, [1], id="two-attempts"),
            pytest.param(3, [1, 2], id="three-attempts"),
            pytest.param(4, [1, 2, 4], id="four-attempts"),
            pytest.param(8, [1, 2, 4, 8, 16, 32, 32], id="backoff-capped-at-32s"),
        ],
    )
    def test_exhausted_retries_reraise_last_original_error_and_log_once(
        self, monkeypatch, sleeps, caplog, max_retries, expected_sleeps
    ):
        errors = [OperationalError(f"down #{n}") for n in range(10)]
        server = install_server(monkeypatch, FakeClickhouseServer(insert_errors=errors))

        with caplog.at_level(logging.WARNING, logger=CLIENT_LOGGER):
            with pytest.raises(OperationalError) as exc_info:
                load_astros_raw(make_settings(max_retries=max_retries), PAYLOAD)

        assert exc_info.value is errors[max_retries - 1]
        assert server.connect_attempts == max_retries
        assert [client.close_count for client in server.clients] == [1] * max_retries
        assert server.inserted_rows == []
        assert sleeps == expected_sleeps
        assert len(client_records(caplog, logging.WARNING)) == max_retries - 1
        [record] = error_records(caplog)
        assert f"{max_retries} attempts" in record.getMessage()
        assert record.exc_info is None

    def test_exhausted_retries_on_client_creation_reraise_last_original_error(
        self, monkeypatch, sleeps
    ):
        errors = [OperationalError(f"refused #{n}") for n in range(3)]
        server = install_server(monkeypatch, FakeClickhouseServer(connect_errors=errors))

        with pytest.raises(OperationalError) as exc_info:
            load_astros_raw(make_settings(max_retries=3), PAYLOAD)

        assert exc_info.value is errors[-1]
        assert server.connect_attempts == 3
        assert server.clients == []
        assert sleeps == [1, 2]

    @pytest.mark.parametrize("make_error", NON_RETRYABLE_ERRORS)
    def test_non_retryable_insert_error_fails_after_one_attempt(
        self, monkeypatch, sleeps, caplog, make_error
    ):
        error = make_error()
        server = install_server(monkeypatch, FakeClickhouseServer(insert_errors=[error]))

        with caplog.at_level(logging.WARNING, logger=CLIENT_LOGGER):
            with pytest.raises(type(error)) as exc_info:
                load_astros_raw(make_settings(max_retries=3), PAYLOAD)

        assert exc_info.value is error
        assert server.connect_attempts == 1
        assert [client.close_count for client in server.clients] == [1]
        assert sleeps == []
        assert error_records(caplog) == []

    @pytest.mark.parametrize("make_error", NON_RETRYABLE_ERRORS)
    def test_non_retryable_client_creation_error_fails_after_one_attempt(
        self, monkeypatch, sleeps, caplog, make_error
    ):
        error = make_error()
        server = install_server(monkeypatch, FakeClickhouseServer(connect_errors=[error]))

        with caplog.at_level(logging.WARNING, logger=CLIENT_LOGGER):
            with pytest.raises(type(error)) as exc_info:
                load_astros_raw(make_settings(max_retries=3), PAYLOAD)

        assert exc_info.value is error
        assert server.connect_attempts == 1
        assert server.clients == []
        assert sleeps == []
        assert error_records(caplog) == []

    def test_client_is_used_for_insert_only(self, monkeypatch):
        server = install_server(monkeypatch, FakeClickhouseServer())

        load_astros_raw(make_settings(max_retries=3), PAYLOAD)

        public_calls = [call for call in server.clients[0].calls if not call.startswith("__")]
        assert public_calls == ["insert", "close"]
