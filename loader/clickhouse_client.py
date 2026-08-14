import clickhouse_connect
from clickhouse_connect.driver import Client

from loader.settings import Settings


def get_clickhouse_client(settings: Settings) -> Client:
    return clickhouse_connect.get_client(
        host=settings.clickhouse_settings.host,
        port=settings.clickhouse_settings.port,
        username=settings.clickhouse_settings.username,
        password=settings.clickhouse_settings.password,
        database=settings.clickhouse_settings.database,
    )


def insert_raw_astros(client: Client, data: dict) -> None:
    client.insert(
        "raw_astros",
        [[data]],
        column_names=["data"],
    )

