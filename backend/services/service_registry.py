"""
Service Registry for Microservices Discovery.

Provides service registration, discovery, and health monitoring
for distributed deployment of trading platform components.

Features:
- Service registration with metadata
- Health check monitoring
- Load balancing strategies
- Circuit breaker integration
- Redis-backed for distributed state
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration
# ============================================================================


class ServiceStatus(Enum):
    """Service health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class LoadBalancingStrategy(Enum):
    """Load balancing strategies."""

    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED = "weighted"
    HEALTH_WEIGHTED = "health_weighted"


@dataclass
class ServiceInstance:
    """Represents a service instance."""

    instance_id: str
    service_name: str
    host: str
    port: int
    version: str = "1.0.0"
    status: ServiceStatus = ServiceStatus.UNKNOWN
    metadata: dict[str, Any] = field(default_factory=dict)
    weight: int = 100  # For weighted load balancing
    active_connections: int = 0
    last_health_check: Optional[datetime] = None
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    health_check_url: str = "/health"
    tags: list[str] = field(default_factory=list)

    @property
    def url(self) -> str:
        """Get base URL for service."""
        return f"http://{self.host}:{self.port}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "instance_id": self.instance_id,
            "service_name": self.service_name,
            "host": self.host,
            "port": self.port,
            "version": self.version,
            "status": self.status.value,
            "metadata": self.metadata,
            "weight": self.weight,
            "active_connections": self.active_connections,
            "last_health_check": (self.last_health_check.isoformat() if self.last_health_check else None),
            "registered_at": self.registered_at.isoformat(),
            "health_check_url": self.health_check_url,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServiceInstance":
        """Create from dictionary."""
        return cls(
            instance_id=data["instance_id"],
            service_name=data["service_name"],
            host=data["host"],
            port=data["port"],
            version=data.get("version", "1.0.0"),
            status=ServiceStatus(data.get("status", "unknown")),
            metadata=data.get("metadata", {}),
            weight=data.get("weight", 100),
            active_connections=data.get("active_connections", 0),
            last_health_check=(
                datetime.fromisoformat(data["last_health_check"]) if data.get("last_health_check") else None
            ),
            registered_at=(
                datetime.fromisoformat(data["registered_at"])
                if data.get("registered_at")
                else datetime.now(timezone.utc)
            ),
            health_check_url=data.get("health_check_url", "/health"),
            tags=data.get("tags", []),
        )


@dataclass
class ServiceDefinition:
    """Service definition with all instances."""

    name: str
    instances: list[ServiceInstance] = field(default_factory=list)
    load_balancing: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN
    health_check_interval: int = 30  # seconds
    deregister_after: int = 90  # seconds without health check
    retry_policy: dict[str, Any] = field(default_factory=lambda: {"max_retries": 3, "backoff_factor": 0.5})

    @property
    def healthy_instances(self) -> list[ServiceInstance]:
        """Get only healthy instances."""
        return [i for i in self.instances if i.status == ServiceStatus.HEALTHY]


# ============================================================================
# Load Balancer
# ============================================================================


class LoadBalancer:
    """Load balancer for service instances."""

    def __init__(self):
        self._round_robin_index: dict[str, int] = {}

    def select(
        self,
        instances: list[ServiceInstance],
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN,
    ) -> Optional[ServiceInstance]:
        """Select instance based on strategy."""
        if not instances:
            return None

        healthy = [i for i in instances if i.status == ServiceStatus.HEALTHY]
        if not healthy:
            # Fall back to all instances if none healthy
            healthy = instances

        if strategy == LoadBalancingStrategy.RANDOM:
            return random.choice(healthy)

        elif strategy == LoadBalancingStrategy.ROUND_ROBIN:
            service_name = healthy[0].service_name
            idx = self._round_robin_index.get(service_name, 0)
            instance = healthy[idx % len(healthy)]
            self._round_robin_index[service_name] = idx + 1
            return instance

        elif strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            return min(healthy, key=lambda x: x.active_connections)

        elif strategy == LoadBalancingStrategy.WEIGHTED:
            total_weight = sum(i.weight for i in healthy)
            if total_weight == 0:
                return random.choice(healthy)

            r = random.randint(1, total_weight)
            cumulative = 0
            for instance in healthy:
                cumulative += instance.weight
                if r <= cumulative:
                    return instance

            return healthy[-1]

        elif strategy == LoadBalancingStrategy.HEALTH_WEIGHTED:
            # Weight by health: healthy=100, degraded=50, unhealthy=10
            weights = {
                ServiceStatus.HEALTHY: 100,
                ServiceStatus.DEGRADED: 50,
                ServiceStatus.UNHEALTHY: 10,
                ServiceStatus.UNKNOWN: 25,
            }

            total = sum(weights.get(i.status, 25) for i in instances)
            r = random.randint(1, total)
            cumulative = 0
            for instance in instances:
                cumulative += weights.get(instance.status, 25)
                if r <= cumulative:
                    return instance

            return instances[-1]

        return healthy[0] if healthy else None


