"""
Tests for Prompt Versioning System

Run: pytest tests/monitoring/test_prompt_versioning.py -v
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "d:/bybit_strategy_tester_v2")

import pytest

from backend.monitoring.prompt_versioning import (
    PromptVersion,
    PromptVersioning,
    VersionComparison,
    get_prompt_versioning,
)


class TestPromptVersioning:
    """Tests for PromptVersioning."""

    @pytest.fixture
    def versioning(self):
        """Create versioning instance with temp storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "prompt_versions.json"
            yield PromptVersioning(str(storage_path))

    def test_create_version(self, versioning):
        """Test creating a version."""
        template = "You are a helpful assistant."

        version_id = versioning.create_version(
            prompt_name="test_prompt",
            template=template,
        )

        assert version_id
        assert version_id.startswith("v")

    def test_get_version(self, versioning):
        """Test getting a version."""
        template = "You are a helpful assistant."

        version_id = versioning.create_version("test_prompt", template)

        version = versioning.get_version("test_prompt", version_id)

        assert version is not None
        assert version.template == template
        assert version.version_id == version_id

    def test_get_active_version(self, versioning):
        """Test getting active version."""
        template_v1 = "Version 1"
        template_v2 = "Version 2"

        v1 = versioning.create_version("test", template_v1)
        v2 = versioning.create_version("test", template_v2)

        # Explicitly set v2 as active
        versioning.set_active_version("test", v2)

        # v2 should be active
        active = versioning.get_active_version("test")

        assert active is not None
        assert active.version_id == v2
        assert active.template == template_v2

    def test_list_versions(self, versioning):
        """Test listing versions."""
        versioning.create_version("test", "v1")
        versioning.create_version("test", "v2")
        versioning.create_version("test", "v3")

        versions = versioning.list_versions("test")

        # Should have 3 versions
        assert len(versions) == 3

        # Should be sorted newest first
        assert versions[0].template == "v3"
        assert versions[1].template == "v2"
        assert versions[2].template == "v1"

    def test_compare_versions(self, versioning):
        """Test comparing versions."""
        v1 = versioning.create_version("test", "Template version 1")
        v2 = versioning.create_version("test", "Template version 2")

        comparison = versioning.compare_versions("test", v1, v2)

        assert comparison is not None
        assert comparison.template_changed is True
        assert comparison.similarity_score > 0
        assert comparison.similarity_score < 1

    def test_compare_identical_versions(self, versioning):
        """Test comparing identical versions."""
        template = "Same template"
        v1 = versioning.create_version("test", template)
        v2 = versioning.create_version("test", template)

        comparison = versioning.compare_versions("test", v1, v2)

        assert comparison is not None
        assert comparison.template_changed is False
        assert comparison.similarity_score == 1.0

    def test_rollback(self, versioning):
        """Test rolling back to previous version."""
        v1 = versioning.create_version("test", "v1")
        v2 = versioning.create_version("test", "v2")

        # Explicitly set v2 as active
        versioning.set_active_version("test", v2)

        # v2 should be active
        active = versioning.get_active_version("test")
        assert active.version_id == v2

        # Rollback to v1
        success = versioning.rollback("test", v1)
        assert success is True

        # v1 should be active now
        active = versioning.get_active_version("test")
        assert active.version_id == v1
        assert active.template == "v1"

    def test_add_tag(self, versioning):
        """Test adding tag to version."""
        version_id = versioning.create_version("test", "template")

        success = versioning.add_tag("test", version_id, "production")
        assert success is True

        # Verify tag added
        version = versioning.get_version("test", version_id)
        assert "production" in version.tags

    def test_remove_tag(self, versioning):
        """Test removing tag from version."""
        version_id = versioning.create_version("test", "template", tags=["production"])

        success = versioning.remove_tag("test", version_id, "production")
        assert success is True

        # Verify tag removed
        version = versioning.get_version("test", version_id)
        assert "production" not in version.tags

    def test_set_active_version(self, versioning):
        """Test setting active version."""
        v1 = versioning.create_version("test", "v1")
        v2 = versioning.create_version("test", "v2")

        # Set v1 as active
        success = versioning.set_active_version("test", v1)
        assert success is True

        active = versioning.get_active_version("test")
        assert active.version_id == v1

    def test_get_version_history(self, versioning):
        """Test getting version history."""
        v1 = versioning.create_version("test", "v1")
        v2 = versioning.create_version("test", "v2", parent_version=v1)

        history = versioning.get_version_history("test")

        assert len(history) == 2
        assert history[0]["version_id"] == v2
        assert history[1]["version_id"] == v1
        assert history[0]["parent_version"] == v1

    def test_version_metadata(self, versioning):
        """Test version metadata."""
        metadata = {"author": "John", "purpose": "testing"}

        version_id = versioning.create_version("test", "template", metadata=metadata, created_by="test_user")

        version = versioning.get_version("test", version_id)

        assert version is not None
        assert version.metadata == metadata
        assert version.created_by == "test_user"

    def test_version_parent_lineage(self, versioning):
        """Test version parent lineage."""
        v1 = versioning.create_version("test", "v1")
        v2 = versioning.create_version("test", "v2", parent_version=v1)
        v3 = versioning.create_version("test", "v3", parent_version=v2)

        version_v3 = versioning.get_version("test", v3)

        assert version_v3 is not None
        assert version_v3.parent_version == v2

    def test_get_stats(self, versioning):
        """Test getting statistics."""
        versioning.create_version("prompt1", "template")
        versioning.create_version("prompt1", "template v2")
        versioning.create_version("prompt2", "template")

        stats = versioning.get_stats()

        assert stats["total_prompts"] == 2
        assert stats["total_versions"] == 3
        assert "prompt1" in stats["prompts"]
        assert "prompt2" in stats["prompts"]

    def test_persistence(self, versioning):
        """Test saving and loading from disk."""
        versioning.create_version("test", "template", tags=["production"])

        # Create new instance (should load from disk)
        versioning2 = PromptVersioning(versioning.storage_path)

        # Should have same data
        versions = versioning2.list_versions("test")
        assert len(versions) == 1
        assert versions[0].template == "template"
        assert "production" in versions[0].tags

    def test_get_nonexistent_version(self, versioning):
        """Test getting nonexistent version."""
        version = versioning.get_version("nonexistent", "v1")
        assert version is None

    def test_compare_nonexistent_versions(self, versioning):
        """Test comparing nonexistent versions."""
        comparison = versioning.compare_versions("nonexistent", "v1", "v2")
        assert comparison is None


