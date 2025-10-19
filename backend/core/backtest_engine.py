"""
Backtest Engine - Ядро системы бэктестирования

Этот модуль отвечает за:
- Выполнение бэктестов с историческими данными
- Интеграцию с OrderManager и PositionManager
- Расчет equity curve и метрик
- Управление стратегиями и сигналами
- Обработку комиссий, slippage и liquidation
"""

from typing import Dict, List, Any, Optional, Callable
import pandas as pd
import numpy as np
from datetime import datetime
from dataclasses import dataclass, field
import logging

from backend.core.order_manager import (
    OrderManager, Order, OrderType, OrderSide, OrderStatus
)
from backend.core.position_manager import (
    PositionManager, Position, PositionSide, PositionStatus
)
from backend.core.metrics_calculator import MetricsCalculator

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """
    Конфигурация бэктеста
    
    Attributes:
        initial_capital: Начальный капитал
        leverage: Кредитное плечо (1x-5x)
        commission_rate: Комиссия за сделку (0.0006 = 0.06%)
        slippage_rate: Проскальзывание (0.0001 = 0.01%)
        maintenance_margin_rate: Маржа поддержки (0.005 = 0.5%)
        liquidation_fee_rate: Комиссия за ликвидацию (0.001 = 0.1%)
        risk_free_rate: Безрисковая ставка для Sharpe (0.02 = 2%)
        stop_on_liquidation: Остановить бэктест при ликвидации
        max_position_size_pct: Максимальный размер позиции (% от капитала)
    """
    initial_capital: float = 10000.0
    leverage: float = 1.0
    commission_rate: float = 0.0006  # 0.06% Bybit maker
    slippage_rate: float = 0.0001  # 0.01%
    maintenance_margin_rate: float = 0.005  # 0.5%
    liquidation_fee_rate: float = 0.001  # 0.1%
    risk_free_rate: float = 0.02  # 2% годовых
    stop_on_liquidation: bool = False
    max_position_size_pct: float = 100.0  # 100% = весь капитал


@dataclass
class BacktestResult:
    """
    Результат бэктеста
    
    Attributes:
        config: Конфигурация бэктеста
        trades: Список закрытых позиций
        equity_curve: История капитала
        orders: Все ордера
        metrics: Метрики производительности
        start_time: Время начала
        end_time: Время окончания
        duration_seconds: Длительность бэктеста
        liquidation_occurred: Была ли ликвидация
        error: Ошибка (если была)
    """
    config: BacktestConfig
    trades: List[Dict[str, Any]] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=lambda: pd.Series())
    orders: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    liquidation_occurred: bool = False
    error: Optional[str] = None


