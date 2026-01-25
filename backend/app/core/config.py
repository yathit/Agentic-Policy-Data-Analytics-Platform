from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    app_name: str = "IMDA Agentic Policy Analytics"
    app_version: str = "0.1.0"
    environment: str = "development"
    
    # Database
    database_url: str = "postgresql://user:password@postgres:5432/imda_policy"
    
    # Redis
    redis_url: str = "redis://redis:6379/0"
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    class Config:
        env_file = ".env"


settings = Settings()
