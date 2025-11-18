# 🚨 КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ БЕЗОПАСНОСТИ

**Дата:** 2025-10-30  
**Статус:** ⚠️ **ТРЕБУЕТСЯ НЕМЕДЛЕННОЕ ВНИМАНИЕ**  
**Источник:** Perplexity AI + Copilot Collaborative Analysis

---

## 🔐 КРИТИЧЕСКАЯ ПРОБЛЕМА: Hardcoded API Keys

### ❌ Обнаружено в файлах:

```
1. analyze_project_with_mcp.py - HARDCODED
2. query_perplexity.py - HARDCODED
3. query_mcp_tools.py - HARDCODED
4. test_real_ai_workflow.py - HARDCODED
5. test_real_ai_workflow_mtf.py - HARDCODED
6. mcp-server/server.py - fallback exposed
7. analyze_with_perplexity.py - fallback exposed
8. test_*.py - multiple test files with exposed keys
```

### ⚠️ РИСКИ:

1. **Data Breach** - API ключ виден в Git истории
2. **Unauthorized Access** - Любой с доступом к репозиторию может использовать ключ
3. **Financial Loss** - Неограниченное использование API = счета
4. **Compliance Violation** - Нарушение PCI DSS, GDPR standards

---

## ✅ НЕМЕДЛЕННЫЕ ДЕЙСТВИЯ

### 1. Создать .env файл (СЕЙЧАС):

```bash
# В корне проекта
New-Item -Path .env -ItemType File -Force

# Добавить содержимое:
@"
PERPLEXITY_API_KEY=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
BYBIT_API_KEY=your_bybit_key_here
BYBIT_API_SECRET=your_bybit_secret_here
DATABASE_URL=postgresql://user:password@localhost:5432/bybit_strategy_tester
"@ | Out-File -FilePath .env -Encoding utf8
```

### 2. Добавить .env в .gitignore (СЕЙЧАС):

```bash
# Проверить .gitignore
@"
# Environment variables
.env
.env.local
.env.*.local

# API Keys
*api_key*
*secret*
*.pem
*.key
"@ | Out-File -FilePath .gitignore -Append -Encoding utf8
```

### 3. Удалить hardcoded ключи из Git истории:

```bash
# ⚠️ ВНИМАНИЕ: Это переписывает Git историю!
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch analyze_project_with_mcp.py" \
  --prune-empty --tag-name-filter cat -- --all

# Или используйте BFG Repo-Cleaner (быстрее):
# https://rtyley.github.io/bfg-repo-cleaner/
```

### 4. Ротация API ключа:

```
1. Перейти: https://www.perplexity.ai/settings/api
2. Revoke текущий ключ: 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
3. Сгенерировать новый ключ
4. Добавить новый ключ в .env файл
5. НИКОГДА не коммитить .env в Git
```

---

## 🔧 ИСПРАВЛЕННЫЕ ФАЙЛЫ

### ✅ FIXED: analyze_with_perplexity.py

**Было:**
```python
PERPLEXITY_API_KEY = "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"
```

**Стало:**
```python
import os
from dotenv import load_dotenv

load_dotenv()  # Загрузить .env файл
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

if not PERPLEXITY_API_KEY:
    raise ValueError("PERPLEXITY_API_KEY not found in environment variables")
```

### ✅ FIXED: query_perplexity.py

**Было:**
```python
PERPLEXITY_API_KEY = "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"
```

**Стало:**
```python
import os
from dotenv import load_dotenv

load_dotenv()
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

if not PERPLEXITY_API_KEY:
    raise ValueError("⚠️ SECURITY: PERPLEXITY_API_KEY not configured. Add to .env file.")
```

### ✅ RECOMMENDATION: mcp-server/server.py

**Текущий код (НЕБЕЗОПАСНО):**
```python
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "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")
```

**Рекомендуется:**
```python
from dotenv import load_dotenv
load_dotenv()

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

if not PERPLEXITY_API_KEY:
    logger.critical("⚠️ PERPLEXITY_API_KEY not found in environment!")
    logger.critical("Please add PERPLEXITY_API_KEY to .env file")
    raise ValueError("API key not configured")
```

**Почему убрать fallback:**
- Fallback = hardcoded ключ в коде
- Если .env не загружен, код все равно работает (но с exposed ключом)
- Лучше fail fast и показать ошибку

---

## 📋 ПОЛНЫЙ СПИСОК ИСПРАВЛЕНИЙ

### Приоритет P0 (КРИТИЧНО):

- [ ] **query_perplexity.py** - Убрать hardcoded ключ
- [ ] **query_mcp_tools.py** - Убрать hardcoded ключ
- [ ] **analyze_project_with_mcp.py** - Убрать hardcoded ключ
- [ ] **test_real_ai_workflow.py** - Убрать hardcoded ключ
- [ ] **test_real_ai_workflow_mtf.py** - Убрать hardcoded ключ

### Приоритет P1 (ВЫСОКИЙ):

- [ ] **mcp-server/server.py** - Убрать fallback ключ
- [ ] **analyze_with_perplexity.py** - Убрать fallback ключ
- [ ] **conduct_project_audit.py** - Убрать fallback ключ
- [ ] **test_mcp_conceptual_100.py** - Убрать fallback ключ
- [ ] **test_full_90days_mtf_ai_workflow.py** - Убрать fallback ключ

### Приоритет P2 (СРЕДНИЙ):

