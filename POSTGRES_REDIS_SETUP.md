# PostgreSQL + TimescaleDB + Redis - Автоматическая Установка

## 🚀 Быстрый Старт

Запущен автоматизированный установщик, который установит:

### Что устанавливается:

1. **PostgreSQL 16** (~240 MB)
   - Версия: 16.6
   - Порт: 5432
   - Пароль по умолчанию: `postgres123` ⚠️ **ИЗМЕНИТЕ ПОСЛЕ УСТАНОВКИ!**
   - Путь: `C:\Program Files\PostgreSQL\16`
   - Служба Windows: `postgresql-x64-16`

2. **TimescaleDB** (~20 MB)
   - Версия: 2.18.0
   - Расширение для time-series данных
   - Автоматически добавляется в `shared_preload_libraries`
   - Требует перезапуск PostgreSQL

3. **Redis 7** (~5 MB)
   - Версия: 5.0.14.1 (совместимая Windows версия)
   - Порт: 6379
   - Путь: `C:\Program Files\Redis`
   - Служба Windows: `Redis`

4. **Python Драйверы**
   - `psycopg2-binary` - синхронный драйвер PostgreSQL
   - `asyncpg` - асинхронный драйвер PostgreSQL

5. **База Данных**
   - Имя: `bybit_strategy_tester`
   - Кодировка: UTF-8
   - TimescaleDB расширение включено

---

## 📋 Процесс Установки

Установщик выполняет следующие шаги:

### Шаг 1/4: PostgreSQL 16
```
[1/3] Загрузка PostgreSQL 16 (~240 MB)
[2/3] Тихая установка (5-10 минут)
[3/3] Добавление в системный PATH
[ПРОВЕРКА] Проверка версии и службы
```

### Шаг 2/4: TimescaleDB
```
[1/3] Загрузка TimescaleDB (~20 MB)
[2/3] Распаковка и копирование файлов
[3/3] Настройка postgresql.conf
[ПРОВЕРКА] Перезапуск PostgreSQL
```

### Шаг 3/4: Redis 7
```
[1/3] Загрузка Redis (~5 MB)
[2/3] Установка через MSI (2-3 минуты)
[3/3] Запуск службы Windows
[ПРОВЕРКА] redis-cli ping
```

### Шаг 4/4: Python Драйверы
```
[1/2] Установка psycopg2-binary
[2/2] Установка asyncpg
[ПРОВЕРКА] pip list
```

### Бонус: Создание БД
```
[1/2] CREATE DATABASE bybit_strategy_tester
[2/2] CREATE EXTENSION timescaledb
[INFO] Строка подключения
```

---

## ✅ Финальная Проверка

Установщик автоматически проверяет:

- ✓ PostgreSQL доступен (`psql --version`)
- ✓ TimescaleDB расширение работает
- ✓ Redis отвечает (`redis-cli ping → PONG`)
- ✓ Python драйверы установлены в venv
- ✓ База данных создана

**Ожидаемый результат:** 100% готовность (5/5 компонентов)

---

## 🔧 После Установки

### 1. Измените пароль PostgreSQL

```powershell
psql -U postgres
```

```sql
ALTER USER postgres WITH PASSWORD 'ваш_новый_безопасный_пароль';
\q
```

### 2. Обновите `.env` файл

Откройте `D:\bybit_strategy_tester_v2\.env` и измените:

```env
# Database
DATABASE_URL=postgresql://postgres:ваш_новый_пароль@localhost:5432/bybit_strategy_tester

# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

### 3. Создайте схему базы данных

Скопируйте SQL код из `docs/TECHNICAL_SPECIFICATION.md` (раздел 2.3 - Database Schema):

```powershell
# Создайте файл schema.sql с SQL из документации
psql -U postgres -d bybit_strategy_tester -f schema.sql
```

Или выполните напрямую:

```powershell
psql -U postgres -d bybit_strategy_tester
```

```sql
-- Включить TimescaleDB (если еще не включено)
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Скопируйте остальные таблицы из TECHNICAL_SPECIFICATION.md
-- Раздел 2.3: Database Schema (~800 строк SQL)
```

### 4. Проверьте подключение из Python

```powershell
cd D:\bybit_strategy_tester_v2\backend
.\venv\Scripts\Activate.ps1
python
```

```python
# Проверка PostgreSQL
import psycopg2
conn = psycopg2.connect("postgresql://postgres:ваш_пароль@localhost:5432/bybit_strategy_tester")
print("PostgreSQL: OK")
conn.close()

# Проверка asyncpg
import asyncio
import asyncpg

async def test():
    conn = await asyncpg.connect("postgresql://postgres:ваш_пароль@localhost:5432/bybit_strategy_tester")
    print("asyncpg: OK")
    await conn.close()

asyncio.run(test())

# Проверка Redis
import redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)
r.ping()  # Должно вернуть True
print("Redis: OK")
```

---

## 🛠️ Управление Службами

### PostgreSQL

```powershell
# Статус
Get-Service postgresql-x64-16

# Запуск
Start-Service postgresql-x64-16

# Остановка
Stop-Service postgresql-x64-16

# Перезапуск
Restart-Service postgresql-x64-16
```

### Redis

```powershell
# Статус
Get-Service Redis

# Запуск
Start-Service Redis

# Остановка
Stop-Service Redis

