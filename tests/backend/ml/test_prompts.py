"""
Тесты для backend/ml/prompts.py
AI prompt templates library для ML-оптимизации торговых стратегий
"""
import pytest
import json
from backend.ml.prompts import (
    # Константы промптов
    OPTIMIZATION_TEMPLATE,
    FEATURE_ENGINEERING_TEMPLATE,
    ANALYSIS_TEMPLATE,
    NEW_STRATEGIES_TEMPLATE,
    WALK_FORWARD_TEMPLATE,
    ENSEMBLE_STRATEGIES_TEMPLATE,
    RISK_MANAGEMENT_TEMPLATE,
    MARKET_REGIME_DETECTION_TEMPLATE,
    HYPERPARAMETER_SEARCH_TEMPLATE,
    OVERFITTING_DETECTION_TEMPLATE,
    STRATEGY_COMPARISON_TEMPLATE,
    # Helper functions
    get_optimization_prompt,
    get_feature_engineering_prompt,
    get_analysis_prompt,
    get_new_strategies_prompt,
)


class TestPromptConstants:
    """Тесты для проверки структуры prompt constants"""
    
    def test_optimization_template_structure(self):
        """Optimization template должен содержать все placeholder'ы"""
        assert "{strategy_description}" in OPTIMIZATION_TEMPLATE
        assert "{param_space}" in OPTIMIZATION_TEMPLATE
        assert "{optimization_goal}" in OPTIMIZATION_TEMPLATE
        assert "{ml_library}" in OPTIMIZATION_TEMPLATE
        assert "Python" in OPTIMIZATION_TEMPLATE
        assert "ВАЖНО" in OPTIMIZATION_TEMPLATE
    
    def test_feature_engineering_template_structure(self):
        """Feature engineering template должен содержать все placeholder'ы"""
        assert "{data_description}" in FEATURE_ENGINEERING_TEMPLATE
        assert "{strategy_type}" in FEATURE_ENGINEERING_TEMPLATE
        assert "SMA" in FEATURE_ENGINEERING_TEMPLATE
        assert "RSI" in FEATURE_ENGINEERING_TEMPLATE
        assert "create_features" in FEATURE_ENGINEERING_TEMPLATE
    
    def test_analysis_template_structure(self):
        """Analysis template должен содержать все placeholder'ы"""
        assert "{strategy_description}" in ANALYSIS_TEMPLATE
        assert "{results_json}" in ANALYSIS_TEMPLATE
        assert "переобучения" in ANALYSIS_TEMPLATE
        assert "Рекомендации" in ANALYSIS_TEMPLATE
    
    def test_new_strategies_template_structure(self):
        """New strategies template должен содержать все placeholder'ы"""
        assert "{market_data_summary}" in NEW_STRATEGIES_TEMPLATE
        assert "{current_strategy_performance}" in NEW_STRATEGIES_TEMPLATE
        assert "{constraints}" in NEW_STRATEGIES_TEMPLATE
        assert "CatBoost" in NEW_STRATEGIES_TEMPLATE
        assert "Sharpe" in NEW_STRATEGIES_TEMPLATE
    
    def test_walk_forward_template_structure(self):
        """Walk-forward template должен содержать все placeholder'ы"""
        assert "{strategy_description}" in WALK_FORWARD_TEMPLATE
        assert "{param_space}" in WALK_FORWARD_TEMPLATE
        assert "In-Sample" in WALK_FORWARD_TEMPLATE
        assert "Out-Of-Sample" in WALK_FORWARD_TEMPLATE
    
    def test_ensemble_strategies_template_structure(self):
        """Ensemble strategies template должен содержать все placeholder'ы"""
        assert "{available_strategies}" in ENSEMBLE_STRATEGIES_TEMPLATE
        assert "EnsembleStrategy" in ENSEMBLE_STRATEGIES_TEMPLATE
        assert "CatBoost" in ENSEMBLE_STRATEGIES_TEMPLATE
    
    def test_risk_management_template_structure(self):
        """Risk management template должен содержать все placeholder'ы"""
        assert "{market_data_description}" in RISK_MANAGEMENT_TEMPLATE
        assert "MLRiskManager" in RISK_MANAGEMENT_TEMPLATE
        assert "Kelly Criterion" in RISK_MANAGEMENT_TEMPLATE
        assert "stop-loss" in RISK_MANAGEMENT_TEMPLATE
    
    def test_market_regime_detection_template_structure(self):
        """Market regime detection template должен содержать структуру"""
        assert "MarketRegimeDetector" in MARKET_REGIME_DETECTION_TEMPLATE
        assert "Trending" in MARKET_REGIME_DETECTION_TEMPLATE
        assert "Ranging" in MARKET_REGIME_DETECTION_TEMPLATE
        assert "CatBoost" in MARKET_REGIME_DETECTION_TEMPLATE
    
    def test_hyperparameter_search_template_structure(self):
        """Hyperparameter search template должен содержать структуру"""
        assert "HyperparameterOptimizer" in HYPERPARAMETER_SEARCH_TEMPLATE
        assert "Optuna" in HYPERPARAMETER_SEARCH_TEMPLATE
        assert "Multi-objective" in HYPERPARAMETER_SEARCH_TEMPLATE
        assert "Pareto Front" in HYPERPARAMETER_SEARCH_TEMPLATE
    
    def test_overfitting_detection_template_structure(self):
        """Overfitting detection template должен содержать placeholder'ы"""
        assert "{optimization_results}" in OVERFITTING_DETECTION_TEMPLATE
        assert "переобучения" in OVERFITTING_DETECTION_TEMPLATE
        assert "In-Sample" in OVERFITTING_DETECTION_TEMPLATE
        assert "регуляризации" in OVERFITTING_DETECTION_TEMPLATE
    
    def test_strategy_comparison_template_structure(self):
        """Strategy comparison template должен содержать placeholder'ы"""
        assert "{strategies_json}" in STRATEGY_COMPARISON_TEMPLATE
        assert "Sharpe Ratio" in STRATEGY_COMPARISON_TEMPLATE
        assert "Sortino Ratio" in STRATEGY_COMPARISON_TEMPLATE
        assert "Max Drawdown" in STRATEGY_COMPARISON_TEMPLATE


