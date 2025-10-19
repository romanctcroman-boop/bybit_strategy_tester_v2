# 🚀 Bybit Strategy Tester

**Professional Cryptocurrency Trading Strategy Backtesting Platform**

[![Status](https://img.shields.io/badge/Status-Production%20Ready-green)]()
[![Python](https://img.shields.io/badge/Python-3.11+-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-009688)]()
[![License](https://img.shields.io/badge/License-MIT-yellow)]()

---

## ⚡ Быстрый старт

### 1. Запустить приложение (Windows)
```powershell
.\start.ps1
```
или двойной клик на `START_ALL.bat`

### 2. Открыть Demo UI
http://localhost:8080/demo.html

### 3. Запустить бэктест
1. Выберите символ (BTCUSDT)
2. Выберите интервал (15 minutes / D)
3. Нажмите "Run Backtest"
4. Посмотрите результаты!

---

## 📋 Возможности

- ✅ **Загрузка данных** с Bybit API v5
- ✅ **Бэктестинг** торговых стратегий
- ✅ **RSI Mean Reversion** стратегия
- ✅ **Метрики:** Sharpe Ratio, Max Drawdown, Win Rate
- ✅ **REST API** с автодокументацией
- ✅ **Web UI** для удобного тестирования
- ✅ **Настройка** leverage, capital, комиссий

---

## 🛠️ Технологии

**Backend:**
- Python 3.13+ | FastAPI | Pandas | Bybit API v5

**Frontend:**
- HTML/CSS/JavaScript | Swagger UI

**Data:**
- SQLAlchemy ORM | PostgreSQL (опционально)

---

## 📚 Документация

- **[Быстрый старт](QUICK_START_GUIDE.md)** - Начните за 2 минуты
- **[Руководство по тестированию](TESTING_GUIDE.md)** - Примеры использования
- **[Финальный статус](PROJECT_STATUS_FINAL.md)** - Что работает
- **[API Docs](http://localhost:8000/docs)** - Swagger UI (после запуска)

---

## 🎯 Примеры использования

### PowerShell
```powershell
# Быстрый бэктест
Invoke-RestMethod "http://localhost:8000/api/v1/backtest/quick/BTCUSDT/D?days=60"

# Получить символы
Invoke-RestMethod "http://localhost:8000/api/v1/data/symbols"
```

### Demo UI
1. Откройте http://localhost:8080/demo.html
2. Настройте параметры
3. Нажмите "Run Backtest"
4. Смотрите результаты!

---

## 📊 Доступные endpoints

### Data API
- `GET /api/v1/data/symbols` - Список символов
- `POST /api/v1/data/load` - Загрузить данные
- `GET /api/v1/data/latest/{symbol}/{interval}` - Последние свечи

### Backtesting API
- `GET /api/v1/backtest/strategies` - Список стратегий
- `POST /api/v1/backtest/run` - Запустить полный бэктест
- `GET /api/v1/backtest/quick/{symbol}/{interval}` - Быстрый бэктест

---

## 📈 Прогресс проекта

- [x] Project Setup & Infrastructure
- [x] Database Schema
- [x] Data Layer (Bybit integration)
- [x] Backtest Engine
- [x] REST API Layer
- [ ] Strategy Library expansion
- [ ] Optimization Engine
- [ ] Electron + React Frontend

**Текущий прогресс:** ~45%

---

## 🎉 Статус

**✅ ПРОЕКТ ПОЛНОСТЬЮ РАБОТАЕТ!**

Готов к использованию для реального бэктестинга торговых стратегий!

---

**Версия:** 1.0.0 | **Дата:** Октябрь 2025
