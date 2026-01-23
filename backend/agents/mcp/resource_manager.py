"""
MCP Resource Manager

Manages resources accessible to AI agents:
- File system resources
- Database resources
- API resources
- Memory resources
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from loguru import logger


class ResourceType(Enum):
    """Types of resources"""

    FILE = "file"
    DIRECTORY = "directory"
    DATABASE = "database"
    API = "api"
    MEMORY = "memory"
    CUSTOM = "custom"


@dataclass
class Resource:
    """
    Resource definition

    Example:
        resource = Resource(
            uri="file:///data/strategies.json",
            name="Trading Strategies",
            type=ResourceType.FILE,
            mime_type="application/json",
        )
    """

    uri: str
    name: str
    type: ResourceType = ResourceType.CUSTOM
    description: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = {
            "uri": self.uri,
            "name": self.name,
            "type": self.type.value,
        }
        if self.description:
            data["description"] = self.description
        if self.mime_type:
            data["mimeType"] = self.mime_type
        if self.size_bytes is not None:
            data["size"] = self.size_bytes
        if self.created_at:
            data["createdAt"] = self.created_at.isoformat()
        if self.modified_at:
            data["modifiedAt"] = self.modified_at.isoformat()
        if self.metadata:
            data["metadata"] = self.metadata
        return data


@dataclass
class ResourceContent:
    """Content of a resource"""

    uri: str
    mime_type: str
    text: Optional[str] = None
    blob: Optional[bytes] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MCP format"""
        data = {
            "uri": self.uri,
            "mimeType": self.mime_type,
        }
        if self.text is not None:
            data["text"] = self.text
        if self.blob is not None:
            import base64

            data["blob"] = base64.b64encode(self.blob).decode()
        return data


class ResourceProvider(ABC):
    """Abstract resource provider"""

    @abstractmethod
    async def list_resources(self) -> List[Resource]:
        """List available resources"""
        pass

    @abstractmethod
    async def read_resource(self, uri: str) -> ResourceContent:
        """Read resource content"""
        pass

    @abstractmethod
    async def supports(self, uri: str) -> bool:
        """Check if provider supports this URI"""
        pass


class FileResourceProvider(ResourceProvider):
    """File system resource provider"""

    def __init__(self, base_path: str, allowed_extensions: Optional[List[str]] = None):
        self.base_path = Path(base_path)
        self.allowed_extensions = allowed_extensions or [
            ".json",
            ".txt",
            ".md",
            ".py",
            ".yaml",
            ".yml",
            ".csv",
        ]

        logger.info(f"📁 FileResourceProvider initialized: {base_path}")

    async def list_resources(self) -> List[Resource]:
        """List files in base path"""
        resources = []

        if not self.base_path.exists():
            return resources

        for path in self.base_path.rglob("*"):
            if path.is_file() and path.suffix in self.allowed_extensions:
                stat = path.stat()
                resources.append(
                    Resource(
                        uri=f"file://{path.absolute()}",
                        name=path.name,
                        type=ResourceType.FILE,
                        mime_type=self._get_mime_type(path.suffix),
                        size_bytes=stat.st_size,
                        modified_at=datetime.fromtimestamp(
                            stat.st_mtime, tz=timezone.utc
                        ),
                    )
                )

        return resources

    async def read_resource(self, uri: str) -> ResourceContent:
        """Read file content"""
        if not uri.startswith("file://"):
            raise ValueError(f"Invalid file URI: {uri}")

        path = Path(uri.replace("file://", ""))

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # Check if within base path
        try:
            path.resolve().relative_to(self.base_path.resolve())
        except ValueError:
            raise PermissionError(f"Access denied: {path}")

        mime_type = self._get_mime_type(path.suffix)

        if path.suffix in [".json", ".txt", ".md", ".py", ".yaml", ".yml", ".csv"]:
            text = path.read_text(encoding="utf-8")
            return ResourceContent(uri=uri, mime_type=mime_type, text=text)
        else:
            blob = path.read_bytes()
            return ResourceContent(uri=uri, mime_type=mime_type, blob=blob)

    async def supports(self, uri: str) -> bool:
        """Check if file URI"""
        return uri.startswith("file://")

    def _get_mime_type(self, suffix: str) -> str:
        """Get MIME type from extension"""
        mime_types = {
            ".json": "application/json",
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".py": "text/x-python",
            ".yaml": "application/x-yaml",
            ".yml": "application/x-yaml",
            ".csv": "text/csv",
            ".html": "text/html",
            ".xml": "application/xml",
        }
        return mime_types.get(suffix, "application/octet-stream")


class MemoryResourceProvider(ResourceProvider):
    """In-memory resource provider"""

    def __init__(self):
        self._resources: Dict[str, tuple[Resource, ResourceContent]] = {}
        logger.info("🧠 MemoryResourceProvider initialized")

    def add_resource(
        self,
        uri: str,
        name: str,
        content: str,
        mime_type: str = "text/plain",
        description: Optional[str] = None,
    ) -> Resource:
        """Add in-memory resource"""
        resource = Resource(
            uri=uri,
            name=name,
            type=ResourceType.MEMORY,
            description=description,
            mime_type=mime_type,
            size_bytes=len(content.encode()),
            created_at=datetime.now(timezone.utc),
        )

        content_obj = ResourceContent(
            uri=uri,
            mime_type=mime_type,
            text=content,
        )

        self._resources[uri] = (resource, content_obj)
        return resource

    def update_resource(self, uri: str, content: str) -> None:
        """Update resource content"""
        if uri not in self._resources:
            raise KeyError(f"Resource not found: {uri}")

        resource, _ = self._resources[uri]
        resource.size_bytes = len(content.encode())
        resource.modified_at = datetime.now(timezone.utc)

        self._resources[uri] = (
            resource,
            ResourceContent(uri=uri, mime_type=resource.mime_type, text=content),
        )

    async def list_resources(self) -> List[Resource]:
        """List in-memory resources"""
        return [res for res, _ in self._resources.values()]

    async def read_resource(self, uri: str) -> ResourceContent:
        """Read resource content"""
        if uri not in self._resources:
            raise KeyError(f"Resource not found: {uri}")
        return self._resources[uri][1]

    async def supports(self, uri: str) -> bool:
        """Check if memory URI"""
        return uri.startswith("memory://") or uri in self._resources


