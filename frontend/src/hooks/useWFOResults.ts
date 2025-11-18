import { useState, useEffect } from 'react';

export interface WFOPeriod {
  period: number;
  is_start: number;
  is_end: number;
  oos_start: number;
  oos_end: number;
  best_params: {
    lookback_bars?: number;
    level_tolerance_pct?: number;
    entry_tolerance_pct?: number;
    stop_loss_pct?: number;
    max_holding_bars?: number;
    ema_fast?: number;
    ema_slow?: number;
    bb_period?: number;
    bb_std?: number;
    rsi_period?: number;
    rsi_oversold?: number;
    rsi_overbought?: number;
  };
  oos_metrics: {
    oos_return: number;
    oos_sharpe: number;
    oos_trades: number;
    oos_win_rate: number;
    oos_max_dd: number;
    oos_profit_factor: number;
    oos_avg_trade?: number;
    oos_best_trade?: number;
    oos_worst_trade?: number;
  };
}

export interface WFOResults {
  metadata: {
    strategy: string;
    symbol: string;
    timeframe: string;
    total_periods: number;
    execution_time_minutes?: number;
    data_start?: string;
    data_end?: string;
  };
  periods: WFOPeriod[];
  aggregate_metrics?: {
    avg_oos_return: number;
    avg_sharpe: number;
    avg_win_rate: number;
    total_trades: number;
    positive_periods: number;
    negative_periods: number;
  };
}

export interface AggregateMetrics {
  avg_return: number;
  avg_sharpe: number;
  avg_win_rate: number;
  avg_max_dd: number;
  avg_profit_factor: number;
  total_trades: number;
  positive_periods: number;
  negative_periods: number;
}

/**
 * Hook для загрузки WFO результатов из JSON файлов
 * Поддерживает автоматическое обновление при изменении файлов
 */
export const useWFOResults = (strategy: string, autoRefresh: boolean = false) => {
  const [data, setData] = useState<WFOResults | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const loadResults = async () => {
    setLoading(true);
    setError(null);

    try {
      // Определяем имя файла на основе стратегии
      const fileMap: Record<string, string> = {
        ema_crossover: 'wfo_ema_22_cycles',
        sr_mean_reversion: 'wfo_sr_22_cycles',
        bb_mean_reversion: 'wfo_bb_22_cycles',
        sr_rsi: 'wfo_sr_rsi_22_cycles',
      };

      const fileName = fileMap[strategy];
      if (!fileName) {
        throw new Error(`Unknown strategy: ${strategy}`);
      }

      // Пробуем загрузить файл из /results/
      // Добавляем timestamp для cache busting при autoRefresh
      const cacheBuster = autoRefresh ? `?t=${Date.now()}` : '';
      const response = await fetch(`/results/${fileName}_20251029_184838.json${cacheBuster}`);

      if (!response.ok) {
        // Если файл не найден, пробуем без timestamp
        const fallbackResponse = await fetch(`/results/${fileName}.json${cacheBuster}`);
        if (!fallbackResponse.ok) {
          throw new Error(`Failed to load WFO results for ${strategy}`);
        }
        const json = await fallbackResponse.json();
        setData(json);
      } else {
        const json = await response.json();
        setData(json);
      }
    } catch (err) {
      console.error('Error loading WFO results:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadResults();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strategy, refreshTrigger]);

  // Auto-refresh mechanism
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      setRefreshTrigger((prev) => prev + 1);
    }, 10000); // Refresh every 10 seconds

    return () => clearInterval(interval);
  }, [autoRefresh]);

  const refresh = () => {
    setRefreshTrigger((prev) => prev + 1);
  };

  return { data, loading, error, refresh };
};

/**
 * Вычисляет агрегированные метрики из WFO периодов
 */
export const calculateAggregateMetrics = (periods: WFOPeriod[]): AggregateMetrics => {
  if (periods.length === 0) {
    return {
      avg_return: 0,
      avg_sharpe: 0,
      avg_win_rate: 0,
      avg_max_dd: 0,
      avg_profit_factor: 0,
      total_trades: 0,
      positive_periods: 0,
      negative_periods: 0,
    };
  }

  const totalReturn = periods.reduce((sum, p) => sum + p.oos_metrics.oos_return, 0);
  const totalSharpe = periods.reduce((sum, p) => sum + p.oos_metrics.oos_sharpe, 0);
  const totalWinRate = periods.reduce((sum, p) => sum + p.oos_metrics.oos_win_rate, 0);
  const totalMaxDD = periods.reduce((sum, p) => sum + p.oos_metrics.oos_max_dd, 0);
  const totalPF = periods.reduce((sum, p) => sum + p.oos_metrics.oos_profit_factor, 0);
  const totalTrades = periods.reduce((sum, p) => sum + p.oos_metrics.oos_trades, 0);

  const positivePeriods = periods.filter((p) => p.oos_metrics.oos_return > 0).length;
  const negativePeriods = periods.filter((p) => p.oos_metrics.oos_return <= 0).length;

  return {
    avg_return: totalReturn / periods.length,
    avg_sharpe: totalSharpe / periods.length,
    avg_win_rate: totalWinRate / periods.length,
    avg_max_dd: totalMaxDD / periods.length,
    avg_profit_factor: totalPF / periods.length,
    total_trades: totalTrades,
    positive_periods: positivePeriods,
    negative_periods: negativePeriods,
  };
};

/**
 * Преобразует WFO периоды в данные для equity curve
 */
export const calculateEquityCurve = (
  periods: WFOPeriod[]
): Array<{ time: number; value: number }> => {
  let cumulative = 100; // Начинаем с $100
  const curve: Array<{ time: number; value: number }> = [
    { time: periods[0]?.oos_start || Date.now(), value: 100 },
  ];

  periods.forEach((period) => {
    const periodReturn = period.oos_metrics.oos_return / 100; // Конвертируем % в decimal
    cumulative = cumulative * (1 + periodReturn);
    curve.push({
      time: period.oos_end,
      value: cumulative,
    });
  });

  return curve;
};
