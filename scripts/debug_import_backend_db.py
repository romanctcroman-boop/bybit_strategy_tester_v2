"""Debug helper: import backend.database and print attributes."""

import sys
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
if str(repo) not in sys.path:
    sys.path.insert(0, str(repo))

import importlib

mod = importlib.import_module("backend.database")
print("module:", mod)
print("file:", getattr(mod, "__file__", None))
print("attrs:", sorted([a for a in dir(mod) if not a.startswith("_")]))
print("engine present?", hasattr(mod, "engine"))
print("SessionLocal present?", hasattr(mod, "SessionLocal"))