class DatabaseResourceProvider(ResourceProvider):
    """Database resource provider (placeholder)"""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        logger.info("🗄️ DatabaseResourceProvider initialized")

    async def list_resources(self) -> List[Resource]:
        """List tables/views as resources"""
        # Placeholder - would query database metadata
        return [
            Resource(
                uri="db://strategies",
                name="Strategies Table",
                type=ResourceType.DATABASE,
                mime_type="application/json",
            ),
            Resource(
                uri="db://backtests",
                name="Backtests Table",
                type=ResourceType.DATABASE,
                mime_type="application/json",
            ),
        ]

    async def read_resource(self, uri: str) -> ResourceContent:
        """Query database resource"""
        # Placeholder - would execute query
        return ResourceContent(
            uri=uri,
            mime_type="application/json",
            text=json.dumps({"message": "Database query placeholder"}),
        )

    async def supports(self, uri: str) -> bool:
        """Check if database URI"""
        return uri.startswith("db://")


class ResourceManager:
    """
    Centralized resource management

    Features:
    - Multiple provider support
    - URI-based routing
    - Caching
    - Access control

    Example:
        manager = ResourceManager()
        manager.add_provider(FileResourceProvider("./data"))

        resources = await manager.list_resources()
        content = await manager.read_resource("file:///data/config.json")
    """

    def __init__(self):
        self.providers: List[ResourceProvider] = []
        self._cache: Dict[str, tuple[ResourceContent, datetime]] = {}
        self._cache_ttl_seconds: int = 60
        self._subscriptions: Dict[str, List[Callable]] = {}

        logger.info("📦 ResourceManager initialized")

    def add_provider(self, provider: ResourceProvider) -> None:
        """Add resource provider"""
        self.providers.append(provider)
        logger.debug(f"Added provider: {type(provider).__name__}")

    async def list_resources(
        self, type_filter: Optional[ResourceType] = None
    ) -> List[Resource]:
        """List all resources from all providers"""
        all_resources = []

        for provider in self.providers:
            try:
                resources = await provider.list_resources()
                if type_filter:
                    resources = [r for r in resources if r.type == type_filter]
                all_resources.extend(resources)
            except Exception as e:
                logger.warning(f"Provider error: {e}")

        return all_resources

    async def read_resource(self, uri: str, use_cache: bool = True) -> ResourceContent:
        """Read resource content"""
        # Check cache
        if use_cache and uri in self._cache:
            content, cached_at = self._cache[uri]
            age = (datetime.now(timezone.utc) - cached_at).total_seconds()
            if age < self._cache_ttl_seconds:
                return content

        # Find provider
        for provider in self.providers:
            if await provider.supports(uri):
                content = await provider.read_resource(uri)

                # Cache if text content
                if content.text:
                    self._cache[uri] = (content, datetime.now(timezone.utc))

                return content

        raise ValueError(f"No provider supports URI: {uri}")

    async def subscribe(self, uri: str, callback: Callable) -> str:
        """Subscribe to resource changes"""
        if uri not in self._subscriptions:
            self._subscriptions[uri] = []

        self._subscriptions[uri].append(callback)

        subscription_id = f"sub_{len(self._subscriptions[uri])}"
        logger.debug(f"Subscribed to {uri}: {subscription_id}")

        return subscription_id

    async def unsubscribe(self, uri: str, subscription_id: str) -> None:
        """Unsubscribe from resource changes"""
        # Simplified - would track by ID in production
        if uri in self._subscriptions:
            self._subscriptions[uri] = []

    async def notify_change(self, uri: str) -> None:
        """Notify subscribers of resource change"""
        if uri in self._subscriptions:
            for callback in self._subscriptions[uri]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(uri)
                    else:
                        callback(uri)
                except Exception as e:
                    logger.error(f"Subscription callback error: {e}")

        # Invalidate cache
        self._cache.pop(uri, None)

    def clear_cache(self) -> None:
        """Clear resource cache"""
        self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics"""
        return {
            "providers": len(self.providers),
            "cached_resources": len(self._cache),
            "subscriptions": sum(len(subs) for subs in self._subscriptions.values()),
        }


# Global instance
_global_manager: Optional[ResourceManager] = None


def get_resource_manager() -> ResourceManager:
    """Get global resource manager"""
    global _global_manager
    if _global_manager is None:
        _global_manager = ResourceManager()
    return _global_manager


__all__ = [
    "ResourceType",
    "Resource",
    "ResourceContent",
    "ResourceProvider",
    "FileResourceProvider",
    "MemoryResourceProvider",
    "DatabaseResourceProvider",
    "ResourceManager",
    "get_resource_manager",
]
