from typing import Any

from fastapi import APIRouter, Query

router = APIRouter()


# In a real system, these would be loaded from DB/models and pydantic schemas
MOCK_STRATEGY_VERSIONS = [
    {"id": 101, "strategy_id": 1, "name": "Dimkud BIG2 v1.7"},
    {"id": 102, "strategy_id": 1, "name": "Dimkud BIG2 v1.8"},
]

MOCK_SCHEMAS: dict[int, dict[str, Any]] = {
    101: {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "BIG2 Parameters",
        "type": "object",
        "properties": {
            "rsi_period": {"type": "integer", "minimum": 2, "maximum": 100, "default": 14},
            "ema_fast": {"type": "integer", "minimum": 2, "maximum": 100, "default": 12},
            "ema_slow": {"type": "integer", "minimum": 2, "maximum": 200, "default": 26},
            "take_profit_pct": {"type": "number", "minimum": 0.0, "maximum": 100.0, "default": 1.2},
            "stop_loss_pct": {"type": "number", "minimum": 0.0, "maximum": 100.0, "default": 0.8},
        },
        "required": ["rsi_period", "ema_fast", "ema_slow"],
    },
    102: {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "BIG2 Parameters v1.8",
        "type": "object",
        "properties": {
            "rsi_period": {"type": "integer", "minimum": 2, "maximum": 100, "default": 14},
            "ema_fast": {"type": "integer", "minimum": 2, "maximum": 100, "default": 10},
            "ema_slow": {"type": "integer", "minimum": 2, "maximum": 200, "default": 30},
        },
        "required": ["rsi_period", "ema_fast", "ema_slow"],
    },
}

MOCK_PRESETS: dict[int, list[dict[str, Any]]] = {
    101: [
        {"id": 1, "name": "Default", "params": {"rsi_period": 14, "ema_fast": 12, "ema_slow": 26}},
        {"id": 2, "name": "Aggressive", "params": {"rsi_period": 9, "ema_fast": 9, "ema_slow": 21}},
    ],
    102: [
        {
            "id": 3,
            "name": "Conservative",
            "params": {"rsi_period": 21, "ema_fast": 10, "ema_slow": 30},
        },
    ],
}


@router.get("/strategy-versions")
def list_strategy_versions():
    return {"items": MOCK_STRATEGY_VERSIONS, "total": len(MOCK_STRATEGY_VERSIONS)}


@router.get("/strategy-version/{version_id}/schema")
def get_strategy_version_schema(version_id: int):
    return MOCK_SCHEMAS.get(version_id) or {"type": "object", "properties": {}}


@router.get("/presets")
def list_presets(version_id: int | None = Query(None)):
    if version_id is None:
        all_items = [p for arr in MOCK_PRESETS.values() for p in arr]
        return {"items": all_items, "total": len(all_items)}
    items = MOCK_PRESETS.get(version_id, [])
    return {"items": items, "total": len(items)}


@router.post("/backtests/quick")
def quick_backtest(payload: dict[str, Any]):
    # This is a mock. In real impl, call backtest pipeline with limited window to compute metrics quickly.
    return {
        "metrics": {"win_rate": 0.56, "profit_factor": 1.23, "max_dd": 0.12},
        "equity_preview": [100, 101, 99, 103, 104],
        "warnings": [],
    }


@router.post("/bots")
def create_bot(payload: dict[str, Any]):
    # return a fake id
    return {"bot_id": 9001, "status": "created"}
