# 🔌 PostgreSQL Connection Setup - VS Code
## Пошаговая инструкция подключения

---

## 📋 Шаг 1: Проверка PostgreSQL Service

Перед подключением убедитесь что PostgreSQL запущен:

```powershell
# Проверить статус службы
Get-Service -Name "postgresql-x64-16"

# Если не запущен - запустить
Start-Service -Name "postgresql-x64-16"

# Проверить подключение через psql
psql -U postgres -c "SELECT version();"
```

**Ожидаемый результат:**
```
Status: Running
PostgreSQL 16.x on x86_64-pc-windows-msvc, compiled by Visual C++ build...
```

---

## 📋 Шаг 2: Открыть PostgreSQL Extension

1. Нажмите **Ctrl+Shift+P**
2. Введите: `PostgreSQL: New Connection`
3. Или кликните на иконку PostgreSQL в левой панели (иконка слона 🐘)

---

## 📋 Шаг 3: Настроить Connection

### Вариант A: Через UI (Рекомендуется)

1. **Нажмите "+" в панели PostgreSQL**
2. **Заполните параметры:**

```
Connection Name: Bybit Strategy Tester
Server name or IP: localhost
Database: bybit_strategy_tester
Port: 5432
Username: postgres
Password: postgres123
Save Password: ✅ Yes (рекомендую)
```

3. **Нажмите "Connect"**

### Вариант B: Connection String

Если extension попросит connection string, используйте:

```
postgresql://postgres:postgres123@localhost:5432/bybit_strategy_tester?sslmode=disable
```

---

## 📋 Шаг 4: Создать Database (если не существует)

Если база `bybit_strategy_tester` не создана:

1. Подключитесь к `postgres` (default database):
```
Connection Name: PostgreSQL Default
Database: postgres
```

2. Выполните SQL:
```sql
-- Создать базу данных
CREATE DATABASE bybit_strategy_tester
    WITH 
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.UTF-8'
    LC_CTYPE = 'en_US.UTF-8'
    TEMPLATE = template0;

-- Подключиться к новой БД
\c bybit_strategy_tester

-- Установить TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Проверить что установлено
SELECT * FROM pg_extension WHERE extname = 'timescaledb';
```

---

## 📋 Шаг 5: Выполнить Schema Setup

После успешного подключения, выполните `database_schema.sql`:

### Способ 1: Через VS Code UI

1. Откройте `database_schema.sql` в VS Code
2. Правой кнопкой → **"Run Query"**
3. Выберите connection: `Bybit Strategy Tester`

### Способ 2: Через Terminal

```powershell
# Перейти в папку проекта
cd D:\bybit_strategy_tester_v2

# Выполнить schema
psql -U postgres -d bybit_strategy_tester -f database_schema.sql
```

### Способ 3: Через PowerShell скрипт (Автоматизация)

Используйте готовый скрипт:
```powershell
.\setup_database.ps1
```

---

## 📋 Шаг 6: Проверка установки

Выполните проверочные запросы:

```sql
-- 1. Проверить TimescaleDB
SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';

-- 2. Список всех таблиц
SELECT tablename FROM pg_tables WHERE schemaname = 'public';

-- 3. Проверить hypertables (TimescaleDB)
SELECT * FROM timescaledb_information.hypertables;

-- 4. Посмотреть структуру таблицы strategies
\d strategies

-- 5. Вставить тестовую стратегию
INSERT INTO strategies (name, description, strategy_type, config) 
VALUES (
    'RSI Mean Reversion',
    'Simple RSI-based mean reversion strategy',
    'Indicator-Based',
    '{"rsi_period": 14, "oversold": 30, "overbought": 70}'::jsonb
)
RETURNING id, name;
```

**Ожидаемые результаты:**
```
timescaledb: 2.18.0
tables: users, strategies, backtest_runs, trades, daily_metrics, optimization_runs, walk_forward_results
hypertables: daily_metrics (partitioned by time)
strategies: Table exists with JSONB config column
INSERT: ID=1, name='RSI Mean Reversion'
```

---

## 🔑 Шаг 7: Настроить .env для Backend

Создайте/обновите файл `.env` в корне проекта:

```env
# PostgreSQL Connection
DATABASE_URL=postgresql://postgres:postgres123@localhost:5432/bybit_strategy_tester
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=bybit_strategy_tester
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123

# Redis Connection  
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# API Settings
API_HOST=127.0.0.1
API_PORT=8000
DEBUG=True

# Bybit API (for data loading)
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here
```

---

## 🎯 Шаг 8: Интегрировать с Backend

### A. Установить Python драйверы

```powershell
pip install psycopg2-binary asyncpg sqlalchemy[asyncio]
```

### B. Создать database module (уже есть)

Проверьте что существует:
- `backend/database/__init__.py`
- `backend/database/models.py` (может быть)
- `backend/database/crud.py` (может быть)

### C. Тестовое подключение

Создайте тестовый скрипт `test_db_connection.py`:

