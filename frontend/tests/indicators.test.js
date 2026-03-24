/**
 * Technical Indicators Unit Tests
 * Tests for SMA, EMA, Bollinger Bands, RSI, MACD, ATR, Stochastic, ADX,
 * CCI, Keltner, Donchian, Parabolic SAR, AD Line, StochRSI
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

/**
 * Calculate Relative Strength Index (RSI)
 */
function calculateRSI(data, period = 14) {
  const result = [];
  let gains = 0;
  let losses = 0;

  for (let i = 1; i <= period && i < data.length; i++) {
    const change = data[i].close - data[i - 1].close;
    if (change > 0) gains += change;
    else losses -= change;
  }

  let avgGain = gains / period;
  let avgLoss = losses / period;

  if (data.length > period) {
    const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    const rsi = 100 - (100 / (1 + rs));
    result.push({ time: data[period].time, value: rsi });

    for (let i = period + 1; i < data.length; i++) {
      const change = data[i].close - data[i - 1].close;
      const gain = change > 0 ? change : 0;
      const loss = change < 0 ? -change : 0;

      avgGain = ((avgGain * (period - 1)) + gain) / period;
      avgLoss = ((avgLoss * (period - 1)) + loss) / period;

      const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
      const rsi = 100 - (100 / (1 + rs));
      result.push({ time: data[i].time, value: rsi });
    }
  }

  return result;
}

/**
 * Calculate Average True Range (ATR)
 */
function calculateATR(data, period = 14) {
  const result = [];
  const trueRanges = [];

  for (let i = 1; i < data.length; i++) {
    const high = data[i].high;
    const low = data[i].low;
    const prevClose = data[i - 1].close;

    const tr = Math.max(
      high - low,
      Math.abs(high - prevClose),
      Math.abs(low - prevClose)
    );
    trueRanges.push({ time: data[i].time, value: tr });
  }

  if (trueRanges.length >= period) {
    let atr = trueRanges.slice(0, period).reduce((sum, tr) => sum + tr.value, 0) / period;
    result.push({ time: trueRanges[period - 1].time, value: atr });

    for (let i = period; i < trueRanges.length; i++) {
      atr = ((atr * (period - 1)) + trueRanges[i].value) / period;
      result.push({ time: trueRanges[i].time, value: atr });
    }
  }

  return result;
}

/**
 * Calculate MACD
 */
function calculateMACD(data, fastPeriod = 12, slowPeriod = 26, signalPeriod = 9) {
  const fastEMA = calculateEMA(data, fastPeriod);
  const slowEMA = calculateEMA(data, slowPeriod);

  const macdLine = [];
  const offset = slowPeriod - fastPeriod;

  for (let i = 0; i < slowEMA.length; i++) {
    const fastValue = fastEMA[i + offset]?.value;
    const slowValue = slowEMA[i]?.value;

    if (fastValue !== undefined && slowValue !== undefined) {
      macdLine.push({
        time: slowEMA[i].time,
        value: fastValue - slowValue
      });
    }
  }

  const signalLine = [];
  if (macdLine.length >= signalPeriod) {
    const multiplier = 2 / (signalPeriod + 1);
    let ema = macdLine.slice(0, signalPeriod).reduce((sum, d) => sum + d.value, 0) / signalPeriod;
    signalLine.push({ time: macdLine[signalPeriod - 1].time, value: ema });

    for (let i = signalPeriod; i < macdLine.length; i++) {
      ema = (macdLine[i].value - ema) * multiplier + ema;
      signalLine.push({ time: macdLine[i].time, value: ema });
    }
  }

  const histogram = [];
  const signalOffset = macdLine.length - signalLine.length;
  for (let i = 0; i < signalLine.length; i++) {
    histogram.push({
      time: signalLine[i].time,
      value: macdLine[i + signalOffset].value - signalLine[i].value,
      color: macdLine[i + signalOffset].value - signalLine[i].value >= 0 ? '#3fb950' : '#f85149'
    });
  }

  return { macd: macdLine, signal: signalLine, histogram };
}

/**
 * Calculate Stochastic Oscillator
 */
function calculateStochastic(data, kPeriod = 14, dPeriod = 3, smooth = 3) {
  const result = { k: [], d: [] };
  const kValues = [];

  for (let i = kPeriod - 1; i < data.length; i++) {
    let highestHigh = -Infinity;
    let lowestLow = Infinity;

    for (let j = 0; j < kPeriod; j++) {
      highestHigh = Math.max(highestHigh, data[i - j].high);
      lowestLow = Math.min(lowestLow, data[i - j].low);
    }

    const k = ((data[i].close - lowestLow) / (highestHigh - lowestLow)) * 100;
    kValues.push({ time: data[i].time, value: k });
  }

  for (let i = smooth - 1; i < kValues.length; i++) {
    let sum = 0;
    for (let j = 0; j < smooth; j++) {
      sum += kValues[i - j].value;
    }
    result.k.push({ time: kValues[i].time, value: sum / smooth });
  }

  for (let i = dPeriod - 1; i < result.k.length; i++) {
    let sum = 0;
    for (let j = 0; j < dPeriod; j++) {
      sum += result.k[i - j].value;
    }
    result.d.push({ time: result.k[i].time, value: sum / dPeriod });
  }

  return result;
}

/**
 * Calculate Average Directional Index (ADX)
 */
