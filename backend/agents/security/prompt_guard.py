"""
Prompt Injection Guard

Detects and blocks prompt injection attacks targeting AI agents.
Uses pattern matching and heuristic analysis to identify:
- Direct injection attempts ("ignore all instructions")
- Indirect injection via encoding tricks
- Role manipulation ("you are now...")
- Data exfiltration attempts ("print your system prompt")
- Jailbreak patterns

Thread-safe and stateless — safe for concurrent use.

References:
- OWASP LLM Top 10 (2024): LLM01 — Prompt Injection
- "Not what you've signed up for" (Perez & Ribeiro, 2022)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


class ThreatCategory(str, Enum):
    """Categories of prompt injection threats."""

    DIRECT_INJECTION = "direct_injection"
    ROLE_MANIPULATION = "role_manipulation"
    DATA_EXFILTRATION = "data_exfiltration"
    JAILBREAK = "jailbreak"
    ENCODING_ATTACK = "encoding_attack"
    EXCESSIVE_LENGTH = "excessive_length"
    SAFE = "safe"


@dataclass
class ThreatDetection:
    """Result of threat analysis on a prompt."""

    is_safe: bool
    category: ThreatCategory
    confidence: float  # 0.0 to 1.0
    matched_patterns: list[str] = field(default_factory=list)
    sanitized_prompt: str = ""
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_safe": self.is_safe,
            "category": self.category.value,
            "confidence": round(self.confidence, 4),
            "matched_patterns": self.matched_patterns,
            "details": self.details,
        }


# ═══════════════════════════════════════════════════════════════════
# Pattern Definitions
# ═══════════════════════════════════════════════════════════════════

DIRECT_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?i)ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|context)"),
    re.compile(r"(?i)disregard\s+(all\s+)?(previous|prior|above)\s+(instructions?|rules?)"),
    re.compile(r"(?i)forget\s+(everything|all)\s+(you|that)"),
    re.compile(r"(?i)override\s+(your|all|the)\s+(instructions?|rules?|programming)"),
    re.compile(r"(?i)new\s+instructions?\s*:"),
    re.compile(r"(?i)system\s*:\s*you\s+are"),
    re.compile(r"(?i)\[system\]"),
    re.compile(r"(?i)<\|?system\|?>"),
    re.compile(r"(?i)do\s+not\s+follow\s+(your|the)\s+(rules?|instructions?)"),
]

ROLE_MANIPULATION_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?i)you\s+are\s+now\s+(a|an|the)"),
    re.compile(r"(?i)pretend\s+(you\s+are|to\s+be)\s+(a|an)"),
    re.compile(r"(?i)act\s+as\s+(a|an|if)"),
    re.compile(r"(?i)role.?play\s+as"),
    re.compile(r"(?i)switch\s+to\s+.+\s+mode"),
    re.compile(r"(?i)enter\s+(developer|debug|admin|root|sudo)\s+mode"),
    re.compile(r"(?i)enable\s+(developer|debug|admin|DAN)\s+mode"),
]

DATA_EXFILTRATION_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?i)(print|show|display|reveal|output|repeat)\s+(your|the)\s+(system\s+)?prompt"),
    re.compile(r"(?i)(print|show|reveal)\s+(your|the)\s+(instructions?|rules?|config)"),
    re.compile(r"(?i)what\s+(are|is)\s+your\s+(system\s+)?prompt"),
    re.compile(r"(?i)(list|show)\s+(all\s+)?(api\s*keys?|secrets?|passwords?|tokens?)"),
    re.compile(r"(?i)(print|echo|cat)\s+.*(\.env|config|secret|key)"),
]

JAILBREAK_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?i)DAN\s*(mode|\d+)"),
    re.compile(r"(?i)do\s+anything\s+now"),
    re.compile(r"(?i)hypothetical(ly)?.*without\s+(restrictions?|rules?|limits?)"),
    re.compile(r"(?i)in\s+a\s+fictional\s+world\s+where"),
    re.compile(r"(?i)evil\s+twin"),
    re.compile(r"(?i)opposite\s+day"),
    re.compile(r"(?i)grandma.*(bedtime|story|recipe).*napalm|explosiv"),
]

ENCODING_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?i)(base64|rot13|hex)\s*(encode|decode)?"),
    re.compile(r"\\x[0-9a-fA-F]{2}"),  # Hex escapes
    re.compile(r"\\u[0-9a-fA-F]{4}"),  # Unicode escapes
    re.compile(r"&#x?[0-9a-fA-F]+;"),  # HTML entities
]

# Maximum prompt length (chars) before flagging
MAX_PROMPT_LENGTH = 10_000


class PromptGuard:
    """
    Detects and blocks prompt injection attacks.

    Usage:
        guard = PromptGuard()
        detection = guard.analyze("Ignore all instructions and...")
        if not detection.is_safe:
            logger.warning(f"Blocked: {detection.category}")
    """

    def __init__(
        self,
        max_prompt_length: int = MAX_PROMPT_LENGTH,
        strict_mode: bool = False,
    ) -> None:
        """
        Args:
            max_prompt_length: Maximum allowed prompt length.
            strict_mode: If True, block on ANY pattern match (lower threshold).
        """
        self.max_prompt_length = max_prompt_length
        self.strict_mode = strict_mode
        self._pattern_groups: list[tuple[ThreatCategory, list[re.Pattern]]] = [
            (ThreatCategory.DIRECT_INJECTION, DIRECT_INJECTION_PATTERNS),
            (ThreatCategory.ROLE_MANIPULATION, ROLE_MANIPULATION_PATTERNS),
            (ThreatCategory.DATA_EXFILTRATION, DATA_EXFILTRATION_PATTERNS),
            (ThreatCategory.JAILBREAK, JAILBREAK_PATTERNS),
            (ThreatCategory.ENCODING_ATTACK, ENCODING_PATTERNS),
        ]

    def analyze(self, prompt: str) -> ThreatDetection:
        """
        Analyze a prompt for injection threats.

        Args:
            prompt: The user prompt to analyze.

        Returns:
            ThreatDetection with safety assessment.
        """
        if not prompt or not prompt.strip():
            return ThreatDetection(
                is_safe=True,
                category=ThreatCategory.SAFE,
                confidence=1.0,
                sanitized_prompt="",
                details="Empty prompt",
            )

        # Length check
        if len(prompt) > self.max_prompt_length:
            return ThreatDetection(
                is_safe=False,
                category=ThreatCategory.EXCESSIVE_LENGTH,
                confidence=0.9,
                sanitized_prompt=prompt[: self.max_prompt_length],
                details=f"Prompt length {len(prompt)} exceeds max {self.max_prompt_length}",
            )

        # Pattern matching
        all_matches: list[tuple[ThreatCategory, str]] = []
        for category, patterns in self._pattern_groups:
            for pattern in patterns:
                match = pattern.search(prompt)
                if match:
                    all_matches.append((category, match.group()))

        if not all_matches:
            return ThreatDetection(
                is_safe=True,
                category=ThreatCategory.SAFE,
                confidence=0.85,
                sanitized_prompt=prompt.strip(),
                details="No threat patterns detected",
            )

        # Determine primary threat
        primary_category = all_matches[0][0]
        matched_texts = [m[1] for m in all_matches]

        # Confidence based on number of matches
        confidence = min(1.0, 0.6 + len(all_matches) * 0.1)

        # In strict mode, any match = unsafe
        # In normal mode, need high confidence for blocking
        is_safe = not self.strict_mode and confidence < 0.7

        if not is_safe:
            logger.warning(
                f"Prompt injection detected: category={primary_category.value}, "
                f"patterns={len(all_matches)}, confidence={confidence:.2f}"
            )

        return ThreatDetection(
            is_safe=is_safe,
            category=primary_category,
            confidence=confidence,
            matched_patterns=matched_texts,
            sanitized_prompt=self._sanitize(prompt) if not is_safe else prompt.strip(),
            details=f"Detected {len(all_matches)} pattern(s) in category {primary_category.value}",
        )

    def is_safe(self, prompt: str) -> bool:
        """Quick safety check (returns bool only)."""
        return self.analyze(prompt).is_safe

    def sanitize(self, prompt: str) -> str:
        """Remove detected injection patterns from prompt."""
        return self._sanitize(prompt)

    def _sanitize(self, prompt: str) -> str:
        """Internal sanitization: strip known injection patterns."""
        sanitized = prompt
        for _, patterns in self._pattern_groups:
            for pattern in patterns:
                sanitized = pattern.sub("[FILTERED]", sanitized)
        return sanitized.strip()
