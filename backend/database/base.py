"""Re-export Base from __init__ for backward compatibility.

This module allows imports like:
    from backend.database.base import Base

Which is equivalent to:
    from backend.database import Base
"""

from backend.database import Base

__all__ = ["Base"]
