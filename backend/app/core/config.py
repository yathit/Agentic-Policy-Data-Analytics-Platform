"""Application configuration."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    app_name: str = "IMDA Policy Analytics API"
    debug: bool = True

    # Database
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "policy_analytics"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0

    # data.gov.sg ingest settings
    data_gov_sg_ingest_weekly_cron: str = "0 2 * * 0"  # Sunday 02:00
    data_gov_sg_ingest_tz: str = "Asia/Singapore"
    data_gov_sg_ingest_startup_if_empty: bool = True

    @property
    def database_url(self) -> str:
        """Construct database URL."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        """Construct Redis URL."""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
