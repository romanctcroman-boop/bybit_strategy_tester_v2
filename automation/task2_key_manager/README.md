# 🔐 Task 2: Key Manager - Безопасное управление API ключами

**Статус**: ✅ Готово к использованию  
**Время внедрения**: 2-3 часа  
**Приоритет**: Высокий (критично для безопасности)

---

## 📋 Описание

KeyManager - это Singleton класс для безопасного управления API ключами в MCP сервере. Обеспечивает:

- ✅ Шифрование API ключей с использованием Fernet (AES)
- ✅ Безопасное хранение в `encrypted_secrets.json`
- ✅ Автоматическую расшифровку при старте MCP сервера
- ✅ Доступ к ключам без логирования значений
- ✅ Декоратор `@with_keys` для защиты MCP tools

---

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
pip install cryptography python-dotenv
```

### 2. Создание ENCRYPTION_KEY

```bash
# Сгенерируйте случайный ключ (минимум 32 символа)
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Добавьте в `.env`:
```bash
ENCRYPTION_KEY=ваш_сгенерированный_ключ
```

### 3. Шифрование секретов

```bash
cd automation/task2_key_manager
python encrypt_secrets.py
```

Следуйте инструкциям:
1. Введите ENCRYPTION_KEY (будет скрыт)
2. Добавьте API ключи (DEEPSEEK_API_KEY, PERPLEXITY_API_KEY и т.д.)
3. Файл `encrypted_secrets.json` будет создан

### 4. Добавьте в .gitignore

```gitignore
encrypted_secrets.json
.env
*.log
```

### 5. Интеграция с MCP сервером

См. раздел "Интеграция" ниже.

---

## 📁 Структура файлов

```
automation/task2_key_manager/
├── key_manager.py          # Основной класс KeyManager
├── encrypt_secrets.py      # Утилита для шифрования
├── test_key_manager.py     # Тесты
└── README.md               # Эта документация

# Создаются после использования:
encrypted_secrets.json      # Зашифрованные ключи (НЕ КОММИТИТЬ!)
.env                        # ENCRYPTION_KEY (НЕ КОММИТИТЬ!)
```

---

## 🔧 Использование

### Основное использование

```python
from key_manager import KeyManager

# Получение экземпляра (Singleton)
key_manager = KeyManager()

# Инициализация шифрования
encryption_key = os.getenv("ENCRYPTION_KEY")
key_manager.initialize_encryption(encryption_key)

# Загрузка ключей
key_manager.load_keys("encrypted_secrets.json")

# Получение ключа
api_key = key_manager.get_key("DEEPSEEK_API_KEY")

# Проверка наличия ключей
if key_manager.has_keys():
    print("Ключи загружены")

# Список доступных ключей (без значений!)
keys = key_manager.get_available_keys()
print(f"Доступные ключи: {keys}")
```

### Декоратор @with_keys

```python
from key_manager import with_keys, KeyManager

@with_keys
async def my_protected_function():
    key_manager = KeyManager()
    api_key = key_manager.get_key("DEEPSEEK_API_KEY")
    # ... использование ключа
```

Декоратор автоматически проверит наличие загруженных ключей и выбросит исключение, если их нет.

---

## 🔗 Интеграция с MCP сервером

### Вариант 1: Callback при startup

```python
# mcp-server/server.py
import os
import sys
from pathlib import Path

# Добавляем путь к key_manager
sys.path.insert(0, str(Path(__file__).parent.parent / "automation" / "task2_key_manager"))

from key_manager import KeyManager, with_keys
from mcp import Server

server = Server("bybit-strategy-tester")
key_manager = KeyManager()

@server.callback("startup")
async def on_startup():
    """Загрузка ключей при старте сервера"""
    try:
        # Получение ключа шифрования из .env
        encryption_key = os.getenv("ENCRYPTION_KEY")
        if not encryption_key:
            print("❌ ENCRYPTION_KEY не найден в .env")
            return False
        
        # Инициализация
        if not key_manager.initialize_encryption(encryption_key):
            print("❌ Ошибка инициализации шифрования")
            return False
        
        # Загрузка ключей
        secrets_file = os.getenv("SECRETS_FILE", "encrypted_secrets.json")
        if key_manager.load_keys(secrets_file):
            print(f"✅ Загружено ключей: {len(key_manager.get_available_keys())}")
            
            # Опционально: установка в environment
            for key_name in key_manager.get_available_keys():
                key_value = key_manager.get_key(key_name)
                if key_value:
                    os.environ[key_name] = key_value
            
            return True
        else:
            print("❌ Ошибка загрузки ключей")
            return False
            
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        return False

# Используйте в MCP tools
@server.tool()
@with_keys
async def deepseek_query(prompt: str) -> str:
    """Запрос к DeepSeek API с защищенным ключом"""
    api_key = key_manager.get_key("DEEPSEEK_API_KEY")
    # ... использование ключа
```

### Вариант 2: Ручная инициализация

```python
# mcp-server/server.py
import os
from key_manager import KeyManager

def initialize_keys():
    """Ручная инициализация перед запуском сервера"""
    key_manager = KeyManager()
    
    encryption_key = os.getenv("ENCRYPTION_KEY")
    if key_manager.initialize_encryption(encryption_key):
        if key_manager.load_keys():
            print("✅ Ключи загружены")
            return True
    
    print("❌ Ошибка загрузки ключей")
    return False

if __name__ == "__main__":
    if not initialize_keys():
        sys.exit(1)
    
    # Запуск сервера
    asyncio.run(main())
```

---

## 🧪 Тестирование

### Запуск тестов

```bash
# С pytest
cd automation/task2_key_manager
pytest test_key_manager.py -v

# Или вручную
python test_key_manager.py
```

### Ожидаемый вывод

