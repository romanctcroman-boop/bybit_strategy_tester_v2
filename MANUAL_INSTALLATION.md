# 🔧 РУЧНАЯ УСТАНОВКА PostgreSQL + Redis

## Вариант 1: Автоматическая установка (Chocolatey) ⚡

### Шаг 1: Откройте PowerShell от имени администратора
1. Нажмите `Win + X`
2. Выберите **"Windows PowerShell (администратор)"**
3. Разрешите запуск

### Шаг 2: Выполните установщик
```powershell
cd D:\bybit_strategy_tester_v2
.\install_db_easy.ps1
```

**Что делает скрипт:**
- ✅ Устанавливает Chocolatey (если нужно)
- ✅ Устанавливает PostgreSQL 16 через `choco install postgresql16`
- ✅ Устанавливает Redis через `choco install redis-64`
- ✅ Устанавливает Python драйверы (psycopg2-binary, asyncpg)
- ✅ Создает базу данных `bybit_strategy_tester`
- ✅ Применяет схему из `database_schema.sql`

**Время выполнения:** ~10-15 минут

---

## Вариант 2: Ручная установка (если автоматика не работает) 🛠️

### PostgreSQL 16

#### Способ A: Через официальный установщик

1. **Скачайте установщик:**
   - URL: https://www.enterprisedb.com/downloads/postgres-postgresql-downloads
   - Файл: `postgresql-16.6-1-windows-x64.exe` (~300 MB)

2. **Запустите установщик:**
   - Двойной клик по скачанному файлу
   - Нажмите "Next"

3. **Выберите компоненты:**
   - ✅ PostgreSQL Server
   - ✅ pgAdmin 4
   - ✅ Command Line Tools
   - ❌ Stack Builder (не обязательно)

4. **Укажите директорию:**
   - По умолчанию: `C:\Program Files\PostgreSQL\16`
   - Нажмите "Next"

5. **Укажите директорию для данных:**
   - По умолчанию: `C:\Program Files\PostgreSQL\16\data`
   - Нажмите "Next"

6. **Установите пароль:**
   - Пароль для пользователя `postgres`: **`postgres123`**
   - ⚠️ **ЗАПОМНИТЕ ЭТОТ ПАРОЛЬ!**
   - Нажмите "Next"

7. **Укажите порт:**
   - По умолчанию: `5432`
   - Нажмите "Next"

8. **Выберите локаль:**
   - `Russian, Russia` или `Default locale`
   - Нажмите "Next"

9. **Начните установку:**
   - Нажмите "Next" → "Install"
   - Подождите ~5-10 минут

10. **Завершите установку:**
    - Снимите галку "Launch Stack Builder"
    - Нажмите "Finish"

#### Способ B: Через Chocolatey (команда)

```powershell
# От имени администратора
choco install postgresql16 --params '/Password:postgres123' -y
```

### Redis

#### Способ A: Через GitHub релизы

1. **Скачайте установщик:**
   - URL: https://github.com/tporadowski/redis/releases
   - Файл: `Redis-x64-5.0.14.1.msi` (~5 MB)

2. **Запустите установщик:**
   - Двойной клик по скачанному .msi файлу
   - Нажмите "Next"

3. **Прочитайте лицензию:**
   - Согласитесь с лицензией
   - Нажмите "Next"

4. **Выберите директорию:**
   - По умолчанию: `C:\Program Files\Redis`
   - Нажмите "Next"

5. **Настройте порт:**
   - Порт: `6379`
   - ✅ "Add the Redis installation folder to the PATH"
   - ✅ "Install the Redis service"
   - Нажмите "Next"

6. **Начните установку:**
   - Нажмите "Install"
   - Подождите ~1-2 минуты

7. **Завершите:**
   - Нажмите "Finish"

#### Способ B: Через Chocolatey (команда)

```powershell
# От имени администратора
choco install redis-64 -y
```

### Проверка установки

После установки **закройте и откройте PowerShell заново**, затем выполните:

```powershell
# PostgreSQL
psql --version
# Ожидаемый вывод: psql (PostgreSQL) 16.6

Get-Service postgresql*
# Ожидаемый вывод: postgresql-x64-16 | Running

# Redis
redis-server --version
# Ожидаемый вывод: Redis server v=5.0.14.1

Get-Service Redis
# Ожидаемый вывод: Redis | Running
```

---

## Настройка после установки

### 1. Создайте базу данных

```powershell
# Установите переменную окружения для пароля
$env:PGPASSWORD = "postgres123"

# Создайте БД
psql -U postgres -c "CREATE DATABASE bybit_strategy_tester ENCODING 'UTF8';"

# Проверьте
psql -U postgres -l

# Удалите переменную
Remove-Item Env:\PGPASSWORD
```

### 2. Примените схему базы данных

```powershell
cd D:\bybit_strategy_tester_v2

# Установите пароль
$env:PGPASSWORD = "postgres123"

# Выполните SQL скрипт
psql -U postgres -d bybit_strategy_tester -f database_schema.sql

# Удалите пароль
Remove-Item Env:\PGPASSWORD
```

**Что создается:**
- 6 таблиц (users, strategies, backtests, trades, optimizations, market_data)
- 2 TimescaleDB hypertables (если TimescaleDB установлен)
- Indexes, triggers, views
- Тестовый пользователь admin/changeme
- Пример стратегии

### 3. Установите Python драйверы

```powershell
cd D:\bybit_strategy_tester_v2\backend
.\venv\Scripts\Activate.ps1

# PostgreSQL драйверы
pip install psycopg2-binary asyncpg

# Проверка
pip list | Select-String "psycopg2|asyncpg"
```

### 4. Измените пароль PostgreSQL (ВАЖНО!)