```python
import psycopg2
from psycopg2.extras import RealDictCursor

def test_connection():
    """Test PostgreSQL connection"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="bybit_strategy_tester",
            user="postgres",
            password="postgres123"
        )
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Test 1: Check TimescaleDB
        cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")
        version = cursor.fetchone()
        print(f"✅ TimescaleDB version: {version['extversion']}")
        
        # Test 2: List tables
        cursor.execute("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        """)
        tables = cursor.fetchall()
        print(f"✅ Tables found: {len(tables)}")
        for table in tables:
            print(f"   - {table['tablename']}")
        
        # Test 3: Count strategies
        cursor.execute("SELECT COUNT(*) as count FROM strategies")
        count = cursor.fetchone()
        print(f"✅ Strategies in DB: {count['count']}")
        
        cursor.close()
        conn.close()
        print("\n✅ Database connection successful!")
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    test_connection()
```

Запустите:
```powershell
python test_db_connection.py
```

---

## 🛠️ Troubleshooting

### Проблема 1: "Connection refused"
```powershell
# Проверить что служба запущена
Get-Service postgresql-x64-16

# Запустить службу
Start-Service postgresql-x64-16

# Проверить порт
netstat -an | findstr 5432
```

### Проблема 2: "Authentication failed"
```powershell
# Сбросить пароль postgres
# 1. Открыть pgAdmin
# 2. Или через psql с Windows аутентификацией
psql -U postgres

# 3. Изменить пароль
ALTER USER postgres PASSWORD 'postgres123';
```

### Проблема 3: "Database does not exist"
```powershell
# Создать БД через psql
psql -U postgres -c "CREATE DATABASE bybit_strategy_tester;"

# Или через скрипт
.\setup_database.ps1
```

### Проблема 4: VS Code не видит extension
```
1. Ctrl+Shift+X → Найти "PostgreSQL"
2. Проверить что установлен: ms-ossdata.vscode-pgsql
3. Reload Window (Ctrl+Shift+P → "Reload Window")
4. Открыть PostgreSQL панель (иконка в левой панели)
```

---

## 📊 PostgreSQL Extension Features

После успешного подключения вы сможете:

### 1. Schema Explorer
- Просмотр всех таблиц, колонок, типов
- Просмотр indexes, constraints, foreign keys
- Просмотр functions и procedures

### 2. Query Editor
- SQL autocomplete (IntelliSense)
- Syntax highlighting
- Execute queries (F5 или Ctrl+Shift+E)
- Multiple query execution

### 3. Results View
- Table view (сетка с данными)
- JSON view (для JSONB columns)
- Export to CSV/JSON
- Copy results

### 4. Query History
- История всех выполненных запросов
- Повторное выполнение из истории

### 5. Dashboards (если настроить)
- Performance metrics
- Table sizes
- Index usage statistics
- Query performance

---

## 🎯 Рекомендуемые SQL Queries

Сохраните эти запросы для быстрого доступа:

### Monitoring Queries

```sql
-- 1. Database size
SELECT 
    pg_size_pretty(pg_database_size('bybit_strategy_tester')) as size;

-- 2. Table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    pg_total_relation_size(schemaname||'.'||tablename) AS size_bytes
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY size_bytes DESC;

-- 3. Active connections
SELECT 
    datname,
    usename,
    application_name,
    client_addr,
    state,
    query
FROM pg_stat_activity
WHERE datname = 'bybit_strategy_tester';

-- 4. Recent backtest runs
SELECT 
    id,
    strategy_id,
    symbol,
    interval,
    final_capital,
    total_return_pct,
    win_rate,
    status,
    created_at
FROM backtest_runs
ORDER BY created_at DESC
LIMIT 10;

-- 5. Top performing strategies
SELECT 
    s.name,
    COUNT(br.id) as runs_count,
    AVG(br.total_return_pct) as avg_return,
    AVG(br.win_rate) as avg_win_rate,
    MAX(br.sharpe_ratio) as max_sharpe
FROM strategies s
LEFT JOIN backtest_runs br ON br.strategy_id = s.id
GROUP BY s.id, s.name
ORDER BY avg_return DESC;
```

---

## 📚 Дополнительные Ресурсы

- **VS Code PostgreSQL Docs**: https://github.com/Microsoft/vscode-pgsql
- **TimescaleDB Docs**: https://docs.timescale.com/
- **PostgreSQL 16 Docs**: https://www.postgresql.org/docs/16/
- **psycopg2 Tutorial**: https://www.psycopg.org/docs/

---

## ✅ Checklist

После выполнения всех шагов у вас должно быть:

- [x] PostgreSQL 16 запущен (служба Windows)
- [x] TimescaleDB extension установлено
- [x] База данных `bybit_strategy_tester` создана
- [x] VS Code PostgreSQL extension подключен
- [x] Schema из `database_schema.sql` применена
- [x] Все таблицы созданы (users, strategies, backtest_runs, trades, etc.)
- [x] Hypertable для daily_metrics настроена
- [x] `.env` файл с DATABASE_URL настроен
- [x] Python драйверы установлены
- [x] Тестовое подключение работает

---

**Следующие шаги:**
1. Интегрировать PostgreSQL в Backend API endpoints
2. Добавить CRUD операции для strategies
3. Сохранять результаты backtests в БД
4. Создать endpoints для history и analytics

**Готовы продолжить?** Выберите:
- A) Создать Backend endpoints для PostgreSQL
- B) Тестировать queries через VS Code
- C) Что-то другое
