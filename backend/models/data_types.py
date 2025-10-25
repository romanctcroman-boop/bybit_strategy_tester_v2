"""
Pydantic Models для валидации данных
Соответствует: docs/DATA_TYPES.md версия 1.1

Все модели обеспечивают строгую типизацию и валидацию данных
на входе/выходе всех модулей системы.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime
from typing import Literal, Optional, Any, Dict, List
from enum import Enum


# ============================================================================
# 1. ИСТОРИЧЕСКИЕ ДАННЫЕ (OHLCV)
# ============================================================================

class OHLCVCandle(BaseModel):
    """
    Свечные данные OHLCV
    Источник: Bybit API v5 /v5/market/kline
    Использование: Основа для всех графиков и индикаторов
    """
    timestamp: int = Field(..., description="Unix timestamp в миллисекундах")
    time: datetime = Field(..., description="Преобразованное время")
    open: float = Field(..., gt=0, description="Цена открытия")
    high: float = Field(..., gt=0, description="Максимум")
    low: float = Field(..., gt=0, description="Минимум")
    close: float = Field(..., gt=0, description="Цена закрытия")
    volume: float = Field(..., ge=0, description="Объем торгов")
    turnover: Optional[float] = Field(None, ge=0, description="Оборот в USDT")
    
    @model_validator(mode='after')
    def validate_high_low(self):
        """Проверка: high >= max(open, close, low) и low <= min(open, close)"""
        if self.high < max(self.open, self.close, self.low):
            raise ValueError(f'High ({self.high}) must be >= max(open={self.open}, close={self.close}, low={self.low})')
        
        if self.low > min(self.open, self.close):
            raise ValueError(f'Low ({self.low}) must be <= min(open={self.open}, close={self.close})')
        
        return self
    
    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": 1719847200000,
                "time": "2025-07-01T16:15:00Z",
                "open": 38.999,
                "high": 39.311,
                "low": 38.567,
                "close": 39.147,
                "volume": 145234.56,
                "turnover": 5678901.23
            }
        }


# ============================================================================
# 2. СДЕЛКИ (TRADES LOG)
# ============================================================================

class TradeType(str, Enum):
    """Тип сделки"""
    ENTRY_LONG = "Entry long"
    EXIT_LONG = "Exit long"
    ENTRY_SHORT = "Entry short"
    EXIT_SHORT = "Exit short"


class TradeEntry(BaseModel):
    """
    Запись о входе/выходе в позицию
    Источник: Генерируется движком бэктестирования
    CSV: List-of-trades.csv
    """
    trade_number: int = Field(..., ge=1, description="Trade #")
    type: TradeType = Field(..., description="Тип сделки")
    date_time: str = Field(..., description="YYYY-MM-DD HH:MM (ISO 8601)")
    signal: str = Field(..., description="Название сигнала")
    price_usdt: float = Field(..., gt=0, description="Цена исполнения")
    position_size_qty: float = Field(..., gt=0, description="Количество контрактов")
    position_size_value: float = Field(..., gt=0, description="Стоимость позиции")
    net_pl_usdt: float = Field(..., description="Чистый P&L с комиссиями")
    net_pl_percent: float = Field(..., description="P&L в процентах")
    run_up_usdt: float = Field(..., ge=0, description="Макс. прибыль внутри сделки")
    run_up_percent: float = Field(..., ge=0, description="Run-up в %")
    drawdown_usdt: float = Field(..., le=0, description="Макс. убыток (отрицательный)")
    drawdown_percent: float = Field(..., le=0, description="Drawdown в %")
    cumulative_pl_usdt: float = Field(..., description="Накопленный P&L")
    cumulative_pl_percent: float = Field(..., description="Накопленный P&L в %")
    
    @field_validator('date_time')
    @classmethod
    def validate_datetime_format(cls, v):
        """Проверка формата даты YYYY-MM-DD HH:MM"""
        try:
            datetime.strptime(v, '%Y-%m-%d %H:%M')
        except ValueError:
            raise ValueError('Date must be in format YYYY-MM-DD HH:MM')
        return v
    
    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "trade_number": 1,
                "type": "Exit long",
                "date_time": "2025-07-02 19:00",
                "signal": "Long Trail",
                "price_usdt": 39.311,
                "position_size_qty": 3.725,
                "position_size_value": 145.271275,
                "net_pl_usdt": 1.02,
                "net_pl_percent": 0.70,
                "run_up_usdt": 1.75,
                "run_up_percent": 1.20,
                "drawdown_usdt": -8.13,
                "drawdown_percent": -5.59,
                "cumulative_pl_usdt": 0.84,
                "cumulative_pl_percent": 0.08
            }
        }


# ============================================================================
# 3. МЕТРИКИ ПРОИЗВОДИТЕЛЬНОСТИ
# ============================================================================

class PerformanceMetrics(BaseModel):
    """
    Метрики производительности стратегии
    Источник: Расчет на основе List-of-trades.csv
    CSV: Performance.csv
    """
    open_pl_usdt: float = Field(..., description="Открытый P&L в USDT")
    open_pl_percent: float = Field(..., description="Открытый P&L в %")
    net_profit_usdt: float = Field(..., description="Чистая прибыль")
    net_profit_percent: float = Field(..., description="Чистая прибыль в %")
    gross_profit_usdt: float = Field(..., ge=0, description="Сумма прибыльных сделок")
    gross_profit_percent: float = Field(..., ge=0)
    gross_loss_usdt: float = Field(..., le=0, description="Сумма убыточных сделок")
    gross_loss_percent: float = Field(..., le=0)
    commission_paid_usdt: float = Field(..., ge=0, description="Уплаченные комиссии")
    buy_hold_return_usdt: float = Field(..., description="Пассивная доходность USDT")
    buy_hold_return_percent: float = Field(..., description="Пассивная доходность %")
    max_equity_run_up_usdt: float = Field(..., ge=0, description="Макс. рост капитала")
    max_equity_run_up_percent: float = Field(..., ge=0)
    max_equity_drawdown_usdt: float = Field(..., ge=0, description="Макс. просадка")
    max_equity_drawdown_percent: float = Field(..., ge=0)
    max_contracts_held: int = Field(..., ge=0, description="Макс. позиций одновременно")
    
    class Config:
        json_schema_extra = {
            "example": {
                "open_pl_usdt": -4.22,
                "open_pl_percent": -0.30,
                "net_profit_usdt": 424.19,
                "net_profit_percent": 42.42,
                "gross_profit_usdt": 965.45,
                "gross_profit_percent": 96.54,
                "gross_loss_usdt": -541.25,
                "gross_loss_percent": -54.13,
                "commission_paid_usdt": 48.22,
                "buy_hold_return_usdt": 4.64,
                "buy_hold_return_percent": 0.46,
                "max_equity_run_up_usdt": 450.07,
                "max_equity_run_up_percent": 31.04,
                "max_equity_drawdown_usdt": 94.86,
                "max_equity_drawdown_percent": 6.55,
                "max_contracts_held": 18
            }
        }


class RiskPerformanceRatios(BaseModel):
    """
    Коэффициенты риска и эффективности
    Источник: Расчет на основе equity curve
    CSV: Risk-performance-ratios.csv
    
    Формулы (ТЗ 3.4.2):
    - Sharpe: (returns.mean() * 252) / (returns.std() * sqrt(252))
    - Sortino: (returns.mean() * 252) / (downside_std * sqrt(252))
    - Profit Factor: gross_profit / gross_loss
    """
    sharpe_ratio: float = Field(..., description="Коэффициент Шарпа (аннуализированный)")
    sortino_ratio: float = Field(..., description="Коэффициент Сортино")
    profit_factor: float = Field(..., ge=0, description="Gross Profit / Gross Loss")
    margin_calls: int = Field(..., ge=0, description="Количество маржин-коллов")
    
    @field_validator('sharpe_ratio')
    @classmethod
    def sharpe_reasonable(cls, v):
        """Проверка: Sharpe обычно в диапазоне -5 до +5"""
        if abs(v) > 10:
            raise ValueError('Sharpe ratio seems unrealistic (> 10)')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "sharpe_ratio": 1.59,
                "sortino_ratio": 2.13,
                "profit_factor": 1.784,
                "margin_calls": 0
            }
        }


class TradesAnalysis(BaseModel):
    """
    Детальный анализ сделок
    Источник: Статистический анализ List-of-trades.csv
    CSV: Trades-analysis.csv
    """
    total_trades: int = Field(..., ge=0)
    total_open_trades: int = Field(..., ge=0)
    winning_trades: int = Field(..., ge=0)
    losing_trades: int = Field(..., ge=0)
    percent_profitable: float = Field(..., ge=0, le=100, description="Win Rate %")
    avg_pl_usdt: float
    avg_pl_percent: float
    avg_winning_trade_usdt: float = Field(..., ge=0)
    avg_winning_trade_percent: float = Field(..., ge=0)
    avg_losing_trade_usdt: float = Field(..., le=0)
    avg_losing_trade_percent: float = Field(..., le=0)
    ratio_avg_win_avg_loss: float = Field(..., ge=0)
    largest_winning_trade_usdt: float = Field(..., ge=0)
    largest_winning_trade_percent: float = Field(..., ge=0)
    largest_losing_trade_usdt: float = Field(..., le=0)
    largest_losing_trade_percent: float = Field(..., le=0)
    avg_bars_in_trades: int = Field(..., ge=0)
    avg_bars_in_winning_trades: int = Field(..., ge=0)
    avg_bars_in_losing_trades: int = Field(..., ge=0)
    
    @model_validator(mode='after')
    def validate_total_trades(self):
        """total_trades должно быть >= winning_trades + losing_trades"""
        if self.total_trades < (self.winning_trades + self.losing_trades):
            raise ValueError(
                f'total_trades ({self.total_trades}) must be >= '
                f'winning_trades ({self.winning_trades}) + losing_trades ({self.losing_trades})'
            )
        return self
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_trades": 331,
                "total_open_trades": 2,
                "winning_trades": 248,
                "losing_trades": 83,
                "percent_profitable": 74.92,
                "avg_pl_usdt": 1.28,
                "avg_pl_percent": 1.12,
                "avg_winning_trade_usdt": 3.89,
                "avg_winning_trade_percent": 2.87,
                "avg_losing_trade_usdt": -6.52,
                "avg_losing_trade_percent": -4.08,
                "ratio_avg_win_avg_loss": 0.597,
                "largest_winning_trade_usdt": 12.81,
                "largest_winning_trade_percent": 6.78,
                "largest_losing_trade_usdt": -14.12,
                "largest_losing_trade_percent": -9.71,
                "avg_bars_in_trades": 56,
                "avg_bars_in_winning_trades": 50,
                "avg_bars_in_losing_trades": 75
            }
        }


# ============================================================================
# 4. КОНФИГУРАЦИЯ СТРАТЕГИИ
# ============================================================================

class PositionSizing(str, Enum):
    """Метод расчета размера позиции"""
    FIXED_PCT = "fixed_pct"
    KELLY = "kelly"
    VOLATILITY_BASED = "volatility_based"


class CapitalConfig(BaseModel):
    """Конфигурация капитала"""
    initial_deposit: float = Field(..., gt=0, description="Начальный депозит")
    leverage: int = Field(..., ge=1, le=100, description="Плечо 1x-100x")
    max_positions: int = Field(..., ge=1, description="Макс. одновременных позиций")
    position_sizing: PositionSizing
    risk_per_trade: float = Field(..., gt=0, le=100, description="Риск на сделку в %")
    
    class Config:
        use_enum_values = True


class SignalType(str, Enum):
    """Тип сигнала"""
    INDICATOR_CROSS = "indicator_cross"
    PATTERN = "pattern"
    PRICE_ACTION = "price_action"


class Signal(BaseModel):
    """Сигнал входа в позицию"""
    name: str = Field(..., description="Название сигнала")
    type: SignalType
    params: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True


class FilterType(str, Enum):
    """Тип фильтра"""
    MOVING_AVERAGE = "moving_average"
    ATR = "atr"
    VOLUME = "volume"
    TIME = "time"


class Filter(BaseModel):
    """Фильтр для подтверждения сигнала"""
    name: str
    type: FilterType
    params: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True


class EntryConditions(BaseModel):
    """Полный набор условий входа"""
    capital: CapitalConfig
    signals: List[Signal] = Field(..., min_length=1, description="Минимум 1 сигнал")
    filters: List[Filter] = Field(default_factory=list)


# ============================================================================
# 5. EXIT CONDITIONS
# ============================================================================

class ExitType(str, Enum):
    """Тип выхода"""
    FIXED_PCT = "fixed_pct"
    ATR_BASED = "atr_based"
    DYNAMIC = "dynamic"


class TakeProfitConfig(BaseModel):
    """Конфигурация тейк-профита"""
    enabled: bool
    type: ExitType
    value: float = Field(..., gt=0, description="Значение в % или множитель ATR")
    signal_name: str = Field(default="Long Cond TP")


class StopLossConfig(BaseModel):
    """Конфигурация стоп-лосса"""
    enabled: bool
    type: Literal["fixed_pct", "atr_based"]
    value: float = Field(..., gt=0)
    signal_name: str = Field(default="Long Cond SL")


class TrailingStopConfig(BaseModel):
    """Конфигурация трейлинг-стопа"""
    enabled: bool
    activation: float = Field(..., gt=0, description="% прибыли для активации")
    distance: float = Field(..., gt=0, description="% отступ от максимума")
    signal_name: str = Field(default="Long Trail")


class TimeExitConfig(BaseModel):
    """Конфигурация выхода по времени"""
    enabled: bool
    max_bars: int = Field(..., gt=0, description="Макс. баров в позиции")
    signal_name: str = Field(default="Time Exit")


class ExitConditions(BaseModel):
    """Полный набор условий выхода"""
    take_profit: TakeProfitConfig
    stop_loss: StopLossConfig
    trailing_stop: TrailingStopConfig
    time_exit: TimeExitConfig


# ============================================================================
# 6. РЕЗУЛЬТАТЫ ОПТИМИЗАЦИИ
# ============================================================================

class OptimizationResult(BaseModel):
    """Результат одной комбинации параметров"""
    parameters: Dict[str, float] = Field(..., description="Протестированные параметры")
    metrics: PerformanceMetrics
    score: float = Field(..., description="Функция полезности")
    rank: int = Field(..., ge=1, description="Позиция в рейтинге")


# ============================================================================
# 7. EQUITY CURVE
# ============================================================================

class EquityPoint(BaseModel):
    """Точка на equity curve"""
    timestamp: int
    date_time: str = Field(..., description="YYYY-MM-DD HH:MM")
    equity: float = Field(..., gt=0, description="Текущий капитал")
    drawdown: float = Field(..., ge=0, description="Просадка от пика")
    cumulative_pl: float = Field(..., description="Накопленный P&L")
    
    @field_validator('date_time')
    @classmethod
    def validate_datetime_format(cls, v):
        """Проверка формата даты"""
        try:
            datetime.strptime(v, '%Y-%m-%d %H:%M')
        except ValueError:
            raise ValueError('Date must be in format YYYY-MM-DD HH:MM')
        return v


# ============================================================================
# 8. BACKTEST РЕЗУЛЬТАТЫ (Complete Response)
# ============================================================================

class BacktestResults(BaseModel):
    """
    Полный результат бэктеста
    Возвращается из BacktestEngine.run()
    """
    final_capital: float = Field(..., gt=0)
    total_return: float
    total_trades: int = Field(..., ge=0)
    winning_trades: int = Field(..., ge=0)
    losing_trades: int = Field(..., ge=0)
    win_rate: float = Field(..., ge=0, le=100)
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float = Field(..., ge=0, le=1, description="As decimal (0.065 = 6.5%)")
    profit_factor: float = Field(..., ge=0)
    
    # Extended metrics
    metrics: Dict[str, float] = Field(default_factory=dict)
    
    # Trades list
    trades: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Equity curve (list of dicts or floats, flexible)
    equity_curve: List[Any] = Field(default_factory=list)
    
    class Config:
        json_schema_extra = {
            "example": {
                "final_capital": 10424.19,
                "total_return": 0.4242,
                "total_trades": 331,
                "winning_trades": 248,
                "losing_trades": 83,
                "win_rate": 74.92,
                "sharpe_ratio": 1.59,
                "sortino_ratio": 2.13,
                "max_drawdown": 0.0655,
                "profit_factor": 1.784,
                "metrics": {
                    "net_profit": 424.19,
                    "buy_hold_return": 4.64,
                    "buy_hold_return_pct": 0.46
                }
            }
        }
