/**
 * 🧪 Тестовый скрипт для проверки работы с localStorage
 *
 * Использование: Скопируйте этот код в консоль браузера (F12)
 */

// Утилиты для тестирования
const TestUtils = {
  // Очистить ВСЮ базу данных
  clearAllStorage() {
    console.log('🗑️ Очистка ВСЕЙ базы данных...');
    let count = 0;
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const key = localStorage.key(i);
      if (key && key.startsWith('bybit_candles_')) {
        localStorage.removeItem(key);
        count++;
      }
    }
    console.log(`✅ Удалено ${count} записей из localStorage`);
  },

  // Очистить конкретную пару
  clearSymbol(symbol, interval, category = 'linear') {
    const key = `bybit_candles_v1_${category}_${symbol.toUpperCase()}_${interval}`;
    console.log(`🗑️ Очистка ${key}...`);
    localStorage.removeItem(key);
    console.log('✅ Удалено');
  },

  // Частично очистить базу (удалить последние N свечей)
  partialClear(symbol, interval, removeCount = 500, category = 'linear') {
    const key = `bybit_candles_v1_${category}_${symbol.toUpperCase()}_${interval}`;
    console.log(`📊 Частичная очистка ${key}: удаление последних ${removeCount} свечей...`);

    const raw = localStorage.getItem(key);
    if (!raw) {
      console.log('⚠️ Данные не найдены');
      return;
    }

    const data = JSON.parse(raw);
    const oldCount = data.candles.length;
    data.candles = data.candles.slice(0, -removeCount);
    data.timestamp = Date.now();

    localStorage.setItem(key, JSON.stringify(data));
    console.log(`✅ Было: ${oldCount}, стало: ${data.candles.length}`);
  },

  // Показать статистику по всем данным
  showStats() {
    console.log('📊 Статистика localStorage:');
    console.log('═══════════════════════════════════════════════');

    let totalCandles = 0;
    let totalSize = 0;

    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith('bybit_candles_')) {
        const raw = localStorage.getItem(key);
        const size = new Blob([raw]).size;
        const data = JSON.parse(raw);
        const candleCount = data.candles.length;

        totalCandles += candleCount;
        totalSize += size;

        const parts = key.split('_');
        const symbol = parts[3];
        const interval = parts[4];
        const oldest = data.candles[0];
        const newest = data.candles[candleCount - 1];

        console.log(`\n📈 ${symbol} ${interval}:`);
        console.log(`   Свечей: ${candleCount}`);
        console.log(`   Размер: ${(size / 1024).toFixed(2)} KB`);
        console.log(
          `   Период: ${new Date(oldest.time * 1000).toISOString()} - ${new Date(newest.time * 1000).toISOString()}`
        );
      }
    }

    console.log('\n═══════════════════════════════════════════════');
    console.log(`📊 Всего свечей: ${totalCandles}`);
    console.log(`💾 Общий размер: ${(totalSize / 1024).toFixed(2)} KB`);
    console.log(`📦 Записей: ${localStorage.length}`);
  },

  // Создать фейковый кэш для тестирования
  createFakeCache(symbol, interval, count = 500, category = 'linear') {
    console.log(`🎭 Создание фейкового кэша: ${symbol} ${interval}, ${count} свечей...`);

    const now = Math.floor(Date.now() / 1000);
    const intervalSec = interval === 'D' ? 86400 : parseInt(interval) * 60;

    const candles = [];
    let price = 50000;

    for (let i = count - 1; i >= 0; i--) {
      const time = now - i * intervalSec;
      const change = (Math.random() - 0.5) * 200;
      price += change;

      const open = price;
      const close = price + (Math.random() - 0.5) * 100;
      const high = Math.max(open, close) + Math.random() * 50;
      const low = Math.min(open, close) - Math.random() * 50;

      candles.push({
        time,
        open: parseFloat(open.toFixed(2)),
        high: parseFloat(high.toFixed(2)),
        low: parseFloat(low.toFixed(2)),
        close: parseFloat(close.toFixed(2)),
        volume: Math.random() * 1000,
      });
    }

    const key = `bybit_candles_v1_${category}_${symbol.toUpperCase()}_${interval}`;
    const data = {
      timestamp: Date.now(),
      candles: candles,
    };

    localStorage.setItem(key, JSON.stringify(data));
    console.log(`✅ Создано ${count} свечей в ${key}`);
  },
};