class TestGetOptimizationPrompt:
    """Тесты для get_optimization_prompt()"""
    
    def test_basic_formatting(self):
        """Должен форматировать промпт с базовыми параметрами"""
        result = get_optimization_prompt(
            strategy_description="Test strategy",
            param_space={"param1": [1, 2, 3]},
            optimization_goal="Sharpe Ratio",
            ml_library="catboost"
        )
        
        assert "Test strategy" in result
        assert "Sharpe Ratio" in result
        assert "catboost" in result
        assert "param1" in result
    
    def test_param_space_json_formatting(self):
        """Должен форматировать param_space как JSON"""
        result = get_optimization_prompt(
            strategy_description="Test",
            param_space={"rsi_period": [14, 21], "take_profit": [0.02, 0.03]},
            optimization_goal="Win Rate",
            ml_library="optuna"
        )
        
        assert "rsi_period" in result
        assert "take_profit" in result
        # Проверяем что параметры присутствуют в результате
        assert "14" in result and "21" in result
        assert "0.02" in result and "0.03" in result
    
    def test_with_complex_param_space(self):
        """Должен работать со сложным param_space"""
        result = get_optimization_prompt(
            strategy_description="SR/RSI стратегия",
            param_space={
                "sr_lookback": [50, 100, 150],
                "rsi_period": [14, 21],
                "take_profit_pct": [0.02, 0.03],
                "stop_loss_pct": [0.01, 0.015]
            },
            optimization_goal="Sharpe Ratio",
            ml_library="catboost"
        )
        
        assert "SR/RSI стратегия" in result
        assert "sr_lookback" in result
        assert "rsi_period" in result
        assert "take_profit_pct" in result
        assert "stop_loss_pct" in result
    
    def test_with_russian_text(self):
        """Должен корректно работать с русским текстом"""
        result = get_optimization_prompt(
            strategy_description="Стратегия Bollinger Bands с RSI фильтром",
            param_space={"период": [20, 50]},
            optimization_goal="Коэффициент Шарпа",
            ml_library="optuna"
        )
        
        assert "Стратегия Bollinger Bands" in result
        assert "Коэффициент Шарпа" in result
        assert "период" in result
    
    def test_all_placeholders_replaced(self):
        """Все placeholder'ы должны быть заменены"""
        result = get_optimization_prompt(
            strategy_description="Test",
            param_space={"p": [1]},
            optimization_goal="Goal",
            ml_library="lib"
        )
        
        assert "{strategy_description}" not in result
        assert "{param_space}" not in result
        assert "{optimization_goal}" not in result
        assert "{ml_library}" not in result


