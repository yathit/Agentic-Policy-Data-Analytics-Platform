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
    data_gov_sg_api_key: str | None = None

    # Analytics settings - Demo mode: bypass time range filtering
    analytics_bypass_time_filter: bool = True  # Set to True to bypass time range filtering for demo

    # Discovery settings
    discovery_max_candidates: int = 1000  # Max candidates to retrieve across all sources
    discovery_page_size: int = 100  # Batch size for paginated retrieval
    pre_filter_max_candidates: int = 200  # Max candidates to send to LLM ranking

    # LLM ranking settings
    llm_ranking_batch_size: int = 20  # Candidates per LLM ranking call
    llm_ranking_timeout_ms: int = 30000  # Timeout before falling back to deterministic
    llm_ranking_max_parallel: int = 5  # Max concurrent LLM ranking requests

    # Fetch settings
    fetch_max_pages_per_dataset: int = 20  # Max API pages to fetch per dataset

    # Selection settings
    selection_max_total_rows: int = 20000  # Total row budget for selected datasets
    selection_max_rows_per_dataset: int = 5000  # Per-dataset row cap
    row_estimate_default: int = 1000  # Conservative default when estimation unavailable
    selection_row_estimate_max_api_calls: int = 5  # Cap external row-estimation calls during planning

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
