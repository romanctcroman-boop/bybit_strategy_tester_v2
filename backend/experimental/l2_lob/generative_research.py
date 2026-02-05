"""
Generative LOB — research skeleton.

Цель: CGAN (Conditional GAN) для синтеза order book.
- Обучающие данные: L2 снимки из collect_snapshots
- Вход: timestamp, mid_price, volatility и др. признаки
- Выход: синтетический стакан (bids, asks)

Литература:
- "Generating Realistic Order Book Data" (arXiv)
- Conditional GAN for time series

Статус: Research. Требует:
- PyTorch/TensorFlow
- Достаточный объём L2 данных
- Эксперименты с архитектурой
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def load_lob_dataset(path: Path) -> list[dict[str, Any]]:
    """
    Load L2 snapshots from NDJSON for training.

    Returns list of dicts with keys: ts, symbol, bids, asks, mid, spread_bps.
    """
    data = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                import json

                d = json.loads(line)
                bids = d.get("bids", [])
                asks = d.get("asks", [])
                if not bids or not asks:
                    continue
                best_bid = float(bids[0][0])
                best_ask = float(asks[0][0])
                mid = (best_bid + best_ask) / 2
                spread_bps = ((best_ask - best_bid) / mid) * 10_000 if mid else 0
                data.append(
                    {
                        "ts": d.get("ts"),
                        "symbol": d.get("symbol", ""),
                        "bids": bids,
                        "asks": asks,
                        "mid": mid,
                        "spread_bps": spread_bps,
                    }
                )
            except (json.JSONDecodeError, (IndexError, TypeError, ValueError)):
                continue
    return data


def generate_synthetic_lob(
    condition: dict[str, Any],
    model_path: Path | None = None,
) -> dict[str, Any] | None:
    """
    Generate synthetic order book given conditioning.

    Uses LOB_CGAN if model_path provided and PyTorch available.

    Args:
        condition: Dict with mid_price, spread_bps (optional, default 10)
        model_path: Path to trained CGAN weights (.pt)

    Returns:
        Dict with bids, asks or None
    """
    mid = condition.get("mid_price") or condition.get("mid")
    if mid is None:
        return None
    spread_bps = condition.get("spread_bps", 10.0)

    if model_path and model_path.exists():
        try:
            from backend.experimental.l2_lob.generative_cgan import _HAS_TORCH, LOB_CGAN

            if _HAS_TORCH:
                model = LOB_CGAN.load(model_path)
                result = model.generate(mid_price=float(mid), spread_bps=float(spread_bps), n_samples=1)
                bids, asks = result[0]
                return {"bids": [[p, s] for p, s in bids], "asks": [[p, s] for p, s in asks]}
        except Exception as e:
            logger.warning("CGAN generation failed: %s", e)
    return None