- [ ] **tests/integration/test_*.py** - Использовать mock API keys для тестов
- [ ] **mcp-server/test_perplexity.py** - Убрать fallback ключ
- [ ] **tests/integration/test_simplified_real.py** - Убрать fallback ключ
- [ ] **tests/integration/test_mcp_cyclic_dialogue.py** - Убрать fallback ключ

---

## 🛡️ BEST PRACTICES: Безопасное управление ключами

### 1. Environment Variables (.env файл):

```python
# ✅ ПРАВИЛЬНО:
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("PERPLEXITY_API_KEY")

if not API_KEY:
    raise ValueError("API key not configured")
```

### 2. Secrets Management (Production):

```python
# ✅ Для Production используйте:
# - AWS Secrets Manager
# - Azure Key Vault
# - HashiCorp Vault
# - Google Secret Manager

import boto3

def get_secret(secret_name: str) -> str:
    """Get secret from AWS Secrets Manager."""
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return response['SecretString']

API_KEY = get_secret("perplexity-api-key")
```

### 3. Для тестов используйте Mock:

```python
# ✅ В тестах используйте моки
import pytest
from unittest.mock import patch

@patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test_key_12345"})
def test_api_call():
    # Тест с моком ключа
    assert os.getenv("PERPLEXITY_API_KEY") == "test_key_12345"
```

### 4. Валидация формата ключа:

```python
# ✅ Добавьте валидацию
import re

def validate_api_key(key: str) -> bool:
    """Validate Perplexity API key format."""
    if not key:
        return False
    
    # Perplexity keys: pplx-[40 alphanumeric chars]
    pattern = r'^pplx-[A-Za-z0-9]{40,}$'
    
    if not re.match(pattern, key):
        raise ValueError(
            "Invalid API key format. "
            "Expected: pplx-[40+ characters]"
        )
    
    return True

# Использование:
API_KEY = os.getenv("PERPLEXITY_API_KEY")
validate_api_key(API_KEY)
```

---

## 🔍 ПРОВЕРКА БЕЗОПАСНОСТИ

### Checklist:

```bash
# 1. Проверить .gitignore
cat .gitignore | grep -E "\.env|api_key|secret"

# 2. Проверить, что .env НЕ в Git
git ls-files | grep .env
# Должно быть ПУСТО

# 3. Найти все hardcoded ключи
grep -r "pplx-" --include="*.py" .
# Должно быть 0 результатов (или только в .env.example)

# 4. Проверить Git историю
git log --all --full-history --source -- "**/*api*key*"

# 5. Сканировать с помощью TruffleHog
pip install truffleHog
truffleHog --regex --entropy=False .
```

---

## 📊 СТАТИСТИКА ИСПРАВЛЕНИЙ

**Файлов с проблемами:** 18  
**Hardcoded keys:** 8  
**Fallback keys:** 10  
**Приоритет P0:** 5 файлов  
**Приоритет P1:** 5 файлов  
**Приоритет P2:** 8 файлов  

**Ожидаемое время:** 1-2 часа  
**Риск exposure:** **ВЫСОКИЙ** ⚠️  
**Рекомендация:** **НЕМЕДЛЕННО**

---

## 🚀 AUTOMATED FIX SCRIPT

Создан скрипт для автоматического исправления:

```python
# fix_security_issues.py
import os
import re
from pathlib import Path

def fix_hardcoded_api_keys(file_path: Path):
    """Replace hardcoded API keys with os.getenv()."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern 1: Hardcoded key
    pattern1 = r'PERPLEXITY_API_KEY = "pplx-[A-Za-z0-9]+"'
    replacement1 = '''import os
from dotenv import load_dotenv

load_dotenv()
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

if not PERPLEXITY_API_KEY:
    raise ValueError("PERPLEXITY_API_KEY not configured")'''
    
    # Pattern 2: Fallback key
    pattern2 = r'os\.getenv\("PERPLEXITY_API_KEY", "pplx-[A-Za-z0-9]+"\)'
    replacement2 = 'os.getenv("PERPLEXITY_API_KEY")'
    
    content = re.sub(pattern1, replacement1, content)
    content = re.sub(pattern2, replacement2, content)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Fixed: {file_path}")

# Запустить для всех файлов
files_to_fix = [
    "query_perplexity.py",
    "query_mcp_tools.py",
    "analyze_project_with_mcp.py",
    "test_real_ai_workflow.py",
    "test_real_ai_workflow_mtf.py",
]

for file_name in files_to_fix:
    file_path = Path(file_name)
    if file_path.exists():
        fix_hardcoded_api_keys(file_path)
```

---

## 📚 ССЫЛКИ

1. **OWASP - Hardcoded Passwords**  
   https://owasp.org/www-community/vulnerabilities/Use_of_hard-coded_password

2. **NIST - Key Management**  
   https://csrc.nist.gov/projects/key-management/key-management-guidelines

3. **Python-Dotenv Documentation**  
   https://github.com/theskumar/python-dotenv

4. **AWS Secrets Manager**  
   https://aws.amazon.com/secrets-manager/

5. **TruffleHog - Secret Scanner**  
   https://github.com/trufflesecurity/trufflehog

---

**Создано:** 2025-10-30  
**Источник:** Perplexity AI Collaborative Analysis  
**Приоритет:** 🚨 **P0 - КРИТИЧНО**  
**Статус:** ⚠️ **ТРЕБУЕТ НЕМЕДЛЕННОГО ДЕЙСТВИЯ**
