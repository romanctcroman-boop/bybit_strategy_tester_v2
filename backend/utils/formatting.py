"""
Formatting Utilities for Backend

Централизованные функции форматирования для backend.
Используются в API responses, логировании, отчетах.

Author: Backend Refactoring Initiative
Date: 2025-10-31
"""

import json
from datetime import datetime, timezone
from typing import Any


def format_number(value: float | int, precision: int = 2) -> str:
    """
    Форматирование числа с заданной точностью
    
    Args:
        value: Число для форматирования
        precision: Количество десятичных знаков
    
    Returns:
        Отформатированная строка
    
    Examples:
        >>> format_number(1234.5678, 2)
        '1,234.57'
        >>> format_number(1000000, 0)
        '1,000,000'
    """
    return f"{value:,.{precision}f}"


def format_percentage(value: float, precision: int = 2) -> str:
    """
    Форматирование процента
    
    Args:
        value: Процентное значение (0.5 = 50%)
        precision: Количество десятичных знаков
    
    Returns:
        Отформатированная строка с %
    
    Examples:
        >>> format_percentage(0.4567, 2)
        '45.67%'
        >>> format_percentage(1.0, 1)
        '100.0%'
    """
    return f"{value * 100:.{precision}f}%"


def format_currency(value: float, currency: str = "USDT", precision: int = 2) -> str:
    """
    Форматирование валюты
    
    Args:
        value: Сумма
        currency: Код валюты
        precision: Количество десятичных знаков
    
    Returns:
        Отформатированная строка с валютой
    
    Examples:
        >>> format_currency(1234.56)
        '1,234.56 USDT'
        >>> format_currency(1000000, 'USD', 0)
        '1,000,000 USD'
    """
    return f"{value:,.{precision}f} {currency}"


def format_timestamp(
    timestamp: datetime | str | int | float | None,
    format_str: str = "%Y-%m-%d %H:%M:%S",
    timezone_aware: bool = True,
) -> str:
    """
    Форматирование timestamp в строку
    
    Args:
        timestamp: Дата/время для форматирования
        format_str: Формат вывода (strftime format)
        timezone_aware: Конвертировать в UTC если True
    
    Returns:
        Отформатированная строка
    
    Examples:
        >>> format_timestamp(datetime(2023, 10, 31, 12, 30))
        '2023-10-31 12:30:00'
        >>> format_timestamp(1698765432)
        '2023-10-31 14:37:12'
        >>> format_timestamp(None)
        '—'
    """
    if timestamp is None:
        return "—"
    
    # Convert to datetime if needed
    if isinstance(timestamp, (int, float)):
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc if timezone_aware else None)
    elif isinstance(timestamp, str):
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    else:
        dt = timestamp
    
    # Convert to UTC if requested
    if timezone_aware and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    return dt.strftime(format_str)


