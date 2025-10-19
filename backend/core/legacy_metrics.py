# -*- coding: utf-8 -*-
"""
Модуль расчета метрик производительности стратегии
Аналог TradingView Performance Summary
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime

import numpy as np
import pandas as pd


class PerformanceMetrics:
    """Расчет метрик производительности стратегии"""

    def __init__(self, trades_df, initial_capital, equity_curve=None):
        """
        Args:
            trades_df: DataFrame со сделками
                Обязательные колонки: 'pnl', 'status' (open/closed)
                Опциональные: 'commission', 'entry_price', 'exit_price',
                             'bars_in_trade', 'side' (long/short)
            initial_capital: начальный капитал
            equity_curve: Series с историей капитала (индекс = время)
        """
        self.trades = trades_df.copy()
        self.initial_capital = initial_capital
        self.equity_curve = equity_curve
        self.metrics = {}

        if len(self.trades) > 0:
            self._calculate_all()

    def _calculate_all(self):
        """Расчет всех метрик"""
        print(" Расчет метрик производительности...")

        # 1. БАЗОВЫЕ МЕТРИКИ
        self._calculate_basic_metrics()

        # 2. ПРИБЫЛЬ/УБЫТОК
        self._calculate_profit_loss()

        # 3. СТАТИСТИКА СДЕЛОК
        self._calculate_trade_statistics()

        # 4. РИСК МЕТРИКИ
        self._calculate_risk_metrics()

        # 5. КОЭФФИЦИЕНТЫ
        self._calculate_ratios()

        print(" Метрики рассчитаны!")

    def _calculate_basic_metrics(self):
        """Базовые метрики (Обзор)"""
        # Открытая ПР/Уб
        open_trades = self.trades[self.trades["status"] == "open"]
        self.metrics["open_pl"] = open_trades["pnl"].sum() if len(open_trades) > 0 else 0
        self.metrics["open_pl_pct"] = (self.metrics["open_pl"] / self.initial_capital) * 100

        # Закрытые сделки
        closed_trades = self.trades[self.trades["status"] == "closed"]

        # Чистая прибыль
        self.metrics["net_profit"] = closed_trades["pnl"].sum()
        self.metrics["net_profit_pct"] = (self.metrics["net_profit"] / self.initial_capital) * 100

        # Валовая прибыль/убыток
        winning_trades = closed_trades[closed_trades["pnl"] > 0]
        losing_trades = closed_trades[closed_trades["pnl"] < 0]

        self.metrics["gross_profit"] = winning_trades["pnl"].sum()
        self.metrics["gross_profit_pct"] = (
            self.metrics["gross_profit"] / self.initial_capital
        ) * 100

        self.metrics["gross_loss"] = abs(losing_trades["pnl"].sum())
        self.metrics["gross_loss_pct"] = (self.metrics["gross_loss"] / self.initial_capital) * 100

        # Комиссии
        self.metrics["total_commission"] = (
            closed_trades["commission"].sum() if "commission" in closed_trades.columns else 0
        )

        # Максимальное количество контрактов
        if "quantity" in self.trades.columns:
            self.metrics["max_contracts"] = self.trades["quantity"].max()
        else:
            self.metrics["max_contracts"] = 0

    def _calculate_profit_loss(self):
        """Метрики прибыли/убытка"""
        closed_trades = self.trades[self.trades["status"] == "closed"]

        if len(closed_trades) == 0:
            self.metrics["max_runup"] = 0
            self.metrics["max_runup_pct"] = 0
            self.metrics["max_drawdown"] = 0
            self.metrics["max_drawdown_value"] = 0
            self.metrics["buy_hold_return"] = 0
            self.metrics["buy_hold_return_pct"] = 0
            return

        # Максимальный рост средств (Max Runup)
        if self.equity_curve is not None and len(self.equity_curve) > 0:
            runup = self.equity_curve - self.equity_curve.shift(1).fillna(self.initial_capital)
            self.metrics["max_runup"] = runup.max()
            self.metrics["max_runup_pct"] = (self.metrics["max_runup"] / self.initial_capital) * 100
        else:
            self.metrics["max_runup"] = 0
            self.metrics["max_runup_pct"] = 0

        # Максимальная просадка (Max Drawdown)
        if self.equity_curve is not None and len(self.equity_curve) > 0:
            cummax = self.equity_curve.cummax()
            drawdown = self.equity_curve - cummax
            self.metrics["max_drawdown_value"] = abs(drawdown.min())
            self.metrics["max_drawdown"] = (
                (self.metrics["max_drawdown_value"] / cummax.max()) * 100 if cummax.max() > 0 else 0
            )
        else:
            self.metrics["max_drawdown"] = 0
            self.metrics["max_drawdown_value"] = 0

        # Buy & Hold прибыль
        if "entry_price" in closed_trades.columns and "exit_price" in closed_trades.columns:
            first_price = closed_trades.iloc[0]["entry_price"]
            last_price = closed_trades.iloc[-1]["exit_price"]
            self.metrics["buy_hold_return"] = last_price - first_price
            self.metrics["buy_hold_return_pct"] = ((last_price / first_price) - 1) * 100
        else:
            self.metrics["buy_hold_return"] = 0
            self.metrics["buy_hold_return_pct"] = 0

    def _calculate_trade_statistics(self):
        """Статистика сделок"""
        closed_trades = self.trades[self.trades["status"] == "closed"]

        # Всего сделок
        self.metrics["total_trades"] = len(closed_trades)

        # Открытых сделок
        self.metrics["open_trades"] = len(self.trades[self.trades["status"] == "open"])

        if len(closed_trades) == 0:
            self.metrics["winning_trades"] = 0
            self.metrics["losing_trades"] = 0
            self.metrics["win_rate"] = 0
            self.metrics["avg_trade_pl"] = 0
            self.metrics["avg_trade_pl_pct"] = 0
            self.metrics["avg_winning_trade"] = 0
            self.metrics["avg_winning_trade_pct"] = 0
            self.metrics["avg_losing_trade"] = 0
            self.metrics["avg_losing_trade_pct"] = 0
            self.metrics["largest_winning_trade"] = 0
            self.metrics["largest_winning_trade_pct"] = 0
            self.metrics["largest_losing_trade"] = 0
            self.metrics["largest_losing_trade_pct"] = 0
            return

        # Прибыльные/убыточные
        winning_trades = closed_trades[closed_trades["pnl"] > 0]
        losing_trades = closed_trades[closed_trades["pnl"] < 0]

        self.metrics["winning_trades"] = len(winning_trades)
        self.metrics["losing_trades"] = len(losing_trades)

        # Процент прибыльных
        self.metrics["win_rate"] = len(winning_trades) / len(closed_trades) * 100

        # Средняя ПР/Уб
        self.metrics["avg_trade_pl"] = closed_trades["pnl"].mean()
        self.metrics["avg_trade_pl_pct"] = (
            self.metrics["avg_trade_pl"] / self.initial_capital
        ) * 100

        # Средняя прибыль/убыток
        self.metrics["avg_winning_trade"] = (
            winning_trades["pnl"].mean() if len(winning_trades) > 0 else 0
        )
        self.metrics["avg_winning_trade_pct"] = (
            (self.metrics["avg_winning_trade"] / self.initial_capital) * 100
            if self.metrics["avg_winning_trade"] != 0
            else 0
        )

        self.metrics["avg_losing_trade"] = (
            losing_trades["pnl"].mean() if len(losing_trades) > 0 else 0
        )
        self.metrics["avg_losing_trade_pct"] = (
            (self.metrics["avg_losing_trade"] / self.initial_capital) * 100
            if self.metrics["avg_losing_trade"] != 0
            else 0
        )

        # Самая прибыльная/убыточная сделка
        self.metrics["largest_winning_trade"] = (
            winning_trades["pnl"].max() if len(winning_trades) > 0 else 0
        )
        self.metrics["largest_winning_trade_pct"] = (
            (self.metrics["largest_winning_trade"] / self.initial_capital) * 100
            if self.metrics["largest_winning_trade"] != 0
            else 0
        )

        self.metrics["largest_losing_trade"] = (
            losing_trades["pnl"].min() if len(losing_trades) > 0 else 0
        )
        self.metrics["largest_losing_trade_pct"] = (
            (self.metrics["largest_losing_trade"] / self.initial_capital) * 100
            if self.metrics["largest_losing_trade"] != 0
            else 0
        )

        # Среднее количество баров в позиции
        if "bars_in_trade" in closed_trades.columns:
            self.metrics["avg_bars_in_trade"] = closed_trades["bars_in_trade"].mean()
            self.metrics["avg_bars_winning"] = (
                winning_trades["bars_in_trade"].mean() if len(winning_trades) > 0 else 0
            )
            self.metrics["avg_bars_losing"] = (
                losing_trades["bars_in_trade"].mean() if len(losing_trades) > 0 else 0
            )
        else:
            self.metrics["avg_bars_in_trade"] = 0
            self.metrics["avg_bars_winning"] = 0
            self.metrics["avg_bars_losing"] = 0

    def _calculate_risk_metrics(self):
        """Метрики риска"""
        closed_trades = self.trades[self.trades["status"] == "closed"]

        if len(closed_trades) == 0:
            self.metrics["sharpe_ratio"] = 0
            self.metrics["sortino_ratio"] = 0
            return

        # Коэффициент Шарпа
        returns = closed_trades["pnl"] / self.initial_capital
        if returns.std() > 0:
            self.metrics["sharpe_ratio"] = returns.mean() / returns.std() * np.sqrt(252)
        else:
            self.metrics["sharpe_ratio"] = 0

        # Коэффициент Сортино
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0 and downside_returns.std() > 0:
            self.metrics["sortino_ratio"] = returns.mean() / downside_returns.std() * np.sqrt(252)
        else:
            self.metrics["sortino_ratio"] = 0

    def _calculate_ratios(self):
        """Коэффициенты"""
        # Фактор прибыли (Profit Factor)
        if self.metrics.get("gross_loss", 0) > 0:
            self.metrics["profit_factor"] = (
                self.metrics["gross_profit"] / self.metrics["gross_loss"]
            )
        else:
            self.metrics["profit_factor"] = 0

        # Коэффициент средней прибыли / среднего убытка
        if self.metrics.get("avg_losing_trade", 0) != 0:
            self.metrics["avg_win_loss_ratio"] = abs(
                self.metrics["avg_winning_trade"] / self.metrics["avg_losing_trade"]
            )
        else:
            self.metrics["avg_win_loss_ratio"] = 0

    def get_summary(self):
        """Получить сводку всех метрик"""
        return self.metrics

    def print_report(self):
        """Вывод красивого отчета (как в TradingView)"""
        print("\n" + "=" * 70)
        print(" ОТЧЕТ О ПРОИЗВОДИТЕЛЬНОСТИ СТРАТЕГИИ")
        print("=" * 70)

        print("\n【ОБЗОР】")
        print(
            f"  Открыть ПР/Уб:          {self.metrics.get('open_pl', 0):>10.2f} USDT  ({self.metrics.get('open_pl_pct', 0):>6.2f}%)"
        )
        print(
            f"  Чистая прибыль:         {self.metrics.get('net_profit', 0):>10.2f} USDT  ({self.metrics.get('net_profit_pct', 0):>6.2f}%)"
        )
        print(
            f"  Валовая прибыль:        {self.metrics.get('gross_profit', 0):>10.2f} USDT  ({self.metrics.get('gross_profit_pct', 0):>6.2f}%)"
        )
        print(
            f"  Валовый убыток:         {self.metrics.get('gross_loss', 0):>10.2f} USDT  ({self.metrics.get('gross_loss_pct', 0):>6.2f}%)"
        )
        print(f"  Выплаченная комиссия:   {self.metrics.get('total_commission', 0):>10.2f} USDT")
        print(f"  Макс. контрактов:       {self.metrics.get('max_contracts', 0):>10.0f}")

        print("\n【ПРИБЫЛЬ ОТ ПОКУПКИ И УДЕРЖАНИЯ】")
        print(
            f"  Buy & Hold:             {self.metrics.get('buy_hold_return', 0):>10.2f} USDT  ({self.metrics.get('buy_hold_return_pct', 0):>6.2f}%)"
        )

        print("\n【РОСТ И ПРОСАДКА】")
        print(
            f"  Макс. рост средств:     {self.metrics.get('max_runup', 0):>10.2f} USDT  ({self.metrics.get('max_runup_pct', 0):>6.2f}%)"
        )
        print(
            f"  Макс. просадка средств: {self.metrics.get('max_drawdown_value', 0):>10.2f} USDT  ({self.metrics.get('max_drawdown', 0):>6.2f}%)"
        )

        print("\n【КОЭФФИЦИЕНТЫ РИСКА/ЭФФЕКТИВНОСТИ】")
        print(f"  Коэффициент Шарпа:      {self.metrics.get('sharpe_ratio', 0):>10.3f}")
        print(f"  Коэффициент Сортино:    {self.metrics.get('sortino_ratio', 0):>10.3f}")
        print(f"  Фактор прибыли:         {self.metrics.get('profit_factor', 0):>10.3f}")

        print("\n【АНАЛИЗ СДЕЛОК】")
        print(f"  Всего сделок:           {self.metrics.get('total_trades', 0):>10.0f}")
        print(f"  Всего открытых сделок:  {self.metrics.get('open_trades', 0):>10.0f}")
        print(
            f"  Прибыльные сделки:      {self.metrics.get('winning_trades', 0):>10.0f}  ({self.metrics.get('win_rate', 0):>6.2f}%)"
        )
        print(f"  Убыточные сделки:       {self.metrics.get('losing_trades', 0):>10.0f}")

        print("\n【СРЕДНИЕ ПОКАЗАТЕЛИ】")
        print(
            f"  Среднее ПР/Уб:          {self.metrics.get('avg_trade_pl', 0):>10.2f} USDT  ({self.metrics.get('avg_trade_pl_pct', 0):>6.2f}%)"
        )
        print(
            f"  Средняя прибыль:        {self.metrics.get('avg_winning_trade', 0):>10.2f} USDT  ({self.metrics.get('avg_winning_trade_pct', 0):>6.2f}%)"
        )
        print(
            f"  Средний убыток:         {self.metrics.get('avg_losing_trade', 0):>10.2f} USDT  ({self.metrics.get('avg_losing_trade_pct', 0):>6.2f}%)"
        )
        print(f"  Коэф. прибыль/убыток:   {self.metrics.get('avg_win_loss_ratio', 0):>10.3f}")

        print("\n【ЭКСТРЕМАЛЬНЫЕ ЗНАЧЕНИЯ】")
        print(
            f"  Макс. прибыль:          {self.metrics.get('largest_winning_trade', 0):>10.2f} USDT  ({self.metrics.get('largest_winning_trade_pct', 0):>6.2f}%)"
        )
        print(
            f"  Макс. убыток:           {self.metrics.get('largest_losing_trade', 0):>10.2f} USDT  ({self.metrics.get('largest_losing_trade_pct', 0):>6.2f}%)"
        )

        print("\n【ВРЕМЯ В СДЕЛКАХ】")
        print(f"  Среднее # баров:        {self.metrics.get('avg_bars_in_trade', 0):>10.1f}")
        print(f"  В прибыльных:           {self.metrics.get('avg_bars_winning', 0):>10.1f}")
        print(f"  В убыточных:            {self.metrics.get('avg_bars_losing', 0):>10.1f}")

        print("\n" + "=" * 70 + "\n")


# ============ ТЕСТ ============

if __name__ == "__main__":
    print("=" * 70)
    print("ТЕСТ МОДУЛЯ МЕТРИК")
    print("=" * 70)

    # Создаем тестовые данные сделок
    test_trades = pd.DataFrame(
        {
            "status": ["closed"] * 10,
            "pnl": [100, -50, 200, -30, 150, -20, 80, -40, 120, -10],
            "commission": [1, 1, 2, 1, 1.5, 0.5, 0.8, 1, 1.2, 0.3],
            "entry_price": [50000] * 10,
            "exit_price": [50100, 49950, 50200, 49970, 50150, 49980, 50080, 49960, 50120, 49990],
            "bars_in_trade": [5, 8, 3, 12, 4, 15, 6, 10, 5, 18],
        }
    )

    # Создаем equity curve
    equity = pd.Series(
        [10000, 10100, 10050, 10250, 10220, 10370, 10350, 10430, 10390, 10510, 10500]
    )

    # Расчет метрик
    metrics = PerformanceMetrics(test_trades, initial_capital=10000, equity_curve=equity)

    # Вывод отчета
    metrics.print_report()

    print("\n Тест завершен!")
