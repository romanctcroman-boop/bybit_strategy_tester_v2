"""
🏗️ UNIFIED BACKTEST ENGINE INTERFACES
Общие интерфейсы для всех движков бэктестинга.
Обеспечивает независимость и сравнимость результатов.

Архитектура:
- BacktestInput: унифицированный вход для всех движков
- BacktestOutput: унифицированный выход для сравнения точности
- BaseBacktestEngine: абстрактный базовый класс
"""

from abc import ABC, abstractmethod


def recalculate_tp_portions(
    portions: tuple[float, ...],
    changed_index: int,
) -> tuple[float, ...]:
    """
    Автопересчёт portions после изменения одного из TP.

    Логика:
    - Сумма portions должна быть = 1.0 (100%)
    - Изменённые portions (0..changed_index) остаются как есть
    - Остальные делят остаток поровну

    Args:
        portions: Текущие portions (например (0.30, 0.25, 0.25, 0.20))
        changed_index: Индекс последнего изменённого TP (0-based)

    Returns:
        Новые portions с суммой = 1.0

    Example:
        >>> recalculate_tp_portions((0.40, 0.25, 0.25, 0.10), 0)
        (0.40, 0.20, 0.20, 0.20)  # TP1=40%, остальные по 20%

        >>> recalculate_tp_portions((0.40, 0.30, 0.25, 0.05), 1)
        (0.40, 0.30, 0.15, 0.15)  # TP1=40%, TP2=30%, остальные по 15%
    """
    portions_list: list[float] = list(portions)
    n = len(portions_list)

    if changed_index < 0 or changed_index >= n:
        return tuple(portions_list)

    # Считаем сумму уже зафиксированных portions (0..changed_index включительно)
    fixed_sum = sum(portions_list[: changed_index + 1])

    # Остаток для распределения
    remaining = max(0.0, 1.0 - fixed_sum)

    # Количество portions для распределения
    remaining_count = n - changed_index - 1

    if remaining_count > 0:
        each = remaining / remaining_count
        for i in range(changed_index + 1, n):
            portions_list[i] = round(each, 4)

    # Корректировка последнего для точной суммы = 1.0
    current_sum = sum(portions_list)
    if abs(current_sum - 1.0) > 0.0001:
        portions_list[-1] = round(portions_list[-1] + (1.0 - current_sum), 4)

    return tuple(portions_list)


from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd


class TradeDirection(Enum):
    """Направление торговли"""

    LONG = "long"
    SHORT = "short"
    BOTH = "both"


class TpMode(Enum):
    """
    Режим Take Profit - три взаимоисключающие системы.

    FIXED: Фиксированный TP в процентах (take_profit=0.03 = 3%)
    ATR: Динамический TP на основе ATR (atr_tp_multiplier x ATR)
    MULTI: Частичное закрытие на 4 уровнях TP (TP1-TP4)

    ⚠️ ВЗАИМНАЯ БЛОКИРОВКА:
    - FIXED и ATR не могут быть активны одновременно для TP
    - MULTI заменяет любой одиночный TP полностью
    - ATR-SL может работать с любым режимом TP
    """

    FIXED = "fixed"  # Фиксированный TP %
    ATR = "atr"  # ATR-based TP
    MULTI = "multi"  # Multi-level TP (TP1-TP4)


class SlMode(Enum):
    """
    Режим Stop Loss.

    FIXED: Фиксированный SL в процентах (stop_loss=0.02 = 2%)
    ATR: Динамический SL на основе ATR (atr_sl_multiplier x ATR)

    Примечание: SL режим независим от TP режима.
    Fixed SL может использоваться как MAX-лимит для ATR-SL.
    """

    FIXED = "fixed"  # Фиксированный SL %
    ATR = "atr"  # ATR-based SL


class ExitReason(Enum):
    """Причина закрытия позиции"""

    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    SIGNAL = "signal"
    END_OF_DATA = "end_of_data"
    MAX_DRAWDOWN = "max_drawdown"
    TRAILING_STOP = "trailing_stop"
    # Time-based exits
    TIME_EXIT = "time_exit"  # max_bars_in_trade
    SESSION_CLOSE = "session_close"  # exit_on_session_close
    WEEKEND_CLOSE = "weekend_close"  # exit_end_of_week
    # Order-related
    LIMIT_TIMEOUT = "limit_timeout"  # Лимитный ордер истёк
    # Fallback
    UNKNOWN = "unknown"  # For cases where exit_reason is None


@dataclass
class TradeRecord:
    """Унифицированная запись о сделке"""

    entry_time: datetime
    exit_time: datetime
    direction: str  # "long" или "short"
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    pnl_pct: float
    fees: float
    exit_reason: ExitReason
    duration_bars: int

    # Bar Magnifier данные (опционально)
    intrabar_sl_hit: bool = False
    intrabar_tp_hit: bool = False
    intrabar_exit_price: float | None = None

    # MFE/MAE (Maximum Favorable/Adverse Excursion)
    mfe: float = 0.0  # Максимальная прибыль во время сделки
    mae: float = 0.0  # Максимальный убыток во время сделки


