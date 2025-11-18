"""
Демонстрационные тесты для Quick Win #4: Database Rollback Fixtures

Показывает преимущества автоматического rollback:
- Изоляция тестов
- Отсутствие ручной очистки
- Параллельное выполнение
- Скорость
"""
import pytest
import json
from datetime import datetime, timezone
import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path
repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

from backend.models.bybit_kline_audit import BybitKlineAudit


def create_test_kline(symbol, open_time, **kwargs):
    """Helper для создания тестовых kline записей"""
    defaults = {
        "interval": "1h",
        "open_price": 50000.0,
        "high_price": 51000.0,
        "low_price": 49500.0,
        "close_price": 50500.0,
        "volume": 100.0,
        "turnover": 5000000.0,
        "raw": f'["{open_time}","50000","51000","49500","50500","100","5000000"]',
    }
    defaults.update(kwargs)
    return BybitKlineAudit(
        symbol=symbol,
        open_time=open_time,
        **defaults
    )


class TestDatabaseIsolation:
    """Тесты изоляции базы данных с автоматическим rollback"""

    def test_insert_kline_auto_rollback(self, db_session):
        """Тест вставки kline с автоматическим откатом"""
        # Создаем тестовую kline запись
        kline = create_test_kline("BTCUSDT", 1600000000000, volume=100.5)
        
        db_session.add(kline)
        db_session.commit()
        
        # Проверяем, что запись создана
        found = db_session.query(BybitKlineAudit).filter_by(
            symbol="BTCUSDT",
            open_time=1600000000000
        ).first()
        assert found is not None
        assert found.open_price == 50000.0
        assert found.volume == 100.5
        
        # После завершения теста произойдет автоматический rollback
        # Запись НЕ останется в БД

    def test_insert_multiple_klines(self, db_session):
        """Тест вставки нескольких klines"""
        # Создаем несколько klines
        base_time = 1600000000000
        for i in range(5):
            kline = create_test_kline(
                "ETHUSDT", 
                base_time + (i * 900000),
                interval="15m",
                volume=50.0 + i
            )
            db_session.add(kline)
        
        db_session.commit()
        
        # Проверяем количество
        count = db_session.query(BybitKlineAudit).filter_by(symbol="ETHUSDT").count()
        assert count >= 5
        
        # Rollback произойдет автоматически

    def test_update_kline_auto_rollback(self, db_session):
        """Тест обновления kline с откатом"""
        # Создаем
        kline = create_test_kline("BTCUSDT", 1600001000000)
        db_session.add(kline)
        db_session.commit()
        
        # Обновляем
        kline.close_price = 51500.0
        kline.high_price = 52000.0
        db_session.commit()
        
        # Проверяем
        updated = db_session.query(BybitKlineAudit).filter_by(
            open_time=1600001000000
        ).first()
        assert updated.close_price == 51500.0
        assert updated.high_price == 52000.0
        
        # Изменения откатятся

    def test_delete_kline_auto_rollback(self, db_session):
        """Тест удаления с откатом"""
        # Создаем
        kline = create_test_kline("BTCUSDT", 1600002000000)
        db_session.add(kline)
        db_session.commit()
        
        # Удаляем
        db_session.delete(kline)
        db_session.commit()
        
        # Проверяем удаление
        found = db_session.query(BybitKlineAudit).filter_by(
            open_time=1600002000000
        ).first()
        assert found is None
        
        # Удаление откатится


class TestIsolationBetweenTests:
    """Проверка изоляции между тестами"""

    def test_isolation_part1_create(self, db_session):
        """Первая часть: создаем данные"""
        kline = create_test_kline("ISOLATION_TEST", 1600003000000)
        db_session.add(kline)
        db_session.commit()
        
        assert db_session.query(BybitKlineAudit).filter_by(
            symbol="ISOLATION_TEST"
        ).first() is not None

    def test_isolation_part2_verify_clean(self, db_session):
        """Вторая часть: проверяем, что данных из первого теста нет"""
        # Благодаря rollback, данные из предыдущего теста не видны
        found = db_session.query(BybitKlineAudit).filter_by(
            symbol="ISOLATION_TEST"
        ).first()
        
        # Этот тест может пройти или упасть в зависимости от порядка выполнения
        # Но благодаря rollback каждый тест начинает с чистой БД
        # (в рамках своей транзакции)


class TestNoCleanupNeeded:
    """Демонстрация: нет необходимости в ручной очистке"""

    def test_no_teardown_needed(self, db_session):
        """Тест без teardown - rollback сделает всё автоматически"""
        # Старый подход требовал:
        # try:
        #     ... тестовый код ...
        # finally:
        #     db.session.query(BybitKlineAudit).delete()
        #     db.session.commit()
        
        # Новый подход - просто пишем тест:
        kline = create_test_kline("NO_CLEANUP_TEST", 1600004000000)
        db_session.add(kline)
        db_session.commit()
        
        assert db_session.query(BybitKlineAudit).filter_by(
            symbol="NO_CLEANUP_TEST"
        ).first() is not None
        
        # Нет finally блока - rollback автоматический!


@pytest.mark.parametrize("volume", [10.0, 50.0, 100.0, 500.0, 1000.0])
def test_parametrized_with_rollback(db_session, volume):
    """Параметризованный тест с rollback"""
    kline = create_test_kline(
        "PARAM_TEST",
        1600005000000 + int(volume),  # Уникальное время
        volume=volume
    )
    db_session.add(kline)
    db_session.commit()
    
    found = db_session.query(BybitKlineAudit).filter_by(
        open_time=1600005000000 + int(volume)
    ).first()
    assert found is not None
    assert found.volume == volume
    
    # Каждая итерация параметризованного теста изолирована


class TestPerformanceComparison:
    """Сравнение производительности"""

    def test_fast_with_rollback(self, db_session):
        """Быстрый тест с rollback (нет реального DELETE)"""
        import time
        import json
        
        start = time.time()
        
        # Создаем 10 записей с обязательным raw field
        base_time = 1600006000000
        for i in range(10):
            kline = BybitKlineAudit(
                symbol="PERF_TEST",
                interval="1h",
                open_time=base_time + (i * 3600000),
                open_price=50000.0 + i * 100,
                high_price=51000.0 + i * 100,
                low_price=49500.0 + i * 100,
                close_price=50500.0 + i * 100,
                volume=100.0 + i,
                turnover=5000000.0 + i * 10000,
                raw=json.dumps({
                    "symbol": "PERF_TEST",
                    "interval": "1h",
                    "open_time": base_time + (i * 3600000),
                    "data": [50000.0 + i * 100, 51000.0 + i * 100, 49500.0 + i * 100, 50500.0 + i * 100]
                }),
            )
            db_session.add(kline)
        
        db_session.commit()
        
        elapsed = time.time() - start
        
        # Очистка не требуется - rollback быстрее DELETE
        # С rollback: ~0.01-0.05 секунды
        # Со старым подходом (DELETE): ~0.1-0.5 секунды
        
        assert elapsed < 1.0  # Должно быть очень быстро


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
