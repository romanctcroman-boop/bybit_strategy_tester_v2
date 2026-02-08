"""
Agent Configuration Hot-Reload System
======================================
Provides centralized YAML-based configuration with file watching for hot-reload.

Features:
- YAML config file support (agents.yaml)
- Hot-reload on file changes
- Thread-safe singleton pattern
- Fallback defaults if config unavailable
"""

import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Try to import yaml - optional dependency
try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    yaml = None  # type: ignore
    YAML_AVAILABLE = False
    logger.warning("PyYAML not installed - using default configuration")


# ═══════════════════════════════════════════════════════════════════════════════════
# Configuration Data Classes
# ═══════════════════════════════════════════════════════════════════════════════════


@dataclass
class MetaConfig:
    """Meta configuration section"""

    version: int = 1
    name: str = "Agent System"
    description: str = "AI Agent Configuration"


@dataclass
class PromptConfig:
    """Prompt configuration section"""

    max_length: int = 16000
    truncate_notice: str = "[TRUNCATED]"
    system_prompt_template: str = "You are a helpful AI assistant."


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker settings"""

    failure_threshold: int = 5
    recovery_timeout: int = 60
    half_open_requests: int = 3


@dataclass
class RateLimitConfig:
    """Rate limiting settings"""

    requests_per_minute: int = 60
    burst_size: int = 10


@dataclass
class AgentConfig:
    """
    Main agent configuration container.

    Attributes:
        meta: Meta information about the config
        prompt: Prompt-related settings
        circuit_breaker: Circuit breaker settings
        rate_limit: Rate limiting settings
    """

    meta: MetaConfig = field(default_factory=MetaConfig)
    prompt: PromptConfig = field(default_factory=PromptConfig)
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)

    # Raw data for custom keys
    _raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentConfig":
        """Create AgentConfig from dictionary (parsed YAML)"""
        meta_data = data.get("meta", {})
        prompt_data = data.get("prompt", {})
        cb_data = data.get("circuit_breaker", {})
        rl_data = data.get("rate_limit", {})

        return cls(
            meta=MetaConfig(
                version=meta_data.get("version", 1),
                name=meta_data.get("name", "Agent System"),
                description=meta_data.get("description", "AI Agent Configuration"),
            ),
            prompt=PromptConfig(
                max_length=prompt_data.get("max_length", 16000),
                truncate_notice=prompt_data.get("truncate_notice", "[TRUNCATED]"),
                system_prompt_template=prompt_data.get(
                    "system_prompt_template", "You are a helpful AI assistant."
                ),
            ),
            circuit_breaker=CircuitBreakerConfig(
                failure_threshold=cb_data.get("failure_threshold", 5),
                recovery_timeout=cb_data.get("recovery_timeout", 60),
                half_open_requests=cb_data.get("half_open_requests", 3),
            ),
            rate_limit=RateLimitConfig(
                requests_per_minute=rl_data.get("requests_per_minute", 60),
                burst_size=rl_data.get("burst_size", 10),
            ),
            _raw=data,
        )

    def get(self, key: str, default: Any = None) -> Any:
        """Get raw config value by dot-separated key path"""
        parts = key.split(".")
        current = self._raw
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current


# ═══════════════════════════════════════════════════════════════════════════════════
# Global State & Callbacks
# ═══════════════════════════════════════════════════════════════════════════════════

_config: AgentConfig | None = None
_config_lock = threading.Lock()
_reload_callbacks: list[Callable[[AgentConfig], None]] = []
_config_file_path: Path | None = None


def _get_default_config_path() -> Path:
    """Get default path to agents.yaml"""
    # Look for config in project root first
    project_root = Path(__file__).resolve().parent.parent.parent
    config_path = project_root / "agents.yaml"

    # Fallback to environment variable
    env_path = os.getenv("AGENT_CONFIG_PATH")
    if env_path:
        config_path = Path(env_path)

    return config_path


def _load_config_from_file(path: Path) -> AgentConfig:
    """Load configuration from YAML file"""
    if not YAML_AVAILABLE:
        logger.debug("YAML not available, using defaults")
        return AgentConfig()

    if not path.exists():
        logger.debug(f"Config file not found: {path}, using defaults")
        return AgentConfig()

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        config = AgentConfig.from_dict(data)
        logger.info(
            f"✅ Loaded agent config from {path} (version={config.meta.version})"
        )
        return config

    except Exception as e:
        logger.error(f"❌ Failed to load config from {path}: {e}")
        return AgentConfig()


def get_agent_config() -> AgentConfig:
    """
    Get the global agent configuration (singleton).

    Thread-safe. Loads from agents.yaml on first call.

    Returns:
        AgentConfig instance with current settings
    """
    global _config, _config_file_path

    if _config is None:
        with _config_lock:
            if _config is None:  # Double-check locking
                _config_file_path = _get_default_config_path()
                _config = _load_config_from_file(_config_file_path)

    return _config


def reload_config() -> AgentConfig:
    """
    Force reload configuration from file.

    Triggers all registered callbacks after reload.

    Returns:
        New AgentConfig instance
    """
    global _config, _config_file_path

    with _config_lock:
        if _config_file_path is None:
            _config_file_path = _get_default_config_path()

        new_config = _load_config_from_file(_config_file_path)
        _config = new_config

    # Trigger reload callbacks
    for callback in _reload_callbacks:
        try:
            callback(new_config)
        except Exception as e:
            logger.error(f"Error in config reload callback: {e}")

    return new_config


def register_reload_callback(callback: Callable[[AgentConfig], None]) -> None:
    """
    Register a callback to be called when config is reloaded.

    Args:
        callback: Function that takes the new AgentConfig as argument
    """
    if callback not in _reload_callbacks:
        _reload_callbacks.append(callback)
        logger.debug(f"Registered config reload callback: {callback.__name__}")


def unregister_reload_callback(callback: Callable[[AgentConfig], None]) -> None:
    """Remove a previously registered callback"""
    if callback in _reload_callbacks:
        _reload_callbacks.remove(callback)


# ═══════════════════════════════════════════════════════════════════════════════════
# File Watcher for Hot-Reload
# ═══════════════════════════════════════════════════════════════════════════════════


class ConfigWatcher:
    """
    Watches agents.yaml for changes and triggers hot-reload.

    Uses simple polling (1 second interval) to avoid watchdog dependency.
    """

    def __init__(self, config_path: Path, poll_interval: float = 1.0):
        self.config_path = config_path
        self.poll_interval = poll_interval
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_mtime: float = 0

    def start(self) -> None:
        """Start watching for file changes"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info("Config watcher started for: %s", self.config_path)

    def stop(self) -> None:
        """Stop watching for file changes"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("Config watcher stopped")

    def _watch_loop(self) -> None:
        """Main watching loop (runs in background thread)"""
        # Initialize last mtime
        if self.config_path.exists():
            self._last_mtime = self.config_path.stat().st_mtime

        while self._running:
            try:
                if self.config_path.exists():
                    current_mtime = self.config_path.stat().st_mtime

                    if current_mtime > self._last_mtime:
                        self._last_mtime = current_mtime
                        logger.info("Config file changed, reloading...")
                        reload_config()

            except Exception as e:
                logger.error(f"Error in config watcher: {e}")

            time.sleep(self.poll_interval)


_watcher: ConfigWatcher | None = None


def start_config_watcher() -> ConfigWatcher:
    """
    Start the configuration file watcher for hot-reload.

    Returns:
        ConfigWatcher instance
    """
    global _watcher, _config_file_path

    if _watcher is not None:
        return _watcher

    if _config_file_path is None:
        _config_file_path = _get_default_config_path()

    _watcher = ConfigWatcher(_config_file_path)
    _watcher.start()

    return _watcher


def stop_config_watcher() -> None:
    """Stop the configuration file watcher"""
    global _watcher

    if _watcher is not None:
        _watcher.stop()
        _watcher = None


# ═══════════════════════════════════════════════════════════════════════════════════
# Module Exports
# ═══════════════════════════════════════════════════════════════════════════════════

__all__ = [
    "AgentConfig",
    "CircuitBreakerConfig",
    "ConfigWatcher",
    "MetaConfig",
    "PromptConfig",
    "RateLimitConfig",
    "get_agent_config",
    "register_reload_callback",
    "reload_config",
    "start_config_watcher",
    "stop_config_watcher",
    "unregister_reload_callback",
]
