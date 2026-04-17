"""
Provider Health Monitor

Monitors availability of Anthropic (Claude) and Perplexity APIs.
Used for pre-flight checks before pipeline start and reactive error detection.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum

import aiohttp
from loguru import logger


class ProviderStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass
class HealthResult:
    provider: str
    status: ProviderStatus
    message: str
    latency_ms: float = 0.0
    checked_at: float = field(default_factory=time.time)

    @property
    def is_ok(self) -> bool:
        return self.status == ProviderStatus.OK

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "status": self.status.value,
            "message": self.message,
            "latency_ms": round(self.latency_ms, 1),
            "checked_at": self.checked_at,
        }


class ProviderHealthMonitor:
    """
    Checks availability of Anthropic and Perplexity APIs.

    Usage:
        monitor = ProviderHealthMonitor()
        report = await monitor.preflight_check()
        if not report["all_ok"]:
            logger.warning(f"Provider issues: {report}")
    """

    # Minimal test prompts (1-2 tokens output) to verify API reachability
    _ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
    _PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
    _TIMEOUT = aiohttp.ClientTimeout(total=10.0)

    def __init__(self) -> None:
        self._last_check: dict[str, HealthResult] = {}
        self._cache_ttl = 60.0  # re-check at most every 60s

    async def check_anthropic(self, api_key: str | None = None) -> HealthResult:
        """Verify Anthropic API with a minimal 1-token call."""
        import os

        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            # Fallback: try key_manager (respects .env loaded at server start)
            try:
                from backend.security.key_manager import get_key_manager

                km = get_key_manager()
                key = km.get_key("ANTHROPIC_API_KEY") or ""
            except Exception:
                pass
        if not key:
            return HealthResult("anthropic", ProviderStatus.UNKNOWN, "ANTHROPIC_API_KEY not set")

        start = time.time()
        try:
            async with aiohttp.ClientSession(timeout=self._TIMEOUT) as session:
                payload = {
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "Hi"}],
                }
                headers = {
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }
                async with session.post(self._ANTHROPIC_URL, json=payload, headers=headers) as resp:
                    latency = (time.time() - start) * 1000
                    if resp.status == 200:
                        result = HealthResult("anthropic", ProviderStatus.OK, "API reachable", latency)
                    elif resp.status in (401, 403):
                        result = HealthResult("anthropic", ProviderStatus.DOWN, f"Auth error: {resp.status}", latency)
                    elif resp.status == 529:
                        result = HealthResult("anthropic", ProviderStatus.DEGRADED, "Overloaded (529)", latency)
                    elif resp.status >= 500:
                        result = HealthResult(
                            "anthropic", ProviderStatus.DEGRADED, f"Server error: {resp.status}", latency
                        )
                    else:
                        try:
                            body = await resp.json()
                            detail = body.get("error", {}).get("message", "")[:120]
                        except Exception:
                            detail = ""
                        result = HealthResult(
                            "anthropic",
                            ProviderStatus.UNKNOWN,
                            f"Unexpected status: {resp.status}" + (f" — {detail}" if detail else ""),
                            latency,
                        )
        except TimeoutError:
            result = HealthResult("anthropic", ProviderStatus.DOWN, "Timeout (>10s)")
        except Exception as e:
            result = HealthResult("anthropic", ProviderStatus.DOWN, f"Connection error: {e}")

        self._last_check["anthropic"] = result
        if not result.is_ok:
            logger.warning(f"Anthropic health: {result.status.value} — {result.message}")
        else:
            logger.debug(f"Anthropic OK ({result.latency_ms:.0f}ms)")
        return result

    async def check_perplexity(self, api_key: str | None = None) -> HealthResult:
        """Verify Perplexity API with a minimal call."""
        import os

        key = api_key or os.environ.get("PERPLEXITY_API_KEY", "")
        if not key:
            return HealthResult("perplexity", ProviderStatus.UNKNOWN, "PERPLEXITY_API_KEY not set")

        start = time.time()
        try:
            async with aiohttp.ClientSession(timeout=self._TIMEOUT) as session:
                payload = {
                    "model": "sonar",  # cheapest model for health check
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "Hi"}],
                }
                headers = {
                    "Authorization": f"Bearer {key}",
                    "content-type": "application/json",
                }
                async with session.post(self._PERPLEXITY_URL, json=payload, headers=headers) as resp:
                    latency = (time.time() - start) * 1000
                    if resp.status == 200:
                        result = HealthResult("perplexity", ProviderStatus.OK, "API reachable", latency)
                    elif resp.status in (401, 403):
                        result = HealthResult("perplexity", ProviderStatus.DOWN, f"Auth error: {resp.status}", latency)
                    elif resp.status >= 500:
                        result = HealthResult(
                            "perplexity", ProviderStatus.DEGRADED, f"Server error: {resp.status}", latency
                        )
                    else:
                        result = HealthResult("perplexity", ProviderStatus.UNKNOWN, f"Status: {resp.status}", latency)
        except TimeoutError:
            result = HealthResult("perplexity", ProviderStatus.DOWN, "Timeout (>10s)")
        except Exception as e:
            result = HealthResult("perplexity", ProviderStatus.DOWN, f"Connection error: {e}")

        self._last_check["perplexity"] = result
        if not result.is_ok:
            logger.warning(f"Perplexity health: {result.status.value} — {result.message}")
        else:
            logger.debug(f"Perplexity OK ({result.latency_ms:.0f}ms)")
        return result

    async def preflight_check(
        self,
        anthropic_key: str | None = None,
        perplexity_key: str | None = None,
    ) -> dict:
        """
        Run both checks in parallel. Returns status report dict.
        Logs WARNING if either provider is not OK.
        Does NOT raise — pipeline continues with degraded functionality.
        """
        anthropic_result, perplexity_result = await asyncio.gather(
            self.check_anthropic(anthropic_key),
            self.check_perplexity(perplexity_key),
            return_exceptions=True,
        )

        # Handle unexpected exceptions from gather
        if isinstance(anthropic_result, Exception):
            anthropic_result = HealthResult("anthropic", ProviderStatus.DOWN, str(anthropic_result))
        if isinstance(perplexity_result, Exception):
            perplexity_result = HealthResult("perplexity", ProviderStatus.DOWN, str(perplexity_result))

        all_ok = anthropic_result.is_ok and perplexity_result.is_ok

        if not all_ok:
            issues = []
            if not anthropic_result.is_ok:
                issues.append(f"Anthropic {anthropic_result.status.value}: {anthropic_result.message}")
            if not perplexity_result.is_ok:
                issues.append(f"Perplexity {perplexity_result.status.value}: {perplexity_result.message}")
            logger.warning(f"Provider health issues detected: {'; '.join(issues)}")
        else:
            logger.info(
                f"Providers OK — Anthropic {anthropic_result.latency_ms:.0f}ms, "
                f"Perplexity {perplexity_result.latency_ms:.0f}ms"
            )

        return {
            "all_ok": all_ok,
            "anthropic": anthropic_result.to_dict(),
            "perplexity": perplexity_result.to_dict(),
        }

    def get_cached_status(self) -> dict:
        """Return last known status without making new API calls."""
        return {provider: result.to_dict() for provider, result in self._last_check.items()}


# Singleton
_monitor: ProviderHealthMonitor | None = None


def get_health_monitor() -> ProviderHealthMonitor:
    global _monitor
    if _monitor is None:
        _monitor = ProviderHealthMonitor()
    return _monitor


__all__ = ["HealthResult", "ProviderHealthMonitor", "ProviderStatus", "get_health_monitor"]
