# Quick Start - WebSocket Live-Data

Быстрое руководство по запуску и использованию WebSocket Live-Data (Phase 1.7)

---

## 🚀 Быстрый старт

### 1. Установить зависимости

```powershell
cd D:\bybit_strategy_tester_v2
.venv\Scripts\pip install websockets==12.0
```

### 2. Запустить инфраструктуру

```powershell
.\start_infrastructure.ps1
```

Это запустит:

- ✅ Redis
- ✅ RabbitMQ
- ✅ Celery Worker
- ✅ FastAPI Server
- ✅ **Bybit WebSocket Worker** (новое!)

### 3. Проверить статус

```powershell
.\start_infrastructure.ps1 -StatusOnly
```

Ожидаемый вывод:

```
[OK] Redis: Running (port 6379)
[OK] RabbitMQ: Running (port 5672)
[OK] Celery: Running (PID: 1234)
[OK] FastAPI: Running (port 8000)
[OK] Bybit WS Worker: Running (PID: 5678)  ← Новый компонент
```

### 4. Запустить тесты

```powershell
python test_live_websocket.py
```

Все 6 тестов должны пройти успешно! ✅

---

## 📡 Доступные Endpoints

### WebSocket Endpoints

#### 1. Candles (свечи)

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/live/ws/candles/BTCUSDT/1');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Candle:', data.candle);
};
```

**Параметры:**

- `{symbol}`: BTCUSDT, ETHUSDT, SOLUSDT, etc.
- `{timeframe}`: 1, 5, 15, 60, D (минуты или день)

#### 2. Trades (сделки)

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/live/ws/trades/BTCUSDT');
```

#### 3. Ticker (24h статистика)

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/live/ws/ticker/BTCUSDT');
```

### REST Endpoints

#### Health Check

```bash
curl http://localhost:8000/api/v1/live/health
```

Ответ:

```json
{
  "status": "healthy",
  "redis": "connected",
  "active_channels": 9
}
```

#### Active Channels

```bash
curl http://localhost:8000/api/v1/live/channels
```

Ответ:

```json
{
  "success": true,
  "channels": ["candles:BTCUSDT:1", "candles:BTCUSDT:5", "candles:ETHUSDT:1"],
  "count": 9
}
```

---

## 💻 Пример использования (Frontend)

### HTML + JavaScript

```html
<!DOCTYPE html>
<html>
  <head>
    <title>Live Candles</title>
  </head>
  <body>
    <h1>BTCUSDT Live Price</h1>
    <div id="price"></div>

    <script>
      const ws = new WebSocket('ws://localhost:8000/api/v1/live/ws/candles/BTCUSDT/1');

      ws.onopen = () => {
        console.log('Connected!');
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'update') {
          const candle = data.candle;
          document.getElementById('price').innerHTML = `
                    <p>Open: ${candle.open}</p>
                    <p>High: ${candle.high}</p>
                    <p>Low: ${candle.low}</p>
                    <p>Close: ${candle.close}</p>
                    <p>Volume: ${candle.volume}</p>
                    <p>Status: ${candle.confirm ? '✅ Closed' : '⏳ Ongoing'}</p>
                `;
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      ws.onclose = () => {
        console.log('Disconnected');
      };
    </script>
  </body>
</html>
```

### Python Client

```python
import asyncio
import json
import websockets

async def listen():
    uri = "ws://localhost:8000/api/v1/live/ws/candles/BTCUSDT/1"

    async with websockets.connect(uri) as websocket:
        print("Connected!")

        while True:
            message = await websocket.recv()
            data = json.loads(message)

            if data['type'] == 'update':
                candle = data['candle']
                print(f"Close: {candle['close']}, Volume: {candle['volume']}")

asyncio.run(listen())
```

---

## ⚙️ Настройка Worker

### Изменить символы и таймфреймы

**Вручную запустить worker:**

```powershell
.venv\Scripts\python.exe -m backend.workers.bybit_ws_worker `
    --symbols BTCUSDT,ETHUSDT,BNBUSDT `
    --timeframes 1,5,15,60
```

**Или отредактировать `start_infrastructure.ps1`:**

```powershell
# Найти строку:
$proc = Start-Process -FilePath ".venv\Scripts\python.exe" `
    -ArgumentList "-m", "backend.workers.bybit_ws_worker", `
    "--symbols", "BTCUSDT,ETHUSDT,SOLUSDT", `  ← Изменить здесь
    "--timeframes", "1,5,15" `                  ← И здесь
    -WindowStyle Hidden -PassThru
```

---

## 🐛 Troubleshooting

### ❌ Redis не запущен

```
[X] Redis: Not running
```

**Решение:**

```powershell
Start-Service Redis
```

### ❌ Worker не публикует данные

```
⚠️ No messages (Bybit WS Worker not publishing?)
```

**Решение:**

1. Проверить логи worker:

   ```powershell
   Get-Process | Where-Object { $_.ProcessName -eq "python" }
   ```

2. Перезапустить worker:
   ```powershell
   .\start_infrastructure.ps1 -StopAll
   .\start_infrastructure.ps1
   ```

### ❌ WebSocket connection failed

```
❌ WebSocket connection failed
```

**Решение:**

1. Убедитесь что FastAPI запущен:

   ```bash
   curl http://localhost:8000/health
   ```

2. Проверьте Redis:
   ```bash
   curl http://localhost:8000/api/v1/live/health
   ```

### ❌ No data received

```
⚠️ No data received (Bybit WS Worker not running?)
```

**Решение:**

- Worker может быть отключен от Bybit
- Проверить статус:
  ```bash
  curl http://localhost:8000/api/v1/live/channels
  ```
- Если `count: 0`, перезапустить worker

---

## 📊 Swagger UI

Откройте в браузере:

```
http://localhost:8000/docs
```

Найдите секцию **"Live Data"** с эндпоинтами:

- `GET /api/v1/live/health`
- `GET /api/v1/live/channels`
- `WS /api/v1/live/ws/candles/{symbol}/{timeframe}`
- `WS /api/v1/live/ws/trades/{symbol}`
- `WS /api/v1/live/ws/ticker/{symbol}`

---

## 📚 Дополнительная информация

- **Полная документация:** `docs/PHASE1.7_COMPLETED.md`
- **Тесты:** `test_live_websocket.py`
- **Код worker:** `backend/workers/bybit_ws_worker.py`
- **Код endpoints:** `backend/api/routers/live.py`

---

## ✅ Checklist перед использованием

- [ ] Redis запущен
- [ ] RabbitMQ запущен
- [ ] FastAPI запущен
- [ ] Bybit WS Worker запущен
- [ ] Тесты прошли (6/6)
- [ ] Health check вернул "healthy"
- [ ] Active channels > 0

---

**Готово!** Теперь у вас работает real-time стриминг данных от Bybit! 🎉

**Следующий шаг:** Phase 2 - Frontend Electron Application с графиками в реальном времени!
