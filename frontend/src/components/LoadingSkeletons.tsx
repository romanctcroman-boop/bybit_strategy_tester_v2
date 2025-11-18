/**
 * Loading Skeletons - Reusable skeleton components for loading states
 *
 * Based on Perplexity AI recommendations for trading platform UI.
 * Uses MUI Skeleton for consistent loading experience.
 *
 * Components:
 * - TableSkeleton: For data grids and tables
 * - ChartSkeleton: For chart containers
 * - CardSkeleton: For card-based layouts
 * - ListSkeleton: For list items
 * - MetricsSkeleton: For metrics/stats displays
 */

import React from 'react';
import { Skeleton, Box, Stack, Paper, Grid } from '@mui/material';

/**
 * Skeleton for data tables/grids
 */
export const TableSkeleton: React.FC<{ rows?: number }> = ({ rows = 5 }) => (
  <Box sx={{ width: '100%' }}>
    {/* Header */}
    <Skeleton variant="rectangular" width="100%" height={56} sx={{ mb: 1 }} />

    {/* Rows */}
    {Array.from({ length: rows }).map((_, index) => (
      <Skeleton key={index} variant="rectangular" width="100%" height={52} sx={{ mb: 0.5 }} />
    ))}
  </Box>
);

/**
 * Skeleton for charts (Plotly, TradingView, etc.)
 */
export const ChartSkeleton: React.FC<{ height?: number }> = ({ height = 400 }) => (
  <Paper
    elevation={0}
    sx={{
      width: '100%',
      height,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      bgcolor: 'background.paper',
      border: 1,
      borderColor: 'divider',
      borderRadius: 2,
    }}
  >
    <Stack spacing={2} alignItems="center" sx={{ width: '90%', height: '85%' }}>
      {/* Chart title */}
      <Skeleton variant="text" width="40%" height={32} />

      {/* Chart area */}
      <Box sx={{ width: '100%', flex: 1, position: 'relative' }}>
        <Skeleton variant="rectangular" width="100%" height="100%" sx={{ borderRadius: 1 }} />

        {/* Simulated chart lines */}
        <Box
          sx={{
            position: 'absolute',
            top: '20%',
            left: '10%',
            right: '10%',
            height: '60%',
            display: 'flex',
            alignItems: 'flex-end',
            gap: 1,
          }}
        >
          {[40, 70, 50, 80, 60, 90, 75, 85].map((height, i) => (
            <Skeleton
              key={i}
              variant="rectangular"
              width="10%"
              height={`${height}%`}
              animation="wave"
            />
          ))}
        </Box>
      </Box>

      {/* Legend */}
      <Stack direction="row" spacing={3}>
        <Skeleton variant="text" width={80} />
        <Skeleton variant="text" width={80} />
        <Skeleton variant="text" width={80} />
      </Stack>
    </Stack>
  </Paper>
);

/**
 * Skeleton for card-based content
 */
export const CardSkeleton: React.FC<{ count?: number }> = ({ count = 3 }) => (
  <Grid container spacing={2}>
    {Array.from({ length: count }).map((_, index) => (
      <Grid item xs={12} sm={6} md={4} key={index}>
        <Paper elevation={2} sx={{ p: 2 }}>
          <Skeleton variant="text" width="60%" height={32} sx={{ mb: 1 }} />
          <Skeleton variant="text" width="40%" />
          <Skeleton
            variant="rectangular"
            width="100%"
            height={100}
            sx={{ mt: 2, borderRadius: 1 }}
          />
          <Stack direction="row" spacing={2} sx={{ mt: 2 }}>
            <Skeleton variant="rectangular" width="48%" height={36} />
            <Skeleton variant="rectangular" width="48%" height={36} />
          </Stack>
        </Paper>
      </Grid>
    ))}
  </Grid>
);

/**
 * Skeleton for list items
 */
export const ListSkeleton: React.FC<{ items?: number }> = ({ items = 8 }) => (
  <Stack spacing={1.5}>
    {Array.from({ length: items }).map((_, index) => (
      <Paper key={index} elevation={0} sx={{ p: 2, border: 1, borderColor: 'divider' }}>
        <Stack direction="row" spacing={2} alignItems="center">
          <Skeleton variant="circular" width={40} height={40} />
          <Box sx={{ flex: 1 }}>
            <Skeleton variant="text" width="70%" />
            <Skeleton variant="text" width="40%" />
          </Box>
          <Skeleton variant="rectangular" width={80} height={32} />
        </Stack>
      </Paper>
    ))}
  </Stack>
);

/**
 * Skeleton for metrics/stats displays
 */
export const MetricsSkeleton: React.FC = () => (
  <Grid container spacing={2}>
    {Array.from({ length: 4 }).map((_, index) => (
      <Grid item xs={12} sm={6} md={3} key={index}>
        <Paper
          elevation={0}
          sx={{
            p: 2,
            textAlign: 'center',
            border: 1,
            borderColor: 'divider',
            borderRadius: 2,
          }}
        >
          <Skeleton variant="text" width="60%" sx={{ mx: 'auto', mb: 1 }} />
          <Skeleton variant="text" width="80%" height={40} sx={{ mx: 'auto' }} />
          <Skeleton variant="text" width="40%" sx={{ mx: 'auto', mt: 1 }} />
        </Paper>
      </Grid>
    ))}
  </Grid>
);

/**
 * Skeleton for backtest list (trading-specific)
 */
export const BacktestListSkeleton: React.FC<{ count?: number }> = ({ count = 5 }) => (
  <Stack spacing={2}>
    {Array.from({ length: count }).map((_, index) => (
      <Paper key={index} elevation={1} sx={{ p: 3 }}>
        <Stack direction="row" spacing={3} alignItems="center">
          {/* Strategy name */}
          <Box sx={{ flex: 1 }}>
            <Skeleton variant="text" width="40%" height={28} />
            <Skeleton variant="text" width="60%" />
          </Box>

          {/* Metrics */}
          <Stack direction="row" spacing={4}>
            <Box>
              <Skeleton variant="text" width={60} />
              <Skeleton variant="text" width={80} height={32} />
            </Box>
            <Box>
              <Skeleton variant="text" width={60} />
              <Skeleton variant="text" width={80} height={32} />
            </Box>
            <Box>
              <Skeleton variant="text" width={60} />
              <Skeleton variant="text" width={80} height={32} />
            </Box>
          </Stack>

          {/* Actions */}
          <Stack direction="row" spacing={1}>
            <Skeleton variant="rectangular" width={80} height={36} />
            <Skeleton variant="rectangular" width={80} height={36} />
          </Stack>
        </Stack>
      </Paper>
    ))}
  </Stack>
);

export default {
  TableSkeleton,
  ChartSkeleton,
  CardSkeleton,
  ListSkeleton,
  MetricsSkeleton,
  BacktestListSkeleton,
};
