"""Tests for user management service."""

import pytest
from datetime import datetime, UTC
from unittest.mock import Mock, MagicMock, patch

from sqlalchemy.orm import Session

from backend.services.user_service import UserService
from backend.models import User


class TestUserServiceInit:
    """Test UserService initialization."""
    
    def test_init_with_db_session(self):
        """Test initialization with database session."""
        mock_db = Mock(spec=Session)
        service = UserService(db=mock_db)
        
        assert service.db is mock_db


class TestCreateUser:
    """Test user creation functionality."""
    
    def test_create_user_basic(self):
        """Test creating a basic user."""
        mock_db = Mock(spec=Session)
        mock_db.query().filter().first.return_value = None  # No existing user
        
        service = UserService(db=mock_db)
        
        with patch('backend.services.user_service.hash_password', return_value='hashed_password'):
            user = service.create_user(
                username='testuser',
                password='password123'
            )
        
        assert user.username == 'testuser'
        assert user.hashed_password == 'hashed_password'
        assert user.is_active is True
        assert user.is_admin is False
        assert user.email is None
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
    
    def test_create_user_with_email(self):
        """Test creating user with email."""
        mock_db = Mock(spec=Session)
        mock_db.query().filter().first.return_value = None
        
        service = UserService(db=mock_db)
        
        with patch('backend.services.user_service.hash_password', return_value='hashed_password'):
            user = service.create_user(
                username='testuser',
                password='password123',
                email='test@example.com'
            )
        
        assert user.email == 'test@example.com'
    
    def test_create_admin_user(self):
        """Test creating admin user."""
        mock_db = Mock(spec=Session)
        mock_db.query().filter().first.return_value = None
        
        service = UserService(db=mock_db)
        
        with patch('backend.services.user_service.hash_password', return_value='hashed_password'):
            user = service.create_user(
                username='admin',
                password='admin123',
                is_admin=True
            )
        
        assert user.is_admin is True
    
    def test_create_user_duplicate_username(self):
        """Test creating user with existing username."""
        mock_db = Mock(spec=Session)
        existing_user = Mock(spec=User)
        mock_db.query().filter().first.return_value = existing_user
        
        service = UserService(db=mock_db)
        
        with pytest.raises(ValueError, match="Username 'testuser' already exists"):
            service.create_user(username='testuser', password='password123')
    
    def test_create_user_duplicate_email(self):
        """Test creating user with existing email."""
        mock_db = Mock(spec=Session)
        
        # First query (username) returns None, second query (email) returns existing user
        mock_query = Mock()
        mock_filter = Mock()
        
        # Setup the chain for two different queries
        first_filter = Mock()
        first_filter.first.return_value = None  # No user with this username
        
        second_filter = Mock()
        second_filter.first.return_value = Mock(spec=User)  # Email exists
        
        mock_query.filter.side_effect = [first_filter, second_filter]
        mock_db.query.return_value = mock_query
        
        service = UserService(db=mock_db)
        
        with pytest.raises(ValueError, match="Email 'test@example.com' already exists"):
            service.create_user(
                username='testuser',
                password='password123',
                email='test@example.com'
            )


class TestAuthenticateUser:
    """Test user authentication."""
    
    def test_authenticate_valid_user(self):
        """Test authenticating with valid credentials."""
        mock_db = Mock(spec=Session)
        
        mock_user = Mock(spec=User)
        mock_user.username = 'testuser'
        mock_user.hashed_password = 'hashed_password'
        mock_user.is_active = True
        mock_user.last_login = None
        
        mock_db.query().filter().first.return_value = mock_user
        
        service = UserService(db=mock_db)
        
        with patch('backend.services.user_service.verify_password', return_value=True):
            result = service.authenticate_user('testuser', 'password123')
        
        assert result is mock_user
        assert isinstance(mock_user.last_login, datetime)
        mock_db.commit.assert_called_once()
    
    def test_authenticate_user_not_found(self):
        """Test authentication with non-existent user."""
        mock_db = Mock(spec=Session)
        mock_db.query().filter().first.return_value = None
        
        service = UserService(db=mock_db)
        
        result = service.authenticate_user('nonexistent', 'password')
        
        assert result is None
    
    def test_authenticate_inactive_user(self):
        """Test authentication with inactive user."""
        mock_db = Mock(spec=Session)
        
        mock_user = Mock(spec=User)
        mock_user.is_active = False
        
        mock_db.query().filter().first.return_value = mock_user
        
        service = UserService(db=mock_db)
        
        result = service.authenticate_user('testuser', 'password123')
        
        assert result is None
    
    def test_authenticate_wrong_password(self):
        """Test authentication with wrong password."""
        mock_db = Mock(spec=Session)
        
        mock_user = Mock(spec=User)
        mock_user.is_active = True
        mock_user.hashed_password = 'hashed_password'
        
        mock_db.query().filter().first.return_value = mock_user
        
        service = UserService(db=mock_db)
        
        with patch('backend.services.user_service.verify_password', return_value=False):
            result = service.authenticate_user('testuser', 'wrongpassword')
        
        assert result is None


class TestGetUserByUsername:
    """Test getting user by username."""
    
    def test_get_existing_user(self):
        """Test getting existing user."""
        mock_db = Mock(spec=Session)
        mock_user = Mock(spec=User)
        mock_user.username = 'testuser'
        
        mock_db.query().filter().first.return_value = mock_user
        
        service = UserService(db=mock_db)
        result = service.get_user_by_username('testuser')
        
        assert result is mock_user
    
    def test_get_nonexistent_user(self):
        """Test getting non-existent user."""
        mock_db = Mock(spec=Session)
        mock_db.query().filter().first.return_value = None
        
        service = UserService(db=mock_db)
        result = service.get_user_by_username('nonexistent')
        
        assert result is None


