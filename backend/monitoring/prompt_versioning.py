"""
Prompt Versioning System

Track, compare, and manage different versions of prompts:
- Version control for prompt templates
- Compare different versions
- Rollback to previous versions
- A/B testing foundation

Usage:
    from backend.monitoring.prompt_versioning import PromptVersioning
    versioning = PromptVersioning()
    version_id = versioning.create_version("strategy_prompt", template, metadata)
    template = versioning.get_version("strategy_prompt", version_id)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class PromptVersion:
    """Prompt version object."""

    version_id: str
    prompt_name: str
    template: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    created_by: str = "system"
    parent_version: str | None = None
    tags: list[str] = field(default_factory=list)
    is_active: bool = True

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "version_id": self.version_id,
            "prompt_name": self.prompt_name,
            "template": self.template,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "parent_version": self.parent_version,
            "tags": self.tags,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PromptVersion:
        """Create from dict."""
        return cls(**data)


@dataclass
class VersionComparison:
    """Result of version comparison."""

    version_a: str
    version_b: str
    template_changed: bool
    metadata_changed: bool
    tags_changed: bool
    changes: list[str] = field(default_factory=list)
    similarity_score: float = 0.0


class PromptVersioning:
    """
    Version control system for prompts.

    Features:
    - Create versions with metadata
    - List all versions of a prompt
    - Compare versions
    - Rollback to previous versions
    - Tag versions
    - Activate/deactivate versions

    Example:
        versioning = PromptVersioning()
        v1 = versioning.create_version("strategy", template_v1)
        v2 = versioning.create_version("strategy", template_v2, tags=["improved"])
        comparison = versioning.compare_versions("strategy", v1, v2)
    """

    def __init__(self, storage_path: str = "data/prompt_versions.json"):
        """
        Initialize versioning system.

        Args:
            storage_path: Path to store versions
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # In-memory storage
        self._versions: dict[str, dict[str, PromptVersion]] = {}  # prompt_name -> version_id -> version
        self._active_versions: dict[str, str] = {}  # prompt_name -> active_version_id

        # Load from disk
        self._load()

        logger.info(f"📝 PromptVersioning initialized (storage={storage_path})")

    def create_version(
        self,
        prompt_name: str,
        template: str,
        metadata: dict[str, Any] | None = None,
        created_by: str = "system",
        parent_version: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """
        Create a new version.

        Args:
            prompt_name: Name of the prompt
            template: Prompt template text
            metadata: Additional metadata
            created_by: Creator identifier
            parent_version: Parent version ID (for lineage)
            tags: Version tags

        Returns:
            Version ID
        """
        # Generate version ID
        timestamp = datetime.now(UTC).isoformat()
        content_hash = hashlib.sha256(f"{template}{timestamp}".encode()).hexdigest()[:12]
        version_id = f"v{len(self._versions.get(prompt_name, {})) + 1}_{content_hash}"

        # Create version
        version = PromptVersion(
            version_id=version_id,
            prompt_name=prompt_name,
            template=template,
            metadata=metadata or {},
            created_at=timestamp,
            created_by=created_by,
            parent_version=parent_version,
            tags=tags or [],
        )

        # Store
        if prompt_name not in self._versions:
            self._versions[prompt_name] = {}

        self._versions[prompt_name][version_id] = version

        # Set as active if first version
        if prompt_name not in self._active_versions:
            self._active_versions[prompt_name] = version_id

        # Save
        self._save()

        logger.info(f"✅ Created version {version_id} for {prompt_name}")

        return version_id

    def get_version(
        self,
        prompt_name: str,
        version_id: str | None = None,
    ) -> PromptVersion | None:
        """
        Get version by ID.

        Args:
            prompt_name: Name of the prompt
            version_id: Version ID (None for active version)

        Returns:
            PromptVersion or None
        """
        if prompt_name not in self._versions:
            return None

        if version_id is None:
            # Get active version
            version_id = self._active_versions.get(prompt_name)

        if version_id is None:
            return None

        return self._versions[prompt_name].get(version_id)

    def list_versions(self, prompt_name: str) -> list[PromptVersion]:
        """
        List all versions of a prompt.

        Args:
            prompt_name: Name of the prompt

        Returns:
            List of versions (newest first)
        """
        if prompt_name not in self._versions:
            return []

        versions = list(self._versions[prompt_name].values())
        return sorted(versions, key=lambda v: v.created_at, reverse=True)

    def compare_versions(
        self,
        prompt_name: str,
        version_a_id: str,
        version_b_id: str,
    ) -> VersionComparison | None:
        """
        Compare two versions.

        Args:
            prompt_name: Name of the prompt
            version_a_id: First version ID
            version_b_id: Second version ID

        Returns:
            VersionComparison or None
        """
        version_a = self.get_version(prompt_name, version_a_id)
        version_b = self.get_version(prompt_name, version_b_id)

        if version_a is None or version_b is None:
            return None

        changes = []

        # Compare template
        template_changed = version_a.template != version_b.template
        if template_changed:
            changes.append("Template content changed")

        # Compare metadata
        metadata_changed = version_a.metadata != version_b.metadata
        if metadata_changed:
            changes.append("Metadata changed")

        # Compare tags
        tags_changed = set(version_a.tags) != set(version_b.tags)
        if tags_changed:
            changes.append("Tags changed")

        # Calculate similarity
        similarity = self._calculate_similarity(version_a.template, version_b.template)

        return VersionComparison(
            version_a=version_a_id,
            version_b=version_b_id,
            template_changed=template_changed,
            metadata_changed=metadata_changed,
            tags_changed=tags_changed,
            changes=changes,
            similarity_score=similarity,
        )

    def rollback(
        self,
        prompt_name: str,
        version_id: str,
    ) -> bool:
        """
        Rollback to a previous version.

        Args:
            prompt_name: Name of the prompt
            version_id: Version to rollback to

        Returns:
            True if successful
        """
        version = self.get_version(prompt_name, version_id)

        if version is None:
            logger.error(f"Version {version_id} not found for {prompt_name}")
            return False

        # Set as active
        self._active_versions[prompt_name] = version_id

        # Save
        self._save()

        logger.info(f"🔄 Rolled back {prompt_name} to {version_id}")

        return True

    def add_tag(
        self,
        prompt_name: str,
        version_id: str,
        tag: str,
    ) -> bool:
        """
        Add tag to version.

        Args:
            prompt_name: Name of the prompt
            version_id: Version ID
            tag: Tag to add

        Returns:
            True if successful
        """
        version = self.get_version(prompt_name, version_id)

        if version is None:
            return False

        if tag not in version.tags:
            version.tags.append(tag)
            self._save()

        return True

    def remove_tag(
        self,
        prompt_name: str,
        version_id: str,
        tag: str,
    ) -> bool:
        """
        Remove tag from version.

        Args:
            prompt_name: Name of the prompt
            version_id: Version ID
            tag: Tag to remove

        Returns:
            True if successful
        """
        version = self.get_version(prompt_name, version_id)

        if version is None:
            return False

        if tag in version.tags:
            version.tags.remove(tag)
            self._save()

        return True

    def get_active_version(self, prompt_name: str) -> PromptVersion | None:
        """
        Get active version of a prompt.

        Args:
            prompt_name: Name of the prompt

        Returns:
            Active version or None
        """
        version_id = self._active_versions.get(prompt_name)
        return self.get_version(prompt_name, version_id)

    def set_active_version(
        self,
        prompt_name: str,
        version_id: str,
    ) -> bool:
        """
        Set active version.

        Args:
            prompt_name: Name of the prompt
            version_id: Version ID

        Returns:
            True if successful
        """
        version = self.get_version(prompt_name, version_id)

        if version is None:
            return False

        self._active_versions[prompt_name] = version_id
        self._save()

        logger.info(f"✅ Set active version {version_id} for {prompt_name}")

        return True

    def get_version_history(self, prompt_name: str) -> list[dict[str, Any]]:
        """
        Get version history with lineage.

        Args:
            prompt_name: Name of the prompt

        Returns:
            List of version info with parent relationships
        """
        versions = self.list_versions(prompt_name)

        history = []
        for v in versions:
            history.append(
                {
                    "version_id": v.version_id,
                    "created_at": v.created_at,
                    "created_by": v.created_by,
                    "parent_version": v.parent_version,
                    "tags": v.tags,
                    "is_active": v.version_id == self._active_versions.get(prompt_name),
                    "template_preview": v.template[:100] + "..." if len(v.template) > 100 else v.template,
                }
            )

        return history

    def _calculate_similarity(self, text_a: str, text_b: str) -> float:
        """Calculate similarity between two texts (0-1)."""
        if not text_a or not text_b:
            return 0.0

        # Simple word-based similarity
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())

        if not words_a or not words_b:
            return 0.0

        intersection = words_a & words_b
        union = words_a | words_b

        return len(intersection) / len(union) if union else 0.0

    def _load(self) -> None:
        """Load from disk."""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path, encoding="utf-8") as f:
                data = json.load(f)

            # Load versions
            for prompt_name, versions_data in data.get("versions", {}).items():
                self._versions[prompt_name] = {}
                for version_id, version_data in versions_data.items():
                    self._versions[prompt_name][version_id] = PromptVersion.from_dict(version_data)

            # Load active versions
            self._active_versions = data.get("active_versions", {})

            logger.info(f"📝 Loaded {sum(len(v) for v in self._versions.values())} versions")

        except Exception as e:
            logger.error(f"Failed to load versions: {e}")

    def _save(self) -> None:
        """Save to disk."""
        try:
            data = {
                "versions": {
                    prompt_name: {version_id: version.to_dict() for version_id, version in versions.items()}
                    for prompt_name, versions in self._versions.items()
                },
                "active_versions": self._active_versions,
                "updated_at": datetime.now(UTC).isoformat(),
            }

            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to save versions: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get versioning statistics."""
        total_versions = sum(len(v) for v in self._versions.values())

        return {
            "total_prompts": len(self._versions),
            "total_versions": total_versions,
            "prompts": list(self._versions.keys()),
            "versions_per_prompt": {name: len(versions) for name, versions in self._versions.items()},
        }


# Global instance
_versioning: PromptVersioning | None = None


def get_prompt_versioning(storage_path: str = "data/prompt_versions.json") -> PromptVersioning:
    """
    Get or create versioning instance (singleton).

    Args:
        storage_path: Storage path

    Returns:
        PromptVersioning instance
    """
    global _versioning
    if _versioning is None:
        _versioning = PromptVersioning(storage_path)
    return _versioning
