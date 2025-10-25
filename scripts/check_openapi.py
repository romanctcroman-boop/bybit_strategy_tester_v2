"""
Quick sanity check that FastAPI/Pydantic can generate OpenAPI with our generic models.

Usage:
  python scripts/check_openapi.py
"""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure repository root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from backend.api.app import app


def main() -> None:
    d = app.openapi()
    ok = bool(d and "components" in d and "schemas" in d["components"])
    print("OPENAPI_OK", ok)


if __name__ == "__main__":
    main()
