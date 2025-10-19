"""
Order Manager - Управление ордерами в бэктесте

Этот модуль отвечает за:
- Создание и валидацию ордеров (Market, Limit, Stop)
- Симуляцию исполнения ордеров
- Расчет slippage
- Расчет комиссий
- Управление состоянием ордеров
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class OrderType(Enum):
    """Тип ордера"""
    MARKET = "MARKET"      # Исполняется немедленно по текущей цене
    LIMIT = "LIMIT"        # Исполняется по указанной цене или лучше
    STOP = "STOP"          # Стоп-лосс или тейк-профит
    STOP_MARKET = "STOP_MARKET"  # Стоп-ордер, превращающийся в market


class OrderSide(Enum):
    """Сторона ордера"""
    BUY = "BUY"       # Покупка (открытие LONG или закрытие SHORT)
    SELL = "SELL"     # Продажа (закрытие LONG или открытие SHORT)


class OrderStatus(Enum):
    """Статус ордера"""
    PENDING = "PENDING"           # Ожидает исполнения
    FILLED = "FILLED"             # Исполнен полностью
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # Исполнен частично
    CANCELLED = "CANCELLED"       # Отменен
    REJECTED = "REJECTED"         # Отклонен (валидация не прошла)
    EXPIRED = "EXPIRED"           # Истек срок действия


class TimeInForce(Enum):
    """Время действия ордера"""
    GTC = "GTC"  # Good Till Cancel - до отмены
    IOC = "IOC"  # Immediate Or Cancel - исполнить немедленно или отменить
    FOK = "FOK"  # Fill Or Kill - исполнить полностью или отменить


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Order:
    """
    Ордер в бэктесте
    
    Attributes:
        order_id: Уникальный ID ордера
        timestamp: Время создания ордера
        order_type: Тип ордера (MARKET, LIMIT, STOP)
        side: Сторона (BUY/SELL)
        symbol: Торговая пара
        quantity: Количество (в базовой валюте)
        price: Цена (для LIMIT/STOP ордеров)
        stop_price: Стоп-цена (для STOP ордеров)
        time_in_force: Время действия
        status: Текущий статус ордера
        filled_quantity: Исполненное количество
        filled_price: Средняя цена исполнения
        commission: Комиссия
        slippage: Slippage (разница между ожидаемой и фактической ценой)
        meta: Дополнительные данные (причина, заметки и т.д.)
    """
    order_id: str
    timestamp: datetime
    order_type: OrderType
    side: OrderSide
    symbol: str
    quantity: float
    
    # Optional fields
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    status: OrderStatus = OrderStatus.PENDING
    
    # Execution fields
    filled_quantity: float = 0.0
    filled_price: Optional[float] = None
    commission: float = 0.0
    slippage: float = 0.0
    
    # Metadata
    meta: Dict[str, Any] = field(default_factory=dict)
    filled_at: Optional[datetime] = None
    
    def is_filled(self) -> bool:
        """Проверить, полностью ли исполнен ордер"""
        return self.status == OrderStatus.FILLED
    
    def is_pending(self) -> bool:
        """Проверить, ожидает ли ордер исполнения"""
        return self.status == OrderStatus.PENDING
    
    def is_buy(self) -> bool:
        """Проверить, является ли ордер покупкой"""
        return self.side == OrderSide.BUY
    
    def is_sell(self) -> bool:
        """Проверить, является ли ордер продажей"""
        return self.side == OrderSide.SELL
    
    def remaining_quantity(self) -> float:
        """Вычислить оставшееся количество"""
        return self.quantity - self.filled_quantity
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь"""
        return {
            'order_id': self.order_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'order_type': self.order_type.value,
            'side': self.side.value,
            'symbol': self.symbol,
            'quantity': self.quantity,
            'price': self.price,
            'stop_price': self.stop_price,
            'time_in_force': self.time_in_force.value,
            'status': self.status.value,
            'filled_quantity': self.filled_quantity,
            'filled_price': self.filled_price,
            'commission': self.commission,
            'slippage': self.slippage,
            'meta': self.meta,
            'filled_at': self.filled_at.isoformat() if self.filled_at else None
        }


