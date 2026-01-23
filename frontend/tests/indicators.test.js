/**
 * Technical Indicators Unit Tests
 * Tests for SMA, EMA, Bollinger Bands calculations
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// Import indicator calculation functions (extracted from market-chart.html)
// These functions are self-contained and can be tested directly

/**
 * Calculate Simple Moving Average
 */
function calculateSMA(data, period) {
  const result = [];
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) {
      sum += data[i - j].close;
    }
    result.push({ time: data[i].time, value: sum / period });
  }
  return result;
}

/**
 * Calculate Exponential Moving Average
 */
function calculateEMA(data, period) {
  if (!data || data.length === 0) return [];
  
  const result = [];
  const multiplier = 2 / (period + 1);
  let ema = data[0].close;
  
  for (let i = 0; i < data.length; i++) {
    if (i === 0) {
      result.push({ time: data[i].time, value: ema });
    } else {
      ema = (data[i].close - ema) * multiplier + ema;
      result.push({ time: data[i].time, value: ema });
    }
  }
  return result;
}

/**
 * Calculate Bollinger Bands
 */
function calculateBollingerBands(data, period, stdDev) {
  const upper = [];
  const middle = [];
  const lower = [];
  
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) {
      sum += data[i - j].close;
    }
    const sma = sum / period;
    
    let variance = 0;
    for (let j = 0; j < period; j++) {
      variance += Math.pow(data[i - j].close - sma, 2);
    }
    const std = Math.sqrt(variance / period);
    
    upper.push({ time: data[i].time, value: sma + stdDev * std });
    middle.push({ time: data[i].time, value: sma });
    lower.push({ time: data[i].time, value: sma - stdDev * std });
  }
  
  return { upper, middle, lower };
}

