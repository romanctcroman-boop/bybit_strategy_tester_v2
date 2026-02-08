"""
Self-Reflection Engine for Metacognitive AI Agents

Implements structured self-reflection patterns for autonomous improvement:
- Task Analysis: Understanding what was challenging
- Solution Evaluation: Rating own performance
- Improvement Planning: Identifying what to do better
- Knowledge Gap Detection: Finding missing knowledge
- Pattern Extraction: Learning from past experiences

Inspired by:
- Reflexion (Shinn et al., 2023)
- Self-Refine (Madaan et al., 2023)
- Constitutional AI reflection patterns
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class ReflectionResult:
    """Result of a single reflection session"""

    id: str
    task: str
    solution: str
    outcome: dict[str, Any]
    reflections: dict[str, str]
    quality_score: float
    lessons_learned: list[str]
    improvement_actions: list[str]
    knowledge_gaps: list[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task": self.task,
            "solution": self.solution[:500] + "..."
            if len(self.solution) > 500
            else self.solution,
            "outcome": self.outcome,
            "reflections": self.reflections,
            "quality_score": self.quality_score,
            "lessons_learned": self.lessons_learned,
            "improvement_actions": self.improvement_actions,
            "knowledge_gaps": self.knowledge_gaps,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Pattern:
    """A recurring pattern extracted from reflections"""

    id: str
    description: str
    frequency: int
    success_rate: float
    contexts: list[str]
    recommendations: list[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_seen: datetime = field(default_factory=lambda: datetime.now(UTC))


class SelfReflectionEngine:
    """
    Metacognitive self-reflection for autonomous improvement

    Implements structured reflection following cognitive science patterns:
    1. What happened? (observation)
    2. What worked / didn't work? (analysis)
    3. Why? (reasoning)
    4. What would I do differently? (planning)
    5. What do I need to learn? (gap identification)

    Example:
        reflection = SelfReflectionEngine(persist_path="./reflections")

        # Reflect on completed task
        result = await reflection.reflect_on_task(
            task="Generate RSI strategy code",
            solution=generated_code,
            outcome={"success": True, "tests_passed": 5}
        )

        # Extract patterns from history
        patterns = await reflection.extract_patterns(n_recent=50)

        # Generate improvement recommendations
        recommendations = await reflection.get_recommendations()
    """

    # Structured reflection prompts
    REFLECTION_PROMPTS = {
        "task_analysis": (
            "Analyze the task: What was the main challenge? "
            "What skills/knowledge did it require?"
        ),
        "solution_quality": (
            "Rate the solution quality (1-10). What are its strengths and weaknesses?"
        ),
        "what_worked": (
            "What approaches/strategies worked well in this task? "
            "What should be repeated?"
        ),
        "what_didnt_work": (
            "What didn't work as expected? What caused difficulties or errors?"
        ),
        "improvement": (
            "What would I do differently next time? "
            "What specific changes would improve the outcome?"
        ),
        "knowledge_gap": (
            "What knowledge or skills were missing that would have helped? "
            "What should be learned or practiced?"
        ),
        "transferable_lessons": (
            "What lessons from this task apply to other situations? "
            "What patterns should be remembered?"
        ),
    }

    def __init__(
        self,
        persist_path: str | None = None,
        reflection_fn: Callable | None = None,
    ):
        """
        Initialize self-reflection engine

        Args:
            persist_path: Path for persisting reflections
            reflection_fn: Optional async function to generate reflections
                          (prompt, task, solution) -> reflection_text
        """
        self.persist_path = Path(persist_path) if persist_path else None
        self.reflection_fn = reflection_fn

        self.reflection_history: list[ReflectionResult] = []
        self.patterns: dict[str, Pattern] = {}

        # Statistics
        self.stats = {
            "total_reflections": 0,
            "avg_quality_score": 0.0,
            "patterns_extracted": 0,
            "lessons_accumulated": 0,
        }

        # Load persisted data
        if self.persist_path:
            self._load_history()

        logger.info("🪞 Self-Reflection Engine initialized")

    async def reflect_on_task(
        self,
        task: str,
        solution: str,
        outcome: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> ReflectionResult:
        """
        Perform structured reflection on a completed task

        Args:
            task: Description of the task
            solution: The solution/output produced
            outcome: Results/metrics from the task
            context: Optional additional context

        Returns:
            ReflectionResult with structured insights
        """
        import uuid

        reflections = {}

        # Generate reflection for each prompt
        for key, prompt in self.REFLECTION_PROMPTS.items():
            reflection = await self._generate_reflection(
                prompt=prompt,
                task=task,
                solution=solution,
                outcome=outcome,
            )
            reflections[key] = reflection

        # Extract quality score from solution_quality reflection
        quality_score = self._extract_quality_score(
            reflections.get("solution_quality", "")
        )

        # Extract structured lessons
        lessons_learned = self._extract_lessons(reflections)

        # Extract improvement actions
        improvement_actions = self._extract_actions(reflections.get("improvement", ""))

        # Extract knowledge gaps
        knowledge_gaps = self._extract_gaps(reflections.get("knowledge_gap", ""))

        result = ReflectionResult(
            id=f"ref_{uuid.uuid4().hex[:12]}",
            task=task,
            solution=solution,
            outcome=outcome,
            reflections=reflections,
            quality_score=quality_score,
            lessons_learned=lessons_learned,
            improvement_actions=improvement_actions,
            knowledge_gaps=knowledge_gaps,
        )

        # Add to history
        self.reflection_history.append(result)
        self._update_stats()

        # Persist
        if self.persist_path:
            self._persist_reflection(result)

        # Update patterns
        await self._update_patterns(result)

        logger.info(
            f"🪞 Reflection complete: quality={quality_score:.1f}, "
            f"lessons={len(lessons_learned)}, gaps={len(knowledge_gaps)}"
        )

        return result

    async def extract_patterns(self, n_recent: int = 100) -> list[Pattern]:
        """
        Extract recurring patterns from recent reflections

        Args:
            n_recent: Number of recent reflections to analyze

        Returns:
            List of extracted patterns
        """
        recent = self.reflection_history[-n_recent:] if self.reflection_history else []

        if len(recent) < 3:
            logger.info("Need more reflections for pattern extraction")
            return []

        # Collect all lessons and actions
        all_lessons: dict[str, list[tuple[str, float]]] = {}
        all_contexts: dict[str, list[str]] = {}

        for reflection in recent:
            for lesson in reflection.lessons_learned:
                # Normalize lesson text
                key = self._normalize_text(lesson)
                if key not in all_lessons:
                    all_lessons[key] = []
                    all_contexts[key] = []
                all_lessons[key].append((lesson, reflection.quality_score))
                all_contexts[key].append(reflection.task[:100])

        # Find patterns (lessons that appear multiple times)
        new_patterns = []
        for key, occurrences in all_lessons.items():
            if len(occurrences) >= 2:  # Minimum frequency for pattern
                scores = [s for _, s in occurrences]
                avg_score = statistics.mean(scores) if scores else 0.0

                # Original lesson text from first occurrence
                original = occurrences[0][0]

                pattern = Pattern(
                    id=f"pat_{hash(key) % 10000:04d}",
                    description=original,
                    frequency=len(occurrences),
                    success_rate=avg_score / 10,  # Normalize to 0-1
                    contexts=list(set(all_contexts[key]))[:5],
                    recommendations=self._generate_recommendations(key, occurrences),
                )

                # Store pattern
                self.patterns[pattern.id] = pattern
                new_patterns.append(pattern)

        self.stats["patterns_extracted"] = len(self.patterns)

        logger.info(
            f"🔍 Extracted {len(new_patterns)} patterns from {len(recent)} reflections"
        )
        return new_patterns

    async def get_recommendations(
        self,
        current_task: str | None = None,
        top_k: int = 5,
    ) -> list[str]:
        """
        Get improvement recommendations based on reflection history

        Args:
            current_task: Optional current task for context-aware recommendations
            top_k: Number of recommendations to return
        """
        recommendations = []

        # Most common improvement actions
        action_counts: dict[str, int] = {}
        for reflection in self.reflection_history[-50:]:
            for action in reflection.improvement_actions:
                normalized = self._normalize_text(action)
                action_counts[normalized] = action_counts.get(normalized, 0) + 1

        # Sort by frequency
        sorted_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)

        for action, count in sorted_actions[:top_k]:
            recommendations.append(f"[Frequency: {count}] {action}")

        # Add pattern-based recommendations
        for pattern in sorted(
            self.patterns.values(),
            key=lambda p: p.frequency * p.success_rate,
            reverse=True,
        )[:3]:
            for rec in pattern.recommendations[:2]:
                if rec not in recommendations:
                    recommendations.append(rec)

        return recommendations[:top_k]

    async def get_knowledge_gaps_summary(self) -> dict[str, int]:
        """Get summary of identified knowledge gaps"""
        gap_counts: dict[str, int] = {}

        for reflection in self.reflection_history:
            for gap in reflection.knowledge_gaps:
                normalized = self._normalize_text(gap)
                gap_counts[normalized] = gap_counts.get(normalized, 0) + 1

        return dict(sorted(gap_counts.items(), key=lambda x: x[1], reverse=True)[:20])

    async def generate_training_data(self, min_quality: float = 7.0) -> list[dict]:
        """
        Generate training data from high-quality reflections

        This implements the "Self-Data Generation" pattern where agents
        create their own training examples from successful interactions.

        Args:
            min_quality: Minimum quality score to include
        """
        training_data = []

        for reflection in self.reflection_history:
            if reflection.quality_score >= min_quality:
                training_data.append(
                    {
                        "task": reflection.task,
                        "solution": reflection.solution,
                        "quality": reflection.quality_score,
                        "lessons": reflection.lessons_learned,
                        "context": {
                            "what_worked": reflection.reflections.get(
                                "what_worked", ""
                            ),
                        },
                    }
                )

        logger.info(f"📚 Generated {len(training_data)} training examples")
        return training_data

    async def _generate_reflection(
        self,
        prompt: str,
        task: str,
        solution: str,
        outcome: dict[str, Any],
    ) -> str:
        """Generate reflection using custom function or heuristics"""
        if self.reflection_fn:
            try:
                return await self.reflection_fn(prompt, task, solution)
            except Exception as e:
                logger.warning(f"Reflection function failed: {e}")

        # Fallback: Simple heuristic-based reflection
        return self._heuristic_reflect(prompt, task, solution, outcome)

    def _heuristic_reflect(
        self,
        prompt: str,
        task: str,
        solution: str,
        outcome: dict[str, Any],
    ) -> str:
        """Simple heuristic-based reflection"""
        success = outcome.get("success", True)
        errors = outcome.get("errors", [])

        if "quality" in prompt.lower():
            if success and not errors:
                return "Quality: 8/10. The solution addresses the task requirements clearly."
            elif success:
                return "Quality: 6/10. The solution works but has some minor issues."
            else:
                return "Quality: 4/10. The solution has significant problems."

        if "challenge" in prompt.lower():
            return "The main challenge was understanding the requirements and implementing correctly."

        if "worked" in prompt.lower() and "didnt" not in prompt.lower():
            return "Systematic approach and breaking down the problem worked well."

        if "didnt" in prompt.lower() or "didn't" in prompt.lower():
            if errors:
                return (
                    f"Issues encountered: {', '.join(str(e)[:50] for e in errors[:3])}"
                )
            return "No major issues identified."

        if "improvement" in prompt.lower():
            return "More testing and validation would improve future solutions."

        if "knowledge" in prompt.lower() or "gap" in prompt.lower():
            return "Could benefit from deeper domain knowledge."

        if "lesson" in prompt.lower():
            return "Always validate solutions and consider edge cases."

        return "Reflection in progress."

    def _extract_quality_score(self, text: str) -> float:
        """Extract quality score from reflection text"""
        import re

        # Look for patterns like "8/10", "Quality: 7", "score: 6.5"
        patterns = [
            r"(\d+(?:\.\d+)?)\s*/\s*10",
            r"[Qq]uality[:\s]+(\d+(?:\.\d+)?)",
            r"[Ss]core[:\s]+(\d+(?:\.\d+)?)",
            r"rate[d]?\s+(\d+(?:\.\d+)?)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                score = float(match.group(1))
                return min(10.0, max(0.0, score))

        # Default based on keywords
        if any(w in text.lower() for w in ["excellent", "great", "outstanding"]):
            return 8.5
        elif any(w in text.lower() for w in ["good", "well", "solid"]):
            return 7.0
        elif any(w in text.lower() for w in ["ok", "acceptable", "adequate"]):
            return 5.5
        elif any(w in text.lower() for w in ["poor", "bad", "issues"]):
            return 3.5

        return 6.0  # Default neutral score

    def _extract_lessons(self, reflections: dict[str, str]) -> list[str]:
        """Extract lessons learned from reflections"""
        lessons = []

        # Extract from what_worked
        worked = reflections.get("what_worked", "")
        if worked:
            sentences = worked.replace("\n", ". ").split(". ")
            lessons.extend([s.strip() for s in sentences if len(s.strip()) > 20][:3])

        # Extract from transferable_lessons
        transferable = reflections.get("transferable_lessons", "")
        if transferable:
            sentences = transferable.replace("\n", ". ").split(". ")
            lessons.extend([s.strip() for s in sentences if len(s.strip()) > 20][:3])

        return list(set(lessons))[:5]  # Deduplicate and limit

    def _extract_actions(self, text: str) -> list[str]:
        """Extract improvement actions from text"""
        if not text:
            return []

        actions = []
        sentences = text.replace("\n", ". ").split(". ")

        action_keywords = ["should", "would", "could", "need to", "will", "must"]

        for sentence in sentences:
            if any(kw in sentence.lower() for kw in action_keywords):
                clean = sentence.strip()
                if len(clean) > 15:
                    actions.append(clean)

        return actions[:5]

    def _extract_gaps(self, text: str) -> list[str]:
        """Extract knowledge gaps from text"""
        if not text:
            return []

        gaps = []
        sentences = text.replace("\n", ". ").split(". ")

        gap_keywords = [
            "missing",
            "learn",
            "study",
            "understand",
            "know more",
            "practice",
        ]

        for sentence in sentences:
            if any(kw in sentence.lower() for kw in gap_keywords):
                clean = sentence.strip()
                if len(clean) > 10:
                    gaps.append(clean)

        return gaps[:5]

    def _normalize_text(self, text: str) -> str:
        """Normalize text for pattern matching"""
        import re

        # Lowercase, remove extra spaces, remove punctuation
        text = text.lower().strip()
        text = re.sub(r"[^\w\s]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text[:100]  # Limit length

    def _generate_recommendations(
        self,
        pattern_key: str,
        occurrences: list[tuple[str, float]],
    ) -> list[str]:
        """Generate recommendations from pattern occurrences"""
        recommendations = []

        # High success pattern -> recommend continuing
        scores = [s for _, s in occurrences]
        avg_score = statistics.mean(scores) if scores else 5.0

        if avg_score >= 7.0:
            recommendations.append(f"Continue: {occurrences[0][0]}")
        else:
            recommendations.append(f"Improve: {occurrences[0][0]}")

        return recommendations

    async def _update_patterns(self, reflection: ReflectionResult) -> None:
        """Update patterns based on new reflection"""
        # Update existing patterns
        for lesson in reflection.lessons_learned:
            key = self._normalize_text(lesson)

            for pattern in self.patterns.values():
                if self._normalize_text(pattern.description) == key:
                    pattern.frequency += 1
                    pattern.last_seen = datetime.now(UTC)
                    if reflection.task[:100] not in pattern.contexts:
                        pattern.contexts.append(reflection.task[:100])
                    break

    def _update_stats(self) -> None:
        """Update statistics"""
        self.stats["total_reflections"] = len(self.reflection_history)

        if self.reflection_history:
            scores = [r.quality_score for r in self.reflection_history]
            self.stats["avg_quality_score"] = statistics.mean(scores)

        self.stats["lessons_accumulated"] = sum(
            len(r.lessons_learned) for r in self.reflection_history
        )

    def _persist_reflection(self, reflection: ReflectionResult) -> None:
        """Persist reflection to disk"""
        if not self.persist_path:
            return

        self.persist_path.mkdir(parents=True, exist_ok=True)
        file_path = self.persist_path / f"{reflection.id}.json"

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(reflection.to_dict(), f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist reflection: {e}")

    def _load_history(self) -> None:
        """Load reflection history from disk"""
        if not self.persist_path or not self.persist_path.exists():
            return

        # Note: Full loading would require storing solution fully
        # For now, just count for stats
        count = len(list(self.persist_path.glob("*.json")))
        logger.info(f"📂 Found {count} persisted reflections")

    def get_stats(self) -> dict[str, Any]:
        """Get engine statistics"""
        return {
            **self.stats,
            "patterns_count": len(self.patterns),
            "recent_quality": [r.quality_score for r in self.reflection_history[-10:]],
        }


__all__ = [
    "Pattern",
    "ReflectionResult",
    "SelfReflectionEngine",
]
