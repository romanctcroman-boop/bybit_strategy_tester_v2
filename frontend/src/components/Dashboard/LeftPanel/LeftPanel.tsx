import React from 'react';
import {
  useWFOResults,
  calculateAggregateMetrics,
  calculateEquityCurve,
  WFOPeriod,
} from '../../../hooks/useWFOResults';
import EquityCurveChart from './EquityCurveChart';
import MetricsCards from './MetricsCards';
import './LeftPanel.css';

interface LeftPanelProps {
  strategy?: string;
}

const WFOPeriodTable: React.FC<{ periods: WFOPeriod[]; loading?: boolean }> = ({
  periods,
  loading,
}) => {
  if (loading) {
    return (
      <div className="wfo-table-container">
        <h3>WFO Period Breakdown</h3>
        <div className="table-loading">Loading...</div>
      </div>
    );
  }

  return (
    <div className="wfo-table-container">
      <h3>WFO Period Breakdown ({periods.length} Cycles)</h3>
      <div className="table-wrapper">
        <table className="wfo-table">
          <thead>
            <tr>
              <th>Period</th>
              <th>Return %</th>
              <th>Sharpe</th>
              <th>Win Rate</th>
              <th>Trades</th>
              <th>Profit Factor</th>
            </tr>
          </thead>
          <tbody>
            {periods.map((period) => (
              <tr key={period.period}>
                <td>{period.period}</td>
                <td className={period.oos_metrics.oos_return > 0 ? 'positive' : 'negative'}>
                  {period.oos_metrics.oos_return >= 0 ? '+' : ''}
                  {period.oos_metrics.oos_return.toFixed(2)}%
                </td>
                <td>{period.oos_metrics.oos_sharpe.toFixed(2)}</td>
                <td>{(period.oos_metrics.oos_win_rate * 100).toFixed(1)}%</td>
                <td>{period.oos_metrics.oos_trades}</td>
                <td className={period.oos_metrics.oos_profit_factor > 1 ? 'positive' : 'negative'}>
                  {period.oos_metrics.oos_profit_factor.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const LeftPanel: React.FC<LeftPanelProps> = ({ strategy = 'sr_mean_reversion' }) => {
  const { data, loading, error } = useWFOResults(strategy);

  if (error) {
    return (
      <div className="left-panel">
        <div className="error-message">
          <h3>Error Loading Data</h3>
          <p>{error}</p>
          <p>Strategy: {strategy}</p>
        </div>
      </div>
    );
  }

  const equityCurve = data ? calculateEquityCurve(data.periods) : [];
  const metrics = data ? calculateAggregateMetrics(data.periods) : null;

  return (
    <div className="left-panel">
      <EquityCurveChart
        data={equityCurve}
        title={`Equity Curve - ${data?.metadata.strategy || 'Loading...'}`}
      />
      <MetricsCards metrics={metrics} loading={loading} />
      <WFOPeriodTable periods={data?.periods || []} loading={loading} />
    </div>
  );
};

export default LeftPanel;