@dataclass
class BacktestInput:
    """
    Унифицированный вход для всех движков.
    Все движки получают ОДИНАКОВЫЕ данные.
    """

    # === РЫНОЧНЫЕ ДАННЫЕ ===
    candles: pd.DataFrame  # Основной таймфрейм (OHLCV)
    candles_1m: pd.DataFrame | None = None  # 1-минутные для Bar Magnifier

    # === СИГНАЛЫ ===
    long_entries: np.ndarray | None = None  # bool array
    long_exits: np.ndarray | None = None  # bool array
    short_entries: np.ndarray | None = None  # bool array
    short_exits: np.ndarray | None = None  # bool array

    # === КОНФИГУРАЦИЯ ===
    symbol: str = "BTCUSDT"
    interval: str = "60"
    initial_capital: float = 10000.0
    position_size: float = 0.10  # 10% от капитала (используется если use_fixed_amount=False)
    use_fixed_amount: bool = False  # True = использовать fixed_amount вместо position_size
    fixed_amount: float = 0.0  # Фиксированная сумма в USDT (как в TradingView)
    leverage: int = 10

    # === РИСК-МЕНЕДЖМЕНТ ===
    stop_loss: float = 0.02  # 2% - базовый SL (или MAX-лимит для ATR)
    take_profit: float = 0.03  # 3% - базовый TP (игнорируется при multi_tp)
    direction: TradeDirection = TradeDirection.BOTH

    # === РЕЖИМЫ ВЫХОДА (ВЗАИМОИСКЛЮЧАЮЩИЕ) ===
    # TP Mode: FIXED (по умолчанию), ATR, или MULTI
    tp_mode: TpMode = TpMode.FIXED
    # SL Mode: FIXED (по умолчанию) или ATR
    sl_mode: SlMode = SlMode.FIXED
    # Использовать fixed SL как максимальный лимит для ATR-SL
    sl_max_limit_enabled: bool = True

    # === ИЗДЕРЖКИ ===
    taker_fee: float = 0.0007  # 0.07% — TradingView parity (CLAUDE.md §5)
    maker_fee: float = 0.0006  # 0.06%
    slippage: float = 0.0005  # 0.05%

    # === ОПЦИИ ===
    use_bar_magnifier: bool = True  # Использовать 1m данные для SL/TP
    max_drawdown_limit: float = 0.0  # Лимит просадки (0 = без лимита)
    pyramiding: int = 1  # Макс. позиций одновременно (0 или 1 = отключено)
    close_entries_rule: str = "ALL"  # Правило закрытия: "ALL", "FIFO", "LIFO"

    # === DCA (Dollar Cost Averaging) ===
    # Первый вход по сигналу, остальные по лимитным уровням
    dca_enabled: bool = False  # Включить DCA режим
    dca_safety_orders: int = 0  # Количество Safety Orders (0 = отключено)
    dca_price_deviation: float = 0.01  # Первый SO при падении на 1%
    dca_step_scale: float = 1.4  # Мультипликатор шага (SO2 на 1.4%, SO3 на 1.96%...)
    dca_volume_scale: float = 1.0  # Мультипликатор объёма (1.0 = без мартингейла)
    dca_base_order_size: float = 0.1  # Размер базового ордера (10% капитала)
    dca_safety_order_size: float = 0.1  # Размер первого SO (10% капитала)

    # === MULTI-LEVEL TP (tp_mode=MULTI) ===
    # TP1-TP4: частичное закрытие на 4 уровнях
    # Активируется когда tp_mode = TpMode.MULTI
    tp_levels: tuple[float, ...] = (
        0.005,
        0.010,
        0.015,
        0.020,
    )  # Уровни TP в % от входа (0.5%, 1%, 1.5%, 2%)
    tp_portions: tuple[float, ...] = (
        0.25,
        0.25,
        0.25,
        0.25,
    )  # Доли закрытия (сумма = 1.0, по умолчанию 25% каждый)

    # === ATR ПАРАМЕТРЫ (для tp_mode=ATR или sl_mode=ATR) ===
    atr_period: int = 14  # Период ATR
    atr_tp_multiplier: float = 2.0  # TP = Entry +/- ATR x multiplier
    atr_sl_multiplier: float = 1.5  # SL = Entry -/+ ATR x multiplier

    # === TRAILING STOP (Трейлинг стоп) ===
    # Работает с любым режимом TP, активируется после входа
    trailing_stop_enabled: bool = False  # Включить трейлинг стоп
    trailing_stop_activation: float = 0.01  # Активация при прибыли 1%
    trailing_stop_distance: float = 0.005  # Дистанция трейлинга 0.5%

    # === BREAKEVEN STOP (Стоп в безубыток) ===
    # После срабатывания TP1 (или первого TP), SL переносится в безубыток
    # Работает только с tp_mode=MULTI
    breakeven_enabled: bool = False  # Включить перенос SL в безубыток
    breakeven_mode: str = "average"  # "average" = на среднюю цену входа, "tp" = на предыдущий TP
    breakeven_offset: float = 0.0  # Отступ от безубытка (0.001 = +0.1% от средней)

    # =========================================================================
    # === TIME-BASED EXITS (Выходы по времени) ===
    # =========================================================================
    max_bars_in_trade: int = 0  # Закрыть позицию через N баров (0 = отключено)
    exit_on_session_close: bool = False  # Закрыть все позиции в конце сессии
    session_start_hour: int = 0  # Час начала торговой сессии (0-23 UTC)
    session_end_hour: int = 24  # Час конца сессии (24 = конец дня)
    no_trade_days: tuple[int, ...] = ()  # Дни без торговли (0=Пн, 6=Вс)
    no_trade_hours: tuple[int, ...] = ()  # Часы без входов (например (0,1,2,3))
    exit_end_of_week: bool = False  # Закрыть позиции в пятницу вечером
    exit_before_weekend: int = 0  # Закрыть за N часов до конца пятницы
    # Timezone для time filter: "UTC", "US/Eastern", "Europe/London", "Asia/Tokyo"
    timezone: str = "UTC"

    # =========================================================================
    # === POSITION SIZING (Размер позиции) ===
    # =========================================================================
    position_sizing_mode: str = "fixed"  # "fixed", "risk", "kelly", "volatility"
    # fixed: использует position_size (% от капитала)
    # risk: размер = risk_per_trade / stop_loss (риск фиксирован)
    # kelly: оптимальный Kelly с kelly_fraction
    # volatility: обратно пропорционально ATR
    risk_per_trade: float = 0.01  # Риск на сделку 1% (для mode="risk")
    kelly_fraction: float = 0.5  # Доля от оптимального Kelly (0.5 = Half-Kelly)
    volatility_target: float = 0.02  # Целевая волатильность 2% (для mode="volatility")
    max_position_size: float = 1.0  # Максимум позиции (1.0 = 100% капитала)
    min_position_size: float = 0.01  # Минимум позиции (0.01 = 1% капитала)

    # =========================================================================
    # === RE-ENTRY RULES (Правила повторного входа) ===
    # =========================================================================
    allow_re_entry: bool = True  # Разрешить вход после выхода
    re_entry_delay_bars: int = 0  # Ждать N баров перед повторным входом
    max_trades_per_day: int = 0  # Лимит сделок в день (0 = без лимита)
    max_trades_per_week: int = 0  # Лимит сделок в неделю (0 = без лимита)
    max_consecutive_losses: int = 0  # Стоп торговли после N убытков подряд
    cooldown_after_loss: int = 0  # Пауза N баров после убыточной сделки

    # =========================================================================
    # === ADVANCED ORDER TYPES (Продвинутые ордера) ===
    # =========================================================================
    entry_order_type: str = "market"  # "market", "limit", "stop"
    # market: немедленное исполнение по рынку
    # limit: лимитный ордер с отступом
    # stop: стоп-ордер (вход на пробой)
    limit_entry_offset: float = 0.001  # Отступ лимитника от цены (0.1%)
    limit_entry_timeout_bars: int = 5  # Отмена лимитника через N баров
    stop_entry_offset: float = 0.001  # Отступ стоп-ордера от цены

    # =========================================================================
    # === PARTIAL ENTRY (Масштабирование входа) ===
    # =========================================================================
    scale_in_enabled: bool = False  # Частичный вход (scale-in)
    scale_in_levels: tuple[float, ...] = (1.0,)  # Уровни входа (1.0 = сразу 100%)
    scale_in_portions: tuple[float, ...] = (1.0,)  # Доли на каждом уровне
    # Пример: levels=(0, 0.01, 0.02), portions=(0.33, 0.33, 0.34)
    # = 33% сразу, 33% при +1%, 34% при +2%

    # =========================================================================
    # === PORTFOLIO & CORRELATION (Портфель и корреляция) ===
    # =========================================================================
    hedge_mode: bool = False  # Разрешить одновременные long и short
    max_open_positions: int = 1  # Максимум открытых позиций (для multi-symbol)
    max_correlated_positions: int = 0  # Лимит коррелирующих позиций (0 = без лимита)
    portfolio_heat_limit: float = 0.0  # Макс. риск портфеля (0 = без лимита)

    # =========================================================================
    # === SLIPPAGE MODEL (Модель проскальзывания) ===
    # =========================================================================
    slippage_model: str = "fixed"  # "fixed", "volume", "volatility", "combined"
    # fixed: slippage = slippage (константа)
    # volume: slippage зависит от размера позиции и объёма бара
    # volatility: slippage зависит от ATR/волатильности
    # combined: комбинация volume + volatility
    slippage_volume_impact: float = 0.1  # Коэффициент влияния объёма (для volume model)
    slippage_volatility_mult: float = 0.5  # Множитель ATR для slippage (для volatility)

    # =========================================================================
    # === FUNDING RATE (Ставка финансирования для perpetual futures) ===
    # =========================================================================
    include_funding: bool = False  # Учитывать funding rate
    funding_rate: float = 0.0001  # Фиксированная ставка (0.01% каждые 8 часов)
    funding_interval_hours: int = 8  # Интервал списания (Bybit = 8 часов)
    use_historical_funding: bool = False  # Использовать исторические данные funding

    # =========================================================================
    # === MARKET CONDITION FILTERS (Фильтры рыночных условий) ===
    # =========================================================================
    # Volatility Filter - не торговать при экстремальной волатильности
    volatility_filter_enabled: bool = False
    min_volatility_percentile: float = 10.0  # Мин. волатильность (процентиль ATR)
    max_volatility_percentile: float = 90.0  # Макс. волатильность (процентиль ATR)
    volatility_lookback: int = 100  # Окно для расчёта процентиля

    # Volume Filter - не торговать при низком объёме
    volume_filter_enabled: bool = False
    min_volume_percentile: float = 20.0  # Мин. объём (процентиль)
    volume_lookback: int = 50  # Окно для расчёта процентиля

    # Spread/Liquidity Filter - не торговать при широком спреде
    spread_filter_enabled: bool = False
    max_spread_pct: float = 0.001  # Макс. допустимый спред (0.1%)

    # Trend Filter - торговать только по тренду
    trend_filter_enabled: bool = False
    trend_filter_period: int = 200  # Период SMA для определения тренда
    trend_filter_mode: str = "with"  # "with" - по тренду, "against" - контртренд

    # Momentum Filter - фильтр по моментуму (RSI)
    momentum_filter_enabled: bool = False
    momentum_oversold: float = 30.0  # Зона перепроданности
    momentum_overbought: float = 70.0  # Зона перекупленности
    momentum_period: int = 14  # Период RSI

    # Range Filter - не торговать в боковике
    range_filter_enabled: bool = False
    range_adr_min: float = 0.01  # Мин. ADR (Average Daily Range) как % цены
    range_lookback: int = 20  # Окно для расчёта ADR

    # =========================================================================
    # === MARKET REGIME DETECTOR (Детектор рыночного режима) ===
    # =========================================================================
    # Определяет режим рынка и фильтрует сигналы в неподходящих условиях
    market_regime_enabled: bool = False  # Включить детектор режима рынка
    market_regime_filter: str = "not_volatile"  # Разрешённые режимы:
    # "all" - торговать всегда
    # "trending" - только в тренде (Hurst > 0.55)
    # "ranging" - только в боковике (Hurst < 0.45)
    # "volatile" - только при высокой волатильности
    # "not_volatile" - исключать высоковолатильные периоды
    market_regime_lookback: int = 50  # Окно для расчёта режима

    # =========================================================================
    # === ADAPTIVE ATR MULTIPLIER ===
    # =========================================================================
    adaptive_atr_enabled: bool = False  # Включить адаптивный ATR
    adaptive_atr_lookback: int = 100  # Окно для расчёта волатильности ATR

    # =========================================================================
    # === MULTI-TIMEFRAME (MTF) FILTERING ===
    # =========================================================================
    # HTF trend filter - торговать только в направлении HTF тренда
    # Пример: RSI на 5m, но только если цена > SMA200 на 1H
    mtf_enabled: bool = False  # Включить MTF фильтрацию
    mtf_htf_interval: str = "60"  # Интервал HTF (старший ТФ): "60"=1H, "240"=4H, "D"=Day
    mtf_htf_candles: pd.DataFrame | None = None  # HTF OHLCV данные
    mtf_htf_index_map: np.ndarray | None = None  # Маппинг LTF→HTF (от index_mapper)
    mtf_filter_type: str = "sma"  # Тип HTF фильтра: "sma", "ema"
    mtf_filter_period: int = 200  # Период индикатора HTF (например, SMA200)
    mtf_neutral_zone_pct: float = 0.0  # Нейтральная зона % (0 = строгий режим)
    mtf_lookahead_mode: str = "none"  # "none" (безопасный) или "allow" (исследования)

    # BTC Correlation filter - торговать альты только по направлению BTC
    # Пример: LONG на ETHUSDT только если BTC > SMA50
    mtf_btc_filter_enabled: bool = False  # Включить BTC корреляцию
    mtf_btc_candles: pd.DataFrame | None = None  # BTC OHLCV данные
    mtf_btc_index_map: np.ndarray | None = None  # Маппинг LTF→BTC
    mtf_btc_filter_period: int = 50  # Период SMA для BTC (например, D50)

    # === LEGACY COMPATIBILITY (deprecated, use tp_mode/sl_mode) ===
    multi_tp_enabled: bool = False  # DEPRECATED: use tp_mode=TpMode.MULTI
    atr_enabled: bool = False  # DEPRECATED: use sl_mode=SlMode.ATR or tp_mode=TpMode.ATR

    def __post_init__(self):
        """
        Автоматическое исправление технических ограничений.
        Вызывается автоматически после создания dataclass.
        """
        import warnings

        # =====================================================================
        # FIX 1: use_bar_magnifier=False если нет 1m данных
        # =====================================================================
        if self.use_bar_magnifier and self.candles_1m is None:
            object.__setattr__(self, "use_bar_magnifier", False)
            warnings.warn(
                "⚠️ use_bar_magnifier автоматически отключен: 1m данные не предоставлены",
                UserWarning,
                stacklevel=2,
            )

        # =====================================================================
        # FIX 2: breakeven требует TpMode.MULTI - автопереключение
        # =====================================================================
        if self.breakeven_enabled and self.tp_mode != TpMode.MULTI:
            object.__setattr__(self, "tp_mode", TpMode.MULTI)
            # Установим дефолтные tp_levels/tp_portions если не заданы
            if self.tp_levels == (0.005, 0.010, 0.015, 0.020):
                # Стандартные уровни для автопереключения
                object.__setattr__(self, "tp_levels", (0.01, 0.02, 0.03, 0.05))
            warnings.warn(
                "⚠️ tp_mode автоматически переключен на MULTI: breakeven_enabled=True требует Multi-TP",
                UserWarning,
                stacklevel=2,
            )

        # =====================================================================
        # FIX 3: candles должен быть DataFrame с datetime index
        # =====================================================================
        if self.candles is not None:
            # Если это не DataFrame - попробуем конвертировать
            if not isinstance(self.candles, pd.DataFrame):
                try:
                    df = pd.DataFrame(self.candles)
                    if "open_time" in df.columns:
                        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
                        df.set_index("open_time", inplace=True)
                    object.__setattr__(self, "candles", df)
                    warnings.warn(
                        "⚠️ candles автоматически конвертирован в DataFrame с datetime index",
                        UserWarning,
                        stacklevel=2,
                    )
                except Exception:
                    pass  # Оставим как есть, validate() покажет ошибку

            # Если DataFrame но без datetime index
            elif isinstance(self.candles, pd.DataFrame) and not isinstance(self.candles.index, pd.DatetimeIndex):
                df = self.candles.copy()
                if "open_time" in df.columns:
                    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
                    df.set_index("open_time", inplace=True)
                    object.__setattr__(self, "candles", df)
                    warnings.warn(
                        "⚠️ candles.index автоматически конвертирован в DatetimeIndex",
                        UserWarning,
                        stacklevel=2,
                    )

        # =====================================================================
        # FIX 4: htf_index_map должен быть np.int32
        # =====================================================================
        if self.mtf_htf_index_map is not None:
            if isinstance(self.mtf_htf_index_map, np.ndarray):
                if self.mtf_htf_index_map.dtype != np.int32:
                    fixed_map = self.mtf_htf_index_map.astype(np.int32)
                    object.__setattr__(self, "mtf_htf_index_map", fixed_map)
                    warnings.warn(
                        f"⚠️ mtf_htf_index_map dtype конвертирован из {self.mtf_htf_index_map.dtype} в np.int32",
                        UserWarning,
                        stacklevel=2,
                    )
            elif isinstance(self.mtf_htf_index_map, (list, tuple)):
                fixed_map = np.array(self.mtf_htf_index_map, dtype=np.int32)
                object.__setattr__(self, "mtf_htf_index_map", fixed_map)
                warnings.warn(
                    "⚠️ mtf_htf_index_map автоматически конвертирован в np.ndarray(dtype=np.int32)",
                    UserWarning,
                    stacklevel=2,
                )

        # =====================================================================
        # FIX 5: HTF candles также должен быть DataFrame
        # =====================================================================
        if self.mtf_htf_candles is not None and not isinstance(self.mtf_htf_candles, pd.DataFrame):
            try:
                df = pd.DataFrame(self.mtf_htf_candles)
                if "open_time" in df.columns:
                    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
                    df.set_index("open_time", inplace=True)
                object.__setattr__(self, "mtf_htf_candles", df)
            except Exception:
                pass

        # =====================================================================
        # FIX 6: BTC candles для MTF фильтра
        # =====================================================================
        if self.mtf_btc_candles is not None and not isinstance(self.mtf_btc_candles, pd.DataFrame):
            try:
                df = pd.DataFrame(self.mtf_btc_candles)
                if "open_time" in df.columns:
                    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
                    df.set_index("open_time", inplace=True)
                object.__setattr__(self, "mtf_btc_candles", df)
            except Exception:
                pass

    def validate(self) -> tuple[bool, list[str]]:
        """Валидация входных данных с проверкой взаимной блокировки режимов."""
        errors = []

        # === БАЗОВАЯ ВАЛИДАЦИЯ ===
        if self.candles is None or len(self.candles) == 0:
            errors.append("Candles DataFrame пуст или None")

        if self.use_bar_magnifier and self.candles_1m is None:
            errors.append("Bar Magnifier включен, но 1m данные не предоставлены")

        if self.stop_loss < 0 or self.stop_loss > 1:
            errors.append(f"stop_loss должен быть 0-1, получено: {self.stop_loss}")

        if self.take_profit < 0 or self.take_profit > 1:
            errors.append(f"take_profit должен быть 0-1, получено: {self.take_profit}")

        if self.position_size <= 0 or self.position_size > 1:
            errors.append(f"position_size должен быть 0-1, получено: {self.position_size}")

        # === ВАЛИДАЦИЯ РЕЖИМОВ ВЫХОДА ===

        # Legacy compatibility: преобразование старых флагов в новые режимы
        effective_tp_mode = self.tp_mode
        effective_sl_mode = self.sl_mode

        if self.multi_tp_enabled and self.tp_mode == TpMode.FIXED:
            effective_tp_mode = TpMode.MULTI
        if self.atr_enabled:
            if self.tp_mode == TpMode.FIXED and not self.multi_tp_enabled:
                effective_tp_mode = TpMode.ATR
            if self.sl_mode == SlMode.FIXED:
                effective_sl_mode = SlMode.ATR

        # Валидация Multi-level TP (tp_mode=MULTI)
        if effective_tp_mode == TpMode.MULTI:
            if len(self.tp_levels) != len(self.tp_portions):
                errors.append(
                    f"tp_levels и tp_portions должны иметь одинаковую длину: "
                    f"{len(self.tp_levels)} != {len(self.tp_portions)}"
                )
            if len(self.tp_levels) != 4:
                errors.append(f"Multi-TP требует ровно 4 уровня, получено: {len(self.tp_levels)}")
            portions_sum = sum(self.tp_portions)
            if abs(portions_sum - 1.0) > 0.001:
                errors.append(f"Сумма tp_portions должна быть 1.0, получено: {portions_sum:.4f}")
            # Проверка что уровни возрастают
            for i in range(1, len(self.tp_levels)):
                if self.tp_levels[i] <= self.tp_levels[i - 1]:
                    errors.append(
                        f"tp_levels должны возрастать: TP{i}={self.tp_levels[i - 1]} >= TP{i + 1}={self.tp_levels[i]}"
                    )

        # Валидация ATR параметров (если используется ATR)
        if effective_tp_mode == TpMode.ATR or effective_sl_mode == SlMode.ATR:
            if self.atr_period < 1:
                errors.append(f"atr_period должен быть >= 1, получено: {self.atr_period}")
            if effective_tp_mode == TpMode.ATR and self.atr_tp_multiplier <= 0:
                errors.append(f"atr_tp_multiplier должен быть > 0, получено: {self.atr_tp_multiplier}")
            if effective_sl_mode == SlMode.ATR and self.atr_sl_multiplier <= 0:
                errors.append(f"atr_sl_multiplier должен быть > 0, получено: {self.atr_sl_multiplier}")

        # === ВАЛИДАЦИЯ BREAKEVEN ===
        if self.breakeven_enabled:
            if effective_tp_mode != TpMode.MULTI:
                errors.append("Breakeven SL работает только с tp_mode=MULTI (Multi-level TP)")
            if self.breakeven_mode not in ("average", "tp"):
                errors.append(f"breakeven_mode должен быть 'average' или 'tp', получено: {self.breakeven_mode}")

        # === ВАЛИДАЦИЯ TRAILING STOP ===
        if self.trailing_stop_enabled:
            if self.trailing_stop_activation <= 0:
                errors.append(f"trailing_stop_activation должен быть > 0, получено: {self.trailing_stop_activation}")
            if self.trailing_stop_distance <= 0:
                errors.append(f"trailing_stop_distance должен быть > 0, получено: {self.trailing_stop_distance}")

        # === ВАЛИДАЦИЯ TIME-BASED EXITS ===
        if self.max_bars_in_trade < 0:
            errors.append(f"max_bars_in_trade должен быть >= 0, получено: {self.max_bars_in_trade}")
        if self.session_start_hour < 0 or self.session_start_hour > 23:
            errors.append(f"session_start_hour должен быть 0-23, получено: {self.session_start_hour}")
        if self.session_end_hour < 1 or self.session_end_hour > 24:
            errors.append(f"session_end_hour должен быть 1-24, получено: {self.session_end_hour}")
        if self.session_start_hour >= self.session_end_hour:
            errors.append("session_start_hour должен быть < session_end_hour")
        for day in self.no_trade_days:
            if day < 0 or day > 6:
                errors.append(f"no_trade_days: день {day} вне диапазона 0-6")
        for hour in self.no_trade_hours:
            if hour < 0 or hour > 23:
                errors.append(f"no_trade_hours: час {hour} вне диапазона 0-23")

        # === ВАЛИДАЦИЯ POSITION SIZING ===
        valid_sizing_modes = ("fixed", "risk", "kelly", "volatility")
        if self.position_sizing_mode not in valid_sizing_modes:
            errors.append(f"position_sizing_mode должен быть одним из {valid_sizing_modes}")
        if self.risk_per_trade <= 0 or self.risk_per_trade > 1:
            errors.append(f"risk_per_trade должен быть 0-1, получено: {self.risk_per_trade}")
        if self.kelly_fraction <= 0 or self.kelly_fraction > 1:
            errors.append(f"kelly_fraction должен быть 0-1, получено: {self.kelly_fraction}")
        if self.max_position_size <= 0 or self.max_position_size > 1:
            errors.append(f"max_position_size должен быть 0-1, получено: {self.max_position_size}")
        if self.min_position_size < 0 or self.min_position_size > self.max_position_size:
            errors.append("min_position_size должен быть 0-max_position_size")

        # === ВАЛИДАЦИЯ RE-ENTRY RULES ===
        if self.re_entry_delay_bars < 0:
            errors.append("re_entry_delay_bars должен быть >= 0")
        if self.max_trades_per_day < 0:
            errors.append("max_trades_per_day должен быть >= 0")
        if self.max_consecutive_losses < 0:
            errors.append("max_consecutive_losses должен быть >= 0")
        if self.cooldown_after_loss < 0:
            errors.append("cooldown_after_loss должен быть >= 0")

        # === ВАЛИДАЦИЯ ADVANCED ORDERS ===
        valid_order_types = ("market", "limit", "stop")
        if self.entry_order_type not in valid_order_types:
            errors.append(f"entry_order_type должен быть одним из {valid_order_types}")
        if self.limit_entry_offset < 0:
            errors.append("limit_entry_offset должен быть >= 0")
        if self.limit_entry_timeout_bars < 1:
            errors.append("limit_entry_timeout_bars должен быть >= 1")

        # === ВАЛИДАЦИЯ SCALE-IN ===
        if self.scale_in_enabled:
            if len(self.scale_in_levels) != len(self.scale_in_portions):
                errors.append("scale_in_levels и scale_in_portions должны иметь одинаковую длину")
            portions_sum = sum(self.scale_in_portions)
            if abs(portions_sum - 1.0) > 0.001:
                errors.append(f"Сумма scale_in_portions должна быть 1.0, получено: {portions_sum}")

        # === ВАЛИДАЦИЯ SLIPPAGE MODEL ===
        valid_slippage_models = ("fixed", "volume", "volatility", "combined")
        if self.slippage_model not in valid_slippage_models:
            errors.append(f"slippage_model должен быть одним из {valid_slippage_models}")

        # === ВАЛИДАЦИЯ FUNDING ===
        if self.include_funding and self.funding_interval_hours not in (1, 4, 8):
            errors.append("funding_interval_hours должен быть 1, 4 или 8")

        return len(errors) == 0, errors

    def get_effective_modes(self) -> tuple["TpMode", "SlMode"]:
        """
        Возвращает эффективные режимы с учётом legacy флагов.
        Используйте этот метод в движке для определения актуальных режимов.
        """
        effective_tp_mode = self.tp_mode
        effective_sl_mode = self.sl_mode

        # Legacy compatibility
        if self.multi_tp_enabled and self.tp_mode == TpMode.FIXED:
            effective_tp_mode = TpMode.MULTI
        if self.atr_enabled:
            if self.tp_mode == TpMode.FIXED and not self.multi_tp_enabled:
                effective_tp_mode = TpMode.ATR
            if self.sl_mode == SlMode.FIXED:
                effective_sl_mode = SlMode.ATR

        return effective_tp_mode, effective_sl_mode


