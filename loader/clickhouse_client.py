import clickhouse_connect
from clickhouse_connect.driver import Client

from loader.settings import Settings


def get_clickhouse_client(settings: Settings) -> Client:
    return clickhouse_connect.get_client(
        host=settings.clickhouse_settings.host,
        port=settings.clickhouse_settings.port,
        username=settings.clickhouse_settings.user,
        password=settings.clickhouse_settings.password,
        database=settings.clickhouse_settings.db,
    )


def insert_astros_raw(client: Client, payload: str) -> None:
    client.insert(
        "astros_raw",
        [[payload]],
        column_names=["payload"],
    )

