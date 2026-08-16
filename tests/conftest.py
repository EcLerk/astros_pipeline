import os

import pytest

os.environ.setdefault("API__URL", "http://api.open-notify.org/astros.json")
os.environ.setdefault("API__MAX_RETRIES", "5")
os.environ.setdefault("CLICKHOUSE__HOST", "localhost")
os.environ.setdefault("CLICKHOUSE__PORT", "8123")
os.environ.setdefault("CLICKHOUSE__USER", "default")
os.environ.setdefault("CLICKHOUSE__PASSWORD", "password")
os.environ.setdefault("CLICKHOUSE__DB", "astros_db")


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_args, **_kwargs: None)
