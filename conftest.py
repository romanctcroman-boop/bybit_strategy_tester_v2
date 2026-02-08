"""
Root pytest configuration.

This ensures correct import resolution by adding the project root to sys.path
before any test modules are collected.
"""

import sys
from pathlib import Path

# Add project root to path FIRST
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Pre-import backend to ensure correct resolution
import backend
import backend.database  # noqa: F401
