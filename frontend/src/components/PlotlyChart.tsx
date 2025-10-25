import React, { useEffect, useRef } from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';
import type { PlotlyHTMLElement } from 'plotly.js-basic-dist-min';

interface PlotlyChartProps {
  /**
   * JSON content from backend (Plotly figure as JSON string)
   */
  plotlyJson: string | null;
  /**
   * Optional height in pixels
   */
  height?: number;
  /**
   * Loading state
   */
  loading?: boolean;
  /**
   * Error message
   */
  error?: string;
}

/**
 * Generic Plotly Chart Component
 *
 * Renders interactive Plotly charts from JSON received from backend.
 * Uses dynamic import to avoid bundling Plotly.js in main bundle.
 */
const PlotlyChart: React.FC<PlotlyChartProps> = ({
  plotlyJson,
  height = 400,
  loading = false,
  error = null,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const plotRef = useRef<PlotlyHTMLElement | null>(null);

  useEffect(() => {
    if (!plotlyJson || !containerRef.current) {
      return;
    }

    const containerElement = containerRef.current;

    // Dynamic import Plotly to reduce bundle size
    import('plotly.js-basic-dist-min')
      .then((Plotly) => {
        if (!containerElement) return;

        try {
          // Parse JSON from backend
          const figure = JSON.parse(plotlyJson);

          // Render or update plot
          if (plotRef.current) {
            // Update existing plot
            Plotly.react(containerElement, figure.data, figure.layout || {}, {
              responsive: true,
            });
          } else {
            // Create new plot
            Plotly.newPlot(containerElement, figure.data, figure.layout || {}, {
              responsive: true,
              displayModeBar: true,
              modeBarButtonsToRemove: ['toImage'],
              displaylogo: false,
            }).then((plot: PlotlyHTMLElement) => {
              plotRef.current = plot;
            });
          }
        } catch (err) {
          console.error('Error rendering Plotly chart:', err);
        }
      })
      .catch((err) => {
        console.error('Error loading Plotly:', err);
      });

    // Cleanup on unmount
    return () => {
      if (plotRef.current && containerElement) {
        import('plotly.js-basic-dist-min')
          .then((Plotly) => {
            Plotly.purge(containerElement);
          })
          .catch((err) => {
            console.error('Error cleaning up Plotly:', err);
          });
        plotRef.current = null;
      }
    };
  }, [plotlyJson]);

  if (loading) {
    return (
      <Box display="flex" alignItems="center" justifyContent="center" height={height}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box display="flex" alignItems="center" justifyContent="center" height={height}>
        <Typography color="error">{error}</Typography>
      </Box>
    );
  }

  if (!plotlyJson) {
    return (
      <Box display="flex" alignItems="center" justifyContent="center" height={height}>
        <Typography color="text.secondary">Нет данных для визуализации</Typography>
      </Box>
    );
  }

  return (
    <Box
      ref={containerRef}
      sx={{
        width: '100%',
        height: height,
        '& .plotly': {
          width: '100%',
          height: '100%',
        },
      }}
    />
  );
};

export default PlotlyChart;
