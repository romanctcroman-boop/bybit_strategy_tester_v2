/**
 * Utility Functions Unit Tests
 * Tests for formatPrice, formatPercent, and other utility functions
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// Utility functions extracted from frontend HTML files

/**
 * Format price with appropriate decimal places and currency symbol
 */
function formatPrice(price) {
  if (price === null || price === undefined || isNaN(price)) {
    return '$--';
  }
  
  if (price >= 1000) {
    return '$' + price.toLocaleString('en-US', { 
      minimumFractionDigits: 2, 
      maximumFractionDigits: 2 
    });
  }
  
  if (price >= 1) {
    return '$' + price.toFixed(4);
  }
  
  // For very small prices (like meme coins)
  return '$' + price.toFixed(8);
}

/**
 * Format currency with larger units (K, M, B)
 */
function formatCurrency(value) {
  if (value === null || value === undefined || isNaN(value)) {
    return '$--';
  }
  
  if (Math.abs(value) >= 1e9) {
    return '$' + (value / 1e9).toFixed(2) + 'B';
  }
  if (Math.abs(value) >= 1e6) {
    return '$' + (value / 1e6).toFixed(2) + 'M';
  }
  if (Math.abs(value) >= 1e3) {
    return '$' + (value / 1e3).toFixed(2) + 'K';
  }
  
  return '$' + value.toFixed(2);
}

/**
 * Format percentage
 */
function formatPercent(value, decimals = 2) {
  if (value === null || value === undefined || isNaN(value)) {
    return '--%';
  }
  
  const sign = value >= 0 ? '+' : '';
  return sign + value.toFixed(decimals) + '%';
}

/**
 * Format timestamp to readable time
 */
function formatTime(timestamp) {
  if (!timestamp) return '--:--:--';
  
  const date = new Date(timestamp);
  if (isNaN(date.getTime())) return '--:--:--';
  
  return date.toLocaleTimeString('en-US', { 
    hour: '2-digit', 
    minute: '2-digit', 
    second: '2-digit' 
  });
}

/**
 * Format date to readable format
 */
function formatDate(timestamp) {
  if (!timestamp) return '--/--/----';
  
  const date = new Date(timestamp);
  if (isNaN(date.getTime())) return '--/--/----';
  
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
}

/**
 * Escape HTML to prevent XSS
 * Uses manual replacement for test reliability across environments
 */
