# Edge Cases Documentation

## Comprehensive Guide to Edge Cases Handling in Bybit Strategy Tester

**Version:** 2.0  
**Last Updated:** 2025-11-09  
**Status:** Production Ready

---

## Table of Contents

1. [Data Edge Cases](#1-data-edge-cases)
2. [API Rate Limits](#2-api-rate-limits)
3. [Concurrent Requests](#3-concurrent-requests)
4. [Invalid Strategy Parameters](#4-invalid-strategy-parameters)
5. [Network Failures](#5-network-failures)
6. [Database Edge Cases](#6-database-edge-cases)
7. [MTF Backtest Edge Cases](#7-mtf-backtest-edge-cases)
8. [Testing Edge Cases](#8-testing-edge-cases)

---

## 1. Data Edge Cases

### 1.1 Empty Dataset

**Scenario:** Market data query returns no candles

**Causes:**
- Symbol not available in selected date range
- Weekend/holiday period with no trading
- New listing with insufficient history
- Data provider outage

**Handling:**
```python
# Backend: backend/api/routers/marketdata.py
def get_klines(symbol: str, timeframe: str, start_date: str, end_date: str):
    try:
        candles = fetch_from_bybit(symbol, timeframe, start_date, end_date)
        
        if not candles or len(candles) == 0:
            raise ValidationError(
                message=f"No market data available for {symbol} in specified period",
                field="date_range",
                details={
                    "symbol": symbol,
                    "start_date": start_date,
                    "end_date": end_date,
                    "suggestion": "Try different date range or symbol"
                }
            )
        
        # Minimum data requirement (at least 50 candles)
        if len(candles) < 50:
            logger.warning(f"Insufficient data: {len(candles)} candles for {symbol}")
            raise ValidationError(
                message=f"Insufficient data: {len(candles)} candles (minimum 50 required)",
                field="date_range",
                details={"candles_found": len(candles), "minimum_required": 50}
            )
        
        return candles
        
    except Exception as e:
        logger.error(f"Data fetch failed: {e}")
        raise DataFetchError(
            message="Failed to fetch market data",
            source="Bybit API",
            details={"symbol": symbol, "error": str(e)}
        )
```

**Frontend Handling:**
```typescript
// frontend/src/services/api.ts
try {
  const response = await axios.get('/api/marketdata/klines', { params });
  
  if (response.data.items.length === 0) {
    notify({
      message: 'Нет данных для выбранного периода. Попробуйте другой диапазон дат.',
      type: 'warning'
    });
    return [];
  }
  
  return response.data.items;
  
} catch (error) {
  const apiError = parseApiError(error);
  
  if (apiError.code === 'DATA_FETCH_ERROR') {
    notify({
      message: apiError.message,
      type: 'error',
      duration: 8000
    });
  }
  
  throw apiError;
}
```

### 1.2 Missing OHLCV Fields

**Scenario:** Candle data has null/undefined values

**Validation:**
```python
def validate_candle_data(candles: List[Dict]) -> List[Dict]:
    """Validate and clean candle data"""
    required_fields = ['open', 'high', 'low', 'close', 'volume', 'timestamp']
    cleaned = []
    
    for i, candle in enumerate(candles):
        # Check required fields
        if not all(field in candle for field in required_fields):
            logger.warning(f"Candle {i} missing required fields: {candle}")
            continue
        
        # Check for null/zero values
        if any(candle[f] is None or candle[f] == 0 for f in ['open', 'high', 'low', 'close']):
            logger.warning(f"Candle {i} has invalid OHLC values: {candle}")
            # Fill with previous candle if available
            if cleaned:
                candle = {**cleaned[-1], 'timestamp': candle['timestamp']}
            else:
                continue  # Skip first candle if invalid
        
        # Validate OHLC relationships
        if not (candle['low'] <= candle['open'] <= candle['high'] and
                candle['low'] <= candle['close'] <= candle['high']):
            logger.warning(f"Invalid OHLC relationships in candle {i}")
            continue
        
        cleaned.append(candle)
    
    return cleaned
```

### 1.3 Extreme Price Movements

**Scenario:** Price changes > 50% in single candle (flash crash/spike)

**Detection and Handling:**
```python
def detect_price_anomalies(candles: List[Dict], threshold: float = 0.5) -> List[int]:
    """Detect and flag extreme price movements"""
    anomalies = []
    
    for i in range(1, len(candles)):
        prev_close = candles[i-1]['close']
        curr_open = candles[i]['open']
        
        # Check for gap
        gap_pct = abs(curr_open - prev_close) / prev_close
        if gap_pct > threshold:
            anomalies.append(i)
            logger.warning(f"Price gap detected at index {i}: {gap_pct:.2%}")
        
        # Check intra-candle movement
        range_pct = (candles[i]['high'] - candles[i]['low']) / candles[i]['low']
        if range_pct > threshold:
            anomalies.append(i)
            logger.warning(f"Extreme volatility at index {i}: {range_pct:.2%}")
    
    return anomalies
```

---

## 2. API Rate Limits

### 2.1 Bybit API Limits

**Limits:**
- Public endpoints: 50 requests/second
- Private endpoints: 10 requests/second
- WebSocket: 20 subscriptions per connection

**Rate Limiter Implementation:**
```python
# backend/services/rate_limiter.py
from redis import Redis
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
    
    def check_limit(self, key: str, limit: int, window_seconds: int) -> bool:
        """
        Sliding window rate limiter
        
        Args:
            key: Rate limit key (e.g., "api:bybit:public")
            limit: Maximum requests in window
            window_seconds: Time window in seconds
        
        Returns:
            True if request allowed, False if rate limited
        """
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=window_seconds)
        
        # Remove old entries
        self.redis.zremrangebyscore(key, 0, window_start.timestamp())
        
        # Count requests in window
        current_count = self.redis.zcard(key)
        
        if current_count >= limit:
            logger.warning(f"Rate limit exceeded for {key}: {current_count}/{limit}")
            return False
        
        # Add current request
        self.redis.zadd(key, {now.timestamp(): now.timestamp()})
        self.redis.expire(key, window_seconds)
        
        return True
    
    def wait_if_needed(self, key: str, limit: int, window_seconds: int):
        """Wait until rate limit allows request"""
        while not self.check_limit(key, limit, window_seconds):
            sleep_time = window_seconds / limit
            logger.info(f"Rate limited, waiting {sleep_time}s")
            time.sleep(sleep_time)
```

**Usage in API:**
```python
@router.post("/backtests/")
async def create_backtest(payload: BacktestCreate, request: Request):
    # Check user rate limit
    user_id = request.state.user.id
    rate_limiter = RateLimiter(redis_client)
    
    if not rate_limiter.check_limit(f"user:{user_id}:backtests", limit=10, window_seconds=60):
        raise RateLimitError(
            message="Слишком много запросов на создание бэктестов",
            retry_after=60
        )
    
    # Proceed with backtest creation
    ...
```

### 2.2 Frontend Rate Limiting

**Debouncing User Input:**
```typescript
// frontend/src/hooks/useDebounce.ts
import { useEffect, useState } from 'react';

export function useDebounce<T>(value: T, delay: number = 500): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}

// Usage in component
const BacktestForm = () => {
  const [params, setParams] = useState({ fast_period: 10, slow_period: 20 });
  const debouncedParams = useDebounce(params, 1000);
  
  useEffect(() => {
    // Only validate after user stops typing
    validateParams(debouncedParams);
  }, [debouncedParams]);
};
```

**Request Queue:**
```typescript
// frontend/src/utils/requestQueue.ts
class RequestQueue {
  private queue: Array<() => Promise<any>> = [];
  private processing = false;
  private maxConcurrent = 3;
  private currentCount = 0;

  async add<T>(request: () => Promise<T>): Promise<T> {
    return new Promise((resolve, reject) => {
      this.queue.push(async () => {
        try {
          const result = await request();
          resolve(result);
        } catch (error) {
          reject(error);
        }
      });
      
      this.process();
    });
  }

  private async process() {
    if (this.processing || this.currentCount >= this.maxConcurrent) {
      return;
    }

    this.processing = true;

    while (this.queue.length > 0 && this.currentCount < this.maxConcurrent) {
      const request = this.queue.shift();
      if (request) {
        this.currentCount++;
        request().finally(() => {
          this.currentCount--;
          this.process();
        });
      }
    }

    this.processing = false;
  }
}

export const backtestQueue = new RequestQueue();
```

---

## 3. Concurrent Requests

### 3.1 Database Connection Pooling

**PostgreSQL Pool Configuration:**
```python
# backend/services/db_pool.py
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,  # Max connections in pool
    max_overflow=20,  # Additional connections when needed
    pool_timeout=30,  # Wait time for connection
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_pre_ping=True,  # Test connections before use
    echo=False
)
```

**Connection Deadlock Prevention:**
```python
from contextlib import contextmanager
from sqlalchemy.orm import Session

@contextmanager
def get_db_session(timeout: int = 30):
    """Get database session with timeout"""
    session = Session(engine)
    
    try:
        # Set lock timeout
        session.execute(f"SET lock_timeout = '{timeout}s'")
        session.execute(f"SET statement_timeout = '{timeout * 2}s'")
        
        yield session
        session.commit()
        
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {e}")
        raise DatabaseError(
            message="Database operation failed",
            operation="transaction",
            details={"error": str(e)}
        )
    finally:
        session.close()
```

### 3.2 Optimistic Locking

**Version-based Concurrency Control:**
```python
# backend/models/backtest.py
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import Session

class Backtest(Base):
    __tablename__ = "backtests"
    
    id = Column(Integer, primary_key=True)
    version = Column(Integer, default=1, nullable=False)  # Optimistic lock
    status = Column(String(20))
    updated_at = Column(DateTime)
    
    @classmethod
    def update_status(cls, session: Session, backtest_id: int, new_status: str, expected_version: int):
        """Update with version check"""
        result = session.query(cls).filter(
            cls.id == backtest_id,
            cls.version == expected_version
        ).update({
            "status": new_status,
            "version": cls.version + 1,
            "updated_at": datetime.utcnow()
        })
        
        if result == 0:
            raise DatabaseError(
                message="Concurrent modification detected",
                operation="update_backtest",
                details={
                    "backtest_id": backtest_id,
                    "expected_version": expected_version,
                    "suggestion": "Refresh and try again"
                }
            )
        
        session.commit()
```

### 3.3 Distributed Locking (Redis)

**Prevent Duplicate Backtest Execution:**
```python
import redis
from contextlib import contextmanager

@contextmanager
def distributed_lock(redis_client: redis.Redis, key: str, timeout: int = 300):
    """Acquire distributed lock"""
    lock_key = f"lock:{key}"
    lock_id = str(uuid.uuid4())
    
    # Try to acquire lock
    acquired = redis_client.set(lock_key, lock_id, nx=True, ex=timeout)
    
    if not acquired:
        raise DatabaseError(
            message="Resource is locked by another process",
            operation="acquire_lock",
            details={"resource": key, "timeout": timeout}
        )
    
    try:
        yield
    finally:
        # Release lock only if we still own it
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        redis_client.eval(lua_script, 1, lock_key, lock_id)

# Usage
def run_backtest(backtest_id: int):
    with distributed_lock(redis_client, f"backtest:{backtest_id}"):
        # Execute backtest
        ...
```

---

## 4. Invalid Strategy Parameters

### 4.1 Parameter Validation

**Type and Range Validation:**
```python
# backend/api/error_handling.py
def validate_strategy_params(strategy_id: int, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate strategy parameters against schema
    
    Args:
        strategy_id: Strategy identifier
        params: User-provided parameters
    
    Returns:
        Validated and sanitized parameters
    
    Raises:
        ValidationError: If parameters are invalid
    """
    from backend.services.data_service import DataService
    
    with DataService() as ds:
        strategy = ds.get_strategy(strategy_id)
        
        if not strategy:
            raise ResourceNotFoundError("Strategy", strategy_id)
        
        schema = strategy.params_schema or {}
        validated = {}
        
        for param_name, param_config in schema.items():
            # Check required parameters
            if param_config.get('required', False) and param_name not in params:
                raise ValidationError(
                    message=f"Required parameter missing: {param_name}",
                    field=param_name,
                    details={"required": True}
                )
            
            value = params.get(param_name, param_config.get('default'))
            
            if value is None:
                continue
            
            # Type validation
            expected_type = param_config.get('type', 'number')
            
            if expected_type == 'number':
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    raise ValidationError(
                        message=f"Parameter {param_name} must be a number",
                        field=param_name,
                        details={"provided": value, "expected_type": "number"}
                    )
                
                # Range validation
                if 'min' in param_config and value < param_config['min']:
                    raise ValidationError(
                        message=f"{param_name} must be >= {param_config['min']}",
                        field=param_name,
                        details={"value": value, "min": param_config['min']}
                    )
                
                if 'max' in param_config and value > param_config['max']:
                    raise ValidationError(
                        message=f"{param_name} must be <= {param_config['max']}",
                        field=param_name,
                        details={"value": value, "max": param_config['max']}
                    )
            
            elif expected_type == 'integer':
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    raise ValidationError(
                        message=f"Parameter {param_name} must be an integer",
                        field=param_name,
                        details={"provided": value, "expected_type": "integer"}
                    )
            
            elif expected_type == 'string':
                if not isinstance(value, str):
                    raise ValidationError(
                        message=f"Parameter {param_name} must be a string",
                        field=param_name,
                        details={"provided": type(value).__name__, "expected_type": "string"}
                    )
                
                # Enum validation
                if 'enum' in param_config and value not in param_config['enum']:
                    raise ValidationError(
                        message=f"{param_name} must be one of: {param_config['enum']}",
                        field=param_name,
                        details={"value": value, "allowed_values": param_config['enum']}
                    )
            
            validated[param_name] = value
        
        return validated
```

### 4.2 Logical Parameter Conflicts

**Cross-parameter Validation:**
```python
def validate_ema_crossover_params(params: Dict[str, Any]) -> None:
    """Validate EMA crossover specific logic"""
    fast = params.get('fast_period', 10)
    slow = params.get('slow_period', 20)
    
    if fast >= slow:
        raise ValidationError(
            message="Fast period must be less than slow period",
            field="periods",
            details={
                "fast_period": fast,
                "slow_period": slow,
                "requirement": "fast < slow"
            }
        )
    
    # Ensure reasonable ratio
    ratio = slow / fast
    if ratio > 10:
        logger.warning(f"Large period ratio: {ratio:.1f}x")
        raise ValidationError(
            message="Period ratio too large (slow/fast > 10)",
            field="periods",
            details={
                "ratio": ratio,
                "max_ratio": 10,
                "suggestion": "Reduce slow period or increase fast period"
            }
        )
```

---

## 5. Network Failures

### 5.1 Retry Strategy

**Exponential Backoff with Jitter:**
```typescript
// frontend/src/utils/errorHandling.ts
export async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  initialDelay: number = 1000
): Promise<T> {
  let lastError: any;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      
      const apiError = parseApiError(error);
      
      // Don't retry non-retryable errors
      if (!apiError.isRetryable) {
        throw apiError;
      }
      
      // Don't retry on last attempt
      if (attempt === maxRetries) {
        throw apiError;
      }
      
      // Calculate backoff: exponential + jitter
      const backoff = initialDelay * Math.pow(2, attempt);
      const jitter = Math.random() * 1000;
      const delay = backoff + jitter;
      
      console.log(`Retry ${attempt + 1}/${maxRetries} after ${Math.round(delay)}ms`);
      
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  
  throw parseApiError(lastError);
}
```

### 5.2 Circuit Breaker

**Prevent Cascading Failures:**
```python
# backend/utils/circuit_breaker.py
from enum import Enum
from datetime import datetime, timedelta
import threading

class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self._lock = threading.Lock()
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker"""
        with self._lock:
            if self.state == CircuitState.OPEN:
                if datetime.now() - self.last_failure_time > timedelta(seconds=self.timeout):
                    self.state = CircuitState.HALF_OPEN
                    logger.info("Circuit breaker: HALF_OPEN")
                else:
                    raise DataFetchError(
                        message="Circuit breaker is OPEN",
                        source="circuit_breaker",
                        details={
                            "failure_count": self.failure_count,
                            "retry_after": self.timeout
                        }
                    )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        with self._lock:
            self.failure_count = 0
            self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.error(f"Circuit breaker: OPEN (failures: {self.failure_count})")

# Usage
bybit_circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60)

def fetch_bybit_klines(symbol: str, timeframe: str):
    return bybit_circuit_breaker.call(
        _internal_bybit_fetch,
        symbol,
        timeframe
    )
```

---

## 6. Database Edge Cases

### 6.1 Transaction Deadlocks

**Deadlock Detection and Retry:**
```python
from sqlalchemy.exc import OperationalError
import time

def execute_with_deadlock_retry(session: Session, operation: callable, max_retries: int = 3):
    """Execute database operation with deadlock retry"""
    for attempt in range(max_retries):
        try:
            result = operation(session)
            session.commit()
            return result
            
        except OperationalError as e:
            session.rollback()
            
            if "deadlock detected" in str(e).lower():
                if attempt < max_retries - 1:
                    wait_time = 0.1 * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Deadlock detected, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Deadlock persists after {max_retries} retries")
                    raise DatabaseError(
                        message="Database deadlock could not be resolved",
                        operation="transaction",
                        details={"retries": max_retries}
                    )
            else:
                raise DatabaseError(
                    message=f"Database operation failed: {str(e)}",
                    operation="transaction",
                    details={"error": str(e)}
                )
```

### 6.2 Connection Leak Detection

**Monitor Active Connections:**
```python
from sqlalchemy import event
from sqlalchemy.pool import Pool

@event.listens_for(Pool, "connect")
def receive_connect(dbapi_conn, connection_record):
    logger.debug("New database connection created")

@event.listens_for(Pool, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    # Track connection checkout time
    connection_record.info['checkout_time'] = datetime.utcnow()

@event.listens_for(Pool, "checkin")
def receive_checkin(dbapi_conn, connection_record):
    # Calculate connection hold time
    checkout_time = connection_record.info.get('checkout_time')
    if checkout_time:
        hold_time = (datetime.utcnow() - checkout_time).total_seconds()
        if hold_time > 30:  # Warning if held > 30s
            logger.warning(f"Connection held for {hold_time:.1f}s (potential leak)")

# Periodic check for pool exhaustion
def check_pool_health():
    pool = engine.pool
    logger.info(f"Pool status: size={pool.size()}, overflow={pool.overflow()}, checked_out={pool.checkedout()}")
    
    if pool.checkedout() >= pool.size() + pool.overflow():
        logger.error("Database connection pool exhausted!")
        # Trigger alert
```

---

## 7. MTF Backtest Edge Cases

### 7.1 Timeframe Synchronization

**Handle Missing Data on Higher Timeframes:**
```python
def align_mtf_data(
    central_data: pd.DataFrame,
    higher_data: pd.DataFrame,
    central_tf: str,
    higher_tf: str
) -> pd.DataFrame:
    """
    Align higher timeframe data with central timeframe
    
    Forward-fill HTF data to match central timeframe timestamps
    """
    # Convert timeframe to minutes
    tf_minutes = {
        '1': 1, '5': 5, '15': 15, '30': 30, '60': 60,
        '240': 240, 'D': 1440, 'W': 10080
    }
    
    central_min = tf_minutes[central_tf]
    higher_min = tf_minutes[higher_tf]
    
    if higher_min <= central_min:
        raise ValidationError(
            message="Higher timeframe must be larger than central timeframe",
            field="timeframes",
            details={
                "central": central_tf,
                "higher": higher_tf,
                "requirement": "higher > central"
            }
        )
    
    # Merge and forward-fill
    merged = pd.merge_asof(
        central_data,
        higher_data,
        on='timestamp',
        direction='backward',
        suffixes=('', f'_{higher_tf}')
    )
    
    # Check for gaps
    null_count = merged.isnull().sum().sum()
    if null_count > len(merged) * 0.1:  # > 10% missing
        logger.warning(f"High proportion of missing HTF data: {null_count}/{len(merged)} rows")
    
    # Forward-fill remaining NaN
    merged = merged.fillna(method='ffill')
    
    return merged
```

### 7.2 HTF Filter Logic Errors

**Validate Filter Configuration:**
```python
def validate_htf_filters(filters: List[Dict]) -> None:
    """Validate HTF filter configurations"""
    valid_types = ['trend_ma', 'momentum_rsi', 'volatility_bb']
    
    for i, filter_config in enumerate(filters):
        # Required fields
        if 'timeframe' not in filter_config or 'type' not in filter_config:
            raise ValidationError(
                message=f"HTF filter {i} missing required fields",
                field="htf_filters",
                details={"filter_index": i, "required_fields": ["timeframe", "type"]}
            )
        
        # Valid type
        if filter_config['type'] not in valid_types:
            raise ValidationError(
                message=f"Invalid HTF filter type: {filter_config['type']}",
                field="htf_filters",
                details={
                    "filter_index": i,
                    "provided_type": filter_config['type'],
                    "valid_types": valid_types
                }
            )
        
        # Type-specific validation
        if filter_config['type'] == 'trend_ma':
            params = filter_config.get('params', {})
            if 'period' not in params or params['period'] < 5:
                raise ValidationError(
                    message="trend_ma filter requires period >= 5",
                    field="htf_filters",
                    details={"filter_index": i, "min_period": 5}
                )
```

---

## 8. Testing Edge Cases

### 8.1 Test Data Generation

**Generate Edge Case Test Data:**
```python
# tests/utils/test_data_generator.py
import pandas as pd
import numpy as np

def generate_extreme_volatility_data(length: int = 100) -> pd.DataFrame:
    """Generate data with flash crashes and spikes"""
    df = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=length, freq='1h'),
        'open': 50000,
        'high': 50000,
        'low': 50000,
        'close': 50000,
        'volume': 1000000
    })
    
    # Add flash crash (index 50)
    df.loc[50, 'low'] = 25000  # 50% drop
    df.loc[50, 'close'] = 30000
    
    # Add spike (index 75)
    df.loc[75, 'high'] = 75000  # 50% spike
    df.loc[75, 'close'] = 70000
    
    return df

def generate_missing_data(length: int = 100, missing_pct: float = 0.1) -> pd.DataFrame:
    """Generate data with random missing values"""
    df = generate_normal_data(length)
    
    # Randomly set values to NaN
    mask = np.random.random(len(df)) < missing_pct
    df.loc[mask, ['open', 'high', 'low', 'close']] = np.nan
    
    return df

def generate_zero_volume_data(length: int = 100) -> pd.DataFrame:
    """Generate data with periods of zero volume"""
    df = generate_normal_data(length)
    
    # Weekend periods (no volume)
    df.loc[20:30, 'volume'] = 0
    df.loc[60:70, 'volume'] = 0
    
    return df
```

### 8.2 Integration Tests for Edge Cases

**Test Suite:**
```python
# tests/test_edge_cases.py
import pytest
from backend.api.error_handling import ValidationError, DataFetchError

class TestEdgeCases:
    
    def test_empty_dataset_handling(self):
        """Test backtest with no market data"""
        with pytest.raises(ValidationError) as exc_info:
            create_backtest({
                "symbol": "FAKESYMBOL",
                "start_date": "2024-01-01",
                "end_date": "2024-01-02",
                ...
            })
        
        assert "No market data available" in str(exc_info.value)
    
    def test_invalid_strategy_params(self):
        """Test validation of strategy parameters"""
        with pytest.raises(ValidationError) as exc_info:
            validate_strategy_params(1, {
                "fast_period": 50,  # Invalid: fast >= slow
                "slow_period": 20
            })
        
        assert "Fast period must be less than slow period" in str(exc_info.value)
    
    def test_concurrent_backtest_creation(self):
        """Test multiple concurrent backtest creations"""
        from concurrent.futures import ThreadPoolExecutor
        
        def create():
            return create_backtest(valid_payload)
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create) for _ in range(10)]
            results = [f.result() for f in futures]
        
        # All should succeed without deadlock
        assert len(results) == 10
    
    def test_rate_limit_enforcement(self):
        """Test API rate limiting"""
        # Create 20 requests rapidly
        for i in range(20):
            try:
                create_backtest(valid_payload)
            except RateLimitError:
                # Should hit rate limit before 20 requests
                assert i < 20
                break
        else:
            pytest.fail("Rate limit not enforced")
    
    def test_mtf_timeframe_validation(self):
        """Test MTF timeframe validation"""
        with pytest.raises(ValidationError) as exc_info:
            create_mtf_backtest({
                "timeframe": "60",  # Central
                "additional_timeframes": ["15"],  # Invalid: 15 < 60
                ...
            })
        
        assert "Higher timeframe must be larger" in str(exc_info.value)
```

---

## Summary

This documentation covers comprehensive edge case handling for:

1. **Data Issues:** Empty datasets, missing fields, extreme volatility
2. **API Limits:** Rate limiting, request queuing, circuit breakers
3. **Concurrency:** Connection pooling, deadlock prevention, distributed locking
4. **Validation:** Parameter type/range checks, logical conflicts
5. **Network:** Retry strategies, exponential backoff, failure detection
6. **Database:** Transaction handling, connection management
7. **MTF:** Timeframe synchronization, filter validation
8. **Testing:** Edge case test data generation, integration tests

All edge cases are handled with:
- ✅ Detailed error messages
- ✅ Logging for debugging
- ✅ User-friendly feedback
- ✅ Graceful degradation
- ✅ Automatic recovery where possible

**Status:** Production Ready ✅
