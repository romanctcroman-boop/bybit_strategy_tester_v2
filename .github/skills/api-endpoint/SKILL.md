---
name: API Endpoint Development
description: "Create and modify FastAPI endpoints following project conventions with proper error handling, validation, and async patterns."
---

# API Endpoint Development Skill

## Overview

Create FastAPI router endpoints following project standards with consistent error handling, request validation, and async database patterns.

## Endpoint Template

```python
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from loguru import logger
from typing import Optional, List

router = APIRouter(prefix="/api/v1/feature", tags=["Feature"])


class FeatureRequest(BaseModel):
    """Request model with validation."""
    name: str
    value: float
    options: Optional[dict] = None


class FeatureResponse(BaseModel):
    """Response model."""
    id: str
    result: dict
    message: str = "success"


@router.post("/action", response_model=FeatureResponse)
async def action(request: FeatureRequest) -> FeatureResponse:
    """
    Perform an action.

    Args:
        request: The action parameters.

    Returns:
        FeatureResponse with results.
    """
    try:
        result = await process(request)
        return FeatureResponse(id="123", result=result)
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Action failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/items", response_model=List[FeatureResponse])
async def list_items(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> List[FeatureResponse]:
    """List items with pagination."""
    try:
        items = await get_items(limit=limit, offset=offset)
        return items
    except Exception as e:
        logger.error(f"List items failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

## File Location

Routers go in `backend/api/routers/`.

## Router Registration

Register in `backend/api/app.py`:

```python
from backend.api.routers.feature import router as feature_router
app.include_router(feature_router)
```

## Async Database Pattern

SQLite operations are blocking — use `asyncio.to_thread`:

```python
import asyncio
from backend.core.database import get_db

async def get_items_from_db():
    db = next(get_db())
    try:
        items = await asyncio.to_thread(
            lambda: db.query(Model).filter(...).all()
        )
        return items
    finally:
        db.close()
```

## Error Handling Standards

| Status Code | When                               |
| ----------- | ---------------------------------- |
| 400         | Invalid input, validation errors   |
| 404         | Resource not found                 |
| 409         | Conflict (duplicate)               |
| 422         | Pydantic validation failure (auto) |
| 429         | Rate limit exceeded                |
| 500         | Internal server error              |

## Bybit API Integration

```python
from backend.services.adapters.bybit import BybitAdapter

adapter = BybitAdapter()
response = await adapter.get_historical_klines(symbol, interval, start, end)

# ALWAYS check retCode
if response.get('retCode') != 0:
    raise HTTPException(status_code=502, detail=response.get('retMsg'))
```

## Testing Endpoints

```python
import pytest
from httpx import AsyncClient, ASGITransport
from backend.api.app import app

@pytest.mark.asyncio
async def test_feature_action_returns_200():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/feature/action", json={
            "name": "test",
            "value": 1.0
        })
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "success"
```
