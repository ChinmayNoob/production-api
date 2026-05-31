from dotenv import load_dotenv
load_dotenv()

from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    openai_api_key: str
    primary_model: str = "gpt-4o-mini"
    fallback_model: str = "gpt-4o-mini"

    langchain_tracing_v2: bool = True
    langchain_project: str = "prodapp"
    
    app_env: str = "development"
    log_level: str = "INFO"
    rate_limit: str = "20/minute"
    cache_ttl_seconds: int = 300
    max_retries: int = 3

    model_config = {"env_file": ".env","extra": "ignore"}

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"
    

@lru_cache()
def get_settings() -> Settings:
    """Get the application settings, cached for performance."""
    return Settings()

