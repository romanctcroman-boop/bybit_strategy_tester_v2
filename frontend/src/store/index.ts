/**
 * Zustand Store - Global State Management
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import type {
  BacktestResult,
  OptimizationTaskResponse,
  OptimizationResultsResponse,
  OptimizationProgress,
  Candle,
  Strategy,
  AppSettings,
  AppError,
} from '../types';

// ============================================================================
// APP STATE INTERFACE
// ============================================================================

interface AppState {
  // Settings
  settings: AppSettings;
  updateSettings: (settings: Partial<AppSettings>) => void;

  // Errors
  errors: AppError[];
  error: AppError | null;
  addError: (error: Omit<AppError, 'id' | 'timestamp'>) => void;
  setError: (error: AppError | null) => void;
  clearErrors: () => void;
  removeError: (id: string) => void;

  // Loading states
  isLoading: boolean;
  loading: boolean;
  setLoading: (loading: boolean) => void;

  // Strategies
  strategies: Strategy[];
  setStrategies: (strategies: Strategy[]) => void;

  // Market Data
  candles: Candle[];
  setCandles: (candles: Candle[]) => void;
  selectedSymbol: string;
  setSelectedSymbol: (symbol: string) => void;
  selectedTimeframe: string;
  setSelectedTimeframe: (timeframe: string) => void;

  // Backtests
  backtests: BacktestResult[];
  currentBacktest: BacktestResult | null;
  setBacktests: (backtests: BacktestResult[]) => void;
  setCurrentBacktest: (backtest: BacktestResult | null) => void;
  addBacktest: (backtest: BacktestResult) => void;

  // Optimizations
  optimizations: OptimizationTaskResponse[];
  currentOptimization: OptimizationResultsResponse | null;
  optimizationProgress: Record<string, OptimizationProgress>;
  setOptimizations: (optimizations: OptimizationTaskResponse[]) => void;
  setCurrentOptimization: (optimization: OptimizationResultsResponse | null) => void;
  addOptimization: (optimization: OptimizationTaskResponse) => void;
  updateOptimizationProgress: (taskId: string, progress: OptimizationProgress) => void;

  // WebSocket connection
  wsConnected: boolean;
  setWsConnected: (connected: boolean) => void;
}

// ============================================================================
// STORE IMPLEMENTATION
// ============================================================================

export const useAppStore = create<AppState>()(
  devtools(
    (set) => ({
      // Settings
      settings: {
        theme: 'dark',
        apiBaseUrl: 'http://localhost:8000',
        wsBaseUrl: 'ws://localhost:8000/ws',
        autoConnect: true,
        notifications: true,
      },
      updateSettings: (newSettings) =>
        set((state) => ({
          settings: { ...state.settings, ...newSettings },
        })),

      // Errors
      errors: [],
      error: null,
      addError: (error) =>
        set((state) => ({
          errors: [
            ...state.errors,
            {
              ...error,
              id: `error-${Date.now()}-${Math.random()}`,
              timestamp: new Date(),
            },
          ],
        })),
      setError: (error) => set({ error }),
      clearErrors: () => set({ errors: [], error: null }),
      removeError: (id) =>
        set((state) => ({
          errors: state.errors.filter((e) => e.id !== id),
        })),

      // Loading
      isLoading: false,
      loading: false,
      setLoading: (loading) => set({ isLoading: loading, loading }),

      // Strategies
      strategies: [],
      setStrategies: (strategies) => set({ strategies }),

      // Market Data
      candles: [],
      setCandles: (candles) => set({ candles }),
      selectedSymbol: 'BTCUSDT',
      setSelectedSymbol: (symbol) => set({ selectedSymbol: symbol }),
      selectedTimeframe: '15',
      setSelectedTimeframe: (timeframe) => set({ selectedTimeframe: timeframe }),

      // Backtests
      backtests: [],
      currentBacktest: null,
      setBacktests: (backtests) => set({ backtests }),
      setCurrentBacktest: (backtest) => set({ currentBacktest: backtest }),
      addBacktest: (backtest) =>
        set((state) => ({
          backtests: [backtest, ...state.backtests],
          currentBacktest: backtest,
        })),

      // Optimizations
      optimizations: [],
      currentOptimization: null,
      optimizationProgress: {},
      setOptimizations: (optimizations) => set({ optimizations }),
      setCurrentOptimization: (optimization) => set({ currentOptimization: optimization }),
      addOptimization: (optimization) =>
        set((state) => ({
          optimizations: [optimization, ...state.optimizations],
        })),
      updateOptimizationProgress: (taskId, progress) =>
        set((state) => ({
          optimizationProgress: {
            ...state.optimizationProgress,
            [taskId]: progress,
          },
        })),

      // WebSocket
      wsConnected: false,
      setWsConnected: (connected) => set({ wsConnected: connected }),
    }),
    { name: 'bybit-strategy-tester' }
  )
);

export default useAppStore;
