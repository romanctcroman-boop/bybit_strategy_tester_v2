"""
Logging Middleware - Automatic request/response logging with sanitization
"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message

from backend.security.secure_logger import api_logger


class SecureLoggingMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for automatic request/response logging.
    
    Features:
    - Logs all HTTP requests/responses
    - Automatic sensitive data sanitization
    - Request/response correlation IDs
    - Performance timing
    - Error tracking
    """
    
    # Paths to exclude from logging (too noisy)
    EXCLUDE_PATHS = {
        '/health',
        '/metrics',
        '/favicon.ico'
    }
    
    # Headers to log (excluding sensitive ones)
    LOG_HEADERS = {
        'content-type',
        'content-length',
        'user-agent',
        'accept',
        'accept-language'
    }
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Process request and response"""
        
        # Skip excluded paths
        if request.url.path in self.EXCLUDE_PATHS:
            return await call_next(request)
        
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        
        # Set context for all logs in this request
        api_logger.set_context(
            correlation_id=correlation_id,
            request_id=correlation_id
        )
        
        # Extract request info
        start_time = time.time()
        
        request_info = {
            'method': request.method,
            'path': request.url.path,
            'query_params': dict(request.query_params),
            'headers': self._filter_headers(request.headers),
            'client_host': request.client.host if request.client else None,
        }
        
        # Log request
        api_logger.info(
            f"Request: {request.method} {request.url.path}",
            **request_info
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log response
            response_info = {
                'status_code': response.status_code,
                'duration_ms': round(duration_ms, 2),
            }
            
            # Determine log level based on status code
            if response.status_code >= 500:
                api_logger.error(
                    f"Response: {request.method} {request.url.path} - {response.status_code}",
                    **response_info
                )
            elif response.status_code >= 400:
                api_logger.warning(
                    f"Response: {request.method} {request.url.path} - {response.status_code}",
                    **response_info
                )
            else:
                api_logger.info(
                    f"Response: {request.method} {request.url.path} - {response.status_code}",
                    **response_info
                )
            
            # Add correlation ID to response headers
            response.headers['X-Correlation-ID'] = correlation_id
            
            return response
            
        except Exception as e:
            # Log exception
            duration_ms = (time.time() - start_time) * 1000
            
            api_logger.error(
                f"Exception: {request.method} {request.url.path}",
                exception=str(e),
                exception_type=type(e).__name__,
                duration_ms=round(duration_ms, 2)
            )
            
            raise
        
        finally:
            # Clear request context
            api_logger.clear_context()
    
    def _filter_headers(self, headers) -> dict:
        """Filter headers to log (remove sensitive ones)"""
        return {
            key: value
            for key, value in headers.items()
            if key.lower() in self.LOG_HEADERS
        }


class SecurityEventMiddleware(BaseHTTPMiddleware):
    """
    Middleware for tracking security events.
    
    Logs:
    - Failed authentication attempts
    - Suspicious patterns
    - Rate limit hits
    - Authorization failures
    """
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Track security events"""
        
        response = await call_next(request)
        
        # Track failed authentication
        if response.status_code == 401:
            api_logger.security_event(
                event_type='authentication_failure',
                severity='medium',
                user_id=getattr(request.state, 'user_id', None),
                path=request.url.path,
                method=request.method,
                client_host=request.client.host if request.client else None
            )
        
        # Track authorization failures
        elif response.status_code == 403:
            api_logger.security_event(
                event_type='authorization_failure',
                severity='medium',
                user_id=getattr(request.state, 'user_id', None),
                path=request.url.path,
                method=request.method,
                client_host=request.client.host if request.client else None
            )
        
        # Track rate limit hits
        elif response.status_code == 429:
            api_logger.security_event(
                event_type='rate_limit_exceeded',
                severity='low',
                user_id=getattr(request.state, 'user_id', None),
                path=request.url.path,
                method=request.method,
                client_host=request.client.host if request.client else None
            )
        
        return response
