/**
 * Settings Page - User Level Management
 *
 * Позволяет пользователю переключать уровень доступа:
 * - BASIC: Просмотр, простой бектест, CSV экспорт
 * - ADVANCED: + Grid/WFO оптимизация, MTF анализ
 * - EXPERT: + Monte Carlo, кастомные стратегии, API доступ
 */

import React, { useState, useEffect } from 'react';

type UserLevel = 'basic' | 'advanced' | 'expert';

interface FeatureFlags {
  view_strategies: boolean;
  run_backtest: boolean;
  export_csv: boolean;
  grid_optimization: boolean;
  walk_forward: boolean;
  multi_timeframe: boolean;
  monte_carlo: boolean;
  custom_strategies: boolean;
  api_access: boolean;
}

const LEVEL_INFO = {
  basic: {
    title: 'Базовый',
    description: 'Просмотр стратегий, простой бектестинг, экспорт в CSV',
    color: '#4CAF50',
    features: [
      'Просмотр готовых стратегий',
      'Запуск простого бектеста',
      'Экспорт результатов в CSV',
      'Просмотр графиков PnL',
    ],
  },
  advanced: {
    title: 'Продвинутый',
    description: 'Все функции Базового + оптимизация, MTF анализ',
    color: '#FF9800',
    features: [
      'Все функции Базового уровня',
      'Grid оптимизация параметров',
      'Walk-Forward оптимизация',
      'Multi-Timeframe анализ',
      'Сравнение стратегий',
    ],
  },
  expert: {
    title: 'Экспертный',
    description: 'Полный доступ ко всем функциям',
    color: '#F44336',
    features: [
      'Все функции Продвинутого уровня',
      'Monte Carlo симуляция',
      'Создание кастомных стратегий',
      'API доступ для автоматизации',
      'Расширенная аналитика',
    ],
  },
};

export default function SettingsPage() {
  const [currentLevel, setCurrentLevel] = useState<UserLevel>('basic');
  const [features, setFeatures] = useState<FeatureFlags | null>(null);

  // Загрузка уровня из localStorage при монтировании
  useEffect(() => {
    const savedLevel = localStorage.getItem('user_level') as UserLevel;
    if (savedLevel && ['basic', 'advanced', 'expert'].includes(savedLevel)) {
      setCurrentLevel(savedLevel);
    }

    // Fetch доступных функций
    fetchAvailableFeatures(savedLevel || 'basic');
  }, []);

  const fetchAvailableFeatures = async (level: UserLevel) => {
    try {
      const response = await fetch('http://localhost:8000/api/rbac/features', {
        headers: {
          'X-User-Level': level,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setFeatures(data);
      }
    } catch (error) {
      console.error('Failed to fetch features:', error);
    }
  };

  const handleLevelChange = (newLevel: UserLevel) => {
    setCurrentLevel(newLevel);
    localStorage.setItem('user_level', newLevel);

    // Обновить доступные функции
    fetchAvailableFeatures(newLevel);

    // Показать уведомление
    alert(
      `Уровень доступа изменён на: ${LEVEL_INFO[newLevel].title}\n\nПерезагрузите страницу для применения изменений.`
    );
  };

  return (
    <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      <h1>⚙️ Настройки</h1>

      <section style={{ marginBottom: '40px' }}>
        <h2>Уровень доступа</h2>
        <p style={{ color: '#666', marginBottom: '20px' }}>
          Выберите уровень доступа к функциям платформы. Изменения вступят в силу после перезагрузки
          страницы.
        </p>

        <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
          {(['basic', 'advanced', 'expert'] as UserLevel[]).map((level) => (
            <div
              key={level}
              onClick={() => handleLevelChange(level)}
              style={{
                flex: '1 1 300px',
                padding: '20px',
                border: `3px solid ${currentLevel === level ? LEVEL_INFO[level].color : '#ddd'}`,
                borderRadius: '8px',
                cursor: 'pointer',
                backgroundColor: currentLevel === level ? `${LEVEL_INFO[level].color}15` : '#fff',
                transition: 'all 0.2s',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: '10px' }}>
                <h3 style={{ margin: 0, color: LEVEL_INFO[level].color }}>
                  {LEVEL_INFO[level].title}
                </h3>
                {currentLevel === level && (
                  <span style={{ marginLeft: 'auto', fontSize: '24px' }}>✓</span>
                )}
              </div>

              <p style={{ color: '#666', fontSize: '14px', marginBottom: '15px' }}>
                {LEVEL_INFO[level].description}
              </p>

              <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px' }}>
                {LEVEL_INFO[level].features.map((feature, idx) => (
                  <li key={idx} style={{ marginBottom: '5px' }}>
                    {feature}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      {features && (
        <section style={{ marginTop: '40px' }}>
          <h2>Доступные функции</h2>
          <div
            style={{
              padding: '20px',
              backgroundColor: '#f5f5f5',
              borderRadius: '8px',
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
              gap: '10px',
            }}
          >
            {Object.entries(features).map(([key, value]) => (
              <div
                key={key}
                style={{
                  padding: '10px',
                  backgroundColor: value ? '#e8f5e9' : '#ffebee',
                  borderRadius: '4px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                }}
              >
                <span style={{ fontSize: '18px' }}>{value ? '✅' : '❌'}</span>
                <span style={{ fontSize: '13px' }}>
                  {key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      <section
        style={{
          marginTop: '40px',
          padding: '20px',
          backgroundColor: '#fff3cd',
          borderRadius: '8px',
        }}
      >
        <h3>ℹ️ Важно</h3>
        <ul style={{ margin: 0 }}>
          <li>Уровень доступа сохраняется в localStorage браузера</li>
          <li>
            При каждом запросе к API уровень передаётся в заголовке <code>X-User-Level</code>
          </li>
          <li>Некоторые эндпоинты заблокированы для определённых уровней</li>
          <li>Для применения изменений перезагрузите страницу</li>
        </ul>
      </section>
    </div>
  );
}
