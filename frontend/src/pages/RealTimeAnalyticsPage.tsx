/**
 * Real-Time Analytics Dashboard Page
 *
 * Главная страница для мониторинга live бэктестов
 *
 * Features:
 * - Список активных бэктестов
 * - Live equity curves (WebSocket updates)
 * - Multi-strategy comparison (side-by-side charts)
 * - Real-time metrics dashboard
 * - Auto-refresh active backtests
 *
 * Usage:
 * Маршрут: /analytics
 */

import React, { useEffect, useState } from 'react';
import { RealTimeChart } from '../components/RealTimeChart';
import axios from 'axios';

// ============================================================================
// Types
// ============================================================================

interface Backtest {
  id: number;
  strategy_id: number;
  symbol: string;
  timeframe: string;
  status: string;
  progress: number;
  created_at: string;
  strategy?: {
    name: string;
  };
}

// ============================================================================
// Component
// ============================================================================

export const RealTimeAnalyticsPage: React.FC = () => {
  // ============================================================================
  // State
  // ============================================================================

  const [backtests, setBacktests] = useState<Backtest[]>([]);
  const [selectedBacktests, setSelectedBacktests] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ============================================================================
  // Fetch Active Backtests
  // ============================================================================

  const fetchActiveBacktests = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await axios.get('/api/v1/backtests', {
        params: {
          status: 'running',
          limit: 20,
          order_by: 'created_at',
          order_dir: 'desc',
        },
      });

      const items = response.data.items || [];
      setBacktests(items);

      // Auto-select first 2 backtests
      if (selectedBacktests.length === 0 && items.length > 0) {
        setSelectedBacktests(items.slice(0, 2).map((bt: Backtest) => bt.id));
      }
    } catch (err: any) {
      console.error('Failed to fetch backtests:', err);
      setError(err.response?.data?.detail || 'Failed to load backtests');
    } finally {
      setLoading(false);
    }
  };

  // ============================================================================
  // Effects
  // ============================================================================

  useEffect(() => {
    fetchActiveBacktests();

    // Refresh every 30 seconds
    const interval = setInterval(() => {
      fetchActiveBacktests();
    }, 30000);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ============================================================================
  // Handlers
  // ============================================================================

  const toggleBacktest = (backtestId: number) => {
    setSelectedBacktests((prev) => {
      if (prev.includes(backtestId)) {
        return prev.filter((id) => id !== backtestId);
      } else {
        // Limit to 4 charts (performance)
        if (prev.length >= 4) {
          return [...prev.slice(1), backtestId];
        }
        return [...prev, backtestId];
      }
    });
  };

  const clearSelection = () => {
    setSelectedBacktests([]);
  };

  const selectAll = () => {
    setSelectedBacktests(backtests.slice(0, 4).map((bt) => bt.id));
  };

  // ============================================================================
  // Render
  // ============================================================================

  return (
    <div className="real-time-analytics-page" style={{ padding: '24px' }}>
      {/* Page Header */}
      <div style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '32px', fontWeight: 'bold', marginBottom: '8px' }}>
          📊 Real-Time Analytics Dashboard
        </h1>
        <p style={{ color: '#9ca3af', fontSize: '16px' }}>
          Monitor live backtest performance with WebSocket streaming
        </p>
      </div>

      {/* Error Message */}
      {error && (
        <div
          style={{
            padding: '16px',
            marginBottom: '24px',
            borderRadius: '8px',
            background: '#ef444420',
            border: '1px solid #ef4444',
            color: '#ef4444',
          }}
        >
          ⚠️ {error}
        </div>
      )}

      {/* Controls */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          marginBottom: '24px',
          padding: '16px',
          background: '#1f2937',
          borderRadius: '8px',
          border: '1px solid #374151',
        }}
      >
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '14px', color: '#9ca3af', marginBottom: '4px' }}>
            Selected: {selectedBacktests.length} / 4
          </div>
          <div style={{ fontSize: '12px', color: '#6b7280' }}>
            Click on backtests below to toggle selection
          </div>
        </div>

        <button
          onClick={selectAll}
          disabled={backtests.length === 0}
          style={{
            padding: '8px 16px',
            borderRadius: '6px',
            border: '1px solid #3b82f6',
            background: '#3b82f620',
            color: '#3b82f6',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: '500',
          }}
        >
          Select First 4
        </button>

        <button
          onClick={clearSelection}
          disabled={selectedBacktests.length === 0}
          style={{
            padding: '8px 16px',
            borderRadius: '6px',
            border: '1px solid #6b7280',
            background: '#37415120',
            color: '#9ca3af',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: '500',
          }}
        >
          Clear Selection
        </button>

        <button
          onClick={fetchActiveBacktests}
          disabled={loading}
          style={{
            padding: '8px 16px',
            borderRadius: '6px',
            border: '1px solid #10b981',
            background: '#10b98120',
            color: '#10b981',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: '500',
          }}
        >
          {loading ? '⟳ Refreshing...' : '🔄 Refresh'}
        </button>
      </div>

      {/* Active Backtests List */}
      {backtests.length > 0 && (
        <div style={{ marginBottom: '32px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: 'bold', marginBottom: '16px' }}>
            Running Backtests ({backtests.length})
          </h2>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
              gap: '12px',
            }}
          >
            {backtests.map((backtest) => (
              <BacktestCard
                key={backtest.id}
                backtest={backtest}
                isSelected={selectedBacktests.includes(backtest.id)}
                onToggle={() => toggleBacktest(backtest.id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* No Backtests Message */}
      {!loading && backtests.length === 0 && (
        <div
          style={{
            padding: '48px',
            textAlign: 'center',
            background: '#1f2937',
            borderRadius: '8px',
            border: '1px solid #374151',
          }}
        >
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>📈</div>
          <div style={{ fontSize: '18px', fontWeight: '500', marginBottom: '8px' }}>
            No Running Backtests
          </div>
          <div style={{ color: '#9ca3af', fontSize: '14px' }}>
            Start a backtest to see real-time analytics here
          </div>
        </div>
      )}

      {/* Real-Time Charts */}
      {selectedBacktests.length > 0 && (
        <div>
          <h2 style={{ fontSize: '20px', fontWeight: 'bold', marginBottom: '16px' }}>
            Live Performance Charts
          </h2>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: selectedBacktests.length === 1 ? '1fr' : 'repeat(2, 1fr)',
              gap: '24px',
            }}
          >
            {selectedBacktests.map((backtestId) => (
              <div
                key={backtestId}
                style={{
                  padding: '20px',
                  background: '#1f2937',
                  borderRadius: '8px',
                  border: '1px solid #374151',
                }}
              >
                <RealTimeChart
                  backtestId={backtestId}
                  height={selectedBacktests.length === 1 ? 500 : 350}
                  showMetrics={true}
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// Backtest Card Component
// ============================================================================

interface BacktestCardProps {
  backtest: Backtest;
  isSelected: boolean;
  onToggle: () => void;
}

const BacktestCard: React.FC<BacktestCardProps> = ({ backtest, isSelected, onToggle }) => {
  return (
    <div
      onClick={onToggle}
      style={{
        padding: '16px',
        borderRadius: '8px',
        border: `2px solid ${isSelected ? '#3b82f6' : '#374151'}`,
        background: isSelected ? '#3b82f610' : '#1f2937',
        cursor: 'pointer',
        transition: 'all 0.2s',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
        {/* Selection Checkbox */}
        <div
          style={{
            width: '20px',
            height: '20px',
            borderRadius: '4px',
            border: `2px solid ${isSelected ? '#3b82f6' : '#6b7280'}`,
            background: isSelected ? '#3b82f6' : 'transparent',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontSize: '12px',
            fontWeight: 'bold',
          }}
        >
          {isSelected && '✓'}
        </div>

        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '16px', fontWeight: 'bold' }}>Backtest #{backtest.id}</div>
          <div style={{ fontSize: '12px', color: '#9ca3af' }}>
            {backtest.strategy?.name || `Strategy #${backtest.strategy_id}`}
          </div>
        </div>
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: '12px',
          color: '#9ca3af',
          marginBottom: '8px',
        }}
      >
        <span>{backtest.symbol}</span>
        <span>•</span>
        <span>{backtest.timeframe}</span>
      </div>

      {/* Progress Bar */}
      <div
        style={{
          width: '100%',
          height: '6px',
          borderRadius: '3px',
          background: '#374151',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${backtest.progress}%`,
            height: '100%',
            background: '#3b82f6',
            transition: 'width 0.3s',
          }}
        />
      </div>

      <div
        style={{
          marginTop: '4px',
          fontSize: '11px',
          color: '#6b7280',
          textAlign: 'right',
        }}
      >
        {backtest.progress}%
      </div>
    </div>
  );
};

export default RealTimeAnalyticsPage;
