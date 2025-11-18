"""User management service."""

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.models import User
from backend.utils.password import hash_password, verify_password


class UserService:
    """Service for managing users."""

    def __init__(self, db: Session):
        self.db = db

    def create_user(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
        is_admin: bool = False,
    ) -> User:
        """Create a new user.
        
        Args:
            username: Username (must be unique)
            password: Plain text password (will be hashed)
            email: Optional email address
            is_admin: Whether user has admin privileges
            
        Returns:
            Created user object
            
        Raises:
            ValueError: If username already exists
        """
        # Check if user exists
        existing = self.db.query(User).filter(User.username == username).first()
        if existing:
            raise ValueError(f"Username '{username}' already exists")

        # Check email if provided
        if email:
            existing_email = self.db.query(User).filter(User.email == email).first()
            if existing_email:
                raise ValueError(f"Email '{email}' already exists")

        # Create user
        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            is_admin=is_admin,
            is_active=True,
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        return user

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user by username and password.
        
        Args:
            username: Username
            password: Plain text password
            
        Returns:
            User object if authentication successful, None otherwise
        """
        user = self.db.query(User).filter(User.username == username).first()
        
        if not user:
            return None
            
        if not user.is_active:
            return None
            
        if not verify_password(password, user.hashed_password):
            return None

        # Update last login
        user.last_login = datetime.now(UTC)
        self.db.commit()
        
        return user

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username.
        
        Args:
            username: Username to search for
            
        Returns:
            User object if found, None otherwise
        """
        return self.db.query(User).filter(User.username == username).first()

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID.
        
        Args:
            user_id: User ID
            
        Returns:
            User object if found, None otherwise
        """
        return self.db.query(User).filter(User.id == user_id).first()

    def update_password(self, username: str, new_password: str) -> bool:
        """Update user password.
        
        Args:
            username: Username
            new_password: New plain text password
            
        Returns:
            True if successful, False otherwise
        """
        user = self.get_user_by_username(username)
        if not user:
            return False
            
        user.hashed_password = hash_password(new_password)
        self.db.commit()
        
        return True

    def deactivate_user(self, username: str) -> bool:
        """Deactivate a user account.
        
        Args:
            username: Username
            
        Returns:
            True if successful, False otherwise
        """
        user = self.get_user_by_username(username)
        if not user:
            return False
            
        user.is_active = False
        self.db.commit()
        
        return True

    def activate_user(self, username: str) -> bool:
        """Activate a user account.
        
        Args:
            username: Username
            
        Returns:
            True if successful, False otherwise
        """
        user = self.get_user_by_username(username)
        if not user:
            return False
            
        user.is_active = True
        self.db.commit()
        
        return True
