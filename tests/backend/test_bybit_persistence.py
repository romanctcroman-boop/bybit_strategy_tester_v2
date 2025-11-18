"""
Test Bybit persistence with automatic rollback.

Quick Win #4: Использует db_session fixture с автоматическим rollback.
Больше не нужно вручную очищать данные!
"""
import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path so `backend` package imports work during pytest runs
repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

from backend.models.bybit_kline_audit import BybitKlineAudit
from backend.services.adapters.bybit import BybitAdapter


def test_persist_idempotent(db_session):
    """
    ✅ Quick Win #4: Автоматический rollback после теста.
    
    Тест проверяет идемпотентность персистенции:
    - Вставляет одинаковые строки дважды
    - Должно остаться только 2 уникальных записи
    - После теста все данные автоматически откатятся
    """
    # Ensure persistence env is enabled
    os.environ["BYBIT_PERSIST_KLINES"] = "1"

    adapter = BybitAdapter()
    # prepare two identical rows (same open_time) and one different
    now_ms = 1600000000000
    rows = [
        {
            "open_time": now_ms,
            "open": 1.0,
            "high": 2.0,
            "low": 0.9,
            "close": 1.5,
            "volume": 10,
            "turnover": 15,
            "raw": ["1600000000000", "1", "2", "0.9", "1.5", "10", "15"],
        },
        {
            "open_time": now_ms,
            "open": 1.0,
            "high": 2.0,
            "low": 0.9,
            "close": 1.5,
            "volume": 10,
            "turnover": 15,
            "raw": ["1600000000000", "1", "2", "0.9", "1.5", "10", "15"],
        },
        {
            "open_time": now_ms + 60000,
            "open": 1.5,
            "high": 2.5,
            "low": 1.4,
            "close": 2.0,
            "volume": 5,
            "turnover": 10,
            "raw": ["1600000060000", "1.5", "2.5", "1.4", "2.0", "5", "10"],
        },
    ]

    # ✅ Используем db_session из fixture вместо SessionLocal()
    # run persistence twice to validate idempotency
    adapter._persist_klines_to_db("TESTUSD", rows, db=db_session)
    adapter._persist_klines_to_db("TESTUSD", rows, db=db_session)

    all_rows = db_session.query(BybitKlineAudit).filter(BybitKlineAudit.symbol == "TESTUSD").all()
    # Expect two rows (unique open_time)
    assert len(all_rows) == 2
    
    # ✅ Не нужно вручную закрывать сессию или чистить данные!
    # Fixture автоматически сделает rollback после теста
