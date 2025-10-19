# -*- coding: utf-8 -*-
"""
Walk-Forward Analysis Module
Модуль для пошаговой оптимизации и проверки устойчивости торговых стратегий
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from backtest.simple_backtest_v2 import SimpleBacktest
from tqdm import tqdm

logger = logging.getLogger(__name__)


class WalkForwardWindow:
    """РћРґРЅРѕ РѕРєРЅРѕ Walk-Forward Р°РЅР°Р»РёР·Р°"""

    def __init__(
        self,
        window_id: int,
        is_start: datetime,
        is_end: datetime,
        oos_start: datetime,
        oos_end: datetime,
        best_params: Optional[Dict[str, Any]] = None,
        is_results: Optional[pd.DataFrame] = None,
        oos_result: Optional[Dict[str, float]] = None,
    ):
        self.window_id = window_id
        self.is_start = is_start
        self.is_end = is_end
        self.oos_start = oos_start
        self.oos_end = oos_end
        self.best_params = best_params
        self.is_results = is_results
        self.oos_result = oos_result

    def __repr__(self):
        return (
            f"WFWindow #{self.window_id}: "
            f"IS({self.is_start.date()}в†’{self.is_end.date()}) "
            f"OOS({self.oos_start.date()}в†’{self.oos_end.date()})"
        )


class WalkForwardAnalyzer:
    """
    РљР»Р°СЃСЃ РґР»СЏ Walk-Forward РѕРїС‚РёРјРёР·Р°С†РёРё СЃС‚СЂР°С‚РµРіРёР№

    Р Р°Р·Р±РёРІР°РµС‚ РёСЃС‚РѕСЂРёС‡РµСЃРєРёРµ РґР°РЅРЅС‹Рµ РЅР° РѕРєРЅР°:
    - In-Sample (IS) - РїРµСЂРёРѕРґ РѕР±СѓС‡РµРЅРёСЏ РґР»СЏ РїРѕРёСЃРєР° РѕРїС‚РёРјР°Р»СЊРЅС‹С… РїР°СЂР°РјРµС‚СЂРѕРІ
    - Out-of-Sample (OOS) - РїРµСЂРёРѕРґ РїСЂРѕРІРµСЂРєРё РЅР°Р№РґРµРЅРЅС‹С… РїР°СЂР°РјРµС‚СЂРѕРІ

    Example:
        >>> wfa = WalkForwardAnalyzer(
        ...     data=df,
        ...     initial_capital=10000,
        ...     is_window_days=120,
        ...     oos_window_days=60,
        ...     step_days=30
        ... )
        >>> results = wfa.run(
        ...     strategy_class=MACrossoverStrategy,
        ...     param_grid={'fast_period': [5, 10, 20], 'slow_period': [20, 50]}
        ... )
    """

    def __init__(
        self,
        data: pd.DataFrame,
        initial_capital: float = 10000.0,
        commission: float = 0.001,
        is_window_days: int = 120,
        oos_window_days: int = 60,
        step_days: int = 30,
        metric: str = "net_profit",
    ):
        """
        Args:
            data: DataFrame СЃ РёСЃС‚РѕСЂРёС‡РµСЃРєРёРјРё РґР°РЅРЅС‹РјРё (OHLCV)
            initial_capital: РќР°С‡Р°Р»СЊРЅС‹Р№ РєР°РїРёС‚Р°Р»
            commission: РљРѕРјРёСЃСЃРёСЏ Р·Р° СЃРґРµР»РєСѓ
            is_window_days: Р Р°Р·РјРµСЂ In-Sample РѕРєРЅР° (РїРµСЂРёРѕРґ РѕР±СѓС‡РµРЅРёСЏ)
            oos_window_days: Р Р°Р·РјРµСЂ Out-of-Sample РѕРєРЅР° (РїРµСЂРёРѕРґ РїСЂРѕРІРµСЂРєРё)
            step_days: РЁР°Рі СЃРґРІРёРіР° РѕРєРѕРЅ
            metric: РњРµС‚СЂРёРєР° РґР»СЏ РѕРїС‚РёРјРёР·Р°С†РёРё ('net_profit', 'sharpe_ratio', etc.)
        """
        self.data = data.copy()
        self.initial_capital = initial_capital
        self.commission = commission
        self.is_window_days = is_window_days
        self.oos_window_days = oos_window_days
        self.step_days = step_days
        self.metric = metric

        self.windows: List[WalkForwardWindow] = []
        self._create_windows()

    def _create_windows(self):
        """РЎРѕР·РґР°С‘С‚ СЃРїРёСЃРѕРє РѕРєРѕРЅ РґР»СЏ Walk-Forward Р°РЅР°Р»РёР·Р°"""
        if "timestamp" not in self.data.columns:
            raise ValueError("DataFrame РґРѕР»Р¶РµРЅ СЃРѕРґРµСЂР¶Р°С‚СЊ РєРѕР»РѕРЅРєСѓ 'timestamp'")

        self.data = self.data.sort_values("timestamp").reset_index(drop=True)

        start_date = self.data["timestamp"].iloc[0]
        end_date = self.data["timestamp"].iloc[-1]

        window_size_days = self.is_window_days + self.oos_window_days
        current_start = start_date
        window_id = 0

        while True:
            # РћРїСЂРµРґРµР»СЏРµРј РіСЂР°РЅРёС†С‹ IS РѕРєРЅР°
            is_start = current_start
            is_end = is_start + timedelta(days=self.is_window_days)

            # РћРїСЂРµРґРµР»СЏРµРј РіСЂР°РЅРёС†С‹ OOS РѕРєРЅР°
            oos_start = is_end
            oos_end = oos_start + timedelta(days=self.oos_window_days)

            # РџСЂРѕРІРµСЂСЏРµРј С‡С‚Рѕ OOS РѕРєРЅРѕ РµС‰С‘ РїРѕРјРµС‰Р°РµС‚СЃСЏ
            if oos_end > end_date:
                break

            window = WalkForwardWindow(
                window_id=window_id,
                is_start=is_start,
                is_end=is_end,
                oos_start=oos_start,
                oos_end=oos_end,
            )
            self.windows.append(window)

            # РЎРґРІРёРіР°РµРј РЅР° step_days
            current_start += timedelta(days=self.step_days)
            window_id += 1

        if len(self.windows) == 0:
            raise ValueError(
                f"РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РґР°РЅРЅС‹С… РґР»СЏ СЃРѕР·РґР°РЅРёСЏ РѕРєРѕРЅ. "
                f"РўСЂРµР±СѓРµС‚СЃСЏ РјРёРЅРёРјСѓРј {window_size_days} РґРЅРµР№, "
                f"РґРѕСЃС‚СѓРїРЅРѕ {(end_date - start_date).days} РґРЅРµР№"
            )

        print(f"[WFO] РЎРѕР·РґР°РЅРѕ {len(self.windows)} РѕРєРѕРЅ РґР»СЏ Р°РЅР°Р»РёР·Р°")
        for window in self.windows:
            print(f"  {window}")

    def _get_window_data(self, start: datetime, end: datetime) -> pd.DataFrame:
        """РџРѕР»СѓС‡Р°РµС‚ РґР°РЅРЅС‹Рµ РґР»СЏ РєРѕРЅРєСЂРµС‚РЅРѕРіРѕ РѕРєРЅР°"""
        mask = (self.data["timestamp"] >= start) & (self.data["timestamp"] < end)
        return self.data[mask].copy()

    def _optimize_window(
        self, window: WalkForwardWindow, strategy_class, param_grid: Dict[str, List]
    ) -> Tuple[Dict[str, Any], pd.DataFrame]:
        """
        РћРїС‚РёРјРёР·РёСЂСѓРµС‚ РїР°СЂР°РјРµС‚СЂС‹ РЅР° IS РѕРєРЅРµ

        Returns:
            (best_params, all_results_df)
        """
        is_data = self._get_window_data(window.is_start, window.is_end)

        if len(is_data) == 0:
            raise ValueError(f"РќРµС‚ РґР°РЅРЅС‹С… РґР»СЏ РѕРєРЅР° {window}")

        # РСЃРїРѕР»СЊР·СѓРµРј StrategyOptimizer РґР»СЏ Grid Search РЅР° IS РѕРєРЅРµ
        from backtest.optimizer import StrategyOptimizer

        optimizer = StrategyOptimizer(
            data=is_data, initial_capital=self.initial_capital, commission=self.commission
        )

        results_df = optimizer.grid_search(
            strategy_class=strategy_class,
            param_grid=param_grid,
            metric=self.metric,
            max_combinations=None,  # Р±РµР· РѕРіСЂР°РЅРёС‡РµРЅРёР№ РґР»СЏ WFO
        )

        if results_df.empty:
            return {}, pd.DataFrame()

        # Р‘РµСЂС‘Рј Р»СѓС‡С€СѓСЋ РєРѕРјР±РёРЅР°С†РёСЋ
        best_row = results_df.iloc[0]
        best_params = {}

        # РР·РІР»РµРєР°РµРј РїР°СЂР°РјРµС‚СЂС‹ РёР· СЃС‚СЂРѕРєРё 'parameters'
        import re

        params_str = best_row["parameters"]
        for param_name in param_grid.keys():
            pattern = f"{param_name}=([^,)]+)"
            match = re.search(pattern, params_str)
            if match:
                value = match.group(1)
                # РџС‹С‚Р°РµРјСЃСЏ РїСЂРµРѕР±СЂР°Р·РѕРІР°С‚СЊ РІ int/float
                try:
                    best_params[param_name] = int(value)
                except ValueError:
                    try:
                        best_params[param_name] = float(value)
                    except ValueError:
                        best_params[param_name] = value

        return best_params, results_df

    def _test_window(
        self, window: WalkForwardWindow, strategy_class, params: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        РўРµСЃС‚РёСЂСѓРµС‚ РїР°СЂР°РјРµС‚СЂС‹ РЅР° OOS РѕРєРЅРµ

        Returns:
            РЎР»РѕРІР°СЂСЊ СЃ РјРµС‚СЂРёРєР°РјРё РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊРЅРѕСЃС‚Рё
        """
        oos_data = self._get_window_data(window.oos_start, window.oos_end)

        if len(oos_data) == 0:
            return {}

        # РЎРѕР·РґР°С‘Рј backtest Рё С‚РµСЃС‚РёСЂСѓРµРј
        backtest = SimpleBacktest(initial_capital=self.initial_capital, commission=self.commission)

        strategy = strategy_class(**params)
        # Ручной запуск backtest (как в web/pages/1_Backtest.py)
        for i in range(len(oos_data)):
            row = oos_data.iloc[i]
            backtest.update_equity(row["close"])

            signal = strategy.generate_signal(oos_data.iloc[: i + 1])

            if signal == "buy" and backtest.position == 0:
                quantity = (backtest.capital * 0.95) / row["close"]
                backtest.buy(row["close"], quantity, row["timestamp"])
            elif signal == "sell" and backtest.position > 0:
                backtest.sell(row["close"], backtest.position, row["timestamp"])

        metrics_obj = backtest.get_metrics()
        if not metrics_obj:
            return {}
        metrics = metrics_obj.get_summary()
        return metrics

    def run(
        self, strategy_class, param_grid: Dict[str, List], top_n: int = 1, verbose: bool = True
    ) -> pd.DataFrame:
        """
        Р—Р°РїСѓСЃРєР°РµС‚ Walk-Forward Р°РЅР°Р»РёР·

        Args:
            strategy_class: РљР»Р°СЃСЃ СЃС‚СЂР°С‚РµРіРёРё РґР»СЏ С‚РµСЃС‚РёСЂРѕРІР°РЅРёСЏ
            param_grid: РЎР»РѕРІР°СЂСЊ СЃ РґРёР°РїР°Р·РѕРЅР°РјРё РїР°СЂР°РјРµС‚СЂРѕРІ
            top_n: РЎРєРѕР»СЊРєРѕ Р»СѓС‡С€РёС… РєРѕРјР±РёРЅР°С†РёР№ С‚РµСЃС‚РёСЂРѕРІР°С‚СЊ РЅР° OOS (РѕР±С‹С‡РЅРѕ 1)
            verbose: РџРѕРєР°Р·С‹РІР°С‚СЊ РїСЂРѕРіСЂРµСЃСЃ

        Returns:
            DataFrame СЃ СЂРµР·СѓР»СЊС‚Р°С‚Р°РјРё РїРѕ РІСЃРµРј РѕРєРЅР°Рј
        """
        print(f"\n[WFO] Р—Р°РїСѓСЃРє Walk-Forward Р°РЅР°Р»РёР·Р°")
        print(f"  РћРєРѕРЅ: {len(self.windows)}")
        print(f"  IS РѕРєРЅРѕ: {self.is_window_days} РґРЅРµР№")
        print(f"  OOS РѕРєРЅРѕ: {self.oos_window_days} РґРЅРµР№")
        print(f"  РњРµС‚СЂРёРєР°: {self.metric}\n")

        all_results = []

        iterator = tqdm(self.windows, desc="WFO Progress") if verbose else self.windows

        for window in iterator:
            # 1. РћРїС‚РёРјРёР·Р°С†РёСЏ РЅР° IS РѕРєРЅРµ
            if verbose:
                print(f"\n[WFO] РћРєРЅРѕ #{window.window_id}")
                print(f"  IS: {window.is_start.date()} в†’ {window.is_end.date()}")

            best_params, is_results = self._optimize_window(window, strategy_class, param_grid)

            if not best_params:
                print(
                    f"  вљ пёЏ РќРµ РЅР°Р№РґРµРЅРѕ РїР°СЂР°РјРµС‚СЂРѕРІ РґР»СЏ РѕРєРЅР° #{window.window_id}"
                )
                continue

            window.best_params = best_params
            window.is_results = is_results

            if verbose:
                print(f"  вњ… Р›СѓС‡С€РёРµ РїР°СЂР°РјРµС‚СЂС‹: {best_params}")

            # 2. РўРµСЃС‚РёСЂРѕРІР°РЅРёРµ РЅР° OOS РѕРєРЅРµ
            if verbose:
                print(f"  OOS: {window.oos_start.date()} в†’ {window.oos_end.date()}")

            oos_result = self._test_window(window, strategy_class, best_params)
            window.oos_result = oos_result

            if oos_result:
                if verbose:
                    oos_profit = oos_result.get("net_profit", 0)
                    oos_trades = oos_result.get("total_trades", 0)
                    print(
                        f"  рџ“Љ OOS СЂРµР·СѓР»СЊС‚Р°С‚: {oos_profit:.2f} ({oos_trades} СЃРґРµР»РѕРє)"
                    )

                # РЎРѕС…СЂР°РЅСЏРµРј СЂРµР·СѓР»СЊС‚Р°С‚
                result_row = {
                    "window_id": window.window_id,
                    "is_start": window.is_start,
                    "is_end": window.is_end,
                    "oos_start": window.oos_start,
                    "oos_end": window.oos_end,
                    "parameters": str(best_params),
                    **{f"oos_{k}": v for k, v in oos_result.items()},
                }
                all_results.append(result_row)

        if not all_results:
            print("\n[WFO] вљ пёЏ РќРµ РїРѕР»СѓС‡РµРЅРѕ СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ!")
            return pd.DataFrame()

        results_df = pd.DataFrame(all_results)

        # Р’С‹С‡РёСЃР»СЏРµРј СЃРІРѕРґРЅСѓСЋ СЃС‚Р°С‚РёСЃС‚РёРєСѓ
        oos_profit_col = "oos_net_profit"
        if oos_profit_col in results_df.columns:
            total_oos_profit = results_df[oos_profit_col].sum()
            positive_windows = (results_df[oos_profit_col] > 0).sum()
            total_windows = len(results_df)

            print(f"\n[WFO] вњ… РРўРћР“Р:")
            print(f"  РћРєРѕРЅ РїСЂРѕС‚РµСЃС‚РёСЂРѕРІР°РЅРѕ: {total_windows}")
            print(
                f"  РџСЂРёР±С‹Р»СЊРЅС‹С… РѕРєРѕРЅ: {positive_windows} ({positive_windows/total_windows*100:.1f}%)"
            )
            print(f"  РћР±С‰РёР№ OOS РїСЂРѕС„РёС‚: {total_oos_profit:.2f}")
            print(f"  РЎСЂРµРґРЅРёР№ OOS РїСЂРѕС„РёС‚: {results_df[oos_profit_col].mean():.2f}")

        return results_df

    def get_oos_equity_curve(self) -> pd.DataFrame:
        """
        РЎС‚СЂРѕРёС‚ РѕР±С‰СѓСЋ equity curve РїРѕ РІСЃРµРј OOS РѕРєРЅР°Рј

        Returns:
            DataFrame СЃ РєРѕР»РѕРЅРєР°РјРё: timestamp, equity, window_id
        """
        all_equity = []

        for window in self.windows:
            if window.oos_result is None:
                continue

            # РџРѕР»СѓС‡Р°РµРј РґР°РЅРЅС‹Рµ OOS РѕРєРЅР°
            oos_data = self._get_window_data(window.oos_start, window.oos_end)

            # Р—Р°РїСѓСЃРєР°РµРј backtest РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ equity curve
            from backtest.optimizer import StrategyOptimizer

            # TODO: СЂРµР°Р»РёР·РѕРІР°С‚СЊ РїРѕР»СѓС‡РµРЅРёРµ equity curve РёР· window.oos_result
            # РїРѕРєР° РІРѕР·РІСЂР°С‰Р°РµРј РїСЂРѕСЃС‚РѕР№ DataFrame

        return pd.DataFrame(all_equity)


def calculate_wfo_windows(total_days: int, is_window: int, oos_window: int, step: int) -> int:
    """
    Р’С‹С‡РёСЃР»СЏРµС‚ РєРѕР»РёС‡РµСЃС‚РІРѕ Walk-Forward РѕРєРѕРЅ

    Args:
        total_days: РћР±С‰РёР№ РїРµСЂРёРѕРґ РґР°РЅРЅС‹С… (РґРЅРµР№)
        is_window: Р Р°Р·РјРµСЂ In-Sample РѕРєРЅР° (РґРЅРµР№)
        oos_window: Р Р°Р·РјРµСЂ Out-of-Sample РѕРєРЅР° (РґРЅРµР№)
        step: РЁР°Рі СЃРґРІРёРіР° РѕРєРѕРЅ (РґРЅРµР№)

    Returns:
        РљРѕР»РёС‡РµСЃС‚РІРѕ РѕРєРѕРЅ
    """
    window_size = is_window + oos_window
    available_range = total_days - window_size

    if available_range < 0:
        return 0

    num_windows = (available_range // step) + 1
    return num_windows