```
================================================================================
🧪 ЗАПУСК ТЕСТОВ KEY_MANAGER
================================================================================

✅ Singleton pattern работает
✅ Шифрование и расшифровка работают корректно
✅ Обработка несуществующих ключей работает
✅ has_keys() работает корректно
✅ Декоратор @with_keys работает корректно
✅ Проверка инициализации работает

================================================================================
✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!
================================================================================
```

---

## 🔒 Безопасность

### ✅ Что БЕЗОПАСНО:

- ✅ Ключи шифруются с использованием Fernet (AES-128)
- ✅ Используется PBKDF2 для деривации ключа
- ✅ Значения ключей НЕ логируются
- ✅ Файл `encrypted_secrets.json` в .gitignore
- ✅ ENCRYPTION_KEY в .env (НЕ в коде!)

### ⚠️ Важные правила:

1. **НИКОГДА** не коммитьте `encrypted_secrets.json` в git
2. **НИКОГДА** не коммитьте `.env` с ENCRYPTION_KEY
3. Используйте **разные** ENCRYPTION_KEY для dev/staging/production
4. Храните ENCRYPTION_KEY в безопасном месте (password manager)
5. Регулярно **ротируйте** ENCRYPTION_KEY и API ключи

### 🔄 Ротация ключей:

```bash
# 1. Создайте новый ENCRYPTION_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 2. Обновите .env
# ENCRYPTION_KEY=новый_ключ

# 3. Перешифруйте секреты
python encrypt_secrets.py

# 4. Удалите старый encrypted_secrets.json
```

---

## 📊 Трудозатраты

### Разработка (ГОТОВО): 4 часа
- ✅ Проектирование: 0.5 часа
- ✅ Разработка KeyManager: 1.5 часа
- ✅ Утилита шифрования: 0.5 часа
- ✅ Тесты: 1 час
- ✅ Документация: 0.5 часа

### Внедрение (TODO): 2-3 часа
- [ ] Установка зависимостей: 15 минут
- [ ] Генерация ENCRYPTION_KEY: 5 минут
- [ ] Шифрование текущих ключей: 15 минут
- [ ] Интеграция с MCP сервером: 1 час
- [ ] Тестирование интеграции: 1 час
- [ ] Обновление документации: 30 минут

**ИТОГО: 6-7 часов (разработка + внедрение)**

---

## 🐛 Troubleshooting

### Проблема: "Шифрование не инициализировано"

**Решение**: Убедитесь, что вы вызвали `initialize_encryption()` перед `load_keys()`:

```python
key_manager.initialize_encryption(encryption_key)
key_manager.load_keys()
```

### Проблема: "Файл секретов не найден"

**Решение**: Запустите `encrypt_secrets.py` для создания файла:

```bash
python encrypt_secrets.py
```

### Проблема: "Ошибка расшифровки ключа"

**Возможные причины**:
1. Неправильный ENCRYPTION_KEY
2. Файл поврежден
3. Файл создан с другим ключом

**Решение**: Перешифруйте ключи с правильным ENCRYPTION_KEY.

### Проблема: Ключи не доступны в MCP tools

**Решение**: Проверьте, что callback `startup` вызывается:

```python
@server.callback("startup")
async def on_startup():
    # ... инициализация KeyManager
```

---

## 📝 Примеры использования

### Пример 1: Простое использование

```python
from key_manager import KeyManager
import os

key_manager = KeyManager()
key_manager.initialize_encryption(os.getenv("ENCRYPTION_KEY"))
key_manager.load_keys()

deepseek_key = key_manager.get_key("DEEPSEEK_API_KEY")
print(f"Ключ загружен: {deepseek_key[:10]}...")  # Показываем только первые 10 символов
```

### Пример 2: С проверкой ошибок

```python
from key_manager import KeyManager
import os
import sys

def load_api_keys():
    key_manager = KeyManager()
    
    encryption_key = os.getenv("ENCRYPTION_KEY")
    if not encryption_key:
        print("❌ ENCRYPTION_KEY не найден в .env")
        return False
    
    if not key_manager.initialize_encryption(encryption_key):
        print("❌ Ошибка инициализации")
        return False
    
    if not key_manager.load_keys():
        print("❌ Ошибка загрузки ключей")
        return False
    
    print(f"✅ Загружено ключей: {len(key_manager.get_available_keys())}")
    return True

if __name__ == "__main__":
    if not load_api_keys():
        sys.exit(1)
```

### Пример 3: В асинхронной функции

```python
from key_manager import KeyManager, with_keys
import aiohttp

@with_keys
async def query_api(prompt: str):
    key_manager = KeyManager()
    api_key = key_manager.get_key("DEEPSEEK_API_KEY")
    
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {api_key}"}
        async with session.post(url, json={"prompt": prompt}, headers=headers) as response:
            return await response.json()
```

---

## 🎯 Следующие шаги

### Сейчас:
1. ✅ Код KeyManager готов
2. ✅ Утилита шифрования готова
3. ✅ Тесты написаны
4. ✅ Документация готова

### TODO:
1. [ ] Установить cryptography: `pip install cryptography`
2. [ ] Сгенерировать ENCRYPTION_KEY
3. [ ] Запустить `encrypt_secrets.py`
4. [ ] Интегрировать в mcp-server/server.py
5. [ ] Протестировать загрузку ключей
6. [ ] Обновить документацию MCP сервера

---

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи: `test_watcher.log`, `audit_agent.log`
2. Запустите тесты: `python test_key_manager.py`
3. Проверьте, что ENCRYPTION_KEY установлен в .env
4. Убедитесь, что encrypted_secrets.json существует

---

**Создано**: 7 ноября 2025  
**Статус**: ✅ Готово к внедрению  
**Версия**: 1.0.0
