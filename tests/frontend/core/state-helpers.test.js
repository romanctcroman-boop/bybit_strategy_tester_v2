/**
 * State Helpers Unit Tests
 *
 * Tests for frontend/js/core/state-helpers.js
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { StateManager } from '../../js/core/StateManager.js';
import {
  bindToState,
  bindInputToState,
  bindCheckboxToState,
  bindSelectToState,
  withStateUpdate,
  createComputed,
  clearState,
  initState,
  getStateSlice,
  createLoggingMiddleware
} from '../../js/core/state-helpers.js';

// Mock DOM elements
function createMockElement(tag = 'div', properties = {}) {
  const element = {
    tagName: tag.toUpperCase(),
    ...properties,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    querySelector: vi.fn()
  };
  return element;
}

describe('state-helpers', () => {
  let store;
  let mockElement;

  beforeEach(() => {
    // Create fresh store for each test
    store = new StateManager({
      theme: 'dark',
      count: 0,
      enabled: true,
      user: {
        name: 'John',
        age: 30
      },
      settings: {
        language: 'en',
        notifications: true
      }
    });

    // Mock global getStore
    vi.mock('../../js/core/StateManager.js', () => ({
      getStore: () => store
    }));

    mockElement = createMockElement('div', {
      textContent: '',
      value: '',
      checked: false
    });
  });

  describe('bindToState', () => {
    it('should bind element textContent to state', () => {
      document.querySelector = vi.fn().mockReturnValue(mockElement);

      const unsubscribe = bindToState('#test', 'theme');

      expect(mockElement.textContent).toBe('dark');
      expect(document.querySelector).toHaveBeenCalledWith('#test');

      // Update state
      store.set('theme', 'light');
      expect(mockElement.textContent).toBe('light');

      unsubscribe();
    });

    it('should use custom property', () => {
      document.querySelector = vi.fn().mockReturnValue(mockElement);

      bindToState('#test', 'theme', 'value');

      expect(mockElement.value).toBe('dark');
    });

    it('should apply transform function', () => {
      document.querySelector = vi.fn().mockReturnValue(mockElement);

      bindToState('#test', 'count', 'textContent', (val) => `Count: ${val}`);

      expect(mockElement.textContent).toBe('Count: 0');

      store.set('count', 5);
      expect(mockElement.textContent).toBe('Count: 5');
    });

    it('should return unsubscribe function', () => {
      document.querySelector = vi.fn().mockReturnValue(mockElement);

      const unsubscribe = bindToState('#test', 'theme');

      store.set('theme', 'light');
      expect(mockElement.textContent).toBe('light');

      unsubscribe();

      store.set('theme', 'dark');
      // Should not update after unsubscribe
      expect(mockElement.textContent).toBe('light');
    });

    it('should warn if store not initialized', () => {
      const consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => {});
      vi.mocked(getStore).mockReturnValue(null);

      const result = bindToState('#test', 'theme');

      expect(consoleWarn).toHaveBeenCalledWith('[bindToState] Store not initialized');
      expect(result).toBeNull();

      consoleWarn.mockRestore();
    });

    it('should warn if element not found', () => {
      const consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => {});
      document.querySelector = vi.fn().mockReturnValue(null);

      const result = bindToState('#nonexistent', 'theme');

      expect(consoleWarn).toHaveBeenCalledWith('[bindToState] Element not found: #nonexistent');
      expect(result).toBeNull();

      consoleWarn.mockRestore();
    });
  });

  describe('bindInputToState', () => {
    it('should bind input value to state', () => {
      document.querySelector = vi.fn().mockReturnValue(mockElement);

      bindInputToState('#test', 'theme');

      expect(mockElement.value).toBe('dark');

      store.set('theme', 'light');
      expect(mockElement.value).toBe('light');
    });

    it('should update state on input change', () => {
      document.querySelector = vi.fn().mockReturnValue(mockElement);

      bindInputToState('#test', 'theme');

      // Simulate input event
      const inputHandler = mockElement.addEventListener.mock.calls.find(
        call => call[0] === 'input'
      )[1];

      inputHandler({ target: { value: 'light' } });

      expect(store.get('theme')).toBe('light');
    });

    it('should not update DOM when element has focus', () => {
      document.querySelector = vi.fn().mockReturnValue(mockElement);
      document.activeElement = mockElement;

      bindInputToState('#test', 'theme');

      store.set('theme', 'light');
      // Should not update value when element has focus
      expect(mockElement.value).toBe('dark');
    });

    it('should apply transformers', () => {
      document.querySelector = vi.fn().mockReturnValue(mockElement);

      bindInputToState('#test', 'count', {
        transformOnGet: true,
        getTransformer: (val) => `Count: ${val}`,
        transformOnSet: true,
        setTransformer: (val) => parseInt(val)
      });

      expect(mockElement.value).toBe('Count: 0');

      const inputHandler = mockElement.addEventListener.mock.calls.find(
        call => call[0] === 'input'
      )[1];

      inputHandler({ target: { value: '5' } });
      expect(store.get('count')).toBe(5);
    });
  });

  describe('bindCheckboxToState', () => {
    it('should bind checkbox checked state', () => {
      document.querySelector = vi.fn().mockReturnValue(mockElement);

      bindCheckboxToState('#test', 'enabled');

      expect(mockElement.checked).toBe(true);

      store.set('enabled', false);
      expect(mockElement.checked).toBe(false);
    });

    it('should update state on checkbox change', () => {
      document.querySelector = vi.fn().mockReturnValue(mockElement);

      bindCheckboxToState('#test', 'enabled');

      mockElement.checked = false;
      const changeHandler = mockElement.addEventListener.mock.calls.find(
        call => call[0] === 'change'
      )[1];

      changeHandler();

      expect(store.get('enabled')).toBe(false);
    });
  });

  describe('bindSelectToState', () => {
    it('should bind select element', () => {
      document.querySelector = vi.fn().mockReturnValue(mockElement);

      bindSelectToState('#test', 'settings.language');

      expect(mockElement.value).toBe('en');

      store.set('settings.language', 'ru');
      expect(mockElement.value).toBe('ru');
    });
  });

  describe('withStateUpdate', () => {
    it('should wrap handler with state update', () => {
      const handler = vi.fn();
      const wrapped = withStateUpdate(handler, 'count');

      const mockEvent = {
        target: { value: 5 }
      };

      wrapped(mockEvent);

      expect(handler).toHaveBeenCalledWith(mockEvent);
      expect(store.get('count')).toBe(5);
    });

    it('should use valueMapper if provided', () => {
      const handler = vi.fn();
      const wrapped = withStateUpdate(
        handler,
        'count',
        (event) => event.target.value * 2
      );

      const mockEvent = {
        target: { value: 5 }
      };

      wrapped(mockEvent);

      expect(store.get('count')).toBe(10);
    });
  });

  describe('createComputed', () => {
    it('should compute derived value', () => {
      const callback = vi.fn();

      createComputed(
        ['user.age', 'count'],
        (age, count) => age + count,
        'user.total'
      );

      expect(store.get('user.total')).toBe(30);

      store.set('count', 5);
      expect(store.get('user.total')).toBe(35);
    });

    it('should return unsubscribe function', () => {
      const unsubscribe = createComputed(
        ['user.age', 'count'],
        (age, count) => age + count,
        'user.total'
      );

      expect(typeof unsubscribe).toBe('function');
    });
  });

  describe('clearState', () => {
    it('should delete value from state', () => {
      clearState('theme');

      expect(store.get('theme')).toBeUndefined();
    });
  });

  describe('initState', () => {
    it('should initialize if value does not exist', () => {
      initState('newKey', 'newValue');

      expect(store.get('newKey')).toBe('newValue');
    });

    it('should not overwrite existing value', () => {
      initState('theme', 'light');

      expect(store.get('theme')).toBe('dark');
    });
  });

  describe('getStateSlice', () => {
    it('should return object with values for paths', () => {
      const slice = getStateSlice(['theme', 'count', 'user.name']);

      expect(slice).toEqual({
        theme: 'dark',
        count: 0,
        'user.name': 'John'
      });
    });
  });

  describe('createLoggingMiddleware', () => {
    it('should log state changes in dev mode', () => {
      const consoleLog = vi.spyOn(console, 'log').mockImplementation(() => {});
      global.window = { __DEV__: true };

      const middleware = createLoggingMiddleware('[Test]');
      middleware({
        type: 'SET',
        path: 'theme',
        value: 'light',
        prevValue: 'dark'
      });

      expect(consoleLog).toHaveBeenCalledWith(
        '[Test] SET',
        expect.objectContaining({
          path: 'theme',
          value: 'light',
          prevValue: 'dark'
        })
      );

      consoleLog.mockRestore();
      delete global.window;
    });

    it('should not log in production mode', () => {
      const consoleLog = vi.spyOn(console, 'log').mockImplementation(() => {});
      global.window = { __DEV__: false };

      const middleware = createLoggingMiddleware('[Test]');
      middleware({
        type: 'SET',
        path: 'theme',
        value: 'light',
        prevValue: 'dark'
      });

      expect(consoleLog).not.toHaveBeenCalled();

      consoleLog.mockRestore();
      delete global.window;
    });
  });
});
