"""
Pytest configuration for the entire test suite.

This file MUST be at tests/conftest.py to be loaded before test collection.
"""

import sys
import os
from pathlib import Path

# Add project root to Python path BEFORE any test imports
# This allows imports like "from backend.utils.timestamp_utils import ..."
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

# Also set PYTHONPATH environment variable
os.environ['PYTHONPATH'] = str(project_root)