class TestGetFeatureEngineeringPrompt:
    """Тесты для get_feature_engineering_prompt()"""
    
    def test_basic_formatting(self):
        """Должен форматировать промпт с базовыми параметрами"""
        result = get_feature_engineering_prompt(
            data_description="OHLCV data for BTCUSDT",
            strategy_type="Momentum"
        )
        
        assert "OHLCV data for BTCUSDT" in result
        assert "Momentum" in result
    
    def test_all_placeholders_replaced(self):
        """Все placeholder'ы должны быть заменены"""
        result = get_feature_engineering_prompt(
            data_description="Test data",
            strategy_type="Mean Reversion"
        )
        
        assert "{data_description}" not in result
        assert "{strategy_type}" not in result
    
    def test_with_russian_text(self):
        """Должен корректно работать с русским текстом"""
        result = get_feature_engineering_prompt(
            data_description="Данные OHLCV для всех пар Bybit",
            strategy_type="Трендовая стратегия"
        )
        
        assert "Данные OHLCV" in result
        assert "Трендовая стратегия" in result


class TestGetAnalysisPrompt:
    """Тесты для get_analysis_prompt()"""
    
    def test_basic_formatting(self):
        """Должен форматировать промпт с базовыми параметрами"""
        results = {"sharpe": 2.5, "win_rate": 0.65}
        result = get_analysis_prompt(
            strategy_description="Test strategy",
            results_json=json.dumps(results, indent=2)
        )
        
        assert "Test strategy" in result
        assert "sharpe" in result
        assert "2.5" in result
    
    def test_all_placeholders_replaced(self):
        """Все placeholder'ы должны быть заменены"""
        result = get_analysis_prompt(
            strategy_description="Test",
            results_json='{"metric": 1.0}'
        )
        
        assert "{strategy_description}" not in result
        assert "{results_json}" not in result
    
    def test_with_complex_results(self):
        """Должен работать со сложными результатами"""
        results = {
            "sharpe_ratio": 2.1,
            "sortino_ratio": 3.0,
            "max_drawdown": -0.15,
            "win_rate": 0.62,
            "total_trades": 150,
            "profit_factor": 1.8
        }
        result = get_analysis_prompt(
            strategy_description="SR/RSI оптимизированная",
            results_json=json.dumps(results, indent=2, ensure_ascii=False)
        )
        
        assert "SR/RSI" in result
        assert "sharpe_ratio" in result
        assert "max_drawdown" in result


class TestGetNewStrategiesPrompt:
    """Тесты для get_new_strategies_prompt()"""
    
    def test_basic_formatting(self):
        """Должен форматировать промпт с базовыми параметрами"""
        result = get_new_strategies_prompt(
            market_data_summary="Bull market",
            current_strategy_performance="Sharpe: 1.5"
        )
        
        assert "Bull market" in result
        assert "Sharpe: 1.5" in result
    
    def test_with_default_constraints(self):
        """Должен использовать дефолтные constraints"""
        result = get_new_strategies_prompt(
            market_data_summary="Test",
            current_strategy_performance="Test"
        )
        
        assert "Без ограничений" in result
    
    def test_with_custom_constraints(self):
        """Должен использовать кастомные constraints"""
        result = get_new_strategies_prompt(
            market_data_summary="Test",
            current_strategy_performance="Test",
            constraints="Max leverage 3x, только USDT пары"
        )
        
        assert "Max leverage 3x" in result
        assert "только USDT пары" in result
    
    def test_all_placeholders_replaced(self):
        """Все placeholder'ы должны быть заменены"""
        result = get_new_strategies_prompt(
            market_data_summary="Market summary",
            current_strategy_performance="Performance data",
            constraints="Custom constraints"
        )
        
        assert "{market_data_summary}" not in result
        assert "{current_strategy_performance}" not in result
        assert "{constraints}" not in result


class TestPromptsContentQuality:
    """Тесты для проверки качества контента промптов"""
    
    def test_optimization_template_contains_key_concepts(self):
        """Optimization template должен содержать ключевые концепции"""
        assert "Grid Search" in OPTIMIZATION_TEMPLATE
        assert "Bayesian Optimization" in OPTIMIZATION_TEMPLATE
        assert "кросс-валидацию" in OPTIMIZATION_TEMPLATE
        assert "переобучения" in OPTIMIZATION_TEMPLATE
    
    def test_key_templates_mention_python(self):
        """Основные template'ы должны упоминать Python"""
        templates = [
            OPTIMIZATION_TEMPLATE,
            FEATURE_ENGINEERING_TEMPLATE,
            WALK_FORWARD_TEMPLATE,
        ]
        
        for template in templates:
            assert "Python" in template or "python" in template
    
    def test_key_templates_mention_production_ready(self):
        """Ключевые template'ы должны упоминать production-ready подход"""
        templates = [
            OPTIMIZATION_TEMPLATE,
            WALK_FORWARD_TEMPLATE,
            MARKET_REGIME_DETECTION_TEMPLATE
        ]
        
        for template in templates:
            assert "production" in template.lower()
    
    def test_ml_libraries_mentioned(self):
        """Template'ы должны упоминать современные ML библиотеки"""
        all_content = " ".join([
            OPTIMIZATION_TEMPLATE,
            ENSEMBLE_STRATEGIES_TEMPLATE,
            RISK_MANAGEMENT_TEMPLATE,
            MARKET_REGIME_DETECTION_TEMPLATE,
            HYPERPARAMETER_SEARCH_TEMPLATE
        ])
        
        assert "CatBoost" in all_content or "catboost" in all_content
        assert "XGBoost" in all_content or "xgboost" in all_content
        assert "Optuna" in all_content or "optuna" in all_content