// Автоматические тесты
const AutoTests = {
  async test1_EmptyStorage() {
    console.log('\n🧪 ТЕСТ 1: Загрузка 2000 свечей в пустую базу');
    console.log('═══════════════════════════════════════════════');

    TestUtils.clearAllStorage();
    console.log('⏳ Перезагрузите страницу и наблюдайте консоль...');
    console.log('📌 Ожидаемый результат: "🆕 No cache found, loading fresh data"');
    console.log('📌 Должно загрузиться ~1000 свечей (лимит API)');
  },

  async test2_EmptyStorage1h() {
    console.log('\n🧪 ТЕСТ 2: Загрузка для 1h таймфрейма в пустую базу');
    console.log('═══════════════════════════════════════════════');

    TestUtils.clearAllStorage();
    console.log('⏳ Перезагрузите страницу, переключитесь на 1h и наблюдайте...');
    console.log('📌 Ожидаемый результат: загрузка свежих данных для 1h');
  },

  async test3_PartialStorage() {
    console.log('\n🧪 ТЕСТ 3: Догрузка в базу с существующими свечами');
    console.log('═══════════════════════════════════════════════');

    // Создаём кэш с устаревшими данными (500 свечей, последняя - 2 дня назад)
    const symbol = 'BTCUSDT';
    const interval = '15';

    TestUtils.createFakeCache(symbol, interval, 500);
    TestUtils.partialClear(symbol, interval, 100); // Удалим последние 100

    console.log('⏳ Перезагрузите страницу и наблюдайте консоль...');
    console.log('📌 Ожидаемый результат:');
    console.log('   - "📦 Found 400 cached candles"');
    console.log('   - "✅ Updated last 10 candles"');
    console.log('   - "📊 New candles needed: ~XXX"');
    console.log('   - Догрузка новых свечей');
  },

  async test4_PartialStorage1h() {
    console.log('\n🧪 ТЕСТ 4: Догрузка для 1h с существующими данными');
    console.log('═══════════════════════════════════════════════');

    TestUtils.createFakeCache('BTCUSDT', '60', 300);
    TestUtils.partialClear('BTCUSDT', '60', 50);

    console.log('⏳ Перезагрузите страницу, переключитесь на 1h...');
    console.log('📌 Ожидаемый результат: обновление + догрузка для 1h');
  },

  async test5_Historical() {
    console.log('\n🧪 ТЕСТ 5: Загрузка исторических данных (2000 свечей в прошлое)');
    console.log('═══════════════════════════════════════════════');

    console.log('📌 Эта функция пока ограничена API Bybit');
    console.log('📌 API не поддерживает загрузку старых данных');
    console.log('💡 Для реализации нужен backend с историческим API');

    // Можно проверить функцию loadHistoricalCandles
    console.log('\n📝 Можно вызвать вручную:');
    console.log('const store = window.__ZUSTAND_STORE__?.getState();');
    console.log('await store.loadHistoricalCandles("BTCUSDT", "15", 2000);');
  },

  async test6_GracefulShutdown() {
    console.log('\n🧪 ТЕСТ 6: Корректный выход из программы');
    console.log('═══════════════════════════════════════════════');

    console.log('📌 Шаги теста:');
    console.log('1. Загрузите данные (любой таймфрейм)');
    console.log('2. Нажмите кнопку "Выход" в интерфейсе');
    console.log('3. Подтвердите сохранение');
    console.log('4. После перезагрузки проверьте, что данные сохранились');
    console.log('\n💡 Проверка: TestUtils.showStats()');
  },

  async test7_MultipleTimeframes() {
    console.log('\n🧪 ТЕСТ 7: Работа с несколькими таймфреймами одновременно');
    console.log('═══════════════════════════════════════════════');

    TestUtils.clearAllStorage();

    console.log('📌 Создаём данные для нескольких таймфреймов...');
    TestUtils.createFakeCache('BTCUSDT', '1', 200);
    TestUtils.createFakeCache('BTCUSDT', '5', 300);
    TestUtils.createFakeCache('BTCUSDT', '15', 400);
    TestUtils.createFakeCache('BTCUSDT', '60', 500);

    console.log('\n⏳ Переключайтесь между таймфреймами...');
    console.log('📌 Ожидаемый результат: каждый таймфрейм имеет свой кэш');
    console.log('📌 Данные не смешиваются между таймфреймами');

    TestUtils.showStats();
  },

  async test8_SymbolSwitch() {
    console.log('\n🧪 ТЕСТ 8: Переключение между торговыми парами');
    console.log('═══════════════════════════════════════════════');

    console.log('📌 Создаём данные для разных пар...');
    TestUtils.createFakeCache('BTCUSDT', '15', 400);
    TestUtils.createFakeCache('ETHUSDT', '15', 400);
    TestUtils.createFakeCache('SOLUSDT', '15', 400);

    console.log('\n⏳ Переключайтесь между парами в интерфейсе...');
    console.log('📌 Ожидаемый результат: каждая пара имеет свой кэш');

    TestUtils.showStats();
  },

  async test9_CacheLimits() {
    console.log('\n🧪 ТЕСТ 9: Проверка лимита кэша (MAX 2000 свечей)');
    console.log('═══════════════════════════════════════════════');

    console.log('📌 Создаём избыточный кэш (2500 свечей)...');
    TestUtils.createFakeCache('BTCUSDT', '15', 2500);

    console.log('⏳ Перезагрузите страницу и проверьте...');
    console.log('📌 Ожидаемый результат: после обработки останется макс 2000 свечей');
    console.log('📌 Старые свечи должны быть удалены');
  },

  async runAll() {
    console.log('\n🚀 ЗАПУСК ВСЕХ ТЕСТОВ');
    console.log('═══════════════════════════════════════════════\n');

    await this.test1_EmptyStorage();
    console.log('\n⏸️  Выполните тест вручную, затем продолжите...\n');
  },
};

