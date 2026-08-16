import logging

from loader.api.api import fetch_raw_astros
from loader.api.exceptions import FetchError
from loader.clickhouse_client import get_clickhouse_client, insert_astros_raw
from loader.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run() -> None:
    try:
        payload = fetch_raw_astros(url=settings.api_settings.url)
    except FetchError:
        logger.exception("Failed to download data after all retry attempts")
        raise

    client = get_clickhouse_client(settings)
    insert_astros_raw(client, payload)
    logger.info("Done: raw data loaded into astros_raw")


if __name__ == "__main__":
    run()
