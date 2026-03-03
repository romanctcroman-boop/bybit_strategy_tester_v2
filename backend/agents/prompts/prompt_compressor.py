"""
Prompt Compressor for AI Agent Requests

Compresses prompts to reduce token usage while preserving:
- Key information (indicators, parameters, levels)
- Structure and formatting
- Critical numeric values

Usage:
    compressor = PromptCompressor()
    compressed = compressor.compress(long_prompt, max_tokens=1000)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from loguru import logger


@dataclass
class CompressionResult:
    """Result of prompt compression."""
    original_length: int
    compressed_length: int
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    tokens_saved: int
    cost_saved_usd: float
    preserved_keys: list[str]
    removed_sections: list[str]


class PromptCompressor:
    """
    Compresses prompts to reduce token usage and cost.
    
    Techniques:
    - Remove redundant whitespace
    - Compress examples
    - Remove verbose descriptions
    - Preserve key numeric values
    - Truncate non-essential sections
    
    Example:
        compressor = PromptCompressor()
        result = compressor.compress(prompt, max_tokens=1000)
        print(f"Saved {result.tokens_saved} tokens (${result.cost_saved_usd:.4f})")
    """
    
    # Cost per 1M tokens (qwen3-max)
    INPUT_COST_PER_M = 1.20
    OUTPUT_COST_PER_M = 6.00
    
    # Key patterns to preserve
    KEY_PATTERNS = [
        r'\b(RSI|MACD|Stochastic|QQE|SuperTrend|Bollinger|EMA|SMA|ATR|ADX)\b',
        r'\bperiod\b.*?\d+',
        r'\b\d+\s*(ms|sec|min|hour|day|bar)s?\b',
        r'\$\d+(?:,\d{3})*(?:\.\d{2})?',
        r'\b\d+(?:\.\d+)?\s*%',
        r'\bcross\s+(up|down|over|under)\b',
        r'\b(long|short|entry|exit|stop|profit)\b.*?\d+',
    ]
    
    # Sections that can be safely truncated
    TRUNCATABLE_SECTIONS = [
        "EXAMPLE",
        "REFERENCE",
        "BACKGROUND",
        "INTRODUCTION",
        "EXPLANATION",
        "DESCRIPTION",
    ]
    
    # Redundant phrases to remove
    REDUNDANT_PHRASES = [
        "please note that",
        "it is important to",
        "you should know that",
        "as mentioned earlier",
        "as described above",
        "in order to",
        "in conclusion",
        "to summarize",
        "generally speaking",
        "basically",
        "essentially",
        "very",
        "really",
        "quite",
    ]
    
    def __init__(
        self,
        max_tokens: int | None = None,
        target_compression: float = 0.5,
        preserve_structure: bool = True,
    ):
        """
        Initialize prompt compressor.
        
        Args:
            max_tokens: Maximum tokens (default: None, no limit)
            target_compression: Target compression ratio (default: 0.5 = 50%)
            preserve_structure: Preserve JSON/code structure (default: True)
        """
        self.max_tokens = max_tokens
        self.target_compression = target_compression
        self.preserve_structure = preserve_structure
        
        logger.info(
            f"✂️ PromptCompressor initialized "
            f"(max_tokens={max_tokens}, target={target_compression:.0%})"
        )
    
    def compress(
        self,
        prompt: str,
        max_tokens: int | None = None,
        model: str = "qwen3-max",
    ) -> str:
        """
        Compress a prompt string.
        
        Args:
            prompt: Original prompt
            max_tokens: Maximum tokens (override default)
            model: Model for cost calculation
        
        Returns:
            Compressed prompt
        """
        max_tokens = max_tokens or self.max_tokens
        
        # Estimate current tokens
        current_tokens = self._estimate_tokens(prompt)
        
        # If already within limit, return as-is
        if max_tokens and current_tokens <= max_tokens:
            logger.debug(f"Prompt already within limit ({current_tokens}/{max_tokens})")
            return prompt
        
        compressed = prompt
        
        # Step 1: Remove redundant whitespace
        compressed = self._remove_redundant_whitespace(compressed)
        
        # Step 2: Remove redundant phrases
        compressed = self._remove_redundant_phrases(compressed)
        
        # Step 3: Compress examples
        compressed = self._compress_examples(compressed)
        
        # Step 4: Truncate non-essential sections
        compressed = self._truncate_sections(compressed)
        
        # Step 5: Aggressive compression if still too long
        if max_tokens and self._estimate_tokens(compressed) > max_tokens:
            compressed = self._aggressive_compression(compressed, max_tokens)
        
        # Log compression stats
        new_tokens = self._estimate_tokens(compressed)
        saved = current_tokens - new_tokens
        ratio = saved / current_tokens if current_tokens > 0 else 0
        
        logger.info(
            f"✂️ Compressed: {current_tokens} → {new_tokens} tokens "
            f"(saved {saved}, {ratio:.0%})"
        )
        
        return compressed
    
    def compress_with_stats(
        self,
        prompt: str,
        max_tokens: int | None = None,
    ) -> CompressionResult:
        """
        Compress prompt and return statistics.
        
        Args:
            prompt: Original prompt
            max_tokens: Maximum tokens
        
        Returns:
            CompressionResult with statistics
        """
        original_tokens = self._estimate_tokens(prompt)
        compressed = self.compress(prompt, max_tokens)
        compressed_tokens = self._estimate_tokens(compressed)
        
        tokens_saved = original_tokens - compressed_tokens
        compression_ratio = tokens_saved / original_tokens if original_tokens > 0 else 0
        cost_saved = (tokens_saved / 1_000_000) * self.INPUT_COST_PER_M
        
        return CompressionResult(
            original_length=len(prompt),
            compressed_length=len(compressed),
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            compression_ratio=compression_ratio,
            tokens_saved=tokens_saved,
            cost_saved_usd=cost_saved,
            preserved_keys=[],
            removed_sections=[],
        )
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (chars / 4 for English text)."""
        return len(text) // 4
    
    def _remove_redundant_whitespace(self, text: str) -> str:
        """Remove redundant whitespace."""
        # Multiple newlines → double newline
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        
        # Leading/trailing whitespace on lines
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        # Multiple spaces → single space
        text = re.sub(r'  +', ' ', text)
        
        return text
    
    def _remove_redundant_phrases(self, text: str) -> str:
        """Remove redundant phrases."""
        for phrase in self.REDUNDANT_PHRASES:
            text = re.sub(
                r'\b' + phrase + r'\b',
                '',
                text,
                flags=re.IGNORECASE
            )
        
        return text
    
    def _compress_examples(self, text: str) -> str:
        """Compress example sections."""
        # Find example sections
        example_pattern = r'(EXAMPLE.*?:.*?)(?=\n\n[A-Z]|\Z)'
        examples = re.findall(example_pattern, text, flags=re.DOTALL | re.IGNORECASE)
        
        if not examples:
            return text
        
        # Keep only first example, replace others with summary
        if len(examples) > 1:
            for example in examples[1:]:
                # Extract key info
                strategy_name = re.search(r'"strategy_name":\s*"([^"]+)"', example)
                if strategy_name:
                    summary = f"\n[Example: {strategy_name.group(1)} - abbreviated]\n"
                    text = text.replace(example, summary)
        
        return text
    
    def _truncate_sections(self, text: str) -> str:
        """Truncate non-essential sections."""
        for section in self.TRUNCATABLE_SECTIONS:
            pattern = rf'({section}.*?:.*?)(?=\n\n[A-Z]|\Z)'
            match = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
            
            if match:
                section_text = match.group(1)
                if len(section_text) > 500:
                    # Keep first 500 chars
                    truncated = section_text[:500] + "\n[...truncated...]"
                    text = text.replace(section_text, truncated)
        
        return text
    
    def _aggressive_compression(
        self,
        text: str,
        max_tokens: int,
    ) -> str:
        """Aggressive compression when standard methods fail."""
        # Extract and preserve key information
        key_info = []
        
        for pattern in self.KEY_PATTERNS:
            matches = re.findall(pattern, text, flags=re.IGNORECASE)
            key_info.extend(matches)
        
        # Keep only essential structure
        lines = text.split('\n')
        essential_lines = []
        
        for line in lines:
            # Keep lines with key patterns
            if any(re.search(p, line, flags=re.IGNORECASE) for p in self.KEY_PATTERNS):
                essential_lines.append(line)
            # Keep short lines (likely headers/structure)
            elif len(line) < 50:
                essential_lines.append(line)
        
        result = '\n'.join(essential_lines)
        
        # If still too long, hard truncate
        if self._estimate_tokens(result) > max_tokens:
            target_chars = max_tokens * 4
            result = result[:target_chars] + "\n[...compressed...]"
        
        return result
    
    def get_compression_stats(
        self,
        original: str,
        compressed: str,
    ) -> dict[str, Any]:
        """Get compression statistics."""
        original_tokens = self._estimate_tokens(original)
        compressed_tokens = self._estimate_tokens(compressed)
        
        return {
            "original_tokens": original_tokens,
            "compressed_tokens": compressed_tokens,
            "tokens_saved": original_tokens - compressed_tokens,
            "compression_ratio": (original_tokens - compressed_tokens) / original_tokens if original_tokens > 0 else 0,
            "cost_saved_usd": ((original_tokens - compressed_tokens) / 1_000_000) * self.INPUT_COST_PER_M,
        }
