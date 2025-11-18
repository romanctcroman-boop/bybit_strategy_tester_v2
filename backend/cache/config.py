"""
Cache Configuration Settings

Provides environment-based configuration for cache system using Pydantic Settings.

Features:
- L1 (in-memory) cache configuration
- L2 (Redis) cache configuration
- Feature flags (enable_l1, enable_l2, enable_metrics)
- Environment-specific defaults (dev, staging, prod)
- Validation with Pydantic

Usage:
    from backend.cache.config import get_cache_settings
    
    settings = get_cache_settings()
    print(f"L1 size: {settings.l1_size}")
    print(f"L2 enabled: {settings.enable_l2}")

Environment Variables:
    CACHE_L1_SIZE=1000
    CACHE_L1_TTL=300
    CACHE_L2_TTL=3600
    CACHE_ENABLE_L1=true
    CACHE_ENABLE_L2=true
    CACHE_ENABLE_METRICS=true
    CACHE_ENABLE_ETAG=true
    ENV=production
"""

from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CacheSettings(BaseSettings):
    """
    Cache system configuration settings.
    
    Loads configuration from environment variables with CACHE_ prefix.
    Provides sensible defaults for different environments.
    """
    
    # ========================================================================
    # L1 Cache (In-Memory) Configuration
    # ========================================================================
    
    l1_size: int = Field(
        default=1000,
        ge=10,
        le=100000,
        description="L1 cache maximum size (number of items)"
    )
    
    l1_ttl: int = Field(
        default=300,
        ge=10,
        le=86400,
        description="L1 cache TTL in seconds (default: 5 minutes)"
    )
    
    # ========================================================================
    # L2 Cache (Redis) Configuration
    # ========================================================================
    
    l2_ttl: int = Field(
        default=3600,
        ge=60,
        le=604800,
        description="L2 cache TTL in seconds (default: 1 hour)"
    )
    
    l2_redis_url: Optional[str] = Field(
        default=None,
        description="Redis URL for L2 cache (e.g., redis://localhost:6379/0)"
    )
    
    l2_connection_timeout: int = Field(
        default=5,
        ge=1,
        le=30,
        description="L2 Redis connection timeout in seconds"
    )
    
    l2_operation_timeout: int = Field(
        default=2,
        ge=1,
        le=10,
        description="L2 Redis operation timeout in seconds"
    )
    
    # ========================================================================
    # Feature Flags
    # ========================================================================
    
    enable_l1: bool = Field(
        default=True,
        description="Enable L1 (in-memory) cache"
    )
    
    enable_l2: bool = Field(
        default=True,
        description="Enable L2 (Redis) cache"
    )
    
    enable_metrics: bool = Field(
        default=True,
        description="Enable Prometheus metrics collection"
    )
    
    enable_etag: bool = Field(
        default=True,
        description="Enable HTTP ETag cache headers"
    )
    
    enable_cache_warming: bool = Field(
        default=False,
        description="Enable automatic cache warming on startup"
    )
    
    # ========================================================================
    # HTTP Cache Headers Configuration
    # ========================================================================
    
    http_cache_max_age: int = Field(
        default=60,
        ge=0,
        le=86400,
        description="HTTP Cache-Control max-age in seconds"
    )
    
    # ========================================================================
    # Environment Configuration
    # ========================================================================
    
    env: Literal['development', 'staging', 'production'] = Field(
        default='development',
        description="Application environment"
    )
    
    # ========================================================================
    # Pydantic Settings Configuration
    # ========================================================================
    
    model_config = SettingsConfigDict(
        env_prefix='CACHE_',  # All env vars start with CACHE_
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )
    
    # ========================================================================
    # Validators
    # ========================================================================
    
    @field_validator('l1_size')
    @classmethod
    def validate_l1_size(cls, v: int) -> int:
        """Validate L1 cache size is reasonable."""
        if v < 10:
            raise ValueError('L1 size must be at least 10')
        if v > 100000:
            raise ValueError('L1 size too large (max 100000)')
        return v
    
    @field_validator('l1_ttl', 'l2_ttl')
    @classmethod
    def validate_ttl(cls, v: int) -> int:
        """Validate TTL values are reasonable."""
        if v < 10:
            raise ValueError('TTL must be at least 10 seconds')
        if v > 604800:  # 1 week
            raise ValueError('TTL too large (max 1 week)')
        return v
    
    @field_validator('env')
    @classmethod
    def adjust_for_environment(cls, v: str, info) -> str:
        """Adjust defaults based on environment."""
        # Note: This is called during initialization
        # Actual adjustment happens in model_post_init
        return v
    
    def model_post_init(self, __context) -> None:
        """Adjust settings based on environment after initialization."""
        if self.env == 'production':
            # Production: aggressive caching
            if self.l1_size == 1000:  # Default
                self.l1_size = 5000
            if self.l1_ttl == 300:  # Default
                self.l1_ttl = 600  # 10 minutes
            if self.l2_ttl == 3600:  # Default
                self.l2_ttl = 7200  # 2 hours
        
        elif self.env == 'development':
            # Development: shorter TTLs for faster iteration
            if self.l1_ttl == 300:  # Default
                self.l1_ttl = 60  # 1 minute
            if self.l2_ttl == 3600:  # Default
                self.l2_ttl = 300  # 5 minutes
            # Disable L2 in dev by default if not explicitly set
            # (check if it was explicitly set via env var)
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def get_cache_config(self) -> dict:
        """
        Get cache configuration as dictionary.
        
        Returns:
            Dictionary with all cache settings
        """
        return {
            'l1': {
                'enabled': self.enable_l1,
                'size': self.l1_size,
                'ttl': self.l1_ttl,
            },
            'l2': {
                'enabled': self.enable_l2,
                'ttl': self.l2_ttl,
                'redis_url': self.l2_redis_url,
                'connection_timeout': self.l2_connection_timeout,
                'operation_timeout': self.l2_operation_timeout,
            },
            'features': {
                'metrics': self.enable_metrics,
                'etag': self.enable_etag,
                'cache_warming': self.enable_cache_warming,
            },
            'http': {
                'max_age': self.http_cache_max_age,
            },
            'environment': self.env,
        }
    
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.env == 'production'
    
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.env == 'development'
    
    def is_staging(self) -> bool:
        """Check if running in staging."""
        return self.env == 'staging'


@lru_cache()
def get_cache_settings() -> CacheSettings:
    """
    Get cache settings singleton.
    
    Uses lru_cache to ensure settings are loaded only once.
    
    Returns:
        CacheSettings instance
        
    Example:
        >>> settings = get_cache_settings()
        >>> print(f"L1 size: {settings.l1_size}")
        L1 size: 1000
    """
    return CacheSettings()


# Global settings instance
cache_settings = get_cache_settings()