# ============================================================================
# Service Registry (In-Memory)
# ============================================================================


class InMemoryServiceRegistry:
    """In-memory service registry for single-node deployment."""

    def __init__(self):
        self._services: dict[str, ServiceDefinition] = {}
        self._instances: dict[str, ServiceInstance] = {}  # instance_id -> instance
        self._load_balancer = LoadBalancer()
        self._health_check_task: Optional[asyncio.Task[None]] = None
        self._running = False

    async def start(self) -> None:
        """Start the registry with health check monitoring."""
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Service registry started")

    async def stop(self) -> None:
        """Stop the registry."""
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        logger.info("Service registry stopped")

    async def register(
        self,
        service_name: str,
        host: str,
        port: int,
        version: str = "1.0.0",
        metadata: Optional[dict[str, Any]] = None,
        health_check_url: str = "/health",
        tags: Optional[list[str]] = None,
        weight: int = 100,
    ) -> str:
        """
        Register a service instance.

        Returns:
            Instance ID
        """
        instance_id = str(uuid4())

        instance = ServiceInstance(
            instance_id=instance_id,
            service_name=service_name,
            host=host,
            port=port,
            version=version,
            metadata=metadata or {},
            health_check_url=health_check_url,
            tags=tags or [],
            weight=weight,
            status=ServiceStatus.UNKNOWN,
        )

        # Create service definition if not exists
        if service_name not in self._services:
            self._services[service_name] = ServiceDefinition(name=service_name)

        self._services[service_name].instances.append(instance)
        self._instances[instance_id] = instance

        logger.info(f"Registered service: {service_name} ({host}:{port}) -> {instance_id}")

        # Perform initial health check
        await self._check_instance_health(instance)

        return instance_id

    async def deregister(self, instance_id: str) -> bool:
        """Deregister a service instance."""
        instance = self._instances.pop(instance_id, None)
        if not instance:
            return False

        service = self._services.get(instance.service_name)
        if service:
            service.instances = [i for i in service.instances if i.instance_id != instance_id]
            if not service.instances:
                del self._services[instance.service_name]

        logger.info(f"Deregistered service instance: {instance_id}")
        return True

    async def discover(
        self,
        service_name: str,
        tags: Optional[list[str]] = None,
        healthy_only: bool = True,
    ) -> list[ServiceInstance]:
        """
        Discover service instances.

        Args:
            service_name: Name of service to discover
            tags: Filter by tags
            healthy_only: Only return healthy instances

        Returns:
            List of matching instances
        """
        service = self._services.get(service_name)
        if not service:
            return []

        instances = service.instances

        if healthy_only:
            instances = [i for i in instances if i.status == ServiceStatus.HEALTHY]

        if tags:
            instances = [i for i in instances if all(t in i.tags for t in tags)]

        return instances

    async def get_instance(
        self,
        service_name: str,
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN,
    ) -> Optional[ServiceInstance]:
        """
        Get a single instance using load balancing.

        Args:
            service_name: Service name
            strategy: Load balancing strategy

        Returns:
            Selected instance or None
        """
        instances = await self.discover(service_name, healthy_only=True)
        return self._load_balancer.select(instances, strategy)

    async def heartbeat(self, instance_id: str) -> bool:
        """
        Send heartbeat for an instance.

        Returns:
            True if instance exists
        """
        instance = self._instances.get(instance_id)
        if not instance:
            return False

        instance.last_health_check = datetime.now(timezone.utc)
        instance.status = ServiceStatus.HEALTHY
        return True

    async def update_status(self, instance_id: str, status: ServiceStatus) -> bool:
        """Update instance status."""
        instance = self._instances.get(instance_id)
        if not instance:
            return False

        instance.status = status
        instance.last_health_check = datetime.now(timezone.utc)
        return True

    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while self._running:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds

                for instance in list(self._instances.values()):
                    await self._check_instance_health(instance)

                    # Deregister stale instances
                    if instance.last_health_check:
                        service = self._services.get(instance.service_name)
                        if service:
                            seconds_since = (datetime.now(timezone.utc) - instance.last_health_check).total_seconds()
                            if seconds_since > service.deregister_after:
                                await self.deregister(instance.instance_id)

            except Exception as e:
                logger.error(f"Health check loop error: {e}")

    async def _check_instance_health(self, instance: ServiceInstance) -> None:
        """Check health of a single instance."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                url = f"{instance.url}{instance.health_check_url}"
                response = await client.get(url)

                if response.status_code == 200:
                    instance.status = ServiceStatus.HEALTHY
                elif response.status_code in [503, 429]:
                    instance.status = ServiceStatus.DEGRADED
                else:
                    instance.status = ServiceStatus.UNHEALTHY

        except ImportError:
            # No httpx, mark as unknown
            logger.debug("httpx not available for health checks")
        except Exception:
            instance.status = ServiceStatus.UNHEALTHY

        instance.last_health_check = datetime.now(timezone.utc)

    def get_all_services(self) -> dict[str, Any]:
        """Get summary of all registered services."""
        result = {}
        for name, service in self._services.items():
            result[name] = {
                "instances": len(service.instances),
                "healthy": len(service.healthy_instances),
                "load_balancing": service.load_balancing.value,
                "versions": list(set(i.version for i in service.instances)),
            }
        return result


# ============================================================================
# Redis-backed Service Registry
# ============================================================================


class RedisServiceRegistry:
    """Redis-backed service registry for distributed deployment."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._redis: Optional[Any] = None
        self._load_balancer = LoadBalancer()
        self._local_instance_id: Optional[str] = None
        self._heartbeat_task: Optional[asyncio.Task[None]] = None
        self._running = False
        self._key_prefix = "service_registry:"

    async def connect(self) -> None:
        """Connect to Redis."""
        try:
            import redis.asyncio as aioredis

            self._redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info(f"Connected to Redis for service registry: {self.redis_url}")
        except ImportError:
            logger.warning("redis package not installed")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")

    async def start(self) -> None:
        """Start the registry."""
        await self.connect()
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Redis service registry started")

    async def stop(self) -> None:
        """Stop the registry."""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        if self._local_instance_id:
            await self.deregister(self._local_instance_id)

        if self._redis:
            await self._redis.close()

    async def register(
        self,
        service_name: str,
        host: str,
        port: int,
        version: str = "1.0.0",
        metadata: Optional[dict[str, Any]] = None,
        health_check_url: str = "/health",
        tags: Optional[list[str]] = None,
        weight: int = 100,
        ttl: int = 30,
    ) -> str:
        """Register service instance with TTL."""
        if not self._redis:
            raise RuntimeError("Redis not connected")

        import json

        instance_id = str(uuid4())
        instance = ServiceInstance(
            instance_id=instance_id,
            service_name=service_name,
            host=host,
            port=port,
            version=version,
            metadata=metadata or {},
            health_check_url=health_check_url,
            tags=tags or [],
            weight=weight,
            status=ServiceStatus.HEALTHY,
        )

        # Store instance data
        key = f"{self._key_prefix}instances:{instance_id}"
        await self._redis.setex(key, ttl, json.dumps(instance.to_dict()))

        # Add to service set
        service_key = f"{self._key_prefix}services:{service_name}"
        await self._redis.sadd(service_key, instance_id)

        self._local_instance_id = instance_id

        logger.info(f"Registered service in Redis: {service_name} -> {instance_id}")
        return instance_id

    async def deregister(self, instance_id: str) -> bool:
        """Deregister service instance."""
        if not self._redis:
            return False

        key = f"{self._key_prefix}instances:{instance_id}"
        data = await self._redis.get(key)
        if not data:
            return False

        import json

        instance_data = json.loads(data)
        service_name = instance_data.get("service_name")

        # Remove from service set
        if service_name:
            service_key = f"{self._key_prefix}services:{service_name}"
            await self._redis.srem(service_key, instance_id)

        # Delete instance data
        await self._redis.delete(key)

        logger.info(f"Deregistered service from Redis: {instance_id}")
        return True

    async def discover(
        self,
        service_name: str,
        healthy_only: bool = True,
    ) -> list[ServiceInstance]:
        """Discover service instances."""
        if not self._redis:
            return []

        import json

        service_key = f"{self._key_prefix}services:{service_name}"
        instance_ids = await self._redis.smembers(service_key)

        instances = []
        for instance_id in instance_ids:
            key = f"{self._key_prefix}instances:{instance_id}"
            data = await self._redis.get(key)
            if data:
                instance = ServiceInstance.from_dict(json.loads(data))
                if not healthy_only or instance.status == ServiceStatus.HEALTHY:
                    instances.append(instance)
            else:
                # Clean up stale reference
                await self._redis.srem(service_key, instance_id)

        return instances

    async def get_instance(
        self,
        service_name: str,
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN,
    ) -> Optional[ServiceInstance]:
        """Get a single instance using load balancing."""
        instances = await self.discover(service_name, healthy_only=True)
        return self._load_balancer.select(instances, strategy)

    async def heartbeat(self, instance_id: str, ttl: int = 30) -> bool:
        """Send heartbeat by refreshing TTL."""
        if not self._redis:
            return False

        key = f"{self._key_prefix}instances:{instance_id}"
        exists = await self._redis.expire(key, ttl)
        return bool(exists)

    async def _heartbeat_loop(self) -> None:
        """Background heartbeat loop."""
        while self._running:
            try:
                await asyncio.sleep(10)

                if self._local_instance_id:
                    await self.heartbeat(self._local_instance_id, ttl=30)

            except Exception as e:
                logger.error(f"Heartbeat error: {e}")


