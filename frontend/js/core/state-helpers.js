/**
 * 🛠️ State Helpers - Bybit Strategy Tester v2
 *
 * Helper functions for StateManager integration
 *
 * @version 1.0.0
 * @date 2026-02-26
 */

import { getStore } from './StateManager.js';

/**
 * Создать привязку DOM элемента к пути в state
 * @param {string} selector - CSS селектор
 * @param {string} statePath - Путь в state
 * @param {string} property - DOM свойство ('textContent', 'value', 'checked')
 * @param {Function} [transform] - Функция трансформации значения
 */
export function bindToState(selector, statePath, property = 'textContent', transform = null) {
  const store = getStore();
  if (!store) {
    console.warn('[bindToState] Store not initialized');
    return null;
  }

  const element = document.querySelector(selector);
  if (!element) {
    console.warn(`[bindToState] Element not found: ${selector}`);
    return null;
  }

  // Initial value
  const initialValue = store.get(statePath);
  if (initialValue !== undefined) {
    const value = transform ? transform(initialValue) : initialValue;
    element[property] = value;
  }

  // Subscribe to changes
  const unsubscribe = store.subscribe(statePath, (value) => {
    const transformedValue = transform ? transform(value) : value;
    if (element[property] !== transformedValue) {
      element[property] = transformedValue;
    }
  });

  return unsubscribe;
}

/**
 * Создать двустороннюю привязку для input элементов
 * @param {string} selector - CSS селектор
 * @param {string} statePath - Путь в state
 * @param {Object} options - Опции
 * @param {boolean} [options.transformOnGet] - Трансформировать при чтении из state
 * @param {boolean} [options.transformOnSet] - Трансформировать при записи в state
 * @param {Function} [options.getTransformer] - Функция трансформации при чтении
 * @param {Function} [options.setTransformer] - Функция трансформации при записи
 */
export function bindInputToState(
  selector,
  statePath,
  options = {}
) {
  const store = getStore();
  if (!store) {
    console.warn('[bindInputToState] Store not initialized');
    return null;
  }

  const element = document.querySelector(selector);
  if (!element) {
    console.warn(`[bindInputToState] Element not found: ${selector}`);
    return null;
  }

  const {
    transformOnGet = false,
    transformOnSet = false,
    getTransformer = (v) => v,
    setTransformer = (v) => v
  } = options;

  // Initial value
  const initialValue = store.get(statePath);
  if (initialValue !== undefined) {
    element.value = transformOnGet ? getTransformer(initialValue) : initialValue;
  }

  // Subscribe to state changes
  const unsubscribe = store.subscribe(statePath, (value) => {
    // Don't update if element has focus (user is typing)
    if (document.activeElement !== element) {
      element.value = transformOnGet ? getTransformer(value) : value;
    }
  });

  // Update state on input change
  const handleChange = (e) => {
    const newValue = transformOnSet ? setTransformer(e.target.value) : e.target.value;
    store.set(statePath, newValue);
  };

  element.addEventListener('input', handleChange);
  element.addEventListener('change', handleChange);

  // Return unsubscribe function
  return () => {
    unsubscribe();
    element.removeEventListener('input', handleChange);
    element.removeEventListener('change', handleChange);
  };
}

/**
 * Создать привязку для checkbox элементов
 * @param {string} selector - CSS селектор
 * @param {string} statePath - Путь в state
 */
export function bindCheckboxToState(selector, statePath) {
  const store = getStore();
  if (!store) {
    console.warn('[bindCheckboxToState] Store not initialized');
    return null;
  }

  const element = document.querySelector(selector);
  if (!element) {
    console.warn(`[bindCheckboxToState] Element not found: ${selector}`);
    return null;
  }

  // Initial value
  const initialValue = store.get(statePath);
  if (initialValue !== undefined) {
    element.checked = Boolean(initialValue);
  }

  // Subscribe to changes
  const unsubscribe = store.subscribe(statePath, (value) => {
    if (element.checked !== Boolean(value)) {
      element.checked = Boolean(value);
    }
  });

  // Update state on change
  const handleChange = () => {
    store.set(statePath, element.checked);
  };

  element.addEventListener('change', handleChange);

  // Return unsubscribe function
  return () => {
    unsubscribe();
    element.removeEventListener('change', handleChange);
  };
}

/**
 * Создать привязку для select элементов
 * @param {string} selector - CSS селектор
 * @param {string} statePath - Путь в state
 */
export function bindSelectToState(selector, statePath) {
  return bindInputToState(selector, statePath);
}

/**
 * Обернуть обработчик события с обновлением state
 * @param {Function} handler - Обработчик события
 * @param {string} statePath - Путь для обновления
 * @param {Function} [valueMapper] - Функция маппинга значения
 */
export function withStateUpdate(handler, statePath, valueMapper = null) {
  const store = getStore();
  if (!store) {
    console.warn('[withStateUpdate] Store not initialized');
    return handler;
  }

  return function (event) {
    // Call original handler
    const result = handler.call(this, event);

    // Update state
    const value = valueMapper ? valueMapper(event) : event.target?.value;
    if (value !== undefined) {
      store.set(statePath, value);
    }

    return result;
  };
}

/**
 * Создать computed значение
 * @param {string[]} dependencies - Зависимые пути
 * @param {Function} computeFn - Функция вычисления
 * @param {string} targetPath - Путь для сохранения результата
 */
export function createComputed(dependencies, computeFn, targetPath) {
  const store = getStore();
  if (!store) {
    console.warn('[createComputed] Store not initialized');
    return null;
  }

  const update = () => {
    const values = dependencies.map(dep => store.get(dep));
    const result = computeFn(...values);
    store.set(targetPath, result);
  };

  // Initial compute
  update();

  // Subscribe to all dependencies
  const unsubscribers = dependencies.map(dep => store.subscribe(dep, update));

  // Return unsubscribe function
  return () => {
    unsubscribers.forEach(unsub => unsub());
  };
}

/**
 * Удалить значение из state
 * @param {string} path - Путь
 */
export function clearState(path) {
  const store = getStore();
  if (!store) {
    console.warn('[clearState] Store not initialized');
    return;
  }
  store.delete(path);
}

/**
 * Инициализировать state значением если оно не существует
 * @param {string} path - Путь
 * @param {*} defaultValue - Значение по умолчанию
 */
export function initState(path, defaultValue) {
  const store = getStore();
  if (!store) {
    console.warn('[initState] Store not initialized');
    return;
  }

  const currentValue = store.get(path);
  if (currentValue === undefined) {
    store.set(path, defaultValue);
  }
}

/**
 * Получить срез state по путям
 * @param {string[]} paths - Пути
 * @returns {Object} Объект с значениями
 */
export function getStateSlice(paths) {
  const store = getStore();
  if (!store) {
    console.warn('[getStateSlice] Store not initialized');
    return {};
  }

  const result = {};
  for (const path of paths) {
    result[path] = store.get(path);
  }
  return result;
}

/**
 * Создать middleware для логирования изменений
 * @param {string} prefix - Префикс для логов
 */
export function createLoggingMiddleware(prefix = '[State]') {
  return function (action) {
    if (typeof window !== 'undefined' && window.__DEV__) {
      console.log(`${prefix} ${action.type}`, {
        path: action.path,
        from: action.prevValue,
        to: action.value
      });
    }
    return action.value;
  };
}

export default {
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
};
