"""
Common utilities for scripts directory.

Usage in scripts:
    # Instead of: sys.path.insert(0, 'd:/bybit_strategy_tester_v2')
    # Use:
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    # Or import this module:
    from scripts._common import PROJECT_ROOT, get_db_path
"""

import os
from pathlib import Path

# Project root directory (parent of scripts/)
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Common paths
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
CACHE_DIR = PROJECT_ROOT / ".cache"


def get_db_path() -> Path:
    """Get database path from env or default."""
    db_path = os.environ.get("DATABASE_PATH")
    if db_path:
        return Path(db_path)
    return PROJECT_ROOT / "data.sqlite3"


def get_data_db_path() -> Path:
    """Get data database path."""
    return PROJECT_ROOT / "data.sqlite3"


def setup_project_path():
    """Add project root to sys.path if not present."""
    import sys

    root_str = str(PROJECT_ROOT)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


# Auto-setup on import
setup_project_path()