# ============================================================================
# Service Client with Discovery
# ============================================================================


class ServiceClient:
    """
    HTTP client with service discovery and load balancing.

    Recommended usage (context manager):
        async with ServiceClient(registry, "my-service") as client:
            response = await client.request("GET", "/api/data")

    Alternative (manual cleanup):
        client = ServiceClient(registry, "my-service")
        try:
            response = await client.request("GET", "/api/data")
        finally:
            await client.close()
    """

    def __init__(
        self,
        registry: InMemoryServiceRegistry | RedisServiceRegistry,
        service_name: str,
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN,
        timeout: float = 10.0,
        max_retries: int = 3,
    ):
        self.registry = registry
        self.service_name = service_name
        self.strategy = strategy
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[Any] = None
        self._closed = False

    async def __aenter__(self) -> "ServiceClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - ensures cleanup."""
        await self.close()

    async def _get_client(self) -> Any:
        """Get or create HTTP client."""
        if self._closed:
            raise RuntimeError("ServiceClient is closed")
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        """
        Make request to discovered service.

        Includes retry logic and load balancing.
        """
        client = await self._get_client()
        last_error = None

        for attempt in range(self.max_retries):
            instance = await self.registry.get_instance(self.service_name, self.strategy)
            if not instance:
                raise RuntimeError(f"No healthy instances for {self.service_name}")

            try:
                instance.active_connections += 1
                url = f"{instance.url}{path}"
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()

            except Exception as e:
                last_error = e
                logger.warning(f"Request to {instance.url} failed (attempt {attempt + 1}): {e}")

                # Mark instance as potentially unhealthy
                if hasattr(self.registry, "update_status"):
                    await self.registry.update_status(instance.instance_id, ServiceStatus.DEGRADED)

            finally:
                instance.active_connections -= 1

            # Backoff before retry
            await asyncio.sleep(0.5 * (attempt + 1))

        raise last_error or RuntimeError("All retries failed")

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()


# ============================================================================
# Factory Functions
# ============================================================================


def create_service_registry(
    backend: str = "memory",
    redis_url: str = "redis://localhost:6379/0",
) -> InMemoryServiceRegistry | RedisServiceRegistry:
    """
    Create service registry.

    Args:
        backend: "memory" or "redis"
        redis_url: Redis URL for redis backend

    Returns:
        Service registry instance
    """
    if backend == "redis":
        return RedisServiceRegistry(redis_url)
    return InMemoryServiceRegistry()


# ============================================================================
# Global Instance
# ============================================================================

_registry: Optional[InMemoryServiceRegistry | RedisServiceRegistry] = None


def get_service_registry() -> InMemoryServiceRegistry | RedisServiceRegistry:
    """Get or create global service registry."""
    global _registry
    if _registry is None:
        _registry = InMemoryServiceRegistry()
    return _registry


async def init_service_registry(
    backend: str = "memory",
    redis_url: str = "redis://localhost:6379/0",
) -> InMemoryServiceRegistry | RedisServiceRegistry:
    """Initialize global service registry."""
    global _registry
    _registry = create_service_registry(backend, redis_url)
    await _registry.start()
    return _registry
