from __future__ import annotations

"""Mock Backtests API backed by local CSV files.

Environment variables:
  - MOCK_BT_DIR: directory containing 1.csv..6.csv

Endpoints (drop-in replacement for real /backtests):
  GET /          -> list with a single mock backtest
  GET /{id}      -> the same mock backtest
  GET /{id}/trades -> trades parsed and normalized from 6.csv

CSV expectations:
  - 5.csv: key;value pairs (semicolon-delimited) used for metadata
  - 6.csv: trades log (comma-delimited) with two rows per trade: entry/exit
    - 1.csv: OHLCV candles (time, open, high, low, close[, volume])
    - 2.csv: indicators per-bar (time plus any number of indicator columns)
    - 3.csv: benchmarks/Buy&Hold or any auxiliary per-bar series
    - 4.csv: growth/drawdown per-bar (time plus equity/growth and/or drawdown)
"""

import csv
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query


router = APIRouter()


# -----------------------------
# Parsing helpers (cached)
# -----------------------------


@dataclass
class MockBacktest:
    id: int
    strategy_id: int
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    initial_capital: float
    leverage: Optional[float] = None
    status: str = "completed"
    results: Optional[Dict[str, Any]] = None


_CACHE: Dict[str, Any] = {}


def _read_text(path: str) -> str:
    # Try UTF-8 first, then cp1251 (common for RU CSV)
    for enc in ("utf-8", "utf-8-sig", "cp1251"):
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                return f.read()
        except Exception:
            continue
    raise FileNotFoundError(path)


def _parse_params_csv(dirpath: str) -> Dict[str, str]:
    key = ("params", dirpath)
    if key in _CACHE:
        return _CACHE[key]
    path = os.path.join(dirpath, "5.csv")
    if not os.path.exists(path):
        return {}
    text = _read_text(path)
    rows: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip().strip("\ufeff")
        if not line:
            continue
        # semicolon separated: key;value
        parts = [p.strip() for p in line.split(";")]
        if len(parts) >= 2:
            rows[parts[0]] = parts[1]
    _CACHE[key] = rows
    return rows


