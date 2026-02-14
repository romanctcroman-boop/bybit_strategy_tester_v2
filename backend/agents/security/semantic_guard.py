"""
Semantic Prompt Guard

Extends regex-based PromptGuard with semantic analysis for prompt injection detection.
Addresses audit finding: "PromptGuard regex-only is vulnerable to semantic jailbreaks" (Qwen, P1)

Approach:
- Layer 1: Fast regex patterns (existing)
- Layer 2: Heuristic semantic checks (keyword density, role confusion detection)
- Layer 3: Structure analysis (suspicious formatting patterns)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class GuardResult:
    """Result of prompt guard analysis."""

    is_safe: bool
    risk_score: float  # 0.0 = safe, 1.0 = definitely malicious
    blocked_reason: str | None = None
    layer: str | None = None  # which layer caught it: regex, semantic, structure
    details: dict[str, Any] | None = None


# Regex patterns for fast detection (Layer 1)
UNSAFE_REGEX_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"output\s+(all\s+)?(api\s+)?keys",
    r"execute\s+code",
    r"<script>",
    r"eval\(",
    r"forget\s+(all\s+)?previous",
    r"disregard\s+",
    r"you\s+are\s+(now|actually)\s+a",
    r"pretend\s+(you\s+are|to\s+be)",
    r"new\s+instructions?\s*:",
    r"system\s+prompt\s*:",
    r"reveal\s+(your|the)\s+(system|original)\s+(prompt|instructions)",
    r"bypass\s+(all\s+)?(safety|security|filter)",
]

# Semantic keywords that indicate prompt injection attempts (Layer 2)
INJECTION_KEYWORDS = {
    "role_confusion": [
        "you are now",
        "you're now",
        "act as",
        "pretend to be",
        "new role",
        "change your role",
        "forget you are",
        "you are actually",
        "your real purpose",
        "true identity",
    ],
    "instruction_override": [
        "ignore previous",
        "disregard above",
        "override instructions",
        "new instructions",
        "forget everything",
        "reset context",
        "start fresh",
        "begin new session",
        "previous instructions don't apply",
    ],
    "data_exfiltration": [
        "show me your prompt",
        "reveal system prompt",
        "display instructions",
        "output your rules",
        "print your guidelines",
        "show configuration",
        "list all api keys",
        "show environment variables",
    ],
    "code_execution": [
        "execute this code",
        "run this script",
        "eval this",
        "import os",
        "subprocess",
        "__import__",
        "exec(",
    ],
}

# Suspicious structural patterns (Layer 3)
STRUCTURE_PATTERNS = [
    # Markdown/formatting tricks to inject system-level instructions
    r"```system\n",
    r"\[SYSTEM\]",
    r"<\|im_start\|>system",
    r"<\|endoftext\|>",
    r"### System:",
    # Base64 encoded payloads
    r"base64\s*:\s*[A-Za-z0-9+/=]{50,}",
    # Unicode tricks
    r"[\u200b\u200c\u200d\ufeff]",  # Zero-width characters
]


class SemanticPromptGuard:
    """
    Multi-layer prompt injection guard.

    Layer 1: Fast regex pattern matching
    Layer 2: Semantic keyword density analysis
    Layer 3: Structure/formatting analysis

    Example:
        guard = SemanticPromptGuard()
        result = guard.check("Please analyze this trading strategy")
        if not result.is_safe:
            logger.warning(f"Blocked: {result.blocked_reason}")
    """

    def __init__(
        self,
        *,
        enable_semantic: bool = True,
        enable_structure: bool = True,
        keyword_threshold: int = 2,
        strict_mode: bool = False,
    ):
        self.enable_semantic = enable_semantic
        self.enable_structure = enable_structure
        self.keyword_threshold = keyword_threshold
        self.strict_mode = strict_mode
        # In strict mode, lower the keyword threshold for more aggressive detection
        if self.strict_mode:
            self.keyword_threshold = max(1, keyword_threshold - 1)
        self._compiled_regex = [re.compile(p, re.IGNORECASE) for p in UNSAFE_REGEX_PATTERNS]
        self._compiled_structure = [re.compile(p, re.IGNORECASE) for p in STRUCTURE_PATTERNS]

    def check(self, text: str) -> GuardResult:
        """
        Check text for prompt injection attempts.

        Args:
            text: Input text to check

        Returns:
            GuardResult with safety assessment
        """
        if not text:
            return GuardResult(is_safe=True, risk_score=0.0)

        # Layer 1: Fast regex check
        result = self._check_regex(text)
        if not result.is_safe:
            return result

        # Layer 2: Semantic keyword check
        if self.enable_semantic:
            result = self._check_semantic(text)
            if not result.is_safe:
                return result

        # Layer 3: Structure check
        if self.enable_structure:
            result = self._check_structure(text)
            if not result.is_safe:
                return result

        return GuardResult(is_safe=True, risk_score=0.0)

    def _check_regex(self, text: str) -> GuardResult:
        """Layer 1: Fast regex pattern matching."""
        for pattern in self._compiled_regex:
            match = pattern.search(text)
            if match:
                return GuardResult(
                    is_safe=False,
                    risk_score=0.9,
                    blocked_reason=f"Regex match: {match.group()}",
                    layer="regex",
                    details={"pattern": pattern.pattern, "match": match.group()},
                )
        return GuardResult(is_safe=True, risk_score=0.0)

    def _check_semantic(self, text: str) -> GuardResult:
        """Layer 2: Semantic keyword density analysis."""
        text_lower = text.lower()
        matches: dict[str, list[str]] = {}
        total_matches = 0

        for category, keywords in INJECTION_KEYWORDS.items():
            found = [kw for kw in keywords if kw in text_lower]
            if found:
                matches[category] = found
                total_matches += len(found)

        if total_matches >= self.keyword_threshold:
            risk_score = min(1.0, total_matches * 0.15)
            categories = list(matches.keys())
            return GuardResult(
                is_safe=False,
                risk_score=risk_score,
                blocked_reason=(f"Semantic injection detected: {total_matches} keywords across {categories}"),
                layer="semantic",
                details={"matches": matches, "total_keywords": total_matches},
            )

        return GuardResult(is_safe=True, risk_score=min(0.3, total_matches * 0.1))

    def _check_structure(self, text: str) -> GuardResult:
        """Layer 3: Structural pattern analysis."""
        for pattern in self._compiled_structure:
            match = pattern.search(text)
            if match:
                return GuardResult(
                    is_safe=False,
                    risk_score=0.8,
                    blocked_reason=f"Structural injection: {match.group()!r}",
                    layer="structure",
                    details={"pattern": pattern.pattern, "match": match.group()},
                )

        return GuardResult(is_safe=True, risk_score=0.0)

    def sanitize(self, text: str) -> str:
        """Sanitize text by replacing detected injection patterns."""
        if not text:
            return text

        result = text
        for pattern in self._compiled_regex:
            result = pattern.sub("[REDACTED]", result)

        return result


# Singleton
_guard: SemanticPromptGuard | None = None


def get_prompt_guard() -> SemanticPromptGuard:
    """Get global prompt guard singleton."""
    global _guard
    if _guard is None:
        try:
            from backend.agents.config_validator import get_agent_config

            config = get_agent_config()
            _guard = SemanticPromptGuard(
                enable_semantic=config.security.enable_semantic_guard,
            )
        except Exception:
            _guard = SemanticPromptGuard()
    return _guard
