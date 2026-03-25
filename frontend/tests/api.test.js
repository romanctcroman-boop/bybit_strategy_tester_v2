/**
 * API Integration Tests
 * Tests for API calls and data handling
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock API base URL
const API_BASE = 'http://localhost:8000';

/**
 * Generic API fetch wrapper
 */
async function apiFetch(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    },
    ...options
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Unknown error' }));
    throw new Error(error.message || error.detail || 'API Error');
  }
  
  return response.json();
}

/**
 * Fetch strategies from API
 */
async function fetchStrategies(filters = {}) {
  const params = new URLSearchParams();
  
  if (filters.type) params.set('type', filters.type);
  if (filters.status) params.set('status', filters.status);
  if (filters.search) params.set('search', filters.search);
  
  const queryString = params.toString();
  const endpoint = `/api/strategies${queryString ? '?' + queryString : ''}`;
  
  return apiFetch(endpoint);
}

/**
 * Fetch backtest results
 */
async function fetchBacktests(strategyId = null) {
  const endpoint = strategyId 
    ? `/api/backtests?strategy_id=${strategyId}`
    : '/api/backtests';
  
  return apiFetch(endpoint);
}

/**
 * Fetch market data (klines)
 */
async function fetchKlines(symbol, interval, limit = 500) {
  const endpoint = `/api/marketdata/bybit/klines/fetch?symbol=${symbol}&interval=${interval}&limit=${limit}`;
  return apiFetch(endpoint);
}

/**
 * Run a backtest
 */
async function runBacktest(strategyId, params) {
  return apiFetch(`/api/backtests/run-from-strategy/${strategyId}`, {
    method: 'POST',
    body: JSON.stringify(params)
  });
}


describe('API Integration', () => {
  
  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe('apiFetch', () => {
    it('should make GET request successfully', async () => {
      const mockData = { data: 'test' };
      
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockData)
      });
      
      const result = await apiFetch('/api/test');
      
      expect(fetch).toHaveBeenCalledWith(
        `${API_BASE}/api/test`,
        expect.objectContaining({
          headers: expect.objectContaining({
            'Content-Type': 'application/json'
          })
        })
      );
      expect(result).toEqual(mockData);
    });

    it('should throw error on failed request', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        json: () => Promise.resolve({ message: 'Not Found' })
      });
      
      await expect(apiFetch('/api/nonexistent')).rejects.toThrow('Not Found');
    });

    it('should handle network errors', async () => {
      global.fetch = vi.fn().mockRejectedValue(new Error('Network Error'));
      
      await expect(apiFetch('/api/test')).rejects.toThrow('Network Error');
    });

    it('should handle custom headers', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({})
      });
      
      await apiFetch('/api/test', {
        headers: { 'Authorization': 'Bearer token123' }
      });
      
      // Verify fetch was called
      expect(fetch).toHaveBeenCalled();
      
      // Get the actual call arguments
      const callArgs = fetch.mock.calls[0];
      expect(callArgs[0]).toBe(`${API_BASE}/api/test`);
      
      // The headers should include Authorization
      expect(callArgs[1].headers).toHaveProperty('Authorization', 'Bearer token123');
    });
  });

  describe('fetchStrategies', () => {
    it('should fetch all strategies', async () => {
      const mockStrategies = [
        testUtils.createMockStrategy({ name: 'Strategy 1' }),
        testUtils.createMockStrategy({ name: 'Strategy 2' })
      ];
      
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockStrategies)
      });
      
      const result = await fetchStrategies();
      
      expect(fetch).toHaveBeenCalledWith(
        `${API_BASE}/api/strategies`,
        expect.any(Object)
      );
      expect(result).toEqual(mockStrategies);
    });

    it('should apply filters correctly', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([])
      });
      
      await fetchStrategies({ type: 'sma_crossover', status: 'active' });
      
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('type=sma_crossover'),
        expect.any(Object)
      );
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('status=active'),
        expect.any(Object)
      );
    });

    it('should handle search parameter', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([])
      });
      
      await fetchStrategies({ search: 'bitcoin' });
      
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('search=bitcoin'),
        expect.any(Object)
      );
    });
  });

  describe('fetchBacktests', () => {
    it('should fetch all backtests', async () => {
      const mockBacktests = [testUtils.createMockBacktest()];
      
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockBacktests)
      });
      
      const result = await fetchBacktests();
      
      expect(fetch).toHaveBeenCalledWith(
        `${API_BASE}/api/backtests`,
        expect.any(Object)
      );
      expect(result).toEqual(mockBacktests);
    });

    it('should filter by strategy ID', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([])
      });
      
      await fetchBacktests('strategy-123');
      
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('strategy_id=strategy-123'),
        expect.any(Object)
      );
    });
  });

  describe('fetchKlines', () => {
    it('should fetch kline data correctly', async () => {
      const mockKlines = testUtils.createMockCandles(100);
      
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockKlines)
      });
      
      const result = await fetchKlines('BTCUSDT', '60', 100);
      
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('symbol=BTCUSDT'),
        expect.any(Object)
      );
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('interval=60'),
        expect.any(Object)
      );
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('limit=100'),
        expect.any(Object)
      );
    });

    it('should use default limit of 500', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([])
      });
      
      await fetchKlines('ETHUSDT', '15');
      
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('limit=500'),
        expect.any(Object)
      );
    });
  });

  describe('runBacktest', () => {
    it('should send POST request with parameters', async () => {
      const mockResult = testUtils.createMockBacktest();
      const params = {
        start_date: '2024-01-01',
        end_date: '2024-06-01',
        initial_capital: 10000
      };
      
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResult)
      });
      
      const result = await runBacktest('strategy-123', params);
      
      expect(fetch).toHaveBeenCalledWith(
        `${API_BASE}/api/backtests/run-from-strategy/strategy-123`,
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(params)
        })
      );
      expect(result).toEqual(mockResult);
    });

    it('should handle backtest errors', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        json: () => Promise.resolve({ detail: 'Backtest failed: insufficient data' })
      });
      
      await expect(runBacktest('strategy-123', {})).rejects.toThrow('Backtest failed');
    });
  });

  describe('Error Handling', () => {
    it('should handle 400 Bad Request', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: () => Promise.resolve({ detail: 'Invalid parameters' })
      });
      
      await expect(apiFetch('/api/test')).rejects.toThrow('Invalid parameters');
    });

    it('should handle 401 Unauthorized', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: 'Unauthorized' })
      });
      
      await expect(apiFetch('/api/protected')).rejects.toThrow('Unauthorized');
    });

    it('should handle 500 Internal Server Error', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: () => Promise.reject() // Server might not return JSON
      });
      
      await expect(apiFetch('/api/broken')).rejects.toThrow();
    });

    it('should handle timeout', async () => {
      vi.useFakeTimers();
      
      global.fetch = vi.fn().mockImplementation(() => 
        new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Timeout')), 30000)
        )
      );
      
      const promise = apiFetch('/api/slow');
      vi.advanceTimersByTime(30000);
      
      await expect(promise).rejects.toThrow('Timeout');
      
      vi.useRealTimers();
    });
  });
});