// Экспорт в глобальную область
window.TestUtils = TestUtils;
window.AutoTests = AutoTests;

console.log(`
╔═══════════════════════════════════════════════════════════╗
║  🧪 Тестовые утилиты загружены!                          ║
╚═══════════════════════════════════════════════════════════╝

📋 Доступные команды:

  TestUtils.clearAllStorage()           - Очистить всю базу
  TestUtils.clearSymbol('BTCUSDT', '15') - Очистить конкретную пару
  TestUtils.partialClear('BTCUSDT', '15', 500) - Удалить последние N свечей
  TestUtils.showStats()                  - Показать статистику
  TestUtils.createFakeCache('BTC', '15', 500) - Создать тестовые данные

  AutoTests.test1_EmptyStorage()         - Тест 1: Пустая база
  AutoTests.test2_EmptyStorage1h()       - Тест 2: Пустая база + 1h
  AutoTests.test3_PartialStorage()       - Тест 3: Догрузка
  AutoTests.test4_PartialStorage1h()     - Тест 4: Догрузка + 1h
  AutoTests.test5_Historical()           - Тест 5: Исторические данные
  AutoTests.test6_GracefulShutdown()     - Тест 6: Корректный выход
  AutoTests.test7_MultipleTimeframes()   - Тест 7: Несколько таймфреймов
  AutoTests.test8_SymbolSwitch()         - Тест 8: Смена пар
  AutoTests.test9_CacheLimits()          - Тест 9: Лимиты кэша

🎯 Быстрый старт:
   1. Откройте http://localhost:5174 (или проверьте в терминале)
   2. Нажмите F12 (консоль)
   3. Скопируйте содержимое test_storage.js
   4. Выполните: AutoTests.test1_EmptyStorage()
`);
