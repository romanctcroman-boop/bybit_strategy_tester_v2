# 🚀 Быстрый старт - Bybit Strategy Tester

## Самый простой способ запуска

### Windows:
Дважды кликните на файл:
```
START_ALL.bat
```

Или в PowerShell:
```powershell
.\start.ps1
```

Это автоматически запустит:
- ✅ Backend API (http://localhost:8000)
- ✅ Frontend Server (http://localhost:8080)
- ✅ Откроет Demo UI и Swagger UI в браузере

---

## 📊 Доступные интерфейсы

### 1. Demo UI (Рекомендуется!)
**http://localhost:8080/demo.html**

Красивый веб-интерфейс с:
- Загрузка данных с Bybit
- Запуск бэктестов
- Просмотр метрик и сделок
- Графики результатов

### 2. Swagger UI (Для разработчиков)
**http://localhost:8000/docs**

Интерактивная документация API:
- Полный список endpoints
- Тестирование прямо в браузере
- Примеры запросов/ответов
- JSON схемы

### 3. Test Page (Для отладки)
**http://localhost:8080/test.html**

Простая страница для тестирования endpoints:
- Быстрая проверка работоспособности
- Кнопки для каждого endpoint
- Вывод JSON ответов

---

## 🎯 Как использовать Demo UI

### Шаг 1: Открыть Demo UI
http://localhost:8080/demo.html

### Шаг 2: Настроить параметры
**Run Backtest секция:**
- Symbol: BTCUSDT (или другой)
- Interval: D (дневной) / 15 (15 минут) / 1 (1 минута)
- Days to Test: 30-90
- Strategy: RSI Mean Reversion
- Initial Capital: 10000
- Leverage: 1-10

### Шаг 3: Запустить
Нажмите **"Run Backtest"** или **"Quick Test"**

### Шаг 4: Просмотреть результаты
- **Метрики**: Total Return, Sharpe Ratio, Max Drawdown
- **Сделки**: Список всех входов/выходов с PnL
- **Статистика**: Win Rate, Profit Factor

---

## 💻 Использование через PowerShell

### Быстрый бэктест
```powershell
Invoke-RestMethod "http://localhost:8000/api/v1/backtest/quick/BTCUSDT/D?days=60" | ConvertTo-Json
```

### Получить список символов
```powershell
Invoke-RestMethod "http://localhost:8000/api/v1/data/symbols"
```

### Получить список стратегий
```powershell
Invoke-RestMethod "http://localhost:8000/api/v1/backtest/strategies" | ConvertTo-Json
```

### Полный бэктест с параметрами
```powershell
$body = @{
    symbol = "ETHUSDT"
    interval = "15"
    start_date = "2025-09-01T00:00:00"
    end_date = "2025-10-16T00:00:00"
    strategy_name = "RSI Mean Reversion"
    initial_capital = 10000
    leverage = 2
    commission_rate = 0.0006
    slippage_rate = 0.0001
    strategy_params = @{
        rsi_period = 14
        rsi_oversold = 30
        rsi_overbought = 70
    }
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/backtest/run" `
    -Method POST `
    -Headers @{"Content-Type"="application/json"} `
    -Body $body | ConvertTo-Json -Depth 5
```

---

## 🔧 Остановка сервисов

### Способ 1: Закрыть окна
Просто закройте окна терминалов:
- "Backend API - Port 8000"
- "Frontend Server - Port 8080"

### Способ 2: Через PowerShell
```powershell
# Остановить процессы Python
Get-Process python | Where-Object {$_.MainWindowTitle -like "*8000*" -or $_.MainWindowTitle -like "*8080*"} | Stop-Process
```

---

## ⚙️ Ручной запуск (если батник не работает)

### Терминал 1: Backend API
```powershell
cd D:\bybit_strategy_tester_v2
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### Терминал 2: Frontend Server
```powershell
cd D:\bybit_strategy_tester_v2\frontend
python -m http.server 8080
```

### Открыть браузеры
- Demo UI: http://localhost:8080/demo.html
- Swagger: http://localhost:8000/docs

---

## 📝 Примеры тестирования

### Пример 1: BTC на дневных свечах
- Symbol: BTCUSDT
- Interval: D
- Days: 60
- Capital: 10000
- Leverage: 1

### Пример 2: ETH на 15-минутках
- Symbol: ETHUSDT
- Interval: 15
- Days: 30
- Capital: 5000
- Leverage: 3

### Пример 3: Агрессивная стратегия
- Symbol: SOLUSDT
- Interval: 5
- Days: 14
- Capital: 10000
- Leverage: 5
- RSI Oversold: 25
- RSI Overbought: 75

---

## ❓ Проблемы и решения

### "Error: Failed to fetch"
**Решение:**
1. Нажмите Ctrl+Shift+R для очистки кэша
2. Или используйте http://localhost:8080/demo.html вместо file://
3. Или используйте Swagger UI: http://localhost:8000/docs

### "Connection refused"
**Решение:**
1. Проверьте что сервисы запущены
2. Выполните: `.\start.ps1` или `START_ALL.bat`
3. Подождите 5-10 секунд после запуска

### "No data found"
**Решение:**
1. Проверьте интернет-соединение
2. Bybit API может быть недоступен
3. Попробуйте другой символ или интервал

### Сервер не запускается
**Решение:**
```powershell
# Проверить что порты свободны
netstat -ano | findstr :8000
netstat -ano | findstr :8080

# Если порты заняты, найти и убить процесс
Get-Process | Where-Object {$_.ProcessName -eq "python"} | Stop-Process
```

---

## 🎉 Готово!

Теперь у вас полностью рабочая платформа для бэктестинга!

**Следующие шаги:**
1. Попробуйте разные символы (BTC, ETH, SOL)
2. Поэкспериментируйте с параметрами RSI
3. Измените leverage и capital
4. Сравните результаты на разных интервалах

**Удачного тестирования! 🚀**
