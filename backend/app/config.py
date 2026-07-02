from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://scheduler:scheduler@localhost:5432/scheduler"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    # Worker tuning
    worker_poll_interval_seconds: float = 1.0
    worker_heartbeat_interval_seconds: float = 5.0
    worker_heartbeat_timeout_seconds: int = 30
    worker_default_concurrency: int = 4

    # Scheduler tuning
    scheduler_poll_interval_seconds: float = 1.0

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


settings = Settings()
