import React from 'react';
import './Header.css';

interface DashboardHeaderProps {
  strategyName?: string;
  timeframe?: string;
  onStrategyChange?: (strategy: string) => void;
  onTimeframeChange?: (timeframe: string) => void;
}

const DashboardHeader: React.FC<DashboardHeaderProps> = ({
  strategyName = 'S/R Mean-Reversion',
  timeframe = '5m',
  onStrategyChange,
  onTimeframeChange,
}) => {
  const handleStrategyChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const displayNames: Record<string, string> = {
      ema_crossover: 'EMA Crossover',
      sr_mean_reversion: 'S/R Mean-Reversion',
      bb_mean_reversion: 'Bollinger Bands',
      sr_rsi: 'S/R + RSI Enhanced',
    };
    onStrategyChange?.(displayNames[e.target.value] || e.target.value);
  };

  const handleTimeframeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onTimeframeChange?.(e.target.value);
  };

  return (
    <header className="dashboard-header">
      <div className="header-left">
        <h1 className="header-title">Bybit Strategy Tester v2</h1>
        <div className="status-indicator">
          <span className="status-dot status-active"></span>
          <span className="status-text">WFO Analysis Complete</span>
        </div>
      </div>

      <div className="header-center">
        <div className="control-group">
          <label htmlFor="strategy-select">Strategy:</label>
          <select
            id="strategy-select"
            className="strategy-select"
            defaultValue={strategyName}
            onChange={handleStrategyChange}
          >
            <option value="ema_crossover">EMA Crossover</option>
            <option value="sr_mean_reversion">S/R Mean-Reversion</option>
            <option value="bb_mean_reversion">Bollinger Bands</option>
            <option value="sr_rsi">S/R + RSI Enhanced</option>
          </select>
        </div>

        <div className="control-group">
          <label htmlFor="timeframe-select">Timeframe:</label>
          <select
            id="timeframe-select"
            className="timeframe-select"
            defaultValue={timeframe}
            onChange={handleTimeframeChange}
          >
            <option value="1m">1 Minute</option>
            <option value="5m">5 Minutes</option>
            <option value="15m">15 Minutes</option>
            <option value="30m">30 Minutes</option>
            <option value="1h">1 Hour</option>
            <option value="4h">4 Hours</option>
          </select>
        </div>
      </div>

      <div className="header-right">
        <button className="btn-compare">Compare All</button>
        <button className="btn-export">Export Results</button>
      </div>
    </header>
  );
};

export default DashboardHeader;
