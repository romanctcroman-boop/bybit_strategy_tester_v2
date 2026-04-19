"""
Prompt Validator for AI Agent Requests

Validates prompts before sending to LLM APIs:
- Injection attack detection
- Length validation
- Structure validation
- Content safety checks

Usage:
    validator = PromptValidator()
    is_valid, errors = validator.validate_prompt(prompt)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class ValidationResult:
    """Result of prompt validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sanitized_prompt: str | None = None


class PromptValidator:
    """
    Validates prompts for safety and correctness before LLM API calls.

    Checks:
    - Prompt injection attacks
    - Length limits
    - Required structure
    - Content safety

    Example:
        validator = PromptValidator()
        is_valid, errors = validator.validate_prompt(prompt)
        if not is_valid:
            raise ValueError(f"Invalid prompt: {errors}")
    """

    # Maximum prompt length (tokens approximated as chars / 4)
    MAX_PROMPT_LENGTH = 50000  # ~12500 tokens
    MIN_PROMPT_LENGTH = 10

    # Injection patterns (case-insensitive)
    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"disregard\s+(all\s+)?previous",
        r"forget\s+(all\s+)?previous",
        r"output\s+(all\s+)?(api\s+)?keys",
        r"print\s+(your\s+)?(api\s+)?key",
        r"execute\s+code",
        r"run\s+this\s+code",
        r"<script>",
        r"eval\s*\(",
        r"function\s*\(",
        r"system\s+prompt",
        r"your\s+instructions",
        r"bypass\s+security",
        r"override\s+rules",
        r"act\s+as\s+(a\s+)?different",
        r"pretend\s+to\s+be",
        r"role\s+play\s+as",
    ]

    # Sensitive data patterns
    SENSITIVE_PATTERNS = [
        r"sk-[a-zA-Z0-9]{32,}",  # API keys
        r"Bearer\s+[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+",  # JWT tokens
        r"password\s*[=:]\s*\S+",  # Passwords
        r"secret\s*[=:]\s*\S+",  # Secrets
    ]

    def __init__(
        self,
        max_length: int | None = None,
        min_length: int | None = None,
        block_injections: bool = True,
        block_sensitive_data: bool = True,
    ):
        """
        Initialize prompt validator.

        Args:
            max_length: Maximum prompt length (default: 50000)
            min_length: Minimum prompt length (default: 10)
            block_injections: Block injection attempts (default: True)
            block_sensitive_data: Block sensitive data (default: True)
        """
        self.max_length = max_length or self.MAX_PROMPT_LENGTH
        self.min_length = min_length or self.MIN_PROMPT_LENGTH
        self.block_injections = block_injections
        self.block_sensitive_data = block_sensitive_data

        # Compile regex patterns
        self._injection_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.INJECTION_PATTERNS]
        self._sensitive_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.SENSITIVE_PATTERNS]

        logger.info(f"🛡️ PromptValidator initialized (max_len={self.max_length}, injections={block_injections})")

    def validate_prompt(
        self,
        prompt: str,
        check_structure: bool = True,
    ) -> tuple[bool, list[str]]:
        """
        Validate a prompt string.

        Args:
            prompt: Prompt text to validate
            check_structure: Whether to check structure (default: True)

        Returns:
            Tuple of (is_valid, errors)
        """
        result = ValidationResult(is_valid=True)

        # Check 1: Length validation
        self._check_length(prompt, result)

        # Check 2: Injection detection
        if self.block_injections:
            self._check_injections(prompt, result)

        # Check 3: Sensitive data detection
        if self.block_sensitive_data:
            self._check_sensitive_data(prompt, result)

        # Check 4: Structure validation
        if check_structure:
            self._check_structure(prompt, result)

        # Sanitize if there were issues
        if result.errors or result.warnings:
            result.sanitized_prompt = self._sanitize_prompt(prompt)

        return result.is_valid, result.errors

    def validate_or_raise(
        self,
        prompt: str,
        exception_class: type[Exception] = ValueError,
    ) -> str:
        """
        Validate prompt and raise exception if invalid.

        Args:
            prompt: Prompt text to validate
            exception_class: Exception type to raise

        Returns:
            Sanitized prompt if valid

        Raises:
            exception_class: If prompt is invalid
        """
        is_valid, errors = self.validate_prompt(prompt)

        if not is_valid:
            error_msg = "; ".join(errors)
            logger.error(f"🚫 Prompt validation failed: {error_msg}")
            raise exception_class(f"Prompt validation failed: {error_msg}")

        # Return sanitized version
        result = self.validate_prompt(prompt)
        return (result[1] and result.sanitized_prompt) or prompt

    def _check_length(self, prompt: str, result: ValidationResult) -> None:
        """Check prompt length."""
        length = len(prompt)

        if length < self.min_length:
            result.errors.append(f"Prompt too short: {length} chars (min: {self.min_length})")
            result.is_valid = False

        if length > self.max_length:
            result.errors.append(f"Prompt too long: {length} chars (max: {self.max_length})")
            result.is_valid = False

        # Warning for long prompts
        elif length > self.max_length * 0.8:
            result.warnings.append(f"Prompt approaching length limit: {length}/{self.max_length}")

    def _check_injections(self, prompt: str, result: ValidationResult) -> None:
        """Check for prompt injection attempts."""
        for i, pattern in enumerate(self._injection_regex):
            match = pattern.search(prompt)
            if match:
                pattern_str = self.INJECTION_PATTERNS[i]
                result.errors.append(f"Injection attempt detected: '{pattern_str}'")
                result.is_valid = False
                logger.warning(f"🚫 Prompt injection blocked: {pattern_str}")

    def _check_sensitive_data(self, prompt: str, result: ValidationResult) -> None:
        """Check for sensitive data leakage."""
        for i, pattern in enumerate(self._sensitive_regex):
            match = pattern.search(prompt)
            if match:
                pattern_str = self.SENSITIVE_PATTERNS[i]
                result.errors.append(f"Sensitive data detected: '{pattern_str}'")
                result.is_valid = False
                logger.warning(f"🚫 Sensitive data blocked: {pattern_str}")

    def _check_structure(self, prompt: str, result: ValidationResult) -> None:
        """Check prompt structure."""
        # Check for empty prompt
        if not prompt.strip():
            result.errors.append("Prompt is empty")
            result.is_valid = False

        # Check for only whitespace
        elif len(prompt.strip()) < self.min_length:
            result.errors.append(f"Prompt contains only whitespace ({len(prompt)} chars)")
            result.is_valid = False

        # Check for balanced brackets (basic check)
        if prompt.count("{") != prompt.count("}"):
            result.warnings.append("Unbalanced curly braces in prompt")

        if prompt.count("[") != prompt.count("]"):
            result.warnings.append("Unbalanced square brackets in prompt")

    def _sanitize_prompt(self, prompt: str) -> str:
        """
        Sanitize prompt by removing/replacing unsafe content.

        Args:
            prompt: Original prompt

        Returns:
            Sanitized prompt
        """
        sanitized = prompt

        # Replace injection patterns
        for pattern in self._injection_regex:
            sanitized = pattern.sub("[INJECTION_BLOCKED]", sanitized)

        # Replace sensitive data
        for pattern in self._sensitive_regex:
            sanitized = pattern.sub("[SENSITIVE_BLOCKED]", sanitized)

        return sanitized

    def get_validation_stats(self) -> dict[str, Any]:
        """Get validation statistics."""
        return {
            "max_length": self.max_length,
            "min_length": self.min_length,
            "injection_patterns": len(self.INJECTION_PATTERNS),
            "sensitive_patterns": len(self.SENSITIVE_PATTERNS),
            "block_injections": self.block_injections,
            "block_sensitive_data": self.block_sensitive_data,
        }
