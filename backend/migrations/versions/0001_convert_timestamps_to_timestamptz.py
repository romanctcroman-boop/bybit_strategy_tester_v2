"""
Compatibility shim for tests: expose upgrade_sqls/downgrade_sqls under the filename the tests expect.

This module dynamically loads the existing migration module `1a2b3c4d5e6f_convert_timestamps_to_timestamptz.py`
and re-exports the helper functions so tests that load the file by path work without changing the repo history.

The file also includes minimal Alembic revision identifiers so Alembic's script loader can parse this file when scanning
the `versions/` directory during `alembic upgrade` runs. The shim delegates the real logic to the template module.
"""

import importlib.util  # noqa: E402
from pathlib import Path  # noqa: E402

# Alembic revision identifiers (shim values; real migration logic lives in the template module)
revision = "0001_convert_timestamps_to_timestamptz"
down_revision = None
branch_labels = None
depends_on = None

_here = Path(__file__).resolve().parent
_src = _here / "1a2b3c4d5e6f_convert_timestamps_to_timestamptz.py"
spec = importlib.util.spec_from_file_location("mig_src", str(_src))
_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_mod)

upgrade_sqls = getattr(_mod, "upgrade_sqls")
downgrade_sqls = getattr(_mod, "downgrade_sqls")

__all__ = ["upgrade_sqls", "downgrade_sqls"]