def format_duration_seconds(seconds: float | int) -> str:
    """
    Форматирование длительности в секундах
    
    Args:
        seconds: Длительность в секундах
    
    Returns:
        Человекочитаемая строка
    
    Examples:
        >>> format_duration_seconds(45)
        '45s'
        >>> format_duration_seconds(150)
        '2m 30s'
        >>> format_duration_seconds(7265)
        '2h 1m 5s'
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    
    minutes, secs = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins}m {secs}s"


def format_duration_minutes(minutes: float | int) -> str:
    """
    Форматирование длительности в минутах
    
    Args:
        minutes: Длительность в минутах
    
    Returns:
        Человекочитаемая строка
    
    Examples:
        >>> format_duration_minutes(45)
        '45 мин'
        >>> format_duration_minutes(150)
        '2 ч 30 мин'
    """
    if minutes < 60:
        return f"{int(minutes)} мин"
    
    hours, mins = divmod(int(minutes), 60)
    return f"{hours} ч {mins} мин"


def format_bytes(bytes_value: int | float, precision: int = 2) -> str:
    """
    Форматирование размера в байтах
    
    Args:
        bytes_value: Размер в байтах
        precision: Количество десятичных знаков
    
    Returns:
        Человекочитаемая строка (KB, MB, GB, TB)
    
    Examples:
        >>> format_bytes(1024)
        '1.00 KB'
        >>> format_bytes(1048576)
        '1.00 MB'
        >>> format_bytes(5368709120)
        '5.00 GB'
    """
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    size = float(bytes_value)
    unit_index = 0
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    return f"{size:.{precision}f} {units[unit_index]}"


def format_large_number(value: float | int) -> str:
    """
    Форматирование больших чисел с K, M, B суффиксами
    
    Args:
        value: Число для форматирования
    
    Returns:
        Компактная строка
    
    Examples:
        >>> format_large_number(1500)
        '1.5K'
        >>> format_large_number(1500000)
        '1.5M'
        >>> format_large_number(2300000000)
        '2.3B'
    """
    abs_value = abs(value)
    sign = '-' if value < 0 else ''
    
    if abs_value < 1000:
        return f"{sign}{abs_value:.0f}"
    elif abs_value < 1_000_000:
        return f"{sign}{abs_value/1000:.1f}K"
    elif abs_value < 1_000_000_000:
        return f"{sign}{abs_value/1_000_000:.1f}M"
    else:
        return f"{sign}{abs_value/1_000_000_000:.1f}B"


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Безопасное преобразование в float
    
    Args:
        value: Значение для преобразования
        default: Значение по умолчанию
    
    Returns:
        Float или default
    
    Examples:
        >>> safe_float("123.45")
        123.45
        >>> safe_float("invalid", 0.0)
        0.0
        >>> safe_float(None, -1.0)
        -1.0
    """
    if value is None:
        return default
    
    try:
        result = float(value)
        return result if not (result != result) else default  # Check for NaN
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """
    Безопасное преобразование в int
    
    Args:
        value: Значение для преобразования
        default: Значение по умолчанию
    
    Returns:
        Int или default
    
    Examples:
        >>> safe_int("123")
        123
        >>> safe_int("123.99")
        123
        >>> safe_int("invalid", -1)
        -1
    """
    if value is None:
        return default
    
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def truncate_string(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    Обрезка строки с добавлением суффикса
    
    Args:
        text: Строка для обрезки
        max_length: Максимальная длина
        suffix: Суффикс для добавления
    
    Returns:
        Обрезанная строка
    
    Examples:
        >>> truncate_string("Very long text that needs truncation", 20)
        'Very long text th...'
        >>> truncate_string("Short text", 50)
        'Short text'
    """
    if len(text) <= max_length:
        return text
    
    return text[: max_length - len(suffix)] + suffix


# 🎯 PERFECT 10/10: Enhanced utilities for edge cases

def safe_json_loads(data: str, default=None):
    """
    Safe JSON parsing with fallback.
    
    Args:
        data: JSON string to parse
        default: Default value on error (default: None)
        
    Returns:
        Parsed JSON or default value
        
    Examples:
        >>> safe_json_loads('{"key": "value"}')
        {'key': 'value'}
        >>> safe_json_loads('invalid json', default={})
        {}
        >>> safe_json_loads('', default=None)
        None
    """
    if not data or not isinstance(data, str) or not data.strip():
        return default
    
    try:
        result = json.loads(data)
        return result if isinstance(result, (dict, list)) else default
    except (json.JSONDecodeError, ValueError):
        return default


def clamp(value: float, min_value: float, max_value: float) -> float:
    """
    Clamp value between min and max.
    
    Args:
        value: Value to clamp
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        
    Returns:
        Clamped value
        
    Examples:
        >>> clamp(5, 0, 10)
        5
        >>> clamp(-5, 0, 10)
        0
        >>> clamp(15, 0, 10)
        10
    """
    return max(min_value, min(value, max_value))


def format_percentage_change(old_value: float, new_value: float, precision: int = 2) -> str:
    """
    Format percentage change between two values.
    
    Args:
        old_value: Original value
        new_value: New value
        precision: Decimal precision
        
    Returns:
        Formatted percentage change with sign
        
    Examples:
        >>> format_percentage_change(100, 150)
        '+50.00%'
        >>> format_percentage_change(100, 75)
        '-25.00%'
        >>> format_percentage_change(0, 100)
        'N/A'
    """
    if old_value == 0:
        return "N/A"
    
    change = ((new_value - old_value) / old_value) * 100
    sign = "+" if change > 0 else ""
    
    return f"{sign}{change:.{precision}f}%"
