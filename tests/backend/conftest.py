"""
Custom fixtures для backend тестов.

Решает проблему с Windows permissions для tmp_path:
- Создаёт временные директории в проекте вместо системной temp
- Автоматическая очистка после тестов
"""

import pytest
import shutil
import uuid
from pathlib import Path


@pytest.fixture
def tmp_path():
    """
    Custom tmp_path fixture для обхода Windows permission issues.
    
    Создаёт временную директорию в проекте вместо системной temp:
    - D:/bybit_strategy_tester_v2/.pytest_tmp/<uuid>/
    
    Автоматически очищается после теста.
    """
    # Создать базовую директорию в проекте
    base_tmp = Path(__file__).parent.parent.parent / ".pytest_tmp"
    base_tmp.mkdir(exist_ok=True)
    
    # Создать уникальную поддиректорию для теста
    unique_id = str(uuid.uuid4())[:8]
    tmp_dir = base_tmp / unique_id
    tmp_dir.mkdir(parents=True, exist_ok=True)
    
    yield tmp_dir
    
    # Очистка
    try:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass  # Игнорируем ошибки очистки
