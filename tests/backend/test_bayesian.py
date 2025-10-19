"""
Unit Tests for Bayesian Optimization

Тесты для проверки корректности работы Bayesian оптимизации с Optuna.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any

import numpy as np
import pandas as pd
import pytest

from backend.core.bayesian import BayesianOptimizer


@pytest.fixture
def sample_data():
    """Создаёт тестовые данные для оптимизации"""
    dates = pd.date_range(start="2024-01-01", end="2024-06-30", freq="1H")
    
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
    """Простая конфигурация стратегии"""
    return {
        "type": "MA_Crossover",
        "initial_capital": 10000.0,
        "commission": 0.001,
    }


@pytest.fixture
def int_param_space():
    """Пространство параметров с int типами"""
    return {
        "fast_period": {
            "type": "int",
            "low": 5,
            "high": 50
        },
        "slow_period": {
            "type": "int",
            "low": 20,
            "high": 200
        }
    }


@pytest.fixture
def float_param_space():
    """Пространство параметров с float типами"""
    return {
        "threshold": {
            "type": "float",
            "low": 0.001,
            "high": 0.1,
            "log": True  # Логарифмическая шкала
        },
        "multiplier": {
            "type": "float",
            "low": 1.0,
            "high": 3.0,
            "step": 0.1
        }
    }


@pytest.fixture
def categorical_param_space():
    """Пространство параметров с categorical типами"""
    return {
        "indicator": {
            "type": "categorical",
            "choices": ["SMA", "EMA", "WMA"]
        },
        "signal_type": {
            "type": "categorical",
            "choices": ["cross", "threshold", "divergence"]
        }
    }


@pytest.fixture
def mixed_param_space():
    """Смешанное пространство параметров"""
    return {
        "period": {
            "type": "int",
            "low": 10,
            "high": 100
        },
        "threshold": {
            "type": "float",
            "low": 0.01,
            "high": 0.1
        },
        "method": {
            "type": "categorical",
            "choices": ["simple", "weighted", "exponential"]
        }
    }


class TestBayesianOptimizer:
    """Тесты для BayesianOptimizer"""
    
    def test_optimizer_initialization(self, sample_data):
        """Тест инициализации оптимизатора"""
        optimizer = BayesianOptimizer(
            data=sample_data,
            initial_capital=10000.0,
            commission=0.001,
            n_trials=10,
            n_jobs=1,
            random_state=42
        )
        
        assert optimizer.initial_capital == 10000.0
        assert optimizer.commission == 0.001
        assert optimizer.n_trials == 10
        assert optimizer.n_jobs == 1
        assert optimizer.random_state == 42
        assert optimizer.study is None  # До запуска оптимизации
    
    def test_optimizer_with_defaults(self, sample_data):
        """Тест с дефолтными параметрами"""
        optimizer = BayesianOptimizer(data=sample_data)
        
        assert optimizer.n_trials == 100
        assert optimizer.n_jobs == 1
        assert optimizer.random_state is None


@pytest.mark.asyncio
@pytest.mark.slow
class TestBayesianOptimization:
    """Integration тесты оптимизации (медленные)"""
    
    async def test_int_parameters_optimization(
        self, 
        sample_data, 
        simple_strategy_config, 
        int_param_space
    ):
        """
        Тест оптимизации с int параметрами
        
        ПРИМЕЧАНИЕ: Требует реализованного BacktestEngine
        """
        pytest.skip("Requires BacktestEngine implementation")
        
        optimizer = BayesianOptimizer(
            data=sample_data,
            n_trials=5,  # Малое количество для быстрого теста
            random_state=42
        )
        
        results = await optimizer.optimize_async(
            strategy_config=simple_strategy_config,
            param_space=int_param_space,
            metric="sharpe_ratio",
            direction="maximize",
            show_progress=False
        )
        
        # Проверяем структуру результатов
        assert "best_params" in results
        assert "best_value" in results
        assert "best_trial" in results
        assert "trials_data" in results
        assert "statistics" in results
        
        # Проверяем типы параметров
        best_params = results["best_params"]
        assert isinstance(best_params["fast_period"], int)
        assert isinstance(best_params["slow_period"], int)
        
        # Проверяем диапазоны
        assert 5 <= best_params["fast_period"] <= 50
        assert 20 <= best_params["slow_period"] <= 200
        
        # Проверяем статистику
        stats = results["statistics"]
        assert stats["total_trials"] == 5
        assert stats["completed_trials"] <= 5
    
    async def test_float_parameters_optimization(
        self, 
        sample_data, 
        simple_strategy_config, 
        float_param_space
    ):
        """Тест оптимизации с float параметрами"""
        pytest.skip("Requires BacktestEngine implementation")
        
        optimizer = BayesianOptimizer(
            data=sample_data,
            n_trials=5,
            random_state=42
        )
        
        results = await optimizer.optimize_async(
            strategy_config=simple_strategy_config,
            param_space=float_param_space,
            metric="sharpe_ratio",
            show_progress=False
        )
        
        # Проверяем типы
        best_params = results["best_params"]
        assert isinstance(best_params["threshold"], float)
        assert isinstance(best_params["multiplier"], float)
        
        # Проверяем диапазоны
        assert 0.001 <= best_params["threshold"] <= 0.1
        assert 1.0 <= best_params["multiplier"] <= 3.0
    
    async def test_categorical_parameters_optimization(
        self, 
        sample_data, 
        simple_strategy_config, 
        categorical_param_space
    ):
        """Тест оптимизации с categorical параметрами"""
        pytest.skip("Requires BacktestEngine implementation")
        
        optimizer = BayesianOptimizer(
            data=sample_data,
            n_trials=5,
            random_state=42
        )
        
        results = await optimizer.optimize_async(
            strategy_config=simple_strategy_config,
            param_space=categorical_param_space,
            metric="sharpe_ratio",
            show_progress=False
        )
        
        # Проверяем что выбраны значения из choices
        best_params = results["best_params"]
        assert best_params["indicator"] in ["SMA", "EMA", "WMA"]
        assert best_params["signal_type"] in ["cross", "threshold", "divergence"]
    
    async def test_mixed_parameters_optimization(
        self, 
        sample_data, 
        simple_strategy_config, 
        mixed_param_space
    ):
        """Тест оптимизации со смешанными типами параметров"""
        pytest.skip("Requires BacktestEngine implementation")
        
        optimizer = BayesianOptimizer(
            data=sample_data,
            n_trials=10,
            random_state=42
        )
        
        results = await optimizer.optimize_async(
            strategy_config=simple_strategy_config,
            param_space=mixed_param_space,
            metric="sharpe_ratio",
            show_progress=False
        )
        
        best_params = results["best_params"]
        
        # Проверяем все три типа
        assert isinstance(best_params["period"], int)
        assert isinstance(best_params["threshold"], float)
        assert isinstance(best_params["method"], str)
        
        assert best_params["method"] in ["simple", "weighted", "exponential"]
    
    async def test_minimize_direction(
        self, 
        sample_data, 
        simple_strategy_config, 
        int_param_space
    ):
        """Тест минимизации метрики"""
        pytest.skip("Requires BacktestEngine implementation")
        
        optimizer = BayesianOptimizer(
            data=sample_data,
            n_trials=5,
            random_state=42
        )
        
        results = await optimizer.optimize_async(
            strategy_config=simple_strategy_config,
            param_space=int_param_space,
            metric="max_drawdown",  # Минимизируем просадку
            direction="minimize",
            show_progress=False
        )
        
        assert results["direction"] == "minimize"
        assert results["metric"] == "max_drawdown"


class TestParameterImportance:
    """Тесты для вычисления важности параметров"""
    
    def test_get_importance_before_optimization(self, sample_data):
        """Тест вызова get_importance до оптимизации"""
        optimizer = BayesianOptimizer(data=sample_data, n_trials=10)
        
        with pytest.raises(ValueError, match="Необходимо сначала запустить"):
            optimizer.get_importance()
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_get_importance_after_optimization(
        self, 
        sample_data, 
        simple_strategy_config, 
        int_param_space
    ):
        """Тест вычисления важности после оптимизации"""
        pytest.skip("Requires BacktestEngine implementation")
        
        optimizer = BayesianOptimizer(
            data=sample_data,
            n_trials=10,
            random_state=42
        )
        
        await optimizer.optimize_async(
            strategy_config=simple_strategy_config,
            param_space=int_param_space,
            metric="sharpe_ratio",
            show_progress=False
        )
        
        importance = optimizer.get_importance()
        
        # Проверяем структуру
        assert isinstance(importance, dict)
        assert "fast_period" in importance
        assert "slow_period" in importance
        
        # Проверяем что importance это числа от 0 до 1
        for param, value in importance.items():
            assert 0 <= value <= 1


class TestBayesianPerformance:
    """Performance тесты"""
    
    def test_initialization_speed(self, sample_data, benchmark):
        """Тест скорости инициализации"""
        
        def create_optimizer():
            return BayesianOptimizer(
                data=sample_data,
                n_trials=100,
                random_state=42
            )
        
        optimizer = benchmark(create_optimizer)
        assert optimizer.n_trials == 100
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_small_vs_large_n_trials(
        self, 
        sample_data, 
        simple_strategy_config, 
        int_param_space
    ):
        """Сравнение скорости с разным количеством trials"""
        pytest.skip("Requires BacktestEngine implementation")
        
        import time
        
        # Малое количество
        start = time.time()
        optimizer_small = BayesianOptimizer(data=sample_data, n_trials=5)
        await optimizer_small.optimize_async(
            strategy_config=simple_strategy_config,
            param_space=int_param_space,
            metric="sharpe_ratio",
            show_progress=False
        )
        time_small = time.time() - start
        
        # Большое количество
        start = time.time()
        optimizer_large = BayesianOptimizer(data=sample_data, n_trials=20)
        await optimizer_large.optimize_async(
            strategy_config=simple_strategy_config,
            param_space=int_param_space,
            metric="sharpe_ratio",
            show_progress=False
        )
        time_large = time.time() - start
        
        # Проверяем что время растёт примерно линейно
        assert time_large > time_small
        assert time_large < time_small * 5  # Не более чем в 5 раз


class TestEdgeCases:
    """Тесты граничных случаев"""
    
    def test_invalid_param_type(self, sample_data, simple_strategy_config):
        """Тест с неверным типом параметра"""
        pytest.skip("Requires BacktestEngine implementation")
        
        invalid_param_space = {
            "period": {
                "type": "invalid_type",  # Неверный тип
                "low": 10,
                "high": 100
            }
        }
        
        optimizer = BayesianOptimizer(data=sample_data, n_trials=5)
        
        with pytest.raises(ValueError, match="Unknown parameter type"):
            asyncio.run(optimizer.optimize_async(
                strategy_config=simple_strategy_config,
                param_space=invalid_param_space,
                metric="sharpe_ratio"
            ))
    
    def test_empty_param_space(self, sample_data, simple_strategy_config):
        """Тест с пустым пространством параметров"""
        pytest.skip("Requires BacktestEngine implementation")
        
        optimizer = BayesianOptimizer(data=sample_data, n_trials=5)
        
        # Пустое пространство параметров должно вызвать ошибку
        # (либо Optuna, либо наш код)
        with pytest.raises(Exception):
            asyncio.run(optimizer.optimize_async(
                strategy_config=simple_strategy_config,
                param_space={},
                metric="sharpe_ratio"
            ))
    
    def test_single_trial(self, sample_data, simple_strategy_config, int_param_space):
        """Тест с одним trial"""
        pytest.skip("Requires BacktestEngine implementation")
        
        optimizer = BayesianOptimizer(data=sample_data, n_trials=1)
        
        results = asyncio.run(optimizer.optimize_async(
            strategy_config=simple_strategy_config,
            param_space=int_param_space,
            metric="sharpe_ratio",
            show_progress=False
        ))
        
        # С одним trial результаты должны быть, но importance может не считаться
        assert "best_params" in results
        assert results["statistics"]["total_trials"] == 1


@pytest.mark.benchmark
class TestBayesianVsGridSearch:
    """Сравнение Bayesian с Grid Search"""
    
    def test_convergence_speed(self):
        """
        Тест что Bayesian сходится быстрее Grid Search
        
        Этот тест требует реализации Grid Search для сравнения
        """
        pytest.skip("Requires Grid Search implementation for comparison")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
