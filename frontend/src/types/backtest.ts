/**
 * Backtest Type Definitions
 *
 * Строгая типизация для форм и конфигураций бэктеста
 */

export interface BollingerParams {
  bb_period: number;
  bb_std_dev: number;
  entry_threshold_pct: number;
  stop_loss_pct: number;
  max_holding_bars: number;
}

export interface EMAParams {
  fast_ema: number;
  slow_ema: number;
  direction: 'long' | 'short' | 'both';
}

export interface RSIParams {
  rsi_period: number;
  rsi_overbought: number;
  rsi_oversold: number;
  direction: 'long' | 'short' | 'both';
}

export type StrategyParams = BollingerParams | EMAParams | RSIParams;

export interface Strategy {
  id: number;
  name: string;
  type: string;
  description?: string;
  default_params?: Record<string, any>;
}

export interface BacktestConfig {
  symbol: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  commission: number;
  leverage: number;
  strategy_config: {
    type: string;
    [key: string]: any;
  };
}

export interface BacktestResponse {
  id: number;
  status: string;
  created_at: string;
  symbol: string;
  timeframe: string;
  strategy_id?: number;
}
