/**
 * PlotlyEquityCurve - Interactive equity curve with Plotly.js
 *
 * Features:
 * - Interactive zoom and pan
 * - Hover tooltips with detailed info
 * - Multiple series (equity, drawdown, buy-hold)
 * - Customizable styling
 * - Export to PNG
 */

import React, { useMemo } from 'react';
import Plot from 'react-plotly.js';
import { useTheme } from '@mui/material';
import type { PlotParams } from 'react-plotly.js';

interface DataPoint {
  timestamp: number;
  equity?: number;
  drawdown?: number;
  buyHold?: number;
}

interface PlotlyEquityCurveProps {
  data: DataPoint[];
  height?: number;
  showDrawdown?: boolean;
  showBuyHold?: boolean;
  title?: string;
}

const PlotlyEquityCurve: React.FC<PlotlyEquityCurveProps> = ({
  data,
  height = 500,
  showDrawdown = true,
  showBuyHold = true,
  title = 'Капитал и просадка',
}) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  const plotData = useMemo<PlotParams['data']>(() => {
    const dates = data.map((d) => new Date(d.timestamp));

    const traces: PlotParams['data'] = [
      // Equity line
      {
        x: dates,
        y: data.map((d) => d.equity ?? 0),
        type: 'scatter',
        mode: 'lines',
        name: 'Капитал',
        line: {
          color: '#2563eb',
          width: 2,
        },
        hovertemplate:
          '<b>Капитал</b><br>' +
          'Дата: %{x|%d.%m.%Y %H:%M}<br>' +
          'Значение: %{y:.2f} USDT<br>' +
          '<extra></extra>',
      },
    ];

    // Drawdown area
    if (showDrawdown) {
      traces.push({
        x: dates,
        y: data.map((d) => d.drawdown ?? 0),
        type: 'scatter',
        mode: 'lines',
        name: 'Просадка',
        fill: 'tozeroy',
        fillcolor: 'rgba(239, 68, 68, 0.2)',
        line: {
          color: '#ef4444',
          width: 1,
        },
        yaxis: 'y2',
        hovertemplate:
          '<b>Просадка</b><br>' +
          'Дата: %{x|%d.%m.%Y %H:%M}<br>' +
          'Просадка: %{y:.2f}%<br>' +
          '<extra></extra>',
      });
    }

    // Buy & Hold comparison
    if (showBuyHold) {
      traces.push({
        x: dates,
        y: data.map((d) => d.buyHold ?? 0),
        type: 'scatter',
        mode: 'lines',
        name: 'Buy & Hold',
        line: {
          color: '#facc15',
          width: 1,
          dash: 'dash',
        },
        hovertemplate:
          '<b>Buy & Hold</b><br>' +
          'Дата: %{x|%d.%m.%Y %H:%M}<br>' +
          'Значение: %{y:.2f} USDT<br>' +
          '<extra></extra>',
      });
    }

    return traces;
  }, [data, showDrawdown, showBuyHold]);

  const layout = useMemo<Partial<PlotParams['layout']>>(
    () => ({
      title: {
        text: title,
        font: {
          size: 16,
          color: isDark ? '#e2e8f0' : '#0f172a',
        },
      },
      autosize: true,
      height,
      hovermode: 'x unified',
      showlegend: true,
      legend: {
        orientation: 'h',
        y: -0.15,
        x: 0.5,
        xanchor: 'center',
        font: {
          color: isDark ? '#cbd5e1' : '#475569',
        },
      },
      xaxis: {
        title: { text: 'Время' },
        gridcolor: isDark ? 'rgba(148, 163, 184, 0.1)' : 'rgba(15, 23, 42, 0.05)',
        color: isDark ? '#cbd5e1' : '#475569',
        showgrid: true,
        zeroline: false,
      },
      yaxis: {
        title: { text: 'Капитал (USDT)' },
        gridcolor: isDark ? 'rgba(148, 163, 184, 0.1)' : 'rgba(15, 23, 42, 0.05)',
        color: isDark ? '#cbd5e1' : '#475569',
        showgrid: true,
        zeroline: true,
        zerolinecolor: isDark ? 'rgba(148, 163, 184, 0.3)' : 'rgba(15, 23, 42, 0.2)',
      },
      yaxis2: {
        title: { text: showDrawdown ? 'Просадка (%)' : '' },
        overlaying: 'y',
        side: 'right',
        gridcolor: 'transparent',
        color: isDark ? '#fca5a5' : '#dc2626',
        showgrid: false,
        zeroline: true,
        zerolinecolor: isDark ? 'rgba(239, 68, 68, 0.3)' : 'rgba(239, 68, 68, 0.2)',
      },
      plot_bgcolor: isDark ? 'rgba(2, 8, 23, 0.6)' : '#ffffff',
      paper_bgcolor: isDark ? 'rgba(2, 8, 23, 0.8)' : '#fafafa',
      margin: {
        l: 60,
        r: showDrawdown ? 60 : 20,
        t: 60,
        b: 80,
      },
      dragmode: 'zoom',
    }),
    [isDark, height, showDrawdown, title]
  );

  const config: Partial<PlotParams['config']> = useMemo(
    () => ({
      responsive: true,
      displayModeBar: true,
      displaylogo: false,
      modeBarButtonsToRemove: ['lasso2d', 'select2d'],
      toImageButtonOptions: {
        format: 'png',
        filename: 'equity_curve',
        height: 1000,
        width: 1600,
        scale: 2,
      },
    }),
    []
  );

  if (data.length === 0) {
    return null;
  }

  return (
    <Plot
      data={plotData}
      layout={layout}
      config={config}
      style={{ width: '100%' }}
      useResizeHandler={true}
    />
  );
};

export default PlotlyEquityCurve;