def _parse_trades_csv(dirpath: str) -> List[Dict[str, Any]]:
    key = ("trades", dirpath)
    if key in _CACHE:
        return _CACHE[key]
    path = os.path.join(dirpath, "6.csv")
    if not os.path.exists(path):
        return []
    # Comma-delimited, RU headers
    content = _read_text(path)
    # Normalize newlines for csv reader
    lines = [l for l in content.splitlines() if l.strip()]
    reader = csv.reader(lines)
    header = next(reader, None) or []
    # Column indices by header names
    def idx(name: str) -> int:
        for i, h in enumerate(header):
            if (h or "").strip().lower() == name.lower():
                return i
        # Fallback: by Russian display text (partial)
        for i, h in enumerate(header):
            if name.lower() in (h or "").lower():
                return i
        return -1

    idx_id = 0
    idx_type = 1
    idx_dt = 2
    idx_price = 4
    idx_qty = 5
    idx_pnl = 7
    # Optional indices for richer data if present in CSV
    idx_signal = idx("Сигнал") if "Сигнал" in header else idx("signal")
    idx_peak = idx("Пик") if "Пик" in header else idx("peak")
    idx_drawdown = idx("Просад") if "Просад" in "|".join(header) else idx("drawdown")
    idx_plpct = idx("Чистая прибыль") if any("Чистая" in (h or "") and "%" in (h or "") for h in header) else idx("pnl%")
    # Fees / commission (optional)
    idx_fee = idx("Комисс") if any("комисс" in (h or "").lower() for h in header) else idx("fee")
    idx_duration = idx("Длитель") if any("Длитель" in (h or "") for h in header) else idx("duration")

    entries: Dict[str, Dict[str, Any]] = {}
    exits: Dict[str, Dict[str, Any]] = {}

    for row in reader:
        if not row or len(row) <= idx_dt:
            continue
        trade_id = str(row[idx_id]).strip()
        typ = (row[idx_type] or "").strip()
        dt_raw = (row[idx_dt] or "").strip()
        price = float((row[idx_price] or "0").replace(" ", "").replace(",", "."))
        qty = float((row[idx_qty] or "0").replace(" ", "").replace(",", "."))
        # Parse dt in local format "YYYY-MM-DD HH:MM"
        try:
            dt_iso = datetime.strptime(dt_raw, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).isoformat()
        except Exception:
            # fallback: return raw
            dt_iso = dt_raw
        if "Вход" in typ:
            entry_extra: Dict[str, Any] = {"time": dt_iso, "price": price, "qty": qty}
            if 0 <= idx_signal < len(row):
                entry_extra["signal"] = (row[idx_signal] or "").strip()
            if 0 <= idx_peak < len(row):
                try:
                    entry_extra["peak"] = float(str(row[idx_peak]).replace(" ", "").replace(",", "."))
                except Exception:
                    pass
            if 0 <= idx_drawdown < len(row):
                try:
                    entry_extra["drawdown"] = float(str(row[idx_drawdown]).replace(" ", "").replace(",", "."))
                except Exception:
                    pass
            if 0 <= idx_plpct < len(row):
                try:
                    entry_extra["pnl_pct"] = float(str(row[idx_plpct]).replace(" ", "").replace(",", "."))
                except Exception:
                    pass
            if 0 <= idx_duration < len(row):
                entry_extra["duration"] = (row[idx_duration] or "").strip()
            entries[trade_id] = entry_extra
        elif "Выход" in typ:
            pnl = row[idx_pnl]
            try:
                pnl_val = float(str(pnl).replace(" ", "").replace(",", "."))
            except Exception:
                pnl_val = 0.0
            extra: Dict[str, Any] = {"time": dt_iso, "pnl": pnl_val}
            if 0 <= idx_fee < len(row):
                try:
                    extra["fee"] = float(str(row[idx_fee]).replace(" ", "").replace(",", "."))
                except Exception:
                    pass
            exits[trade_id] = extra

    # Merge into TradeOut-like dicts
    out: List[Dict[str, Any]] = []
    for k in sorted(set(entries.keys()) | set(exits.keys()), key=lambda x: int(x)):
        e = entries.get(k) or {}
        x = exits.get(k) or {}
        out.append(
            {
                "id": int(k),
                "backtest_id": 1,
                "entry_time": e.get("time"),
                "exit_time": x.get("time"),
                "price": e.get("price", 0.0),
                "qty": e.get("qty", 0.0),
                "side": "buy",
                "pnl": x.get("pnl", 0.0),
                "fee": x.get("fee"),
                "created_at": None,
                # Optional extras if provided in CSV
                "signal": e.get("signal"),
                "peak": e.get("peak"),
                "drawdown": e.get("drawdown"),
                "pnl_pct": e.get("pnl_pct"),
                "duration_raw": e.get("duration"),
            }
        )

    _CACHE[key] = out
    # Also cache derived times for overview
    times = [t.get("entry_time") for t in out if t.get("entry_time")]
    if times:
        _CACHE[("range", dirpath)] = (times[0], times[-1])
    return out


# -----------------------------
# Generic CSV table parsers for 1.csv..4.csv
# -----------------------------

def _to_float(x: Any) -> float | None:
    try:
        if x is None:
            return None
        s = str(x).strip().replace(" ", "").replace(",", ".")
        if s == "" or s.lower() in {"nan", "none", "null"}:
            return None
        return float(s)
    except Exception:
        return None


def _parse_time_cell(v: Any) -> int | None:
    """Normalize a time cell to epoch seconds.

    Accepts:
    - integer seconds
    - integer milliseconds
    - ISO8601 string (e.g., 2024-10-21T12:34:00+00:00 or 2024-10-21 12:34)
    - date-only string -> assume 00:00 UTC
    """
    if v is None:
        return None
    # numeric path
    try:
        iv = int(float(str(v).strip()))
        # Heuristic: ms if > 10^12
        if iv > 10**12:
            return iv // 1000
        # seconds if > 10^9 (reasonable unix ts)
        if iv > 10**9 / 10:  # be tolerant
            return iv
    except Exception:
        pass
    s = str(v).strip().replace("Z", "+00:00")
    # try common formats
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            # if naive (no tz), assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except Exception:
            continue
    # last resort: datetime.fromisoformat
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        return None