# Перезапуск
Restart-Service Redis
```

---

## 📊 Проверка Работы

### PostgreSQL

```powershell
# Версия
psql --version

# Список баз данных
psql -U postgres -l

# Подключение к БД
psql -U postgres -d bybit_strategy_tester

# Проверка TimescaleDB
psql -U postgres -d bybit_strategy_tester -c "SELECT extversion FROM pg_extension WHERE extname='timescaledb';"
```

### Redis

```powershell
# Версия
redis-server --version

# Проверка подключения
redis-cli ping  # Должно вернуть PONG

# Информация
redis-cli info

# Мониторинг
redis-cli monitor
```

---

## ❌ Устранение Проблем

### PostgreSQL не запускается

1. Проверьте логи:
   ```powershell
   Get-Content "C:\Program Files\PostgreSQL\16\data\log\*.log" -Tail 50
   ```

2. Проверьте порт 5432:
   ```powershell
   netstat -an | Select-String ":5432"
   ```

3. Переустановите службу:
   ```powershell
   Stop-Service postgresql-x64-16
   Start-Service postgresql-x64-16
   ```

### Redis не запускается

1. Проверьте порт 6379:
   ```powershell
   netstat -an | Select-String ":6379"
   ```

2. Проверьте службу:
   ```powershell
   Get-Service Redis | Format-List *
   ```

3. Запустите вручную:
   ```powershell
   redis-server
   ```

### TimescaleDB не работает

1. Проверьте `postgresql.conf`:
   ```powershell
   Get-Content "C:\Program Files\PostgreSQL\16\data\postgresql.conf" | Select-String "timescaledb"
   ```

2. Должна быть строка:
   ```
   shared_preload_libraries = 'timescaledb'
   ```

3. Перезапустите PostgreSQL:
   ```powershell
   Restart-Service postgresql-x64-16
   ```

### Python драйверы не работают

1. Убедитесь, что используете venv:
   ```powershell
   cd D:\bybit_strategy_tester_v2\backend
   .\venv\Scripts\Activate.ps1
   ```

2. Переустановите драйверы:
   ```powershell
   pip install --upgrade --force-reinstall psycopg2-binary asyncpg
   ```

3. Проверьте версии:
   ```powershell
   pip show psycopg2-binary asyncpg
   ```

---

## 🔗 Строки Подключения

### PostgreSQL

```
# Синхронный (SQLAlchemy, psycopg2)
postgresql://postgres:пароль@localhost:5432/bybit_strategy_tester

# Асинхронный (asyncpg)
postgresql://postgres:пароль@localhost:5432/bybit_strategy_tester

# С SSL (для продакшена)
postgresql://postgres:пароль@localhost:5432/bybit_strategy_tester?sslmode=require
```

### Redis

```
# Базовая
redis://localhost:6379/0

# С паролем (если настроили)
redis://:пароль@localhost:6379/0

# Для Celery broker
redis://localhost:6379/1

# Для Celery results
redis://localhost:6379/2
```

---

## 📁 Пути к Файлам

### PostgreSQL

```
Установка:       C:\Program Files\PostgreSQL\16
Исполняемые:     C:\Program Files\PostgreSQL\16\bin
Данные:          C:\Program Files\PostgreSQL\16\data
Конфигурация:    C:\Program Files\PostgreSQL\16\data\postgresql.conf
Логи:            C:\Program Files\PostgreSQL\16\data\log
```

### Redis

```
Установка:       C:\Program Files\Redis
Исполняемые:     C:\Program Files\Redis\redis-server.exe
Конфигурация:    C:\Program Files\Redis\redis.windows.conf
Логи:            C:\Program Files\Redis\Logs
```

---

## 🎯 Следующие Шаги

После успешной установки:

1. ✅ **Измените пароль PostgreSQL** (см. раздел "После Установки")
2. ✅ **Обновите `.env` файл** с новыми паролями
3. ✅ **Создайте схему БД** из `TECHNICAL_SPECIFICATION.md`
4. ✅ **Запустите backend** и проверьте подключение
5. ✅ **Начните разработку** по плану из `IMPLEMENTATION_ROADMAP.md`

---

## 📚 Документация

- [PostgreSQL 16 Documentation](https://www.postgresql.org/docs/16/)
- [TimescaleDB Documentation](https://docs.timescale.com/)
- [Redis Documentation](https://redis.io/docs/)
- [psycopg2 Documentation](https://www.psycopg.org/docs/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)

---

## ⏱️ Время Установки

- **PostgreSQL**: 5-10 минут
- **TimescaleDB**: 2-3 минуты
- **Redis**: 2-3 минуты
- **Python Драйверы**: 1 минута
- **База Данных**: 1 минута

**ИТОГО: ~15-20 минут**

---

## 🎉 Готовность

После установки всех компонентов:

```
✓ PostgreSQL 16        [OK]
✓ TimescaleDB          [OK]
✓ Redis 7              [OK]
✓ Python Drivers       [OK]
✓ Database Created     [OK]

ГОТОВНОСТЬ: 100% (5/5)

✓ ВСЕ КОМПОНЕНТЫ УСТАНОВЛЕНЫ И РАБОТАЮТ!
  Можно начинать разработку!
```

---

**Создано:** 2025-01-22  
**Автор:** GitHub Copilot  
**Проект:** Bybit Strategy Tester v2.0
