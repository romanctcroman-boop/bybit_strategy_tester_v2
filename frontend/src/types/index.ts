/**
 * TypeScript Type Definitions for Bybit Strategy Tester
 *
 * Defines all data structures used across the frontend application
 */

// ============================================================================
// COMMON TYPES
// ============================================================================

export type TimeFrame = '1' | '3' | '5' | '15' | '30' | '60' | '120' | '240' | 'D' | 'W';

export type OptimizationMethod = 'grid_search' | 'walk_forward' | 'bayesian';

export type TaskStatus =
  | 'PENDING'
  | 'STARTED'
  | 'PROGRESS'
  | 'SUCCESS'
  | 'FAILURE'
  | 'RETRY'
  | 'REVOKED';

// ============================================================================
// MARKET DATA
// ============================================================================

export interface Candle {
  timestamp: string | Date;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// ============================================================================
// STRATEGY
// ============================================================================

export interface StrategyParameter {
  name: string;
  type: 'int' | 'float' | 'bool' | 'string';
  min?: number;
  max?: number;
  step?: number;
  default?: any;
  description?: string;
}

export interface Strategy {
  id: string;
  name: string;
  description?: string;
  parameters: StrategyParameter[];
  category?: string;
}

// ============================================================================
// BACKTEST
// ============================================================================

export interface BacktestMetrics {
  total_return: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  win_rate: number;
  profit_factor: number;
  total_trades: number;
  avg_trade_return: number;
  avg_win: number;
  avg_loss: number;
  final_capital: number;
}

export interface Trade {
  id: number;
  entry_time: string;
  exit_time?: string;
  side: 'long' | 'short';
  entry_price: number;
  exit_price?: number;
  quantity: number;
  pnl?: number;
  pnl_pct?: number;
  status: 'open' | 'closed';
  exit_reason?: string;
}

export interface BacktestResult {
  id: string;
  strategy_name: string;
  symbol: string;
  timeframe: TimeFrame;
  start_date: string;
  end_date: string;
  initial_capital: number;
  metrics: BacktestMetrics;
  trades: Trade[];
  equity_curve: Array<{ timestamp: string; value: number }>;
  status: 'pending' | 'running' | 'completed' | 'failed';
  error?: string;
  created_at: string;
}

// ============================================================================
// OPTIMIZATION
// ============================================================================

export interface ParameterRange {
  min: number;
  max: number;
  step: number;
}

export interface BayesianParameter {
  type: 'int' | 'float' | 'categorical';
  low?: number;
  high?: number;
  step?: number;
  log?: boolean;
  choices?: string[];
}

export interface OptimizationRequest {
  method: OptimizationMethod;
  strategy_class: string;
  symbol: string;
  timeframe: TimeFrame;
  start_date: string;
  end_date: string;
  initial_capital: number;
  commission: number;
  parameters: Record<string, ParameterRange | BayesianParameter>;
  metric?: string;

  // Grid Search specific
  max_combinations?: number;

  // Walk-Forward specific
  in_sample_period?: number;
  out_sample_period?: number;
  step?: number;

  // Bayesian specific
  n_trials?: number;
  direction?: 'maximize' | 'minimize';
  n_jobs?: number;
  random_state?: number;
}

export interface OptimizationResult {
  params: Record<string, any>;
  score: number;
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  total_trades: number;
}

export interface WalkForwardWindow {
  window_id: number;
  is_start: string;
  is_end: string;
  oos_start: string;
  oos_end: string;
  best_params?: Record<string, any>;
  is_metrics?: BacktestMetrics;
  oos_metrics?: BacktestMetrics;
}

export interface OptimizationProgress {
  current: number;
  total: number;
  percent: number;
  best_score: number;
  best_params: Record<string, any>;
  message?: string;
}

export interface OptimizationTaskResponse {
  task_id: string;
  status: TaskStatus;
  method: OptimizationMethod;
  created_at: string;
  message?: string;
}

export interface OptimizationResultsResponse {
  task_id: string;
  status: TaskStatus;
  method: OptimizationMethod;
  best_params: Record<string, any>;
  best_score: number;
  results: OptimizationResult[];
  walk_forward_windows?: WalkForwardWindow[];
  parameter_importance?: Record<string, number>;
  total_combinations?: number;
  completed_combinations?: number;
  started_at?: string;
  completed_at?: string;
  error?: string;
}

// ============================================================================
// WEBSOCKET
// ============================================================================

export interface WebSocketMessage {
  type: 'progress' | 'result' | 'error' | 'ping' | 'pong';
  task_id?: string;
  data?: any;
  error?: string;
  timestamp: string;
}

export interface ProgressUpdate extends WebSocketMessage {
  type: 'progress';
  data: OptimizationProgress;
}

// ============================================================================
// UI STATE
// ============================================================================

export interface ChartData {
  candles: Candle[];
  indicators?: Record<string, number[]>;
  trades?: Trade[];
}

export interface AppSettings {
  theme: 'light' | 'dark';
  apiBaseUrl: string;
  wsBaseUrl: string;
  autoConnect: boolean;
  notifications: boolean;
}

export interface AppError {
  id: string;
  message: string;
  details?: string;
  timestamp: Date;
  severity: 'error' | 'warning' | 'info';
}
