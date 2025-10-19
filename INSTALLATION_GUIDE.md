# ⚡ БЫСТРАЯ ИНСТРУКЦИЯ: Установка недостающих компонентов

**Дата:** 16 октября 2025  
**Время:** ~30 минут

---

## 🎯 ЧТО НУЖНО УСТАНОВИТЬ

### 1️⃣ PostgreSQL 16 + TimescaleDB (КРИТИЧНО)

### 2️⃣ Python пакеты в venv (КРИТИЧНО)

### 3️⃣ Redis 7 (ОПЦИОНАЛЬНО)

---

## 📥 ШАГ 1: Установка PostgreSQL 16

### Windows:

**1. Download installer:**

```
https://www.enterprisedb.com/downloads/postgres-postgresql-downloads
```

- Выбрать: PostgreSQL 16.x Windows x86-64
- Размер: ~350 MB

**2. Запустить installer:**

- Install for: All Users
- Installation Directory: `C:\Program Files\PostgreSQL\16`
- Components: ✅ Все (PostgreSQL Server, pgAdmin, Command Line Tools)
- Data Directory: `C:\Program Files\PostgreSQL\16\data`
- **Password:** задать пароль для superuser (postgres)
- Port: **5432** (default)
- Locale: English, United States

**3. Добавить в PATH:**

```powershell
# Открыть PowerShell как Administrator
$env:Path += ";C:\Program Files\PostgreSQL\16\bin"
[System.Environment]::SetEnvironmentVariable("Path", $env:Path, [System.EnvironmentVariableTarget]::Machine)
```

**4. Проверить установку:**

```powershell
psql --version
# Должно вывести: psql (PostgreSQL) 16.x
```

---

## 📥 ШАГ 2: Установка TimescaleDB

### Windows:

**1. Download installer:**

```
https://docs.timescale.com/self-hosted/latest/install/installation-windows/
```

- Выбрать версию для PostgreSQL 16

**2. Запустить installer:**

- Выбрать PostgreSQL installation: `C:\Program Files\PostgreSQL\16`
- Install TimescaleDB extension

**3. Проверить установку:**

```powershell
# Подключиться к PostgreSQL
psql -U postgres

# В psql консоли:
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

# Должно вывести: CREATE EXTENSION
\dx timescaledb

# Выйти
\q
```

---

## 📥 ШАГ 3: Создание базы данных

```powershell
# 1. Создать базу данных
createdb -U postgres bybit_strategy_tester

# 2. Подключиться
psql -U postgres -d bybit_strategy_tester

# 3. Установить TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

# 4. Проверить
\dx

# 5. Выйти
\q
```

---

## 📥 ШАГ 4: Переустановка Python пакетов

```powershell
# 1. Перейти в backend
cd D:\bybit_strategy_tester_v2\backend

# 2. Активировать venv
.\venv\Scripts\Activate.ps1

# 3. Обновить pip
python -m pip install --upgrade pip

# 4. Установить все пакеты
pip install -r requirements.txt

# Если ошибка с psycopg2-binary:
# Убедитесь что PostgreSQL/bin в PATH!
```

**Ожидаемый результат:**

```
Successfully installed:
- fastapi-0.109.0
- uvicorn-0.27.0
- sqlalchemy-2.0.25
- alembic-1.13.0
- psycopg2-binary-2.9.9  <- Должен установиться!
- redis-5.0.1
- celery-5.3.4
- pandas-2.1.4
- numpy-1.26.2
- pybit-5.7.0
- python-jose-3.3.0
- python-dotenv-1.0.0
- loguru-0.7.2
- pytest-7.4.3
- pytest-asyncio-0.21.1
```

---

## 📥 ШАГ 5: Установка Redis (ОПЦИОНАЛЬНО)

### Windows:

**1. Download installer:**

```
https://github.com/tporadowski/redis/releases
```

- Выбрать: Redis-x64-5.0.14.1.msi
- Размер: ~5 MB

**2. Запустить installer:**

- Install as Windows Service: ✅ Yes
- Port: **6379** (default)
- Max Memory: 100 MB (для development)

**3. Проверить установку:**

```powershell
# Проверить сервис
Get-Service Redis

# Должно показать: Running

# Проверить подключение
redis-cli ping
# Должно вывести: PONG
```

---

## ✅ ПРОВЕРКА ГОТОВНОСТИ

### После установки всех компонентов:

```powershell
# 1. Проверка PostgreSQL
psql --version
psql -U postgres -d bybit_strategy_tester -c "SELECT version();"

# 2. Проверка TimescaleDB
psql -U postgres -d bybit_strategy_tester -c "\dx timescaledb"

# 3. Проверка Python пакетов
cd D:\bybit_strategy_tester_v2\backend
.\venv\Scripts\Activate.ps1
pip list | findstr "fastapi uvicorn sqlalchemy psycopg2 pandas"

# 4. Проверка Redis (если установлен)
redis-cli ping
```

