"""
Configuration Management

Loads settings from environment variables and provides
application-wide configuration.
"""

from functools import lru_cache
from typing import Optional

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings
    
    All settings can be overridden via environment variables
    """
    
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"  # Allow extra fields in .env
    )
    
    # API Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RELOAD: bool = True
    
    # Database Settings
    USE_SQLITE: bool = False  # PostgreSQL по умолчанию
    DATABASE_URL: Optional[str] = None
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "bybit_strategy_tester"
    SQLITE_DB_PATH: str = "D:/bybit_strategy_tester_v2/data/bybit_strategy_tester.db"
    
    # Redis Settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    # RabbitMQ Settings
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "bybit"  # Changed from "guest" to match .env
    RABBITMQ_PASS: str = "bybitpassword"  # Changed from "guest" to match .env
    RABBITMQ_VHOST: str = "/"
    
    # Celery Settings
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    
    # Security Settings
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Application Settings
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    
    # Bybit API Settings
    BYBIT_TESTNET: bool = False
    BYBIT_API_KEY: Optional[str] = None
    BYBIT_API_SECRET: Optional[str] = None
    
    @property
    def database_url(self) -> str:
        """Build database connection URL (SQLite or PostgreSQL)"""
        if self.DATABASE_URL:
            return self.DATABASE_URL

        if self.USE_SQLITE:
            return f"sqlite:///{self.SQLITE_DB_PATH}"

        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
    
    @property
    def async_database_url(self) -> str:
        """Build async PostgreSQL connection URL"""
        if self.DATABASE_URL and "+asyncpg" in self.DATABASE_URL:
            return self.DATABASE_URL

        if self.DATABASE_URL:
            return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
    
    @property
    def redis_url(self) -> str:
        """Build Redis connection URL"""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def broker_url(self) -> str:
        """Build RabbitMQ broker URL"""
        if self.CELERY_BROKER_URL:
            return self.CELERY_BROKER_URL
        
        return (
            f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASS}"
            f"@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}//"
        )
    
    @property
    def result_backend_url(self) -> str:
        """Build Celery result backend URL"""
        if self.CELERY_RESULT_BACKEND:
            return self.CELERY_RESULT_BACKEND
        
        return self.redis_url


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    
    Using lru_cache ensures we create only one instance
    """
    return Settings()


# Global settings instance
settings = get_settings()
