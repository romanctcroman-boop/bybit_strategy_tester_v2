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