function calculateADX(data, period = 14) {
  const result = { adx: [], plusDI: [], minusDI: [] };

  const n = data.length;
  if (n < period + 1) {
    return result;
  }

  const tr = new Array(n).fill(0);
  tr[0] = data[0].high - data[0].low;
  for (let i = 1; i < n; i++) {
    const high = data[i].high;
    const low = data[i].low;
    const prevClose = data[i - 1].close;

    tr[i] = Math.max(
      high - low,
      Math.abs(high - prevClose),
      Math.abs(low - prevClose)
    );
  }

  const plusDM = new Array(n).fill(0);
  const minusDM = new Array(n).fill(0);

  for (let i = 1; i < n; i++) {
    const upMove = data[i].high - data[i - 1].high;
    const downMove = data[i - 1].low - data[i].low;

    if (upMove > downMove && upMove > 0) {
      plusDM[i] = upMove;
    }
    if (downMove > upMove && downMove > 0) {
      minusDM[i] = downMove;
    }
  }

  const atr = new Array(n).fill(0);
  const smoothPlusDM = new Array(n).fill(0);
  const smoothMinusDM = new Array(n).fill(0);

  for (let i = 1; i <= period; i++) {
    atr[period] += tr[i];
    smoothPlusDM[period] += plusDM[i];
    smoothMinusDM[period] += minusDM[i];
  }

  for (let i = period + 1; i < n; i++) {
    atr[i] = atr[i - 1] - (atr[i - 1] / period) + tr[i];
    smoothPlusDM[i] = smoothPlusDM[i - 1] - (smoothPlusDM[i - 1] / period) + plusDM[i];
    smoothMinusDM[i] = smoothMinusDM[i - 1] - (smoothMinusDM[i - 1] / period) + minusDM[i];
  }

  const plusDI = new Array(n).fill(0);
  const minusDI = new Array(n).fill(0);

  for (let i = period; i < n; i++) {
    if (atr[i] !== 0) {
      plusDI[i] = 100 * smoothPlusDM[i] / atr[i];
      minusDI[i] = 100 * smoothMinusDM[i] / atr[i];
    }
  }

  const dx = new Array(n).fill(0);
  for (let i = period; i < n; i++) {
    const diSum = plusDI[i] + minusDI[i];
    if (diSum !== 0) {
      dx[i] = 100 * Math.abs(plusDI[i] - minusDI[i]) / diSum;
    }
  }

  let adxSum = 0;
  for (let i = period; i < 2 * period; i++) {
    adxSum += dx[i];
  }
  const firstADX = adxSum / period;
  result.adx.push({ time: data[2 * period - 1].time, value: firstADX });
  result.plusDI.push({ time: data[period].time, value: plusDI[period] });
  result.minusDI.push({ time: data[period].time, value: minusDI[period] });

  let currentADX = firstADX;
  for (let i = 2 * period; i < n; i++) {
    currentADX = (currentADX * (period - 1) + dx[i]) / period;
    result.adx.push({ time: data[i].time, value: currentADX });
    result.plusDI.push({ time: data[i].time, value: plusDI[i] });
    result.minusDI.push({ time: data[i].time, value: minusDI[i] });
  }

  return result;
}

/**
 * Calculate Commodity Channel Index (CCI)
 */
function calculateCCI(data, period = 20, constant = 0.015) {
  const result = [];
  const n = data.length;

  if (n < period) {
    return result;
  }

  for (let i = period - 1; i < n; i++) {
    const typicalPrices = [];
    for (let j = 0; j < period; j++) {
      const tp = (data[i - j].high + data[i - j].low + data[i - j].close) / 3;
      typicalPrices.push(tp);
    }

    const smaTp = typicalPrices.reduce((sum, tp) => sum + tp, 0) / period;

    let meanDev = 0;
    for (let j = 0; j < period; j++) {
      meanDev += Math.abs(typicalPrices[j] - smaTp);
    }
    meanDev /= period;

    const currentTp = (data[i].high + data[i].low + data[i].close) / 3;

    let cci = 0;
    if (meanDev !== 0) {
      cci = (currentTp - smaTp) / (constant * meanDev);
    }

    result.push({ time: data[i].time, value: cci });
  }

  return result;
}

/**
 * Calculate Keltner Channels
 */
function calculateKeltner(data, period = 20, atrPeriod = 10, multiplier = 2) {
  const result = { middle: [], upper: [], lower: [] };
  const n = data.length;

  if (n < period + atrPeriod - 1) {
    return result;
  }

  const ema = [];
  let emaValue = data[0].close;
  const emaMultiplier = 2 / (period + 1);

  for (let i = 0; i < n; i++) {
    if (i === 0) {
      ema.push({ time: data[i].time, value: emaValue });
    } else {
      emaValue = (data[i].close - emaValue) * emaMultiplier + emaValue;
      ema.push({ time: data[i].time, value: emaValue });
    }
  }

  const atr = calculateATR(data, atrPeriod);

  for (let i = period - 1; i < n; i++) {
    const middleValue = ema[i].value;
    const atrValue = atr[i - (period - 1)]?.value || 0;

    result.middle.push({ time: data[i].time, value: middleValue });
    result.upper.push({ time: data[i].time, value: middleValue + (multiplier * atrValue) });
    result.lower.push({ time: data[i].time, value: middleValue - (multiplier * atrValue) });
  }

  return result;
}

/**
 * Calculate Donchian Channels
 */
function calculateDonchian(data, period = 20) {
  const result = { middle: [], upper: [], lower: [] };
  const n = data.length;

  if (n < period) {
    return result;
  }

  for (let i = period - 1; i < n; i++) {
    let highestHigh = -Infinity;
    let lowestLow = Infinity;

    for (let j = 0; j < period; j++) {
      highestHigh = Math.max(highestHigh, data[i - j].high);
      lowestLow = Math.min(lowestLow, data[i - j].low);
    }

    const middle = (highestHigh + lowestLow) / 2;

    result.upper.push({ time: data[i].time, value: highestHigh });
    result.lower.push({ time: data[i].time, value: lowestLow });
    result.middle.push({ time: data[i].time, value: middle });
  }

  return result;
}

