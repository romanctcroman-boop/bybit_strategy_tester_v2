/**
 * Zustand Persistence Configuration
 *
 * Quick Win #5: Добавляем persist middleware для сохранения состояния
 * между перезагрузками страницы
 */

/**
 * 🎯 QUICK WIN #5: Zustand Persistence
 * Note: Используем default localStorage (zustand автоматически обрабатывает ошибки)
 *
 * Migrations between versions
 * Используется при изменении схемы данных
 */
export const migrations = {
  // Example: Migration from v0 to v1
  1: (state: any) => {
    console.log('📦 Применяем миграцию persist v0 → v1');
    return {
      ...state,
      // Add migration logic here if schema changes
    };
  },
};

/**
 * 🎯 QUICK WIN #5: Persist configurations for different stores
 */

// Backtests Store - сохраняем пагинацию и фильтры
export const backtestsPersistConfig = {
  name: 'backtests-storage',
  version: 1,
  // storage: default localStorage (zustand handles errors)
  partialize: (state: any) => ({
    // ✅ Сохраняем пагинацию
    limit: state.limit,
    offset: state.offset,
    // ✅ Сохраняем фильтры trades
    tradeSide: state.tradeSide,
    tradesLimit: state.tradesLimit,
    tradesOffset: state.tradesOffset,
    // ❌ НЕ сохраняем (временные данные)
    // items, trades, loading, error
  }),
  onRehydrateStorage: () => (state: any, error: any) => {
    if (error) {
      console.error('❌ Ошибка восстановления backtests store:', error);
    } else {
      console.log('✅ Backtests store восстановлен из localStorage');
    }
  },
};

// Strategies Store - сохраняем фильтры и пагинацию
export const strategiesPersistConfig = {
  name: 'strategies-storage',
  version: 1,
  // storage: default localStorage
  partialize: (state: any) => ({
    limit: state.limit,
    offset: state.offset,
  }),
  onRehydrateStorage: () => (state: any, error: any) => {
    if (error) {
      console.error('❌ Ошибка восстановления strategies store:', error);
    } else {
      console.log('✅ Strategies store восстановлен из localStorage');
    }
  },
};

// Optimizations Store - сохраняем настройки
export const optimizationsPersistConfig = {
  name: 'optimizations-storage',
  version: 1,
  // storage: default localStorage
  partialize: (state: any) => ({
    limit: state.limit,
    offset: state.offset,
  }),
  onRehydrateStorage: () => (state: any, error: any) => {
    if (error) {
      console.error('❌ Ошибка восстановления optimizations store:', error);
    } else {
      console.log('✅ Optimizations store восстановлен из localStorage');
    }
  },
};

// Bots Store - сохраняем фильтры
export const botsPersistConfig = {
  name: 'bots-storage',
  version: 1,
  // storage: default localStorage
  partialize: (state: any) => ({
    limit: state.limit,
    offset: state.offset,
    statusFilter: state.statusFilter, // Если есть фильтр по статусу
  }),
  onRehydrateStorage: () => (state: any, error: any) => {
    if (error) {
      console.error('❌ Ошибка восстановления bots store:', error);
    } else {
      console.log('✅ Bots store восстановлен из localStorage');
    }
  },
};

/**
 * Utility для очистки всех persist stores (для разработки/тестирования)
 */
export const clearAllPersistedStores = () => {
  const storageKeys = [
    'backtests-storage',
    'strategies-storage',
    'optimizations-storage',
    'bots-storage',
  ];

  storageKeys.forEach((key) => {
    try {
      localStorage.removeItem(key);
      console.log(`🗑️ Cleared ${key}`);
    } catch (error) {
      console.warn(`❌ Failed to clear ${key}:`, error);
    }
  });

  console.log('✅ All persisted stores cleared');
};

// Expose to window for debugging
if (typeof window !== 'undefined') {
  (window as any).clearAllPersistedStores = clearAllPersistedStores;
}