def _read_csv_rows(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []
    text = _read_text(path)
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return []
    # Attempt DictReader for comma- or semicolon-delimited
    # Prefer comma; if only one column then retry with semicolon
    reader = csv.DictReader(lines, delimiter=",")
    rows = [dict(r) for r in reader]
    if rows and len(rows[0].keys()) <= 1:
        reader = csv.DictReader(lines, delimiter=";")
        rows = [dict(r) for r in reader]
    # Trim BOM/whitespace in keys
    out = []
    for r in rows:
        o: dict[str, Any] = {}
        for k, v in r.items():
            kk = (k or "").strip().strip("\ufeff")
            o[kk] = v
        out.append(o)
    return out


def _norm_key(s: str) -> str:
    return s.strip().lower().replace(" ", "").replace("-", "").replace("_", "")


def _parse_ohlcv_csv(dirpath: str) -> list[dict[str, Any]]:
    key = ("ohlcv", dirpath)
    if key in _CACHE:
        return _CACHE[key]
    rows = _read_csv_rows(os.path.join(dirpath, "1.csv"))
    if not rows:
        _CACHE[key] = []
        return []
    # map columns
    colmap = {
        "time": None,
        "open": None,
        "high": None,
        "low": None,
        "close": None,
        "volume": None,
    }
    aliases = {
        "time": ["time", "timestamp", "datetime", "date", "время", "дата"],
        "open": ["open", "o", "открытие"],
        "high": ["high", "h", "макс", "высок"],
        "low": ["low", "l", "мин"],
        "close": ["close", "c", "закрытие"],
        "volume": ["volume", "vol", "объем", "обьём", "обьем", "v"],
    }
    headers = list(rows[0].keys())
    for k in colmap.keys():
        for h in headers:
            if _norm_key(h) in ( _norm_key(a) for a in aliases[k] ):
                colmap[k] = h
                break
    out: list[dict[str, Any]] = []
    for r in rows:
        t = _parse_time_cell(r.get(colmap["time"])) if colmap["time"] else None
        if t is None:
            continue
        out.append(
            {
                "time": t,
                "open": _to_float(r.get(colmap["open"])) or 0.0,
                "high": _to_float(r.get(colmap["high"])) or 0.0,
                "low": _to_float(r.get(colmap["low"])) or 0.0,
                "close": _to_float(r.get(colmap["close"])) or 0.0,
                "volume": _to_float(r.get(colmap["volume"])) if colmap["volume"] else None,
            }
        )
    out.sort(key=lambda x: x["time"])  # asc
    _CACHE[key] = out
    return out


def _parse_generic_series(dirpath: str, filename: str) -> dict[str, Any]:
    key = ("series", dirpath, filename)
    if key in _CACHE:
        return _CACHE[key]
    rows = _read_csv_rows(os.path.join(dirpath, filename))
    if not rows:
        _CACHE[key] = {"columns": [], "rows": []}
        return _CACHE[key]
    # detect time column
    headers = list(rows[0].keys())
    time_col = None
    for cand in ("time", "timestamp", "datetime", "date", "время", "дата"):
        for h in headers:
            if _norm_key(h) == _norm_key(cand):
                time_col = h
                break
        if time_col:
            break
    # numeric columns: everything except time
    value_cols = [h for h in headers if h != time_col]
    out_rows: list[dict[str, Any]] = []
    for r in rows:
        t = _parse_time_cell(r.get(time_col)) if time_col else None
        if t is None:
            # If no time column, skip row
            continue
        o: dict[str, Any] = {"time": t}
        for c in value_cols:
            o[c] = _to_float(r.get(c))
        out_rows.append(o)
    out_rows.sort(key=lambda x: x["time"])  # asc
    res = {"columns": ["time"] + value_cols, "rows": out_rows}
    _CACHE[key] = res
    return res


def _compute_metrics(
    trades: List[Dict[str, Any]],
    initial_capital: float,
    timeframe_min: Optional[int] = None,
) -> Dict[str, Any]:
    # Basic aggregates
    total = len(trades)
    wins = [t for t in trades if (t.get("pnl") or 0) > 0]
    losses = [t for t in trades if (t.get("pnl") or 0) < 0]
    gross_profit = sum(max(0.0, float(t.get("pnl") or 0)) for t in trades)
    gross_loss = sum(min(0.0, float(t.get("pnl") or 0)) for t in trades)
    net = gross_profit + gross_loss
    profit_factor = (gross_profit / abs(gross_loss)) if gross_loss != 0 else (0.0 if gross_profit == 0 else float("inf"))

    # Equity curve and drawdown
    eq = float(initial_capital or 0.0)
    peak = eq
    equity_series: List[Dict[str, Any]] = []
    pnl_bars: List[Dict[str, Any]] = []
    max_dd_abs = 0.0
    max_dd_pct = 0.0
    returns: List[float] = []
    max_win_pct = 0.0
    max_loss_pct = 0.0  # store magnitude as positive
    open_trades = 0
    bars_all: List[int] = []
    bars_win: List[int] = []
    bars_loss: List[int] = []

    for t in sorted(trades, key=lambda x: x.get("entry_time") or ""):
        pnl = float(t.get("pnl") or 0.0)
        prev_eq = eq if eq != 0 else 1.0
        eq += pnl
        peak = max(peak, eq)
        ts = t.get("entry_time")
        equity_series.append({"time": ts, "equity": eq})
        pnl_bars.append({"time": ts, "pnl": pnl})
        dd_abs = peak - eq
        dd_pct = (dd_abs / peak) if peak > 0 else 0.0
        max_dd_abs = max(max_dd_abs, dd_abs)
        max_dd_pct = max(max_dd_pct, dd_pct)
        # per-step return relative to previous equity
        r = pnl / prev_eq
        returns.append(r)
        if pnl > 0:
            max_win_pct = max(max_win_pct, abs(r) * 100.0)
        elif pnl < 0:
            max_loss_pct = max(max_loss_pct, abs(r) * 100.0)

        # durations and bars held
        try:
            et = t.get("entry_time")
            xt = t.get("exit_time")
            if xt:
                dt1 = datetime.fromisoformat(str(et))
                dt2 = datetime.fromisoformat(str(xt))
                duration_min = max(0, int(round((dt2 - dt1).total_seconds() / 60)))
                if timeframe_min and timeframe_min > 0:
                    bars = int(round(duration_min / timeframe_min))
                    bars_all.append(bars)
                    if pnl > 0:
                        bars_win.append(bars)
                    elif pnl < 0:
                        bars_loss.append(bars)
            else:
                open_trades += 1
        except Exception:
            pass

    import math

    def _mean(xs: List[float]) -> float:
        return (sum(xs) / len(xs)) if xs else 0.0

    def _std(xs: List[float]) -> float:
        if len(xs) <= 1:
            return 0.0
        m = _mean(xs)
        var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
        return math.sqrt(var)

    mu = _mean(returns)
    sigma = _std(returns)
    downside = [r for r in returns if r < 0]
    sigma_down = _std(downside) if len(downside) > 1 else 0.0
    # Scale by sqrt(n) to stabilize with varying number of periods
    n = max(1, len(returns))
    sharpe = (mu / sigma * math.sqrt(n)) if sigma > 0 else 0.0
    sortino = (mu / sigma_down * math.sqrt(n)) if sigma_down > 0 else 0.0

    # Extremes
    max_win = max((float(t.get("pnl") or 0.0) for t in trades), default=0.0)
    max_loss = min((float(t.get("pnl") or 0.0) for t in trades), default=0.0)
    total_fees = sum(float(t.get("fee") or 0.0) for t in trades)
    max_contracts = int(max((abs(float(t.get("qty") or 0.0)) for t in trades), default=0.0))

    # By side (we only have 'buy' in CSV; keep structure for UI parity)
    avg_pl_pct = _mean([r * 100.0 for r in returns])
    avg_win_pct = _mean([r * 100.0 for r in returns if r > 0])
    avg_loss_pct = _mean([abs(r) * 100.0 for r in returns if r < 0])

    all_stats = {
        "total_trades": total,
        "open_trades": open_trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": (len(wins) / total * 100.0) if total else 0.0,
        "avg_pl": (net / total) if total else 0.0,
        "avg_pl_pct": avg_pl_pct,
        "avg_win": (sum(t.get("pnl") or 0 for t in wins) / len(wins)) if wins else 0.0,
        "avg_win_pct": avg_win_pct,
        "avg_loss": (sum(t.get("pnl") or 0 for t in losses) / len(losses)) if losses else 0.0,
        "avg_loss_pct": avg_loss_pct,
        "max_win": max_win,
        "max_loss": max_loss,
        "max_win_pct": max_win_pct,
        "max_loss_pct": max_loss_pct,
        "profit_factor": profit_factor,
        "avg_bars": _mean(bars_all) if bars_all else 0.0,
        "avg_bars_win": _mean(bars_win) if bars_win else 0.0,
        "avg_bars_loss": _mean(bars_loss) if bars_loss else 0.0,
    }
    long_stats = all_stats.copy()
    short_stats = {k: 0 for k in all_stats.keys()}

    overview = {
        "net_pnl": net,
        "net_pct": (net / initial_capital) if initial_capital else 0.0,
        "max_drawdown_abs": max_dd_abs,
        "max_drawdown_pct": max_dd_pct,
        "total_trades": total,
        "win_rate": all_stats["win_rate"],
        "profit_factor": profit_factor,
    }

    risk = {"sharpe": sharpe, "sortino": sortino, "profit_factor": profit_factor}

    # Dynamics summary for table
    def pct_of_init(x: float) -> float:
        return (x / initial_capital * 100.0) if initial_capital else 0.0

    net_profit_abs = gross_profit + abs(gross_loss) * 0.0  # keep parity with user: net = gross_profit - gross_loss_abs
    net_profit_abs = gross_profit - abs(gross_loss)
    dynamics_row = {
        "unrealized_abs": 0.0,  # no live marking in mock
        "unrealized_pct": 0.0,
        "net_abs": net_profit_abs,
        "net_pct": pct_of_init(net_profit_abs),
        "gross_profit_abs": gross_profit,
        "gross_profit_pct": pct_of_init(gross_profit),
        "gross_loss_abs": abs(gross_loss),
        "gross_loss_pct": pct_of_init(abs(gross_loss)),
        "fees_abs": total_fees,
        "max_runup_abs": max(0.0, max(eq_point["equity"] for eq_point in equity_series) - float(initial_capital or 0.0)) if equity_series else 0.0,
        "max_runup_pct": pct_of_init(max(0.0, max(eq_point["equity"] for eq_point in equity_series) - float(initial_capital or 0.0)) if equity_series else 0.0),
        "max_drawdown_abs": max_dd_abs,
        "max_drawdown_pct": max_dd_pct * 100.0,  # convert to % for dynamics table
        "max_contracts": max_contracts,
    }

    dynamics = {"all": dict(dynamics_row), "long": dict(dynamics_row), "short": {
        "unrealized_abs": 0.0,
        "unrealized_pct": 0.0,
        "net_abs": 0.0,
        "net_pct": 0.0,
        "gross_profit_abs": 0.0,
        "gross_profit_pct": 0.0,
        "gross_loss_abs": 0.0,
        "gross_loss_pct": 0.0,
        "fees_abs": 0.0,
        "max_runup_abs": 0.0,
        "max_runup_pct": 0.0,
        "max_drawdown_abs": 0.0,
        "max_drawdown_pct": 0.0,
        "max_contracts": 0,
    }}

    return {
        "overview": overview,
        "risk": risk,
        "by_side": {"all": all_stats, "long": long_stats, "short": short_stats},
        "equity": equity_series,
        "pnl_bars": pnl_bars,
        "dynamics": dynamics,
    }


def _num_from_str(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        s = str(v).strip().replace(" ", "").replace(",", ".")
        if s == "" or s.lower() in {"nan", "none", "null", "-", "—", "n/a"}:
            return None
        return float(s)
    except Exception:
        return None


def _override_metrics_with_params(params: Dict[str, str], metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Override computed metrics with exact values from 5.csv when present.

    Accepts flexible RU/EN keys and fills risk.sharpe/sortino and by_side profit_factor.
    """
    if not params:
        return metrics
    risk = dict(metrics.get("risk") or {})
    by_side = dict(metrics.get("by_side") or {})
    all_stats = dict(by_side.get("all") or {})
    long_stats = dict(by_side.get("long") or {})
    short_stats = dict(by_side.get("short") or {})

    # Key candidates (RU and EN variants)
    key_map = {
        "sharpe": ["Коэффициент Шарпа", "Sharpe", "Sharpe Ratio", "SharpeRatio"],
        "sortino": ["Коэффициент Сортино", "Sortino", "Sortino Ratio", "SortinoRatio"],
        "pf_all": ["Фактор прибыли", "Profit Factor", "ProfitFactor"],
        "pf_long": ["Фактор прибыли (длинная)", "Profit Factor Long", "PF Long"],
        "pf_short": ["Фактор прибыли (короткая)", "Profit Factor Short", "PF Short"],
    }

    def find_key(cands: list[str]) -> Optional[str]:
        if not params:
            return None
        # exact case-insensitive or contains
        for k in params.keys():
            for c in cands:
                if str(k).strip().lower() == str(c).strip().lower():
                    return k
        for k in params.keys():
            for c in cands:
                if str(c).strip().lower() in str(k).strip().lower():
                    return k
        return None

    k_sharpe = find_key(key_map["sharpe"])
    k_sortino = find_key(key_map["sortino"])
    k_pf_all = find_key(key_map["pf_all"])
    k_pf_long = find_key(key_map["pf_long"])
    k_pf_short = find_key(key_map["pf_short"])

    if k_sharpe is not None:
        v = _num_from_str(params.get(k_sharpe))
        risk["sharpe"] = v
    if k_sortino is not None:
        v = _num_from_str(params.get(k_sortino))
        risk["sortino"] = v
    if k_pf_all is not None:
        v = _num_from_str(params.get(k_pf_all))
        all_stats["profit_factor"] = v if v is not None else None
    if k_pf_long is not None:
        v = _num_from_str(params.get(k_pf_long))
        long_stats["profit_factor"] = v if v is not None else None
    if k_pf_short is not None:
        v = _num_from_str(params.get(k_pf_short))
        short_stats["profit_factor"] = v if v is not None else None

    out = dict(metrics)
    out["risk"] = risk
    out["by_side"] = {"all": all_stats, "long": long_stats, "short": short_stats}
    return out


def _build_mock_backtest(dirpath: str) -> MockBacktest:
    key = ("bt", dirpath)
    if key in _CACHE:
        return _CACHE[key]
    params = _parse_params_csv(dirpath)
    trades = _parse_trades_csv(dirpath)
    # Symbol & timeframe
    symbol = params.get("Инструмент") or params.get("Instrument") or "BYBIT:BTCUSDT.P"
    tf_raw = params.get("Временные интервалы") or params.get("Timeframe") or "15"
    # Extract number
    import re

    m = re.search(r"(\d+)", tf_raw)
    timeframe = m.group(1) if m else "15"
    # Capital & leverage
    init_cap = 0.0
    for k in ("Total Deposit for Bot ($)", "Deposit for Bot (for the entire grid) ($)"):
        if params.get(k):
            try:
                init_cap = float(str(params[k]).replace(",", "."))
                break
            except Exception:
                pass
    leverage = None
    if params.get("Leverage (1x-20x)"):
        try:
            leverage = float(str(params["Leverage (1x-20x)"]).replace("x", "").replace(",", "."))
        except Exception:
            leverage = None
    # Date range from trades
    start_iso, end_iso = None, None
    if trades:
        start_iso = trades[0]["entry_time"]
        end_iso = trades[-1]["exit_time"] or trades[-1]["entry_time"]
    else:
        # Fallback to now
        now = datetime.now(timezone.utc).isoformat()
        start_iso = now
        end_iso = now
    # Compute base metrics then override with exact CSV params if available
    # timeframe minutes for metrics
    try:
        tf_min = int(str(timeframe).strip())
        tf_min = max(1, tf_min)
    except Exception:
        tf_min = None

    base_metrics = _compute_metrics(trades, init_cap or 0.0, tf_min)
    # Enrich dynamics with Buy&Hold from 1.csv
    try:
        ohlcv = _parse_ohlcv_csv(dirpath)
        if ohlcv:
            first = next((c for c in ohlcv if c.get("close") is not None), None)
            last = next((c for c in reversed(ohlcv) if c.get("close") is not None), None)
            if first and last:
                pct = ((float(last["close"]) - float(first["close"])) / float(first["close"])) * 100.0
                absv = (init_cap or 0.0) * (pct / 100.0)
                for key in ("all", "long"):
                    base_metrics.setdefault("dynamics", {}).setdefault(key, {})["buyhold_abs"] = absv
                    base_metrics["dynamics"][key]["buyhold_pct"] = pct
                base_metrics.setdefault("dynamics", {}).setdefault("short", {})["buyhold_abs"] = 0.0
                base_metrics["dynamics"]["short"]["buyhold_pct"] = 0.0
    except Exception:
        pass
    base_metrics = _override_metrics_with_params(params, base_metrics)

    bt = MockBacktest(
        id=1,
        strategy_id=1,
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_iso or "",
        end_date=end_iso or "",
        initial_capital=init_cap or 0.0,
        leverage=leverage,
        status="completed",
        results=base_metrics,
    )
    _CACHE[key] = bt
    return bt


def _ensure_dir() -> str:
    dirpath = os.environ.get("MOCK_BT_DIR") or os.environ.get("PERP_DIR") or "d:/PERP"
    if not os.path.isdir(dirpath):
        raise HTTPException(status_code=500, detail=f"MOCK_BT_DIR not found: {dirpath}")
    return dirpath


# -----------------------------
# Routes
# -----------------------------


@router.get("/", response_model=dict)
def list_backtests(limit: int = 100, offset: int = 0):
    dirpath = _ensure_dir()
    bt = _build_mock_backtest(dirpath)
    # Minimal list response shape expected by frontend: {items, total}
    item = {
        "id": bt.id,
        "strategy_id": bt.strategy_id,
        "symbol": bt.symbol,
        "timeframe": bt.timeframe,
        "start_date": bt.start_date,
        "end_date": bt.end_date,
        "initial_capital": bt.initial_capital,
        "leverage": bt.leverage,
        "status": bt.status,
        "results": bt.results or {},
    }
    return {"items": [item], "total": 1}

# Also serve no-trailing-slash variant to avoid 307 redirects in some clients
@router.get("", response_model=dict, include_in_schema=False)
def list_backtests_noslash(limit: int = 100, offset: int = 0):
    return list_backtests(limit=limit, offset=offset)


@router.get("/{backtest_id}", response_model=dict)
def get_backtest(backtest_id: int):
    _ = backtest_id  # single mock
    dirpath = _ensure_dir()
    bt = _build_mock_backtest(dirpath)
    return {
        "id": bt.id,
        "strategy_id": bt.strategy_id,
        "symbol": bt.symbol,
        "timeframe": bt.timeframe,
        "start_date": bt.start_date,
        "end_date": bt.end_date,
        "initial_capital": bt.initial_capital,
        "leverage": bt.leverage,
        "status": bt.status,
        "results": bt.results or {},
    }


@router.get("/{backtest_id}/trades", response_model=dict)
def list_trades(backtest_id: int, limit: int = 1000, offset: int = 0, side: str | None = Query(None)):
    _ = backtest_id
    dirpath = _ensure_dir()
    bt = _build_mock_backtest(dirpath)
    trades = _parse_trades_csv(dirpath)
    # Optional side filter (CSV contains only 'buy' in many cases, but keep for parity)
    if side in ("buy", "sell"):
        trades = [t for t in trades if str(t.get("side") or "").lower() == side]
    # Decorate with derived metrics: pnl_pct (if missing) and duration_min
    params = _parse_params_csv(dirpath)
    init_cap = 0.0
    for k in ("Total Deposit for Bot ($)", "Deposit for Bot (for the entire grid) ($)"):
        if params.get(k):
            try:
                init_cap = float(str(params[k]).replace(",", "."))
                break
            except Exception:
                pass

    # Compute equity-relative percent and duration if exit_time present
    eq = float(init_cap)
    sorted_idx = sorted(range(len(trades)), key=lambda i: trades[i].get("entry_time") or "")
    # timeframe minutes for bars_held
    try:
        tf_min = int(str(bt.timeframe).strip())
        tf_min = max(1, tf_min)
    except Exception:
        tf_min = 1
    for i in sorted_idx:
        t = trades[i]
        prev_eq = eq if eq != 0 else 1.0
        pnl = float(t.get("pnl") or 0.0)
        if t.get("pnl_pct") is None:
            try:
                t["pnl_pct"] = (pnl / prev_eq) * 100.0
            except Exception:
                t["pnl_pct"] = 0.0
        # duration in minutes
        try:
            if t.get("entry_time") and t.get("exit_time"):
                dt1 = datetime.fromisoformat(str(t["entry_time"]))
                dt2 = datetime.fromisoformat(str(t["exit_time"]))
                t["duration_min"] = max(0, int(round((dt2 - dt1).total_seconds() / 60)))
        except Exception:
            pass
        # estimate bars_held from duration and timeframe
        try:
            if t.get("duration_min") is not None:
                t["bars_held"] = int(round(float(t["duration_min"]) / float(tf_min)))
        except Exception:
            pass
        eq = prev_eq + pnl
    # Apply simple pagination and include total
    total = len(trades)
    items = trades[offset : offset + limit]
    return {"items": items, "total": total}


@router.get("/{backtest_id}/overlays", response_model=dict)
def get_overlays(backtest_id: int):
    """Return auxiliary per-bar series sourced from CSV files 1.csv..4.csv.

    Shape:
      {
        "ohlcv": [ {time, open, high, low, close, volume?}, ...],   # from 1.csv
        "indicators": { columns: [...], rows: [...] },                # from 2.csv (generic)
        "benchmarks": { columns: [...], rows: [...] },                # from 3.csv (generic)
        "growth": { columns: [...], rows: [...] }                     # from 4.csv (generic)
      }
    """
    _ = backtest_id
    dirpath = _ensure_dir()
    ohlcv = _parse_ohlcv_csv(dirpath)
    indicators = _parse_generic_series(dirpath, "2.csv")
    benchmarks = _parse_generic_series(dirpath, "3.csv")
    growth = _parse_generic_series(dirpath, "4.csv")

    # If growth has only an equity-like column, also provide derived drawdown within rows
    try:
        cols = [c for c in (growth.get("columns") or []) if c != "time"]
        if cols:
            # choose first non-time column as equity/growth
            c0 = cols[0]
            eq = 0.0
            peak = 0.0
            out_rows = []
            for r in (growth.get("rows") or []):
                val = _to_float(r.get(c0)) or 0.0
                eq = val
                peak = max(peak, eq)
                dd = ((eq - peak) / peak) if peak > 0 else 0.0
                rr = dict(r)
                rr["drawdown"] = dd
                out_rows.append(rr)
            growth = {"columns": growth.get("columns", []) + ["drawdown"], "rows": out_rows}
    except Exception:
        pass

    return {
        "ohlcv": ohlcv,
        "indicators": indicators,
        "benchmarks": benchmarks,
        "growth": growth,
    }


@router.get("/{backtest_id}/metrics", response_model=dict)
def get_metrics(backtest_id: int):
    _ = backtest_id
    dirpath = _ensure_dir()
    bt = _build_mock_backtest(dirpath)
    return bt.results or {}


@router.get("/{backtest_id}/equity", response_model=dict)
def get_equity(backtest_id: int):
    _ = backtest_id
    dirpath = _ensure_dir()
    trades = _parse_trades_csv(dirpath)
    params = _parse_params_csv(dirpath)
    init_cap = 0.0
    for k in ("Total Deposit for Bot ($)", "Deposit for Bot (for the entire grid) ($)"):
        if params.get(k):
            try:
                init_cap = float(str(params[k]).replace(",", "."))
                break
            except Exception:
                pass
    # timeframe minutes for equity calc (for bars if used later)
    tf_min = None
    try:
        tf_raw = params.get("Временные интервалы") or params.get("Timeframe") or "15"
        import re
        m = re.search(r"(\d+)", str(tf_raw))
        if m:
            tf_min = max(1, int(m.group(1)))
    except Exception:
        tf_min = None
    m = _compute_metrics(trades, init_cap, tf_min)
    return {"equity": m.get("equity", []), "pnl_bars": m.get("pnl_bars", [])}
