"""Compatibility shim for importing configuration helpers.

This module re-exports objects from the package-based backend.config namespace
while advertising a __path__ so submodules (e.g. backend.config.timeout_config)
continue to work."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

_pkg: ModuleType = importlib.import_module("backend.config.__init__")
CONFIG = getattr(_pkg, "CONFIG")
SETTINGS = getattr(_pkg, "SETTINGS", None)
_ns = getattr(_pkg, "_ns")
_build_config = getattr(_pkg, "_build_config")

# Re-export for backwards compatibility
__all__ = ["CONFIG", "SETTINGS", "_ns", "_build_config"]

# Advertise package path so "backend.config.*" imports resolve correctly
__path__ = [str(Path(__file__).with_suffix(""))]
