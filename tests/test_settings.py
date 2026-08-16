from loader.settings import ApiSettings, ClickhouseSettings


class TestClickhouseSettings:
    def test_reads_values_from_env(self, monkeypatch):
        monkeypatch.setenv("CLICKHOUSE__HOST", "test-host")
        monkeypatch.setenv("CLICKHOUSE__PORT", "1234")
        monkeypatch.setenv("CLICKHOUSE__USER", "test-user")
        monkeypatch.setenv("CLICKHOUSE__PASSWORD", "test-pass")
        monkeypatch.setenv("CLICKHOUSE__DB", "test-db")

        config = ClickhouseSettings()

        assert config.host == "test-host"
        assert config.port == 1234
        assert config.user == "test-user"
        assert config.password == "test-pass"
        assert config.db == "test-db"

    def test_port_is_parsed_as_int(self, monkeypatch):
        monkeypatch.setenv("CLICKHOUSE__PORT", "8123")

        config = ClickhouseSettings()

        assert config.port == 8123
        assert isinstance(config.port, int)


class TestApiSettings:
    def test_reads_url_from_env(self, monkeypatch):
        monkeypatch.setenv("API__URL", "http://example.com/astros.json")

        config = ApiSettings()

        assert config.url == "http://example.com/astros.json"

    def test_max_retries_defaults_to_five_when_unset(self, monkeypatch):
        monkeypatch.delenv("API__MAX_RETRIES", raising=False)

        config = ApiSettings()

        assert config.max_retries == 5

    def test_max_retries_overridable_from_env(self, monkeypatch):
        monkeypatch.setenv("API__MAX_RETRIES", "3")

        config = ApiSettings()

        assert config.max_retries == 3
