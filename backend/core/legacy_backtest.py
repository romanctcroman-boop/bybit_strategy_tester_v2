# -*- coding: utf-8 -*-
"""
Обновленный SimpleBacktest с поддержкой PerformanceMetrics
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import math
from datetime import datetime

import pandas as pd
from backtest.metrics import PerformanceMetrics
from utils.exceptions import BacktestError, InsufficientCapitalError, ValidationError

# Настройка логирования
logger = logging.getLogger(__name__)


class SimpleBacktest:
    """Простой бэктестер с детальной историей сделок"""

    def __init__(self, initial_capital=10000, commission=0.001):
        """
        Инициализация бэктестера

        Args:
            initial_capital: Начальный капитал (USDT)
            commission: Комиссия за сделку (0.001 = 0.1%)

        Raises:
            ValidationError: При невалидных параметрах
        """
        if initial_capital <= 0:
            raise ValidationError(f"initial_capital должен быть > 0, получено: {initial_capital}")
        if commission < 0 or commission > 1:
            raise ValidationError(f"commission должна быть от 0 до 1, получено: {commission}")

        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.commission = commission
        self.position = 0
        self.entry_price = 0
        self.entry_time = None
        self.entry_bar = 0

        # История сделок
        self.trades = []
        self.current_trade = None

        # История капитала
        self.equity_history = []
        self.bar_counter = 0

        logger.info(
            f"SimpleBacktest инициализирован: capital={initial_capital}, commission={commission}"
        )

    def buy(self, price, quantity, timestamp, margin=None, leverage=1):
        """
        Покупка (открытие long позиции)

        Args:
            price: Цена покупки
            quantity: Количество
            timestamp: Время сделки
            margin: Маржа (объём собственных средств)
            leverage: Используемое плечо

        Returns:
            bool: True если сделка выполнена, False если нет

        Raises:
            ValidationError: При невалидных параметрах
            InsufficientCapitalError: При недостатке капитала
        """
        # Валидация
        if price <= 0:
            raise ValidationError(f"price должна быть > 0, получено: {price}")
        if quantity <= 0:
            raise ValidationError(f"quantity должна быть > 0, получено: {quantity}")
        if leverage <= 0:
            raise ValidationError(f"leverage должна быть > 0, получено: {leverage}")

        # Проверка существующей позиции
        if self.position > 0:
            logger.debug(f"Позиция уже открыта, пропускаем buy")
            return False

        # Расчет стоимости
        position_value = price * quantity
        commission_cost = position_value * self.commission
        expected_margin = position_value / leverage
        if margin is None:
            margin = expected_margin
        else:
            if margin < expected_margin:
                logger.debug(
                    "Недостаточная маржа: передано %.6f, требуется минимум %.6f при плече %.2f",
                    margin,
                    expected_margin,
                    leverage,
                )
                margin = expected_margin
        total_required = margin + commission_cost

        # Проверка капитала
        if total_required > self.capital:
            msg = f"Недостаточно капитала: нужно {total_required:.2f}, доступно {self.capital:.2f}"
            logger.warning(msg)
            raise InsufficientCapitalError(msg)

        # Выполнение покупки
        self.position = quantity
        self.entry_price = price
        self.entry_time = timestamp
        self.entry_bar = self.bar_counter
        self.capital -= total_required

        # Начало новой сделки
        self.current_trade = {
            "entry_time": timestamp,
            "entry_price": price,
            "entry_bar": self.bar_counter,
            "quantity": quantity,
            "side": "long",
            "status": "open",
            "commission": commission_cost,
            "margin": margin,
            "leverage": leverage,
        }

        logger.debug(
            "BUY: qty=%.6f @ %.2f | value=%.2f | margin=%.2f | leverage=%.2f",
            quantity,
            price,
            position_value,
            margin,
            leverage,
        )
        return True

    def sell(self, price, quantity, timestamp):
        """
        Продажа (закрытие long позиции)

        Args:
            price: Цена продажи
            quantity: Количество
            timestamp: Время сделки

        Returns:
            bool: True если сделка выполнена, False если нет

        Raises:
            ValidationError: При невалидных параметрах
        """
        # Валидация
        if price <= 0:
            raise ValidationError(f"price должна быть > 0, получено: {price}")
        if quantity <= 0:
            raise ValidationError(f"quantity должна быть > 0, получено: {quantity}")

        # Проверка наличия позиции
        if self.position == 0:
            logger.debug(f"Нет открытой позиции, пропускаем sell")
            return False

        # Выполнение продажи
        proceeds = price * quantity
        commission_cost = proceeds * self.commission
        entry_commission = 0
        trade_margin = 0
        if self.current_trade:
            entry_commission = self.current_trade.get("commission", 0)
            trade_margin = self.current_trade.get("margin", proceeds)

        gross_pnl = (price - self.entry_price) * quantity
        net_capital_change = trade_margin + gross_pnl - commission_cost
        self.capital += net_capital_change

        # Закрытие сделки
        if self.current_trade:
            total_commission = entry_commission + commission_cost
            net_pnl = gross_pnl - total_commission
            margin_for_pct = trade_margin if trade_margin else (self.entry_price * quantity)
            pnl_pct = (net_pnl / margin_for_pct) * 100 if margin_for_pct else 0

            self.current_trade.update(
                {
                    "exit_time": timestamp,
                    "exit_price": price,
                    "exit_bar": self.bar_counter,
                    "pnl": net_pnl,
                    "pnl_pct": pnl_pct,
                    "bars_in_trade": self.bar_counter - self.entry_bar,
                    "status": "closed",
                    "commission": total_commission,
                }
            )

            self.trades.append(self.current_trade)
            self.current_trade = None

        self.position = 0
        self.entry_price = 0
        self.entry_time = None

        return True

    def update_equity(self, current_price):
        """Обновление истории капитала"""
        if self.position > 0:
            unrealized_pnl = (current_price - self.entry_price) * self.position
            margin = 0
            if self.current_trade:
                margin = self.current_trade.get("margin", 0)
            total_equity = self.capital + margin + unrealized_pnl
        else:
            total_equity = self.capital

        self.equity_history.append(total_equity)
        self.bar_counter += 1

    def get_total_value(self, current_price):
        """Получить текущую стоимость портфеля"""
        if self.position > 0:
            margin = 0
            if self.current_trade:
                margin = self.current_trade.get("margin", 0)
            unrealized_pnl = (current_price - self.entry_price) * self.position
            return self.capital + margin + unrealized_pnl
        return self.capital

    def get_trades_df(self):
        """Получить DataFrame со всеми сделками"""
        return pd.DataFrame(self.trades)

    def get_equity_curve(self):
        """Получить equity curve как Series"""
        return pd.Series(self.equity_history)

    def get_metrics(self):
        """Получить метрики производительности"""
        trades_df = self.get_trades_df()
        equity_curve = self.get_equity_curve()

        if len(trades_df) == 0:
            logger.warning("Нет сделок для расчета метрик")
            return None

        metrics = PerformanceMetrics(
            trades_df=trades_df, initial_capital=self.initial_capital, equity_curve=equity_curve
        )

        return metrics

    def print_results(self):
        """Вывод результатов с метриками"""
        metrics = self.get_metrics()

        if metrics:
            metrics.print_report()
        else:
            logger.warning("Нет данных для отчета")


# ============ ТЕСТ ============

if __name__ == "__main__":
    print("=" * 70)
    print("ТЕСТ ИНТЕГРАЦИИ BACKTEST + METRICS")
    print("=" * 70)

    # Создаем бэктест
    bt = SimpleBacktest(initial_capital=10000, commission=0.001)

    # Симулируем несколько сделок
    test_data = [
        (datetime(2025, 10, 1, 10, 0), 50000),
        (datetime(2025, 10, 1, 11, 0), 50500),
        (datetime(2025, 10, 1, 12, 0), 50200),
        (datetime(2025, 10, 1, 13, 0), 51000),
        (datetime(2025, 10, 1, 14, 0), 50800),
        (datetime(2025, 10, 1, 15, 0), 52000),
    ]

    print("\n Симуляция торговли...")

    # Сделка 1
    bt.buy(50000, 0.1, test_data[0][0])
    bt.update_equity(50000)

    bt.update_equity(50500)
    bt.sell(50500, 0.1, test_data[1][0])

    # Сделка 2
    bt.buy(50200, 0.1, test_data[2][0])
    bt.update_equity(50200)

    bt.update_equity(51000)
    bt.sell(51000, 0.1, test_data[3][0])

    # Сделка 3
    bt.buy(50800, 0.1, test_data[4][0])
    bt.update_equity(50800)

    bt.update_equity(52000)
    bt.sell(52000, 0.1, test_data[5][0])

    print(f" Выполнено {len(bt.trades)} сделок")

    # Вывод результатов с метриками
    print("\n РЕЗУЛЬТАТЫ:")
    bt.print_results()
