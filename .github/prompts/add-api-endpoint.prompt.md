# Add API Endpoint Prompt

Step-by-step guide for adding a new FastAPI endpoint.

## Prerequisites

- [ ] Endpoint requirements defined
- [ ] Request/response schema designed
- [ ] Related service exists or will be created

## Implementation Steps

### 1. Define Schemas

Path: `backend/api/schemas/[feature].py`

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime


class FeatureRequest(BaseModel):
    """Request model for feature endpoint."""

    field1: str = Field(..., description="Required field")
    field2: Optional[int] = Field(None, ge=0, description="Optional field")

    @validator('field1')
    def validate_field1(cls, v):
        if not v:
            raise ValueError('field1 cannot be empty')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "field1": "value",
                "field2": 42
            }
        }


class FeatureResponse(BaseModel):
    """Response model for feature endpoint."""

    success: bool
    data: dict
    created_at: datetime
```

### 2. Create Router

Path: `backend/api/routers/[feature].py`

```python
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from backend.api.schemas.feature import FeatureRequest, FeatureResponse
from backend.services.feature_service import FeatureService
from backend.api.dependencies import get_feature_service

router = APIRouter(
    prefix="/api/v1/feature",
    tags=["Feature"],
)


@router.post("/", response_model=FeatureResponse)
async def create_feature(
    request: FeatureRequest,
    service: FeatureService = Depends(get_feature_service)
):
    """
    Create a new feature.

    - **field1**: Required description
    - **field2**: Optional description

    Returns the created feature data.
    """
    try:
        logger.info(f"Feature request: {request.field1}")
        result = await service.create(request)
        return FeatureResponse(
            success=True,
            data=result,
            created_at=datetime.utcnow()
        )
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Feature error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{feature_id}", response_model=FeatureResponse)
async def get_feature(
    feature_id: str,
    service: FeatureService = Depends(get_feature_service)
):
    """Get feature by ID."""
    result = await service.get(feature_id)
    if not result:
        raise HTTPException(status_code=404, detail="Feature not found")
    return FeatureResponse(success=True, data=result, created_at=result.created_at)
```

### 3. Register Router

Path: `backend/api/app.py`

```python
from backend.api.routers import feature

app.include_router(feature.router)
```

### 4. Create Service (if needed)

Path: `backend/services/feature_service.py`

```python
from loguru import logger


class FeatureService:
    def __init__(self, db):
        self.db = db

    async def create(self, request):
        logger.debug(f"Creating feature: {request}")
        # Implementation
        return result

    async def get(self, feature_id: str):
        # Implementation
        return result
```

### 5. Add Dependency

Path: `backend/api/dependencies.py`

```python
from backend.services.feature_service import FeatureService

def get_feature_service(db: Session = Depends(get_db)) -> FeatureService:
    return FeatureService(db)
```

### 6. Create Tests

Path: `tests/integration/test_api/test_feature.py`

```python
import pytest
from httpx import AsyncClient
from backend.api.app import app


class TestFeatureAPI:
    @pytest.mark.asyncio
    async def test_create_feature_success(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/api/v1/feature/", json={
                "field1": "test",
                "field2": 42
            })

        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_create_feature_validation_error(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/api/v1/feature/", json={
                "field1": ""  # Invalid
            })

        assert response.status_code == 400
```

### 7. Run Validation

```bash
# Start server
uvicorn backend.api.app:app --reload

# Test endpoint
curl -X POST http://localhost:8000/api/v1/feature/ \
  -H "Content-Type: application/json" \
  -d '{"field1": "test"}'

# Run tests
pytest tests/integration/test_api/test_feature.py -v

# Check OpenAPI docs
# Visit: http://localhost:8000/docs
```

## Checklist

- [ ] Pydantic schemas defined with validators
- [ ] Router created with proper tags
- [ ] Router registered in app.py
- [ ] Service layer implemented
- [ ] Dependency injection configured
- [ ] Error handling (400, 404, 500)
- [ ] Logging added (info for requests, error for failures)
- [ ] Integration tests written
- [ ] OpenAPI documentation verified
