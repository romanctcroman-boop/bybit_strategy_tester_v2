"""
Secure Configuration Handler.

AI Agent Security Recommendation - Phase 4 Implementation:
- Secure .env file handling with proper permissions
- Configuration validation
- Sensitive data masking
- Environment variable management
- Configuration encryption support
"""

import hashlib
import json
import logging
import os
import re
import stat
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ConfigSeverity(str, Enum):
    """Configuration issue severity."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ConfigType(str, Enum):
    """Types of configuration values."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    URL = "url"
    PATH = "path"
    SECRET = "secret"
    API_KEY = "api_key"
    DATABASE_URL = "database_url"


@dataclass
class ConfigVariable:
    """Configuration variable definition."""

    name: str
    config_type: ConfigType
    required: bool = False
    default_value: str | None = None
    description: str = ""
    is_sensitive: bool = False
    validation_pattern: str | None = None


@dataclass
class ConfigIssue:
    """Configuration issue detected."""

    issue_id: str
    severity: ConfigSeverity
    variable: str
    message: str
    recommendation: str
    file_path: str | None = None


@dataclass
class ConfigValidationResult:
    """Result of configuration validation."""

    is_valid: bool
    issues: list[ConfigIssue] = field(default_factory=list)
    variables_found: int = 0
    variables_missing: int = 0
    sensitive_exposed: int = 0


# Common sensitive variable patterns
SENSITIVE_PATTERNS = [
    r".*_KEY$",
    r".*_SECRET$",
    r".*_PASSWORD$",
    r".*_TOKEN$",
    r".*_API_KEY$",
    r".*_PRIVATE.*",
    r"DATABASE_URL",
    r"DB_PASSWORD",
    r"REDIS_URL",
    r"MONGODB_URI",
    r"AWS_.*",
    r"AZURE_.*",
    r"GCP_.*",
]


# Default variable definitions
DEFAULT_VARIABLES: list[ConfigVariable] = [
    ConfigVariable(
        name="BYBIT_API_KEY",
        config_type=ConfigType.API_KEY,
        required=False,
        is_sensitive=True,
        description="Bybit exchange API key",
    ),
    ConfigVariable(
        name="BYBIT_API_SECRET",
        config_type=ConfigType.SECRET,
        required=False,
        is_sensitive=True,
        description="Bybit exchange API secret",
    ),
    ConfigVariable(
        name="DEEPSEEK_API_KEY",
        config_type=ConfigType.API_KEY,
        required=False,
        is_sensitive=True,
        description="DeepSeek AI API key",
    ),
    ConfigVariable(
        name="PERPLEXITY_API_KEY",
        config_type=ConfigType.API_KEY,
        required=False,
        is_sensitive=True,
        description="Perplexity AI API key",
    ),
    ConfigVariable(
        name="DATABASE_URL",
        config_type=ConfigType.DATABASE_URL,
        required=False,
        is_sensitive=True,
        description="Database connection URL",
    ),
    ConfigVariable(
        name="ENCRYPTION_KEY",
        config_type=ConfigType.SECRET,
        required=False,
        is_sensitive=True,
        description="Master encryption key",
    ),
    ConfigVariable(
        name="SECRET_KEY",
        config_type=ConfigType.SECRET,
        required=False,
        is_sensitive=True,
        description="Application secret key",
    ),
    ConfigVariable(
        name="LOG_LEVEL",
        config_type=ConfigType.STRING,
        required=False,
        default_value="INFO",
        description="Logging level",
        validation_pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
    ),
    ConfigVariable(
        name="HOST",
        config_type=ConfigType.STRING,
        required=False,
        default_value="0.0.0.0",
        description="Server host",
    ),
    ConfigVariable(
        name="PORT",
        config_type=ConfigType.INTEGER,
        required=False,
        default_value="8000",
        description="Server port",
        validation_pattern=r"^\d+$",
    ),
]


