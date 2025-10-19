# 📊 Bybit Strategy Tester

Полнофункциональный тестер торговых стратегий для Bybit с веб-интерфейсом Streamlit.

## 🎉 НОВОЕ: TradingView Lightweight Charts

**Проект мигрирован на профессиональные графики TradingView!**

✨ **Преимущества:**
- ⚡ **В 10 раз быстрее** Plotly
- 💎 **Профессиональный вид** как у TradingView
- 🎨 **Плавная интерактивность** (zoom, pan)
- 📦 **Легковесность** (100 KB vs 1 MB)

📖 **Подробнее:** См. [MIGRATION_COMPLETE.md](MIGRATION_COMPLETE.md) и [LIGHTWEIGHT_CHARTS.md](LIGHTWEIGHT_CHARTS.md)

## 🚀 Быстрый старт

```bash
# 1. Запустите Streamlit APP
start.bat

# 2. Откройте в браузере
http://localhost:8501
```

## 📁 Структура проекта

- **config/** - Настройки и API ключи
- **data/** - Загрузчик данных с Bybit
- **strategies/** - Торговые стратегии (MA, RSI, BB, MACD)
- **backtest/** - Модуль бэктестинга
- **web/** - Streamlit интерфейс
- **results/** - Результаты тестов и графики
- **logs/** - Логи работы

## 🎯 Возможности

- ✅ **Streamlit APP** - веб-интерфейс для всех операций
- ✅ **Загрузка данных** - автоматическая загрузка с Bybit API
- ✅ **DataStore** - быстрое хранилище в Parquet
- ✅ **Backtest Engine** - тестирование стратегий
- ✅ **Properties** - настройка капитала, кредитного плеча, комиссий
- ✅ **Strategy Constructor** - конструктор стратегий на индикаторах
- ✅ **Metrics** - детальная аналитика (Sharpe, Sortino, Max DD)
- ✅ **Optimizer** - оптимизация параметров стратегий
- ✅ **Walk-Forward** - валидация на out-of-sample данных

## 📊 Таймфреймы

1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1D, 1W, 1M

## 💱 Торговые пары

BTC, ETH, SOL, BNB, XRP, ADA, DOGE, MATIC, DOT, AVAX, LINK, UNI, LTC, ATOM, XLM, APT, ARB, OP и другие топовые криптовалюты на Bybit

## ⚠️ Важно: Ограничения Bybit API

Bybit предоставляет **ограниченную историю** в зависимости от таймфрейма:

| Таймфрейм | Максимум дней | Примечание |
|-----------|---------------|------------|
| **15m**   | ~106 дней     | 3.5 месяца |
| **1h**    | ~425 дней     | 1.2 года   |
| **4h**    | ~1,700 дней   | 4.6 года   |
| **1D**    | ~3 года       | Для долгосрочного анализа |

**📖 Подробнее**: [BYBIT_API_LIMITS.md](BYBIT_API_LIMITS.md)

## 🛠 Использование

1. **Настройка API ключей** в `config/settings.py`
2. **Запуск**: `start.bat` или `streamlit run web/Streamlit_APP.py`
3. **Загрузка данных** через Streamlit APP
4. **Настройка Properties** (капитал, плечо, комиссии)
5. **Создание стратегии** через Strategy Constructor
6. **Запуск бэктеста** через Backtest Engine
7. **Анализ результатов** в Metrics

## 📚 Документация

### Для пользователей:
- **[📖 Как выбрать таймфрейм и период](TIMEFRAME_PERIOD_GUIDE.md)** ⭐ Начните отсюда!
- [⚠️ Ограничения Bybit API](BYBIT_API_LIMITS.md)
- [🔄 Как работает загрузка данных](PAGINATION_MECHANISM.md)

### Для разработчиков:
- [🔧 Отчёт: Устранение ограничений загрузки](DATA_LIMITS_REPORT.md)
- [🔄 Механизм пагинации API](PAGINATION_MECHANISM.md) - Технические детали
- [⚙️ Интеграция Properties](PROPERTIES_INTEGRATION_REPORT.md)
- [📊 Источники данных](DATA_SOURCE_EXPLANATION.md)
- [🎨 Улучшения Streamlit APP](STREAMLIT_APP_IMPROVEMENTS_REPORT.md)

## 📝 Версия

**v1.0** - Полный функционал с веб-интерфейсом (15.10.2025)
