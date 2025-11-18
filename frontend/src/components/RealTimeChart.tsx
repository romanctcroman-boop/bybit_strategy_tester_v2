/**
 * Real-Time Equity Curve Chart Component
 *
 * Отображает live equity curve с WebSocket обновлениями
 *
 * Features:
 * - Real-time data streaming (WebSocket)
 * - Smooth chart updates (не перерисовывает весь график)
 * - Drawdown visualization (красная зона)
 * - Performance metrics display (Sharpe, Win Rate, Max DD)
 * - Auto-scroll to latest data point
 * - Responsive design
 *
 * Usage:
 * ```tsx
 * <RealTimeChart backtestId={123} />
 * ```
 */

import React, { useEffect, useState } from 'react';
import {
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts';
import { useWebSocket, useWebSocketMessages, useLastWebSocketMessage } from '../hooks/useWebSocket';

// ============================================================================
// Types
// ============================================================================

interface EquityPoint {
  timestamp: string;
  equity: number;
  drawdown: number;
}

interface MetricsData {
  sharpe_ratio?: number;
  max_drawdown?: number;
  win_rate?: number;
  total_trades?: number;
  profit_factor?: number;
}

interface RealTimeChartProps {
  /** ID бэктеста для отслеживания */
  backtestId: number;

  /** Начальный капитал */
  initialCapital?: number;

  /** Высота графика (px) */
  height?: number;

  /** Показывать метрики */
  showMetrics?: boolean;
}

// ============================================================================
// Component
// ============================================================================

export const RealTimeChart: React.FC<RealTimeChartProps> = ({
  backtestId,
  initialCapital = 10000,
  height = 400,
  showMetrics = true,
}) => {
  // ============================================================================
  // WebSocket Connection
  // ============================================================================

  const { isConnected, messages, error } = useWebSocket(backtestId, {
    autoReconnect: true,
    heartbeatInterval: 30000,
    debug: false,
  });

  // ============================================================================
  // State
  // ============================================================================

  const [equityData, setEquityData] = useState<EquityPoint[]>([
    { timestamp: new Date().toISOString(), equity: initialCapital, drawdown: 0 },
  ]);

  const [metrics, setMetrics] = useState<MetricsData>({});
  const [status, setStatus] = useState<string>('pending');
  const [progress, setProgress] = useState<number>(0);

  // ============================================================================
  // WebSocket Message Handlers
  // ============================================================================

  // Equity updates
  const equityUpdates = useWebSocketMessages<{
    timestamp: string;
    equity: number;
    drawdown: number;
  }>(messages, 'equity_update');

  // Metrics updates
  const metricsUpdate = useLastWebSocketMessage<MetricsData>(messages, 'metrics_update');

  // Status changes
  const statusUpdate = useLastWebSocketMessage<{ status: string; progress: number }>(
    messages,
    'status_change'
  );

  // Initial state
  const initialState = useLastWebSocketMessage<any>(messages, 'initial_state');

  // ============================================================================
  // Effects
  // ============================================================================

  // Update equity data
  useEffect(() => {
    if (equityUpdates.length > 0) {
      const newPoints = equityUpdates.map((update) => ({
        timestamp: new Date(update.timestamp).toLocaleTimeString(),
        equity: update.equity,
        drawdown: update.drawdown,
      }));

      setEquityData((prev) => {
        const combined = [...prev, ...newPoints];

        // Limit to last 500 points (performance optimization)
        if (combined.length > 500) {
          return combined.slice(-500);
        }

        return combined;
      });
    }
  }, [equityUpdates]);

  // Update metrics
  useEffect(() => {
    if (metricsUpdate) {
      setMetrics(metricsUpdate);
    }
  }, [metricsUpdate]);

  // Update status
  useEffect(() => {
    if (statusUpdate) {
      setStatus(statusUpdate.status);
      setProgress(statusUpdate.progress || 0);
    }
  }, [statusUpdate]);

  // Initial state
  useEffect(() => {
    if (initialState) {
      setStatus(initialState.status || 'pending');
      setProgress(initialState.progress || 0);
    }
  }, [initialState]);

  // ============================================================================
  // Calculations
  // ============================================================================

  const currentEquity = equityData[equityData.length - 1]?.equity || initialCapital;
  const pnl = currentEquity - initialCapital;
  const pnlPercent = ((pnl / initialCapital) * 100).toFixed(2);
  const pnlColor = pnl >= 0 ? '#10b981' : '#ef4444';

  // ============================================================================
  // Render
  // ============================================================================

  return (
    <div className="real-time-chart">
      {/* Header */}
      <div className="chart-header" style={{ marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <h3 style={{ margin: 0 }}>🚀 Real-Time Equity Curve - Backtest #{backtestId}</h3>

          {/* Connection Status */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 12px',
              borderRadius: '12px',
              fontSize: '12px',
              fontWeight: 'bold',
              background: isConnected ? '#10b98120' : '#ef444420',
              color: isConnected ? '#10b981' : '#ef4444',
            }}
          >
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: isConnected ? '#10b981' : '#ef4444',
                animation: isConnected ? 'pulse 2s ease-in-out infinite' : 'none',
              }}
            />
            {isConnected ? 'LIVE' : 'DISCONNECTED'}
          </div>

          {/* Status Badge */}
          <div
            style={{
              padding: '4px 12px',
              borderRadius: '12px',
              fontSize: '12px',
              fontWeight: 'bold',
              background: status === 'running' ? '#3b82f620' : '#94a3b820',
              color: status === 'running' ? '#3b82f6' : '#6b7280',
            }}
          >
            {status.toUpperCase()} {status === 'running' && `(${progress}%)`}
          </div>
        </div>

        {error && (
          <div
            style={{
              marginTop: '8px',
              padding: '8px 12px',
              borderRadius: '6px',
              background: '#ef444420',
              color: '#ef4444',
              fontSize: '13px',
            }}
          >
            ⚠️ {error}
          </div>
        )}
      </div>

      {/* Metrics Cards */}
      {showMetrics && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: '12px',
            marginBottom: '16px',
          }}
        >
          {/* Current Equity */}
          <MetricCard
            label="Current Equity"
            value={`$${currentEquity.toLocaleString()}`}
            change={`${pnlPercent}%`}
            changeColor={pnlColor}
          />

          {/* PnL */}
          <MetricCard label="PnL" value={`$${pnl.toFixed(2)}`} valueColor={pnlColor} />

          {/* Sharpe Ratio */}
          {metrics.sharpe_ratio !== undefined && (
            <MetricCard
              label="Sharpe Ratio"
              value={metrics.sharpe_ratio.toFixed(2)}
              valueColor={metrics.sharpe_ratio > 1 ? '#10b981' : '#ef4444'}
            />
          )}

          {/* Win Rate */}
          {metrics.win_rate !== undefined && (
            <MetricCard
              label="Win Rate"
              value={`${metrics.win_rate.toFixed(1)}%`}
              valueColor={metrics.win_rate > 50 ? '#10b981' : '#ef4444'}
            />
          )}

          {/* Max Drawdown */}
          {metrics.max_drawdown !== undefined && (
            <MetricCard
              label="Max Drawdown"
              value={`${metrics.max_drawdown.toFixed(2)}%`}
              valueColor="#ef4444"
            />
          )}

          {/* Total Trades */}
          {metrics.total_trades !== undefined && (
            <MetricCard label="Total Trades" value={metrics.total_trades.toString()} />
          )}
        </div>
      )}

      {/* Chart */}
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={equityData}>
          <defs>
            {/* Gradient for equity */}
            <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
          </defs>

          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />

          <XAxis dataKey="timestamp" stroke="#9ca3af" style={{ fontSize: '12px' }} />

          <YAxis stroke="#9ca3af" style={{ fontSize: '12px' }} domain={['auto', 'auto']} />

          <Tooltip
            contentStyle={{
              background: '#1f2937',
              border: '1px solid #374151',
              borderRadius: '6px',
              color: '#f3f4f6',
            }}
            formatter={(value: number, name: string) => {
              if (name === 'equity') {
                return [`$${value.toFixed(2)}`, 'Equity'];
              }
              if (name === 'drawdown') {
                return [`${value.toFixed(2)}%`, 'Drawdown'];
              }
              return [value, name];
            }}
          />

          <Legend />

          {/* Equity Line */}
          <Area
            type="monotone"
            dataKey="equity"
            stroke="#3b82f6"
            strokeWidth={2}
            fill="url(#equityGradient)"
            name="Equity"
          />

          {/* Drawdown Line (optional) */}
          {equityData.some((d) => d.drawdown !== 0) && (
            <Line
              type="monotone"
              dataKey="drawdown"
              stroke="#ef4444"
              strokeWidth={1}
              dot={false}
              name="Drawdown"
            />
          )}
        </AreaChart>
      </ResponsiveContainer>

      {/* CSS for pulse animation */}
      <style>{`
        @keyframes pulse {
          0%, 100% {
            opacity: 1;
          }
          50% {
            opacity: 0.5;
          }
        }
      `}</style>
    </div>
  );
};

// ============================================================================
// Metric Card Component
// ============================================================================

interface MetricCardProps {
  label: string;
  value: string;
  change?: string;
  changeColor?: string;
  valueColor?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  change,
  changeColor,
  valueColor,
}) => {
  return (
    <div
      style={{
        padding: '12px',
        borderRadius: '8px',
        background: '#1f2937',
        border: '1px solid #374151',
      }}
    >
      <div
        style={{
          fontSize: '12px',
          color: '#9ca3af',
          marginBottom: '4px',
          fontWeight: '500',
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: '20px',
          fontWeight: 'bold',
          color: valueColor || '#f3f4f6',
        }}
      >
        {value}
      </div>
      {change && (
        <div
          style={{
            fontSize: '12px',
            color: changeColor || '#9ca3af',
            marginTop: '2px',
          }}
        >
          {change}
        </div>
      )}
    </div>
  );
};

export default RealTimeChart;
