"""
Health check endpoints for monitoring service health.

Provides endpoints to check:
- Overall service health
- Bybit API connectivity
- Database connectivity
- Redis connectivity (if enabled)
- Cache availability
- Prometheus metrics
"""

from fastapi import APIRouter, HTTPException, status, Response
from datetime import datetime
import time
from typing import Dict, Any
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from backend.core.config import get_config
from backend.core.logging_config import get_logger

router = APIRouter(prefix="/health", tags=["health"])
logger = get_logger(__name__)
config = get_config()


@router.get("", response_model=Dict[str, Any])
async def health_check():
    """
    Overall health check.
    
    Returns:
        Health status of all components
    
    Status Codes:
        200: All components healthy
        503: One or more components unhealthy
    """
    checks = {}
    overall_status = "healthy"
    
    # 1. Check Bybit API
    try:
        from backend.services.adapters.bybit import BybitAdapter
        
        adapter = BybitAdapter()
        start = time.time()
        candles = adapter.get_klines('BTCUSDT', '1', 10)
        duration_ms = (time.time() - start) * 1000
        
        checks['bybit_api'] = {
            'status': 'ok' if len(candles) > 0 else 'degraded',
            'response_time_ms': round(duration_ms, 2),
            'candles_fetched': len(candles),
            'message': f'Fetched {len(candles)} candles in {duration_ms:.2f}ms'
        }
        
        if len(candles) == 0:
            overall_status = "degraded"
            
    except Exception as e:
        checks['bybit_api'] = {
            'status': 'error',
            'error': str(e),
            'error_type': type(e).__name__
        }
        overall_status = "unhealthy"
        logger.error("Bybit API health check failed", extra={'error': str(e)})
    
    # 2. Check PostgreSQL
    try:
        from backend.database import SessionLocal
        
        session = SessionLocal()
        try:
            session.execute("SELECT 1")
            checks['database'] = {
                'status': 'ok',
                'message': 'Database connection successful'
            }
        finally:
            session.close()
            
    except Exception as e:
        checks['database'] = {
            'status': 'error',
            'error': str(e),
            'error_type': type(e).__name__
        }
        overall_status = "unhealthy"
        logger.error("Database health check failed", extra={'error': str(e)})
    
    # 3. Check cache directory
    import os
    cache_dir = config.CACHE_DIR
    
    try:
        if os.path.exists(cache_dir):
            cache_files = len(os.listdir(cache_dir))
            checks['cache'] = {
                'status': 'ok',
                'cache_files': cache_files,
                'cache_dir': cache_dir,
                'message': f'{cache_files} cache files in {cache_dir}'
            }
        else:
            checks['cache'] = {
                'status': 'warning',
                'message': f'Cache directory not found: {cache_dir}'
            }
            if overall_status == "healthy":
                overall_status = "degraded"
                
    except Exception as e:
        checks['cache'] = {
            'status': 'error',
            'error': str(e)
        }
    
    # Build response
    response = {
        'status': overall_status,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'checks': checks,
        'config': {
            'cache_enabled': config.CACHE_ENABLED,
            'db_persist_enabled': config.DB_PERSIST_ENABLED,
            'log_level': config.LOG_LEVEL
        }
    }
    
    # Return 503 if unhealthy
    if overall_status == "unhealthy":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response
        )
    
    return response


@router.get("/bybit", response_model=Dict[str, Any])
async def bybit_health():
    """
    Detailed Bybit API health check.
    
    Tests multiple symbols and intervals to ensure API is working correctly.
    """
    from backend.services.adapters.bybit import BybitAdapter
    
    adapter = BybitAdapter()
    results = {}
    
    # Test symbols
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
    
    for symbol in test_symbols:
        try:
            start = time.time()
            candles = adapter.get_klines(symbol, '1', 10)
            duration_ms = (time.time() - start) * 1000
            
            results[symbol] = {
                'status': 'ok',
                'candles': len(candles),
                'response_time_ms': round(duration_ms, 2),
                'latest_price': float(candles[-1]['close']) if candles else None,
                'latest_time': candles[-1]['open_time'] if candles else None
            }
        except Exception as e:
            results[symbol] = {
                'status': 'error',
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    # Calculate success rate
    successful = sum(1 for r in results.values() if r.get('status') == 'ok')
    total = len(results)
    success_rate = (successful / total) * 100 if total > 0 else 0
    
    return {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'success_rate': round(success_rate, 2),
        'successful': successful,
        'total': total,
        'results': results
    }


@router.get("/ready")
async def readiness_check():
    """
    Kubernetes readiness probe.
    
    Returns 200 if service is ready to accept traffic.
    """
    try:
        from backend.services.adapters.bybit import BybitAdapter
        
        # Quick check - just test API connectivity
        adapter = BybitAdapter()
        candles = adapter.get_klines('BTCUSDT', '1', 1)
        
        if len(candles) > 0:
            return {"status": "ready", "timestamp": datetime.utcnow().isoformat() + 'Z'}
        else:
            raise HTTPException(
                status_code=503,
                detail="Bybit API not responding with data"
            )
            
    except Exception as e:
        logger.error("Readiness check failed", extra={'error': str(e)})
        raise HTTPException(
            status_code=503,
            detail=f"Service not ready: {str(e)}"
        )


@router.get("/live")
async def liveness_check():
    """
    Kubernetes liveness probe.
    
    Returns 200 if service is alive (even if degraded).
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat() + 'Z'
    }


@router.get("/metrics")
async def metrics_endpoint():
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus format for scraping.
    
    Metrics include:
    - bybit_api_requests_total: Total API requests by symbol/interval/status
    - bybit_api_duration_seconds: API request latencies
    - bybit_cache_operations_total: Cache hit/miss rates
    - bybit_candles_fetched_total: Candles fetched from API/cache
    - bybit_errors_total: Error counts by type
    - bybit_rate_limit_hits_total: Rate limit violations
    - bybit_historical_fetches_total: Historical fetch operations
    - bybit_adapter_info: Adapter version and configuration
    """
    try:
        metrics_output = generate_latest()
        return Response(
            content=metrics_output,
            media_type=CONTENT_TYPE_LATEST
        )
    except Exception as e:
        logger.error("Failed to generate metrics", extra={'error': str(e)})
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate metrics: {str(e)}"
        )
