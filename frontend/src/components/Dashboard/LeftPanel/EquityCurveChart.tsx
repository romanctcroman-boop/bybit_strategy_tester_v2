import React, { useEffect, useRef } from 'react';
import { createChart, IChartApi, LineData } from 'lightweight-charts';
import './EquityCurveChart.css';

interface EquityCurveChartProps {
  data: Array<{ time: number; value: number }>;
  title?: string;
  height?: number;
}

const EquityCurveChart: React.FC<EquityCurveChartProps> = ({
  data,
  title = 'Equity Curve',
  height = 400,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<any>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Создаем chart
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: height,
      layout: {
        background: { color: 'rgba(0, 0, 51, 0.5)' },
        textColor: '#b0c0e0',
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.1)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.1)' },
      },
      crosshair: {
        mode: 1, // Normal crosshair
      },
      rightPriceScale: {
        borderColor: 'rgba(255, 255, 255, 0.2)',
      },
      timeScale: {
        borderColor: 'rgba(255, 255, 255, 0.2)',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    // Создаем line series (v5 API)
    const lineSeries = (chart as any).addLineSeries({
      color: '#4dabf7',
      lineWidth: 2,
      priceFormat: {
        type: 'price',
        precision: 2,
        minMove: 0.01,
      },
    });

    chartRef.current = chart;
    seriesRef.current = lineSeries;

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
      }
    };
  }, [height]);

  useEffect(() => {
    if (!seriesRef.current || data.length === 0) return;

    // Преобразуем timestamp в секунды (TradingView требует Unix timestamp в секундах)
    const chartData: LineData[] = data.map((point) => ({
      time: Math.floor(point.time / 1000) as any, // Convert ms to seconds
      value: point.value,
    }));

    seriesRef.current.setData(chartData);

    // Fit content
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  }, [data]);

  return (
    <div className="equity-curve-chart">
      <h3 className="chart-title">{title}</h3>
      <div ref={chartContainerRef} className="chart-container" />
      {data.length === 0 && (
        <div className="chart-no-data">
          <p>No data available</p>
        </div>
      )}
    </div>
  );
};

export default EquityCurveChart;