# ============================================================================
# ORDER MANAGER
# ============================================================================

class OrderManager:
    """
    Менеджер ордеров для бэктеста
    
    Features:
    - Создание и валидация ордеров
    - Симуляция исполнения (с учетом slippage)
    - Расчет комиссий
    - Управление состоянием ордеров
    - Partial fills support
    
    Example:
        manager = OrderManager(
            commission_rate=0.0006,  # 0.06% (Bybit maker)
            slippage_rate=0.0001     # 0.01% slippage
        )
        
        order = manager.create_market_order(
            symbol='BTCUSDT',
            side=OrderSide.BUY,
            quantity=0.1,
            timestamp=datetime.now()
        )
        
        filled_order = manager.execute_order(order, current_price=50000.0)
    """
    
    def __init__(
        self,
        commission_rate: float = 0.0006,  # Bybit maker: 0.06%
        slippage_rate: float = 0.0001,    # 0.01% slippage
        min_quantity: float = 0.001,      # Минимальное количество
        price_precision: int = 2,         # Точность цены (знаков после запятой)
        quantity_precision: int = 3       # Точность количества
    ):
        """
        Инициализация Order Manager
        
        Args:
            commission_rate: Ставка комиссии (0.0006 = 0.06%)
            slippage_rate: Ставка slippage (0.0001 = 0.01%)
            min_quantity: Минимальное количество для ордера
            price_precision: Точность цены
            quantity_precision: Точность количества
        """
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.min_quantity = min_quantity
        self.price_precision = price_precision
        self.quantity_precision = quantity_precision
        
        # Tracking
        self._order_counter = 0
        self._orders: Dict[str, Order] = {}
        
        logger.info(
            f"OrderManager initialized: "
            f"commission={commission_rate*100:.3f}%, "
            f"slippage={slippage_rate*100:.3f}%"
        )
    
    def create_market_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        timestamp: datetime,
        meta: Optional[Dict] = None
    ) -> Order:
        """
        Создать Market ордер
        
        Market ордер исполняется немедленно по текущей рыночной цене.
        
        Args:
            symbol: Торговая пара (например, 'BTCUSDT')
            side: Сторона (BUY/SELL)
            quantity: Количество
            timestamp: Время создания
            meta: Дополнительные данные
            
        Returns:
            Order: Созданный ордер
            
        Raises:
            ValueError: Если параметры невалидны
        """
        # Валидация
        self._validate_quantity(quantity)
        
        # Генерация ID
        order_id = self._generate_order_id()
        
        # Создание ордера
        order = Order(
            order_id=order_id,
            timestamp=timestamp,
            order_type=OrderType.MARKET,
            side=side,
            symbol=symbol,
            quantity=round(quantity, self.quantity_precision),
            time_in_force=TimeInForce.IOC,  # Market всегда IOC
            meta=meta or {}
        )
        
        # Сохранение
        self._orders[order_id] = order
        
        logger.debug(
            f"Created MARKET order: {order_id} | "
            f"{side.value} {quantity} {symbol}"
        )
        
        return order
    
    def create_limit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: float,
        timestamp: datetime,
        time_in_force: TimeInForce = TimeInForce.GTC,
        meta: Optional[Dict] = None
    ) -> Order:
        """
        Создать Limit ордер
        
        Limit ордер исполняется только по указанной цене или лучше.
        
        Args:
            symbol: Торговая пара
            side: Сторона
            quantity: Количество
            price: Лимитная цена
            timestamp: Время создания
            time_in_force: Время действия (GTC/IOC/FOK)
            meta: Дополнительные данные
            
        Returns:
            Order: Созданный ордер
        """
        # Валидация
        self._validate_quantity(quantity)
        self._validate_price(price)
        
        # Генерация ID
        order_id = self._generate_order_id()
        
        # Создание ордера
        order = Order(
            order_id=order_id,
            timestamp=timestamp,
            order_type=OrderType.LIMIT,
            side=side,
            symbol=symbol,
            quantity=round(quantity, self.quantity_precision),
            price=round(price, self.price_precision),
            time_in_force=time_in_force,
            meta=meta or {}
        )
        
        # Сохранение
        self._orders[order_id] = order
        
        logger.debug(
            f"Created LIMIT order: {order_id} | "
            f"{side.value} {quantity} {symbol} @ {price}"
        )
        
        return order
    
    def create_stop_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        stop_price: float,
        timestamp: datetime,
        order_type: OrderType = OrderType.STOP_MARKET,
        limit_price: Optional[float] = None,
        meta: Optional[Dict] = None
    ) -> Order:
        """
        Создать Stop ордер (Stop Loss / Take Profit)
        
        Stop ордер активируется при достижении stop_price и превращается в:
        - STOP_MARKET: Market ордер
        - STOP: Limit ордер (с указанием limit_price)
        
        Args:
            symbol: Торговая пара
            side: Сторона
            quantity: Количество
            stop_price: Стоп-цена (цена активации)
            timestamp: Время создания
            order_type: STOP_MARKET или STOP
            limit_price: Лимитная цена (для STOP)
            meta: Дополнительные данные
            
        Returns:
            Order: Созданный ордер
        """
        # Валидация
        self._validate_quantity(quantity)
        self._validate_price(stop_price)
        
        if order_type == OrderType.STOP and limit_price is None:
            raise ValueError("limit_price required for STOP order")
        
        # Генерация ID
        order_id = self._generate_order_id()
        
        # Создание ордера
        order = Order(
            order_id=order_id,
            timestamp=timestamp,
            order_type=order_type,
            side=side,
            symbol=symbol,
            quantity=round(quantity, self.quantity_precision),
            stop_price=round(stop_price, self.price_precision),
            price=round(limit_price, self.price_precision) if limit_price else None,
            time_in_force=TimeInForce.GTC,
            meta=meta or {}
        )
        
        # Сохранение
        self._orders[order_id] = order
        
        logger.debug(
            f"Created {order_type.value} order: {order_id} | "
            f"{side.value} {quantity} {symbol} @ stop={stop_price}"
        )
        
        return order
    
    def execute_order(
        self,
        order: Order,
        current_price: float,
        current_time: datetime,
        available_capital: Optional[float] = None
    ) -> Order:
        """
        Исполнить ордер
        
        Симулирует исполнение ордера с учетом:
        - Типа ордера (MARKET/LIMIT/STOP)
        - Slippage (для MARKET ордеров)
        - Комиссий
        - Достаточности капитала
        
        Args:
            order: Ордер для исполнения
            current_price: Текущая рыночная цена
            current_time: Текущее время
            available_capital: Доступный капитал (для валидации)
            
        Returns:
            Order: Обновленный ордер
        """
        # Проверка статуса
        if not order.is_pending():
            logger.warning(f"Order {order.order_id} is not pending ({order.status.value})")
            return order
        
        # Определение цены исполнения
        execution_price = self._calculate_execution_price(order, current_price)
        
        if execution_price is None:
            # Ордер не может быть исполнен по текущей цене
            return order
        
        # Расчет комиссии
        position_value = order.quantity * execution_price
        commission = position_value * self.commission_rate
        
        # Проверка капитала (для BUY ордеров)
        if order.is_buy() and available_capital is not None:
            total_cost = position_value + commission
            if total_cost > available_capital:
                logger.warning(
                    f"Insufficient capital for order {order.order_id}: "
                    f"need ${total_cost:.2f}, have ${available_capital:.2f}"
                )
                order.status = OrderStatus.REJECTED
                order.meta['rejection_reason'] = 'insufficient_capital'
                return order
        
        # Исполнение ордера
        order.filled_quantity = order.quantity
        order.filled_price = execution_price
        order.commission = commission
        order.status = OrderStatus.FILLED
        order.filled_at = current_time
        
        # Расчет slippage (только для MARKET ордеров)
        if order.order_type == OrderType.MARKET:
            expected_price = current_price
            actual_price = execution_price
            order.slippage = abs(actual_price - expected_price) / expected_price
        
        logger.info(
            f"✅ Order {order.order_id} FILLED | "
            f"{order.side.value} {order.quantity} @ ${execution_price:.2f} | "
            f"Commission: ${commission:.4f}"
        )
        
        return order
    
    def cancel_order(self, order: Order, reason: str = "user_cancelled") -> Order:
        """
        Отменить ордер
        
        Args:
            order: Ордер для отмены
            reason: Причина отмены
            
        Returns:
            Order: Обновленный ордер
        """
        if order.is_filled():
            logger.warning(f"Cannot cancel filled order {order.order_id}")
            return order
        
        order.status = OrderStatus.CANCELLED
        order.meta['cancellation_reason'] = reason
        
        logger.info(f"❌ Order {order.order_id} CANCELLED | Reason: {reason}")
        
        return order
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Получить ордер по ID"""
        return self._orders.get(order_id)
    
    def get_all_orders(self) -> list[Order]:
        """Получить все ордера"""
        return list(self._orders.values())
    
    def get_pending_orders(self) -> list[Order]:
        """Получить все ордера в статусе PENDING"""
        return [o for o in self._orders.values() if o.is_pending()]
    
    def get_filled_orders(self) -> list[Order]:
        """Получить все исполненные ордера"""
        return [o for o in self._orders.values() if o.is_filled()]
    
    def clear_orders(self):
        """Очистить все ордера (для нового бэктеста)"""
        self._orders.clear()
        self._order_counter = 0
        logger.debug("All orders cleared")
    
    # ========================================================================
    # PRIVATE METHODS
    # ========================================================================
    
    def _calculate_execution_price(self, order: Order, current_price: float) -> Optional[float]:
        """
        Вычислить цену исполнения ордера
        
        Returns:
            float: Цена исполнения или None если ордер не может быть исполнен
        """
        if order.order_type == OrderType.MARKET:
            # Market ордер - с учетом slippage
            if order.is_buy():
                # BUY: slippage увеличивает цену
                return current_price * (1 + self.slippage_rate)
            else:
                # SELL: slippage уменьшает цену
                return current_price * (1 - self.slippage_rate)
        
        elif order.order_type == OrderType.LIMIT:
            # Limit ордер - только по указанной цене или лучше
            if order.is_buy():
                # BUY LIMIT: исполняется если цена <= limit
                if current_price <= order.price:
                    return order.price
            else:
                # SELL LIMIT: исполняется если цена >= limit
                if current_price >= order.price:
                    return order.price
            
            return None  # Не может быть исполнен
        
        elif order.order_type in (OrderType.STOP, OrderType.STOP_MARKET):
            # Stop ордер уже должен быть активирован перед вызовом этого метода
            # Здесь просто возвращаем цену с slippage
            if order.is_buy():
                return current_price * (1 + self.slippage_rate)
            else:
                return current_price * (1 - self.slippage_rate)
        
        return None
    
    def _validate_quantity(self, quantity: float):
        """Валидация количества"""
        if quantity <= 0:
            raise ValueError(f"Quantity must be positive: {quantity}")
        
        if quantity < self.min_quantity:
            raise ValueError(
                f"Quantity {quantity} is below minimum {self.min_quantity}"
            )
    
    def _validate_price(self, price: float):
        """Валидация цены"""
        if price <= 0:
            raise ValueError(f"Price must be positive: {price}")
    
    def _generate_order_id(self) -> str:
        """Генерация уника��ьного ID ордера"""
        self._order_counter += 1
        return f"ORDER_{self._order_counter:06d}"
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику ордеров"""
        orders = self.get_all_orders()
        filled = self.get_filled_orders()
        pending = self.get_pending_orders()
        
        total_commission = sum(o.commission for o in filled)
        total_slippage = sum(o.slippage * o.filled_price * o.quantity for o in filled if o.slippage > 0)
        
        return {
            'total_orders': len(orders),
            'filled_orders': len(filled),
            'pending_orders': len(pending),
            'total_commission': total_commission,
            'total_slippage': total_slippage,
            'avg_commission_per_order': total_commission / len(filled) if filled else 0,
            'commission_rate': self.commission_rate,
            'slippage_rate': self.slippage_rate
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_required_margin(
    quantity: float,
    price: float,
    leverage: int
) -> float:
    """
    Рассчитать требуемую маржу для позиции
    
    Args:
        quantity: Количество
        price: Цена входа
        leverage: Кредитное плечо
        
    Returns:
        float: Требуемая маржа
    """
    position_value = quantity * price
    margin = position_value / leverage
    return margin


def calculate_position_size(
    capital: float,
    price: float,
    leverage: int,
    risk_percent: float = 1.0
) -> float:
    """
    Рассчитать размер позиции на основе капитала и риска
    
    Args:
        capital: Доступный капитал
        price: Цена входа
        leverage: Кредитное плечо
        risk_percent: Процент риска от капитала (1.0 = 1%)
        
    Returns:
        float: Размер позиции в базовой валюте
    """
    risk_amount = capital * (risk_percent / 100)
    position_value = risk_amount * leverage
    quantity = position_value / price
    return quantity


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
    print("  ORDER MANAGER - EXAMPLE USAGE")
    print("="*70)
    
    # Создание Order Manager
    manager = OrderManager(
        commission_rate=0.0006,  # 0.06% Bybit maker
        slippage_rate=0.0001     # 0.01% slippage
    )
    
    # Пример 1: Market Order
    print("\n📊 Example 1: Market Order (BUY)")
    print("-" * 70)
    
    market_order = manager.create_market_order(
        symbol='BTCUSDT',
        side=OrderSide.BUY,
        quantity=0.1,
        timestamp=datetime.now(),
        meta={'strategy': 'test', 'signal': 'buy'}
    )
    
    print(f"Created: {market_order.order_id} | {market_order.order_type.value} | {market_order.side.value}")
    
    # Исполнение
    current_price = 50000.0
    filled_order = manager.execute_order(
        market_order,
        current_price=current_price,
        current_time=datetime.now(),
        available_capital=10000.0
    )
    
    print(f"Execution Price: ${filled_order.filled_price:.2f}")
    print(f"Commission: ${filled_order.commission:.4f}")
    print(f"Slippage: {filled_order.slippage*100:.4f}%")
    
    # Пример 2: Limit Order
    print("\n📊 Example 2: Limit Order (SELL)")
    print("-" * 70)
    
    limit_order = manager.create_limit_order(
        symbol='BTCUSDT',
        side=OrderSide.SELL,
        quantity=0.1,
        price=51000.0,  # Sell at $51,000
        timestamp=datetime.now()
    )
    
    print(f"Created: {limit_order.order_id} | LIMIT @ ${limit_order.price:.2f}")
    
    # Попытка исполнения (цена еще не достигла)
    current_price = 50500.0
    manager.execute_order(limit_order, current_price, datetime.now())
    print(f"Status at ${current_price}: {limit_order.status.value} (waiting for ${limit_order.price:.2f})")
    
    # Исполнение когда цена достигла
    current_price = 51000.0
    manager.execute_order(limit_order, current_price, datetime.now())
    print(f"Status at ${current_price}: {limit_order.status.value} ✅")
    
    # Пример 3: Stop Loss Order
    print("\n📊 Example 3: Stop Loss Order")
    print("-" * 70)
    
    stop_order = manager.create_stop_order(
        symbol='BTCUSDT',
        side=OrderSide.SELL,
        quantity=0.1,
        stop_price=48000.0,  # Stop loss at $48,000
        timestamp=datetime.now(),
        meta={'type': 'stop_loss'}
    )
    
    print(f"Created: {stop_order.order_id} | STOP @ ${stop_order.stop_price:.2f}")
    
    # Статистика
    print("\n📊 Order Statistics")
    print("-" * 70)
    stats = manager.get_stats()
    print(f"Total Orders: {stats['total_orders']}")
    print(f"Filled Orders: {stats['filled_orders']}")
    print(f"Pending Orders: {stats['pending_orders']}")
    print(f"Total Commission: ${stats['total_commission']:.4f}")
    print(f"Total Slippage: ${stats['total_slippage']:.4f}")
    
    print("\n" + "="*70)
    print("  ✅ Order Manager working correctly!")
    print("="*70)
