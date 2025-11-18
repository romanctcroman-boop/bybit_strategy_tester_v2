"""
RBAC Manager - Role-Based Access Control
Manages user roles, permissions, and access control
"""

from typing import Dict, List, Set, Optional
from enum import Enum
from dataclasses import dataclass
import logging

logger = logging.getLogger('security.rbac')


class Permission(Enum):
    """System permissions"""
    # Backtest permissions
    BACKTEST_READ = "backtest:read"
    BACKTEST_CREATE = "backtest:create"
    BACKTEST_DELETE = "backtest:delete"
    BACKTEST_EXECUTE = "backtest:execute"
    
    # Strategy permissions
    STRATEGY_READ = "strategy:read"
    STRATEGY_CREATE = "strategy:create"
    STRATEGY_UPDATE = "strategy:update"
    STRATEGY_DELETE = "strategy:delete"
    
    # Data permissions
    DATA_READ = "data:read"
    DATA_WRITE = "data:write"
    DATA_DELETE = "data:delete"
    
    # User management
    USER_READ = "user:read"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    
    # System administration
    SYSTEM_CONFIG = "system:config"
    SYSTEM_LOGS = "system:logs"
    SYSTEM_METRICS = "system:metrics"
    
    # API management
    API_KEY_CREATE = "api:key:create"
    API_KEY_REVOKE = "api:key:revoke"
    
    # Sandbox execution
    SANDBOX_EXECUTE = "sandbox:execute"
    SANDBOX_ADMIN = "sandbox:admin"


class Role(Enum):
    """Predefined system roles"""
    ADMIN = "admin"
    DEVELOPER = "developer"
    ANALYST = "analyst"
    VIEWER = "viewer"
    API_USER = "api_user"


@dataclass
class RoleDefinition:
    """Role definition with permissions"""
    name: str
    display_name: str
    permissions: Set[Permission]
    description: str


