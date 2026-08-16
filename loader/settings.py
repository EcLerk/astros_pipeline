from pydantic_settings import BaseSettings, SettingsConfigDict


class ClickhouseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CLICKHOUSE__", env_file=".env")

    host: str = None
    port: int = None
    db: str = None
    user: str = None
    password: str = None


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="API__", env_file=".env")

    url: str = None
    max_retries: int = 5


class Settings(BaseSettings):
    clickhouse_settings: ClickhouseSettings = ClickhouseSettings()
    api_settings: ApiSettings = ApiSettings()


settings = Settings()
