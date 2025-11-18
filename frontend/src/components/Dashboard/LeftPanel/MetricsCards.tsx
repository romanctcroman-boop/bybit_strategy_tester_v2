import React from 'react';
import { AggregateMetrics } from '../../../hooks/useWFOResults';
import './MetricsCards.css';

// ✅ Импорт централизованных утилит форматирования (Quick Win #3)
import { formatNumber } from '../../../utils/formatting';

interface MetricsCardsProps {
  metrics: AggregateMetrics | null;
  loading?: boolean;
}

interface MetricCardProps {
  title: string;
  value: string | number;
  trend?: 'up' | 'down' | 'neutral';
  color?: string;
  suffix?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ title, value, trend, color, suffix = '' }) => {
  const getValueColor = () => {
    if (color) return color;
    if (trend === 'up') return '#51cf66';
    if (trend === 'down') return '#ff6b6b';
    return '#c0d0ff';
  };

  return (
    <div className="metric-card">
      <span className="metric-label">{title}</span>
      <span className="metric-value" style={{ color: getValueColor() }}>
        {value}
        {suffix}
      </span>
    </div>
  );
};

const MetricsCards: React.FC<MetricsCardsProps> = ({ metrics, loading }) => {
  if (loading) {
    return (
      <div className="metrics-cards">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="metric-card metric-card-loading">
            <div className="skeleton-label"></div>
            <div className="skeleton-value"></div>
          </div>
        ))}
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="metrics-cards">
        <div className="metric-card">
          <span className="metric-label">No Data</span>
          <span className="metric-value">-</span>
        </div>
      </div>
    );
  }

  // ✅ Функции форматирования теперь импортированы из ../../../utils/formatting
  const formatPercent = (value: number) => {
    const sign = value >= 0 ? '+' : '';
    return `${sign}${formatNumber(value, 2)}`;
  };

  return (
    <div className="metrics-cards">
      <MetricCard
        title="Avg Return"
        value={formatPercent(metrics.avg_return)}
        suffix="%"
        trend={metrics.avg_return > 0 ? 'up' : 'down'}
      />
      <MetricCard
        title="Sharpe Ratio"
        value={formatNumber(metrics.avg_sharpe, 2)}
        trend={metrics.avg_sharpe > 0.5 ? 'up' : metrics.avg_sharpe < 0 ? 'down' : 'neutral'}
      />
      <MetricCard
        title="Win Rate"
        value={formatNumber(metrics.avg_win_rate * 100, 1)}
        suffix="%"
        trend={metrics.avg_win_rate > 0.5 ? 'up' : 'down'}
      />
      <MetricCard
        title="Max Drawdown"
        value={formatNumber(metrics.avg_max_dd)}
        suffix="%"
        color="#ff6b6b"
      />
      <MetricCard
        title="Profit Factor"
        value={formatNumber(metrics.avg_profit_factor)}
        trend={metrics.avg_profit_factor > 1 ? 'up' : 'down'}
      />
      <MetricCard title="Total Trades" value={metrics.total_trades} color="#c0d0ff" />
    </div>
  );
};

export default MetricsCards;
