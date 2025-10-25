import React, { useEffect, useState } from 'react';
import {
  Box,
  Paper,
  Stack,
  Typography,
  CircularProgress,
  Alert,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import PlotlyChart from '../components/PlotlyChart';
import { BacktestsApi } from '../services/api';
import { useNotify } from './NotificationsProvider';

interface ChartsTabProps {
  backtestId: number;
}

type ChartType = 'equity' | 'drawdown' | 'pnl';

/**
 * Charts Tab Component (ТЗ 3.7.2)
 *
 * Displays interactive Plotly charts:
 * - Equity Curve (with optional drawdown subplot)
 * - Drawdown Overlay (dual y-axis)
 * - PnL Distribution (histogram)
 */
const ChartsTab: React.FC<ChartsTabProps> = ({ backtestId }) => {
  const notify = useNotify();

  // Chart data states
  const [equityData, setEquityData] = useState<string | null>(null);
  const [drawdownData, setDrawdownData] = useState<string | null>(null);
  const [pnlData, setPnlData] = useState<string | null>(null);

  // Loading states
  const [loadingEquity, setLoadingEquity] = useState(false);
  const [loadingDrawdown, setLoadingDrawdown] = useState(false);
  const [loadingPnl, setLoadingPnl] = useState(false);

  // Error states
  const [errorEquity, setErrorEquity] = useState<string>('');
  const [errorDrawdown, setErrorDrawdown] = useState<string>('');
  const [errorPnl, setErrorPnl] = useState<string>('');

  // Options
  const [showDrawdown, setShowDrawdown] = useState(true);
  const [pnlBins, setPnlBins] = useState(30);
  const [selectedChart, setSelectedChart] = useState<ChartType | 'all'>('all');

  // Fetch equity curve
  const fetchEquityCurve = async () => {
    setLoadingEquity(true);
    setErrorEquity('');
    try {
      const response = await BacktestsApi.getEquityCurve(backtestId, showDrawdown);
      setEquityData(response.plotly_json);
    } catch (error: any) {
      const message = error?.friendlyMessage || 'Failed to load equity curve';
      setErrorEquity(message);
      notify({ message, severity: 'error' });
    } finally {
      setLoadingEquity(false);
    }
  };

  // Fetch drawdown overlay
  const fetchDrawdownOverlay = async () => {
    setLoadingDrawdown(true);
    setErrorDrawdown('');
    try {
      const response = await BacktestsApi.getDrawdownOverlay(backtestId);
      setDrawdownData(response.plotly_json);
    } catch (error: any) {
      const message = error?.friendlyMessage || 'Failed to load drawdown overlay';
      setErrorDrawdown(message);
      notify({ message, severity: 'error' });
    } finally {
      setLoadingDrawdown(false);
    }
  };

  // Fetch PnL distribution
  const fetchPnlDistribution = async () => {
    setLoadingPnl(true);
    setErrorPnl('');
    try {
      const response = await BacktestsApi.getPnlDistribution(backtestId, pnlBins);
      setPnlData(response.plotly_json);
    } catch (error: any) {
      const message = error?.friendlyMessage || 'Failed to load PnL distribution';
      setErrorPnl(message);
      notify({ message, severity: 'error' });
    } finally {
      setLoadingPnl(false);
    }
  };

  // Fetch all charts on mount
  useEffect(() => {
    if (backtestId) {
      fetchEquityCurve();
      fetchDrawdownOverlay();
      fetchPnlDistribution();
    }
  }, [backtestId]);

  // Refetch equity curve when showDrawdown changes
  useEffect(() => {
    if (backtestId && equityData !== null) {
      fetchEquityCurve();
    }
  }, [showDrawdown]);

  // Refetch PnL when bins change
  useEffect(() => {
    if (backtestId && pnlData !== null) {
      fetchPnlDistribution();
    }
  }, [pnlBins]);

  const handleChartTypeChange = (
    _: React.MouseEvent<HTMLElement>,
    newValue: ChartType | 'all' | null
  ) => {
    if (newValue) {
      setSelectedChart(newValue);
    }
  };

  const shouldShowChart = (type: ChartType) => {
    return selectedChart === 'all' || selectedChart === type;
  };

  return (
    <Stack spacing={3} sx={{ mt: 2 }}>
      {/* Chart selector */}
      <Paper sx={{ p: 2 }}>
        <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
          <Typography variant="subtitle2">Выбор графиков:</Typography>
          <ToggleButtonGroup
            size="small"
            color="primary"
            exclusive
            value={selectedChart}
            onChange={handleChartTypeChange}
          >
            <ToggleButton value="all">Все графики</ToggleButton>
            <ToggleButton value="equity">Equity Curve</ToggleButton>
            <ToggleButton value="drawdown">Drawdown Overlay</ToggleButton>
            <ToggleButton value="pnl">PnL Distribution</ToggleButton>
          </ToggleButtonGroup>
        </Stack>
      </Paper>

      {/* Equity Curve */}
      {shouldShowChart('equity') && (
        <Paper sx={{ p: 3, borderRadius: 2 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
            <Typography variant="h6">Equity Curve</Typography>
            <ToggleButton
              size="small"
              value="check"
              selected={showDrawdown}
              onChange={() => setShowDrawdown(!showDrawdown)}
            >
              Show Drawdown
            </ToggleButton>
          </Stack>

          {errorEquity ? (
            <Alert severity="error">{errorEquity}</Alert>
          ) : (
            <PlotlyChart plotlyJson={equityData} height={450} loading={loadingEquity} />
          )}
        </Paper>
      )}

      {/* Drawdown Overlay */}
      {shouldShowChart('drawdown') && (
        <Paper sx={{ p: 3, borderRadius: 2 }}>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Drawdown Overlay
          </Typography>

          {errorDrawdown ? (
            <Alert severity="error">{errorDrawdown}</Alert>
          ) : (
            <PlotlyChart plotlyJson={drawdownData} height={450} loading={loadingDrawdown} />
          )}
        </Paper>
      )}

      {/* PnL Distribution */}
      {shouldShowChart('pnl') && (
        <Paper sx={{ p: 3, borderRadius: 2 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
            <Typography variant="h6">PnL Distribution</Typography>
            <ToggleButtonGroup
              size="small"
              color="primary"
              exclusive
              value={pnlBins}
              onChange={(_, newValue) => {
                if (newValue) setPnlBins(newValue);
              }}
            >
              <ToggleButton value={20}>20 bins</ToggleButton>
              <ToggleButton value={30}>30 bins</ToggleButton>
              <ToggleButton value={50}>50 bins</ToggleButton>
            </ToggleButtonGroup>
          </Stack>

          {errorPnl ? (
            <Alert severity="error">{errorPnl}</Alert>
          ) : (
            <PlotlyChart plotlyJson={pnlData} height={400} loading={loadingPnl} />
          )}
        </Paper>
      )}

      {/* Help text */}
      <Paper sx={{ p: 2, backgroundColor: 'action.hover' }}>
        <Typography variant="body2" color="text.secondary">
          💡 <strong>Подсказка:</strong> Все графики интерактивные — можно масштабировать (zoom),
          перемещать (pan), и наводить курсор (hover) для детальной информации.
        </Typography>
      </Paper>
    </Stack>
  );
};

export default ChartsTab;
