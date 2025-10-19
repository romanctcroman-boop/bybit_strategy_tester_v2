# -*- coding: utf-8 -*-
"""
Strategy Optimizer - Numba Fixed Version
"""
import logging
from datetime import datetime
from itertools import product

import numpy as np
import pandas as pd
from numba import jit
from tqdm import tqdm

logger = logging.getLogger(__name__)


class StrategyOptimizer:
    """Оптимизатор с Numba ускорением"""

    def __init__(self, data, initial_capital=10000, commission=0.001, n_jobs=None):
        self.data = data
        self.initial_capital = initial_capital
        self.commission = commission
        self.results = []

        logger.info("Numba ускорение активировано")

    def grid_search(self, strategy_class, param_grid, metric="net_profit", max_combinations=1000):
        """Grid Search с ускорением"""
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(product(*param_values))

        total_combinations = len(combinations)

        if max_combinations and len(combinations) > max_combinations:
            logger.warning(
                f"Limiting to {max_combinations} combinations (random sample from {total_combinations} total)"
            )
            import random

            combinations = random.sample(combinations, max_combinations)

        logger.info(f"Testing {len(combinations)} combinations...")

        self.results = []

        for combo in tqdm(combinations, desc="Оптимизация"):
            params = dict(zip(param_names, combo))
            result = self._run_backtest(strategy_class, params)

            if result and "net_profit" in result:
                result["params"] = params
                self.results.append(result)

        if len(self.results) == 0:
            logger.error("Нет валидных результатов!")
            return pd.DataFrame()

        df = pd.DataFrame(self.results)

        if metric in df.columns:
            df = df.sort_values(metric, ascending=False)
            best = df.iloc[0]
            logger.info(f"BEST {metric}: {best[metric]:.2f}")
            logger.info(f"BEST Параметры: {best.get('params', {})}")

        return df

    def single_backtest(self, strategy_class, params):
        """
        Запускает один бэктест с заданными параметрами

        Args:
            strategy_class: Класс стратегии
            params: Словарь параметров стратегии

        Returns:
            Словарь с метриками или None при ошибке
        """
        result = self._run_backtest(strategy_class, params)

        if result and "net_profit" in result:
            result["params"] = params
            logger.info(
                f"Single backtest: {result.get('total_trades', 0)} trades, profit: {result.get('net_profit', 0):.2f}"
            )
            return result
        else:
            logger.warning("Single backtest failed - no valid result")
            return None

    def _run_backtest(self, strategy_class, params):
        """Запуск бэктеста"""
        try:
            strategy = strategy_class(**params)
            signals = strategy.generate_signals(self.data)

            if signals is None or len(signals) == 0:
                return None

            trades = self._execute_trades_fast(signals)

            if len(trades) == 0:
                return None

            metrics = self._calculate_metrics_fast(trades)
            return metrics

        except Exception as e:
            return None

    def _execute_trades_fast(self, signals):
        """Быстрое выполнение сделок с Numba"""
        prices = self.data["close"].values
        timestamps = self.data.index.values

        # Вызываем JIT-компилированную функцию
        trades_data, trade_count = execute_trades_numba(
            prices, signals, self.initial_capital, self.commission
        )

        # Преобразуем в список словарей
        trades = []
        for i in range(trade_count):
            trades.append(
                {
                    "entry_time": timestamps[int(trades_data[i, 0])],
                    "exit_time": timestamps[int(trades_data[i, 1])],
                    "entry_price": trades_data[i, 2],
                    "exit_price": trades_data[i, 3],
                    "pnl": trades_data[i, 4],
                    "return": trades_data[i, 5],
                }
            )

        return trades

    def _calculate_metrics_fast(self, trades):
        """Быстрый расчёт метрик"""
        if not trades:
            return None

        pnls = np.array([t["pnl"] for t in trades])
        returns = np.array([t["return"] for t in trades])

        total_return = returns.sum()
        win_rate = (pnls > 0).sum() / len(pnls)

        wins = pnls[pnls > 0]
        losses = pnls[pnls < 0]

        avg_win = wins.mean() if len(wins) > 0 else 0
        avg_loss = abs(losses.mean()) if len(losses) > 0 else 0
        profit_factor = avg_win / avg_loss if avg_loss > 0 else 0

        return {
            "net_profit": pnls.sum(),
            "total_trades": len(trades),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_return": total_return,
        }


@jit(nopython=True)
def execute_trades_numba(prices, signals, initial_capital, commission):
    """
    JIT-компилированная функция выполнения сделок
    Возвращает (trades_data, trade_count)
    """
    n = len(prices)
    max_trades = n // 2
    trades_data = np.zeros((max_trades, 6))

    trade_count = 0
    position = False
    entry_idx = 0
    entry_price = 0.0
    capital = initial_capital

    for i in range(n):
        if signals[i] == 1 and not position:  # Buy
            entry_idx = i
            entry_price = prices[i]
            position = True

        elif signals[i] == -1 and position:  # Sell
            exit_price = prices[i]
            size = capital / entry_price
            pnl = (exit_price - entry_price) * size
            commission_cost = (entry_price + exit_price) * size * commission
            net_pnl = pnl - commission_cost

            capital += net_pnl

            trades_data[trade_count, 0] = entry_idx
            trades_data[trade_count, 1] = i
            trades_data[trade_count, 2] = entry_price
            trades_data[trade_count, 3] = exit_price
            trades_data[trade_count, 4] = net_pnl
            trades_data[trade_count, 5] = net_pnl / initial_capital

            trade_count += 1
            position = False

    return trades_data, trade_count
