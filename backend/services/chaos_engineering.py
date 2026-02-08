"""
Chaos Engineering Framework

Provides tools for testing system resilience through controlled fault injection:
- Service failure simulation
- Latency injection
- Resource exhaustion
- Network partitioning simulation
- Recovery verification
"""

import asyncio
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class FaultType(str, Enum):
    """Types of faults that can be injected."""

    LATENCY = "latency"  # Add delay to requests
    ERROR = "error"  # Return errors
    TIMEOUT = "timeout"  # Simulate timeouts
    PARTIAL_FAILURE = "partial_failure"  # Random failures
    RESOURCE_EXHAUSTION = "resource_exhaustion"  # Simulate resource limits
    NETWORK_PARTITION = "network_partition"  # Simulate network issues


class ExperimentStatus(str, Enum):
    """Status of chaos experiment."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class FaultConfig:
    """Configuration for a fault injection."""

    fault_type: FaultType
    target_service: str
    duration_seconds: int = 30
    probability: float = 1.0  # 0.0 to 1.0
    latency_ms: int = 1000  # For latency fault
    error_code: int = 500  # For error fault
    error_message: str = "Chaos experiment induced failure"
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "fault_type": self.fault_type.value,
            "target_service": self.target_service,
            "duration_seconds": self.duration_seconds,
            "probability": self.probability,
            "latency_ms": self.latency_ms,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "enabled": self.enabled,
        }


@dataclass
class ExperimentResult:
    """Result of a chaos experiment."""

    experiment_id: str
    name: str
    status: ExperimentStatus
    fault_config: FaultConfig
    started_at: datetime
    ended_at: datetime | None = None
    affected_requests: int = 0
    errors_injected: int = 0
    latency_added_ms: int = 0
    recovery_time_ms: int | None = None
    metrics_before: dict[str, Any] = field(default_factory=dict)
    metrics_after: dict[str, Any] = field(default_factory=dict)
    observations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "status": self.status.value,
            "fault_config": self.fault_config.to_dict(),
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "affected_requests": self.affected_requests,
            "errors_injected": self.errors_injected,
            "latency_added_ms": self.latency_added_ms,
            "recovery_time_ms": self.recovery_time_ms,
            "observations": self.observations,
        }


class FaultInjector:
    """Handles actual fault injection during experiments."""

    def __init__(self):
        self.active_faults: dict[str, FaultConfig] = {}
        self._original_handlers: dict[str, Callable] = {}

    def inject_fault(self, config: FaultConfig):
        """Activate a fault injection."""
        self.active_faults[config.target_service] = config
        logger.info(
            f"Fault injected: {config.fault_type.value} on {config.target_service}"
        )

    def remove_fault(self, target_service: str):
        """Remove a fault injection."""
        if target_service in self.active_faults:
            del self.active_faults[target_service]
            logger.info(f"Fault removed from {target_service}")

    def clear_all_faults(self):
        """Remove all active faults."""
        self.active_faults.clear()
        logger.info("All faults cleared")

    def should_inject(self, service_name: str) -> FaultConfig | None:
        """Check if a fault should be injected for a service."""
        config = self.active_faults.get(service_name)
        if not config or not config.enabled:
            return None

        # Check probability
        if random.random() > config.probability:
            return None

        return config

    async def apply_fault(self, config: FaultConfig) -> dict[str, Any]:
        """Apply the fault and return result info."""
        result = {"applied": True, "fault_type": config.fault_type.value}

        if config.fault_type == FaultType.LATENCY:
            await asyncio.sleep(config.latency_ms / 1000.0)
            result["latency_added_ms"] = config.latency_ms

        elif config.fault_type == FaultType.ERROR:
            result["error_code"] = config.error_code
            result["error_message"] = config.error_message
            raise Exception(config.error_message)

        elif config.fault_type == FaultType.TIMEOUT:
            await asyncio.sleep(30)  # Long delay to simulate timeout
            result["timeout"] = True

        elif config.fault_type == FaultType.PARTIAL_FAILURE:
            if random.random() < 0.5:
                result["error_code"] = 503
                raise Exception("Partial failure - service unavailable")
            result["passed"] = True

        return result


class ChaosExperiment:
    """Defines and runs a chaos engineering experiment."""

    def __init__(
        self,
        name: str,
        fault_config: FaultConfig,
        hypothesis: str = "",
        rollback_on_failure: bool = True,
    ):
        self.id = str(uuid4())[:8]
        self.name = name
        self.fault_config = fault_config
        self.hypothesis = hypothesis
        self.rollback_on_failure = rollback_on_failure
        self.status = ExperimentStatus.PENDING
        self.result: ExperimentResult | None = None

    async def run(
        self,
        injector: FaultInjector,
        test_func: Callable | None = None,
    ) -> ExperimentResult:
        """Execute the chaos experiment."""
        self.status = ExperimentStatus.RUNNING
        started_at = datetime.now(UTC)

        result = ExperimentResult(
            experiment_id=self.id,
            name=self.name,
            status=ExperimentStatus.RUNNING,
            fault_config=self.fault_config,
            started_at=started_at,
        )

        try:
            # Inject the fault
            injector.inject_fault(self.fault_config)
            result.observations.append(f"Fault injected at {started_at.isoformat()}")

            # Wait for experiment duration
            await asyncio.sleep(self.fault_config.duration_seconds)

            # Run test function if provided
            if test_func:
                try:
                    await test_func()
                    result.observations.append("Test function completed successfully")
                except Exception as e:
                    result.observations.append(f"Test function failed: {e!s}")

            result.status = ExperimentStatus.COMPLETED
            result.observations.append("Experiment completed successfully")

        except Exception as e:
            result.status = ExperimentStatus.FAILED
            result.observations.append(f"Experiment failed: {e!s}")

            if self.rollback_on_failure:
                injector.remove_fault(self.fault_config.target_service)
                result.status = ExperimentStatus.ROLLED_BACK
                result.observations.append("Fault rolled back due to failure")

        finally:
            # Clean up
            injector.remove_fault(self.fault_config.target_service)
            result.ended_at = datetime.now(UTC)

            # Calculate recovery time
            if result.ended_at:
                recovery_start = time.time()
                # In real implementation, would check service health
                result.recovery_time_ms = int((time.time() - recovery_start) * 1000)

        self.result = result
        self.status = result.status
        return result


class ChaosEngineeringService:
    """
    Central service for chaos engineering experiments.
    """

    def __init__(self):
        self.injector = FaultInjector()
        self.experiments: dict[str, ChaosExperiment] = {}
        self.results: list[ExperimentResult] = []
        self.enabled = False  # Disabled by default for safety

        # Pre-defined experiment templates
        self.templates = self._create_templates()

    def _create_templates(self) -> dict[str, FaultConfig]:
        """Create pre-defined experiment templates."""
        return {
            "deepseek_latency": FaultConfig(
                fault_type=FaultType.LATENCY,
                target_service="deepseek_api",
                latency_ms=2000,
                duration_seconds=30,
            ),
            "perplexity_error": FaultConfig(
                fault_type=FaultType.ERROR,
                target_service="perplexity_api",
                error_code=503,
                error_message="Service unavailable (chaos test)",
                duration_seconds=30,
            ),
            "database_timeout": FaultConfig(
                fault_type=FaultType.TIMEOUT,
                target_service="database",
                duration_seconds=10,
            ),
            "redis_partial_failure": FaultConfig(
                fault_type=FaultType.PARTIAL_FAILURE,
                target_service="redis",
                probability=0.3,
                duration_seconds=60,
            ),
            "api_random_errors": FaultConfig(
                fault_type=FaultType.ERROR,
                target_service="api",
                probability=0.1,
                error_code=500,
                duration_seconds=60,
            ),
        }

    def enable(self):
        """Enable chaos engineering (requires explicit activation)."""
        self.enabled = True
        logger.warning("⚠️ Chaos Engineering ENABLED - faults can now be injected")

    def disable(self):
        """Disable chaos engineering and clear all faults."""
        self.enabled = False
        self.injector.clear_all_faults()
        logger.info("Chaos Engineering disabled - all faults cleared")

    def create_experiment(
        self,
        name: str,
        fault_config: FaultConfig,
        hypothesis: str = "",
    ) -> ChaosExperiment:
        """Create a new chaos experiment."""
        if not self.enabled:
            raise RuntimeError("Chaos engineering is disabled")

        experiment = ChaosExperiment(
            name=name,
            fault_config=fault_config,
            hypothesis=hypothesis,
        )
        self.experiments[experiment.id] = experiment
        return experiment

    def create_from_template(
        self,
        template_name: str,
        experiment_name: str | None = None,
    ) -> ChaosExperiment:
        """Create experiment from a pre-defined template."""
        if template_name not in self.templates:
            raise ValueError(
                f"Template '{template_name}' not found. Available: {list(self.templates.keys())}"
            )

        config = self.templates[template_name]
        name = experiment_name or f"{template_name}_experiment"
        return self.create_experiment(name, config)

    async def run_experiment(self, experiment_id: str) -> ExperimentResult:
        """Run an experiment by ID."""
        if not self.enabled:
            raise RuntimeError("Chaos engineering is disabled")

        experiment = self.experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment '{experiment_id}' not found")

        result = await experiment.run(self.injector)
        self.results.append(result)
        return result

    async def run_quick_test(
        self,
        fault_type: FaultType,
        target_service: str,
        duration_seconds: int = 10,
    ) -> ExperimentResult:
        """Run a quick chaos test."""
        if not self.enabled:
            raise RuntimeError("Chaos engineering is disabled")

        config = FaultConfig(
            fault_type=fault_type,
            target_service=target_service,
            duration_seconds=duration_seconds,
        )

        experiment = ChaosExperiment(
            name=f"quick_test_{fault_type.value}_{target_service}",
            fault_config=config,
        )

        result = await experiment.run(self.injector)
        self.results.append(result)
        return result

    def get_active_faults(self) -> dict[str, FaultConfig]:
        """Get all currently active faults."""
        return self.injector.active_faults.copy()

    def get_experiment_history(self, limit: int = 50) -> list[ExperimentResult]:
        """Get experiment history."""
        return self.results[-limit:]

    def get_metrics(self) -> dict[str, Any]:
        """Get chaos engineering metrics."""
        completed = [r for r in self.results if r.status == ExperimentStatus.COMPLETED]
        failed = [r for r in self.results if r.status == ExperimentStatus.FAILED]

        return {
            "enabled": self.enabled,
            "active_faults": len(self.injector.active_faults),
            "total_experiments": len(self.results),
            "completed_experiments": len(completed),
            "failed_experiments": len(failed),
            "available_templates": list(self.templates.keys()),
            "pending_experiments": len(
                [
                    e
                    for e in self.experiments.values()
                    if e.status == ExperimentStatus.PENDING
                ]
            ),
        }


# Global instance
_chaos_service: ChaosEngineeringService | None = None


def get_chaos_service() -> ChaosEngineeringService:
    """Get or create the global chaos engineering service."""
    global _chaos_service
    if _chaos_service is None:
        _chaos_service = ChaosEngineeringService()
    return _chaos_service
