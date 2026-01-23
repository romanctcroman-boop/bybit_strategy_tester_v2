/**
 * Chart Data Handling Tests
 * Tests for chart data processing and transformations
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

/**
 * Transform API kline data to chart format
 */
function transformKlineData(apiData) {
  if (!Array.isArray(apiData)) return { candles: [], volumes: [] };
  
  const candles = [];
  const volumes = [];
  
  for (const item of apiData) {
    const time = item.time || item.open_time / 1000;
    const open = parseFloat(item.open);
    const high = parseFloat(item.high);
    const low = parseFloat(item.low);
    const close = parseFloat(item.close);
    const volume = parseFloat(item.volume || 0);
    
    // Validate data
    if (isNaN(time) || isNaN(open) || isNaN(high) || isNaN(low) || isNaN(close)) {
      continue;
    }
    
    candles.push({ time, open, high, low, close });
    volumes.push({
      time,
      value: volume,
      color: close >= open ? '#3fb95080' : '#f8514980'
    });
  }
  
  return { candles, volumes };
}

/**
 * Normalize price data for comparison chart (percentage change from start)
 */
function normalizeForComparison(data, baseIndex = 0) {
  if (!Array.isArray(data) || data.length === 0) return [];
  
  const basePrice = data[baseIndex]?.close;
  if (!basePrice || basePrice === 0) return [];
  
  return data.map(item => ({
    time: item.time,
    value: ((item.close - basePrice) / basePrice) * 100
  }));
}

/**
 * Aggregate candles to higher timeframe
 */
function aggregateCandles(candles, factor) {
  if (!Array.isArray(candles) || candles.length === 0 || factor <= 1) {
    return candles;
  }
  
  const result = [];
  
  for (let i = 0; i < candles.length; i += factor) {
    const chunk = candles.slice(i, i + factor);
    if (chunk.length === 0) continue;
    
    const aggregated = {
      time: chunk[0].time,
      open: chunk[0].open,
      high: Math.max(...chunk.map(c => c.high)),
      low: Math.min(...chunk.map(c => c.low)),
      close: chunk[chunk.length - 1].close
    };
    
    result.push(aggregated);
  }
  
  return result;
}

/**
 * Calculate price statistics
 */
function calculatePriceStats(candles) {
  if (!Array.isArray(candles) || candles.length === 0) {
    return null;
  }
  
  const closes = candles.map(c => c.close);
  const highs = candles.map(c => c.high);
  const lows = candles.map(c => c.low);
  
  return {
    high: Math.max(...highs),
    low: Math.min(...lows),
    open: candles[0].open,
    close: candles[candles.length - 1].close,
    change: candles[candles.length - 1].close - candles[0].open,
    changePercent: ((candles[candles.length - 1].close - candles[0].open) / candles[0].open) * 100,
    avgClose: closes.reduce((a, b) => a + b, 0) / closes.length,
    volatility: Math.sqrt(
      closes.reduce((sum, val, i, arr) => {
        const mean = arr.reduce((a, b) => a + b, 0) / arr.length;
        return sum + Math.pow(val - mean, 2);
      }, 0) / closes.length
    )
  };
}

/**
 * Detect price patterns (simple implementation)
 */
function detectPatterns(candles) {
  if (!Array.isArray(candles) || candles.length < 3) {
    return [];
  }
  
  const patterns = [];
  
  // Check for simple patterns in last 3 candles
  const c1 = candles[candles.length - 3]; // oldest
  const c2 = candles[candles.length - 2];
  const c3 = candles[candles.length - 1]; // newest
  
  // Bullish engulfing
  if (c2.close < c2.open && // Previous red
      c3.close > c3.open && // Current green
      c3.open < c2.close && // Opens below previous close
      c3.close > c2.open) { // Closes above previous open
    patterns.push({ type: 'bullish_engulfing', index: candles.length - 1, sentiment: 'bullish' });
  }
  
  // Bearish engulfing
  if (c2.close > c2.open && // Previous green
      c3.close < c3.open && // Current red
      c3.open > c2.close && // Opens above previous close
      c3.close < c2.open) { // Closes below previous open
    patterns.push({ type: 'bearish_engulfing', index: candles.length - 1, sentiment: 'bearish' });
  }
  
  // Doji (open and close very close)
  const bodySize = Math.abs(c3.close - c3.open);
  const range = c3.high - c3.low;
  if (range > 0 && bodySize / range < 0.1) {
    patterns.push({ type: 'doji', index: candles.length - 1, sentiment: 'neutral' });
  }
  
  // Higher highs and higher lows (uptrend)
  if (c2.high > c1.high && c3.high > c2.high &&
      c2.low > c1.low && c3.low > c2.low) {
    patterns.push({ type: 'uptrend', index: candles.length - 1, sentiment: 'bullish' });
  }
  
  // Lower highs and lower lows (downtrend)
  if (c2.high < c1.high && c3.high < c2.high &&
      c2.low < c1.low && c3.low < c2.low) {
    patterns.push({ type: 'downtrend', index: candles.length - 1, sentiment: 'bearish' });
  }
  
  return patterns;
}