```powershell
# Подключитесь к PostgreSQL
psql -U postgres
```

```sql
-- Измените пароль (текущий: postgres123)
ALTER USER postgres WITH PASSWORD 'ваш_безопасный_пароль';

-- Проверьте подключение с новым паролем
\conninfo

-- Выход
\q
```

### 5. Обновите .env файл

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

### 6. Проверьте подключение из Python

```powershell
cd D:\bybit_strategy_tester_v2\backend
.\venv\Scripts\Activate.ps1
python
```

```python
# PostgreSQL
import psycopg2
conn = psycopg2.connect(
    "postgresql://postgres:ваш_пароль@localhost:5432/bybit_strategy_tester"
)
print("✓ PostgreSQL работает")
conn.close()

# Redis
import redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)
print(f"✓ Redis работает: {r.ping()}")
```

---

## Устранение проблем

### PostgreSQL не запускается

1. **Проверьте службу:**
   ```powershell
   Get-Service postgresql*
   ```

2. **Запустите вручную:**
   ```powershell
   Start-Service postgresql-x64-16
   ```

3. **Проверьте логи:**
   ```powershell
   Get-Content "C:\Program Files\PostgreSQL\16\data\log\*.log" -Tail 50
   ```

4. **Проверьте порт:**
   ```powershell
   netstat -an | Select-String ":5432"
   ```

### Redis не запускается

1. **Проверьте службу:**
   ```powershell
   Get-Service Redis
   ```

2. **Запустите вручную:**
   ```powershell
   Start-Service Redis
   ```

3. **Запустите напрямую:**
   ```powershell
   redis-server
   ```

### PostgreSQL не в PATH

1. **Добавьте вручную:**
   - Откройте "Система" → "Дополнительные параметры системы"
   - "Переменные среды" → "Path" → "Изменить"
   - Добавьте: `C:\Program Files\PostgreSQL\16\bin`
   - Нажмите OK

2. **Или через PowerShell (от администратора):**
   ```powershell
   $pgPath = "C:\Program Files\PostgreSQL\16\bin"
   $currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
   [Environment]::SetEnvironmentVariable("Path", "$currentPath;$pgPath", "Machine")
   ```

3. **Перезапустите PowerShell**

### Redis не в PATH

1. **Добавьте вручную:**
   - "Переменные среды" → "Path" → "Изменить"
   - Добавьте: `C:\Program Files\Redis`

2. **Или через PowerShell:**
   ```powershell
   $redisPath = "C:\Program Files\Redis"
   $currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
   [Environment]::SetEnvironmentVariable("Path", "$currentPath;$redisPath", "Machine")
   ```

### База данных не создается

1. **Проверьте пароль:**
   ```powershell
   psql -U postgres
   # Введите пароль: postgres123
   ```

2. **Создайте БД вручную:**
   ```sql
   CREATE DATABASE bybit_strategy_tester ENCODING 'UTF8';
   \l
   \q
   ```

3. **Примените схему:**
   ```powershell
   psql -U postgres -d bybit_strategy_tester -f D:\bybit_strategy_tester_v2\database_schema.sql
   ```

---

## Полезные команды

### PostgreSQL

```powershell
# Список баз данных
psql -U postgres -l

# Подключение к БД
psql -U postgres -d bybit_strategy_tester

# Выполнить SQL файл
psql -U postgres -d bybit_strategy_tester -f schema.sql

# Проверить версию
psql --version

# Статус службы
Get-Service postgresql*

# Запуск/остановка
Start-Service postgresql-x64-16
Stop-Service postgresql-x64-16
Restart-Service postgresql-x64-16
```

### Redis

```powershell
# Проверить версию
redis-server --version

# Проверить подключение
redis-cli ping

# Информация о сервере
redis-cli info

# Мониторинг команд
redis-cli monitor

# Статус службы
Get-Service Redis

# Запуск/остановка
Start-Service Redis
Stop-Service Redis
Restart-Service Redis
```

---

## После успешной установки

### Чеклист ✅

- [ ] PostgreSQL установлен (`psql --version`)
- [ ] Служба PostgreSQL запущена (`Get-Service postgresql*`)
- [ ] Redis установлен (`redis-server --version`)
- [ ] Служба Redis запущена (`Get-Service Redis`)
- [ ] База данных создана (`psql -U postgres -l`)
- [ ] Схема применена (проверьте таблицы в psql)
- [ ] Python драйверы установлены (`pip list | Select-String psycopg2`)
- [ ] Пароль изменен (с postgres123 на свой)
- [ ] .env файл обновлен
- [ ] Подключение проверено (Python тест)

### Следующие шаги

1. **Создайте backend/main.py** (скопируйте из TECHNICAL_SPECIFICATION.md)
2. **Запустите backend:**
   ```powershell
   cd D:\bybit_strategy_tester_v2\backend
   .\venv\Scripts\Activate.ps1
   uvicorn main:app --reload
   ```
3. **Проверьте API:** http://localhost:8000/docs
4. **Начните разработку** по плану из IMPLEMENTATION_ROADMAP.md

---

## Помощь

### Если ничего не работает:

1. **Перезагрузите компьютер** (обновит PATH и службы)
2. **Проверьте антивирус** (может блокировать установку)
3. **Проверьте брандмауэр** (порты 5432 и 6379)
4. **Установите вручную** через GUI установщики
5. **Напишите мне** - опишу альтернативные варианты

### Контакты для помощи:

- **Документация PostgreSQL:** https://www.postgresql.org/docs/16/
- **Документация Redis:** https://redis.io/docs/
- **Chocolatey:** https://community.chocolatey.org/

---

**Создано:** 2025-01-22  
**Версия:** 1.0  
**Проект:** Bybit Strategy Tester v2.0
