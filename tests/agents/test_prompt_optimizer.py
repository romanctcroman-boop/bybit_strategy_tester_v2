"""
Tests for Advanced Prompt Optimization

Run: pytest tests/agents/test_prompt_optimizer.py -v
"""

import sys

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

import pytest

from backend.agents.prompt_optimizer import (
    OptimizationResult,
    PromptOptimizer,
    QualityScore,
    get_prompt_optimizer,
)


class TestOptimizationResult:
    """Tests for OptimizationResult."""

    def test_token_savings_calculation(self):
        """Test token savings calculation."""
        result = OptimizationResult(
            original_prompt="test",
            optimized_prompt="test",
            original_tokens=1000,
            optimized_tokens=700,
            reduction_percent=30.0,
            quality_score=0.8,
        )

        assert result.token_savings == 300

    def test_to_dict(self):
        """Test conversion to dict."""
        result = OptimizationResult(
            original_prompt="original",
            optimized_prompt="optimized",
            original_tokens=100,
            optimized_tokens=80,
            reduction_percent=20.0,
            quality_score=0.9,
            changes=["Removed phrases"],
        )

        data = result.to_dict()

        assert data["original_tokens"] == 100
        assert data["optimized_tokens"] == 80
        assert data["token_savings"] == 20
        assert "Removed phrases" in data["changes"]


class TestQualityScore:
    """Tests for QualityScore."""

    def test_to_dict(self):
        """Test conversion to dict."""
        score = QualityScore(
            overall_score=0.85,
            clarity_score=0.9,
            specificity_score=0.8,
            completeness_score=0.85,
            conciseness_score=0.8,
            feedback=["Good quality"],
        )

        data = score.to_dict()

        assert data["overall_score"] == 0.85
        assert data["clarity_score"] == 0.9
        assert "Good quality" in data["feedback"]


