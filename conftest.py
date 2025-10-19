"""
Root conftest.py - loaded FIRST by pytest before any test collection.

This ensures backend modules can be imported in test files.
"""

import sys
from pathlib import Path

# Add project root to sys.path so "import backend" works
root = Path(__file__).parent.resolve()
# Ensure current working directory is project root (helps imports when pytest is started from a script)
try:
    import os
    os.chdir(str(root))
except Exception:
    pass

if str(root) not in sys.path:
    # insert at front so it takes precedence over other entries
    sys.path.insert(0, str(root))