@dataclass
class BacktestMetrics:
    """
    Унифицированные метрики для сравнения движков.
    Все движки возвращают ОДИНАКОВУЮ структуру.
    """

    # === ОСНОВНЫЕ МЕТРИКИ ===
    net_profit: float = 0.0
    total_return: float = 0.0  # в процентах
    gross_profit: float = 0.0
    gross_loss: float = 0.0

    # === ПРОСАДКА ===
    max_drawdown: float = 0.0  # в процентах
    max_drawdown_duration: int = 0  # в барах
    avg_drawdown: float = 0.0

    # === РИСК-МЕТРИКИ ===
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # === СТАТИСТИКА СДЕЛОК ===
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0  # 0-1
    profit_factor: float = 0.0

    # === СРЕДНИЕ ===
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_trade: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0

    # === LONG/SHORT РАЗБИВКА ===
    long_trades: int = 0
    long_winning_trades: int = 0
    long_losing_trades: int = 0
    short_trades: int = 0
    short_winning_trades: int = 0
    short_losing_trades: int = 0
    long_win_rate: float = 0.0
    short_win_rate: float = 0.0
    long_profit: float = 0.0
    short_profit: float = 0.0
    long_gross_profit: float = 0.0
    long_gross_loss: float = 0.0
    short_gross_profit: float = 0.0
    short_gross_loss: float = 0.0
    long_profit_factor: float = 0.0
    short_profit_factor: float = 0.0
    long_avg_win: float = 0.0
    long_avg_loss: float = 0.0
    short_avg_win: float = 0.0
    short_avg_loss: float = 0.0

    # === ВРЕМЯ ===
    avg_trade_duration: float = 0.0  # в барах
    avg_winning_duration: float = 0.0
    avg_losing_duration: float = 0.0

    # === ДОПОЛНИТЕЛЬНЫЕ ===
    expectancy: float = 0.0  # Математическое ожидание
    recovery_factor: float = 0.0
    payoff_ratio: float = 0.0  # avg_win / abs(avg_loss)

    def to_dict(self) -> dict[str, Any]:
        """Конвертация в словарь для сериализации"""
        return {
            "net_profit": round(self.net_profit, 2),
            "total_return": round(self.total_return, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "calmar_ratio": round(self.calmar_ratio, 2),
            "total_trades": self.total_trades,
            "win_rate": round(self.win_rate * 100, 1),
            "profit_factor": round(self.profit_factor, 2),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "long_trades": self.long_trades,
            "short_trades": self.short_trades,
            "expectancy": round(self.expectancy, 2),
        }


@dataclass
class BacktestOutput:
    """
    Унифицированный выход для всех движков.
    Содержит метрики, сделки и equity curve.
    """

    # === МЕТРИКИ ===
    metrics: BacktestMetrics = field(default_factory=BacktestMetrics)

    # === СДЕЛКИ ===
    trades: list[TradeRecord] = field(default_factory=list)

    # === EQUITY CURVE ===
    equity_curve: np.ndarray = field(default_factory=lambda: np.array([]))
    timestamps: np.ndarray = field(default_factory=lambda: np.array([]))

    # === META-INFO ===
    engine_name: str = ""
    execution_time: float = 0.0  # секунды
    bars_processed: int = 0
    bar_magnifier_used: bool = False

    # === ВАЛИДАЦИЯ ===
    is_valid: bool = True
    validation_errors: list[str] = field(default_factory=list)


class BaseBacktestEngine(ABC):
    """
    Абстрактный базовый класс для всех движков.
    Определяет общий интерфейс.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Имя движка"""
        pass

    @property
    @abstractmethod
    def supports_bar_magnifier(self) -> bool:
        """Поддерживает ли Bar Magnifier"""
        pass

    @property
    @abstractmethod
    def supports_parallel(self) -> bool:
        """Поддерживает ли параллельную оптимизацию"""
        pass

    @abstractmethod
    def run(self, input_data: BacktestInput) -> BacktestOutput:
        """
        Запуск бэктеста.

        Args:
            input_data: Унифицированные входные данные

        Returns:
            BacktestOutput: Унифицированный результат
        """
        pass

    @abstractmethod
    def optimize(
        self,
        input_data: BacktestInput,
        param_ranges: dict[str, list[Any]],
        metric: str = "sharpe_ratio",
        top_n: int = 10,
    ) -> list[tuple[dict[str, Any], BacktestOutput]]:
        """
        Оптимизация параметров.

        Args:
            input_data: Базовые входные данные
            param_ranges: Диапазоны параметров для оптимизации
            metric: Метрика для оптимизации
            top_n: Количество лучших результатов

        Returns:
            List of (params, result) tuples
        """
        pass

    def validate_input(self, input_data: BacktestInput) -> tuple[bool, list[str]]:
        """Валидация входных данных"""
        return input_data.validate()


class EngineComparator:
    """
    Сравнение результатов разных движков.
    Использует Fallback как эталон.
    """

    def __init__(self, reference_engine: BaseBacktestEngine):
        self.reference = reference_engine
        self.engines: list[BaseBacktestEngine] = []

    def add_engine(self, engine: BaseBacktestEngine):
        """Добавить движок для сравнения"""
        self.engines.append(engine)

    def compare(self, input_data: BacktestInput) -> dict[str, Any]:
        """
        Сравнить результаты всех движков.

        Returns:
            Словарь с результатами сравнения
        """
        # Запуск эталона
        reference_result = self.reference.run(input_data)

        comparison = {
            "reference": {
                "engine": self.reference.name,
                "metrics": reference_result.metrics.to_dict(),
                "execution_time": reference_result.execution_time,
            },
            "comparisons": [],
        }

        # Сравнение с другими движками
        for engine in self.engines:
            result = engine.run(input_data)

            drift = self._calculate_drift(reference_result.metrics, result.metrics)

            comparison["comparisons"].append(  # type: ignore[union-attr]
                {
                    "engine": engine.name,
                    "metrics": result.metrics.to_dict(),
                    "execution_time": result.execution_time,
                    "speedup": reference_result.execution_time / result.execution_time
                    if result.execution_time > 0
                    else 0,
                    "drift": drift,
                    "is_accurate": drift["max_drift"] < 0.01,  # < 1% drift
                }
            )

        return comparison

    def _calculate_drift(self, ref: BacktestMetrics, test: BacktestMetrics) -> dict[str, float]:
        """Расчёт отклонения от эталона"""

        def safe_pct_diff(a, b):
            if a == 0:
                return 0 if b == 0 else 1.0
            return abs(a - b) / abs(a)

        drifts = {
            "net_profit_drift": safe_pct_diff(ref.net_profit, test.net_profit),
            "sharpe_drift": safe_pct_diff(ref.sharpe_ratio, test.sharpe_ratio),
            "return_drift": safe_pct_diff(ref.total_return, test.total_return),
            "drawdown_drift": safe_pct_diff(ref.max_drawdown, test.max_drawdown),
            "trades_drift": safe_pct_diff(ref.total_trades, test.total_trades),
            "win_rate_drift": safe_pct_diff(ref.win_rate, test.win_rate),
        }

        drifts["max_drift"] = max(drifts.values())
        drifts["avg_drift"] = sum(drifts.values()) / len(drifts)

        return drifts


# ============================================================================
# FACTORY для создания движков
# ============================================================================


def get_engine(engine_type: str = "fallback", pyramiding: int = 1) -> BaseBacktestEngine:
    """
    Фабрика для создания движков.

    Args:
        engine_type: "fallback", "fallback_v3", "numba", "gpu"
        pyramiding: Если > 1, автоматически использует FallbackEngineV3

    Returns:
        Инстанс движка
    """
    from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
    from backend.backtesting.engines.fallback_engine_v3 import FallbackEngineV3
    from backend.backtesting.engines.gpu_engine_v2 import GPUEngineV2
    from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2

    # Если включён пирамидинг (> 1), используем FallbackEngineV3
    # который поддерживает множественные позиции
    if pyramiding > 1:
        return FallbackEngineV3()

    engines = {
        "fallback": FallbackEngineV2,
        "fallback_v3": FallbackEngineV3,
        "numba": NumbaEngineV2,
        "gpu": GPUEngineV2,
    }

    if engine_type not in engines:
        raise ValueError(f"Unknown engine type: {engine_type}. Available: {list(engines.keys())}")

    return engines[engine_type]()


def get_engine_for_config(config: BacktestInput) -> BaseBacktestEngine:
    """
    Выбор оптимального движка на основе конфигурации бэктеста.

    Автоматически выбирает FallbackEngineV3 если нужен пирамидинг.

    Args:
        config: Конфигурация бэктеста

    Returns:
        Оптимальный движок для данной конфигурации
    """
    from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
    from backend.backtesting.engines.fallback_engine_v3 import FallbackEngineV3
    from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2

    pyramiding = getattr(config, "pyramiding", 1)

    # Пирамидинг > 1 требует FallbackEngineV3
    if pyramiding > 1:
        return FallbackEngineV3()

    # Для обычных случаев - пробуем Numba, потом Fallback
    try:
        engine = NumbaEngineV2()
        return engine
    except Exception:
        return FallbackEngineV2()
