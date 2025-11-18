/**
 * DashboardLayout Component - 4-Zone Architecture
 * Based on Perplexity AI recommendations and user mockup
 *
 * Zones:
 * - GREEN Header: Status indicators, strategy selector, actions
 * - DARK BLUE Left Panel (70%): Charts, metrics, statistics, tables
 * - TEAL Right Panel (30%): Strategy parameters, filters, signals, patterns
 * - PURPLE Footer: Version info, last update, quick links
 */

import React, { useState, useEffect } from 'react';
import './DashboardLayout.css';
import LeftPanel from './LeftPanel';
import RightPanel from './RightPanel';

interface DashboardLayoutProps {
  /** Optional custom header content */
  customHeader?: React.ReactNode;
  /** Optional custom footer content */
  customFooter?: React.ReactNode;
}

export const DashboardLayout: React.FC<DashboardLayoutProps> = ({ customHeader, customFooter }) => {
  // State management
  const [selectedStrategy, setSelectedStrategy] = useState<string>('sr_mean_reversion');
  const [selectedTimeframe, setSelectedTimeframe] = useState<string>('5m');
  const [connectionStatus] = useState<'online' | 'offline'>('online');
  const [lastUpdate, setLastUpdate] = useState<string>(new Date().toLocaleString('ru-RU'));

  // Strategy mapping (display name → file name)
  const strategyMap: Record<string, string> = {
    'S/R Mean-Reversion': 'sr_mean_reversion',
    'Bollinger Bands': 'bb_mean_reversion',
    'EMA Crossover': 'ema_crossover',
    'S/R + RSI Enhanced': 'sr_rsi_enhanced',
  };

  // Update timestamp every minute
  useEffect(() => {
    const interval = setInterval(() => {
      setLastUpdate(new Date().toLocaleString('ru-RU'));
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  // Handle strategy change from dropdown
  const handleStrategyChange = (displayName: string) => {
    const strategyKey = strategyMap[displayName];
    if (strategyKey) {
      setSelectedStrategy(strategyKey);
    }
  };

  // Handle timeframe change
  const handleTimeframeChange = (timeframe: string) => {
    setSelectedTimeframe(timeframe);
  };

  // Default Header
  const defaultHeader = (
    <div className="dashboard-header">
      <div className="dashboard-header-left">
        {/* Connection Status */}
        <div className="connection-status">
          <div className={`connection-status-icon ${connectionStatus}`}></div>
          <span>{connectionStatus === 'online' ? 'Подключено' : 'Отключено'}</span>
        </div>

        {/* Data Freshness */}
        <div className="data-freshness">Обновлено: {lastUpdate}</div>
      </div>

      <div className="dashboard-header-center">
        {/* Strategy Selector */}
        <label htmlFor="strategy-select">Стратегия:</label>
        <select
          id="strategy-select"
          className="strategy-selector"
          value={Object.keys(strategyMap).find((key) => strategyMap[key] === selectedStrategy)}
          onChange={(e) => handleStrategyChange(e.target.value)}
        >
          {Object.keys(strategyMap).map((displayName) => (
            <option key={displayName} value={displayName}>
              {displayName}
            </option>
          ))}
        </select>

        {/* Timeframe Selector */}
        <label htmlFor="timeframe-select">Таймфрейм:</label>
        <select
          id="timeframe-select"
          className="strategy-selector"
          value={selectedTimeframe}
          onChange={(e) => handleTimeframeChange(e.target.value)}
        >
          <option value="1m">1 минута</option>
          <option value="5m">5 минут</option>
          <option value="15m">15 минут</option>
          <option value="1h">1 час</option>
          <option value="4h">4 часа</option>
          <option value="1d">1 день</option>
        </select>
      </div>

      <div className="dashboard-header-right">
        {/* Action Buttons */}
        <button className="header-button" title="Export results">
          📥 Экспорт
        </button>
        <button className="header-button" title="Settings">
          ⚙️ Настройки
        </button>
        <button className="header-button" title="Help">
          ❓ Помощь
        </button>
      </div>
    </div>
  );

  // Default Footer
  const defaultFooter = (
    <div className="dashboard-footer">
      <div className="dashboard-footer-left">
        <span>Bybit Strategy Tester v1.0.0</span>
        <span>|</span>
        <span>Последнее обновление: {lastUpdate}</span>
      </div>

      <div className="dashboard-footer-center">
        <span>Статус: Готов</span>
      </div>

      <div className="dashboard-footer-right">
        <a href="#" className="footer-link">
          Документация
        </a>
        <span>|</span>
        <a href="#" className="footer-link">
          Поддержка
        </a>
        <span>|</span>
        <a href="#" className="footer-link">
          Логи
        </a>
      </div>
    </div>
  );

  return (
    <div className="dashboard-container">
      {/* Header Zone (Green) */}
      {customHeader || defaultHeader}

      {/* Left Panel Zone (Dark Blue) */}
      <div className="dashboard-left-panel">
        <LeftPanel strategy={selectedStrategy} />
      </div>

      {/* Right Panel Zone (Teal) */}
      <div className="dashboard-right-panel">
        <RightPanel />
      </div>

      {/* Footer Zone (Purple) */}
      {customFooter || defaultFooter}
    </div>
  );
};

export default DashboardLayout;
