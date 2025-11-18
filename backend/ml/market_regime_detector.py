"""
Market Regime Detector using technical analysis and volume profiling

Quick Win #3: Tournament + ML Integration
Detects market conditions: Trending, Ranging, Volatile
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np
import pandas as pd
from scipy import stats
from scipy.signal import find_peaks


logger = logging.getLogger(__name__)


class MarketRegime(str, Enum):
    """Market regime types"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    UNKNOWN = "unknown"


@dataclass
class RegimeDetectionResult:
    """Result of market regime detection"""
    regime: MarketRegime
    confidence: float  # 0.0 - 1.0
    trend_strength: float  # -1.0 (strong down) to +1.0 (strong up)
    volatility: float
    volume_profile: Dict[str, float]
    wyckoff_phase: Optional[str] = None
    adx_value: Optional[float] = None
    
    metadata: Optional[Dict] = None


class TechnicalIndicators:
    """
    Custom technical indicators (no dependency on ta-lib or pandas-ta)
    Python 3.14 compatible
    """
    
    @staticmethod
    def sma(series: pd.Series, period: int) -> pd.Series:
        """Simple Moving Average"""
        return series.rolling(window=period).mean()
    
    @staticmethod
    def ema(series: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average"""
        return series.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """Relative Strength Index"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Average True Range"""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr
    
    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Average Directional Index (ADX)
        Returns: (adx, +di, -di)
        """
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        # Directional Movement
        up_move = high - high.shift()
        down_move = low.shift() - low
        
        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0)
        
        # Directional Indicators
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        # ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return adx, plus_di, minus_di
    
    @staticmethod
    def bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Bollinger Bands"""
        middle = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        return upper, middle, lower


class MarketRegimeDetector:
    """
    Detect market regimes using multiple methods:
    
    1. Trend Detection (ADX, Moving Averages)
    2. Volatility Analysis (ATR, Bollinger Bands)
    3. Volume Profile Analysis
    4. Wyckoff Method (Accumulation/Distribution)
    
    Example:
        detector = MarketRegimeDetector()
        result = detector.detect_regime(df)
        print(f"Regime: {result.regime}, Confidence: {result.confidence:.2f}")
    """
    
    def __init__(
        self,
        adx_period: int = 14,
        adx_threshold: float = 25.0,
        volatility_window: int = 20,
        volume_window: int = 20
    ):
        """
        Initialize detector
        
        Args:
            adx_period: Period for ADX calculation
            adx_threshold: ADX threshold for trending market (default: 25)
            volatility_window: Window for volatility calculation
            volume_window: Window for volume analysis
        """
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.volatility_window = volatility_window
        self.volume_window = volume_window
        self.indicators = TechnicalIndicators()
    
    def detect_regime(
        self,
        df: pd.DataFrame,
        return_details: bool = False
    ) -> RegimeDetectionResult:
        """
        Detect current market regime
        
        Args:
            df: DataFrame with OHLCV data (columns: open, high, low, close, volume)
            return_details: Include detailed metrics in result
        
        Returns:
            RegimeDetectionResult with detected regime and confidence
        """
        if len(df) < 50:
            logger.warning(f"Insufficient data for regime detection: {len(df)} bars")
            return RegimeDetectionResult(
                regime=MarketRegime.UNKNOWN,
                confidence=0.0,
                trend_strength=0.0,
                volatility=0.0,
                volume_profile={}
            )
        
        # 1. Trend Analysis
        trend_result = self._analyze_trend(df)
        
        # 2. Volatility Analysis
        volatility_result = self._analyze_volatility(df)
        
        # 3. Volume Profile
        volume_result = self._analyze_volume_profile(df)
        
        # 4. Wyckoff Analysis (optional, computationally expensive)
        wyckoff_phase = self._detect_wyckoff_phase(df)
        
        # 5. Combine results to determine regime
        regime, confidence = self._determine_regime(
            trend_result,
            volatility_result,
            volume_result,
            wyckoff_phase
        )
        
        # Create result
        result = RegimeDetectionResult(
            regime=regime,
            confidence=confidence,
            trend_strength=trend_result["trend_strength"],
            volatility=volatility_result["volatility"],
            volume_profile=volume_result,
            wyckoff_phase=wyckoff_phase,
            adx_value=trend_result.get("adx"),
            metadata={
                "trend_analysis": trend_result if return_details else None,
                "volatility_analysis": volatility_result if return_details else None
            }
        )
        
        logger.info(f"Detected regime: {regime} (confidence: {confidence:.2f})")
        
        return result
    
    def _analyze_trend(self, df: pd.DataFrame) -> Dict:
        """Analyze trend strength and direction"""
        close = df['close']
        high = df['high']
        low = df['low']
        
        # Calculate ADX
        adx, plus_di, minus_di = self.indicators.adx(high, low, close, self.adx_period)
        current_adx = adx.iloc[-1] if not adx.isna().iloc[-1] else 0
        
        # Calculate moving averages
        sma_20 = self.indicators.sma(close, 20)
        sma_50 = self.indicators.sma(close, 50)
        ema_12 = self.indicators.ema(close, 12)
        ema_26 = self.indicators.ema(close, 26)
        
        # Trend strength (-1 to +1)
        if current_adx > self.adx_threshold:
            # Strong trend
            if plus_di.iloc[-1] > minus_di.iloc[-1]:
                trend_strength = min(current_adx / 50, 1.0)  # Normalize to 0-1
            else:
                trend_strength = -min(current_adx / 50, 1.0)
        else:
            # Weak trend / ranging
            trend_strength = 0.0
        
        # MA alignment
        ma_alignment = 0
        if sma_20.iloc[-1] > sma_50.iloc[-1]:
            ma_alignment += 1
        if ema_12.iloc[-1] > ema_26.iloc[-1]:
            ma_alignment += 1
        if close.iloc[-1] > sma_20.iloc[-1]:
            ma_alignment += 1
        
        # Price position relative to MAs (0-1)
        ma_position = ma_alignment / 3.0
        
        return {
            "adx": current_adx,
            "trend_strength": trend_strength,
            "ma_position": ma_position,
            "plus_di": plus_di.iloc[-1],
            "minus_di": minus_di.iloc[-1],
            "is_trending": current_adx > self.adx_threshold,
            "trend_direction": "up" if trend_strength > 0 else "down" if trend_strength < 0 else "neutral"
        }
    
    def _analyze_volatility(self, df: pd.DataFrame) -> Dict:
        """Analyze market volatility"""
        close = df['close']
        high = df['high']
        low = df['low']
        
        # ATR
        atr = self.indicators.atr(high, low, close, self.volatility_window)
        current_atr = atr.iloc[-1]
        atr_pct = (current_atr / close.iloc[-1]) * 100  # ATR as % of price
        
        # Historical volatility (standard deviation of returns)
        returns = close.pct_change()
        hist_vol = returns.rolling(window=self.volatility_window).std().iloc[-1]
        annualized_vol = hist_vol * np.sqrt(252) * 100  # Annualized %
        
        # Bollinger Band width
        bb_upper, bb_middle, bb_lower = self.indicators.bollinger_bands(close, self.volatility_window)
        bb_width = ((bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_middle.iloc[-1]) * 100
        
        # Price position in BB
        bb_position = (close.iloc[-1] - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1])
        
        # Volatility regime (low, normal, high)
        # Compare current volatility to historical average
        avg_atr_pct = (atr / close).rolling(window=50).mean().iloc[-1] * 100
        
        if atr_pct > avg_atr_pct * 1.5:
            volatility_regime = "high"
        elif atr_pct < avg_atr_pct * 0.7:
            volatility_regime = "low"
        else:
            volatility_regime = "normal"
        
        return {
            "volatility": annualized_vol,
            "atr_pct": atr_pct,
            "bb_width": bb_width,
            "bb_position": bb_position,
            "volatility_regime": volatility_regime,
            "is_volatile": volatility_regime == "high"
        }
    
    def _analyze_volume_profile(self, df: pd.DataFrame) -> Dict:
        """Analyze volume profile and patterns"""
        volume = df['volume']
        close = df['close']
        
        # Average volume
        avg_volume = volume.rolling(window=self.volume_window).mean().iloc[-1]
        current_volume = volume.iloc[-1]
        
        # Volume ratio
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        # Volume trend (increasing/decreasing)
        volume_sma_short = volume.rolling(window=5).mean().iloc[-1]
        volume_sma_long = volume.rolling(window=20).mean().iloc[-1]
        volume_trend = "increasing" if volume_sma_short > volume_sma_long else "decreasing"
        
        # On-Balance Volume (OBV) trend
        obv = (volume * np.sign(close.diff())).cumsum()
        obv_trend = obv.diff(5).iloc[-1]
        
        # Volume spikes (potential accumulation/distribution)
        volume_spikes = (volume > avg_volume * 2).rolling(window=10).sum().iloc[-1]
        
        return {
            "volume_ratio": volume_ratio,
            "volume_trend": volume_trend,
            "obv_trend": "up" if obv_trend > 0 else "down",
            "volume_spikes": int(volume_spikes),
            "is_high_volume": volume_ratio > 1.5
        }
    
    def _detect_wyckoff_phase(self, df: pd.DataFrame) -> Optional[str]:
        """
        Detect Wyckoff accumulation/distribution phases
        
        Simplified implementation:
        - Accumulation: Price ranging + increasing volume + price near lows
        - Distribution: Price ranging + increasing volume + price near highs
        """
        if len(df) < 50:
            return None
        
        close = df['close']
        volume = df['volume']
        high = df['high']
        low = df['low']
        
        # Recent price range
        recent_high = high.iloc[-20:].max()
        recent_low = low.iloc[-20:].min()
        price_range = recent_high - recent_low
        
        if price_range == 0:
            return None
        
        current_price = close.iloc[-1]
        price_position = (current_price - recent_low) / price_range
        
        # Volume analysis
        avg_volume = volume.iloc[-50:-20].mean()
        recent_volume = volume.iloc[-20:].mean()
        volume_increase = recent_volume > avg_volume * 1.2
        
        # Price volatility (ranging vs trending)
        returns = close.pct_change().iloc[-20:]
        price_stability = 1.0 - min(returns.std() * 100, 1.0)  # Higher = more stable
        
        # Detect phases
        if price_stability > 0.3 and volume_increase:
            if price_position < 0.4:  # Price near lows
                return "accumulation"
            elif price_position > 0.6:  # Price near highs
                return "distribution"
        
        return None
    
    def _determine_regime(
        self,
        trend_result: Dict,
        volatility_result: Dict,
        volume_result: Dict,
        wyckoff_phase: Optional[str]
    ) -> Tuple[MarketRegime, float]:
        """
        Determine final regime based on all analyses
        
        Returns:
            (regime, confidence)
        """
        confidence_factors = []
        
        # Check for Wyckoff phases first (high priority)
        if wyckoff_phase == "accumulation":
            return MarketRegime.ACCUMULATION, 0.75
        elif wyckoff_phase == "distribution":
            return MarketRegime.DISTRIBUTION, 0.75
        
        # Check for high volatility
        if volatility_result["is_volatile"]:
            confidence = 0.7 if volatility_result["volatility"] > 50 else 0.6
            return MarketRegime.VOLATILE, confidence
        
        # Check for trending
        if trend_result["is_trending"]:
            trend_strength = trend_result["trend_strength"]
            
            # Confidence based on ADX strength
            adx = trend_result["adx"]
            confidence = min(adx / 40, 0.9)  # Max 90% confidence
            
            if trend_strength > 0.2:
                return MarketRegime.TRENDING_UP, confidence
            elif trend_strength < -0.2:
                return MarketRegime.TRENDING_DOWN, confidence
        
        # Default to ranging if no strong trend or volatility
        # Confidence based on lack of trend
        ranging_confidence = 1.0 - min(trend_result["adx"] / 40, 0.8)
        return MarketRegime.RANGING, max(ranging_confidence, 0.5)
    
    def get_regime_statistics(self, df: pd.DataFrame, window: int = 100) -> Dict:
        """
        Calculate regime statistics over a window
        
        Returns:
            Distribution of regimes over the window
        """
        if len(df) < window:
            window = len(df)
        
        regime_counts = {regime.value: 0 for regime in MarketRegime}
        
        # Detect regime for each bar in window
        for i in range(len(df) - window, len(df), 10):  # Sample every 10 bars
            if i < 50:
                continue
            
            subset = df.iloc[:i+1]
            result = self.detect_regime(subset)
            regime_counts[result.regime.value] += 1
        
        # Calculate percentages
        total = sum(regime_counts.values())
        regime_percentages = {
            regime: (count / total * 100) if total > 0 else 0
            for regime, count in regime_counts.items()
        }
        
        return regime_percentages


# Example usage
if __name__ == "__main__":
    # Create sample data
    np.random.seed(42)
    n = 200
    
    df = pd.DataFrame({
        'open': 100 + np.cumsum(np.random.randn(n) * 0.5),
        'high': 100 + np.cumsum(np.random.randn(n) * 0.5) + np.random.rand(n),
        'low': 100 + np.cumsum(np.random.randn(n) * 0.5) - np.random.rand(n),
        'close': 100 + np.cumsum(np.random.randn(n) * 0.5),
        'volume': np.random.randint(1000, 10000, n)
    })
    
    # Detect regime
    detector = MarketRegimeDetector()
    result = detector.detect_regime(df, return_details=True)
    
    print(f"\n✅ Market Regime Detection Result:")
    print(f"Regime: {result.regime.value}")
    print(f"Confidence: {result.confidence:.2%}")
    print(f"Trend Strength: {result.trend_strength:+.2f}")
    print(f"Volatility: {result.volatility:.2f}%")
    print(f"Wyckoff Phase: {result.wyckoff_phase or 'None'}")
    print(f"ADX: {result.adx_value:.2f}")
    
    # Get regime statistics
    stats = detector.get_regime_statistics(df)
    print(f"\n📊 Regime Distribution (last 100 bars):")
    for regime, pct in stats.items():
        if pct > 0:
            print(f"  {regime}: {pct:.1f}%")
