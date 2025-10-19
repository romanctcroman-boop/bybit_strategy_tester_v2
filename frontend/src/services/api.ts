/**
 * API Service for Backend Communication
 *
 * Handles all HTTP requests to the FastAPI backend
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  Candle,
  BacktestResult,
  OptimizationRequest,
  OptimizationTaskResponse,
  OptimizationResultsResponse,
  Strategy,
} from '../types';

class ApiService {
  private client: AxiosInstance;
  private baseURL: string;

  constructor(baseURL: string = 'http://localhost:8000') {
    this.baseURL = baseURL;
    this.client = axios.create({
      baseURL: `${baseURL}/api/v1`,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor
    this.client.interceptors.request.use(
      (config) => {
        console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`);
        return config;
      },
      (error) => {
        console.error('[API] Request error:', error);
        return Promise.reject(error);
      }
    );

    // Response interceptor
    this.client.interceptors.response.use(
      (response) => {
        console.log(`[API] Response from ${response.config.url}:`, response.status);
        return response;
      },
      (error: AxiosError) => {
        console.error('[API] Response error:', error.message);
        if (error.response) {
          console.error('[API] Error details:', error.response.data);
        }
        return Promise.reject(error);
      }
    );
  }

  // ============================================================================
  // HEALTH CHECK
  // ============================================================================

  async healthCheck(): Promise<{ status: string; timestamp: string }> {
    const response = await this.client.get('/health');
    return response.data;
  }

  // ============================================================================
  // MARKET DATA
  // ============================================================================

  async getCandles(params: {
    symbol: string;
    interval: string;
    start_date?: string;
    end_date?: string;
    limit?: number;
  }): Promise<Candle[]> {
    const response = await this.client.get('/data/candles', { params });
    return response.data;
  }

  async getSymbols(): Promise<string[]> {
    const response = await this.client.get('/data/symbols');
    return response.data;
  }

  // ============================================================================
  // STRATEGIES
  // ============================================================================

  async getStrategies(): Promise<Strategy[]> {
    const response = await this.client.get('/strategies');
    return response.data;
  }

  async getStrategy(strategyId: string): Promise<Strategy> {
    const response = await this.client.get(`/strategies/${strategyId}`);
    return response.data;
  }

  // ============================================================================
  // BACKTEST
  // ============================================================================

  async runBacktest(params: {
    strategy_class: string;
    symbol: string;
    timeframe: string;
    start_date: string;
    end_date: string;
    initial_capital: number;
    commission: number;
    strategy_params: Record<string, any>;
  }): Promise<BacktestResult> {
    const response = await this.client.post('/backtest/run', params);
    return response.data;
  }

  async getBacktestResult(backtestId: string): Promise<BacktestResult> {
    const response = await this.client.get(`/backtest/${backtestId}`);
    return response.data;
  }

  async listBacktests(params?: {
    skip?: number;
    limit?: number;
    strategy_class?: string;
  }): Promise<BacktestResult[]> {
    const response = await this.client.get('/backtest', { params });
    return response.data;
  }

  // ============================================================================
  // OPTIMIZATION
  // ============================================================================

  async startOptimization(request: OptimizationRequest): Promise<OptimizationTaskResponse> {
    let endpoint = '/optimize/';

    switch (request.method) {
      case 'grid_search':
        endpoint += 'grid-search';
        break;
      case 'walk_forward':
        endpoint += 'walk-forward';
        break;
      case 'bayesian':
        endpoint += 'bayesian';
        break;
      default:
        throw new Error(`Unknown optimization method: ${request.method}`);
    }

    const response = await this.client.post(endpoint, request);
    return response.data;
  }

  async getOptimizationResult(taskId: string): Promise<OptimizationResultsResponse> {
    const response = await this.client.get(`/optimize/result/${taskId}`);
    return response.data;
  }

  async cancelOptimization(taskId: string): Promise<{ message: string }> {
    const response = await this.client.post(`/optimize/cancel/${taskId}`);
    return response.data;
  }

  async listOptimizations(params?: {
    skip?: number;
    limit?: number;
  }): Promise<OptimizationTaskResponse[]> {
    const response = await this.client.get('/optimize/list', { params });
    return response.data;
  }

  // ============================================================================
  // UTILITY
  // ============================================================================

  getBaseURL(): string {
    return this.baseURL;
  }

  setBaseURL(url: string): void {
    this.baseURL = url;
    this.client.defaults.baseURL = `${url}/api/v1`;
  }
}

// Singleton instance
const API_URL =
  typeof window !== 'undefined'
    ? (window as Window & { ENV?: { VITE_API_URL?: string } }).ENV?.VITE_API_URL ||
      'http://localhost:8000'
    : 'http://localhost:8000';

export const apiService = new ApiService(API_URL);

// Convenient exports
export const api = {
  health: () => apiService.healthCheck(),
  data: {
    getCandles: (params: Parameters<typeof apiService.getCandles>[0]) =>
      apiService.getCandles(params),
    getSymbols: () => apiService.getSymbols(),
  },
  strategies: {
    list: () => apiService.getStrategies(),
    get: (id: string) => apiService.getStrategy(id),
  },
  backtest: {
    run: (params: Parameters<typeof apiService.runBacktest>[0]) => apiService.runBacktest(params),
    get: (id: string) => apiService.getBacktestResult(id),
    list: (params?: Parameters<typeof apiService.listBacktests>[0]) =>
      apiService.listBacktests(params),
  },
  optimization: {
    start: (request: Parameters<typeof apiService.startOptimization>[0]) =>
      apiService.startOptimization(request),
    get: (taskId: string) => apiService.getOptimizationResult(taskId),
    cancel: (taskId: string) => apiService.cancelOptimization(taskId),
    list: (params?: Parameters<typeof apiService.listOptimizations>[0]) =>
      apiService.listOptimizations(params),
  },
};

export default apiService;
