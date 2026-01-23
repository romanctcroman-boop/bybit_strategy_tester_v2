"""
Pytest configuration for the test suite.

CRITICAL: This conftest ensures proper import resolution between the
tests/backend directory and the actual backend package in the project root.
"""

import sys
from pathlib import Path

# Ensure the project root is at the BEGINNING of sys.path
# This is CRITICAL for proper import resolution
project_root = Path(__file__).parent.parent

# Remove the tests directory from path if present (can cause conflicts)
tests_dir = str(Path(__file__).parent)
if tests_dir in sys.path:
    sys.path.remove(tests_dir)

# Insert project root at the beginning
if str(project_root) in sys.path:
    sys.path.remove(str(project_root))
sys.path.insert(0, str(project_root))