class BacktestEngine:
    """
    Движок бэктестирования
    
    Выполняет симуляцию торговли на исторических данных:
    1. Загружает данные (OHLCV)
    2. Вызывает стратегию для генерации сигналов
    3. Создает ордера через OrderManager
    4. Управляет позициями через PositionManager
    5. Отслеживает equity curve
    6. Рассчитывает метрики через MetricsCalculator
    
    Example:
        # Создание конфигурации
        config = BacktestConfig(
            initial_capital=10000.0,
            leverage=2.0,
            commission_rate=0.0006
        )
        
        # Создание engine
        engine = BacktestEngine(config)
        
        # Определение стратегии
        def my_strategy(data: pd.DataFrame, state: Dict) -> Dict:
            # Генерация сигналов
            signal = 'BUY' if data['close'].iloc[-1] > data['close'].iloc[-2] else 'HOLD'
            return {'signal': signal, 'quantity': 0.1}
        
        # Запуск бэктеста
        result = engine.run(df, strategy=my_strategy)
        
        # Результаты
        print(f"Total Return: {result.metrics['total_return']:.2f}%")
        print(f"Sharpe Ratio: {result.metrics['sharpe_ratio']:.2f}")
    """
    
    def __init__(self, config: BacktestConfig):
        """
        Инициализация Backtest Engine
        
        Args:
            config: Конфигурация бэктеста
        """
        self.config = config
        
        # Managers
        self.order_manager = OrderManager(
            commission_rate=config.commission_rate,
            slippage_rate=config.slippage_rate
        )
        
        self.position_manager = PositionManager(
            commission_rate=config.commission_rate,
            maintenance_margin_rate=config.maintenance_margin_rate,
            liquidation_fee_rate=config.liquidation_fee_rate
        )
        
        self.metrics_calculator = MetricsCalculator(
            risk_free_rate=config.risk_free_rate
        )
        
        # State
        self.capital = config.initial_capital
        self.equity_curve: List[float] = []
        self.equity_timestamps: List[datetime] = []
        self.current_candle_index = 0
        self.liquidation_occurred = False
        
        logger.info(
            f"BacktestEngine initialized: capital=${config.initial_capital}, "
            f"leverage={config.leverage}x, commission={config.commission_rate*100:.2f}%"
        )
    
    def run(
        self,
        data: pd.DataFrame,
        strategy: Callable[[pd.DataFrame, Dict], Dict],
        warmup_periods: int = 50
    ) -> BacktestResult:
        """
        Запустить бэктест
        
        Args:
            data: DataFrame с OHLCV данными (columns: open, high, low, close, volume)
            strategy: Функция стратегии (принимает data и state, возвращает signal dict)
            warmup_periods: Количество свечей для прогрева индикаторов
            
        Returns:
            BacktestResult: Результат бэктеста
        """
        start_time = datetime.now()
        logger.info(f"Starting backtest: {len(data)} candles, warmup={warmup_periods}")
        
        # Валидация
        if len(data) < warmup_periods:
            error_msg = f"Not enough data: {len(data)} < {warmup_periods}"
            logger.error(error_msg)
            return BacktestResult(
                config=self.config,
                error=error_msg,
                start_time=start_time,
                end_time=datetime.now()
            )
        
        # Подготовка данных
        data = data.copy()
        if 'timestamp' not in data.columns and isinstance(data.index, pd.DatetimeIndex):
            data['timestamp'] = data.index
        
        # Сброс состояния
        self._reset()
        
        # Strategy state
        strategy_state = {
            'capital': self.capital,
            'position': None,
            'candle_index': 0
        }
        
        try:
            # Основной цикл
            for i in range(warmup_periods, len(data)):
                self.current_candle_index = i
                current_candle = data.iloc[i]
                current_time = current_candle.get('timestamp', datetime.now())
                current_price = float(current_candle['close'])
                
                # Обновление strategy state
                strategy_state['candle_index'] = i
                strategy_state['capital'] = self.capital
                strategy_state['position'] = self.position_manager.get_current_position()
                
                # Вызов стратегии
                historical_data = data.iloc[:i+1]
                signal_data = strategy(historical_data, strategy_state)
                
                # Обработка сигнала
                self._process_signal(signal_data, current_candle, current_time)
                
                # Обновление открытых позиций
                self._update_positions(current_price, current_time)
                
                # Проверка ликвидации
                liquidation_result = self._check_liquidation(current_price, current_time)
                if liquidation_result:
                    self.liquidation_occurred = True
                    if self.config.stop_on_liquidation:
                        logger.warning("Liquidation occurred! Stopping backtest.")
                        break
                
                # Обновление pending orders
                self._update_pending_orders(current_candle, current_time)
                
                # Запись equity
                self._record_equity(current_time, current_price)
            
            # Закрытие открытых позиций в конце
            self._close_remaining_positions(data.iloc[-1], "backtest_end")
            
            # Формирование результата
            result = self._build_result(
                start_time=start_time,
                end_time=datetime.now(),
                data_start=data.iloc[warmup_periods]['timestamp'] if 'timestamp' in data.columns else None,
                data_end=data.iloc[-1]['timestamp'] if 'timestamp' in data.columns else None
            )
            
            logger.info(
                f"Backtest completed: {result.metrics.get('total_trades', 0)} trades, "
                f"return={result.metrics.get('total_return', 0):.2f}%"
            )
            
            return result
            
        except Exception as e:
            logger.exception(f"Backtest error: {e}")
            return BacktestResult(
                config=self.config,
                error=str(e),
                start_time=start_time,
                end_time=datetime.now()
            )
    
    # ========================================================================
    # SIGNAL PROCESSING
    # ========================================================================
    
    def _process_signal(
        self,
        signal_data: Dict[str, Any],
        candle: pd.Series,
        current_time: datetime
    ):
        """
        Обработать сигнал от стратегии
        
        Args:
            signal_data: Dict с 'signal' ('BUY', 'SELL', 'HOLD', 'CLOSE') и другими параметрами
            candle: Текущая свеча
            current_time: Текущее время
        """
        signal = signal_data.get('signal', 'HOLD').upper()
        
        if signal == 'HOLD':
            return
        
        current_price = float(candle['close'])
        
        # CLOSE signal
        if signal == 'CLOSE':
            self._close_current_position(current_price, current_time, "signal_close")
            return
        
        # BUY/SELL signals
        has_position = self.position_manager.has_open_position()
        
        if signal == 'BUY' and not has_position:
            self._open_long_position(signal_data, current_price, current_time)
        
        elif signal == 'SELL' and not has_position:
            self._open_short_position(signal_data, current_price, current_time)
    
    def _open_long_position(
        self,
        signal_data: Dict,
        current_price: float,
        current_time: datetime
    ):
        """Открыть LONG позицию"""
        
        # Размер позиции
        quantity = signal_data.get('quantity')
        if quantity is None:
            # Используем % от капитала
            position_size_pct = signal_data.get('position_size_pct', self.config.max_position_size_pct)
            position_value = self.capital * (position_size_pct / 100)
            quantity = (position_value * self.config.leverage) / current_price
        
        # Создание market order
        order = self.order_manager.create_market_order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=quantity,
            timestamp=current_time
        )
        
        # Выполнение ордера
        executed = self.order_manager.execute_order(
            order=order,
            current_price=current_price,
            current_time=current_time,
            available_capital=self.capital
        )
        
        if executed and order.status == OrderStatus.FILLED:
            # Открытие позиции
            position = self.position_manager.open_position(
                symbol="BTCUSDT",
                side=PositionSide.LONG,
                quantity=order.filled_quantity,
                entry_price=order.filled_price,
                entry_time=current_time,
                leverage=self.config.leverage,
                capital=self.capital
            )
            
            if position:
                # Вычет margin из капитала
                required_margin = position.initial_margin + position.entry_commission
                self.capital -= required_margin
                
                logger.info(
                    f"📈 LONG opened: {position.quantity:.4f} @ ${position.entry_price:.2f}, "
                    f"margin=${required_margin:.2f}"
                )
    
    def _open_short_position(
        self,
        signal_data: Dict,
        current_price: float,
        current_time: datetime
    ):
        """Открыть SHORT позицию"""
        
        # Размер позиции
        quantity = signal_data.get('quantity')
        if quantity is None:
            position_size_pct = signal_data.get('position_size_pct', self.config.max_position_size_pct)
            position_value = self.capital * (position_size_pct / 100)
            quantity = (position_value * self.config.leverage) / current_price
        
        # Создание market order
        order = self.order_manager.create_market_order(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            quantity=quantity,
            timestamp=current_time
        )
        
        # Выполнение ордера
        executed = self.order_manager.execute_order(
            order=order,
            current_price=current_price,
            current_time=current_time,
            available_capital=self.capital
        )
        
        if executed and order.status == OrderStatus.FILLED:
            # Открытие позиции
            position = self.position_manager.open_position(
                symbol="BTCUSDT",
                side=PositionSide.SHORT,
                quantity=order.filled_quantity,
                entry_price=order.filled_price,
                entry_time=current_time,
                leverage=self.config.leverage,
                capital=self.capital
            )
            
            if position:
                required_margin = position.initial_margin + position.entry_commission
                self.capital -= required_margin
                
                logger.info(
                    f"📉 SHORT opened: {position.quantity:.4f} @ ${position.entry_price:.2f}, "
                    f"margin=${required_margin:.2f}"
                )
    
    def _close_current_position(
        self,
        current_price: float,
        current_time: datetime,
        reason: str
    ):
        """Закрыть текущую позицию"""
        
        position = self.position_manager.get_current_position()
        if not position:
            return
        
        # Создание closing order
        order_side = OrderSide.SELL if position.is_long() else OrderSide.BUY
        
        order = self.order_manager.create_market_order(
            symbol=position.symbol,
            side=order_side,
            quantity=position.quantity,
            timestamp=current_time
        )
        
        # Выполнение
        executed = self.order_manager.execute_order(
            order=order,
            current_price=current_price,
            current_time=current_time,
            available_capital=self.capital
        )
        
        if executed and order.status == OrderStatus.FILLED:
            # Закрытие позиции
            closed_position = self.position_manager.close_position(
                position=position,
                exit_price=order.filled_price,
                exit_time=current_time,
                reason=reason
            )
            
            if closed_position:
                # Возврат капитала
                returned_capital = closed_position.initial_margin + closed_position.realized_pnl
                self.capital += returned_capital
                
                logger.info(
                    f"📊 Position closed: PnL=${closed_position.realized_pnl:.2f}, "
                    f"capital=${self.capital:.2f}"
                )
    
    # ========================================================================
    # POSITION MANAGEMENT
    # ========================================================================
    
    def _update_positions(self, current_price: float, current_time: datetime):
        """Обновить открытые позиции"""
        
        position = self.position_manager.get_current_position()
        if position:
            self.position_manager.update_position(position, current_price, current_time)
    
    def _check_liquidation(self, current_price: float, current_time: datetime) -> bool:
        """
        Проверить ликвидацию
        
        Returns:
            bool: True если произошла ликвидация
        """
        position = self.position_manager.get_current_position()
        if not position:
            return False
        
        liquidated = self.position_manager.check_liquidation(
            position=position,
            current_price=current_price,
            current_time=current_time
        )
        
        if liquidated:
            # Капитал полностью потерян (margin + liquidation fee)
            loss = position.initial_margin + position.entry_commission
            logger.error(f"💥 LIQUIDATION! Loss: ${loss:.2f}")
            return True
        
        return False
    
    def _close_remaining_positions(self, last_candle: pd.Series, reason: str):
        """Закрыть все оставшиеся позиции в конце бэктеста"""
        
        position = self.position_manager.get_current_position()
        if position:
            current_price = float(last_candle['close'])
            current_time = last_candle.get('timestamp', datetime.now())
            self._close_current_position(current_price, current_time, reason)
    
    # ========================================================================
    # ORDER MANAGEMENT
    # ========================================================================
    
    def _update_pending_orders(self, candle: pd.Series, current_time: datetime):
        """
        Обновить pending orders (LIMIT, STOP)
        
        Проверяет, достигнута ли цена для исполнения
        """
        pending_orders = self.order_manager.get_pending_orders()
        
        for order in pending_orders:
            # LIMIT orders
            if order.order_type == OrderType.LIMIT:
                self._check_limit_order(order, candle, current_time)
            
            # STOP orders
            elif order.order_type in [OrderType.STOP, OrderType.STOP_MARKET]:
                self._check_stop_order(order, candle, current_time)
    
    def _check_limit_order(self, order: Order, candle: pd.Series, current_time: datetime):
        """Проверить LIMIT order"""
        
        high = float(candle['high'])
        low = float(candle['low'])
        
        # BUY LIMIT: исполняется если цена опустилась до limit price
        if order.side == OrderSide.BUY and low <= order.price:
            self.order_manager.execute_order(order, order.price, current_time, self.capital)
        
        # SELL LIMIT: исполняется если цена поднялась до limit price
        elif order.side == OrderSide.SELL and high >= order.price:
            self.order_manager.execute_order(order, order.price, current_time, self.capital)
    
    def _check_stop_order(self, order: Order, candle: pd.Series, current_time: datetime):
        """Проверить STOP order"""
        
        high = float(candle['high'])
        low = float(candle['low'])
        close = float(candle['close'])
        
        # BUY STOP: активируется если цена поднялась до stop price
        if order.side == OrderSide.BUY and high >= order.stop_price:
            execution_price = order.price if order.price else close
            self.order_manager.execute_order(order, execution_price, current_time, self.capital)
        
        # SELL STOP: активируется если цена опустилась до stop price
        elif order.side == OrderSide.SELL and low <= order.stop_price:
            execution_price = order.price if order.price else close
            self.order_manager.execute_order(order, execution_price, current_time, self.capital)
    
    # ========================================================================
    # EQUITY TRACKING
    # ========================================================================
    
    def _record_equity(self, current_time: datetime, current_price: float):
        """Записать текущий equity"""
        
        # Базовый капитал
        equity = self.capital
        
        # Добавить unrealized PnL от открытой позиции
        position = self.position_manager.get_current_position()
        if position:
            # Обновить unrealized PnL
            position.update_unrealized_pnl(current_price)
            equity += position.unrealized_pnl
        
        self.equity_curve.append(equity)
        self.equity_timestamps.append(current_time)
    
    # ========================================================================
    # RESULT BUILDING
    # ========================================================================
    
    def _build_result(
        self,
        start_time: datetime,
        end_time: datetime,
        data_start: Optional[datetime],
        data_end: Optional[datetime]
    ) -> BacktestResult:
        """Построить результат бэктеста"""
        
        # Trades
        closed_positions = self.position_manager.get_closed_positions()
        trades = [pos.to_dict() for pos in closed_positions]
        
        # Orders
        all_orders = self.order_manager.get_all_orders()
        orders = [order.to_dict() for order in all_orders]
        
        # Equity curve
        equity_series = pd.Series(
            self.equity_curve,
            index=self.equity_timestamps
        )
        
        # Metrics
        metrics = self.metrics_calculator.calculate_all(
            trades=trades,
            equity_curve=equity_series,
            initial_capital=self.config.initial_capital,
            start_date=data_start,
            end_date=data_end
        )
        
        # Duration
        duration = (end_time - start_time).total_seconds()
        
        return BacktestResult(
            config=self.config,
            trades=trades,
            equity_curve=equity_series,
            orders=orders,
            metrics=metrics,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            liquidation_occurred=self.liquidation_occurred
        )
    
    def _reset(self):
        """Сбросить состояние для нового бэктеста"""
        self.capital = self.config.initial_capital
        self.equity_curve = []
        self.equity_timestamps = []
        self.current_candle_index = 0
        self.liquidation_occurred = False
        
        self.order_manager.clear_orders()
        self.position_manager.clear_positions()


