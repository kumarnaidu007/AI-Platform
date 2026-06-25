from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql://aidev:aidev_local@localhost:5432/ai_dev_platform"
    redis_url: str = "redis://localhost:6379/0"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    secret_key: str = "change-me-in-production"
    web_base_url: str = "http://localhost:5180"
    api_public_url: str = "http://localhost:8000"
    teams_mock_mode: bool = False
    teams_tenant_id: str = "common"
    teams_client_id: str = ""
    teams_client_secret: str = ""


settings = Settings()
