---
applyTo: "**/models/**/*.py,**/migrations/**/*.py,**/alembic/**/*.py"
---

# Database & Models Rules

## Database Setup

- **Primary DB**: `data.sqlite3` (SQLAlchemy + SQLite)
- **Klines DB**: `bybit_klines_15m.db` (market data)
- **ORM**: SQLAlchemy 2.0 with async support via `asyncio.to_thread()`
- **Migrations**: Alembic

## Critical Rules

1. **DATA_START_DATE** = `2025-01-01` — import from `backend/config/database_policy.py`
2. **NEVER** hardcode database paths — use config/env
3. **ALWAYS** use `asyncio.to_thread()` for blocking SQLite operations in async contexts
4. **NEVER** use `DROP TABLE` or `TRUNCATE` without explicit approval
5. **Use parameterized queries** — NEVER string concatenation for SQL

## Model Pattern

```python
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class BacktestResult(Base):
    __tablename__ = 'backtest_results'

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False, index=True)
    timeframe = Column(String, nullable=False)
    strategy_type = Column(String, nullable=False)
    strategy_params = Column(JSON, nullable=False)
    metrics = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())
```

## Migration Rules

```python
# Always create migration before schema changes:
# alembic revision --autogenerate -m "description"
# alembic upgrade head

# NEVER modify existing migration files
# ALWAYS test migration: upgrade + downgrade + upgrade
```

## Query Pattern (Repository)

```python
class BacktestRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, id: int) -> Optional[BacktestResult]:
        return self.session.query(BacktestResult).get(id)

    def list_by_symbol(self, symbol: str) -> List[BacktestResult]:
        return (self.session.query(BacktestResult)
                .filter(BacktestResult.symbol == symbol)
                .order_by(BacktestResult.created_at.desc())
                .all())
```
