"""
Демонстрация Monte Carlo Simulation.

Показывает:
- Создание симулятора
- Запуск симуляции на примере сделок
- Вывод метрик и вероятностей
- Анализ доверительных интервалов
"""

import sys
from pathlib import Path

# Добавить backend в sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.optimization import MonteCarloSimulator


def main():
    """Демонстрация Monte Carlo."""
    
    print("=" * 80)
    print("MONTE CARLO SIMULATION DEMO")
    print("=" * 80)
    
    # Пример сделок (реалистичная стратегия)
    trades = [
        {'pnl': 150, 'pnl_pct': 1.5},
        {'pnl': -80, 'pnl_pct': -0.8},
        {'pnl': 200, 'pnl_pct': 2.0},
        {'pnl': 120, 'pnl_pct': 1.2},
        {'pnl': -100, 'pnl_pct': -1.0},
        {'pnl': 180, 'pnl_pct': 1.8},
        {'pnl': -60, 'pnl_pct': -0.6},
        {'pnl': 250, 'pnl_pct': 2.5},
        {'pnl': -90, 'pnl_pct': -0.9},
        {'pnl': 300, 'pnl_pct': 3.0},
    ]
    
    initial_capital = 10000
    
    # Создать симулятор
    mc = MonteCarloSimulator(
        n_simulations=1000,
        ruin_threshold=20.0,
        random_seed=42
    )
    
    # Запустить симуляцию
    result = mc.run(trades, initial_capital=initial_capital)
    
    print("\n" + "=" * 80)
    print("РЕЗУЛЬТАТЫ СИМУЛЯЦИИ")
    print("=" * 80)
    
    print(f"\n📊 Базовые метрики:")
    print(f"   Original Return:    {result.original_return:>8.2f}%")
    print(f"   Mean Return:        {result.mean_return:>8.2f}%")
    print(f"   Median Return:      {result.median_return:>8.2f}%")
    print(f"   Std Return:         {result.std_return:>8.2f}%")
    
    print(f"\n📈 Percentiles:")
    print(f"   5th Percentile:     {result.percentile_5:>8.2f}%")
    print(f"   25th Percentile:    {result.percentile_25:>8.2f}%")
    print(f"   75th Percentile:    {result.percentile_75:>8.2f}%")
    print(f"   95th Percentile:    {result.percentile_95:>8.2f}%")
    
    print(f"\n🎯 Вероятности:")
    print(f"   Prob Profit:        {result.prob_profit:>8.1%}")
    print(f"   Prob Ruin (>20%):   {result.prob_ruin:>8.1%}")
    
    print(f"\n📍 Рейтинг оригинальной стратегии:")
    print(f"   Percentile Rank:    {result.original_percentile:>8.1f}%")
    
    # Доверительные интервалы
    ci_95 = mc.get_confidence_interval(result, confidence=0.95)
    ci_90 = mc.get_confidence_interval(result, confidence=0.90)
    ci_80 = mc.get_confidence_interval(result, confidence=0.80)
    
    print(f"\n📊 Доверительные интервалы:")
    print(f"   95% CI: [{ci_95[0]:>6.2f}%, {ci_95[1]:>6.2f}%]")
    print(f"   90% CI: [{ci_90[0]:>6.2f}%, {ci_90[1]:>6.2f}%]")
    print(f"   80% CI: [{ci_80[0]:>6.2f}%, {ci_80[1]:>6.2f}%]")
    
    # Risk of Ruin для разных уровней
    ruin_10 = mc.get_risk_of_ruin(result, ruin_level=10.0)
    ruin_20 = mc.get_risk_of_ruin(result, ruin_level=20.0)
    ruin_30 = mc.get_risk_of_ruin(result, ruin_level=30.0)
    
    print(f"\n⚠️  Risk of Ruin:")
    print(f"   Drawdown >= 10%:    {ruin_10:>8.1%}")
    print(f"   Drawdown >= 20%:    {ruin_20:>8.1%}")
    print(f"   Drawdown >= 30%:    {ruin_30:>8.1%}")
    
    print("\n" + "=" * 80)
    print("ИНТЕРПРЕТАЦИЯ")
    print("=" * 80)
    
    print(f"\n✨ Выводы:")
    
    if result.prob_profit > 0.7:
        print(f"   ✅ Высокая вероятность прибыли ({result.prob_profit:.1%})")
    elif result.prob_profit > 0.5:
        print(f"   ⚡ Умеренная вероятность прибыли ({result.prob_profit:.1%})")
    else:
        print(f"   ❌ Низкая вероятность прибыли ({result.prob_profit:.1%})")
    
    if result.prob_ruin < 0.1:
        print(f"   ✅ Низкий риск разорения ({result.prob_ruin:.1%})")
    elif result.prob_ruin < 0.3:
        print(f"   ⚡ Умеренный риск разорения ({result.prob_ruin:.1%})")
    else:
        print(f"   ❌ Высокий риск разорения ({result.prob_ruin:.1%})")
    
    if result.std_return < 2.0:
        print(f"   ✅ Низкая вариативность результатов ({result.std_return:.2f}%)")
    elif result.std_return < 5.0:
        print(f"   ⚡ Умеренная вариативность результатов ({result.std_return:.2f}%)")
    else:
        print(f"   ❌ Высокая вариативность результатов ({result.std_return:.2f}%)")
    
    if result.original_percentile > 60:
        print(f"   ✅ Оригинальная стратегия в топ {100 - result.original_percentile:.0f}%")
    elif result.original_percentile > 40:
        print(f"   ⚡ Оригинальная стратегия в среднем диапазоне")
    else:
        print(f"   ❌ Оригинальная стратегия ниже среднего")
    
    print(f"\n💡 Рекомендации:")
    
    if result.prob_profit > 0.6 and result.prob_ruin < 0.2:
        print(f"   → Стратегия показывает хорошую устойчивость")
        print(f"   → Можно рассматривать для реального применения")
    elif result.prob_profit > 0.5 and result.prob_ruin < 0.3:
        print(f"   → Стратегия требует дополнительной оптимизации")
        print(f"   → Рекомендуется снизить риск на сделку")
    else:
        print(f"   → Стратегия нуждается в серьёзной доработке")
        print(f"   → Пересмотрите параметры управления рисками")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
