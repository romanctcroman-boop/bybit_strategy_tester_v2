"""
Repository Pattern - Base Repository

Provides unified data access layer with common CRUD operations.
All database operations should go through repositories to ensure:
- Consistent transaction handling
- Testability via dependency injection
- Single source of truth for queries
- Proper exception handling and logging
"""

import builtins
import logging
from typing import TypeVar

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.database.exceptions import (
    NotFoundError,
    classify_sqlalchemy_error,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BaseRepository[T]:
    """
    Base repository with common CRUD operations and exception handling.

    All methods include:
    - Try-except wrapping for SQLAlchemy errors
    - Logging of operations and failures
    - Classification of errors for retry logic

    Usage:
        class UserRepository(BaseRepository[User]):
            def __init__(self, session: Session):
                super().__init__(session, User)
    """

    def __init__(self, session: Session, model_class: type[T]):
        self.session = session
        self.model_class = model_class
        self._entity_name = model_class.__name__

    def add(self, entity: T) -> T:
        """Add a new entity to the session."""
        try:
            self.session.add(entity)
            logger.debug(f"Added {self._entity_name} entity")
            return entity
        except SQLAlchemyError as e:
            logger.error(f"Failed to add {self._entity_name}: {e}")
            raise classify_sqlalchemy_error(e, "add", self._entity_name) from e

    def add_all(self, entities: list[T]) -> list[T]:
        """Add multiple entities to the session."""
        try:
            self.session.add_all(entities)
            logger.debug(f"Added {len(entities)} {self._entity_name} entities")
            return entities
        except SQLAlchemyError as e:
            logger.error(f"Failed to add_all {self._entity_name}: {e}")
            raise classify_sqlalchemy_error(e, "add_all", self._entity_name) from e

    def get(self, id: int) -> T | None:
        """Get entity by primary key."""
        try:
            result = self.session.get(self.model_class, id)
            if result:
                logger.debug(f"Found {self._entity_name} with id={id}")
            return result
        except SQLAlchemyError as e:
            logger.error(f"Failed to get {self._entity_name} with id={id}: {e}")
            raise classify_sqlalchemy_error(e, "get", self._entity_name) from e

    def get_or_raise(self, id: int) -> T:
        """Get entity by primary key or raise NotFoundError."""
        entity = self.get(id)
        if entity is None:
            raise NotFoundError(
                f"{self._entity_name} with id={id} not found",
                operation="get_or_raise",
                entity=self._entity_name,
            )
        return entity

    def get_by(self, **kwargs) -> T | None:
        """Get first entity matching filter criteria."""
        try:
            result = self.session.query(self.model_class).filter_by(**kwargs).first()
            return result
        except SQLAlchemyError as e:
            logger.error(f"Failed to get_by {self._entity_name} with {kwargs}: {e}")
            raise classify_sqlalchemy_error(e, "get_by", self._entity_name) from e

    def list(self, limit: int = 100, offset: int = 0) -> list[T]:
        """List entities with pagination."""
        try:
            result = (
                self.session.query(self.model_class).limit(limit).offset(offset).all()
            )
            logger.debug(f"Listed {len(result)} {self._entity_name} entities")
            return result
        except SQLAlchemyError as e:
            logger.error(f"Failed to list {self._entity_name}: {e}")
            raise classify_sqlalchemy_error(e, "list", self._entity_name) from e

    def list_by(self, limit: int = 100, offset: int = 0, **kwargs) -> builtins.list[T]:
        """List entities matching filter criteria."""
        try:
            result = (
                self.session.query(self.model_class)
                .filter_by(**kwargs)
                .limit(limit)
                .offset(offset)
                .all()
            )
            return result
        except SQLAlchemyError as e:
            logger.error(f"Failed to list_by {self._entity_name} with {kwargs}: {e}")
            raise classify_sqlalchemy_error(e, "list_by", self._entity_name) from e

    def filter(self, *criterion) -> builtins.list[T]:
        """
        Filter entities using SQLAlchemy criterion expressions.

        Usage:
            repo.filter(User.age > 18, User.name.like('%John%'))
        """
        try:
            result = self.session.query(self.model_class).filter(*criterion).all()
            return result
        except SQLAlchemyError as e:
            logger.error(f"Failed to filter {self._entity_name}: {e}")
            raise classify_sqlalchemy_error(e, "filter", self._entity_name) from e

    def count(self, **kwargs) -> int:
        """Count entities matching filter criteria."""
        try:
            query = self.session.query(self.model_class)
            if kwargs:
                query = query.filter_by(**kwargs)
            return query.count()
        except SQLAlchemyError as e:
            logger.error(f"Failed to count {self._entity_name}: {e}")
            raise classify_sqlalchemy_error(e, "count", self._entity_name) from e

    def exists(self, **kwargs) -> bool:
        """Check if entity exists matching filter criteria."""
        return self.count(**kwargs) > 0

    def delete(self, entity: T) -> None:
        """Delete an entity."""
        try:
            self.session.delete(entity)
            logger.debug(f"Deleted {self._entity_name} entity")
        except SQLAlchemyError as e:
            logger.error(f"Failed to delete {self._entity_name}: {e}")
            raise classify_sqlalchemy_error(e, "delete", self._entity_name) from e

    def delete_by_id(self, id: int) -> bool:
        """Delete entity by primary key. Returns True if deleted."""
        entity = self.get(id)
        if entity:
            self.delete(entity)
            return True
        return False

    def flush(self) -> None:
        """Flush pending changes to database (within transaction)."""
        try:
            self.session.flush()
        except SQLAlchemyError as e:
            logger.error(f"Failed to flush {self._entity_name}: {e}")
            raise classify_sqlalchemy_error(e, "flush", self._entity_name) from e

    def refresh(self, entity: T) -> T:
        """Refresh entity from database."""
        try:
            self.session.refresh(entity)
            return entity
        except SQLAlchemyError as e:
            logger.error(f"Failed to refresh {self._entity_name}: {e}")
            raise classify_sqlalchemy_error(e, "refresh", self._entity_name) from e
