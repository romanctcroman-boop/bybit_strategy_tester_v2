"""
LLM Output Validator

Validates AI agent responses for safety, compliance and quality.
Applies configurable validation rules to catch:
- Sensitive data leakage (API keys, passwords, env vars)
- Hallucinated financial advice
- Dangerous trading recommendations
- Code execution attempts
- Excessive length / empty responses

Thread-safe and stateless — safe for concurrent use.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


class ValidationSeverity(str, Enum):
    """Severity level of validation failures."""

    CRITICAL = "critical"  # Must block response
    WARNING = "warning"  # Log and optionally filter
    INFO = "info"  # Informational only


@dataclass
class ValidationRule:
    """A single validation rule definition."""

    id: str
    name: str
    pattern: re.Pattern
    severity: ValidationSeverity
    description: str = ""
    replacement: str = "[REDACTED]"

    def check(self, text: str) -> list[str]:
        """Return all matches of this rule in text."""
        return self.pattern.findall(text)


@dataclass
class ValidationResult:
    """Result of output validation."""

    is_valid: bool
    original_text: str
    sanitized_text: str
    violations: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_critical(self) -> bool:
        return any(v["severity"] == "critical" for v in self.violations)

    @property
    def violation_count(self) -> int:
        return len(self.violations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "violation_count": self.violation_count,
            "has_critical": self.has_critical,
            "violations": self.violations,
            "warnings": self.warnings,
        }


# ═══════════════════════════════════════════════════════════════════
# Default Validation Rules
# ═══════════════════════════════════════════════════════════════════

DEFAULT_RULES: list[ValidationRule] = [
    # --- Critical: Data Leakage ---
    ValidationRule(
        id="leak_api_key",
        name="API Key Exposure",
        pattern=re.compile(
            r"(?i)(api[_\-\s]?key|secret[_\-\s]?key|access[_\-\s]?token)"
            r"\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}['\"]?"
        ),
        severity=ValidationSeverity.CRITICAL,
        description="Potential API key or secret in output",
    ),
    ValidationRule(
        id="leak_password",
        name="Password Exposure",
        pattern=re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?[^\s'\"]{4,}['\"]?"),
        severity=ValidationSeverity.CRITICAL,
        description="Potential password in output",
    ),
    ValidationRule(
        id="leak_env_var",
        name="Environment Variable",
        pattern=re.compile(r"(?i)(DATABASE_URL|REDIS_URL|SECRET_KEY|JWT_SECRET)\s*=\s*\S+"),
        severity=ValidationSeverity.CRITICAL,
        description="Environment variable value exposed",
    ),
    ValidationRule(
        id="leak_private_key",
        name="Private Key",
        pattern=re.compile(r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----"),
        severity=ValidationSeverity.CRITICAL,
        description="Private key in output",
    ),
    # --- Warning: Dangerous Advice ---
    ValidationRule(
        id="advice_guaranteed",
        name="Guaranteed Returns",
        pattern=re.compile(r"(?i)(guaranteed|100%\s*(profit|return|win)|can'?t?\s+lose|risk.?free)"),
        severity=ValidationSeverity.WARNING,
        description="Unrealistic financial claims",
    ),
    ValidationRule(
        id="advice_all_in",
        name="All-In Recommendation",
        pattern=re.compile(
            r"(?i)(invest\s+(all|everything|your\s+life\s+savings)|go\s+all\s*-?\s*in|max(imum)?\s+leverage)"
        ),
        severity=ValidationSeverity.WARNING,
        description="Dangerous investment recommendation",
    ),
    ValidationRule(
        id="advice_insider",
        name="Insider Trading",
        pattern=re.compile(r"(?i)(insider\s+(info|trading|knowledge)|non.?public\s+information)"),
        severity=ValidationSeverity.WARNING,
        description="Reference to insider information",
    ),
    # --- Warning: Code Injection ---
    ValidationRule(
        id="code_exec",
        name="Code Execution",
        pattern=re.compile(r"(?i)(exec|eval|__import__|subprocess|os\.system)\s*\("),
        severity=ValidationSeverity.WARNING,
        description="Code execution attempt in output",
    ),
    ValidationRule(
        id="code_sql",
        name="SQL Injection",
        pattern=re.compile(r"(?i)(DROP\s+TABLE|DELETE\s+FROM|TRUNCATE\s+TABLE|ALTER\s+TABLE)"),
        severity=ValidationSeverity.WARNING,
        description="Potentially dangerous SQL in output",
    ),
    # --- Info: Quality Checks ---
    ValidationRule(
        id="quality_hallucination",
        name="Hallucination Marker",
        pattern=re.compile(r"(?i)(as\s+an?\s+ai|i\s+don'?t\s+have\s+(access|real-?time))"),
        severity=ValidationSeverity.INFO,
        description="Common LLM hallucination/disclaimer pattern",
    ),
]


class OutputValidator:
    """
    Validates LLM output against security and quality rules.

    Usage:
        validator = OutputValidator()
        result = validator.validate(agent_response)
        if not result.is_valid:
            use result.sanitized_text instead
    """

    def __init__(
        self,
        rules: list[ValidationRule] | None = None,
        max_output_length: int = 50_000,
        min_output_length: int = 1,
        block_on_warning: bool = False,
    ) -> None:
        """
        Args:
            rules: Custom validation rules (defaults to DEFAULT_RULES)
            max_output_length: Maximum allowed output length
            min_output_length: Minimum allowed output length
            block_on_warning: If True, warnings also mark output as invalid
        """
        self.rules = rules if rules is not None else list(DEFAULT_RULES)
        self.max_output_length = max_output_length
        self.min_output_length = min_output_length
        self.block_on_warning = block_on_warning

    def validate(self, text: str) -> ValidationResult:
        """
        Validate output text against all rules.

        Args:
            text: The LLM output to validate.

        Returns:
            ValidationResult with violations and sanitized text.
        """
        violations: list[dict[str, Any]] = []
        warnings: list[str] = []
        sanitized = text

        # Length checks
        if len(text) < self.min_output_length:
            violations.append(
                {
                    "rule_id": "length_min",
                    "name": "Minimum Length",
                    "severity": "warning",
                    "details": f"Output too short: {len(text)} chars",
                }
            )
            warnings.append(f"Output length {len(text)} below minimum {self.min_output_length}")

        if len(text) > self.max_output_length:
            warnings.append(f"Output truncated from {len(text)} to {self.max_output_length} chars")
            sanitized = text[: self.max_output_length]

        # Rule checks
        for rule in self.rules:
            matches = rule.check(text)
            if matches:
                violation = {
                    "rule_id": rule.id,
                    "name": rule.name,
                    "severity": rule.severity.value,
                    "matches": matches[:5],  # Limit stored matches
                    "details": rule.description,
                }
                violations.append(violation)

                if rule.severity == ValidationSeverity.CRITICAL:
                    # Redact critical content
                    sanitized = rule.pattern.sub(rule.replacement, sanitized)
                    logger.warning(f"Output validation CRITICAL: {rule.name} — {len(matches)} match(es)")
                elif rule.severity == ValidationSeverity.WARNING:
                    warnings.append(f"{rule.name}: {rule.description}")
                    logger.info(f"Output validation WARNING: {rule.name}")

        # Determine validity
        has_critical = any(v["severity"] == "critical" for v in violations)
        has_warning = any(v["severity"] == "warning" for v in violations)
        is_valid = not has_critical and (not has_warning or not self.block_on_warning)

        return ValidationResult(
            is_valid=is_valid,
            original_text=text,
            sanitized_text=sanitized,
            violations=violations,
            warnings=warnings,
        )

    def add_rule(self, rule: ValidationRule) -> None:
        """Add a custom validation rule."""
        self.rules.append(rule)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID. Returns True if found and removed."""
        before = len(self.rules)
        self.rules = [r for r in self.rules if r.id != rule_id]
        return len(self.rules) < before

    def get_rule(self, rule_id: str) -> ValidationRule | None:
        """Get a rule by ID."""
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None