class RBACManager:
    """
    Role-Based Access Control manager.
    
    Features:
    - Predefined roles (Admin, Developer, Analyst, Viewer, API User)
    - Custom role creation
    - Permission inheritance
    - Dynamic permission checking
    - User-role assignment
    """
    
    # Predefined role definitions
    ROLE_DEFINITIONS: Dict[Role, RoleDefinition] = {
        Role.ADMIN: RoleDefinition(
            name=Role.ADMIN.value,
            display_name="Administrator",
            permissions={
                # All permissions
                Permission.BACKTEST_READ,
                Permission.BACKTEST_CREATE,
                Permission.BACKTEST_DELETE,
                Permission.BACKTEST_EXECUTE,
                Permission.STRATEGY_READ,
                Permission.STRATEGY_CREATE,
                Permission.STRATEGY_UPDATE,
                Permission.STRATEGY_DELETE,
                Permission.DATA_READ,
                Permission.DATA_WRITE,
                Permission.DATA_DELETE,
                Permission.USER_READ,
                Permission.USER_CREATE,
                Permission.USER_UPDATE,
                Permission.USER_DELETE,
                Permission.SYSTEM_CONFIG,
                Permission.SYSTEM_LOGS,
                Permission.SYSTEM_METRICS,
                Permission.API_KEY_CREATE,
                Permission.API_KEY_REVOKE,
                Permission.SANDBOX_EXECUTE,
                Permission.SANDBOX_ADMIN,
            },
            description="Full system access with all permissions"
        ),
        
        Role.DEVELOPER: RoleDefinition(
            name=Role.DEVELOPER.value,
            display_name="Developer",
            permissions={
                Permission.BACKTEST_READ,
                Permission.BACKTEST_CREATE,
                Permission.BACKTEST_EXECUTE,
                Permission.STRATEGY_READ,
                Permission.STRATEGY_CREATE,
                Permission.STRATEGY_UPDATE,
                Permission.DATA_READ,
                Permission.DATA_WRITE,
                Permission.SANDBOX_EXECUTE,
                Permission.API_KEY_CREATE,
            },
            description="Create and execute strategies and backtests"
        ),
        
        Role.ANALYST: RoleDefinition(
            name=Role.ANALYST.value,
            display_name="Analyst",
            permissions={
                Permission.BACKTEST_READ,
                Permission.BACKTEST_CREATE,
                Permission.BACKTEST_EXECUTE,
                Permission.STRATEGY_READ,
                Permission.DATA_READ,
            },
            description="View and analyze strategies and backtest results"
        ),
        
        Role.VIEWER: RoleDefinition(
            name=Role.VIEWER.value,
            display_name="Viewer",
            permissions={
                Permission.BACKTEST_READ,
                Permission.STRATEGY_READ,
                Permission.DATA_READ,
            },
            description="Read-only access to strategies and backtests"
        ),
        
        Role.API_USER: RoleDefinition(
            name=Role.API_USER.value,
            display_name="API User",
            permissions={
                Permission.BACKTEST_READ,
                Permission.BACKTEST_CREATE,
                Permission.BACKTEST_EXECUTE,
                Permission.STRATEGY_READ,
                Permission.DATA_READ,
            },
            description="API access for automated systems"
        ),
    }
    
    def __init__(self):
        """Initialize RBAC manager"""
        # User-role mappings (in-memory, should be database in production)
        self._user_roles: Dict[str, Set[str]] = {}
        
        # Custom roles (beyond predefined)
        self._custom_roles: Dict[str, RoleDefinition] = {}
    
    def assign_role(self, user_id: str, role: str) -> None:
        """
        Assign role to user.
        
        Args:
            user_id: User identifier
            role: Role name
        """
        if user_id not in self._user_roles:
            self._user_roles[user_id] = set()
        
        self._user_roles[user_id].add(role)
        logger.info(f"Assigned role '{role}' to user {user_id}")
    
    def revoke_role(self, user_id: str, role: str) -> None:
        """
        Revoke role from user.
        
        Args:
            user_id: User identifier
            role: Role name
        """
        if user_id in self._user_roles:
            self._user_roles[user_id].discard(role)
            logger.info(f"Revoked role '{role}' from user {user_id}")
    
    def get_user_roles(self, user_id: str) -> List[str]:
        """
        Get all roles assigned to user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of role names
        """
        return list(self._user_roles.get(user_id, set()))
    
    def get_user_permissions(self, user_id: str) -> Set[Permission]:
        """
        Get all permissions for user (aggregated from roles).
        
        Args:
            user_id: User identifier
            
        Returns:
            Set of permissions
        """
        permissions = set()
        
        for role_name in self.get_user_roles(user_id):
            # Check predefined roles
            for role, definition in self.ROLE_DEFINITIONS.items():
                if role.value == role_name:
                    permissions.update(definition.permissions)
                    break
            
            # Check custom roles
            if role_name in self._custom_roles:
                permissions.update(self._custom_roles[role_name].permissions)
        
        return permissions
    
    def has_permission(self, user_id: str, permission: Permission) -> bool:
        """
        Check if user has specific permission.
        
        Args:
            user_id: User identifier
            permission: Permission to check
            
        Returns:
            True if user has permission
        """
        user_permissions = self.get_user_permissions(user_id)
        has_perm = permission in user_permissions
        
        logger.debug(f"Permission check: user={user_id}, perm={permission.value}, result={has_perm}")
        return has_perm
    
    def has_any_permission(self, user_id: str, permissions: List[Permission]) -> bool:
        """
        Check if user has any of the specified permissions.
        
        Args:
            user_id: User identifier
            permissions: List of permissions to check
            
        Returns:
            True if user has at least one permission
        """
        user_permissions = self.get_user_permissions(user_id)
        return any(perm in user_permissions for perm in permissions)
    
    def has_all_permissions(self, user_id: str, permissions: List[Permission]) -> bool:
        """
        Check if user has all specified permissions.
        
        Args:
            user_id: User identifier
            permissions: List of permissions to check
            
        Returns:
            True if user has all permissions
        """
        user_permissions = self.get_user_permissions(user_id)
        return all(perm in user_permissions for perm in permissions)
    
    def has_role(self, user_id: str, role: str) -> bool:
        """
        Check if user has specific role.
        
        Args:
            user_id: User identifier
            role: Role name
            
        Returns:
            True if user has role
        """
        return role in self._user_roles.get(user_id, set())
    
    def create_custom_role(
        self,
        name: str,
        display_name: str,
        permissions: Set[Permission],
        description: str = ""
    ) -> None:
        """
        Create custom role.
        
        Args:
            name: Role name (unique)
            display_name: Human-readable name
            permissions: Set of permissions
            description: Role description
        """
        if name in self._custom_roles:
            raise ValueError(f"Custom role '{name}' already exists")
        
        self._custom_roles[name] = RoleDefinition(
            name=name,
            display_name=display_name,
            permissions=permissions,
            description=description
        )
        
        logger.info(f"Created custom role '{name}' with {len(permissions)} permissions")
    
    def delete_custom_role(self, name: str) -> None:
        """
        Delete custom role.
        
        Args:
            name: Role name
        """
        if name not in self._custom_roles:
            raise ValueError(f"Custom role '{name}' does not exist")
        
        # Remove role from all users
        for user_id in self._user_roles:
            self._user_roles[user_id].discard(name)
        
        del self._custom_roles[name]
        logger.info(f"Deleted custom role '{name}'")
    
    def get_role_definition(self, role_name: str) -> Optional[RoleDefinition]:
        """
        Get role definition.
        
        Args:
            role_name: Role name
            
        Returns:
            RoleDefinition or None
        """
        # Check predefined roles
        for role, definition in self.ROLE_DEFINITIONS.items():
            if role.value == role_name:
                return definition
        
        # Check custom roles
        return self._custom_roles.get(role_name)
    
    def list_all_roles(self) -> List[RoleDefinition]:
        """
        List all available roles (predefined + custom).
        
        Returns:
            List of role definitions
        """
        roles = list(self.ROLE_DEFINITIONS.values())
        roles.extend(self._custom_roles.values())
        return roles
    
    def get_permission_description(self, permission: Permission) -> str:
        """
        Get human-readable permission description.
        
        Args:
            permission: Permission enum
            
        Returns:
            Description string
        """
        descriptions = {
            Permission.BACKTEST_READ: "View backtest results",
            Permission.BACKTEST_CREATE: "Create new backtests",
            Permission.BACKTEST_DELETE: "Delete backtests",
            Permission.BACKTEST_EXECUTE: "Execute backtests",
            Permission.STRATEGY_READ: "View strategies",
            Permission.STRATEGY_CREATE: "Create new strategies",
            Permission.STRATEGY_UPDATE: "Update existing strategies",
            Permission.STRATEGY_DELETE: "Delete strategies",
            Permission.DATA_READ: "Read market data",
            Permission.DATA_WRITE: "Write market data",
            Permission.DATA_DELETE: "Delete market data",
            Permission.USER_READ: "View user information",
            Permission.USER_CREATE: "Create new users",
            Permission.USER_UPDATE: "Update user information",
            Permission.USER_DELETE: "Delete users",
            Permission.SYSTEM_CONFIG: "Configure system settings",
            Permission.SYSTEM_LOGS: "View system logs",
            Permission.SYSTEM_METRICS: "View system metrics",
            Permission.API_KEY_CREATE: "Create API keys",
            Permission.API_KEY_REVOKE: "Revoke API keys",
            Permission.SANDBOX_EXECUTE: "Execute code in sandbox",
            Permission.SANDBOX_ADMIN: "Administer sandbox system",
        }
        
        return descriptions.get(permission, permission.value)
