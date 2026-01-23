"""Small shim to modify sys.path so the `mcp-server` package is importable.
This shim is safe to import at module level and keeps path-manipulation logic
out of application modules, which helps linters and keeps imports at the top.
"""

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
_mcp_server_path = _project_root / "mcp-server"
if _mcp_server_path.exists() and str(_mcp_server_path) not in sys.path:
    sys.path.insert(0, str(_mcp_server_path))