class TestPromptOptimizer:
    """Tests for PromptOptimizer."""

    @pytest.fixture
    def optimizer(self):
        """Create optimizer instance."""
        return PromptOptimizer()

    def test_optimizer_initialization(self, optimizer):
        """Test optimizer initialization."""
        assert optimizer is not None
        assert optimizer._optimization_history == []
        assert optimizer._quality_history == []

    def test_optimize_prompt_basic(self, optimizer):
        """Test basic prompt optimization."""
        long_prompt = "Please note that I would be happy to help you with this very important task. " * 10

        result = optimizer.optimize_prompt(long_prompt)

        assert result.original_tokens > result.optimized_tokens
        assert result.reduction_percent > 0
        assert result.quality_score > 0
        assert len(result.changes) > 0

    def test_optimize_prompt_with_target(self, optimizer):
        """Test optimization with target tokens."""
        long_prompt = "Test prompt. " * 100

        result = optimizer.optimize_prompt(long_prompt, target_tokens=50)

        # Should attempt to truncate
        assert result.optimized_tokens <= result.original_tokens
        # Truncation may or may not add marker depending on content
        assert result.changes is not None

    def test_optimize_prompt_preserve_structure(self, optimizer):
        """Test optimization with structure preservation."""
        prompt = """
        EXAMPLE 1: This is a detailed example with lots of text.
        
        EXAMPLE 2: This is another detailed example.
        
        Please analyze these examples carefully.
        """

        result_preserve = optimizer.optimize_prompt(prompt, preserve_structure=True)
        result_no_preserve = optimizer.optimize_prompt(prompt, preserve_structure=False)

        # Structure preservation should keep more content
        assert len(result_preserve.optimized_prompt) >= len(result_no_preserve.optimized_prompt)

    def test_score_quality(self, optimizer):
        """Test quality scoring."""
        prompt = "Generate a Python function to calculate RSI with period 14"
        response = """
        def calculate_rsi(prices, period=14):
            # Calculate RSI
            gains = []
            losses = []
            for i in range(1, len(prices)):
                diff = prices[i] - prices[i-1]
                if diff > 0:
                    gains.append(diff)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(diff))
            # Continue implementation...
            return rsi
        """

        score = optimizer.score_quality(prompt, response)

        assert score.overall_score > 0
        assert score.clarity_score > 0
        assert score.specificity_score > 0
        assert score.completeness_score > 0
        assert score.conciseness_score > 0

    def test_score_quality_low_quality(self, optimizer):
        """Test quality scoring with low quality response."""
        prompt = "Generate a Python function to calculate RSI with detailed explanation"
        response = "Here's the function."

        score = optimizer.score_quality(prompt, response)

        # Should have low completeness
        assert score.completeness_score < 0.5

    def test_get_optimization_stats(self, optimizer):
        """Test getting optimization statistics."""
        # Run some optimizations
        optimizer.optimize_prompt("Test prompt 1")
        optimizer.optimize_prompt("Test prompt 2")

        stats = optimizer.get_optimization_stats()

        assert stats["total_optimizations"] == 2
        assert "avg_reduction_percent" in stats
        assert "avg_quality_score" in stats
        assert "total_tokens_saved" in stats

    def test_get_quality_stats(self, optimizer):
        """Test getting quality statistics."""
        # Run some quality scores
        optimizer.score_quality("prompt 1", "response 1")
        optimizer.score_quality("prompt 2", "response 2")

        stats = optimizer.get_quality_stats()

        assert stats["total_scores"] == 2
        assert "avg_overall_score" in stats
        assert "avg_clarity" in stats

    def test_remove_redundant_phrases(self, optimizer):
        """Test redundant phrase removal."""
        text = "Please note that I would be happy to help you. It is important to know that basically this works."

        optimized, count = optimizer._remove_redundant_phrases(text)

        assert count > 0
        assert "please note that" not in optimized.lower()
        assert "it is important to" not in optimized.lower()

    def test_replace_verbose_patterns(self, optimizer):
        """Test verbose pattern replacement."""
        text = "I would be happy to help you. Let me explain the process."

        optimized, count = optimizer._replace_verbose_patterns(text)

        assert count > 0
        assert "I would be happy to" not in optimized
        assert "Sure" in optimized or "I'll" in optimized

    def test_remove_unnecessary_whitespace(self, optimizer):
        """Test whitespace removal."""
        text = "Line 1\n\n\n\nLine 2\n\nLine 3"

        optimized, changed = optimizer._remove_unnecessary_whitespace(text)

        assert changed is True
        assert "\n\n\n" not in optimized

    def test_estimate_tokens(self, optimizer):
        """Test token estimation."""
        text = "This is a test prompt with some words."

        tokens = optimizer._estimate_tokens(text)

        # Should be approximately len/4
        assert tokens == len(text) // 4

    def test_score_clarity(self, optimizer):
        """Test clarity scoring."""
        clear_prompt = "Generate RSI function. Period 14. Input: prices list."
        unclear_prompt = "Can you please help me with something related to stuff and things?"

        clear_score = optimizer._score_clarity(clear_prompt)
        unclear_score = optimizer._score_clarity(unclear_prompt)

        assert clear_score > unclear_score

    def test_score_specificity(self, optimizer):
        """Test specificity scoring."""
        specific_prompt = "Generate Python function with exactly these parameters: period=14, prices=list"
        vague_prompt = "Make something that works good"

        specific_score = optimizer._score_specificity(specific_prompt)
        vague_score = optimizer._score_specificity(vague_prompt)

        assert specific_score > vague_score

    def test_optimization_history(self, optimizer):
        """Test optimization history tracking."""
        optimizer.optimize_prompt("Prompt 1")
        optimizer.optimize_prompt("Prompt 2")
        optimizer.optimize_prompt("Prompt 3")

        assert len(optimizer._optimization_history) == 3

    def test_quality_history(self, optimizer):
        """Test quality history tracking."""
        optimizer.score_quality("prompt 1", "response 1")
        optimizer.score_quality("prompt 2", "response 2")

        assert len(optimizer._quality_history) == 2

    def test_generate_recommendations(self, optimizer):
        """Test recommendation generation."""
        # Create a long prompt (>1000 tokens = >4000 chars)
        long_prompt = "Test word. " * 500  # ~1000 tokens

        optimized = "Test"

        recommendations = optimizer._generate_recommendations(long_prompt, optimized, quality_score=0.5)

        # Should have recommendations for low quality or long prompt
        assert len(recommendations) > 0


class TestGlobalOptimizer:
    """Tests for global optimizer functions."""

    def test_get_prompt_optimizer_singleton(self):
        """Test singleton pattern."""
        o1 = get_prompt_optimizer()
        o2 = get_prompt_optimizer()

        # Should be same instance
        assert o1 is o2


class TestIntegration:
    """Integration tests."""

    def test_full_optimization_workflow(self):
        """Test full optimization workflow."""
        optimizer = PromptOptimizer()

        # Create long prompt
        long_prompt = """
        Please note that I would be very happy if you could help me with this task.
        It is important to understand that we need to generate a trading strategy.
        Basically, the strategy should use RSI indicator with period 14.
        In order to achieve good results, we should also consider MACD.
        To summarize, please generate a complete strategy with entry and exit rules.
        
        EXAMPLE 1: Here's a detailed example of a strategy...
        (imagine lots of text here)
        
        EXAMPLE 2: And another detailed example...
        (more text)
        """

        # Optimize
        result = optimizer.optimize_prompt(long_prompt, target_tokens=100)

        # Verify optimization
        assert result.original_tokens > result.optimized_tokens
        assert result.reduction_percent > 0

        # Score quality
        response = "Generated strategy with RSI and MACD..."
        quality = optimizer.score_quality(result.optimized_prompt, response)

        assert quality.overall_score > 0

        # Get stats
        opt_stats = optimizer.get_optimization_stats()
        quality_stats = optimizer.get_quality_stats()

        assert opt_stats["total_optimizations"] == 1
        assert quality_stats["total_scores"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
