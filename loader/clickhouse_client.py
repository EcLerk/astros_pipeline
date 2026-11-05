import logging

import clickhouse_connect
from clickhouse_connect.driver import Client
from clickhouse_connect.driver.exceptions import OperationalError
from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from loader.settings import Settings

logger = logging.getLogger(__name__)


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


def _insert_with_fresh_client(settings: Settings, payload: str) -> None:
    with get_clickhouse_client(settings) as client:
        insert_astros_raw(client, payload)


def load_astros_raw(settings: Settings, payload: str) -> None:
    """Insert the raw API payload into ``astros_raw``, retrying on transport errors.

    Each attempt builds a new client (re-running the driver's connect/handshake) and
    closes it afterwards, whether it succeeded or failed; HTTP connections themselves
    come from the driver's shared pool. Only ``OperationalError`` (connection/transport
    failures) is retried, with exponential backoff, for at most
    ``settings.clickhouse_settings.max_retries`` total attempts. Any other error is
    raised immediately without retry.

    Delivery is at-least-once: a retried insert may duplicate a row the server had
    already accepted; duplicates are absorbed downstream by the ``stg_people`` dedup
    in dbt.

    Raises:
        OperationalError: the original error from the last attempt, once all attempts
            are exhausted.
        clickhouse_connect.driver.exceptions.Error: any non-retryable driver error,
            raised from the first attempt that hits it.
    """
    max_attempts = settings.clickhouse_settings.max_retries
    retrying = Retrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=32),
        retry=retry_if_exception_type(OperationalError),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    try:
        retrying(_insert_with_fresh_client, settings, payload)
    except OperationalError:
        logger.error("Failed to insert into astros_raw after %d attempts", max_attempts)
        raise
