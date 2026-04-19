"""
🤖 AI Agent Background Service - Автозапуск с IDE

Функции:
1. ✅ Автоматический запуск при старте IDE (через runOptions.runOn: "folderOpen")
2. ✅ Расшифровка всех API ключей (Claude + Perplexity)
3. ✅ Health checks каждые 30 секунд
4. ✅ Автоматический fallback MCP → Direct API
5. ✅ Мониторинг и логирование всех операций
6. ✅ Автоматическое переключение между API ключами при ошибках

Использование:
    python backend/agents/agent_background_service.py

    Или через VS Code task (автозапуск):
    tasks.json → "Start AI Agent Service" → runOptions.runOn: "folderOpen"
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# ✅ FIX: Add project root to sys.path for imports
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ✅ FIX: Windows console encoding for emoji support
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Load .env file BEFORE any other imports
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# ✅ FIX: Now backend imports will work
from backend.utils.time import utc_now

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import httpx

from backend.agents.circuit_breaker_manager import (
    CircuitBreakerError,
    CircuitState,
)
from backend.agents.unified_agent_interface import (
    AgentRequest,
    AgentType,
    APIKeyHealth,
    get_agent_interface,
)
from backend.services.fallback_service import get_fallback_service

# =============================================================================
# BACKGROUND SERVICE
# =============================================================================


class AIAgentBackgroundService:
    """
    Фоновый сервис для AI агентов

    Работает непрерывно с момента запуска IDE
    """

    def __init__(self):
        self.running = False
        self.start_time = time.time()
        self.health_check_interval = 30  # seconds - lightweight check
        self.full_health_check_interval = 300  # seconds (5 min) - with real API calls
        self.last_full_check = 0

        # Skip full API health checks if AGENT_SKIP_API_HEALTHCHECK=1
        # This prevents unnecessary API calls when not actively using agents
        self.skip_api_healthcheck = os.getenv("AGENT_SKIP_API_HEALTHCHECK", "0") == "1"

        self.mcp_health_url = (
            os.getenv("MCP_AGENT_HEALTH_URL")
            or os.getenv("MCP_HEALTH_URL")
            or "http://127.0.0.1:8000/api/v1/agent/health"
        )
        self.mcp_health_timeout = float(os.getenv("MCP_AGENT_HEALTH_TIMEOUT", "5"))

        # Initialize unified interface
        try:
            self.interface = get_agent_interface()
            logger.success("✅ Unified Agent Interface initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize interface: {e}")
            raise

        # Statistics
        self.stats = {
            "health_checks": 0,
            "health_check_failures": 0,
            "api_key_rotations": 0,
            "mcp_availability_changes": 0,
            "mcp_breaker_rejections": 0,
        }
        self.interface.stats["mcp_breaker_rejections"] = 0

        # Initialize fallback service for graceful degradation
        try:
            self.fallback_service = get_fallback_service()
            self.fallback_service.register_service("claude")
            self.fallback_service.register_service("perplexity")
            self.fallback_service.register_service("mcp_server")
            logger.success("✅ FallbackService initialized")
        except Exception as e:
            logger.warning(f"⚠️ FallbackService not available: {e}")
            self.fallback_service = None

    async def start(self):
        """Запустить фоновый сервис"""
        self.running = True

        logger.info("=" * 80)
        logger.info("🚀 AI AGENT BACKGROUND SERVICE STARTED")
        logger.info("=" * 80)
        # UTC-aware start timestamp
        logger.info(f"📅 Started at: {utc_now().isoformat()}")
        logger.info(f"🔑 Claude keys: {len(self.interface.key_manager.claude_keys)}")
        logger.info(f"🔑 Perplexity keys: {len(self.interface.key_manager.perplexity_keys)}")
        logger.info("=" * 80)

        # Initial health check
        await self._comprehensive_health_check()

        # Main loop
        try:
            while self.running:
                await asyncio.sleep(self.health_check_interval)
                await self._comprehensive_health_check()

        except asyncio.CancelledError:
            logger.info("⚠️ Service cancelled")
        except KeyboardInterrupt:
            logger.info("⚠️ Service interrupted by user")
        except Exception as e:
            logger.error(f"❌ Service error: {e}")
            raise
        finally:
            await self.stop()

    async def _comprehensive_health_check(self):
        """Комплексная проверка здоровья всех систем"""
        self.stats["health_checks"] += 1
        current_time = time.time()

        # Determine if this should be a full check (with API calls)
        # Skip full checks if AGENT_SKIP_API_HEALTHCHECK=1
        is_full_check = (
            not self.skip_api_healthcheck and (current_time - self.last_full_check) >= self.full_health_check_interval
        )
        check_type = "FULL" if is_full_check else "LIGHTWEIGHT"

        if self.skip_api_healthcheck and self.stats["health_checks"] == 1:
            logger.info("ℹ️ AGENT_SKIP_API_HEALTHCHECK=1: No API calls for health checks")

        logger.info("─" * 80)
        logger.info(f"🏥 HEALTH CHECK #{self.stats['health_checks']} ({check_type})")
        logger.info(f"🕐 {utc_now().strftime('%H:%M:%S')}")
        logger.info("─" * 80)

        try:
            # 1. Check API Keys (always lightweight)
            await self._check_api_keys()

            # 2. Check MCP Server (always lightweight)
            await self._check_mcp_server()

            # 3. Test Claude connection
            if is_full_check:
                await self._test_claude_connection_full()
                self.last_full_check = current_time
            else:
                await self._test_claude_connection()

            # 4. Test Perplexity connection
            if is_full_check:
                await self._test_perplexity_connection_full()
            else:
                await self._test_perplexity_connection()

            # 5. Check circuit breakers status
            await self._check_circuit_breakers()

            # 6. Print summary
            self._print_health_summary()

            logger.success("✅ Health check completed")

        except Exception as e:
            self.stats["health_check_failures"] += 1
            logger.error(f"❌ Health check failed: {e}")

    async def _check_api_keys(self):
        """Проверка API ключей"""
        km = self.interface.key_manager

        claude_active = sum(1 for k in km.claude_keys if k.is_usable)
        claude_total = len(km.claude_keys)

        perplexity_active = sum(1 for k in km.perplexity_keys if k.is_usable)
        perplexity_total = len(km.perplexity_keys)

        logger.info(f"🔑 Claude keys: {claude_active}/{claude_total} usable")
        logger.info(f"🔑 Perplexity keys: {perplexity_active}/{perplexity_total} usable")

        # Check if need to rotate keys (all have errors)
        if claude_active == 0 and claude_total > 0:
            logger.warning("⚠️ All Claude keys disabled, attempting validation-based recovery...")
            recovered = 0
            for key in km.claude_keys:
                if getattr(key, "health", None) == APIKeyHealth.DISABLED:
                    ok = await self.interface._test_key_health(AgentType.CLAUDE, key)
                    if ok:
                        key.error_count = 1
                        key.health = APIKeyHealth.DEGRADED
                        key.last_error_time = None
                        recovered += 1
            if recovered:
                logger.info(f"✅ Claude: Re-enabled {recovered} keys (DEGRADED)")
                self.stats["api_key_rotations"] += 1

        if perplexity_active == 0 and perplexity_total > 0:
            logger.warning("⚠️ All Perplexity keys disabled, attempting validation-based recovery...")
            recovered = 0
            for key in km.perplexity_keys:
                if getattr(key, "health", None) == APIKeyHealth.DISABLED:
                    ok = await self.interface._test_key_health(AgentType.PERPLEXITY, key)
                    if ok:
                        key.error_count = 1
                        key.health = APIKeyHealth.DEGRADED
                        key.last_error_time = None
                        recovered += 1
            if recovered:
                logger.info(f"✅ Perplexity: Re-enabled {recovered} keys (DEGRADED)")
                self.stats["api_key_rotations"] += 1

    async def _check_mcp_server(self):
        """Проверка MCP Server (теперь встроен в FastAPI на /mcp)"""
        previous = self.interface.mcp_available
        is_available = False
        circuit_manager = getattr(self.interface, "circuit_manager", None)
        breaker_name = "mcp_server"
        breaker_blocked = False

        async def _probe_mcp_health():
            async with httpx.AsyncClient(timeout=self.mcp_health_timeout) as client:
                response = await client.get("http://127.0.0.1:8000/mcp/health")
                response.raise_for_status()
                return response

        try:
            if circuit_manager:
                breaker_state = circuit_manager.get_breaker_state(breaker_name)
                if breaker_state == CircuitState.OPEN:
                    breaker_blocked = True
                    self._increment_mcp_breaker_rejections()
                    logger.warning("⛔ MCP circuit breaker OPEN, skipping health probe")
                    raise CircuitBreakerError("mcp_server breaker open")
                response = await circuit_manager.call_with_breaker(
                    breaker_name,
                    _probe_mcp_health,
                )
            else:
                response = await _probe_mcp_health()

            data = response.json()
            tools = data.get("tools_registered", [])

            # Check if agent tools are registered
            required_tools = [
                "mcp_agent_to_agent_send_to_claude",
                "mcp_agent_to_agent_send_to_perplexity",
                "mcp_agent_to_agent_get_consensus",
            ]

            # Verify all required tools exist
            is_available = all(tool in tools for tool in required_tools) and data.get("status") in (
                "healthy",
                "degraded",
            )

            if is_available:
                logger.debug(f"✅ MCP tools: {len(tools)} total, agent tools available")
            else:
                missing = [t for t in required_tools if t not in tools]
                logger.warning(f"⚠️ Missing MCP tools: {missing}")

        except httpx.HTTPStatusError as exc:
            logger.warning(f"⚠️ MCP health probe HTTP error {exc.response.status_code}")
            is_available = False
        except httpx.TimeoutException:
            logger.warning(f"⚠️ MCP health probe timeout ({self.mcp_health_timeout}s)")
            is_available = False
        except CircuitBreakerError:
            logger.warning("⚠️ MCP health probe blocked by circuit breaker")
            if not breaker_blocked:
                self._increment_mcp_breaker_rejections()
            is_available = False
        except Exception as exc:
            logger.warning(f"⚠️ MCP health probe failed: {exc}")
            is_available = False

        self.interface.mcp_available = is_available

        if previous != is_available:
            self.stats["mcp_availability_changes"] += 1
            status = "Available" if is_available else "Unavailable"
            logger.info(f"🔄 MCP availability changed → {status}")

        status_icon = "✅" if is_available else "❌"
        status_text = "Available" if is_available else "Unavailable"
        logger.info(f"{status_icon} MCP Server: {status_text}")

        # Update fallback service health
        if self.fallback_service:
            from backend.services.fallback_service import ServiceHealth

            health = ServiceHealth.HEALTHY if is_available else ServiceHealth.UNHEALTHY
            self.fallback_service.update_service_health(
                "mcp_server",
                health=health,
                circuit_state=str(circuit_manager.get_breaker_state("mcp_server") if circuit_manager else "unknown"),
            )

    async def _check_circuit_breakers(self):
        """Check status of all circuit breakers"""
        circuit_manager = getattr(self.interface, "circuit_manager", None)
        if not circuit_manager:
            logger.debug("No circuit manager available")
            return

        breaker_names = ["claude", "perplexity", "mcp_server"]
        open_breakers = []
        half_open_breakers = []

        for name in breaker_names:
            try:
                state = circuit_manager.get_breaker_state(name)
                if state == CircuitState.OPEN:
                    open_breakers.append(name)
                elif state == CircuitState.HALF_OPEN:
                    half_open_breakers.append(name)

                # Update fallback service with breaker state
                if self.fallback_service:
                    from backend.services.fallback_service import ServiceHealth

                    if state == CircuitState.OPEN:
                        health = ServiceHealth.UNHEALTHY
                    elif state == CircuitState.HALF_OPEN:
                        health = ServiceHealth.DEGRADED
                    else:
                        health = ServiceHealth.HEALTHY

                    # Get metrics if available
                    metrics = circuit_manager.get_breaker_metrics(name) or {}

                    self.fallback_service.update_service_health(
                        name,
                        health=health,
                        circuit_state=state.value,
                        latency_p95=metrics.get("latency_p95_ms", 0),
                        error_rate=metrics.get("error_rate", 0),
                    )

            except Exception as e:
                logger.debug(f"Could not check breaker {name}: {e}")

        if open_breakers:
            logger.warning(f"⛔ OPEN circuit breakers: {', '.join(open_breakers)}")
        if half_open_breakers:
            logger.info(f"⚠️ HALF_OPEN circuit breakers: {', '.join(half_open_breakers)}")
        if not open_breakers and not half_open_breakers:
            logger.info("✅ All circuit breakers: CLOSED")

    async def _test_claude_connection(self):
        """Легковесная проверка Claude (без реальных API calls)"""
        try:
            km = self.interface.key_manager
            active_keys = [k for k in km.claude_keys if k.is_usable]

            if active_keys:
                total = len(km.claude_keys)
                logger.success(f"✅ Claude: Ready ({len(active_keys)}/{total} keys)")
            else:
                logger.warning("⚠️ Claude: No usable keys available")

        except Exception as e:
            logger.error(f"❌ Claude: Health check failed - {e}")

    async def _test_perplexity_connection(self):
        """Легковесная проверка Perplexity (без реальных API calls)"""
        try:
            km = self.interface.key_manager
            active_keys = [k for k in km.perplexity_keys if k.is_usable]

            if active_keys:
                # Check if at least one key is available (no actual API call)
                total = len(km.perplexity_keys)
                logger.success(f"✅ Perplexity: Ready ({len(active_keys)}/{total} keys)")
            else:
                logger.warning("⚠️ Perplexity: No usable keys available")

        except Exception as e:
            logger.error(f"❌ Perplexity: Health check failed - {e}")

    async def _test_claude_connection_full(self):
        """Полная проверка Claude с реальным API call"""
        try:
            logger.info("🔍 Claude: Running full connectivity test...")
            request = AgentRequest(
                agent_type=AgentType.CLAUDE,
                task_type="health_check",
                prompt="Reply with 'OK' if you can read this message.",
            )

            response = await self.interface.send_request(request)

            if response.success:
                key_idx = response.api_key_index
                latency = response.latency_ms
                logger.success(f"✅ Claude: Connected (key #{key_idx}, {latency:.0f}ms)")
            else:
                logger.warning(f"⚠️ Claude: Failed - {response.error}")

        except Exception as e:
            logger.error(f"❌ Claude: Connection test failed - {e}")

    async def _test_perplexity_connection_full(self):
        """Полная проверка Perplexity с реальным API call"""
        try:
            logger.info("🔍 Perplexity: Running full connectivity test...")
            request = AgentRequest(
                agent_type=AgentType.PERPLEXITY,
                task_type="health_check",
                prompt="What is 2+2?",
            )

            response = await self.interface.send_request(request)

            if response.success:
                key_idx = response.api_key_index
                latency = response.latency_ms
                logger.success(f"✅ Perplexity: Connected (key #{key_idx}, {latency:.0f}ms)")
            else:
                logger.warning(f"⚠️ Perplexity: Failed - {response.error}")

        except Exception as e:
            logger.error(f"❌ Perplexity: Connection test failed - {e}")

    def _print_health_summary(self):
        """Вывести сводку о здоровье системы"""
        uptime = time.time() - self.start_time
        uptime_str = f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m {int(uptime % 60)}s"

        try:
            stats = self.interface.get_stats()
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            stats = {
                "total_requests": 0,
                "mcp_success": 0,
                "mcp_failed": 0,
                "direct_api_success": 0,
                "direct_api_failed": 0,
            }

        logger.info("─" * 80)
        logger.info("📊 STATISTICS")
        logger.info(f"⏱️  Uptime: {uptime_str}")
        logger.info(f"📈 Total requests: {stats.get('total_requests', 0)}")
        logger.info(f"✅ MCP success: {stats.get('mcp_success', 0)}")
        logger.info(f"❌ MCP failed: {stats.get('mcp_failed', 0)}")
        logger.info(f"✅ Direct API success: {stats.get('direct_api_success', 0)}")
        logger.info(f"❌ Direct API failed: {stats.get('direct_api_failed', 0)}")
        logger.info(f"🔄 Key rotations: {self.stats.get('api_key_rotations', 0)}")
        logger.info(f"🚦 MCP breaker skips: {self.stats.get('mcp_breaker_rejections', 0)}")
        logger.info("─" * 80)

    def _increment_mcp_breaker_rejections(self) -> None:
        self.stats["mcp_breaker_rejections"] += 1
        self.interface.stats["mcp_breaker_rejections"] = self.stats["mcp_breaker_rejections"]

    async def stop(self):
        """Остановить сервис"""
        self.running = False
        logger.info("=" * 80)
        logger.info("🛑 AI AGENT BACKGROUND SERVICE STOPPED")
        logger.info("=" * 80)


# =============================================================================
# CLI
# =============================================================================


async def main():
    """Main entry point"""

    # Configure logging with UTF-8 encoding for emoji support
    logger.remove()

    # Create a UTF-8 safe stdout sink
    import io

    utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    logger.add(
        utf8_stdout,
        format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
        colorize=True,
    )
    logger.add(
        Path(__file__).parent.parent.parent / "logs" / "ai_agent_service_{time}.log",
        rotation="1 day",
        retention="7 days",
        level="DEBUG",
        encoding="utf-8",
    )

    # Start service
    service = AIAgentBackgroundService()
    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("⚠️ Interrupted by user")
    except Exception as e:
        logger.error(f"❌ Service crashed: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