# ============================================================================
# EXAMPLE STRATEGIES
# ============================================================================

def simple_buy_hold_strategy(data: pd.DataFrame, state: Dict) -> Dict:
    """
    Простая Buy & Hold стратегия
    
    Покупает на первой свече и держит до конца
    """
    if state['position'] is None and state['candle_index'] == 50:
        return {'signal': 'BUY', 'position_size_pct': 100}
    
    return {'signal': 'HOLD'}


def simple_rsi_strategy(data: pd.DataFrame, state: Dict) -> Dict:
    """
    Простая RSI стратегия
    
    BUY: RSI < 30 (oversold)
    SELL: RSI > 70 (overbought)
    """
    # Расчет RSI
    if len(data) < 14:
        return {'signal': 'HOLD'}
    
    close = data['close'].values
    delta = np.diff(close)
    
    gains = np.where(delta > 0, delta, 0)
    losses = np.where(delta < 0, -delta, 0)
    
    avg_gain = np.mean(gains[-14:])
    avg_loss = np.mean(losses[-14:])
    
    if avg_loss == 0:
        rsi = 100
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
    
    # Сигналы
    if state['position'] is None:
        if rsi < 30:
            return {'signal': 'BUY', 'position_size_pct': 100}
    else:
        if rsi > 70:
            return {'signal': 'CLOSE'}
    
    return {'signal': 'HOLD'}


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s'
    )
    
    print("="*70)
    print("  BACKTEST ENGINE - EXAMPLE USAGE")
    print("="*70)
    
    # Генерация тестовых данных
    print("\n📊 Generating test data...")
    np.random.seed(42)
    
    dates = pd.date_range('2024-01-01', periods=200, freq='1H')
    
    # Симуляция цены с трендом
    base_price = 50000
    trend = np.linspace(0, 5000, 200)  # Восходящий тренд
    noise = np.random.normal(0, 500, 200)  # Волатильность
    close_prices = base_price + trend + noise
    
    # OHLCV
    data = pd.DataFrame({
        'timestamp': dates,
        'open': close_prices * 0.999,
        'high': close_prices * 1.002,
        'low': close_prices * 0.998,
        'close': close_prices,
        'volume': np.random.uniform(100, 1000, 200)
    })
    
    print(f"  Generated {len(data)} candles")
    print(f"  Price range: ${data['close'].min():.2f} - ${data['close'].max():.2f}")
    
    # ========================================================================
    # TEST 1: Buy & Hold Strategy
    # ========================================================================
    
    print("\n" + "="*70)
    print("  TEST 1: BUY & HOLD STRATEGY")
    print("="*70)
    
    config = BacktestConfig(
        initial_capital=10000.0,
        leverage=1.0,
        commission_rate=0.0006,
        slippage_rate=0.0001
    )
    
    engine = BacktestEngine(config)
    result = engine.run(data, strategy=simple_buy_hold_strategy, warmup_periods=50)
    
    if result.error:
        print(f"❌ Error: {result.error}")
    else:
        print(engine.metrics_calculator.format_metrics(result.metrics))
    
    # ========================================================================
    # TEST 2: RSI Strategy
    # ========================================================================
    
    print("\n" + "="*70)
    print("  TEST 2: RSI STRATEGY")
    print("="*70)
    
    config2 = BacktestConfig(
        initial_capital=10000.0,
        leverage=2.0,
        commission_rate=0.0006,
        slippage_rate=0.0001
    )
    
    engine2 = BacktestEngine(config2)
    result2 = engine2.run(data, strategy=simple_rsi_strategy, warmup_periods=50)
    
    if result2.error:
        print(f"❌ Error: {result2.error}")
    else:
        print(engine2.metrics_calculator.format_metrics(result2.metrics))
    
    print("\n" + "="*70)
    print("  ✅ Backtest Engine working correctly!")
    print("="*70)