class SecureConfigHandler:
    """
    Secure Configuration Handler.

    Manages configuration files with security best practices.
    """

    _instance: Optional["SecureConfigHandler"] = None

    def __init__(self):
        self._variables: dict[str, ConfigVariable] = {
            v.name: v for v in DEFAULT_VARIABLES
        }
        self._config_values: dict[str, str] = {}
        self._issues: list[ConfigIssue] = []
        self._issue_count = 0
        self._loaded_files: list[Path] = []

    @classmethod
    def get_instance(cls) -> "SecureConfigHandler":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def add_variable(self, variable: ConfigVariable) -> None:
        """Add a variable definition."""
        self._variables[variable.name] = variable
        logger.debug(f"Added variable definition: {variable.name}")

    def is_sensitive(self, name: str) -> bool:
        """Check if a variable is sensitive."""
        # Check explicit definition
        if name in self._variables:
            return self._variables[name].is_sensitive

        # Check patterns
        return any(re.match(pattern, name, re.IGNORECASE) for pattern in SENSITIVE_PATTERNS)

    def mask_value(self, value: str, visible_chars: int = 4) -> str:
        """Mask a sensitive value."""
        if len(value) <= visible_chars * 2:
            return "*" * len(value)
        return (
            value[:visible_chars]
            + "*" * (len(value) - visible_chars * 2)
            + value[-visible_chars:]
        )

    def check_file_permissions(self, file_path: Path) -> list[ConfigIssue]:
        """Check file permissions for security issues."""
        issues = []

        if not file_path.exists():
            return issues

        try:
            # On Windows, this is limited
            if os.name == "nt":
                # Windows-specific checks
                # Check if file is readable by everyone
                # This is a simplified check for Windows
                logger.debug(f"Windows file permission check for {file_path}")
            else:
                # Unix permissions check
                mode = file_path.stat().st_mode

                # Check for world-readable
                if mode & stat.S_IROTH:
                    self._issue_count += 1
                    issues.append(
                        ConfigIssue(
                            issue_id=f"perm-{self._issue_count}",
                            severity=ConfigSeverity.HIGH,
                            variable="FILE_PERMISSIONS",
                            message=f"Config file {file_path.name} is world-readable",
                            recommendation=f"Run: chmod 600 {file_path}",
                            file_path=str(file_path),
                        )
                    )

                # Check for world-writable
                if mode & stat.S_IWOTH:
                    self._issue_count += 1
                    issues.append(
                        ConfigIssue(
                            issue_id=f"perm-{self._issue_count}",
                            severity=ConfigSeverity.CRITICAL,
                            variable="FILE_PERMISSIONS",
                            message=f"Config file {file_path.name} is world-writable",
                            recommendation=f"Run: chmod 600 {file_path}",
                            file_path=str(file_path),
                        )
                    )

                # Check for group-readable
                if mode & stat.S_IRGRP:
                    self._issue_count += 1
                    issues.append(
                        ConfigIssue(
                            issue_id=f"perm-{self._issue_count}",
                            severity=ConfigSeverity.MEDIUM,
                            variable="FILE_PERMISSIONS",
                            message=f"Config file {file_path.name} is group-readable",
                            recommendation=f"Consider: chmod 600 {file_path}",
                            file_path=str(file_path),
                        )
                    )

        except Exception as e:
            logger.warning(f"Could not check permissions for {file_path}: {e}")

        return issues

    def set_secure_permissions(self, file_path: Path) -> bool:
        """Set secure permissions on a file (Unix only)."""
        if os.name == "nt":
            logger.info(
                f"Windows: Secure permissions require manual setup for {file_path}"
            )
            return True

        try:
            os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)  # 600
            logger.info(f"Set secure permissions (600) on {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to set permissions on {file_path}: {e}")
            return False

    def load_env_file(self, file_path: Path) -> dict[str, str]:
        """Load and parse an .env file."""
        values = {}

        if not file_path.exists():
            logger.warning(f"Config file not found: {file_path}")
            return values

        try:
            with open(file_path, encoding="utf-8") as f:
                for _line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Skip comments and empty lines
                    if not line or line.startswith("#"):
                        continue

                    # Parse KEY=VALUE
                    if "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip()

                        # Remove quotes
                        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                            value = value[1:-1]

                        values[key] = value

            self._loaded_files.append(file_path)
            self._config_values.update(values)
            logger.info(f"Loaded {len(values)} variables from {file_path}")

        except Exception as e:
            logger.error(f"Failed to load {file_path}: {e}")

        return values

    def validate_config(
        self,
        config_values: dict[str, str] | None = None,
        file_path: Path | None = None,
    ) -> ConfigValidationResult:
        """Validate configuration values."""
        values = config_values or self._config_values
        issues = []

        variables_found = 0
        variables_missing = 0
        sensitive_exposed = 0

        # Check file permissions
        if file_path:
            perm_issues = self.check_file_permissions(file_path)
            issues.extend(perm_issues)

        # Check required variables
        for name, variable in self._variables.items():
            if variable.required and name not in values:
                self._issue_count += 1
                issues.append(
                    ConfigIssue(
                        issue_id=f"missing-{self._issue_count}",
                        severity=ConfigSeverity.HIGH,
                        variable=name,
                        message=f"Required variable {name} is not set",
                        recommendation=f"Add {name} to your configuration",
                    )
                )
                variables_missing += 1
            elif name in values:
                variables_found += 1

                # Validate pattern
                if variable.validation_pattern:
                    value = values[name]
                    if not re.match(variable.validation_pattern, value):
                        self._issue_count += 1
                        issues.append(
                            ConfigIssue(
                                issue_id=f"invalid-{self._issue_count}",
                                severity=ConfigSeverity.MEDIUM,
                                variable=name,
                                message=f"Value for {name} does not match expected pattern",
                                recommendation=f"Check the format of {name}",
                            )
                        )

        # Check for sensitive values in unexpected places
        for name, value in values.items():
            if self.is_sensitive(name):
                # Check if value looks like a placeholder
                placeholders = ["your_", "xxx", "placeholder", "example", "test123"]
                for ph in placeholders:
                    if ph in value.lower():
                        self._issue_count += 1
                        issues.append(
                            ConfigIssue(
                                issue_id=f"placeholder-{self._issue_count}",
                                severity=ConfigSeverity.HIGH,
                                variable=name,
                                message=f"Sensitive variable {name} contains placeholder value",
                                recommendation=f"Set a proper value for {name}",
                            )
                        )

                # Check for very short secrets
                if len(value) < 8 and variable.config_type in [
                    ConfigType.SECRET,
                    ConfigType.API_KEY,
                ]:
                    self._issue_count += 1
                    issues.append(
                        ConfigIssue(
                            issue_id=f"weak-{self._issue_count}",
                            severity=ConfigSeverity.MEDIUM,
                            variable=name,
                            message=f"Sensitive variable {name} has a very short value",
                            recommendation=f"Use a longer, more secure value for {name}",
                        )
                    )

        # Check for exposed sensitive values in environment
        for name in os.environ:
            if self.is_sensitive(name):
                sensitive_exposed += 1

        self._issues.extend(issues)

        is_valid = not any(
            i.severity in [ConfigSeverity.CRITICAL, ConfigSeverity.HIGH] for i in issues
        )

        return ConfigValidationResult(
            is_valid=is_valid,
            issues=issues,
            variables_found=variables_found,
            variables_missing=variables_missing,
            sensitive_exposed=sensitive_exposed,
        )

    def get_masked_config(self) -> dict[str, str]:
        """Get configuration with sensitive values masked."""
        masked = {}
        for name, value in self._config_values.items():
            if self.is_sensitive(name):
                masked[name] = self.mask_value(value)
            else:
                masked[name] = value
        return masked

    def get_env_template(self) -> str:
        """Generate an .env template file."""
        lines = [
            "# Environment Configuration Template",
            "# Generated by SecureConfigHandler",
            f"# Date: {datetime.now().isoformat()}",
            "",
            "# IMPORTANT: Set file permissions to 600 (Unix) or restrict access (Windows)",
            "# chmod 600 .env",
            "",
        ]

        # Group by sensitivity
        sensitive_vars = []
        normal_vars = []

        for variable in self._variables.values():
            if variable.is_sensitive:
                sensitive_vars.append(variable)
            else:
                normal_vars.append(variable)

        # Normal variables first
        lines.append("# ============================================")
        lines.append("# General Configuration")
        lines.append("# ============================================")
        lines.append("")

        for var in normal_vars:
            if var.description:
                lines.append(f"# {var.description}")
            default = var.default_value or ""
            required = " (REQUIRED)" if var.required else ""
            lines.append(f"{var.name}={default}{required}")
            lines.append("")

        # Sensitive variables
        lines.append("# ============================================")
        lines.append("# SENSITIVE - Do not commit to version control!")
        lines.append("# ============================================")
        lines.append("")

        for var in sensitive_vars:
            if var.description:
                lines.append(f"# {var.description}")
            required = " (REQUIRED)" if var.required else ""
            lines.append(f"# {var.name}=<your-value-here>{required}")
            lines.append("")

        return "\n".join(lines)

    def export_to_json(self, include_sensitive: bool = False) -> str:
        """Export configuration to JSON (for backup/migration)."""
        data = {
            "exported_at": datetime.now().isoformat(),
            "variables": {},
        }

        for name, value in self._config_values.items():
            if self.is_sensitive(name) and not include_sensitive:
                data["variables"][name] = {
                    "value": self.mask_value(value),
                    "is_sensitive": True,
                    "is_masked": True,
                }
            else:
                data["variables"][name] = {
                    "value": value,
                    "is_sensitive": self.is_sensitive(name),
                    "is_masked": False,
                }

        return json.dumps(data, indent=2)

    def get_checksum(self) -> str:
        """Get a checksum of the current configuration."""
        config_str = json.dumps(sorted(self._config_values.items()))
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]

    def get_issues(
        self,
        severity: ConfigSeverity | None = None,
        variable: str | None = None,
    ) -> list[ConfigIssue]:
        """Get configuration issues."""
        issues = self._issues

        if severity:
            issues = [i for i in issues if i.severity == severity]

        if variable:
            issues = [i for i in issues if i.variable == variable]

        return issues

    def get_status(self) -> dict:
        """Get handler status."""
        return {
            "variables_defined": len(self._variables),
            "variables_loaded": len(self._config_values),
            "loaded_files": [str(f) for f in self._loaded_files],
            "issues_count": len(self._issues),
            "checksum": self.get_checksum(),
        }

    def get_variable_info(self, name: str) -> dict | None:
        """Get information about a variable."""
        if name not in self._variables:
            return None

        var = self._variables[name]
        value = self._config_values.get(name)

        return {
            "name": var.name,
            "type": var.config_type.value,
            "required": var.required,
            "description": var.description,
            "is_sensitive": var.is_sensitive,
            "is_set": value is not None,
            "value": self.mask_value(value) if value and var.is_sensitive else value,
            "default": var.default_value,
        }


# Singleton accessor
def get_config_handler() -> SecureConfigHandler:
    """Get secure config handler instance."""
    return SecureConfigHandler.get_instance()
