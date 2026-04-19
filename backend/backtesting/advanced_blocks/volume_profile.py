"""
🧱 Volume Profile Blocks

Volume profile analysis blocks.
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class VolumeProfileResult:
    """Volume profile result"""

    poc: float  # Point of Control
    value_area_high: float
    value_area_low: float
    profile_type: str  # 'balanced', 'trend', 'double_distribution'
    metadata: dict[str, Any] = field(default_factory=dict)


class VolumeProfileBlock:
    """
    Volume Profile block.

    Анализирует распределение объема по цене.

    Parameters:
        n_bins: Количество ценовых уровней
        value_area_pct: Процент value area

    Returns:
        poc: Point of Control (цена с максимальным объемом)
        value_area_high: Верхняя граница value area
        value_area_low: Нижняя граница value area
    """

    def __init__(
        self,
        n_bins: int = 50,
        value_area_pct: float = 0.70,
    ):
        self.n_bins = n_bins
        self.value_area_pct = value_area_pct

    def calculate(self, data: pd.DataFrame) -> VolumeProfileResult:
        """
        Рассчитать Volume Profile.

        Args:
            data: OHLCV данные

        Returns:
            VolumeProfileResult
        """
        # Create price bins
        price_min = data["low"].min()
        price_max = data["high"].max()

        bins = np.linspace(price_min, price_max, self.n_bins)

        # Calculate volume at each price level
        volume_by_price = np.zeros(self.n_bins - 1)

        for idx in range(len(data)):
            row = data.iloc[idx]
            high = row["high"]
            low = row["low"]
            volume = row["volume"]

            # Find bins that overlap with this bar
            for i in range(len(bins) - 1):
                bin_low = bins[i]
                bin_high = bins[i + 1]

                if high >= bin_low and low <= bin_high:
                    volume_by_price[i] += volume / self.n_bins

        # Point of Control (POC)
        poc_idx = np.argmax(volume_by_price)
        poc = (bins[poc_idx] + bins[poc_idx + 1]) / 2

        # Value Area (70% of volume)
        total_volume = volume_by_price.sum()
        target_volume = total_volume * self.value_area_pct

        # Sort by volume and find value area
        sorted_indices = np.argsort(volume_by_price)[::-1]
        cum_volume = 0
        value_area_bins = []

        for idx in sorted_indices:
            cum_volume += volume_by_price[idx]
            value_area_bins.append(idx)

            if cum_volume >= target_volume:
                break

        value_area_bins = sorted(value_area_bins)
        value_area_low = bins[min(value_area_bins)]
        value_area_high = bins[max(value_area_bins) + 1]

        # Profile type
        profile_type = self._classify_profile(volume_by_price)

        return VolumeProfileResult(
            poc=poc,
            value_area_high=value_area_high,
            value_area_low=value_area_low,
            profile_type=profile_type,
            metadata={
                "total_volume": total_volume,
                "n_levels": self.n_bins,
                "volume_by_price": volume_by_price.tolist(),
            },
        )

    def _classify_profile(self, volume_by_price: np.ndarray) -> str:
        """Classify profile type"""
        # Find peaks
        from scipy.signal import find_peaks

        peaks, _ = find_peaks(volume_by_price, height=volume_by_price.mean())

        if len(peaks) == 0:
            return "flat"
        elif len(peaks) == 1:
            # Check if centered
            center = len(volume_by_price) // 2
            if abs(peaks[0] - center) < len(volume_by_price) * 0.2:
                return "balanced"
            else:
                return "trend"
        elif len(peaks) == 2:
            return "double_distribution"
        else:
            return "complex"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "type": "volume_profile",
            "n_bins": self.n_bins,
            "value_area_pct": self.value_area_pct,
        }


class VolumeImbalanceBlock:
    """
    Volume Imbalance block.

    Анализирует дисбаланс объема.
    """

    def __init__(self, lookback: int = 20):
        self.lookback = lookback

    def calculate(self, data: pd.DataFrame) -> dict[str, Any]:
        """Calculate volume imbalance"""
        # Average volume
        avg_volume = data["volume"].rolling(self.lookback).mean()

        # Current volume vs average
        current_volume = data["volume"].iloc[-1]
        avg = avg_volume.iloc[-1]

        imbalance = (current_volume - avg) / (avg + 1e-10)

        # Classification
        if imbalance > 0.5:
            classification = "high_volume"
        elif imbalance < -0.5:
            classification = "low_volume"
        else:
            classification = "normal"

        return {
            "imbalance": imbalance,
            "current_volume": current_volume,
            "average_volume": avg,
            "classification": classification,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "volume_imbalance",
            "lookback": self.lookback,
        }