class TestPromptsIntegration:
    """Интеграционные тесты для проверки работы промптов вместе"""
    
    def test_full_optimization_workflow(self):
        """Полный workflow оптимизации стратегии"""
        # 1. Optimization prompt
        opt_prompt = get_optimization_prompt(
            strategy_description="SR/RSI стратегия",
            param_space={"sr_lookback": [50, 100], "rsi_period": [14, 21]},
            optimization_goal="Sharpe Ratio",
            ml_library="catboost"
        )
        assert len(opt_prompt) > 100
        assert "SR/RSI" in opt_prompt
        
        # 2. Feature engineering prompt
        fe_prompt = get_feature_engineering_prompt(
            data_description="OHLCV данные Bybit BTCUSDT 1h",
            strategy_type="Momentum + Mean Reversion"
        )
        assert len(fe_prompt) > 100
        assert "BTCUSDT" in fe_prompt
        
        # 3. Analysis prompt
        results = {
            "sharpe_ratio": 2.1,
            "max_drawdown": -0.12,
            "win_rate": 0.64
        }
        analysis_prompt = get_analysis_prompt(
            strategy_description="SR/RSI оптимизированная",
            results_json=json.dumps(results, indent=2)
        )
        assert len(analysis_prompt) > 100
        assert "2.1" in analysis_prompt
    
    def test_all_helper_functions_work(self):
        """Все helper функции должны работать без ошибок"""
        # Optimization
        get_optimization_prompt("test", {"p": [1]}, "goal", "lib")
        
        # Feature engineering
        get_feature_engineering_prompt("data", "type")
        
        # Analysis
        get_analysis_prompt("strat", "{}")
        
        # New strategies (все 3 случая: no constraints, default, custom)
        get_new_strategies_prompt("market", "perf")
        get_new_strategies_prompt("market", "perf", "custom")


class TestEdgeCases:
    """Тесты для edge cases"""
    
    def test_empty_param_space(self):
        """Должен обработать пустой param_space"""
        result = get_optimization_prompt(
            strategy_description="Test",
            param_space={},
            optimization_goal="Goal",
            ml_library="lib"
        )
        
        assert "Test" in result
        assert "{}" in result
    
    def test_very_long_strategy_description(self):
        """Должен обработать очень длинное описание"""
        long_desc = "Test strategy " * 100
        result = get_optimization_prompt(
            strategy_description=long_desc,
            param_space={"p": [1]},
            optimization_goal="Goal",
            ml_library="lib"
        )
        
        assert long_desc in result
    
    def test_special_characters_in_text(self):
        """Должен обработать специальные символы"""
        result = get_optimization_prompt(
            strategy_description="Strategy with $pecial ch@rs & symbols!",
            param_space={"param": [1, 2]},
            optimization_goal="Goal",
            ml_library="lib"
        )
        
        assert "$pecial" in result
        assert "ch@rs" in result
    
    def test_unicode_in_param_space(self):
        """Должен обработать unicode в param_space"""
        result = get_optimization_prompt(
            strategy_description="Test",
            param_space={"параметр": [10, 20], "период_RSI": [14, 21]},
            optimization_goal="Goal",
            ml_library="lib"
        )
        
        assert "параметр" in result
        assert "период_RSI" in result
    
    def test_json_serialization_doesnt_break(self):
        """JSON сериализация не должна ломаться"""
        complex_params = {
            "param1": [1, 2, 3],
            "param2": [0.01, 0.02],
            "param3": ["value1", "value2"],
            "nested": {"subparam": [10, 20]}
        }
        
        result = get_optimization_prompt(
            strategy_description="Test",
            param_space=complex_params,
            optimization_goal="Goal",
            ml_library="lib"
        )
        
        assert "param1" in result
        assert "nested" in result
        assert "subparam" in result
