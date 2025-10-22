// API types for frontend Level-2

export interface Strategy {
  id: number;
  name: string;
  description?: string;
  strategy_type: string;
  config: Record<string, any>;
  is_active: boolean;
  created_at?: string; // ISO8601 UTC
  updated_at?: string;
}

export interface Backtest {
  id: number;
  strategy_id: number;
  symbol: string;
  timeframe: string;
  start_date: string; // ISO8601
  end_date: string;
  initial_capital: number;
  leverage?: number;
  commission?: number;
  config?: Record<string, any>;
  status: 'pending' | 'running' | 'completed' | 'failed';
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  final_capital?: number;
  metrics?: Record<string, number>;
}

export interface Trade {
  id: number;
  backtest_id: number;
  entry_time: string;
  exit_time?: string;
  price: number;
  qty: number;
  side: 'buy' | 'sell';
  pnl?: number;
  created_at?: string;
}

export interface MarketDataPoint {
  id: number;
  symbol: string;
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export type ApiListResponse<T> = { items: T[]; total?: number };

// ======================
// Optimizations (Level-2)
// ======================

export interface Optimization {
  id: number;
  strategy_id: number;
  optimization_type: string; // grid_search | walk_forward | bayesian
  symbol: string;
  timeframe: string;
  start_date?: string; // ISO 8601 UTC
  end_date?: string;   // ISO 8601 UTC
  param_ranges?: Record<string, any>;
  metric: string;
  initial_capital: number;
  total_combinations: number;
  status: string; // pending | queued | running | completed | failed
  created_at?: string;
  updated_at?: string;
  started_at?: string;
  completed_at?: string;
  best_params?: Record<string, any>;
  best_score?: number;
  results?: Record<string, any>;
}

export interface OptimizationResult {
  id: number;
  optimization_id: number;
  params: Record<string, any>;
  score: number;
  total_return?: number;
  sharpe_ratio?: number;
  max_drawdown?: number;
  win_rate?: number;
  total_trades?: number;
  metrics?: Record<string, any>;
}

export type OptimizationEnqueueResponse = {
  task_id: string;
  optimization_id: number;
  queue: string;
  status: string; // queued
};