describe('Chart Data Handling', () => {

  describe('transformKlineData', () => {
    it('should transform valid API data', () => {
      const apiData = [
        { time: 1000, open: '100', high: '105', low: '98', close: '102', volume: '1000' },
        { time: 2000, open: '102', high: '108', low: '101', close: '107', volume: '1500' }
      ];
      
      const result = transformKlineData(apiData);
      
      expect(result.candles).toHaveLength(2);
      expect(result.volumes).toHaveLength(2);
      expect(result.candles[0].open).toBe(100);
      expect(result.candles[0].close).toBe(102);
    });

    it('should handle open_time in milliseconds', () => {
      const apiData = [
        { open_time: 1000000, open: '100', high: '105', low: '98', close: '102' }
      ];
      
      const result = transformKlineData(apiData);
      expect(result.candles[0].time).toBe(1000);
    });

    it('should assign correct volume colors', () => {
      const apiData = [
        { time: 1000, open: '100', high: '105', low: '98', close: '102', volume: '100' }, // green
        { time: 2000, open: '102', high: '103', low: '95', close: '96', volume: '100' }   // red
      ];
      
      const result = transformKlineData(apiData);
      
      expect(result.volumes[0].color).toBe('#3fb95080'); // green
      expect(result.volumes[1].color).toBe('#f8514980'); // red
    });

    it('should skip invalid data points', () => {
      const apiData = [
        { time: 1000, open: '100', high: '105', low: '98', close: '102' },
        { time: 'invalid', open: '100', high: '105', low: '98', close: '102' },
        { time: 3000, open: 'bad', high: '105', low: '98', close: '102' },
        { time: 4000, open: '100', high: '105', low: '98', close: '102' }
      ];
      
      const result = transformKlineData(apiData);
      expect(result.candles).toHaveLength(2);
    });

    it('should handle empty array', () => {
      const result = transformKlineData([]);
      expect(result.candles).toEqual([]);
      expect(result.volumes).toEqual([]);
    });

    it('should handle non-array input', () => {
      expect(transformKlineData(null).candles).toEqual([]);
      expect(transformKlineData(undefined).candles).toEqual([]);
      expect(transformKlineData('string').candles).toEqual([]);
    });
  });

  describe('normalizeForComparison', () => {
    it('should normalize data to percentage change', () => {
      const data = [
        { time: 1000, close: 100 },
        { time: 2000, close: 110 },
        { time: 3000, close: 95 }
      ];
      
      const result = normalizeForComparison(data);
      
      expect(result[0].value).toBe(0);      // 0% change at start
      expect(result[1].value).toBe(10);     // 10% up
      expect(result[2].value).toBe(-5);     // 5% down
    });

    it('should support custom base index', () => {
      const data = [
        { time: 1000, close: 100 },
        { time: 2000, close: 200 },
        { time: 3000, close: 400 }
      ];
      
      const result = normalizeForComparison(data, 1);
      
      expect(result[0].value).toBe(-50);    // 50% below base
      expect(result[1].value).toBe(0);      // base
      expect(result[2].value).toBe(100);    // 100% above base
    });

    it('should handle empty array', () => {
      expect(normalizeForComparison([])).toEqual([]);
    });

    it('should handle zero base price', () => {
      const data = [{ time: 1000, close: 0 }];
      expect(normalizeForComparison(data)).toEqual([]);
    });
  });

  describe('aggregateCandles', () => {
    let candles;
    
    beforeEach(() => {
      candles = [
        { time: 1000, open: 100, high: 105, low: 98, close: 102 },
        { time: 2000, open: 102, high: 110, low: 100, close: 108 },
        { time: 3000, open: 108, high: 115, low: 105, close: 112 },
        { time: 4000, open: 112, high: 120, low: 110, close: 118 },
        { time: 5000, open: 118, high: 125, low: 115, close: 122 },
        { time: 6000, open: 122, high: 130, low: 120, close: 128 }
      ];
    });

    it('should aggregate to higher timeframe', () => {
      const result = aggregateCandles(candles, 2);
      
      expect(result).toHaveLength(3);
    });

    it('should preserve first candle open', () => {
      const result = aggregateCandles(candles, 3);
      
      expect(result[0].open).toBe(100);
    });

    it('should take last candle close', () => {
      const result = aggregateCandles(candles, 3);
      
      expect(result[0].close).toBe(112);
    });

    it('should calculate correct high/low', () => {
      const result = aggregateCandles(candles, 3);
      
      expect(result[0].high).toBe(115); // Max of first 3
      expect(result[0].low).toBe(98);   // Min of first 3
    });

    it('should return original if factor <= 1', () => {
      expect(aggregateCandles(candles, 1)).toBe(candles);
      expect(aggregateCandles(candles, 0)).toBe(candles);
    });

    it('should handle empty array', () => {
      expect(aggregateCandles([], 2)).toEqual([]);
    });

    it('should handle incomplete last chunk', () => {
      const result = aggregateCandles(candles.slice(0, 5), 3);
      expect(result).toHaveLength(2);
    });
  });

  describe('calculatePriceStats', () => {
    let candles;
    
    beforeEach(() => {
      candles = testUtils.createMockCandles(10, 50000);
    });

    it('should calculate high and low', () => {
      const stats = calculatePriceStats(candles);
      
      expect(stats.high).toBeGreaterThan(stats.low);
      expect(stats.high).toBeGreaterThanOrEqual(stats.close);
      expect(stats.low).toBeLessThanOrEqual(stats.close);
    });

    it('should calculate change correctly', () => {
      const fixedCandles = [
        { time: 1000, open: 100, high: 110, low: 95, close: 105 },
        { time: 2000, open: 105, high: 120, low: 100, close: 115 }
      ];
      
      const stats = calculatePriceStats(fixedCandles);
      
      expect(stats.change).toBe(15); // 115 - 100
      expect(stats.changePercent).toBe(15); // 15%
    });

    it('should calculate average close', () => {
      const fixedCandles = [
        { time: 1000, open: 100, high: 100, low: 100, close: 100 },
        { time: 2000, open: 100, high: 100, low: 100, close: 200 }
      ];
      
      const stats = calculatePriceStats(fixedCandles);
      expect(stats.avgClose).toBe(150);
    });

    it('should calculate volatility', () => {
      const stats = calculatePriceStats(candles);
      
      expect(stats.volatility).toBeGreaterThan(0);
      expect(typeof stats.volatility).toBe('number');
    });

    it('should return null for empty array', () => {
      expect(calculatePriceStats([])).toBeNull();
    });

    it('should return null for non-array', () => {
      expect(calculatePriceStats(null)).toBeNull();
      expect(calculatePriceStats(undefined)).toBeNull();
    });
  });

  describe('detectPatterns', () => {
    it('should detect bullish engulfing', () => {
      const candles = [
        { time: 1000, open: 100, high: 102, low: 95, close: 96 },  // setup
        { time: 2000, open: 98, high: 99, low: 94, close: 95 },   // red candle
        { time: 3000, open: 94, high: 103, low: 93, close: 101 }  // green engulfs
      ];
      
      const patterns = detectPatterns(candles);
      const engulfing = patterns.find(p => p.type === 'bullish_engulfing');
      
      expect(engulfing).toBeDefined();
      expect(engulfing.sentiment).toBe('bullish');
    });

    it('should detect bearish engulfing', () => {
      const candles = [
        { time: 1000, open: 100, high: 105, low: 99, close: 104 },  // setup
        { time: 2000, open: 103, high: 108, low: 102, close: 106 }, // green candle
        { time: 3000, open: 108, high: 109, low: 100, close: 101 } // red engulfs
      ];
      
      const patterns = detectPatterns(candles);
      const engulfing = patterns.find(p => p.type === 'bearish_engulfing');
      
      expect(engulfing).toBeDefined();
      expect(engulfing.sentiment).toBe('bearish');
    });

    it('should detect doji', () => {
      const candles = [
        { time: 1000, open: 100, high: 105, low: 95, close: 100 },
        { time: 2000, open: 100, high: 105, low: 95, close: 100 },
        { time: 3000, open: 100, high: 110, low: 90, close: 100.5 } // doji
      ];
      
      const patterns = detectPatterns(candles);
      const doji = patterns.find(p => p.type === 'doji');
      
      expect(doji).toBeDefined();
      expect(doji.sentiment).toBe('neutral');
    });

    it('should detect uptrend', () => {
      const candles = [
        { time: 1000, open: 100, high: 105, low: 98, close: 104 },
        { time: 2000, open: 104, high: 110, low: 102, close: 108 },
        { time: 3000, open: 108, high: 115, low: 106, close: 113 }
      ];
      
      const patterns = detectPatterns(candles);
      const uptrend = patterns.find(p => p.type === 'uptrend');
      
      expect(uptrend).toBeDefined();
      expect(uptrend.sentiment).toBe('bullish');
    });

    it('should return empty for insufficient data', () => {
      expect(detectPatterns([])).toEqual([]);
      expect(detectPatterns([{ time: 1 }])).toEqual([]);
      expect(detectPatterns([{ time: 1 }, { time: 2 }])).toEqual([]);
    });
  });
});