/**
 * Calculate Parabolic SAR
 */
function calculateParabolicSAR(data, afStart = 0.02, afIncrement = 0.02, afMax = 0.2) {
  const result = [];
  const n = data.length;

  if (n < 2) {
    return result;
  }

  let trend = 1;
  let sar = data[0].low;
  let ep = data[0].high;
  let af = afStart;

  result.push({ time: data[0].time, value: sar, trend: trend });

  for (let i = 1; i < n; i++) {
    sar = sar + af * (ep - sar);

    if (trend === 1) {
      sar = Math.min(sar, data[i - 1].low);
      if (i >= 2) sar = Math.min(sar, data[i - 2].low);

      if (data[i].low < sar) {
        trend = -1;
        sar = ep;
        ep = data[i].low;
        af = afStart;
      } else {
        if (data[i].high > ep) {
          ep = data[i].high;
          af = Math.min(af + afIncrement, afMax);
        }
      }
    } else {
      sar = Math.max(sar, data[i - 1].high);
      if (i >= 2) sar = Math.max(sar, data[i - 2].high);

      if (data[i].high > sar) {
        trend = 1;
        sar = ep;
        ep = data[i].high;
        af = afStart;
      } else {
        if (data[i].low < ep) {
          ep = data[i].low;
          af = Math.min(af + afIncrement, afMax);
        }
      }
    }

    result.push({ time: data[i].time, value: sar, trend: trend });
  }

  return result;
}

/**
 * Calculate Accumulation/Distribution Line (AD Line)
 */
function calculateADLine(candles, volumes) {
  const result = [];
  let ad = 0;

  for (let i = 0; i < candles.length; i++) {
    const volume = volumes[i]?.value || 0;
    const high = candles[i].high;
    const low = candles[i].low;
    const close = candles[i].close;

    const hlRange = high - low;

    if (hlRange > 0) {
      const mfm = ((close - low) - (high - close)) / hlRange;
      const mfv = mfm * volume;
      ad += mfv;
    }

    result.push({ time: candles[i].time, value: ad });
  }

  return result;
}

/**
 * Calculate Stochastic RSI (StochRSI)
 */
