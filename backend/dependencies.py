"""
Dependency injection для FastAPI

Управляет жизненным циклом сервисов и их переиспользованием
"""

from functools import lru_cache
from backend.services.bybit_data_loader import BybitDataLoader


# Singleton instance для BybitDataLoader
_bybit_loader_instance = None


@lru_cache()
def get_bybit_loader() -> BybitDataLoader:
    """
    Get or create BybitDataLoader singleton instance
    
    Using @lru_cache() ensures single instance across application lifecycle.
    FastAPI will call this once and reuse the result.
    
    Returns:
        BybitDataLoader instance
        
    Example:
        ```python
        from fastapi import Depends
        from backend.dependencies import get_bybit_loader
        
        @router.get("/data")
        async def load_data(loader: BybitDataLoader = Depends(get_bybit_loader)):
            candles = loader.fetch_klines(...)
            return candles
        ```
    """
    global _bybit_loader_instance
    
    if _bybit_loader_instance is None:
        _bybit_loader_instance = BybitDataLoader(testnet=False)
        
    return _bybit_loader_instance


def reset_bybit_loader():
    """
    Reset singleton instance (for testing purposes)
    
    Call this in tests to get fresh instance:
    ```python
    def test_something():
        reset_bybit_loader()
        loader = get_bybit_loader()
        # ... test code
    ```
    """
    global _bybit_loader_instance
    _bybit_loader_instance = None
    get_bybit_loader.cache_clear()
