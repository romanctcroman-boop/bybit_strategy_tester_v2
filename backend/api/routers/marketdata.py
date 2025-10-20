from fastapi import APIRouter, Query, Depends, HTTPException
from typing import List, Optional
from backend.database import get_db
from sqlalchemy.orm import Session
from backend.models.bybit_kline_audit import BybitKlineAudit

router = APIRouter()


@router.get('/bybit/klines')
def get_bybit_klines(symbol: str = Query(...), limit: int = Query(100, ge=1, le=1000), start_time: Optional[int] = None, db: Session = Depends(get_db)):
    """Return kline audit rows for a symbol. start_time is open_time in ms; returns rows older than or equal to start_time when provided."""
    q = db.query(BybitKlineAudit).filter(BybitKlineAudit.symbol == symbol)
    if start_time:
        q = q.filter(BybitKlineAudit.open_time <= start_time)
    rows = q.order_by(BybitKlineAudit.open_time.desc()).limit(limit).all()
    results = []
    for r in rows:
        results.append({
            'symbol': r.symbol,
            'open_time': r.open_time,
            'open_time_dt': r.open_time_dt.isoformat() if r.open_time_dt else None,
            'open': r.open_price,
            'high': r.high_price,
            'low': r.low_price,
            'close': r.close_price,
            'volume': r.volume,
            'turnover': r.turnover,
            'raw': r.raw,
        })
    return results
