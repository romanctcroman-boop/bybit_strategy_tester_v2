---
name: Database Operations
description: "SQLite/SQLAlchemy patterns for the Bybit Strategy Tester v2 platform. Models, sessions, queries, and async context."
---

# Database Operations Skill

## Overview

Work with SQLite databases using SQLAlchemy ORM following project conventions.

## Database Setup

```python
# Always import from backend.database (NOT from session.py directly)
from backend.database import Base, SessionLocal, engine, get_db
```

- **Engine**: auto-configured from `DATABASE_URL` env var, defaults to `data.sqlite3`
- **SessionLocal**: `sessionmaker(autocommit=False, autoflush=False)`
- **Base**: `declarative_base()` — all models inherit from this
- **get_db()**: FastAPI dependency (generator yielding Session)

## Database Files

| Database              | Purpose                                                    |
| --------------------- | ---------------------------------------------------------- |
| `data.sqlite3`        | Main app DB (strategies, backtests, trades, optimizations) |
| `bybit_klines_15m.db` | Kline/candle market data                                   |

## Model Template

```python
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from backend.database import Base


class MyModel(Base):
    """Model description."""

    __tablename__ = "my_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, index=True)
    data = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
```

## Key Models

| Model              | Table                | Location                                       |
| ------------------ | -------------------- | ---------------------------------------------- |
| `Strategy`         | `strategies`         | `backend/database/models/strategy.py`          |
| `Backtest`         | `backtests`          | `backend/database/models/backtest.py`          |
| `Trade`            | `trades`             | `backend/database/models/trade.py`             |
| `Optimization`     | `optimizations`      | `backend/database/models/optimization.py`      |
| `StrategyVersion`  | `strategy_versions`  | `backend/database/models/strategy_version.py`  |
| `ChatConversation` | `chat_conversations` | `backend/database/models/chat_conversation.py` |

## Async DB in FastAPI Routers

SQLite is blocking — always wrap DB calls with `asyncio.to_thread`:

```python
import asyncio

@router.get("/items")
async def get_items(db: Session = Depends(get_db)):
    items = await asyncio.to_thread(db.query(MyModel).all)
    return items
```

## Query Patterns

```python
# Create
db = SessionLocal()
try:
    item = MyModel(name="test", data={"key": "value"})
    db.add(item)
    db.commit()
    db.refresh(item)
finally:
    db.close()

# Read with filter
items = db.query(MyModel).filter(
    MyModel.name == "test"
).order_by(MyModel.created_at.desc()).all()

# Update
item = db.query(MyModel).get(item_id)
if item:
    item.name = "updated"
    db.commit()

# Delete
db.query(MyModel).filter(MyModel.id == item_id).delete()
db.commit()
```

## Unit of Work Pattern

```python
from backend.database.unit_of_work import UnitOfWork

async with UnitOfWork() as uow:
    uow.session.add(item)
    await uow.commit()
```

## Rules

- **NEVER** set `DATABASE_URL` for local dev — uses SQLite by default
- **ALWAYS** close sessions (use `try/finally` or context managers)
- **ALWAYS** use `asyncio.to_thread()` in async router handlers
- Run migrations with: `alembic upgrade head`
- Import from `backend.database` not `backend.database.session`