class TestGetUserById:
    """Test getting user by ID."""
    
    def test_get_existing_user_by_id(self):
        """Test getting existing user by ID."""
        mock_db = Mock(spec=Session)
        mock_user = Mock(spec=User)
        mock_user.id = 1
        
        mock_db.query().filter().first.return_value = mock_user
        
        service = UserService(db=mock_db)
        result = service.get_user_by_id(1)
        
        assert result is mock_user
    
    def test_get_nonexistent_user_by_id(self):
        """Test getting non-existent user by ID."""
        mock_db = Mock(spec=Session)
        mock_db.query().filter().first.return_value = None
        
        service = UserService(db=mock_db)
        result = service.get_user_by_id(999)
        
        assert result is None


class TestUpdatePassword:
    """Test password update functionality."""
    
    def test_update_password_success(self):
        """Test successful password update."""
        mock_db = Mock(spec=Session)
        mock_user = Mock(spec=User)
        mock_user.username = 'testuser'
        mock_user.hashed_password = 'old_hash'
        
        mock_db.query().filter().first.return_value = mock_user
        
        service = UserService(db=mock_db)
        
        with patch('backend.services.user_service.hash_password', return_value='new_hash'):
            result = service.update_password('testuser', 'newpassword123')
        
        assert result is True
        assert mock_user.hashed_password == 'new_hash'
        mock_db.commit.assert_called_once()
    
    def test_update_password_user_not_found(self):
        """Test password update for non-existent user."""
        mock_db = Mock(spec=Session)
        mock_db.query().filter().first.return_value = None
        
        service = UserService(db=mock_db)
        result = service.update_password('nonexistent', 'newpassword')
        
        assert result is False
        mock_db.commit.assert_not_called()


class TestDeactivateUser:
    """Test user deactivation."""
    
    def test_deactivate_user_success(self):
        """Test successful user deactivation."""
        mock_db = Mock(spec=Session)
        mock_user = Mock(spec=User)
        mock_user.is_active = True
        
        mock_db.query().filter().first.return_value = mock_user
        
        service = UserService(db=mock_db)
        result = service.deactivate_user('testuser')
        
        assert result is True
        assert mock_user.is_active is False
        mock_db.commit.assert_called_once()
    
    def test_deactivate_user_not_found(self):
        """Test deactivating non-existent user."""
        mock_db = Mock(spec=Session)
        mock_db.query().filter().first.return_value = None
        
        service = UserService(db=mock_db)
        result = service.deactivate_user('nonexistent')
        
        assert result is False
        mock_db.commit.assert_not_called()


class TestActivateUser:
    """Test user activation."""
    
    def test_activate_user_success(self):
        """Test successful user activation."""
        mock_db = Mock(spec=Session)
        mock_user = Mock(spec=User)
        mock_user.is_active = False
        
        mock_db.query().filter().first.return_value = mock_user
        
        service = UserService(db=mock_db)
        result = service.activate_user('testuser')
        
        assert result is True
        assert mock_user.is_active is True
        mock_db.commit.assert_called_once()
    
    def test_activate_user_not_found(self):
        """Test activating non-existent user."""
        mock_db = Mock(spec=Session)
        mock_db.query().filter().first.return_value = None
        
        service = UserService(db=mock_db)
        result = service.activate_user('nonexistent')
        
        assert result is False
        mock_db.commit.assert_not_called()


class TestIntegration:
    """Integration tests for UserService."""
    
    def test_create_and_authenticate_workflow(self):
        """Test complete workflow: create user and authenticate."""
        mock_db = Mock(spec=Session)
        mock_db.query().filter().first.return_value = None
        
        service = UserService(db=mock_db)
        
        # Create user
        with patch('backend.services.user_service.hash_password', return_value='hashed_pw'):
            user = service.create_user('testuser', 'password123')
        
        # Simulate finding the user for authentication
        mock_db.query().filter().first.return_value = user
        
        # Authenticate
        with patch('backend.services.user_service.verify_password', return_value=True):
            auth_user = service.authenticate_user('testuser', 'password123')
        
        assert auth_user is user
        assert auth_user.last_login is not None
    
    def test_deactivate_and_authenticate_workflow(self):
        """Test that deactivated users cannot authenticate."""
        mock_db = Mock(spec=Session)
        
        mock_user = Mock(spec=User)
        mock_user.is_active = True
        mock_user.hashed_password = 'hashed_pw'
        
        mock_db.query().filter().first.return_value = mock_user
        
        service = UserService(db=mock_db)
        
        # Deactivate user
        result = service.deactivate_user('testuser')
        assert result is True
        assert mock_user.is_active is False
        
        # Try to authenticate
        auth_result = service.authenticate_user('testuser', 'password123')
        assert auth_result is None
    
    def test_update_password_and_authenticate(self):
        """Test password update and authentication with new password."""
        mock_db = Mock(spec=Session)
        
        mock_user = Mock(spec=User)
        mock_user.username = 'testuser'
        mock_user.hashed_password = 'old_hash'
        mock_user.is_active = True
        
        mock_db.query().filter().first.return_value = mock_user
        
        service = UserService(db=mock_db)
        
        # Update password
        with patch('backend.services.user_service.hash_password', return_value='new_hash'):
            result = service.update_password('testuser', 'newpassword')
        
        assert result is True
        assert mock_user.hashed_password == 'new_hash'
        
        # Authenticate with new password
        with patch('backend.services.user_service.verify_password', return_value=True):
            auth_user = service.authenticate_user('testuser', 'newpassword')
        
        assert auth_user is mock_user
