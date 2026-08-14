from pydantic_settings import BaseSettings, SettingsConfigDict


class ClickhouseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CLICKHOUSE__", env_file=".env")

    host: str = None
    port: int = None
    database: str = None
    user: str = None
    password: str = None


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="API__", env_file=".env")

    url: str
    max_retries: int


class Settings(BaseSettings):
    clickhouse_settings: ClickhouseSettings = ClickhouseSettings()
    api_settings: ApiSettings = ApiSettings()


settings = Settings()