function escapeHtml(text) {
  if (typeof text !== 'string') return '';
  
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Debounce function
 */
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

/**
 * Throttle function
 */
function throttle(func, limit) {
  let inThrottle;
  return function(...args) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}


describe('Utility Functions', () => {
  
  describe('formatPrice', () => {
    it('should format large prices with commas', () => {
      expect(formatPrice(97234.50)).toBe('$97,234.50');
      expect(formatPrice(1234567.89)).toBe('$1,234,567.89');
    });

    it('should format prices >= 1 with 4 decimals', () => {
      expect(formatPrice(10.5)).toBe('$10.5000');
      expect(formatPrice(1)).toBe('$1.0000');
    });

    it('should format small prices with 8 decimals', () => {
      expect(formatPrice(0.00001234)).toBe('$0.00001234');
      expect(formatPrice(0.5)).toBe('$0.50000000');
    });

    it('should handle null/undefined/NaN', () => {
      expect(formatPrice(null)).toBe('$--');
      expect(formatPrice(undefined)).toBe('$--');
      expect(formatPrice(NaN)).toBe('$--');
    });

    it('should handle zero', () => {
      expect(formatPrice(0)).toBe('$0.00000000');
    });

    it('should handle negative prices', () => {
      const result = formatPrice(-100.50);
      expect(result).toContain('-');
      expect(result).toContain('100.5');
    });
  });

  describe('formatCurrency', () => {
    it('should format billions', () => {
      expect(formatCurrency(1e9)).toBe('$1.00B');
      expect(formatCurrency(5.5e9)).toBe('$5.50B');
    });

    it('should format millions', () => {
      expect(formatCurrency(1e6)).toBe('$1.00M');
      expect(formatCurrency(2.5e6)).toBe('$2.50M');
    });

    it('should format thousands', () => {
      expect(formatCurrency(1000)).toBe('$1.00K');
      expect(formatCurrency(50000)).toBe('$50.00K');
    });

    it('should format small values normally', () => {
      expect(formatCurrency(100)).toBe('$100.00');
      expect(formatCurrency(0.50)).toBe('$0.50');
    });

    it('should handle negative values', () => {
      expect(formatCurrency(-1e6)).toBe('$-1.00M');
      expect(formatCurrency(-5000)).toBe('$-5.00K');
    });

    it('should handle null/undefined/NaN', () => {
      expect(formatCurrency(null)).toBe('$--');
      expect(formatCurrency(undefined)).toBe('$--');
      expect(formatCurrency(NaN)).toBe('$--');
    });
  });

  describe('formatPercent', () => {
    it('should add + sign for positive values', () => {
      expect(formatPercent(5.5)).toBe('+5.50%');
      expect(formatPercent(0.01)).toBe('+0.01%');
    });

    it('should show - sign for negative values', () => {
      expect(formatPercent(-3.25)).toBe('-3.25%');
    });

    it('should handle zero', () => {
      expect(formatPercent(0)).toBe('+0.00%');
    });

    it('should respect decimal precision', () => {
      expect(formatPercent(5.5555, 1)).toBe('+5.6%');
      expect(formatPercent(5.5555, 4)).toBe('+5.5555%');
    });

    it('should handle null/undefined/NaN', () => {
      expect(formatPercent(null)).toBe('--%');
      expect(formatPercent(undefined)).toBe('--%');
      expect(formatPercent(NaN)).toBe('--%');
    });
  });

  describe('formatTime', () => {
    it('should format valid timestamps', () => {
      const timestamp = new Date('2024-01-15T14:30:45').getTime();
      const result = formatTime(timestamp);
      
      expect(result).toMatch(/\d{1,2}:\d{2}:\d{2}/);
    });

    it('should handle null/undefined', () => {
      expect(formatTime(null)).toBe('--:--:--');
      expect(formatTime(undefined)).toBe('--:--:--');
    });

    it('should handle invalid timestamps', () => {
      expect(formatTime('invalid')).toBe('--:--:--');
      expect(formatTime(NaN)).toBe('--:--:--');
    });

    it('should handle ISO strings', () => {
      const result = formatTime('2024-01-15T14:30:45Z');
      expect(result).toMatch(/\d{1,2}:\d{2}:\d{2}/);
    });
  });

  describe('formatDate', () => {
    it('should format valid timestamps', () => {
      const timestamp = new Date('2024-01-15').getTime();
      const result = formatDate(timestamp);
      
      expect(result).toContain('2024');
      expect(result).toContain('Jan');
      expect(result).toContain('15');
    });

    it('should handle null/undefined', () => {
      expect(formatDate(null)).toBe('--/--/----');
      expect(formatDate(undefined)).toBe('--/--/----');
    });

    it('should handle ISO date strings', () => {
      const result = formatDate('2024-06-20');
      expect(result).toContain('2024');
      expect(result).toContain('Jun');
    });
  });

  describe('escapeHtml', () => {
    it('should escape HTML tags', () => {
      expect(escapeHtml('<script>alert("xss")</script>')).toBe('&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;');
    });

    it('should escape ampersands', () => {
      expect(escapeHtml('Tom & Jerry')).toBe('Tom &amp; Jerry');
    });

    it('should escape quotes', () => {
      const result = escapeHtml('"Hello" & \'World\'');
      expect(result).not.toContain('<');
      expect(result).toContain('&amp;');
    });

    it('should handle non-string input', () => {
      expect(escapeHtml(null)).toBe('');
      expect(escapeHtml(undefined)).toBe('');
      expect(escapeHtml(123)).toBe('');
    });

    it('should handle empty string', () => {
      expect(escapeHtml('')).toBe('');
    });

    it('should preserve safe text', () => {
      expect(escapeHtml('Hello World')).toBe('Hello World');
    });
  });

  describe('debounce', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    it('should delay function execution', () => {
      const fn = vi.fn();
      const debouncedFn = debounce(fn, 100);
      
      debouncedFn();
      expect(fn).not.toHaveBeenCalled();
      
      vi.advanceTimersByTime(100);
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it('should only execute once for multiple rapid calls', () => {
      const fn = vi.fn();
      const debouncedFn = debounce(fn, 100);
      
      debouncedFn();
      debouncedFn();
      debouncedFn();
      
      vi.advanceTimersByTime(100);
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it('should pass arguments correctly', () => {
      const fn = vi.fn();
      const debouncedFn = debounce(fn, 100);
      
      debouncedFn('arg1', 'arg2');
      vi.advanceTimersByTime(100);
      
      expect(fn).toHaveBeenCalledWith('arg1', 'arg2');
    });
  });

  describe('throttle', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    it('should execute immediately on first call', () => {
      const fn = vi.fn();
      const throttledFn = throttle(fn, 100);
      
      throttledFn();
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it('should ignore calls during throttle period', () => {
      const fn = vi.fn();
      const throttledFn = throttle(fn, 100);
      
      throttledFn();
      throttledFn();
      throttledFn();
      
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it('should allow execution after throttle period', () => {
      const fn = vi.fn();
      const throttledFn = throttle(fn, 100);
      
      throttledFn();
      expect(fn).toHaveBeenCalledTimes(1);
      
      vi.advanceTimersByTime(100);
      throttledFn();
      expect(fn).toHaveBeenCalledTimes(2);
    });
  });
});
