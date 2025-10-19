"""
Unit Tests for Walk-Forward Optimization

Тесты для проверки корректности работы Walk-Forward анализа.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any

import numpy as np
import pandas as pd
import pytest

from backend.core.walkforward import (
    WalkForwardWindow,
    WalkForwardAnalyzer,
    calculate_wfo_windows
)


@pytest.fixture
def sample_data():
    """Создаёт тестовые данные для Walk-Forward"""
    dates = pd.date_range(start="2024-01-01", end="2024-12-31", freq="1H")
    
    # Генерируем синтетические OHLCV данные
    np.random.seed(42)
    close = 50000 + np.cumsum(np.random.randn(len(dates)) * 100)
    
    data = pd.DataFrame({
        "timestamp": dates,
        "open": close + np.random.randn(len(dates)) * 50,
        "high": close + np.abs(np.random.randn(len(dates))) * 100,
        "low": close - np.abs(np.random.randn(len(dates))) * 100,
        "close": close,
        "volume": np.random.randint(100, 1000, len(dates))
    })
    
    return data


@pytest.fixture
def simple_strategy_config():
    """Простая конфигурация стратегии для тестов"""
    return {
        "type": "MA_Crossover",
        "initial_capital": 10000.0,
        "commission": 0.001,
    }


@pytest.fixture
def param_space():
    """Пространство параметров для оптимизации"""
    return {
        "fast_period": [10, 20],
        "slow_period": [50, 100]
    }


class TestWalkForwardWindow:
    """Тесты для WalkForwardWindow"""
    
    def test_window_creation(self):
        """Тест создания окна"""
        window = WalkForwardWindow(
            window_id=0,
            is_start=datetime(2024, 1, 1),
            is_end=datetime(2024, 3, 1),
            oos_start=datetime(2024, 3, 1),
            oos_end=datetime(2024, 4, 1)
        )
        
        assert window.window_id == 0
        assert window.is_start == datetime(2024, 1, 1)
        assert window.oos_end == datetime(2024, 4, 1)
        assert window.best_params is None
    
    def test_window_to_dict(self):
        """Тест сериализации окна"""
        window = WalkForwardWindow(
            window_id=1,
            is_start=datetime(2024, 1, 1),
            is_end=datetime(2024, 3, 1),
            oos_start=datetime(2024, 3, 1),
            oos_end=datetime(2024, 4, 1),
            best_params={"period": 20},
            is_metrics={"sharpe": 1.5},
            oos_metrics={"sharpe": 1.2}
        )
        
        result = window.to_dict()
        
        assert result["window_id"] == 1
        assert result["best_params"] == {"period": 20}
        assert result["is_metrics"]["sharpe"] == 1.5
        assert result["oos_metrics"]["sharpe"] == 1.2
        assert isinstance(result["is_start"], str)  # ISO format


class TestWalkForwardAnalyzer:
    """Тесты для WalkForwardAnalyzer"""
    
    def test_analyzer_initialization(self, sample_data):
        """Тест инициализации анализатора"""
        analyzer = WalkForwardAnalyzer(
            data=sample_data,
            initial_capital=10000.0,
            commission=0.001,
            is_window_days=30,
            oos_window_days=15,
            step_days=15
        )
        
        assert analyzer.initial_capital == 10000.0
        assert analyzer.commission == 0.001
        assert len(analyzer.windows) > 0
    
    def test_window_creation(self, sample_data):
        """Тест создания окон"""
        analyzer = WalkForwardAnalyzer(
            data=sample_data,
            is_window_days=60,
            oos_window_days=30,
            step_days=30
        )
        
        # Проверяем что окна созданы
        assert len(analyzer.windows) > 0
        
        # Проверяем первое окно
        first_window = analyzer.windows[0]
        assert first_window.window_id == 0
        assert first_window.is_start < first_window.is_end
        assert first_window.is_end == first_window.oos_start
        assert first_window.oos_start < first_window.oos_end
    
    def test_window_overlap(self, sample_data):
        """Тест что окна правильно перекрываются"""
        analyzer = WalkForwardAnalyzer(
            data=sample_data,
            is_window_days=60,
            oos_window_days=30,
            step_days=30
        )
        
        if len(analyzer.windows) >= 2:
            window1 = analyzer.windows[0]
            window2 = analyzer.windows[1]
            
            # Второе окно должно начинаться через step_days
            time_diff = (window2.is_start - window1.is_start).days
            assert time_diff == 30
    
    def test_insufficient_data(self):
        """Тест с недостаточным количеством данных"""
        # Создаём очень маленький датасет
        small_data = pd.DataFrame({
            "timestamp": pd.date_range(start="2024-01-01", periods=10, freq="1D"),
            "open": [100] * 10,
            "high": [110] * 10,
            "low": [90] * 10,
            "close": [105] * 10,
            "volume": [1000] * 10
        })
        
        # Должно вызвать ошибку - окна слишком большие
        with pytest.raises(ValueError, match="Недостаточно данных"):
            WalkForwardAnalyzer(
                data=small_data,
                is_window_days=100,
                oos_window_days=50,
                step_days=25
            )
    
    def test_missing_timestamp_column(self):
        """Тест с отсутствующей колонкой timestamp"""
        bad_data = pd.DataFrame({
            "open": [100, 105],
            "high": [110, 115],
            "low": [90, 95],
            "close": [105, 110],
            "volume": [1000, 1100]
        })
        
        with pytest.raises(ValueError, match="должен содержать колонку 'timestamp'"):
            WalkForwardAnalyzer(data=bad_data)
    
    @pytest.mark.asyncio
    async def test_get_window_data(self, sample_data):
        """Тест получения данных окна"""
        analyzer = WalkForwardAnalyzer(
            data=sample_data,
            is_window_days=60,
            oos_window_days=30,
            step_days=30
        )
        
        if len(analyzer.windows) > 0:
            window = analyzer.windows[0]
            
            # Получаем IS данные
            is_data = analyzer._get_window_data(window.is_start, window.is_end)
            assert len(is_data) > 0
            assert is_data["timestamp"].min() >= window.is_start
            assert is_data["timestamp"].max() < window.is_end
            
            # Получаем OOS данные
            oos_data = analyzer._get_window_data(window.oos_start, window.oos_end)
            assert len(oos_data) > 0
            assert oos_data["timestamp"].min() >= window.oos_start
            assert oos_data["timestamp"].max() < window.oos_end


class TestCalculateWFOWindows:
    """Тесты для вспомогательной функции calculate_wfo_windows"""
    
    def test_basic_calculation(self):
        """Тест базового расчёта количества окон"""
        # 365 дней данных, окна по 90+30 дней, шаг 30 дней
        num_windows = calculate_wfo_windows(
            total_days=365,
            is_window=90,
            oos_window=30,
            step=30
        )
        
        # (365 - 120) // 30 + 1 = 9
        assert num_windows == 9
    
    def test_insufficient_data(self):
        """Тест с недостаточным количеством данных"""
        num_windows = calculate_wfo_windows(
            total_days=100,
            is_window=90,
            oos_window=30,
            step=30
        )
        
        assert num_windows == 0
    
    def test_exact_fit(self):
        """Тест когда данных ровно на одно окно"""
        num_windows = calculate_wfo_windows(
            total_days=120,  # Ровно на IS + OOS
            is_window=90,
            oos_window=30,
            step=30
        )
        
        assert num_windows == 1


@pytest.mark.asyncio
@pytest.mark.slow
class TestWalkForwardIntegration:
    """Integration тесты с реальной оптимизацией (медленные)"""
    
    async def test_full_walkforward_cycle(self, sample_data, simple_strategy_config, param_space):
        """
        Полный цикл Walk-Forward оптимизации
        
        ПРИМЕЧАНИЕ: Этот тест требует реализованного BacktestEngine
        """
        pytest.skip("Requires BacktestEngine implementation")
        
        analyzer = WalkForwardAnalyzer(
            data=sample_data,
            is_window_days=60,
            oos_window_days=30,
            step_days=30
        )
        
        # Запускаем оптимизацию
        results = await analyzer.run_async(
            strategy_config=simple_strategy_config,
            param_space=param_space,
            metric="sharpe_ratio"
        )
        
        # Проверяем структуру результатов
        assert "windows" in results
        assert "summary" in results
        assert "config" in results
        
        # Проверяем summary
        summary = results["summary"]
        assert "total_windows" in summary
        assert "positive_windows" in summary
        assert "total_oos_profit" in summary


@pytest.mark.benchmark
class TestWalkForwardPerformance:
    """Performance тесты"""
    
    def test_window_creation_speed(self, sample_data, benchmark):
        """Тест скорости создания окон"""
        
        def create_analyzer():
            return WalkForwardAnalyzer(
                data=sample_data,
                is_window_days=60,
                oos_window_days=30,
                step_days=15
            )
        
        analyzer = benchmark(create_analyzer)
        assert len(analyzer.windows) > 0
    
    def test_large_dataset(self):
        """Тест с большим датасетом"""
        # 2 года данных по 1H
        large_data = pd.DataFrame({
            "timestamp": pd.date_range(start="2023-01-01", end="2024-12-31", freq="1H"),
            "open": np.random.randn(17520) * 100 + 50000,
            "high": np.random.randn(17520) * 100 + 50100,
            "low": np.random.randn(17520) * 100 + 49900,
            "close": np.random.randn(17520) * 100 + 50000,
            "volume": np.random.randint(100, 1000, 17520)
        })
        
        analyzer = WalkForwardAnalyzer(
            data=large_data,
            is_window_days=90,
            oos_window_days=30,
            step_days=30
        )
        
        # Проверяем что создание прошло успешно
        assert len(analyzer.windows) > 0
        assert len(analyzer.windows) < 100  # Разумное количество окон


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
