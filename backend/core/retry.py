"""
Retry decorator with exponential backoff for handling transient failures.

Used for API calls that may fail due to network issues, rate limiting, etc.
"""

import time
import logging
from functools import wraps
from typing import Callable, TypeVar, Any

logger = logging.getLogger(__name__)

# Type variable for generic function
F = TypeVar('F', bound=Callable[..., Any])


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (ConnectionError, TimeoutError)
):
    """
    Decorator для retry с exponential backoff.
    
    Args:
        max_attempts: Максимальное количество попыток
        initial_delay: Начальная задержка в секундах
        backoff_factor: Множитель для увеличения задержки
        exceptions: Tuple исключений, при которых делать retry
    
    Example:
        @retry_with_backoff(max_attempts=3, initial_delay=1.0)
        def fetch_data():
            return requests.get(url, timeout=10)
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts:
                        logger.warning(
                            f"Attempt {attempt}/{max_attempts} failed, retrying in {delay:.1f}s",
                            extra={
                                'function': func.__name__,
                                'attempt': attempt,
                                'max_attempts': max_attempts,
                                'delay': delay,
                                'error': str(e),
                                'error_type': type(e).__name__
                            }
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}",
                            extra={
                                'function': func.__name__,
                                'error': str(e),
                                'error_type': type(e).__name__
                            }
                        )
                        raise
                        
                except Exception as e:
                    # Не повторяем для других типов ошибок
                    logger.error(
                        f"Non-retryable error in {func.__name__}",
                        extra={
                            'function': func.__name__,
                            'error': str(e),
                            'error_type': type(e).__name__
                        }
                    )
                    raise
                    
            # Raise last exception if all retries failed
            if last_exception:
                raise last_exception
                
        return wrapper  # type: ignore
    return decorator


class RetryableError(Exception):
    """
    Base exception для ошибок, которые можно повторить.
    """
    pass


class RateLimitError(RetryableError):
    """
    Превышен rate limit API.
    """
    pass


class NetworkError(RetryableError):
    """
    Сетевая ошибка.
    """
    pass
