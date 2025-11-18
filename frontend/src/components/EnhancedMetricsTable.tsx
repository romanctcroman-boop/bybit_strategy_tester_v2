/**
 * EnhancedMetricsTable - Improved metrics visualization with visual indicators
 *
 * Features:
 * - Color-coded values (positive/negative)
 * - Progress bars for percentages
 * - Sparkline charts for trends
 * - Comparison indicators
 * - Tooltips with additional info
 */

import React from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Paper,
  Typography,
  Box,
  LinearProgress,
  Chip,
  Stack,
  Tooltip,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Remove as NeutralIcon,
} from '@mui/icons-material';

export interface MetricRow {
  label: string;
  value: number | null;
  format: 'usd' | 'percent' | 'plain' | 'ratio';
  benchmark?: number; // For comparison
  tooltip?: string;
  showTrend?: boolean;
}

export interface MetricGroup {
  title: string;
  metrics: MetricRow[];
}

interface EnhancedMetricsTableProps {
  groups: MetricGroup[];
}

const formatValue = (value: number | null, format: string): string => {
  if (value === null || value === undefined) return '—';

  switch (format) {
    case 'usd':
      return `${value >= 0 ? '+' : ''}${value.toFixed(2)} USDT`;
    case 'percent':
      return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
    case 'ratio':
      return value.toFixed(3);
    case 'plain':
      return value.toFixed(0);
    default:
      return value.toString();
  }
};

const getValueColor = (value: number | null, inverse = false): string => {
  if (value === null || value === undefined) return 'text.secondary';

  const isPositive = value > 0;
  const isNegative = value < 0;

  if (inverse) {
    if (isPositive) return 'error.main';
    if (isNegative) return 'success.main';
  } else {
    if (isPositive) return 'success.main';
    if (isNegative) return 'error.main';
  }

  return 'text.primary';
};

const getTrendIcon = (value: number | null, benchmark?: number) => {
  if (value === null || benchmark === undefined) return null;

  if (value > benchmark) {
    return <TrendingUpIcon fontSize="small" color="success" />;
  } else if (value < benchmark) {
    return <TrendingDownIcon fontSize="small" color="error" />;
  } else {
    return <NeutralIcon fontSize="small" color="disabled" />;
  }
};

const MetricProgressBar: React.FC<{ value: number; max?: number }> = ({ value, max = 100 }) => {
  const percentage = Math.min(Math.abs(value), max);
  const color = value >= 0 ? 'success' : 'error';

  return (
    <Box sx={{ width: '100%', mr: 1 }}>
      <LinearProgress
        variant="determinate"
        value={percentage}
        color={color}
        sx={{ height: 8, borderRadius: 1 }}
      />
    </Box>
  );
};

const EnhancedMetricsTable: React.FC<EnhancedMetricsTableProps> = ({ groups }) => {
  return (
    <Stack spacing={3}>
      {groups.map((group, groupIndex) => (
        <Paper key={groupIndex} sx={{ p: 2, borderRadius: 2 }}>
          <Typography variant="h6" sx={{ mb: 2 }}>
            {group.title}
          </Typography>

          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell width="40%">Метрика</TableCell>
                <TableCell width="30%">Значение</TableCell>
                <TableCell width="30%">Визуализация</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {group.metrics.map((metric, metricIndex) => {
                const isPercentage = metric.format === 'percent';
                const showProgress = isPercentage && metric.value !== null;
                const valueColor = getValueColor(
                  metric.value,
                  metric.label.includes('просадка') || metric.label.includes('drawdown')
                );

                return (
                  <TableRow key={metricIndex} hover>
                    <TableCell>
                      <Stack direction="row" spacing={1} alignItems="center">
                        <Typography variant="body2">{metric.label}</Typography>
                        {metric.tooltip && (
                          <Tooltip title={metric.tooltip} arrow>
                            <Box
                              component="span"
                              sx={{
                                width: 16,
                                height: 16,
                                borderRadius: '50%',
                                border: '1px solid',
                                borderColor: 'text.secondary',
                                display: 'inline-flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: '0.7rem',
                                color: 'text.secondary',
                                cursor: 'help',
                              }}
                            >
                              ?
                            </Box>
                          </Tooltip>
                        )}
                      </Stack>
                    </TableCell>

                    <TableCell>
                      <Stack direction="row" spacing={1} alignItems="center">
                        <Typography variant="body1" fontWeight={600} sx={{ color: valueColor }}>
                          {formatValue(metric.value, metric.format)}
                        </Typography>

                        {metric.showTrend && metric.benchmark !== undefined && (
                          <Box>{getTrendIcon(metric.value, metric.benchmark)}</Box>
                        )}

                        {metric.benchmark !== undefined && metric.value !== null && (
                          <Chip
                            label={`vs ${metric.benchmark.toFixed(1)}%`}
                            size="small"
                            variant="outlined"
                            sx={{ height: 20, fontSize: '0.7rem' }}
                          />
                        )}
                      </Stack>
                    </TableCell>

                    <TableCell>
                      {showProgress && metric.value !== null && (
                        <MetricProgressBar value={metric.value} max={100} />
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Paper>
      ))}
    </Stack>
  );
};

export default EnhancedMetricsTable;
