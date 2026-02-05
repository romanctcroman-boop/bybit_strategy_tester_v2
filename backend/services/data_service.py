"""
DataService - Repository Pattern для работы с базой данных

Предоставляет высокоуровневые методы для CRUD операций со всеми моделями.
Инкапсулирует логику работы с SQLAlchemy, транзакциями, batch operations.
"""

import logging
from datetime import UTC, datetime
from typing import Any, TypedDict

from sqlalchemy import and_, asc, desc, func
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import (
    Backtest,
    MarketData,
    Optimization,
    OptimizationResult,
    Strategy,
    Trade,
)

logger = logging.getLogger(__name__)


class ClaimResult(TypedDict):
    status: str  # 'claimed' | 'running' | 'completed' | 'not_found' | 'error'
    backtest: Any | None
    message: str | None


class DataService:
    """
    Repository для работы с базой данных

    Методы организованы по моделям:
    - Strategy CRUD
    - Backtest CRUD
    - Trade CRUD
    - Optimization CRUD
    - OptimizationResult CRUD
    - MarketData CRUD
    """

    def __init__(self, db: Session = None):
        """
        Инициализация сервиса

        Args:
            db: SQLAlchemy сессия (если None, создаётся новая)
        """
        self.db = db or SessionLocal()
        self._auto_close = db is None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._auto_close:
            self.db.close()

    # ========================================================================
    # STRATEGY METHODS
    # ========================================================================

    def create_strategy(
        self,
        name: str,
        description: str,
        strategy_type: str,
        config: dict[str, Any],
        is_active: bool = True,
    ) -> Strategy:
        """
        Создать новую стратегию

        Args:
            name: Название стратегии
            description: Описание
            strategy_type: Тип стратегии (Indicator-Based, Pattern-Based, ML-Based)
            config: Конфигурация стратегии (JSON)
            is_active: Активна ли стратегия

        Returns:
            Созданная стратегия
        """
        strategy = Strategy(
            name=name,
            description=description,
            strategy_type=strategy_type,
            config=config,
            is_active=is_active,
        )
        self.db.add(strategy)
        self.db.commit()
        self.db.refresh(strategy)
        return strategy

    def get_strategy(self, strategy_id: int) -> Strategy | None:
        """Получить стратегию по ID"""
        return self.db.query(Strategy).filter(Strategy.id == strategy_id).first()

    def get_strategies(
        self,
        is_active: bool | None = None,
        strategy_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Strategy]:
        """
        Получить список стратегий с фильтрацией

        Args:
            is_active: Фильтр по активности
            strategy_type: Фильтр по типу
            limit: Максимум результатов
            offset: Смещение для пагинации

        Returns:
            Список стратегий
        """
        query = self.db.query(Strategy)

        if is_active is not None:
            query = query.filter(Strategy.is_active == is_active)

        if strategy_type:
            query = query.filter(Strategy.strategy_type == strategy_type)

        return query.offset(offset).limit(limit).all()

    def update_strategy(self, strategy_id: int, **kwargs) -> Strategy | None:
        """
        Обновить стратегию

        Args:
            strategy_id: ID стратегии
            **kwargs: Поля для обновления

        Returns:
            Обновлённая стратегия или None
        """
        strategy = self.get_strategy(strategy_id)
        if not strategy:
            return None

        for key, value in kwargs.items():
            if hasattr(strategy, key):
                setattr(strategy, key, value)

        strategy.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(strategy)
        return strategy

    def delete_strategy(self, strategy_id: int) -> bool:
        """
        Удалить стратегию (CASCADE удалит связанные бэктесты и оптимизации)

        Args:
            strategy_id: ID стратегии

        Returns:
            True если удалено, False если не найдено
        """
        strategy = self.get_strategy(strategy_id)
        if not strategy:
            return False

        self.db.delete(strategy)
        self.db.commit()
        return True

    # ========================================================================
    # BACKTEST METHODS
    # ========================================================================

    def create_backtest(
        self,
        strategy_id: int,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float,
        leverage: int = 1,
        commission: float = 0.0007,  # 0.07% TradingView parity
        config: dict[str, Any] | None = None,
        status: str = "pending",
    ) -> Backtest:
        """
        Создать новый бэктест

        Args:
            strategy_id: ID стратегии
            symbol: Торговая пара (BTCUSDT)
            timeframe: Таймфрейм (1, 5, 15, 60, 240, D)
            start_date: Дата начала
            end_date: Дата окончания
            initial_capital: Начальный капитал (USDT)
            leverage: Плечо (1-100)
            commission: Комиссия (0.0007 = 0.07% TradingView parity)
            config: Дополнительная конфигурация
            status: Статус (pending, running, completed, failed)

        Returns:
            Созданный бэктест
        """
        backtest = Backtest(
            strategy_id=strategy_id,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            leverage=leverage,
            commission=commission,
            config=config,
            status=status,
        )
        self.db.add(backtest)
        self.db.commit()
        self.db.refresh(backtest)
        return backtest

    def get_backtest(self, backtest_id: int) -> Backtest | None:
        """Получить бэктест по ID"""
        return self.db.query(Backtest).filter(Backtest.id == backtest_id).first()

    def get_backtests(
        self,
        strategy_id: int | None = None,
        symbol: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at",
        order_dir: str = "desc",
    ) -> list[Backtest]:
        """
        Получить список бэктестов с фильтрацией

        Args:
            strategy_id: Фильтр по стратегии
            symbol: Фильтр по символу
            status: Фильтр по статусу
            limit: Максимум результатов
            offset: Смещение
            order_by: Поле для сортировки
            order_dir: Направление сортировки (asc/desc)

        Returns:
            Список бэктестов
        """
        query = self.db.query(Backtest)

        if strategy_id:
            query = query.filter(Backtest.strategy_id == strategy_id)

        if symbol:
            query = query.filter(Backtest.symbol == symbol)

        if status:
            query = query.filter(Backtest.status == status)

        # Сортировка
        order_field = getattr(Backtest, order_by, Backtest.created_at)
        if order_dir == "desc":
            query = query.order_by(desc(order_field))
        else:
            query = query.order_by(asc(order_field))

        return query.offset(offset).limit(limit).all()

    def update_backtest(self, backtest_id: int, **kwargs) -> Backtest | None:
        """
        Обновить бэктест

        Args:
            backtest_id: ID бэктеста
            **kwargs: Поля для обновления

        Returns:
            Обновлённый бэктест или None
        """
        backtest = self.get_backtest(backtest_id)
        if not backtest:
            return None

        for key, value in kwargs.items():
            if hasattr(backtest, key):
                setattr(backtest, key, value)

        self.db.commit()
        self.db.refresh(backtest)
        return backtest

    def claim_backtest_to_run(
        self, backtest_id: int, now: datetime, stale_seconds: int = 24 * 3600
    ) -> ClaimResult:
        """
        Atomically claim a backtest for running.

        - If backtest not found -> None
        - If status == 'completed' -> return 'completed'
        - If status == 'running' and not stale -> return 'running'
        - Otherwise: set status='running', started_at=now, commit and return the Backtest object
        """
        # Use SELECT ... FOR UPDATE to avoid races when supported by DB
        try:
            bt = (
                self.db.query(Backtest)
                .filter(Backtest.id == backtest_id)
                .with_for_update()
                .first()
            )
        except Exception as exc:
            # with_for_update may not be supported by some DBs in test envs; fall back to plain query
            logger.debug(
                "with_for_update not supported or failed, falling back: %s", exc
            )
            bt = self.get_backtest(backtest_id)

        if not bt:
            return ClaimResult(
                status="not_found", backtest=None, message="Backtest not found"
            )

        status = getattr(bt, "status", None)
        started_at = getattr(bt, "started_at", None)

        if status == "completed":
            return ClaimResult(
                status="completed", backtest=bt, message="Already completed"
            )

        if status == "running" and started_at:
            # normalize started_at if naive
            if getattr(started_at, "tzinfo", None) is None:
                # assume UTC for legacy rows
                started_at = started_at.replace(tzinfo=UTC)
            delta = (now - started_at).total_seconds()
            if delta < stale_seconds:
                return ClaimResult(
                    status="running",
                    backtest=bt,
                    message="Already running and not stale",
                )

        # Claim it
        try:
            if hasattr(bt, "status"):
                bt.status = "running"
            if hasattr(bt, "started_at"):
                bt.started_at = now
            if hasattr(bt, "updated_at"):
                bt.updated_at = now
            self.db.commit()
            self.db.refresh(bt)
        except Exception as exc:
            # If commit fails, attempt rollback and return an error status
            logger.exception("Failed to claim backtest %s: %s", backtest_id, exc)
            try:
                self.db.rollback()
            except Exception as _e:
                logging.getLogger("data_service").debug("Operation failed: %s", _e)
            return ClaimResult(status="error", backtest=None, message=str(exc))

        return ClaimResult(status="claimed", backtest=bt, message="Claimed for running")

    def update_backtest_results(
        self,
        backtest_id: int,
        final_capital: float,
        total_return: float,
        total_trades: int,
        winning_trades: int,
        losing_trades: int,
        win_rate: float,
        sharpe_ratio: float,
        max_drawdown: float,
        **other_metrics,
    ) -> Backtest | None:
        """
        Обновить результаты бэктеста

        Args:
            backtest_id: ID бэктеста
            final_capital: Конечный капитал
            total_return: Общая доходность (%)
            total_trades: Всего трейдов
            winning_trades: Прибыльных трейдов
            losing_trades: Убыточных трейдов
            win_rate: Процент выигрышей
            sharpe_ratio: Коэффициент Шарпа
            max_drawdown: Максимальная просадка (%)
            **other_metrics: Дополнительные метрики

        Returns:
            Обновлённый бэктест
        """
        update_data = {
            "final_capital": final_capital,
            "total_return": total_return,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "status": "completed",
            "completed_at": datetime.now(UTC),
            **other_metrics,
        }

        # If the caller passed a full 'results' dict (engine results), unpack useful fields
        results = None
        if "results" in update_data:
            results = update_data.pop("results")

        # Merge common nested metrics if present
        if results:
            # results may contain a nested 'metrics' dict or top-level fields
            metrics = results.get("metrics") if isinstance(results, dict) else None
            if metrics is None and isinstance(results, dict):
                # sometimes engine returns metrics at top-level
                metrics = results

            # Trades list (store in Backtest.trades JSON column)
            trades = None
            if isinstance(results, dict):
                trades = (
                    results.get("trades")
                    or results.get("all_trades")
                    or results.get("trade_list")
                )
            if trades is not None:
                update_data["trades"] = trades
                try:
                    logger.info(
                        "update_backtest_results: will persist %d trades for backtest %s",
                        len(trades) if hasattr(trades, "__len__") else -1,
                        backtest_id,
                    )
                except Exception:
                    # best-effort logging; don't fail the update if logging errors
                    logger.debug("update_backtest_results: trades logging failed")

            # Equity curve
            equity_curve = (
                results.get("equity_curve") if isinstance(results, dict) else None
            )
            if equity_curve is not None:
                update_data["equity_curve"] = equity_curve
                logger.info(
                    "update_backtest_results: will persist equity_curve (len=%s) for backtest %s",
                    len(equity_curve)
                    if hasattr(equity_curve, "__len__")
                    else "unknown",
                    backtest_id,
                )

            # Populate common metrics from nested metrics dict
            if isinstance(metrics, dict):
                # Map a selection of useful fields (safe get)
                for key in [
                    "net_profit",
                    "net_profit_pct",
                    "gross_profit",
                    "gross_loss",
                    "total_commission",
                    "avg_win_value",
                    "avg_loss_value",
                    "avg_trade_value",
                    "avg_win",
                    "avg_loss",
                    "avg_trade",
                    "largest_win_value",
                    "largest_loss_value",
                    "avg_bars_in_trade",
                    "avg_bars_in_winning",
                    "avg_bars_in_losing",
                    "long_trades",
                    "short_trades",
                    "long_gross_profit",
                    "short_gross_profit",
                    "long_net_profit",
                    "short_net_profit",
                    # Added missing Long/Short metrics
                    "long_win_rate",
                    "short_win_rate",
                    "long_pnl",
                    "short_pnl",
                    "profit_factor",
                    "cagr",
                ]:
                    if key in metrics:
                        # Only set if Backtest model has this attribute or JSON columns
                        update_data[key] = metrics.get(key)
                try:
                    logger.info(
                        "update_backtest_results: extracted metric keys for backtest %s: %s",
                        backtest_id,
                        ",".join(sorted([k for k in metrics.keys()]))
                        if hasattr(metrics, "keys")
                        else str(type(metrics)),
                    )
                except Exception:
                    logger.debug("update_backtest_results: metrics logging failed")

        return self.update_backtest(backtest_id, **update_data)

    def delete_backtest(self, backtest_id: int) -> bool:
        """Удалить бэктест (CASCADE удалит связанные трейды)"""
        backtest = self.get_backtest(backtest_id)
        if not backtest:
            return False

        self.db.delete(backtest)
        self.db.commit()
        return True

    # ========================================================================
    # TRADE METHODS
    # ========================================================================

    def create_trade(
        self,
        backtest_id: int,
        entry_time: datetime,
        side: str,
        entry_price: float,
        quantity: float,
        position_size: float,
        exit_time: datetime | None = None,
        exit_price: float | None = None,
        pnl: float | None = None,
        pnl_pct: float | None = None,
        commission: float | None = None,
        exit_reason: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> Trade:
        """
        Создать новый трейд

        Args:
            backtest_id: ID бэктеста
            entry_time: Время входа
            side: Направление (LONG/SHORT)
            entry_price: Цена входа
            quantity: Количество (BTC)
            position_size: Размер позиции (USDT)
            exit_time: Время выхода
            exit_price: Цена выхода
            pnl: Прибыль/убыток (USDT)
            pnl_pct: Прибыль/убыток (%)
            commission: Комиссия (USDT)
            exit_reason: Причина выхода
            meta: Метаданные (JSON)

        Returns:
            Созданный трейд
        """
        trade = Trade(
            backtest_id=backtest_id,
            entry_time=entry_time,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            position_size=position_size,
            exit_time=exit_time,
            exit_price=exit_price,
            pnl=pnl,
            pnl_pct=pnl_pct,
            commission=commission,
            exit_reason=exit_reason,
            meta=meta,
        )
        self.db.add(trade)
        self.db.commit()
        self.db.refresh(trade)
        return trade

    def create_trades_batch(self, trades: list[dict[str, Any]]) -> int:
        """
        Создать несколько трейдов одним запросом (batch insert)

        Args:
            trades: Список словарей с данными трейдов

        Returns:
            Количество созданных трейдов
        """
        trade_objects = [Trade(**trade_data) for trade_data in trades]
        self.db.bulk_save_objects(trade_objects)
        self.db.commit()
        return len(trade_objects)

    def get_trade(self, trade_id: int) -> Trade | None:
        """Получить трейд по ID"""
        return self.db.query(Trade).filter(Trade.id == trade_id).first()

    def get_trades(
        self,
        backtest_id: int,
        side: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[Trade]:
        """
        Получить трейды бэктеста

        Args:
            backtest_id: ID бэктеста
            side: Фильтр по направлению (LONG/SHORT)
            limit: Максимум результатов
            offset: Смещение

        Returns:
            Список трейдов
        """
        query = self.db.query(Trade).filter(Trade.backtest_id == backtest_id)

        if side:
            query = query.filter(Trade.side == side)

        return query.order_by(Trade.entry_time).offset(offset).limit(limit).all()

    def get_trades_count(self, backtest_id: int) -> int:
        """Получить количество трейдов в бэктесте"""
        return (
            self.db.query(func.count(Trade.id))
            .filter(Trade.backtest_id == backtest_id)
            .scalar()
        )

    def delete_trades_by_backtest(self, backtest_id: int) -> int:
        """Удалить все трейды бэктеста"""
        count = self.db.query(Trade).filter(Trade.backtest_id == backtest_id).delete()
        self.db.commit()
        return count

    # ========================================================================
    # OPTIMIZATION METHODS
    # ========================================================================

    def create_optimization(
        self,
        strategy_id: int,
        optimization_type: str,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        param_ranges: dict[str, Any],
        metric: str,
        initial_capital: float,
        total_combinations: int,
        config: dict[str, Any] | None = None,
        status: str = "pending",
    ) -> Optimization:
        """
        Создать новую оптимизацию

        Args:
            strategy_id: ID стратегии
            optimization_type: Тип (grid_search, walk_forward, bayesian)
            symbol: Торговая пара
            timeframe: Таймфрейм
            start_date: Дата начала
            end_date: Дата окончания
            param_ranges: Диапазоны параметров (JSON)
            metric: Метрика для оптимизации (sharpe_ratio, total_return, etc.)
            initial_capital: Начальный капитал
            total_combinations: Всего комбинаций
            config: Дополнительная конфигурация
            status: Статус

        Returns:
            Созданная оптимизация
        """
        optimization = Optimization(
            strategy_id=strategy_id,
            optimization_type=optimization_type,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            param_ranges=param_ranges,
            metric=metric,
            initial_capital=initial_capital,
            total_combinations=total_combinations,
            config=config,
            status=status,
        )
        self.db.add(optimization)
        self.db.commit()
        self.db.refresh(optimization)
        return optimization

    def get_optimization(self, optimization_id: int) -> Optimization | None:
        """Получить оптимизацию по ID"""
        return (
            self.db.query(Optimization)
            .filter(Optimization.id == optimization_id)
            .first()
        )

    def get_optimizations(
        self,
        strategy_id: int | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Optimization]:
        """Получить список оптимизаций"""
        query = self.db.query(Optimization)

        if strategy_id:
            query = query.filter(Optimization.strategy_id == strategy_id)

        if status:
            query = query.filter(Optimization.status == status)

        return (
            query.order_by(desc(Optimization.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def update_optimization(
        self, optimization_id: int, **kwargs
    ) -> Optimization | None:
        """Обновить оптимизацию"""
        optimization = self.get_optimization(optimization_id)
        if not optimization:
            return None

        for key, value in kwargs.items():
            if hasattr(optimization, key):
                setattr(optimization, key, value)

        self.db.commit()
        self.db.refresh(optimization)
        return optimization

    # ========================================================================
    # OPTIMIZATION RESULT METHODS
    # ========================================================================

    def create_optimization_result(
        self,
        optimization_id: int,
        params: dict[str, Any],
        score: float,
        total_return: float | None = None,
        sharpe_ratio: float | None = None,
        max_drawdown: float | None = None,
        win_rate: float | None = None,
        total_trades: int | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> OptimizationResult:
        """Создать результат оптимизации"""
        result = OptimizationResult(
            optimization_id=optimization_id,
            params=params,
            score=score,
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            total_trades=total_trades,
            metrics=metrics,
        )
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        return result

    def create_optimization_results_batch(self, results: list[dict[str, Any]]) -> int:
        """Создать несколько результатов оптимизации (batch)"""
        result_objects = [OptimizationResult(**result_data) for result_data in results]
        self.db.bulk_save_objects(result_objects)
        self.db.commit()
        return len(result_objects)

    def get_optimization_results(
        self,
        optimization_id: int,
        limit: int = 1000,
        offset: int = 0,
        order_by_score: bool = True,
    ) -> list[OptimizationResult]:
        """Получить результаты оптимизации"""
        query = self.db.query(OptimizationResult).filter(
            OptimizationResult.optimization_id == optimization_id
        )

        if order_by_score:
            query = query.order_by(desc(OptimizationResult.score))

        return query.offset(offset).limit(limit).all()

    def get_best_optimization_result(
        self, optimization_id: int
    ) -> OptimizationResult | None:
        """Получить лучший результат оптимизации"""
        return (
            self.db.query(OptimizationResult)
            .filter(OptimizationResult.optimization_id == optimization_id)
            .order_by(desc(OptimizationResult.score))
            .first()
        )

    # ========================================================================
    # MARKET DATA METHODS (uses BybitKlineAudit table)
    # ========================================================================

    def create_market_data(
        self,
        symbol: str,
        timeframe: str,  # Maps to interval in BybitKlineAudit
        timestamp: datetime,  # Maps to open_time_dt in BybitKlineAudit
        open: float,  # Maps to open_price
        high: float,  # Maps to high_price
        low: float,  # Maps to low_price
        close: float,  # Maps to close_price
        volume: float,
        quote_volume: float | None = None,  # Maps to turnover
        trades_count: int | None = None,  # Not used, kept for compatibility
    ) -> MarketData:
        """Создать свечу в bybit_kline_audit"""
        import json

        open_time_ms = int(timestamp.timestamp() * 1000)
        candle = MarketData(
            symbol=symbol,
            interval=timeframe,
            open_time=open_time_ms,
            open_time_dt=timestamp,
            open_price=open,
            high_price=high,
            low_price=low,
            close_price=close,
            volume=volume,
            turnover=quote_volume,
            raw=json.dumps(
                {
                    "symbol": symbol,
                    "interval": timeframe,
                    "open": open,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                }
            ),
        )
        self.db.add(candle)
        self.db.commit()
        self.db.refresh(candle)
        return candle

    def create_market_data_batch(self, candles: list[dict[str, Any]]) -> int:
        """
        Создать несколько свечей (batch insert) в bybit_kline_audit

        Args:
            candles: Список словарей с данными свечей для BybitKlineAudit

        Returns:
            Количество созданных свечей
        """
        candle_objects = [MarketData(**candle_data) for candle_data in candles]
        self.db.bulk_save_objects(candle_objects)
        self.db.commit()
        return len(candle_objects)

    def get_market_data(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 10000,
        market_type: str | None = None,
    ) -> list[MarketData]:
        """
        Получить исторические свечи из bybit_kline_audit

        Args:
            symbol: Торговая пара
            timeframe: Интервал (1, 5, 15, 60, D, etc.)
            start_time: Начало периода (datetime или ISO string)
            end_time: Конец периода (datetime или ISO string)
            limit: Максимум результатов
            market_type: Тип рынка ('spot' или 'linear'), если None - без фильтра

        Returns:
            Список свечей
        """
        # Защитный парсинг - если передали строки, преобразуем в datetime
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)

        # Build base filter conditions
        filters = [
            MarketData.symbol == symbol,
            MarketData.interval == timeframe,
            MarketData.open_time >= start_ms,
            MarketData.open_time <= end_ms,
        ]

        # Add market_type filter if specified
        if market_type:
            filters.append(MarketData.market_type == market_type)

        return (
            self.db.query(MarketData)
            .filter(and_(*filters))
            .order_by(MarketData.open_time)
            .limit(limit)
            .all()
        )

    def get_latest_candle(self, symbol: str, timeframe: str) -> MarketData | None:
        """Получить последнюю свечу из bybit_kline_audit"""
        return (
            self.db.query(MarketData)
            .filter(and_(MarketData.symbol == symbol, MarketData.interval == timeframe))
            .order_by(desc(MarketData.open_time))
            .first()
        )

    def delete_market_data(
        self, symbol: str, timeframe: str, before_date: datetime | None = None
    ) -> int:
        """Удалить старые свечи из bybit_kline_audit"""
        query = self.db.query(MarketData).filter(
            and_(MarketData.symbol == symbol, MarketData.interval == timeframe)
        )

        if before_date:
            before_ms = int(before_date.timestamp() * 1000)
            query = query.filter(MarketData.open_time < before_ms)

        count = query.delete()
        self.db.commit()
        return count

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    def commit(self):
        """Commit транзакции"""
        self.db.commit()

    def rollback(self):
        """Rollback транзакции"""
        self.db.rollback()

    def close(self):
        """Закрыть сессию"""
        if self._auto_close:
            self.db.close()