**Все команды должны работать без ошибок!** ✅

---

## 🚀 ЗАПУСК ПРОЕКТА

### После установки всех компонентов:

````powershell
# Terminal 1: Backend API
cd D:\bybit_strategy_tester_v2\backend
.\venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload --port 8000

# Terminal 2: Redis (если не как сервис)
redis-server

# Terminal 3: Frontend
cd D:\bybit_strategy_tester_v2\frontend
npm run dev

# Terminal 4: Electron (после настройки frontend)
cd D:\bybit_strategy_tester_v2\frontend
npm run electron:dev

---

## 🛰️ Запуск WebSocket publisher (ws_publisher)

Этот воркер подключается к Bybit WebSocket и публикует данные в Redis каналы.

```powershell
# Включить виртуальное окружение
cd D:\bybit_strategy_tester_v2\backend
.\venv\Scripts\Activate.ps1

# Запустить воркер
python -m backend.workers.ws_publisher
````

Проверка (в другом терминале):

```powershell
# Подписаться на Redis канал (пример)
redis-cli SUBSCRIBE "candles:BTCUSDT:1"

# Если приходят сообщения, то pipeline работает.
```

Советы:

- Убедитесь, что `BYBIT_API_KEY` и `BYBIT_API_SECRET` указаны в `.env` при подключении к реальному Bybit.
- Для теста можно использовать `BYBIT_TESTNET=True` в `.env`.

````

---

## 🔧 СОЗДАНИЕ .env ФАЙЛА

```powershell
# 1. Скопировать шаблон
cd D:\bybit_strategy_tester_v2
Copy-Item .env.example .env

# 2. Отредактировать .env
code .env
````

**Содержимое `.env`:**

```env
# Database (замени password на свой)
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/bybit_strategy_tester

# Redis
REDIS_URL=redis://localhost:6379/0

# API
API_PORT=8000

# Bybit API (опционально для live data)
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here
```

---

## 🐛 TROUBLESHOOTING

### Проблема: psycopg2-binary не устанавливается

**Решение:**

```powershell
# 1. Проверить что PostgreSQL/bin в PATH
$env:Path

# Если нет, добавить:
$env:Path += ";C:\Program Files\PostgreSQL\16\bin"

# 2. Переустановить
pip uninstall psycopg2-binary
pip install psycopg2-binary==2.9.9
```

### Проблема: PostgreSQL не запускается

**Решение:**

```powershell
# Проверить сервис
Get-Service postgresql*

# Запустить вручную
Start-Service postgresql-x64-16

# Или через pgAdmin
```

### Проблема: Redis не подключается

**Решение:**

```powershell
# Проверить сервис
Get-Service Redis

# Запустить
Start-Service Redis

# Или запустить вручную
redis-server
```

---

## ⏱️ ВРЕМЯ УСТАНОВКИ

| Компонент           | Время         |
| ------------------- | ------------- |
| PostgreSQL          | 10 минут      |
| TimescaleDB         | 5 минут       |
| База данных         | 2 минуты      |
| Python пакеты       | 5 минут       |
| Redis (опционально) | 5 минут       |
| **ИТОГО**           | **~30 минут** |

---

## 📋 CHECKLIST

- [ ] PostgreSQL 16 установлен
- [ ] TimescaleDB extension установлен
- [ ] База данных `bybit_strategy_tester` создана
- [ ] PostgreSQL/bin добавлен в PATH
- [ ] Python пакеты установлены в venv (проверить `pip list`)
- [ ] psycopg2-binary установлен успешно
- [ ] Redis установлен (опционально)
- [ ] .env файл создан и настроен
- [ ] Все проверки пройдены (`psql --version`, `pip list`, `redis-cli ping`)

---

## ✅ РЕЗУЛЬТАТ

**После выполнения всех шагов:**

1. ✅ PostgreSQL работает
2. ✅ TimescaleDB активирован
3. ✅ Python пакеты установлены в venv
4. ✅ Redis работает (опционально)
5. ✅ Проект готов к полноценной разработке

**Теперь можно:**

- Запустить Backend API (`uvicorn backend.main:app --reload`)
- Создать database schema из TECHNICAL_SPECIFICATION.md
- Запустить Frontend (`npm run dev`)
- Следовать IMPLEMENTATION_ROADMAP.md

---

## 🎉 ГОТОВО!

**Переходи к:** `docs/IMPLEMENTATION_ROADMAP.md` → ЭТАП 1: Backend Foundation

**Удачи в разработке!** 🚀
