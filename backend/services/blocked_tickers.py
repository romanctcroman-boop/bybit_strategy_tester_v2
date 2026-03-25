"""
Blocked Tickers Service.

Manages the list of tickers blocked from auto-reload at startup and in Properties.
Stored in data/blocked_tickers.json.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BLOCKED_FILE = PROJECT_ROOT / "data" / "blocked_tickers.json"


def _ensure_data_dir() -> None:
    BLOCKED_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_raw() -> dict:
    _ensure_data_dir()
    if not BLOCKED_FILE.exists():
        return {"symbols": []}
    try:
        with open(BLOCKED_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load blocked tickers: {e}")
        return {"symbols": []}


def _save(data: dict) -> None:
    _ensure_data_dir()
    with open(BLOCKED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_blocked() -> set[str]:
    """
    Return set of blocked symbol strings (uppercase).
    По умолчанию всё разблокировано: при отсутствии файла или пустом списке возвращает пустое множество.
    """
    data = _load_raw()
    syms = data.get("symbols", [])
    return {str(s).strip().upper() for s in syms if s}


def add_blocked(symbol: str) -> bool:
    """Add symbol to blocked list. Returns True if added."""
    symbol = symbol.strip().upper()
    if not symbol:
        return False
    data = _load_raw()
    syms = data.get("symbols", [])
    if symbol not in syms:
        syms.append(symbol)
        data["symbols"] = sorted(syms)
        _save(data)
        return True
    return False


def remove_blocked(symbol: str) -> bool:
    """Remove symbol from blocked list. Returns True if removed."""
    symbol = symbol.strip().upper()
    data = _load_raw()
    syms = data.get("symbols", [])
    if symbol in syms:
        syms.remove(symbol)
        data["symbols"] = syms
        _save(data)
        return True
    return False


def is_blocked(symbol: str) -> bool:
    """Check if symbol is blocked."""
    return symbol.strip().upper() in get_blocked()
