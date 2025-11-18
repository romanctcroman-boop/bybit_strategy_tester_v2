/**
 * Playwright Global Setup
 * Выполняется один раз перед всеми тестами
 *
 * Рекомендации от DeepSeek:
 * - Сброс БД до чистого состояния
 * - Загрузка базовых фикстур (users, permissions)
 * - Проверка готовности всех сервисов
 */

import { FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0].use.baseURL || 'http://localhost:5173';
  const apiBaseURL = 'http://localhost:8000';

  console.log('🔧 Global Setup: Preparing test environment...');

  // Ждём готовности backend (с retry логикой) + проверка БД
  console.log('⏳ Waiting for backend and database to be ready...');
  const maxRetries = 30;
  let backendReady = false;
  let dbReady = false;

  for (let i = 0; i < maxRetries; i++) {
    try {
      // 1. Проверяем backend health
      const response = await fetch(`${apiBaseURL}/healthz`, {
        method: 'GET',
      });

      if (response.ok) {
        console.log('✅ Backend is ready');
        backendReady = true;

        // 2. Проверяем database connectivity (DeepSeek recommendation)
        try {
          const dbCheck = await fetch(`${apiBaseURL}/api/v1/test/health/db`, {
            method: 'GET',
          });

          if (dbCheck.ok) {
            const dbHealth = await dbCheck.json();
            if (dbHealth.status === 'healthy') {
              console.log('✅ Database is connected and healthy');
              dbReady = true;
              break;
            }
          }
        } catch (e) {
          // DB health check not available yet
          console.log(`⏳ Attempt ${i + 1}/${maxRetries}: DB not ready yet...`);
        }
      }
    } catch (e) {
      // Backend not ready yet
      console.log(`⏳ Attempt ${i + 1}/${maxRetries}: Backend not ready yet...`);
    }

    await new Promise((resolve) => setTimeout(resolve, 2000));
  }

  if (!backendReady) {
    throw new Error('❌ Backend failed to start within timeout');
  }

  if (!dbReady) {
    console.warn('⚠️  Database health check failed - proceeding anyway');
  }

  // Сброс БД до чистого состояния (DeepSeek Priority 1)
  try {
    console.log('🔄 Resetting database to clean state...');
    const resetResponse = await fetch(`${apiBaseURL}/api/v1/test/reset`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });

    if (resetResponse.ok) {
      const result = await resetResponse.json();
      console.log('✅ Database reset completed:');
      console.log(`   - Tables cleared: ${result.tables_cleared.join(', ')}`);
      console.log(`   - Test users: admin/admin123, user/user123`);
    } else if (resetResponse.status === 403) {
      console.warn('⚠️  Test reset endpoint requires TESTING=true environment variable');
    } else if (resetResponse.status === 404) {
      console.log('ℹ️  Test reset endpoint not available (optional)');
    }
  } catch (e) {
    console.log('ℹ️  Test reset endpoint not available (optional)');
  }

  // Проверяем наличие тестовых пользователей
  try {
    const loginResponse = await fetch(`${apiBaseURL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: 'admin',
        password: 'admin123',
      }),
    });

    if (loginResponse.ok) {
      console.log('✅ Test users are available');
    } else {
      console.warn('⚠️  Admin user login failed - tests may fail');
    }
  } catch (e) {
    console.warn('⚠️  Could not verify test users:', e);
  }

  console.log('✅ Global Setup completed\n');
}

export default globalSetup;
