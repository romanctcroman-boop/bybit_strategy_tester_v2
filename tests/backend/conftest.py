"""
Custom fixtures для backend тестов.

Quick Win #4: Database Rollback Fixtures
- Автоматический rollback транзакций после каждого теста
- Изоляция тестов друг от друга
- Ускорение выполнения (не нужна очистка БД)

Другие fixtures:
- tmp_path: решает проблему с Windows permissions
"""

import os
import pytest
import shutil
import uuid
from pathlib import Path
from typing import Generator

# Устанавливаем DATABASE_URL до импорта backend.database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base


# ========================================
# Quick Win #4: Database Fixtures
# ========================================

@pytest.fixture(scope="session")
def db_engine():
    """
    Создаёт SQLAlchemy engine для тестов.
    
    Scope: session - создаётся один раз для всех тестов.
    Использует in-memory SQLite с StaticPool для изоляции.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    
    # Создать все таблицы
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Очистка после всех тестов
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="session")
def db_session_factory(db_engine):
    """
    Создаёт фабрику сессий для тестов.
    
    Scope: session - используется всеми тестами.
    """
    return sessionmaker(autocommit=False, autoflush=False, bind=db_engine)


@pytest.fixture
def db_session(db_engine) -> Generator[Session, None, None]:
    """
    Предоставляет database session с автоматическим rollback.
    
    Quick Win #4 - ключевая фича (FIXED ORDER):
    - Каждый тест получает чистую сессию
    - Все изменения откатываются после теста
    - Тесты изолированы друг от друга
    - Не требуется ручная очистка данных
    
    🔒 SECURITY FIX: Правильный порядок rollback → close
    
    Использование:
        def test_something(db_session):
            user = User(name="test")
            db_session.add(user)
            db_session.commit()
            # После теста всё откатится автоматически
    
    Scope: function - новая сессия для каждого теста.
    """
    # Создаём connection из engine
    connection = db_engine.connect()
    # Начинаем transaction на уровне connection
    transaction = connection.begin()
    # Создаём session привязанную к connection
    session = Session(bind=connection)
    
    try:
        yield session
    finally:
        # 🔒 CRITICAL: Правильный порядок cleanup
        try:
            # 1. Сначала rollback (откатываем изменения)
            transaction.rollback()
        except Exception as e:
            # Логируем ошибку rollback, но продолжаем cleanup
            print(f"Rollback error: {e}")
        finally:
            # 2. Потом close session (закрываем ресурсы)
            session.close()
            # 3. Закрываем connection
            connection.close()


@pytest.fixture
def db_session_no_rollback(db_session_factory) -> Generator[Session, None, None]:
    """
    Database session БЕЗ автоматического rollback.
    
    Используйте только для специальных случаев где нужен commit:
    - Тестирование транзакционной логики
    - Проверка constraint violations
    - Интеграционные тесты с реальными commits
    
    ВНИМАНИЕ: Требует ручную очистку данных!
    
    Использование:
        def test_commit_logic(db_session_no_rollback):
            user = User(name="test")
            db_session_no_rollback.add(user)
            db_session_no_rollback.commit()
            # Данные останутся в БД - очистите вручную!
    """
    session = db_session_factory()
    
    yield session
    
    # Просто закрываем сессию без rollback
    session.close()


# ========================================
# Filesystem Fixtures
# ========================================

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


# ========================================
# 🎯 PERFECT 10/10: Enhanced DB Fixtures
# ========================================

@pytest.fixture(scope="session")
def db_tables_registry(db_engine):
    """
    Registry всех таблиц для оптимизированной очистки.
    
    Использование: позволяет быстро очистить только измененные таблицы.
    """
    from sqlalchemy import inspect
    
    inspector = inspect(db_engine)
    tables = inspector.get_table_names()
    
    return set(tables)


@pytest.fixture
def fast_db_cleanup(db_engine, db_tables_registry):
    """
    Быстрая очистка БД после теста (только для PostgreSQL).
    
    Использует TRUNCATE CASCADE для максимальной скорости.
    Для SQLite использует DELETE (так как TRUNCATE не поддерживается).
    """
    yield
    
    # Cleanup после теста
    if db_engine.dialect.name == 'postgresql':
        # Fast TRUNCATE для PostgreSQL
        with db_engine.connect() as conn:
            for table in db_tables_registry:
                try:
                    conn.execute(f"TRUNCATE TABLE {table} CASCADE")
                    conn.commit()
                except Exception:
                    pass  # Игнорируем ошибки (таблица может не существовать)
    else:
        # DELETE для SQLite
        with db_engine.connect() as conn:
            for table in db_tables_registry:
                try:
                    conn.execute(f"DELETE FROM {table}")
                    conn.commit()
                except Exception:
                    pass
