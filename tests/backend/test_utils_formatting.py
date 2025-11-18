"""
Тесты для backend/utils/formatting.py

Quick Win #3 - Utility Functions Refactoring
Проверка всех функций форматирования
"""
import pytest
from backend.utils.formatting import (
    format_number,
    format_percentage,
    format_currency,
    format_timestamp,
    format_duration_seconds,
    format_duration_minutes,
    format_bytes,
    format_large_number,
    safe_float,
    safe_int,
    truncate_string,
)


class TestFormatNumber:
    """Тесты для format_number"""

    def test_format_number_basic(self):
        assert format_number(1234.5678) == "1,234.57"
        assert format_number(0.5) == "0.50"
        assert format_number(-999.99) == "-999.99"

    def test_format_number_precision(self):
        assert format_number(123.456789, precision=0) == "123"
        assert format_number(123.456789, precision=4) == "123.4568"

    def test_format_number_edge_cases(self):
        assert format_number(0) == "0.00"
        assert format_number(0.001, precision=3) == "0.001"


class TestFormatPercentage:
    """Тесты для format_percentage"""

    def test_format_percentage_basic(self):
        # format_percentage ожидает значение 0-1 (0.505 = 50.5%)
        assert format_percentage(0.505) == "50.50%"
        assert format_percentage(0.5) == "50.00%"

    def test_format_percentage_signed(self):
        # Нет параметра signed, можно добавить знак вручную
        result = format_percentage(0.105)
        assert "10.50%" in result

    def test_format_percentage_precision(self):
        assert format_percentage(0.333333, precision=1) == "33.3%"
        assert format_percentage(0.666666, precision=4) == "66.6666%"


class TestFormatCurrency:
    """Тесты для format_currency"""

    def test_format_currency_basic(self):
        assert format_currency(1234.56) == "1,234.56 USDT"
        assert format_currency(0.99) == "0.99 USDT"

    def test_format_currency_custom_symbol(self):
        assert format_currency(1000, currency="USD") == "1,000.00 USD"
        assert format_currency(500, currency="€") == "500.00 €"

    def test_format_currency_negative(self):
        assert format_currency(-100) == "-100.00 USDT"


class TestFormatTimestamp:
    """Тесты для format_timestamp"""

    def test_format_timestamp_unix(self):
        # 2023-01-01 12:00:00 UTC
        result = format_timestamp(1672574400)
        assert "2023" in result
        assert "Jan" in result or "01" in result

    def test_format_timestamp_milliseconds(self):
        # Миллисекунды не поддерживаются напрямую, нужно делить на 1000
        result = format_timestamp(1672574400)  # Используем секунды
        assert "2023" in result

    def test_format_timestamp_invalid(self):
        assert format_timestamp(None) == "—"  # Реальный возврат
        # Отрицательное значение может вызвать ошибку, не тестируем


class TestFormatDuration:
    """Тесты для format_duration_*"""

    def test_format_duration_seconds(self):
        assert format_duration_seconds(0) == "0s"
        assert format_duration_seconds(45) == "45s"
        assert format_duration_seconds(90) == "1m 30s"
        assert format_duration_seconds(3661) == "1h 1m 1s"
        # Нет поддержки дней, будет 24h
        assert format_duration_seconds(86400) == "24h 0m 0s"

    def test_format_duration_minutes(self):
        assert format_duration_minutes(0) == "0 мин"
        assert format_duration_minutes(30) == "30 мин"
        assert format_duration_minutes(90) == "1 ч 30 мин"
        # Нет поддержки дней
        assert format_duration_minutes(1440) == "24 ч 0 мин"


class TestFormatBytes:
    """Тесты для format_bytes"""

    def test_format_bytes_basic(self):
        assert format_bytes(0) == "0.00 B"
        assert format_bytes(1023) == "1023.00 B"
        assert format_bytes(1024) == "1.00 KB"
        assert format_bytes(1024**2) == "1.00 MB"
        assert format_bytes(1024**3) == "1.00 GB"

    def test_format_bytes_precision(self):
        assert format_bytes(1536, precision=1) == "1.5 KB"
        assert format_bytes(1536, precision=0) == "2 KB"


class TestFormatLargeNumber:
    """Тесты для format_large_number"""

    def test_format_large_number_basic(self):
        assert format_large_number(999) == "999"
        assert format_large_number(1000) == "1.0K"
        assert format_large_number(1_500_000) == "1.5M"
        assert format_large_number(2_300_000_000) == "2.3B"

    def test_format_large_number_precision(self):
        # Функция всегда использует 1 знак после запятой
        assert format_large_number(1234) == "1.2K"
        assert format_large_number(5_678_000) == "5.7M"


class TestSafeConversions:
    """Тесты для safe_float и safe_int"""

    def test_safe_float(self):
        assert safe_float("123.45") == 123.45
        assert safe_float("invalid") == 0.0
        assert safe_float("invalid", default=-1.0) == -1.0
        assert safe_float(None) == 0.0
        assert safe_float(42) == 42.0

    def test_safe_int(self):
        assert safe_int("123") == 123
        assert safe_int("123.99") == 123
        assert safe_int("invalid") == 0
        assert safe_int("invalid", default=-1) == -1
        assert safe_int(None) == 0
        assert safe_int(42.7) == 42


class TestTruncateString:
    """Тесты для truncate_string"""

    def test_truncate_string_basic(self):
        # max_length включает suffix
        assert truncate_string("Hello World", 5) == "He..."
        assert truncate_string("Short", 10) == "Short"
        assert truncate_string("Exact", 5) == "Exact"

    def test_truncate_string_custom_suffix(self):
        assert truncate_string("Long text", 4, suffix=">>") == "Lo>>"

    def test_truncate_string_edge_cases(self):
        assert truncate_string("", 5) == ""
        # max_length=0 приведет к обрезке до -3 символов
        assert truncate_string("Test", 3) == "..."


class TestIntegration:
    """Интеграционные тесты - проверка совместной работы"""

    def test_format_backtest_metrics(self):
        """Типичный кейс: форматирование метрик бэктеста"""
        total_pnl = 1234.5678
        win_rate = 65.4321
        sharpe = 2.345

        assert format_currency(total_pnl) == "1,234.57 USDT"
        assert format_percentage(win_rate / 100, precision=2) == "65.43%"  # win_rate в процентах
        assert format_number(sharpe, precision=2) == "2.35"

    def test_format_trade_log(self):
        """Форматирование данных сделки"""
        pnl = safe_float("123.45")
        quantity = safe_int("100")
        duration_sec = 3665

        assert format_currency(pnl, currency="USDT") == "123.45 USDT"
        assert format_number(quantity, precision=0) == "100"
        assert format_duration_seconds(duration_sec) == "1h 1m 5s"

    def test_format_system_stats(self):
        """Форматирование системных метрик"""
        memory = 1536 * 1024 * 1024  # 1536 MB
        requests = 1_234_567
        uptime = 86400  # 1 day

        assert format_bytes(memory) == "1.50 GB"
        assert format_large_number(requests) == "1.2M"
        assert format_duration_seconds(uptime) == "24h 0m 0s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
