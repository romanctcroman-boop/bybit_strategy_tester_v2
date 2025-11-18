#!/usr/bin/env python3
"""
🧪 Тестирование input_validation.py с реальными торговыми парами
Проверяем рекомендацию DeepSeek: поддержка дефисов и специальных символов
"""

import sys
from pathlib import Path

# Add mcp-server to path
sys.path.insert(0, str(Path(__file__).parent / "mcp-server"))

from input_validation import InputValidator, safe_symbol, ValidationError

def test_real_symbols():
    """
    Тестируем реальные торговые пары с разных бирж
    """
    print("\n" + "=" * 80)
    print("🧪 ТЕСТИРОВАНИЕ ВАЛИДАЦИИ С РЕАЛЬНЫМИ ТОРГОВЫМИ ПАРАМИ")
    print("=" * 80)
    
    validator = InputValidator()
    
    # Реальные торговые пары с разных бирж
    test_symbols = [
        # Bybit (стандарт)
        ("BTCUSDT", True, "Bybit стандартная пара"),
        ("ETHUSDT", True, "Bybit стандартная пара"),
        ("SOLUSDT", True, "Bybit стандартная пара"),
        
        # Binance (стандарт)
        ("BNBUSDT", True, "Binance стандартная пара"),
        ("ADAUSDT", True, "Binance стандартная пара"),
        
        # Coinbase / Kraken (с дефисами)
        ("BTC-USD", False, "Coinbase пара с дефисом"),
        ("ETH-USD", False, "Coinbase пара с дефисом"),
        ("BTC-USDT", False, "Kraken пара с дефисом"),
        
        # FTX style (с косой чертой)
        ("BTC/USD", False, "FTX style пара"),
        ("ETH/USDT", False, "FTX style пара"),
        
        # Spot vs Futures
        ("BTCUSDT_PERP", False, "Perpetual контракт с подчёркиванием"),
        ("ETHUSDT-PERP", False, "Perpetual контракт с дефисом"),
        
        # Edge cases
        ("BTC", True, "Короткий символ"),
        ("BTCUSDTBTCUSDT12345", True, "Длинный символ (19 chars <= 20)"),
        ("BTCUSDTBTCUSDT1234567", False, "Слишком длинный символ (21 chars > 20)"),
        
        # Атаки
        ("BTC'; DROP TABLE--", False, "SQL injection попытка"),
        ("BTC<script>alert(1)</script>", False, "XSS попытка"),
        ("../../../etc/passwd", False, "Path traversal"),
    ]
    
    passed = 0
    failed = 0
    
    print("\n📊 Тестовые случаи:\n")
    
    for symbol, should_pass, description in test_symbols:
        try:
            result = validator.validate_symbol(symbol)
            
            if should_pass:
                print(f"✅ PASS: {symbol:30} - {description}")
                passed += 1
            else:
                print(f"❌ FAIL: {symbol:30} - должен был заблокироваться! ({description})")
                failed += 1
                
        except ValidationError as e:
            if not should_pass:
                print(f"✅ PASS: {symbol:30} - правильно заблокирован ({description})")
                passed += 1
            else:
                print(f"❌ FAIL: {symbol:30} - неправильно заблокирован! ({description})")
                print(f"         Причина: {e}")
                failed += 1
    
    # Итоги
    print("\n" + "=" * 80)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 80)
    
    total = passed + failed
    success_rate = (passed / total * 100) if total > 0 else 0
    
    print(f"\n✅ Пройдено: {passed}/{total}")
    print(f"❌ Провалено: {failed}/{total}")
    print(f"📈 Success Rate: {success_rate:.1f}%")
    
    # Анализ
    print("\n" + "=" * 80)
    print("💡 АНАЛИЗ РЕЗУЛЬТАТОВ")
    print("=" * 80)
    
    if failed == 0:
        print("\n✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("   Валидация работает корректно для текущих требований.")
    else:
        print(f"\n⚠️  Обнаружено {failed} проблем(ы):")
        print("   1. Если нужна поддержка дефисов (BTC-USD) - добавить '-' в regex")
        print("   2. Если нужна поддержка слэшей (BTC/USD) - добавить '/' в regex")
        print("   3. Если нужна поддержка подчёркиваний (_PERP) - добавить '_' в regex")
    
    print("\n" + "=" * 80)
    print("📋 РЕКОМЕНДАЦИИ DEEPSEEK")
    print("=" * 80)
    
    print("\nDeepSeek указал на LOW severity issue:")
    print("'Валидация символов может быть слишком строгой для некоторых торговых пар'")
    
    print("\n🔧 Варианты улучшения:")
    print("   1. CONSERVATIVE: Оставить как есть (только алфавитно-цифровые)")
    print("      ➜ Максимальная безопасность")
    print("      ➜ Работает для Bybit/Binance (основные биржи)")
    
    print("\n   2. MODERATE: Добавить поддержку дефиса")
    print("      ➜ Regex: r'^[A-Za-z0-9-]{{1,20}}$'")
    print("      ➜ Поддержка Coinbase/Kraken стиля (BTC-USD)")
    
    print("\n   3. PERMISSIVE: Добавить дефис, слэш, подчёркивание")
    print("      ➜ Regex: r'^[A-Za-z0-9/_-]{{1,20}}$'")
    print("      ➜ Поддержка всех популярных стилей")
    
    print("\n✅ РЕКОМЕНДАЦИЯ: CONSERVATIVE подход (текущая реализация)")
    print("   Причина: Bybit Strategy Tester работает только с Bybit")
    print("   Bybit использует стандарт: BTCUSDT (без специальных символов)")
    print("   Если понадобится кросс-биржевая поддержка - легко расширить.")
    
    return failed == 0


if __name__ == "__main__":
    success = test_real_symbols()
    sys.exit(0 if success else 1)
