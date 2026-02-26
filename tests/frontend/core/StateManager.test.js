/**
 * StateManager Unit Tests
 *
 * Tests for frontend/js/core/StateManager.js
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { StateManager, createStore, getStore, initStore } from '../../js/core/StateManager.js';

describe('StateManager', () => {
  let store;

  beforeEach(() => {
    store = new StateManager({
      user: null,
      theme: 'dark',
      settings: {
        notifications: true,
        language: 'en'
      },
      market: {
        selectedSymbol: 'BTCUSDT',
        selectedTimeframe: '1h'
      }
    });
  });

  describe('get/set basic operations', () => {
    it('should get initial state', () => {
      expect(store.get('theme')).toBe('dark');
      expect(store.get('user')).toBeNull();
    });

    it('should get nested values', () => {
      expect(store.get('settings.notifications')).toBe(true);
      expect(store.get('settings.language')).toBe('en');
    });

    it('should get deeply nested values', () => {
      expect(store.get('market.selectedSymbol')).toBe('BTCUSDT');
      expect(store.get('market.selectedTimeframe')).toBe('1h');
    });

    it('should set basic values', () => {
      store.set('theme', 'light');
      expect(store.get('theme')).toBe('light');
    });

    it('should set nested values', () => {
      store.set('settings.language', 'ru');
      expect(store.get('settings.language')).toBe('ru');
    });

    it('should create nested structure if not exists', () => {
      store.set('user.name', 'John');
      expect(store.get('user.name')).toBe('John');
    });

    it('should return default value for non-existent path', () => {
      expect(store.get('nonexistent', 'default')).toBe('default');
    });

    it('should return entire state when no path provided', () => {
      const state = store.get();
      expect(state).toEqual({
        user: null,
        theme: 'dark',
        settings: {
          notifications: true,
          language: 'en'
        },
        market: {
          selectedSymbol: 'BTCUSDT',
          selectedTimeframe: '1h'
        }
      });
    });
  });

  describe('set with options', () => {
    it('should set value silently (no history)', () => {
      store.set('theme', 'light', { silent: true });
      expect(store.get('theme')).toBe('light');
      // History should not be updated
      expect(store._history.length).toBe(1); // Only initial state
    });

    it('should set value with custom action name', () => {
      store.set('theme', 'light', { action: 'CHANGE_THEME' });
      expect(store._history[store._historyIndex].action).toBe('CHANGE_THEME');
    });
  });

  describe('batch updates', () => {
    it('should update multiple values at once', () => {
      store.batch({
        'theme': 'light',
        'settings.language': 'ru'
      });

      expect(store.get('theme')).toBe('light');
      expect(store.get('settings.language')).toBe('ru');
    });

    it('should notify all updated paths', () => {
      const themeCallback = vitest.fn();
      const langCallback = vitest.fn();

      store.subscribe('theme', themeCallback);
      store.subscribe('settings.language', langCallback);

      store.batch({
        'theme': 'light',
        'settings.language': 'ru'
      });

      expect(themeCallback).toHaveBeenCalled();
      expect(langCallback).toHaveBeenCalled();
    });
  });

  describe('merge operation', () => {
    it('should merge object into existing state', () => {
      store.merge('settings', { sounds: false });

      expect(store.get('settings.notifications')).toBe(true);
      expect(store.get('settings.sounds')).toBe(false);
      expect(store.get('settings.language')).toBe('en');
    });

    it('should create object if not exists', () => {
      store.merge('user', { name: 'John', age: 30 });

      expect(store.get('user.name')).toBe('John');
      expect(store.get('user.age')).toBe(30);
    });
  });

  describe('delete operation', () => {
    it('should delete value from state', () => {
      store.delete('settings.notifications');
      expect(store.get('settings.notifications')).toBeUndefined();
    });

    it('should return this for chaining', () => {
      const result = store.delete('theme');
      expect(result).toBe(store);
    });
  });

  describe('subscriptions', () => {
    it('should notify subscriber on value change', () => {
      const callback = vitest.fn();
      store.subscribe('theme', callback);

      store.set('theme', 'light');

      expect(callback).toHaveBeenCalledTimes(1);
      expect(callback).toHaveBeenCalledWith('light', 'theme', 'dark');
    });

    it('should notify for nested path changes', () => {
      const callback = vitest.fn();
      store.subscribe('market.selectedSymbol', callback);

      store.set('market.selectedSymbol', 'ETHUSDT');

      expect(callback).toHaveBeenCalledTimes(1);
      expect(callback).toHaveBeenCalledWith('ETHUSDT', 'market.selectedSymbol', 'BTCUSDT');
    });

    it('should notify wildcard subscribers', () => {
      const callback = vitest.fn();
      store.subscribe('*', callback);

      store.set('theme', 'light');

      expect(callback).toHaveBeenCalledTimes(1);
    });

    it('should notify parent path listeners', () => {
      const parentCallback = vitest.fn();
      store.subscribe('market', parentCallback);

      store.set('market.selectedSymbol', 'ETHUSDT');

      expect(parentCallback).toHaveBeenCalled();
    });

    it('should unsubscribe correctly', () => {
      const callback = vitest.fn();
      const unsubscribe = store.subscribe('theme', callback);

      store.set('theme', 'light');
      unsubscribe();
      store.set('theme', 'dark');

      expect(callback).toHaveBeenCalledTimes(1);
    });

    it('should call immediately with current value if options.immediate', () => {
      const callback = vitest.fn();
      store.subscribe('theme', callback, { immediate: true });

      expect(callback).toHaveBeenCalledTimes(1);
      expect(callback).toHaveBeenCalledWith('dark', 'theme', undefined);
    });
  });

  describe('computed values', () => {
    it('should compute derived value', () => {
      const callback = vitest.fn();

      store.computed(
        ['settings.notifications', 'settings.sounds'],
        (notifications, sounds) => notifications && sounds,
        callback
      );

      expect(callback).toHaveBeenCalledTimes(1);
      expect(callback).toHaveBeenCalledWith(true); // notifications=true, sounds=undefined
    });

    it('should recompute when dependencies change', () => {
      const callback = vitest.fn();

      store.set('settings.sounds', true);
      store.computed(
        ['settings.notifications', 'settings.sounds'],
        (notifications, sounds) => notifications && sounds,
        callback
      );

      store.set('settings.notifications', false);

      expect(callback).toHaveBeenCalledTimes(2);
      expect(callback).toHaveBeenLastCalledWith(false);
    });
  });

  describe('history (undo/redo)', () => {
    it('should track history', () => {
      store.set('theme', 'light');
      store.set('theme', 'dark');

      expect(store._history.length).toBe(3); // Initial + 2 changes
      expect(store._historyIndex).toBe(2);
    });

    it('should undo correctly', () => {
      store.set('theme', 'light');
      store.undo();

      expect(store.get('theme')).toBe('dark');
    });

    it('should redo correctly', () => {
      store.set('theme', 'light');
      store.undo();
      store.redo();

      expect(store.get('theme')).toBe('light');
    });

    it('should not undo beyond initial state', () => {
      store.undo();
      store.undo();
      store.undo();

      expect(store._historyIndex).toBe(0);
    });

    it('should clear redo stack on new action', () => {
      store.set('theme', 'light');
      store.undo();
      store.set('theme', 'green');

      expect(store._history.length).toBe(3); // Initial, light, green
      expect(store.get('theme')).toBe('green');
    });

    it('should reset to initial state', () => {
      store.set('theme', 'light');
      store.set('settings.language', 'ru');
      store.reset();

      expect(store.get('theme')).toBe('dark');
      expect(store.get('settings.language')).toBe('en');
    });
  });

  describe('deep clone', () => {
    it('should return deep clone not reference', () => {
      const settings = store.get('settings');
      settings.notifications = false;

      expect(store.get('settings.notifications')).toBe(true);
    });

    it('should handle arrays correctly', () => {
      store.set('watchlist', ['BTCUSDT', 'ETHUSDT']);
      const watchlist = store.get('watchlist');
      watchlist.push('XRPUSDT');

      expect(store.get('watchlist')).toEqual(['BTCUSDT', 'ETHUSDT']);
    });

    it('should handle dates correctly', () => {
      const date = new Date('2026-02-26');
      store.set('lastUpdate', date);

      const retrieved = store.get('lastUpdate');
      expect(retrieved).toEqual(date);
      expect(retrieved).not.toBe(date);
    });
  });

  describe('getSnapshot', () => {
    it('should return snapshot of current state', () => {
      const snapshot = store.getSnapshot();

      expect(snapshot).toHaveProperty('state');
      expect(snapshot).toHaveProperty('historyLength');
      expect(snapshot).toHaveProperty('historyIndex');
      expect(snapshot).toHaveProperty('listeners');
    });
  });

  describe('method chaining', () => {
    it('should support chaining for set', () => {
      const result = store.set('theme', 'light').set('settings.language', 'ru');

      expect(result).toBe(store);
      expect(store.get('theme')).toBe('light');
      expect(store.get('settings.language')).toBe('ru');
    });

    it('should support chaining for delete', () => {
      const result = store.delete('theme').delete('user');

      expect(result).toBe(store);
      expect(store.get('theme')).toBeUndefined();
    });

    it('should support chaining for undo/redo', () => {
      store.set('theme', 'light');
      const result = store.undo().redo();

      expect(result).toBe(store);
      expect(store.get('theme')).toBe('light');
    });
  });
});

describe('createStore and getStore', () => {
  beforeEach(() => {
    // Reset singleton
    const module = await import('../../js/core/StateManager.js');
    module.storeInstance = null;
  });

  it('should create singleton store', () => {
    const store1 = createStore({ theme: 'dark' });
    const store2 = getStore();

    expect(store1).toBe(store2);
  });

  it('should return null if store not created', () => {
    const module = await import('../../js/core/StateManager.js');
    module.storeInstance = null;

    const store = getStore();
    expect(store).toBeNull();
  });
});

describe('initStore', () => {
  beforeEach(() => {
    // Reset singleton
    const module = await import('../../js/core/StateManager.js');
    module.storeInstance = null;

    // Clear localStorage
    localStorage.clear();
  });

  it('should initialize with default state', () => {
    const store = initStore();

    expect(store.get('ui.theme')).toBe('dark');
    expect(store.get('market.selectedSymbol')).toBe('BTCUSDT');
    expect(store.get('market.selectedTimeframe')).toBe('1h');
  });

  it('should merge custom state', () => {
    const store = initStore({
      user: { name: 'John' },
      ui: { theme: 'light' }
    });

    expect(store.get('user.name')).toBe('John');
    expect(store.get('ui.theme')).toBe('light');
    expect(store.get('ui.sidebarCollapsed')).toBe(false);
  });

  it('should persist to localStorage', () => {
    const store = initStore({}, { persist: true });
    store.set('ui.theme', 'light');

    const saved = localStorage.getItem('bybit_strategy_tester_state');
    expect(saved).toContain('light');
  });
});