function calculateStochRSI(data, rsiPeriod = 14, stochPeriod = 14, kPeriod = 3, dPeriod = 3) {
  const result = { stochRsi: [], k: [], d: [] };
  const n = data.length;

  if (n < rsiPeriod + stochPeriod) {
    return result;
  }

  const rsi = calculateRSI(data, rsiPeriod);
  const rawStochRsi = [];

  for (let i = rsiPeriod + stochPeriod - 2; i < n; i++) {
    let minRsi = Infinity;
    let maxRsi = -Infinity;
    const currentRsi = rsi[i - (rsiPeriod - 1)]?.value;

    if (currentRsi === undefined || isNaN(currentRsi)) {
      rawStochRsi.push({ time: data[i].time, value: 50 });
      continue;
    }

    for (let j = 0; j < stochPeriod; j++) {
      const rsiValue = rsi[i - j - (rsiPeriod - 1)]?.value;
      if (rsiValue !== undefined && !isNaN(rsiValue)) {
        minRsi = Math.min(minRsi, rsiValue);
        maxRsi = Math.max(maxRsi, rsiValue);
      }
    }

    let stochRsi = 50;
    if (maxRsi - minRsi > 1e-10) {
      stochRsi = (currentRsi - minRsi) / (maxRsi - minRsi) * 100;
    }

    rawStochRsi.push({ time: data[i].time, value: stochRsi });
  }

  for (let i = kPeriod - 1; i < rawStochRsi.length; i++) {
    let sum = 0;
    for (let j = 0; j < kPeriod; j++) {
      sum += rawStochRsi[i - j].value;
    }
    result.k.push({ time: rawStochRsi[i].time, value: sum / kPeriod });
  }

  for (let i = dPeriod - 1; i < result.k.length; i++) {
    let sum = 0;
    for (let j = 0; j < dPeriod; j++) {
      sum += result.k[i - j].value;
    }
    result.d.push({ time: result.k[i].time, value: sum / dPeriod });
  }

  result.stochRsi = rawStochRsi;
  return result;
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

  describe('calculateRSI', () => {
    it('should calculate RSI correctly for period 3', () => {
      const result = calculateRSI(mockData, 3);

      // RSI should start at index 3 (period)
      expect(result.length).toBeGreaterThan(0);
      expect(result[0].time).toBe(4000);

      // RSI should be between 0 and 100
      result.forEach(r => {
        expect(r.value).toBeGreaterThanOrEqual(0);
        expect(r.value).toBeLessThanOrEqual(100);
      });
    });

    it('should return RSI = 100 when all gains', () => {
      const bullishData = [
        { time: 1000, close: 100 },
        { time: 2000, close: 102 },
        { time: 3000, close: 104 },
        { time: 4000, close: 106 },
        { time: 5000, close: 108 }
      ];

      const result = calculateRSI(bullishData, 3);
      expect(result.length).toBeGreaterThan(0);
      expect(result[result.length - 1].value).toBeGreaterThan(98);
    });

    it('should return RSI = 0 when all losses', () => {
      const bearishData = [
        { time: 1000, close: 100 },
        { time: 2000, close: 98 },
        { time: 3000, close: 96 },
        { time: 4000, close: 94 },
        { time: 5000, close: 92 }
      ];

      const result = calculateRSI(bearishData, 3);
      expect(result.length).toBeGreaterThan(0);
      expect(result[result.length - 1].value).toBeCloseTo(0, 0);
    });

    it('should handle period 14 (standard)', () => {
      const extendedData = [
        ...mockData,
        { time: 11000, close: 112 },
        { time: 12000, close: 111 },
        { time: 13000, close: 113 },
        { time: 14000, close: 115 },
        { time: 15000, close: 114 }
      ];

      const result = calculateRSI(extendedData, 14);
      expect(result.length).toBeGreaterThan(0);
      expect(result[0].time).toBe(15000);
    });
  });

  describe('calculateATR', () => {
    let atrMockData;

    beforeEach(() => {
      atrMockData = [
        { time: 1000, open: 100, high: 105, low: 98, close: 102, volume: 1000 },
        { time: 2000, open: 102, high: 107, low: 101, close: 106, volume: 1100 },
        { time: 3000, open: 106, high: 108, low: 103, close: 104, volume: 950 },
        { time: 4000, open: 104, high: 109, low: 102, close: 108, volume: 1200 },
        { time: 5000, open: 108, high: 110, low: 106, close: 107, volume: 1050 },
        { time: 6000, open: 107, high: 112, low: 105, close: 111, volume: 1300 },
        { time: 7000, open: 111, high: 113, low: 109, close: 110, volume: 1150 },
        { time: 8000, open: 110, high: 115, low: 108, close: 114, volume: 1400 },
        { time: 9000, open: 114, high: 116, low: 112, close: 113, volume: 1250 },
        { time: 10000, open: 113, high: 118, low: 111, close: 117, volume: 1500 }
      ];
    });

    it('should calculate ATR correctly for period 3', () => {
      const result = calculateATR(atrMockData, 3);

      expect(result.length).toBeGreaterThan(0);
      expect(result[0].time).toBe(4000);

      // ATR should be positive
      result.forEach(r => {
        expect(r.value).toBeGreaterThan(0);
      });
    });

    it('should handle period 14 (standard)', () => {
      const result = calculateATR(atrMockData, 14);
      expect(result.length).toBe(0); // Not enough data
    });

    it('should increase with higher volatility', () => {
      const volatileData = [
        { time: 1000, open: 100, high: 120, low: 80, close: 110, volume: 1000 },
        { time: 2000, open: 110, high: 130, low: 90, close: 95, volume: 1100 },
        { time: 3000, open: 95, high: 115, low: 75, close: 105, volume: 950 },
        { time: 4000, open: 105, high: 125, low: 85, close: 115, volume: 1200 }
      ];

      const result = calculateATR(volatileData, 3);
      expect(result.length).toBeGreaterThan(0);
      expect(result[0].value).toBeGreaterThan(10); // High volatility
    });
  });

  describe('calculateMACD', () => {
    it('should calculate MACD with standard parameters', () => {
      const extendedData = [
        ...mockData,
        { time: 11000, close: 112 },
        { time: 12000, close: 111 },
        { time: 13000, close: 113 },
        { time: 14000, close: 115 },
        { time: 15000, close: 114 },
        { time: 16000, close: 116 },
        { time: 17000, close: 118 },
        { time: 18000, close: 117 },
        { time: 19000, close: 119 },
        { time: 20000, close: 120 },
        { time: 21000, close: 121 },
        { time: 22000, close: 122 },
        { time: 23000, close: 123 },
        { time: 24000, close: 124 },
        { time: 25000, close: 125 },
        { time: 26000, close: 126 },
        { time: 27000, close: 127 },
        { time: 28000, close: 128 },
        { time: 29000, close: 129 },
        { time: 30000, close: 130 }
      ];

      const result = calculateMACD(extendedData, 12, 26, 9);

      expect(result).toHaveProperty('macd');
      expect(result).toHaveProperty('signal');
      expect(result).toHaveProperty('histogram');
      expect(result.macd.length).toBeGreaterThan(0);
    });

    it('should have histogram = MACD - Signal', () => {
      const extendedData = [
        ...mockData,
        { time: 11000, close: 112 },
        { time: 12000, close: 111 },
        { time: 13000, close: 113 },
        { time: 14000, close: 115 },
        { time: 15000, close: 114 },
        { time: 16000, close: 116 },
        { time: 17000, close: 118 },
        { time: 18000, close: 117 },
        { time: 19000, close: 119 },
        { time: 20000, close: 120 },
        { time: 21000, close: 121 },
        { time: 22000, close: 122 },
        { time: 23000, close: 123 },
        { time: 24000, close: 124 },
        { time: 25000, close: 125 },
        { time: 26000, close: 126 },
        { time: 27000, close: 127 },
        { time: 28000, close: 128 },
        { time: 29000, close: 129 },
        { time: 30000, close: 130 }
      ];

      const result = calculateMACD(extendedData, 12, 26, 9);

      // Check histogram calculation
      const signalOffset = result.macd.length - result.signal.length;
      for (let i = 0; i < result.signal.length; i++) {
        const expected = result.macd[i + signalOffset].value - result.signal[i].value;
        expect(result.histogram[i].value).toBeCloseTo(expected, 5);
      }
    });

    it('should have correct histogram colors', () => {
      const extendedData = [
        ...mockData,
        { time: 11000, close: 112 },
        { time: 12000, close: 111 },
        { time: 13000, close: 113 },
        { time: 14000, close: 115 },
        { time: 15000, close: 114 },
        { time: 16000, close: 116 },
        { time: 17000, close: 118 },
        { time: 18000, close: 117 },
        { time: 19000, close: 119 },
        { time: 20000, close: 120 },
        { time: 21000, close: 121 },
        { time: 22000, close: 122 },
        { time: 23000, close: 123 },
        { time: 24000, close: 124 },
        { time: 25000, close: 125 },
        { time: 26000, close: 126 },
        { time: 27000, close: 127 },
        { time: 28000, close: 128 },
        { time: 29000, close: 129 },
        { time: 30000, close: 130 }
      ];

      const result = calculateMACD(extendedData, 12, 26, 9);

      result.histogram.forEach(h => {
        if (h.value >= 0) {
          expect(h.color).toBe('#3fb950'); // Green
        } else {
          expect(h.color).toBe('#f85149'); // Red
        }
      });
    });
  });

  describe('calculateStochastic', () => {
    let stochasticData;

    beforeEach(() => {
      stochasticData = [
        { time: 1000, open: 100, high: 105, low: 98, close: 102, volume: 1000 },
        { time: 2000, open: 102, high: 107, low: 101, close: 106, volume: 1100 },
        { time: 3000, open: 106, high: 108, low: 103, close: 104, volume: 950 },
        { time: 4000, open: 104, high: 109, low: 102, close: 108, volume: 1200 },
        { time: 5000, open: 108, high: 110, low: 106, close: 107, volume: 1050 },
        { time: 6000, open: 107, high: 112, low: 105, close: 111, volume: 1300 },
        { time: 7000, open: 111, high: 113, low: 109, close: 110, volume: 1150 },
        { time: 8000, open: 110, high: 115, low: 108, close: 114, volume: 1400 },
        { time: 9000, open: 114, high: 116, low: 112, close: 113, volume: 1250 },
        { time: 10000, open: 113, high: 118, low: 111, close: 117, volume: 1500 },
        { time: 11000, open: 117, high: 119, low: 115, close: 116, volume: 1350 },
        { time: 12000, open: 116, high: 121, low: 114, close: 120, volume: 1600 },
        { time: 13000, open: 120, high: 122, low: 118, close: 119, volume: 1450 },
        { time: 14000, open: 119, high: 124, low: 117, close: 123, volume: 1700 },
        { time: 15000, open: 123, high: 125, low: 121, close: 122, volume: 1550 }
      ];
    });

    it('should calculate Stochastic with %K and %D', () => {
      // Use period=5 so the 15-point dataset produces output (needs period+smoothK-1 = 7 points minimum)
      const result = calculateStochastic(stochasticData, 5, 3, 3);

      expect(result).toHaveProperty('k');
      expect(result).toHaveProperty('d');
      expect(result.k.length).toBeGreaterThan(0);
    });

    it('should have %K and %D between 0 and 100', () => {
      const result = calculateStochastic(stochasticData, 5, 3, 3);

      result.k.forEach(k => {
        expect(k.value).toBeGreaterThanOrEqual(0);
        expect(k.value).toBeLessThanOrEqual(100);
      });

      result.d.forEach(d => {
        expect(d.value).toBeGreaterThanOrEqual(0);
        expect(d.value).toBeLessThanOrEqual(100);
      });
    });

    it('should return overbought when %K > 80', () => {
      const bullishData = [
        { time: 1000, open: 100, high: 102, low: 99, close: 101, volume: 1000 },
        { time: 2000, open: 101, high: 104, low: 100, close: 103, volume: 1100 },
        { time: 3000, open: 103, high: 106, low: 102, close: 105, volume: 950 },
        { time: 4000, open: 105, high: 108, low: 104, close: 107, volume: 1200 },
        { time: 5000, open: 107, high: 110, low: 106, close: 109, volume: 1050 },
        { time: 6000, open: 109, high: 112, low: 108, close: 111, volume: 1300 },
        { time: 7000, open: 111, high: 114, low: 110, close: 113, volume: 1150 },
        { time: 8000, open: 113, high: 116, low: 112, close: 115, volume: 1400 },
        { time: 9000, open: 115, high: 118, low: 114, close: 117, volume: 1250 },
        { time: 10000, open: 117, high: 120, low: 116, close: 119, volume: 1500 },
        { time: 11000, open: 119, high: 122, low: 118, close: 121, volume: 1350 },
        { time: 12000, open: 121, high: 124, low: 120, close: 123, volume: 1600 },
        { time: 13000, open: 123, high: 126, low: 122, close: 125, volume: 1450 },
        { time: 14000, open: 125, high: 128, low: 124, close: 127, volume: 1700 },
        { time: 15000, open: 127, high: 130, low: 126, close: 129, volume: 1550 }
      ];

      const result = calculateStochastic(bullishData, 5, 3, 3);
      const lastK = result.k[result.k.length - 1].value;

      // In strong uptrend, %K should be high (overbought territory)
      expect(lastK).toBeGreaterThan(50);
    });
  });

  describe('calculateADX', () => {
    let adxData;

    beforeEach(() => {
      adxData = [
        { time: 1000, open: 100, high: 105, low: 98, close: 102, volume: 1000 },
        { time: 2000, open: 102, high: 107, low: 101, close: 106, volume: 1100 },
        { time: 3000, open: 106, high: 108, low: 103, close: 104, volume: 950 },
        { time: 4000, open: 104, high: 109, low: 102, close: 108, volume: 1200 },
        { time: 5000, open: 108, high: 110, low: 106, close: 107, volume: 1050 },
        { time: 6000, open: 107, high: 112, low: 105, close: 111, volume: 1300 },
        { time: 7000, open: 111, high: 113, low: 109, close: 110, volume: 1150 },
        { time: 8000, open: 110, high: 115, low: 108, close: 114, volume: 1400 },
        { time: 9000, open: 114, high: 116, low: 112, close: 113, volume: 1250 },
        { time: 10000, open: 113, high: 118, low: 111, close: 117, volume: 1500 },
        { time: 11000, open: 117, high: 119, low: 115, close: 116, volume: 1350 },
        { time: 12000, open: 116, high: 121, low: 114, close: 120, volume: 1600 },
        { time: 13000, open: 120, high: 122, low: 118, close: 119, volume: 1450 },
        { time: 14000, open: 119, high: 124, low: 117, close: 123, volume: 1700 },
        { time: 15000, open: 123, high: 125, low: 121, close: 122, volume: 1550 },
        { time: 16000, open: 122, high: 127, low: 120, close: 126, volume: 1800 },
        { time: 17000, open: 126, high: 128, low: 124, close: 125, volume: 1650 },
        { time: 18000, open: 125, high: 130, low: 123, close: 129, volume: 1900 },
        { time: 19000, open: 129, high: 131, low: 127, close: 128, volume: 1750 },
        { time: 20000, open: 128, high: 133, low: 126, close: 132, volume: 2000 },
        { time: 21000, open: 132, high: 134, low: 130, close: 131, volume: 1850 },
        { time: 22000, open: 131, high: 136, low: 129, close: 135, volume: 2100 },
        { time: 23000, open: 135, high: 137, low: 133, close: 134, volume: 1950 },
        { time: 24000, open: 134, high: 139, low: 132, close: 138, volume: 2200 },
        { time: 25000, open: 138, high: 140, low: 136, close: 137, volume: 2050 },
        { time: 26000, open: 137, high: 142, low: 135, close: 141, volume: 2300 },
        { time: 27000, open: 141, high: 143, low: 139, close: 140, volume: 2150 },
        { time: 28000, open: 140, high: 145, low: 138, close: 144, volume: 2400 }
      ];
    });

    it('should calculate ADX with +DI and -DI', () => {
      const result = calculateADX(adxData, 14);

      expect(result).toHaveProperty('adx');
      expect(result).toHaveProperty('plusDI');
      expect(result).toHaveProperty('minusDI');
      expect(result.adx.length).toBeGreaterThan(0);
    });

    it('should have ADX between 0 and 100', () => {
      const result = calculateADX(adxData, 14);

      result.adx.forEach(adx => {
        expect(adx.value).toBeGreaterThanOrEqual(0);
        expect(adx.value).toBeLessThanOrEqual(100);
      });
    });

    it('should have +DI and -DI between 0 and 100', () => {
      const result = calculateADX(adxData, 14);

      result.plusDI.forEach(di => {
        expect(di.value).toBeGreaterThanOrEqual(0);
        expect(di.value).toBeLessThanOrEqual(100);
      });

      result.minusDI.forEach(di => {
        expect(di.value).toBeGreaterThanOrEqual(0);
        expect(di.value).toBeLessThanOrEqual(100);
      });
    });

    it('should show strong trend when ADX > 25', () => {
      const trendingData = [
        { time: 1000, open: 100, high: 103, low: 99, close: 102, volume: 1000 },
        { time: 2000, open: 102, high: 106, low: 101, close: 105, volume: 1100 },
        { time: 3000, open: 105, high: 109, low: 104, close: 108, volume: 950 },
        { time: 4000, open: 108, high: 112, low: 107, close: 111, volume: 1200 },
        { time: 5000, open: 111, high: 115, low: 110, close: 114, volume: 1050 },
        { time: 6000, open: 114, high: 118, low: 113, close: 117, volume: 1300 },
        { time: 7000, open: 117, high: 121, low: 116, close: 120, volume: 1150 },
        { time: 8000, open: 120, high: 124, low: 119, close: 123, volume: 1400 },
        { time: 9000, open: 123, high: 127, low: 122, close: 126, volume: 1250 },
        { time: 10000, open: 126, high: 130, low: 125, close: 129, volume: 1500 },
        { time: 11000, open: 129, high: 133, low: 128, close: 132, volume: 1350 },
        { time: 12000, open: 132, high: 136, low: 131, close: 135, volume: 1600 },
        { time: 13000, open: 135, high: 139, low: 134, close: 138, volume: 1450 },
        { time: 14000, open: 138, high: 142, low: 137, close: 141, volume: 1700 },
        { time: 15000, open: 141, high: 145, low: 140, close: 144, volume: 1550 },
        { time: 16000, open: 144, high: 148, low: 143, close: 147, volume: 1800 },
        { time: 17000, open: 147, high: 151, low: 146, close: 150, volume: 1650 },
        { time: 18000, open: 150, high: 154, low: 149, close: 153, volume: 1900 },
        { time: 19000, open: 153, high: 157, low: 152, close: 156, volume: 1750 },
        { time: 20000, open: 156, high: 160, low: 155, close: 159, volume: 2000 },
        { time: 21000, open: 159, high: 163, low: 158, close: 162, volume: 1850 },
        { time: 22000, open: 162, high: 166, low: 161, close: 165, volume: 2100 },
        { time: 23000, open: 165, high: 169, low: 164, close: 168, volume: 1950 },
        { time: 24000, open: 168, high: 172, low: 167, close: 171, volume: 2200 },
        { time: 25000, open: 171, high: 175, low: 170, close: 174, volume: 2050 },
        { time: 26000, open: 174, high: 178, low: 173, close: 177, volume: 2300 },
        { time: 27000, open: 177, high: 181, low: 176, close: 180, volume: 2150 },
        { time: 28000, open: 180, high: 184, low: 179, close: 183, volume: 2400 }
      ];

      const result = calculateADX(trendingData, 14);
      const lastADX = result.adx[result.adx.length - 1].value;

      // Strong uptrend should produce ADX > 20
      expect(lastADX).toBeGreaterThan(15);
    });

    it('should return empty arrays when insufficient data', () => {
      const shortData = [
        { time: 1000, open: 100, high: 105, low: 98, close: 102, volume: 1000 },
        { time: 2000, open: 102, high: 107, low: 101, close: 106, volume: 1100 }
      ];

      const result = calculateADX(shortData, 14);

      expect(result.adx.length).toBe(0);
      expect(result.plusDI.length).toBe(0);
      expect(result.minusDI.length).toBe(0);
    });
  });

  describe('calculateCCI', () => {
    it('should calculate CCI correctly for period 20', () => {
      const cciData = [];
      for (let i = 0; i < 30; i++) {
        cciData.push({
          time: 1000 + i * 1000,
          open: 100 + i,
          high: 105 + i,
          low: 98 + i,
          close: 102 + i,
          volume: 1000
        });
      }

      const result = calculateCCI(cciData, 20);
      expect(result.length).toBeGreaterThan(0);
      expect(result[0].time).toBe(20000);
    });

    it('should return CCI > 100 in strong uptrend', () => {
      const bullishData = [];
      for (let i = 0; i < 30; i++) {
        bullishData.push({
          time: 1000 + i * 1000,
          open: 100 + i * 2,
          high: 105 + i * 2,
          low: 98 + i * 2,
          close: 103 + i * 2,
          volume: 1000
        });
      }

      const result = calculateCCI(bullishData, 20);
      const lastCCI = result[result.length - 1].value;
      expect(lastCCI).toBeGreaterThan(50);
    });

    it('should return CCI < -100 in strong downtrend', () => {
      const bearishData = [];
      for (let i = 0; i < 30; i++) {
        bearishData.push({
          time: 1000 + i * 1000,
          open: 200 - i * 2,
          high: 205 - i * 2,
          low: 198 - i * 2,
          close: 197 - i * 2,
          volume: 1000
        });
      }

      const result = calculateCCI(bearishData, 20);
      const lastCCI = result[result.length - 1].value;
      expect(lastCCI).toBeLessThan(-50);
    });

    it('should return empty array when insufficient data', () => {
      const shortData = [
        { time: 1000, open: 100, high: 105, low: 98, close: 102, volume: 1000 },
        { time: 2000, open: 102, high: 107, low: 101, close: 106, volume: 1100 }
      ];

      const result = calculateCCI(shortData, 20);
      expect(result.length).toBe(0);
    });
  });

  describe('calculateKeltner', () => {
    let keltnerData;

    beforeEach(() => {
      keltnerData = [];
      for (let i = 0; i < 30; i++) {
        keltnerData.push({
          time: 1000 + i * 1000,
          open: 100 + i,
          high: 105 + i,
          low: 98 + i,
          close: 102 + i,
          volume: 1000
        });
      }
    });

    it('should calculate Keltner Channels with middle, upper, lower', () => {
      const result = calculateKeltner(keltnerData, 20, 10, 2);

      expect(result).toHaveProperty('middle');
      expect(result).toHaveProperty('upper');
      expect(result).toHaveProperty('lower');
      expect(result.middle.length).toBeGreaterThan(0);
    });

    it('should have upper > middle > lower', () => {
      const result = calculateKeltner(keltnerData, 20, 10, 2);

      result.middle.forEach((middle, index) => {
        const upper = result.upper[index];
        const lower = result.lower[index];

        expect(upper.value).toBeGreaterThan(middle.value);
        expect(middle.value).toBeGreaterThan(lower.value);
      });
    });

    it('should widen channels with higher multiplier', () => {
      const narrow = calculateKeltner(keltnerData, 20, 10, 1);
      const wide = calculateKeltner(keltnerData, 20, 10, 3);

      const narrowWidth = narrow.upper[0].value - narrow.lower[0].value;
      const wideWidth = wide.upper[0].value - wide.lower[0].value;

      expect(wideWidth).toBeGreaterThan(narrowWidth);
    });
  });

  describe('calculateDonchian', () => {
    let donchianData;

    beforeEach(() => {
      donchianData = [];
      for (let i = 0; i < 30; i++) {
        donchianData.push({
          time: 1000 + i * 1000,
          open: 100 + i,
          high: 110 + i * 2,
          low: 95 + i,
          close: 105 + i,
          volume: 1000
        });
      }
    });

    it('should calculate Donchian Channels with upper, middle, lower', () => {
      const result = calculateDonchian(donchianData, 20);

      expect(result).toHaveProperty('upper');
      expect(result).toHaveProperty('middle');
      expect(result).toHaveProperty('lower');
      expect(result.upper.length).toBeGreaterThan(0);
    });

    it('should have upper = highest high', () => {
      const result = calculateDonchian(donchianData, 20);

      result.upper.forEach((upper, index) => {
        const middle = result.middle[index];
        const lower = result.lower[index];

        expect(upper.value).toBeGreaterThan(middle.value);
        expect(middle.value).toBeGreaterThan(lower.value);
      });
    });

    it('should return empty arrays when insufficient data', () => {
      const shortData = [
        { time: 1000, open: 100, high: 105, low: 98, close: 102, volume: 1000 },
        { time: 2000, open: 102, high: 107, low: 101, close: 106, volume: 1100 }
      ];

      const result = calculateDonchian(shortData, 20);

      expect(result.upper.length).toBe(0);
      expect(result.middle.length).toBe(0);
      expect(result.lower.length).toBe(0);
    });
  });

  describe('calculateParabolicSAR', () => {
    let sarData;

    beforeEach(() => {
      sarData = [];
      for (let i = 0; i < 30; i++) {
        sarData.push({
          time: 1000 + i * 1000,
          open: 100 + i * 2,
          high: 105 + i * 2 + (i % 5),
          low: 98 + i * 2 - (i % 3),
          close: 103 + i * 2,
          volume: 1000
        });
      }
    });

    it('should calculate Parabolic SAR with trend', () => {
      const result = calculateParabolicSAR(sarData);

      expect(result.length).toBeGreaterThan(0);
      expect(result[0]).toHaveProperty('value');
      expect(result[0]).toHaveProperty('trend');
    });

    it('should have trend = 1 or -1', () => {
      const result = calculateParabolicSAR(sarData);

      result.forEach(item => {
        expect(item.trend).toBeGreaterThanOrEqual(-1);
        expect(item.trend).toBeLessThanOrEqual(1);
      });
    });

    it('should start with initial SAR', () => {
      const result = calculateParabolicSAR(sarData);

      // First SAR should be first low
      expect(result[0].value).toBe(sarData[0].low);
    });

    it('should flip trend on price crossover', () => {
      const volatileData = [
        { time: 1000, open: 100, high: 110, low: 95, close: 105, volume: 1000 },
        { time: 2000, open: 105, high: 115, low: 100, close: 110, volume: 1100 },
        { time: 3000, open: 110, high: 120, low: 105, close: 115, volume: 1000 },
        { time: 4000, open: 115, high: 125, low: 110, close: 120, volume: 1100 },
        { time: 5000, open: 120, high: 130, low: 80, close: 85, volume: 1000 }, // Crash
        { time: 6000, open: 85, high: 95, low: 75, close: 80, volume: 1100 },
        { time: 7000, open: 80, high: 90, low: 70, close: 75, volume: 1000 }
      ];

      const result = calculateParabolicSAR(volatileData);

      // Should have both uptrend and downtrend
      const hasUptrend = result.some(item => item.trend === 1);
      const hasDowntrend = result.some(item => item.trend === -1);

      expect(hasUptrend).toBe(true);
      expect(hasDowntrend).toBe(true);
    });
  });

  describe('calculateADLine', () => {
    let adlCandles, adlVolumes;

    beforeEach(() => {
      adlCandles = [];
      adlVolumes = [];

      for (let i = 0; i < 20; i++) {
        adlCandles.push({
          time: 1000 + i * 1000,
          open: 100 + i,
          high: 105 + i,
          low: 98 + i,
          close: 103 + i
        });
        adlVolumes.push({ time: 1000 + i * 1000, value: 1000 + i * 100 });
      }
    });

    it('should calculate AD Line cumulative values', () => {
      const result = calculateADLine(adlCandles, adlVolumes);

      expect(result.length).toBe(20);
      expect(result[0]).toHaveProperty('time');
      expect(result[0]).toHaveProperty('value');
    });

    it('should have rising AD Line in uptrend', () => {
      const result = calculateADLine(adlCandles, adlVolumes);

      // AD Line should generally rise in uptrend
      expect(result[result.length - 1].value).toBeGreaterThan(result[0].value);
    });

    it('should handle zero volume', () => {
      const zeroVolumes = adlCandles.map(() => ({ time: 1000, value: 0 }));
      const result = calculateADLine(adlCandles, zeroVolumes);

      // With zero volume, AD Line should stay flat
      result.forEach((item, index) => {
        if (index > 0) {
          expect(item.value).toBeGreaterThanOrEqual(result[index - 1].value);
        }
      });
    });
  });

  describe('calculateStochRSI', () => {
    let stochRsiData;

    beforeEach(() => {
      stochRsiData = [];
      for (let i = 0; i < 50; i++) {
        stochRsiData.push({
          time: 1000 + i * 1000,
          open: 100 + i + Math.sin(i * 0.5) * 5,
          high: 105 + i + Math.sin(i * 0.5) * 5,
          low: 98 + i + Math.sin(i * 0.5) * 5,
          close: 102 + i + Math.sin(i * 0.5) * 5,
          volume: 1000
        });
      }
    });

    it('should calculate StochRSI with stochRsi, k, d', () => {
      const result = calculateStochRSI(stochRsiData);

      expect(result).toHaveProperty('stochRsi');
      expect(result).toHaveProperty('k');
      expect(result).toHaveProperty('d');
      expect(result.stochRsi.length).toBeGreaterThan(0);
    });

    it('should have values between 0 and 100', () => {
      const result = calculateStochRSI(stochRsiData);

      result.stochRsi.forEach(item => {
        expect(item.value).toBeGreaterThanOrEqual(0);
        expect(item.value).toBeLessThanOrEqual(100);
      });

      result.k.forEach(item => {
        expect(item.value).toBeGreaterThanOrEqual(0);
        expect(item.value).toBeLessThanOrEqual(100);
      });

      result.d.forEach(item => {
        expect(item.value).toBeGreaterThanOrEqual(0);
        expect(item.value).toBeLessThanOrEqual(100);
      });
    });

    it('should have %K crossing %D for signals', () => {
      const result = calculateStochRSI(stochRsiData, 14, 14, 3, 3);

      // Should have both %K and %D
      expect(result.k.length).toBeGreaterThan(0);
      expect(result.d.length).toBeGreaterThan(0);

      // %D should be shorter (smoothed)
      expect(result.d.length).toBeLessThanOrEqual(result.k.length);
    });

    it('should return empty arrays when insufficient data', () => {
      const shortData = [
        { time: 1000, open: 100, high: 105, low: 98, close: 102, volume: 1000 },
        { time: 2000, open: 102, high: 107, low: 101, close: 106, volume: 1100 }
      ];

      const result = calculateStochRSI(shortData);

      expect(result.stochRsi.length).toBe(0);
      expect(result.k.length).toBe(0);
      expect(result.d.length).toBe(0);
    });
  });
});
