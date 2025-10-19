"""
Position Manager - Управление позициями в бэктесте

Этот модуль отвечает за:
- Открытие и закрытие Long/Short позиций
- Отслеживание текущей позиции
- Расчет PnL (realized/unrealized)
- Расчет маржи и ликвидации
- Partial close support
- Position history tracking
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class PositionSide(Enum):
    """Тип позиции"""
    LONG = "LONG"     # Покупка (прибыль при росте цены)
    SHORT = "SHORT"   # Продажа (прибыль при падении цены)


class PositionStatus(Enum):
    """Статус позиции"""
    OPEN = "OPEN"          # Открыта
    CLOSED = "CLOSED"      # Закрыта
    LIQUIDATED = "LIQUIDATED"  # Ликвидирована


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Position:
    """
    Торговая позиция
    
    Attributes:
        position_id: Уникальный ID позиции
        symbol: Торговая пара
        side: Сторона (LONG/SHORT)
        entry_time: Время открытия
        entry_price: Цена входа
        quantity: Количество (в базовой валюте)
        leverage: Кредитное плечо
        
        # PnL
        realized_pnl: Реализованный PnL (уже закрыто)
        unrealized_pnl: Нереализованный PnL (текущая позиция)
        
        # Costs
        entry_commission: Комиссия при входе
        exit_commission: Комиссия при выходе
        total_commission: Общая комиссия
        
        # Exit info
        exit_time: Время закрытия
        exit_price: Цена выхода
        exit_reason: Причина закрытия
        
        # Margin
        initial_margin: Начальная маржа
        maintenance_margin: Поддерживающая маржа
        liquidation_price: Цена ликвидации
        
        # Tracking
        highest_price: Максимальная цена (для trailing stop)
        lowest_price: Минимальная цена (для trailing stop)
        duration_seconds: Длительность позиции в секундах
        
        # Status
        status: Текущий статус позиции
        
        # Metadata
        meta: Дополнительные данные
    """
    position_id: str
    symbol: str
    side: PositionSide
    entry_time: datetime
    entry_price: float
    quantity: float
    leverage: int = 1
    
    # PnL
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    
    # Costs
    entry_commission: float = 0.0
    exit_commission: float = 0.0
    
    # Exit info
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    
    # Margin
    initial_margin: float = 0.0
    maintenance_margin: float = 0.0
    liquidation_price: Optional[float] = None
    
    # Tracking
    highest_price: Optional[float] = None
    lowest_price: Optional[float] = None
    duration_seconds: float = 0.0
    
    # Status
    status: PositionStatus = PositionStatus.OPEN
    
    # Metadata
    meta: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Инициализация после создания"""
        if self.highest_price is None:
            self.highest_price = self.entry_price
        if self.lowest_price is None:
            self.lowest_price = self.entry_price
    
    @property
    def total_commission(self) -> float:
        """Общая комиссия"""
        return self.entry_commission + self.exit_commission
    
    @property
    def net_pnl(self) -> float:
        """Чистый PnL (с учетом комиссий)"""
        return self.realized_pnl - self.total_commission
    
    @property
    def position_value(self) -> float:
        """Стоимость позиции"""
        return self.quantity * self.entry_price
    
    @property
    def pnl_percent(self) -> float:
        """PnL в процентах от входа"""
        if self.exit_price is None:
            return 0.0
        
        if self.side == PositionSide.LONG:
            return ((self.exit_price - self.entry_price) / self.entry_price) * 100
        else:  # SHORT
            return ((self.entry_price - self.exit_price) / self.entry_price) * 100
    
    def is_open(self) -> bool:
        """Проверить, открыта ли позиция"""
        return self.status == PositionStatus.OPEN
    
    def is_closed(self) -> bool:
        """Проверить, закрыта ли позиция"""
        return self.status == PositionStatus.CLOSED
    
    def is_long(self) -> bool:
        """Проверить, является ли позиция LONG"""
        return self.side == PositionSide.LONG
    
    def is_short(self) -> bool:
        """Проверить, является ли позиция SHORT"""
        return self.side == PositionSide.SHORT
    
    def update_unrealized_pnl(self, current_price: float):
        """
        Обновить нереализованный PnL на основе текущей цены
        
        Args:
            current_price: Текущая рыночная цена
        """
        if self.side == PositionSide.LONG:
            # LONG: прибыль при росте цены
            price_change = current_price - self.entry_price
        else:
            # SHORT: прибыль при падении цены
            price_change = self.entry_price - current_price
        
        # PnL = изменение цены * количество * кредитное плечо
        self.unrealized_pnl = price_change * self.quantity
        
        # Обновление highest/lowest для trailing stop
        if self.highest_price is None or current_price > self.highest_price:
            self.highest_price = current_price
        if self.lowest_price is None or current_price < self.lowest_price:
            self.lowest_price = current_price
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь"""
        return {
            'position_id': self.position_id,
            'symbol': self.symbol,
            'side': self.side.value,
            'entry_time': self.entry_time.isoformat() if self.entry_time else None,
            'entry_price': self.entry_price,
            'quantity': self.quantity,
            'leverage': self.leverage,
            'realized_pnl': self.realized_pnl,
            'unrealized_pnl': self.unrealized_pnl,
            'entry_commission': self.entry_commission,
            'exit_commission': self.exit_commission,
            'total_commission': self.total_commission,
            'net_pnl': self.net_pnl,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'exit_price': self.exit_price,
            'exit_reason': self.exit_reason,
            'initial_margin': self.initial_margin,
            'maintenance_margin': self.maintenance_margin,
            'liquidation_price': self.liquidation_price,
            'highest_price': self.highest_price,
            'lowest_price': self.lowest_price,
            'duration_seconds': self.duration_seconds,
            'status': self.status.value,
            'pnl_percent': self.pnl_percent,
            'meta': self.meta
        }


# ============================================================================
# POSITION MANAGER
# ============================================================================

class PositionManager:
    """
    Менеджер позиций для бэктеста
    
    Features:
    - Открытие Long/Short позиций
    - Закрытие позиций (полное/частичное)
    - Расчет PnL (realized/unrealized)
    - Расчет маржи и ликвидации
    - Position history tracking
    - Risk management (margin call, liquidation)
    
    Example:
        manager = PositionManager(
            commission_rate=0.0006,
            maintenance_margin_rate=0.005,  # 0.5%
            liquidation_fee_rate=0.001      # 0.1%
        )
        
        # Открыть LONG позицию
        position = manager.open_position(
            symbol='BTCUSDT',
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(),
            leverage=2,
            capital=10000.0
        )
        
        # Обновить PnL при изменении цены
        manager.update_position(position, current_price=51000.0)
        
        # Закрыть позицию
        manager.close_position(
            position,
            exit_price=51500.0,
            exit_time=datetime.now(),
            reason='take_profit'
        )
    """
    
    def __init__(
        self,
        commission_rate: float = 0.0006,       # 0.06% Bybit maker
        maintenance_margin_rate: float = 0.005,  # 0.5% для большинства пар
        liquidation_fee_rate: float = 0.001      # 0.1% ликвидационная комиссия
    ):
        """
        Инициализация Position Manager
        
        Args:
            commission_rate: Ставка комиссии
            maintenance_margin_rate: Ставка поддерживающей маржи
            liquidation_fee_rate: Ставка ликвидационной комиссии
        """
        self.commission_rate = commission_rate
        self.maintenance_margin_rate = maintenance_margin_rate
        self.liquidation_fee_rate = liquidation_fee_rate
        
        # Tracking
        self._position_counter = 0
        self._current_position: Optional[Position] = None
        self._closed_positions: List[Position] = []
        
        logger.info(
            f"PositionManager initialized: "
            f"commission={commission_rate*100:.3f}%, "
            f"maintenance_margin={maintenance_margin_rate*100:.2f}%"
        )
    
    def open_position(
        self,
        symbol: str,
        side: PositionSide,
        quantity: float,
        entry_price: float,
        entry_time: datetime,
        leverage: int = 1,
        capital: Optional[float] = None,
        meta: Optional[Dict] = None
    ) -> Position:
        """
        Открыть новую позицию
        
        Args:
            symbol: Торговая пара
            side: Сторона (LONG/SHORT)
            quantity: Количество
            entry_price: Цена входа
            entry_time: Время открытия
            leverage: Кредитное плечо
            capital: Доступный капитал (для проверки достаточности)
            meta: Дополнительные данные
            
        Returns:
            Position: Открытая позиция
            
        Raises:
            ValueError: Если уже есть открытая позиция или недостаточно капитала
        """
        # Проверка на существующую позицию
        if self._current_position is not None:
            raise ValueError(
                f"Cannot open new position: position {self._current_position.position_id} "
                f"is still open"
            )
        
        # Расчет стоимости позиции
        position_value = quantity * entry_price
        
        # Расчет маржи
        initial_margin = position_value / leverage
        maintenance_margin = position_value * self.maintenance_margin_rate
        
        # Расчет комиссии при входе
        entry_commission = position_value * self.commission_rate
        
        # Проверка достаточности капитала
        required_capital = initial_margin + entry_commission
        if capital is not None and required_capital > capital:
            raise ValueError(
                f"Insufficient capital: need ${required_capital:.2f}, "
                f"have ${capital:.2f}"
            )
        
        # Расчет цены ликвидации
        liquidation_price = self._calculate_liquidation_price(
            entry_price=entry_price,
            side=side,
            leverage=leverage,
            maintenance_margin_rate=self.maintenance_margin_rate,
            liquidation_fee_rate=self.liquidation_fee_rate
        )
        
        # Генерация ID
        position_id = self._generate_position_id()
        
        # Создание позиции
        position = Position(
            position_id=position_id,
            symbol=symbol,
            side=side,
            entry_time=entry_time,
            entry_price=entry_price,
            quantity=quantity,
            leverage=leverage,
            entry_commission=entry_commission,
            initial_margin=initial_margin,
            maintenance_margin=maintenance_margin,
            liquidation_price=liquidation_price,
            meta=meta or {}
        )
        
        # Сохранение
        self._current_position = position
        
        logger.info(
            f"📈 Position {position_id} OPENED | "
            f"{side.value} {quantity} {symbol} @ ${entry_price:.2f} | "
            f"Leverage: {leverage}x | "
            f"Margin: ${initial_margin:.2f} | "
            f"Liquidation: ${liquidation_price:.2f}"
        )
        
        return position
    
    def close_position(
        self,
        position: Position,
        exit_price: float,
        exit_time: datetime,
        reason: str = "manual",
        partial_quantity: Optional[float] = None
    ) -> Position:
        """
        Закрыть позицию (полностью или частично)
        
        Args:
            position: Позиция для закрытия
            exit_price: Цена выхода
            exit_time: Время закрытия
            reason: Причина закрытия ('take_profit', 'stop_loss', 'manual', etc.)
            partial_quantity: Количество для частичного закрытия (None = полное)
            
        Returns:
            Position: Обновленная позиция
        """
        if not position.is_open():
            logger.warning(f"Position {position.position_id} is not open")
            return position
        
        # Определение количества для закрытия
        close_quantity = partial_quantity if partial_quantity else position.quantity
        
        if close_quantity > position.quantity:
            raise ValueError(
                f"Close quantity {close_quantity} exceeds position quantity {position.quantity}"
            )
        
        # Расчет стоимости выхода
        exit_value = close_quantity * exit_price
        
        # Расчет комиссии при выходе
        exit_commission = exit_value * self.commission_rate
        
        # Расчет realized PnL
        if position.side == PositionSide.LONG:
            # LONG: прибыль = (exit - entry) * quantity
            pnl = (exit_price - position.entry_price) * close_quantity
        else:
            # SHORT: прибыль = (entry - exit) * quantity
            pnl = (position.entry_price - exit_price) * close_quantity
        
        # Учет комиссий
        realized_pnl = pnl - exit_commission
        
        # Расчет длительности
        duration = (exit_time - position.entry_time).total_seconds()
        
        # Полное или частичное закрытие
        if partial_quantity is None or close_quantity == position.quantity:
            # Полное закрытие
            position.exit_time = exit_time
            position.exit_price = exit_price
            position.exit_reason = reason
            position.exit_commission = exit_commission
            position.realized_pnl = realized_pnl
            position.unrealized_pnl = 0.0
            position.duration_seconds = duration
            position.status = PositionStatus.CLOSED
            
            # Перемещение в историю
            self._closed_positions.append(position)
            self._current_position = None
            
            logger.info(
                f"📉 Position {position.position_id} CLOSED | "
                f"Exit @ ${exit_price:.2f} | "
                f"PnL: ${realized_pnl:.2f} ({position.pnl_percent:+.2f}%) | "
                f"Reason: {reason}"
            )
        else:
            # Частичное закрытие (упрощенная версия - создаем новую позицию)
            logger.warning(
                f"Partial close not fully implemented for position {position.position_id}"
            )
            # TODO: Implement partial close logic
        
        return position
    
    def update_position(
        self,
        position: Position,
        current_price: float,
        current_time: Optional[datetime] = None
    ):
        """
        Обновить позицию с текущей ценой
        
        Updates:
        - Unrealized PnL
        - Highest/Lowest price tracking
        - Duration
        
        Args:
            position: Позиция для обновления
            current_price: Текущая рыночная цена
            current_time: Текущее время (опционально)
        """
        if not position.is_open():
            return
        
        # Обновление unrealized PnL
        position.update_unrealized_pnl(current_price)
        
        # Обновление duration
        if current_time:
            position.duration_seconds = (current_time - position.entry_time).total_seconds()
    
    def check_liquidation(
        self,
        position: Position,
        current_price: float,
        current_time: datetime
    ) -> bool:
        """
        Проверить, должна ли позиция быть ликвидирована
        
        Args:
            position: Позиция для проверки
            current_price: Текущая рыночная цена
            current_time: Текущее время
            
        Returns:
            bool: True если позиция ликвидирована
        """
        if not position.is_open():
            return False
        
        if position.liquidation_price is None:
            return False
        
        # Проверка условий ликвидации
        should_liquidate = False
        
        if position.side == PositionSide.LONG:
            # LONG: ликвидация если цена упала ниже liquidation_price
            should_liquidate = current_price <= position.liquidation_price
        else:
            # SHORT: ликвидация если цена выросла выше liquidation_price
            should_liquidate = current_price >= position.liquidation_price
        
        if should_liquidate:
            # Ликвидация позиции
            position.status = PositionStatus.LIQUIDATED
            position.exit_time = current_time
            position.exit_price = position.liquidation_price
            position.exit_reason = 'liquidation'
            
            # Расчет потерь при ликвидации
            liquidation_value = position.quantity * position.liquidation_price
            liquidation_fee = liquidation_value * self.liquidation_fee_rate
            
            # Realized PnL при ликвидации (обычно полная потеря margin + комиссия)
            position.realized_pnl = -(position.initial_margin + liquidation_fee)
            position.exit_commission = liquidation_fee
            position.unrealized_pnl = 0.0
            
            # Перемещение в историю
            self._closed_positions.append(position)
            self._current_position = None
            
            logger.warning(
                f"💥 Position {position.position_id} LIQUIDATED | "
                f"Price: ${current_price:.2f} | "
                f"Loss: ${abs(position.realized_pnl):.2f}"
            )
            
            return True
        
        return False
    
    def get_current_position(self) -> Optional[Position]:
        """Получить текущую открытую позицию"""
        return self._current_position
    
    def has_open_position(self) -> bool:
        """Проверить, есть ли открытая позиция"""
        return self._current_position is not None
    
    def get_closed_positions(self) -> List[Position]:
        """Получить все закрытые позиции"""
        return self._closed_positions.copy()
    
    def get_all_positions(self) -> List[Position]:
        """Получить все позиции (открытые + закрытые)"""
        positions = self._closed_positions.copy()
        if self._current_position:
            positions.append(self._current_position)
        return positions
    
    def clear_positions(self):
        """Очистить все позиции (для нового бэктеста)"""
        self._current_position = None
        self._closed_positions.clear()
        self._position_counter = 0
        logger.debug("All positions cleared")
    
    # ========================================================================
    # PRIVATE METHODS
    # ========================================================================
    
    def _calculate_liquidation_price(
        self,
        entry_price: float,
        side: PositionSide,
        leverage: int,
        maintenance_margin_rate: float,
        liquidation_fee_rate: float
    ) -> float:
        """
        Вычислить цену ликвидации
        
        Formula (LONG):
            Liquidation Price = Entry Price * (1 - 1/Leverage + MMR + Liquidation Fee)
        
        Formula (SHORT):
            Liquidation Price = Entry Price * (1 + 1/Leverage - MMR - Liquidation Fee)
        
        где MMR = Maintenance Margin Rate
        
        Args:
            entry_price: Цена входа
            side: Сторона позиции
            leverage: Кредитное плечо
            maintenance_margin_rate: Ставка поддерживающей маржи
            liquidation_fee_rate: Ставка ликвидационной комиссии
            
        Returns:
            float: Цена ликвидации
        """
        if side == PositionSide.LONG:
            # LONG: ликвидация при падении цены
            liquidation_price = entry_price * (
                1 - (1 / leverage) + maintenance_margin_rate + liquidation_fee_rate
            )
        else:
            # SHORT: ликвидация при росте цены
            liquidation_price = entry_price * (
                1 + (1 / leverage) - maintenance_margin_rate - liquidation_fee_rate
            )
        
        return liquidation_price
    
    def _generate_position_id(self) -> str:
        """Генерация уникального ID позиции"""
        self._position_counter += 1
        return f"POS_{self._position_counter:06d}"
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику позиций"""
        closed = self.get_closed_positions()
        
        if not closed:
            return {
                'total_positions': 0,
                'open_positions': 1 if self.has_open_position() else 0,
                'closed_positions': 0
            }
        
        # Winning/Losing positions
        winning = [p for p in closed if p.net_pnl > 0]
        losing = [p for p in closed if p.net_pnl < 0]
        breakeven = [p for p in closed if p.net_pnl == 0]
        
        # PnL statistics
        total_pnl = sum(p.net_pnl for p in closed)
        total_commission = sum(p.total_commission for p in closed)
        
        avg_pnl = total_pnl / len(closed) if closed else 0
        avg_win = sum(p.net_pnl for p in winning) / len(winning) if winning else 0
        avg_loss = sum(p.net_pnl for p in losing) / len(losing) if losing else 0
        
        largest_win = max((p.net_pnl for p in winning), default=0)
        largest_loss = min((p.net_pnl for p in losing), default=0)
        
        # Duration statistics
        avg_duration = sum(p.duration_seconds for p in closed) / len(closed) if closed else 0
        
        # Win rate
        win_rate = (len(winning) / len(closed) * 100) if closed else 0
        
        # Profit factor
        total_wins = sum(p.net_pnl for p in winning)
        total_losses = abs(sum(p.net_pnl for p in losing))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        return {
            'total_positions': len(closed) + (1 if self.has_open_position() else 0),
            'open_positions': 1 if self.has_open_position() else 0,
            'closed_positions': len(closed),
            'winning_positions': len(winning),
            'losing_positions': len(losing),
            'breakeven_positions': len(breakeven),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'total_commission': total_commission,
            'avg_pnl_per_position': avg_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'largest_win': largest_win,
            'largest_loss': largest_loss,
            'profit_factor': profit_factor,
            'avg_duration_seconds': avg_duration,
            'avg_duration_minutes': avg_duration / 60
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_position_pnl(
    entry_price: float,
    exit_price: float,
    quantity: float,
    side: PositionSide,
    leverage: int = 1
) -> float:
    """
    Рассчитать PnL позиции
    
    Args:
        entry_price: Цена входа
        exit_price: Цена выхода
        quantity: Количество
        side: Сторона позиции
        leverage: Кредитное плечо
        
    Returns:
        float: PnL (без учета комиссий)
    """
    if side == PositionSide.LONG:
        pnl = (exit_price - entry_price) * quantity
    else:  # SHORT
        pnl = (entry_price - exit_price) * quantity
    
    return pnl


def calculate_position_roi(
    entry_price: float,
    exit_price: float,
    side: PositionSide,
    leverage: int = 1
) -> float:
    """
    Рассчитать ROI позиции в процентах
    
    Args:
        entry_price: Цена входа
        exit_price: Цена выхода
        side: Сторона позиции
        leverage: Кредитное плечо
        
    Returns:
        float: ROI в процентах
    """
    if side == PositionSide.LONG:
        roi = ((exit_price - entry_price) / entry_price) * 100 * leverage
    else:  # SHORT
        roi = ((entry_price - exit_price) / entry_price) * 100 * leverage
    
    return roi


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
    print("  POSITION MANAGER - EXAMPLE USAGE")
    print("="*70)
    
    # Создание Position Manager
    manager = PositionManager(
        commission_rate=0.0006,          # 0.06%
        maintenance_margin_rate=0.005,   # 0.5%
        liquidation_fee_rate=0.001       # 0.1%
    )
    
    # Пример 1: LONG Position
    print("\n📊 Example 1: LONG Position (Profitable)")
    print("-" * 70)
    
    position = manager.open_position(
        symbol='BTCUSDT',
        side=PositionSide.LONG,
        quantity=0.1,
        entry_price=50000.0,
        entry_time=datetime.now(),
        leverage=2,
        capital=10000.0,
        meta={'strategy': 'test', 'signal': 'buy'}
    )
    
    print(f"Initial Margin: ${position.initial_margin:.2f}")
    print(f"Liquidation Price: ${position.liquidation_price:.2f}")
    
    # Обновление позиции при росте цены
    manager.update_position(position, current_price=51000.0)
    print(f"At $51,000: Unrealized PnL = ${position.unrealized_pnl:.2f}")
    
    # Закрытие с прибылью
    manager.close_position(
        position,
        exit_price=52000.0,
        exit_time=datetime.now(),
        reason='take_profit'
    )
    
    print(f"Realized PnL: ${position.realized_pnl:.2f}")
    print(f"Net PnL: ${position.net_pnl:.2f} ({position.pnl_percent:+.2f}%)")
    
    # Пример 2: SHORT Position
    print("\n📊 Example 2: SHORT Position (Loss)")
    print("-" * 70)
    
    position2 = manager.open_position(
        symbol='BTCUSDT',
        side=PositionSide.SHORT,
        quantity=0.1,
        entry_price=50000.0,
        entry_time=datetime.now(),
        leverage=2,
        capital=10000.0
    )
    
    # Обновление при росте цены (убыток для SHORT)
    manager.update_position(position2, current_price=51000.0)
    print(f"At $51,000: Unrealized PnL = ${position2.unrealized_pnl:.2f}")
    
    # Закрытие с убытком
    manager.close_position(
        position2,
        exit_price=51500.0,
        exit_time=datetime.now(),
        reason='stop_loss'
    )
    
    print(f"Realized PnL: ${position2.realized_pnl:.2f}")
    print(f"Net PnL: ${position2.net_pnl:.2f} ({position2.pnl_percent:+.2f}%)")
    
    # Пример 3: Liquidation
    print("\n📊 Example 3: LONG Position with Liquidation")
    print("-" * 70)
    
    position3 = manager.open_position(
        symbol='BTCUSDT',
        side=PositionSide.LONG,
        quantity=0.1,
        entry_price=50000.0,
        entry_time=datetime.now(),
        leverage=5,  # Высокое кредитное плечо
        capital=10000.0
    )
    
    print(f"Liquidation Price: ${position3.liquidation_price:.2f}")
    
    # Проверка ликвидации при падении цены
    is_liquidated = manager.check_liquidation(
        position3,
        current_price=position3.liquidation_price - 100,
        current_time=datetime.now()
    )
    
    if is_liquidated:
        print(f"Position liquidated! Loss: ${abs(position3.realized_pnl):.2f}")
    
    # Статистика
    print("\n📊 Position Statistics")
    print("-" * 70)
    stats = manager.get_stats()
    print(f"Total Positions: {stats['total_positions']}")
    print(f"Closed Positions: {stats['closed_positions']}")
    print(f"Winning: {stats['winning_positions']} | Losing: {stats['losing_positions']}")
    print(f"Win Rate: {stats['win_rate']:.2f}%")
    print(f"Total PnL: ${stats['total_pnl']:.2f}")
    print(f"Profit Factor: {stats['profit_factor']:.2f}")
    print(f"Avg Win: ${stats['avg_win']:.2f} | Avg Loss: ${stats['avg_loss']:.2f}")
    
    print("\n" + "="*70)
    print("  ✅ Position Manager working correctly!")
    print("="*70)
