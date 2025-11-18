/**
 * Playwright Global Teardown
 * Выполняется один раз после всех тестов
 *
 * Рекомендации от DeepSeek:
 * - Очистка тестовых данных
 * - Graceful shutdown сервисов
 * - Логирование финальной статистики
 */

import { FullConfig } from '@playwright/test';

async function globalTeardown(config: FullConfig) {
  const apiBaseURL = 'http://localhost:8000';

  console.log('\n🧹 Global Teardown: Cleaning up test environment...');

  try {
    // Очистка тестовых артефактов (DeepSeek Priority 1)
    console.log('🗑️  Cleaning up test artifacts...');
    const cleanupResponse = await fetch(`${apiBaseURL}/api/v1/test/cleanup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });

    if (cleanupResponse.ok) {
      const result = await cleanupResponse.json();
      console.log('✅ Test data cleanup completed:');
      console.log(`   - Strategies removed: ${result.removed.strategies}`);
      console.log(`   - Backtests removed: ${result.removed.backtests}`);
    } else if (cleanupResponse.status === 403) {
      console.warn('⚠️  Test cleanup endpoint requires TESTING=true environment variable');
    } else if (cleanupResponse.status === 404) {
      console.log('ℹ️  Test cleanup endpoint not available (optional)');
    }
  } catch (e) {
    console.log('ℹ️  Could not cleanup test data (optional):', (e as Error).message);
  }

  console.log('✅ Global Teardown completed');
}

export default globalTeardown;