class TestPromptVersion:
    """Tests for PromptVersion dataclass."""

    def test_version_creation(self):
        """Test creating a version."""
        version = PromptVersion(
            version_id="v1",
            prompt_name="test",
            template="template",
        )

        assert version.version_id == "v1"
        assert version.prompt_name == "test"
        assert version.template == "template"
        assert version.created_at  # Auto-generated

    def test_version_to_dict(self):
        """Test converting to dict."""
        version = PromptVersion(
            version_id="v1",
            prompt_name="test",
            template="template",
            tags=["production"],
        )

        data = version.to_dict()

        assert data["version_id"] == "v1"
        assert data["prompt_name"] == "test"
        assert data["tags"] == ["production"]

    def test_version_from_dict(self):
        """Test creating from dict."""
        data = {
            "version_id": "v1",
            "prompt_name": "test",
            "template": "template",
            "metadata": {},
            "created_at": "2026-03-03T00:00:00",
            "created_by": "system",
            "parent_version": None,
            "tags": [],
            "is_active": True,
        }

        version = PromptVersion.from_dict(data)

        assert version.version_id == "v1"
        assert version.prompt_name == "test"
        assert version.template == "template"


class TestVersionComparison:
    """Tests for VersionComparison dataclass."""

    def test_comparison_creation(self):
        """Test creating a comparison."""
        comparison = VersionComparison(
            version_a="v1",
            version_b="v2",
            template_changed=True,
            metadata_changed=False,
            tags_changed=False,
            similarity_score=0.8,
        )

        assert comparison.version_a == "v1"
        assert comparison.version_b == "v2"
        assert comparison.template_changed is True
        assert comparison.similarity_score == 0.8


class TestGlobalVersioning:
    """Tests for global versioning functions."""

    def test_get_prompt_versioning_singleton(self):
        """Test singleton pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "versions.json"

            v1 = get_prompt_versioning(str(storage_path))
            v2 = get_prompt_versioning(str(storage_path))

            # Should be same instance
            assert v1 is v2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
