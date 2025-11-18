"""UTC enforcement guard test.

Purpose:
    Ensure runtime code does NOT use naive datetime.now() or datetime.utcnow().
    All timestamps must be timezone-aware via datetime.now(timezone.utc) or helper utc_now().

Temporary migration support:
    During phased migration, a whitelist of files still using naive timestamps is
    maintained. Remove entries from WHITELIST as files are patched.

Fail conditions:
    1. Any occurrence of 'datetime.now()' without 'timezone.utc' argument.
    2. Any occurrence of 'datetime.utcnow()'.

Exceptions:
    - Test files (this test only scans non-test runtime paths)
    - Alembic migration scripts (historical snapshots)

Usage:
    pytest tests/backend/test_utc_enforcement.py -q
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Directories considered runtime code (exclude tests, alembic, notebooks)
SCAN_DIRS = [
    PROJECT_ROOT / "backend",
    PROJECT_ROOT / "mcp-server",
]

# Files still pending migration (whitelist). Remove progressively.
WHITELIST = {
    # Pending migration files – remove entries as each file is patched to UTC-aware timestamps.
    # Backend core & services
    # Removed: backend/health_checks.py migrated to utc_now()
    # Removed: backend/agents/agent_background_service.py migrated to utc_now()
    # Removed: backend/agents/agent_to_agent_communicator.py migrated to utc_now()
    "backend/api/agent_to_agent_api.py",
    "backend/api/deepseek_pool.py",
    "backend/api/orchestrator.py",
    "backend/api/perplexity_client.py",
    "backend/cache/pipeline_manager.py",
    "backend/cache/warming.py",
    "backend/core/cache.py",
    "backend/core/redis_streams_queue.py",
    # ML modules migrated to utc_now() and removed from whitelist:
    # "backend/ml/drift_detector.py",
    # "backend/ml/lstm_queue_predictor.py",
    # "backend/ml/optimizer.py",
    # "backend/ml/optuna_optimizer.py",
    "backend/monitoring/agent_metrics.py",
    "backend/optimization/grid_optimizer.py",
    # Removed: backend/sandbox/docker_sandbox.py migrated to utc_now()
    # Scaling modules migrated to utc_now()
    # "backend/scaling/dynamic_worker_scaling.py",  # removed
    # "backend/scaling/health_checks.py",            # removed
    # "backend/scaling/load_balancer.py",            # removed
    # "backend/scaling/redis_consumer_groups.py",    # removed
    "backend/scripts/backup_database.py",
    "backend/scripts/dr_automation.py",
    "backend/scripts/restore_database.py",
    "backend/scripts/test_dr_system.py",
    "backend/security/key_rotation.py",
    "backend/security/sandbox_executor.py",
    # Removed: backend/services/ab_testing_service.py migrated to utc_now()
    # Removed: backend/services/anomaly_detection_service.py migrated to utc_now()
    # Removed: backend/services/automl_service.py migrated to utc_now()
    "backend/services/backup_service.py",
    "backend/services/data_manager.py",
    "backend/services/report_generator.py",
    "backend/services/strategy_arena.py",
    "backend/services/task_queue.py",
    "backend/services/task_worker.py",
    "backend/services/tournament_orchestrator.py",
    "backend/services/adapters/bybit_async.py",
    # API routers migrated to utc_now() (entries removed)
    # MCP server & orchestrator
    "mcp-server/agent_communication_layer.py",
    "mcp-server/ask_deepseek_max_permissions.py",
    "mcp-server/ask_deepseek_mcp_permissions.py",
    "mcp-server/ask_sonar_mcp_permissions.py",
    "mcp-server/deepseek_auto_refactor.py",
    "mcp-server/deepseek_auto_refactor_with_tests.py",
    "mcp-server/deepseek_background_analysis.py",
    "mcp-server/deepseek_full_analysis.py",
    "mcp-server/deepseek_integration_task.py",
    "mcp-server/deepseek_mcp_server.py",
    "mcp-server/enhanced_mcp_router.py",
    "mcp-server/implement_p1_p2_p3_full_acl.py",
    "mcp-server/monitor_acl_progress.py",
    "mcp-server/monitor_integration_pipeline.py",
    "mcp-server/multi_agent_router.py",
    "mcp-server/reasoning_engine.py",
    "mcp-server/reasoning_logger.py",
    "mcp-server/retry_handler.py",
    "mcp-server/server.py",
    "mcp-server/server_backup.py",
    "mcp-server/service_factories.py",
    "mcp-server/test_ai_interaction.py",
    "mcp-server/test_ai_interaction_full.py",
    "mcp-server/test_protocol.py",
    "mcp-server/test_security.py",
    "mcp-server/test_server_integration.py",
    "mcp-server/tools/utility/utility_tools.py",
    "mcp-server/orchestrator/api/jsonrpc.py",
    "mcp-server/orchestrator/api/metrics.py",
    "mcp-server/orchestrator/autoscaling/arima_forecaster.py",
    "mcp-server/orchestrator/autoscaling/autoscaler.py",
    "mcp-server/orchestrator/autoscaling/latency_autoscaler.py",
    "mcp-server/orchestrator/autoscaling/latency_monitor.py",
    "mcp-server/orchestrator/autoscaling/metrics_collector.py",
    "mcp-server/orchestrator/plugins/audit_logger.py",
    "mcp-server/orchestrator/plugins/metrics_collector.py",
    "mcp-server/orchestrator/queue/example_usage.py",
    "mcp-server/orchestrator/queue/redis_streams.py",
    "mcp-server/orchestrator/queue/test_redis_streams.py",
    "mcp-server/orchestrator/workers/express_pool.py",
    "mcp-server/orchestrator/workers/test_failure_recovery.py",
    "mcp-server/orchestrator/workers/test_integration.py",
    "mcp-server/orchestrator/workers/test_phase_2_3.py",
    "mcp-server/orchestrator/workers/test_predictive_autoscaling.py",
    "mcp-server/orchestrator/workers/test_preemptive_routing.py",
    "mcp-server/orchestrator/workers/worker_pool.py",
    "mcp-server/api/providers/perplexity.py",
    # Utility module still mentions naive patterns (documentation line)
    "backend/utils/time.py",
}

# Regex patterns for naive usages
PATTERN_NOW = re.compile(r"datetime\.now\(\)")
PATTERN_UTCNOW = re.compile(r"datetime\.utcnow\(\)")

# Allow timezone-aware explicit usage or helper calls; negative filters
ALLOW_PATTERNS = [
    re.compile(r"datetime\.now\(timezone\.utc\)"),
    re.compile(r"utc_now\("),
]

def is_python_runtime_file(p: Path) -> bool:
    if not p.is_file() or p.suffix != ".py":
        return False
    rel = p.relative_to(PROJECT_ROOT).as_posix()
    if rel.startswith("tests/"):
        return False
    if rel.startswith("alembic/"):
        return False
    return True


def find_violations() -> list[tuple[str, str]]:
    violations: list[tuple[str, str]] = []
    for base in SCAN_DIRS:
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            if not is_python_runtime_file(p):
                continue
            rel = p.relative_to(PROJECT_ROOT).as_posix()
            content = p.read_text(encoding="utf-8", errors="ignore")

            # Skip whitelist entries
            if rel in WHITELIST:
                continue

            # Filter out allowed timezone-aware usages before naive detection
            # Replace allowed patterns temporarily to avoid false positives
            filtered = content
            for ap in ALLOW_PATTERNS:
                filtered = ap.sub("", filtered)

            if PATTERN_NOW.search(filtered):
                violations.append((rel, "datetime.now()"))
            if PATTERN_UTCNOW.search(filtered):
                violations.append((rel, "datetime.utcnow()"))
    return violations


def test_no_naive_datetimes():
    violations = find_violations()
    if violations:
        formatted = "\n".join(f" - {path}: {kind}" for path, kind in violations)
        raise AssertionError(
            "Found naive datetime usages (remove or whitelist during migration):\n" + formatted
        )
