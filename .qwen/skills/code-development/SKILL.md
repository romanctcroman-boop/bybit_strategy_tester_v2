---
name: Code Development
description: "Write new code, functions, classes, and modules following project patterns and standards."
---

# Code Development Skill for Qwen

## Overview

Create new code that follows existing project patterns, maintains type safety, and integrates seamlessly with the codebase.

## Pre-Development Checklist

Before writing ANY code:

1. **Read CLAUDE.md** — Understand current architecture
2. **Grep for existing patterns** — Find similar implementations
3. **Check high-risk variables** — `commission_rate`, `strategy_params`, `initial_capital`
4. **Identify dependencies** — What modules will this code depend on?

## Code Patterns

### New FastAPI Router

```python
"""
[Feature Name] Router

Provides REST API endpoints for [feature description].
"""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from loguru import logger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/[feature]", tags=["[Feature]"])


class CreateRequest(BaseModel):
    """Request model for creating [resource]."""
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="")


class Response(BaseModel):
    """Response model for [resource]."""
    id: str
    name: str
    created_at: datetime


@router.post("/", response_model=Response, status_code=status.HTTP_201_CREATED)
async def create_resource(
    request: CreateRequest,
    db: Session = Depends(get_db)
) -> Response:
    """Create a new [resource]."""
    try:
        # Implementation here
        return Response(id="uuid", name=request.name, created_at=datetime.now(UTC))
    except Exception as e:
        logger.error(f"Failed to create resource: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
```

### New Service Class

```python
"""
[Service Name] Service

Business logic for [feature description].
"""

from loguru import logger
from typing import Any


class [ServiceName]Service:
    """Service for handling [feature] operations."""
    
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        logger.info(f"[ServiceName]Service initialized")
    
    async def process(self, data: Any) -> Any:
        """Process [data type] and return [result type]."""
        try:
            # Implementation
            return result
        except Exception as e:
            logger.error(f"Processing failed: {e}", exc_info=True)
            raise
```

### New Strategy

```python
"""
[Strategy Name] Strategy

[Brief description of strategy logic].

Signals:
    1 = Long entry
    -1 = Short entry
    0 = No action
"""

from backend.backtesting.strategies.base import BaseStrategy
import pandas as pd
import pandas_ta as ta


class [StrategyName]Strategy(BaseStrategy):
    """[Strategy description]."""
    
    def __init__(self, params: dict):
        super().__init__(params)
        self.required_params = ['param1', 'param2']
        self._validate_params()
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate trading signals from OHLCV data."""
        signals = data.copy()
        signals['signal'] = 0
        
        # Calculate indicator
        indicator = ta.[indicator](signals['close'], length=self.params['param1'])
        
        # Generate signals
        signals.loc[indicator < self.params['param2'], 'signal'] = 1
        signals.loc[indicator > self.params['param3'], 'signal'] = -1
        
        return signals
```

### Pydantic Model

```python
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Any


class [ModelName](BaseModel):
    """Model for [purpose]."""
    
    model_config = ConfigDict(use_enum_values=True)
    
    # Required fields
    name: str = Field(..., min_length=1, max_length=100, description="Description")
    
    # Optional with defaults
    value: float = Field(default=0.0, ge=0, le=100)
    enabled: bool = Field(default=True)
    
    # Computed fields (use @property or model_validator)
    @property
    def formatted_name(self) -> str:
        return self.name.upper()
```

## File Organization

| Type | Location |
|------|----------|
| Router | `backend/api/routers/[feature].py` |
| Service | `backend/services/[feature]/service.py` |
| Model (ORM) | `backend/database/models/[feature].py` |
| Model (Pydantic) | `backend/api/schemas.py` or router file |
| Strategy | `backend/backtesting/strategies/[name].py` |
| Test | `tests/backend/[module]/test_[feature].py` |

## Type Hints

ALWAYS use type hints:

```python
def process_data(
    data: pd.DataFrame,
    params: dict[str, Any],
    threshold: float = 0.5
) -> pd.Series:
    """Process data and return signals."""
    ...
```

## Error Handling

```python
from loguru import logger

try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"Specific error: {e}", exc_info=True)
    raise HTTPException(status_code=400, detail=str(e))
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail="Internal error")
```

## Async Patterns

```python
# Blocking I/O in async context
import asyncio

async def async_operation():
    # Use asyncio.to_thread for blocking calls
    result = await asyncio.to_thread(blocking_function, arg1, arg2)
    return result

# Database queries (SQLAlchemy)
rows = await asyncio.to_thread(
    db.query(Model).filter(Model.id == id).all
)
```

## Testing Requirements

Every new feature needs:

```python
import pytest
from unittest.mock import Mock, patch


def test_new_feature_success(sample_data):
    """Test successful execution."""
    result = new_feature(sample_data)
    assert result is not None
    assert isinstance(result, ExpectedType)


def test_new_feature_with_invalid_input():
    """Test error handling."""
    with pytest.raises(ValueError):
        new_feature(invalid_data)


@patch('module.external_api_call')
def test_new_feature_mocked(mock_api):
    """Test with mocked external dependencies."""
    mock_api.return_value = {'status': 'success'}
    result = new_feature(test_data)
    assert result.expected_value == 'something'
```

## Validation Checklist

Before considering code complete:

- [ ] Type hints on all functions
- [ ] Error handling with logging
- [ ] Follows existing code patterns
- [ ] No hardcoded secrets or paths
- [ ] Tests written and passing
- [ ] Ruff check passes
- [ ] CHANGELOG.md updated

## Post-Development

After writing code:

1. **Run tests:** `pytest tests/path/to/test_file.py -v`
2. **Check lint:** `ruff check . --fix && ruff format .`
3. **Verify imports:** `python -c "from backend.api.app import app; print('OK')"`
4. **Update documentation:** Add to relevant `.md` files
5. **Commit:** `git commit -m "feat: add [feature name]"`
