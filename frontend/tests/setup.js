/**
 * Vitest Setup File
 * Global test configuration and utilities
 */

import { expect, afterEach, vi } from 'vitest';
import '@testing-library/jest-dom';

// Mock localStorage
const localStorageMock = {
  store: {},
  getItem: vi.fn((key) => localStorageMock.store[key] || null),
  setItem: vi.fn((key, value) => { localStorageMock.store[key] = value.toString(); }),
  removeItem: vi.fn((key) => { delete localStorageMock.store[key]; }),
  clear: vi.fn(() => { localStorageMock.store = {}; })
};
global.localStorage = localStorageMock;

// Mock sessionStorage
const sessionStorageMock = {
  store: {},
  getItem: vi.fn((key) => sessionStorageMock.store[key] || null),
  setItem: vi.fn((key, value) => { sessionStorageMock.store[key] = value.toString(); }),
  removeItem: vi.fn((key) => { delete sessionStorageMock.store[key]; }),
  clear: vi.fn(() => { sessionStorageMock.store = {}; })
};
global.sessionStorage = sessionStorageMock;

// Mock fetch API
global.fetch = vi.fn();

// Mock WebSocket
global.WebSocket = vi.fn(() => ({
  onopen: null,
  onmessage: null,
  onerror: null,
  onclose: null,
  send: vi.fn(),
  close: vi.fn(),
  readyState: 1 // OPEN
}));

// Mock requestAnimationFrame
global.requestAnimationFrame = vi.fn((cb) => setTimeout(cb, 16));
global.cancelAnimationFrame = vi.fn((id) => clearTimeout(id));

// Mock ResizeObserver
global.ResizeObserver = vi.fn(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn()
}));

// Mock IntersectionObserver
global.IntersectionObserver = vi.fn(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn()
}));

// Clean up after each test
afterEach(() => {
  vi.clearAllMocks();
  localStorageMock.clear();
  sessionStorageMock.clear();
  document.body.innerHTML = '';
});

// Custom matchers
expect.extend({
  toBeValidPrice(received) {
    const pass = typeof received === 'number' && !isNaN(received) && received >= 0;
    return {
      pass,
      message: () => `expected ${received} ${pass ? 'not ' : ''}to be a valid price`
    };
  },
  
  toBeValidPercentage(received) {
    const pass = typeof received === 'number' && !isNaN(received) && received >= -100 && received <= 1000;
    return {
      pass,
      message: () => `expected ${received} ${pass ? 'not ' : ''}to be a valid percentage`
    };
  }
});

// Global test utilities
global.testUtils = {
  /**
   * Create mock OHLCV candle data
   */
  createMockCandles(count = 100, startPrice = 50000) {
    const candles = [];
    let price = startPrice;
    const now = Math.floor(Date.now() / 1000);
    const interval = 3600; // 1 hour
    
    for (let i = count; i >= 0; i--) {
      const change = (Math.random() - 0.5) * 1000;
      const open = price;
      const close = price + change;
      const high = Math.max(open, close) + Math.random() * 200;
      const low = Math.min(open, close) - Math.random() * 200;
      const volume = Math.random() * 1000 + 500;
      
      candles.push({
        time: now - i * interval,
        open,
        high,
        low,
        close,
        volume
      });
      
      price = close;
    }
    
    return candles;
  },
  
  /**
   * Create mock order book data
   */
  createMockOrderBook(midPrice = 50000, depth = 10) {
    const asks = [];
    const bids = [];
    
    for (let i = 0; i < depth; i++) {
      asks.push({
        price: midPrice + (i + 1) * 10,
        size: Math.random() * 10,
        total: (i + 1) * Math.random() * 10
      });
      bids.push({
        price: midPrice - (i + 1) * 10,
        size: Math.random() * 10,
        total: (i + 1) * Math.random() * 10
      });
    }
    
    return { asks: asks.reverse(), bids };
  },
  
  /**
   * Create mock strategy data
   */
  createMockStrategy(overrides = {}) {
    return {
      id: Math.random().toString(36).substr(2, 9),
      name: 'Test Strategy',
      type: 'sma_crossover',
      status: 'active',
      parameters: {
        fast_period: 10,
        slow_period: 20
      },
      performance: {
        total_return: 15.5,
        sharpe_ratio: 1.8,
        max_drawdown: -12.3
      },
      created_at: new Date().toISOString(),
      ...overrides
    };
  },
  
  /**
   * Create mock backtest result
   */
  createMockBacktest(overrides = {}) {
    return {
      id: Math.random().toString(36).substr(2, 9),
      strategy_id: 'test-strategy',
      status: 'completed',
      metrics: {
        total_return: 25.5,
        win_rate: 62.5,
        sharpe_ratio: 2.1,
        max_drawdown: -8.5,
        total_trades: 150,
        avg_trade_duration: '4h 30m'
      },
      equity_curve: testUtils.createMockCandles(50, 10000).map(c => ({
        time: c.time,
        value: c.close
      })),
      trades: [],
      created_at: new Date().toISOString(),
      ...overrides
    };
  },
  
  /**
   * Wait for async operations
   */
  async waitFor(ms = 100) {
    return new Promise(resolve => setTimeout(resolve, ms));
  },
  
  /**
   * Mock successful API response
   */
  mockApiSuccess(data) {
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve(data),
      text: () => Promise.resolve(JSON.stringify(data))
    });
  },
  
  /**
   * Mock failed API response
   */
  mockApiError(status = 500, message = 'Internal Server Error') {
    return Promise.resolve({
      ok: false,
      status,
      json: () => Promise.resolve({ error: message }),
      text: () => Promise.resolve(message)
    });
  }
};

console.log('✓ Vitest setup complete');