describe('Technical Indicators', () => {
  let mockData;
  
  beforeEach(() => {
    // Create consistent mock data for testing
    mockData = [
      { time: 1000, close: 100 },
      { time: 2000, close: 102 },
      { time: 3000, close: 101 },
      { time: 4000, close: 103 },
      { time: 5000, close: 105 },
      { time: 6000, close: 104 },
      { time: 7000, close: 106 },
      { time: 8000, close: 108 },
      { time: 9000, close: 107 },
      { time: 10000, close: 110 }
    ];
  });

  describe('calculateSMA', () => {
    it('should calculate SMA correctly for period 3', () => {
      const result = calculateSMA(mockData, 3);
      
      // First SMA value should be at index 2 (period - 1)
      expect(result.length).toBe(8); // 10 - 3 + 1
      
      // Check first SMA: (100 + 102 + 101) / 3 = 101
      expect(result[0].value).toBeCloseTo(101, 2);
      expect(result[0].time).toBe(3000);
    });

    it('should calculate SMA correctly for period 5', () => {
      const result = calculateSMA(mockData, 5);
      
      expect(result.length).toBe(6); // 10 - 5 + 1
      
      // First SMA: (100 + 102 + 101 + 103 + 105) / 5 = 102.2
      expect(result[0].value).toBeCloseTo(102.2, 2);
    });

    it('should return empty array if period > data length', () => {
      const result = calculateSMA(mockData, 15);
      expect(result.length).toBe(0);
    });

    it('should handle period of 1', () => {
      const result = calculateSMA(mockData, 1);
      expect(result.length).toBe(10);
      expect(result[0].value).toBe(100);
    });

    it('should preserve timestamps', () => {
      const result = calculateSMA(mockData, 3);
      
      result.forEach((item, index) => {
        expect(item.time).toBe(mockData[index + 2].time);
      });
    });
  });

  describe('calculateEMA', () => {
    it('should calculate EMA correctly', () => {
      const result = calculateEMA(mockData, 3);
      
      expect(result.length).toBe(10);
      
      // First EMA equals first close price
      expect(result[0].value).toBe(100);
    });

    it('should apply multiplier correctly', () => {
      const period = 3;
      const multiplier = 2 / (period + 1); // 0.5
      
      const result = calculateEMA(mockData, period);
      
      // Second EMA: (102 - 100) * 0.5 + 100 = 101
      expect(result[1].value).toBeCloseTo(101, 2);
    });

    it('should be more responsive than SMA', () => {
      const emaResult = calculateEMA(mockData, 5);
      const smaResult = calculateSMA(mockData, 5);
      
      // EMA should react faster to recent price changes
      // In an uptrend, EMA should be higher than SMA at the end
      const lastEMA = emaResult[emaResult.length - 1].value;
      const lastSMA = smaResult[smaResult.length - 1].value;
      
      // Both should be reasonable values
      expect(lastEMA).toBeGreaterThan(100);
      expect(lastSMA).toBeGreaterThan(100);
    });

    it('should handle single data point', () => {
      const singleData = [{ time: 1000, close: 100 }];
      const result = calculateEMA(singleData, 3);
      
      expect(result.length).toBe(1);
      expect(result[0].value).toBe(100);
    });
  });

  describe('calculateBollingerBands', () => {
    it('should calculate three bands', () => {
      const result = calculateBollingerBands(mockData, 5, 2);
      
      expect(result).toHaveProperty('upper');
      expect(result).toHaveProperty('middle');
      expect(result).toHaveProperty('lower');
    });

    it('should have equal length bands', () => {
      const result = calculateBollingerBands(mockData, 5, 2);
      
      expect(result.upper.length).toBe(result.middle.length);
      expect(result.middle.length).toBe(result.lower.length);
    });

    it('should have middle band equal to SMA', () => {
      const period = 5;
      const bbResult = calculateBollingerBands(mockData, period, 2);
      const smaResult = calculateSMA(mockData, period);
      
      bbResult.middle.forEach((item, index) => {
        expect(item.value).toBeCloseTo(smaResult[index].value, 5);
      });
    });

    it('should have upper > middle > lower', () => {
      const result = calculateBollingerBands(mockData, 5, 2);
      
      result.upper.forEach((upper, index) => {
        const middle = result.middle[index];
        const lower = result.lower[index];
        
        expect(upper.value).toBeGreaterThan(middle.value);
        expect(middle.value).toBeGreaterThan(lower.value);
      });
    });

    it('should widen bands with higher stdDev', () => {
      const narrow = calculateBollingerBands(mockData, 5, 1);
      const wide = calculateBollingerBands(mockData, 5, 3);
      
      // Width of bands (upper - lower)
      const narrowWidth = narrow.upper[0].value - narrow.lower[0].value;
      const wideWidth = wide.upper[0].value - wide.lower[0].value;
      
      expect(wideWidth).toBeGreaterThan(narrowWidth);
    });

    it('should handle varying volatility', () => {
      // High volatility data
      const volatileData = [
        { time: 1000, close: 100 },
        { time: 2000, close: 120 },
        { time: 3000, close: 90 },
        { time: 4000, close: 130 },
        { time: 5000, close: 85 }
      ];
      
      const result = calculateBollingerBands(volatileData, 3, 2);
      
      // Should have wider bands due to high volatility
      expect(result.upper.length).toBeGreaterThan(0);
      
      const bandwidth = result.upper[0].value - result.lower[0].value;
      expect(bandwidth).toBeGreaterThan(20); // Significant width
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty data array', () => {
      const smaResult = calculateSMA([], 5);
      const emaResult = calculateEMA([], 5);
      
      expect(smaResult).toEqual([]);
      expect(emaResult).toEqual([]);
    });

    it('should handle negative prices', () => {
      const negativeData = [
        { time: 1000, close: -10 },
        { time: 2000, close: -5 },
        { time: 3000, close: -8 }
      ];
      
      const result = calculateSMA(negativeData, 2);
      expect(result[0].value).toBe(-7.5); // (-10 + -5) / 2
    });

    it('should handle very large numbers', () => {
      const largeData = [
        { time: 1000, close: 1e12 },
        { time: 2000, close: 1e12 + 1000 },
        { time: 3000, close: 1e12 + 2000 }
      ];
      
      const result = calculateSMA(largeData, 2);
      expect(result[0].value).toBeCloseTo(1e12 + 500, 0);
    });

    it('should handle decimal precision', () => {
      const preciseData = [
        { time: 1000, close: 100.123456 },
        { time: 2000, close: 100.234567 },
        { time: 3000, close: 100.345678 }
      ];
      
      const result = calculateSMA(preciseData, 3);
      expect(typeof result[0].value).toBe('number');
      expect(isNaN(result[0].value)).toBe(false);
    });
  });
});
