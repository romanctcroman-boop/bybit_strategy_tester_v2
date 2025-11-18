/**
 * API Error Interceptor - Global error handling for Axios
 *
 * Based on Perplexity AI recommendations for production apps.
 * Integrates with notistack for toast notifications.
 *
 * Features:
 * - Automatic error toast notifications
 * - Retry logic for transient failures
 * - Request/response logging in dev mode
 * - Authentication error handling
 * - Network error detection
 */

import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { enqueueSnackbar } from 'notistack';

// Error message extraction
function extractErrorMessage(error: AxiosError): string {
  // Network errors (no response from server)
  if (!error.response) {
    if (error.code === 'ECONNABORTED') {
      return 'Превышено время ожидания ответа от сервера';
    }
    if (error.code === 'ERR_NETWORK') {
      return 'Ошибка сети. Проверьте подключение к интернету';
    }
    return `Сетевая ошибка: ${error.message}`;
  }

  const { status, data } = error.response;

  // Server error messages
  if (data && typeof data === 'object') {
    if ('detail' in data) {
      if (typeof data.detail === 'string') {
        return data.detail;
      }
      if (Array.isArray(data.detail) && data.detail.length > 0) {
        return data.detail.map((d: any) => d.msg || d.message || '').join(', ');
      }
    }
    if ('message' in data && typeof data.message === 'string') {
      return data.message;
    }
    if ('error' in data && typeof data.error === 'string') {
      return data.error;
    }
  }

  // HTTP status messages
  switch (status) {
    case 400:
      return 'Некорректный запрос';
    case 401:
      return 'Требуется авторизация';
    case 403:
      return 'Доступ запрещен';
    case 404:
      return 'Ресурс не найден';
    case 422:
      return 'Ошибка валидации данных';
    case 429:
      return 'Слишком много запросов. Попробуйте позже';
    case 500:
      return 'Внутренняя ошибка сервера';
    case 502:
      return 'Сервер недоступен';
    case 503:
      return 'Сервис временно недоступен';
    default:
      return `Ошибка HTTP ${status}`;
  }
}

/**
 * Setup Axios interceptors for global error handling
 */
export function setupAxiosInterceptors(axiosInstance: any) {
  // Request interceptor (for logging and auth token injection)
  axiosInstance.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      // Log requests in development
      if (import.meta.env.DEV) {
        console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`, config.data);
      }

      // Add authentication token if available
      const token = localStorage.getItem('auth_token');
      if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
      }

      return config;
    },
    (error: AxiosError) => {
      console.error('[API Request Error]', error);
      return Promise.reject(error);
    }
  );

  // Response interceptor (for global error handling)
  axiosInstance.interceptors.response.use(
    (response: AxiosResponse) => {
      // Log responses in development
      if (import.meta.env.DEV) {
        console.log(
          `[API Response] ${response.config.method?.toUpperCase()} ${response.config.url}`,
          response.data
        );
      }
      return response;
    },
    (error: AxiosError) => {
      const errorMessage = extractErrorMessage(error);

      // Don't show toast for cancelled requests
      if (axios.isCancel(error)) {
        console.log('[API Request Cancelled]', error.message);
        return Promise.reject(error);
      }

      // Log all errors in development
      if (import.meta.env.DEV) {
        console.error('[API Response Error]', {
          message: errorMessage,
          status: error.response?.status,
          data: error.response?.data,
          config: error.config,
        });
      }

      // Handle specific error types
      const status = error.response?.status;

      // Authentication errors - redirect to login
      if (status === 401) {
        localStorage.removeItem('auth_token');
        enqueueSnackbar('Сессия истекла. Требуется повторная авторизация', {
          variant: 'warning',
          autoHideDuration: 5000,
        });
        // Optional: redirect to login page
        // window.location.href = '/login';
        return Promise.reject(error);
      }

      // Validation errors - show specific message
      if (status === 422) {
        enqueueSnackbar(errorMessage || 'Ошибка валидации данных', {
          variant: 'error',
          autoHideDuration: 6000,
        });
        return Promise.reject(error);
      }

      // Server errors - show generic message
      if (status && status >= 500) {
        enqueueSnackbar('Ошибка сервера. Попробуйте позже', {
          variant: 'error',
          autoHideDuration: 5000,
        });
        return Promise.reject(error);
      }

      // Network errors
      if (!error.response) {
        enqueueSnackbar(errorMessage, {
          variant: 'error',
          autoHideDuration: 7000,
        });
        return Promise.reject(error);
      }

      // Default error notification
      enqueueSnackbar(errorMessage, {
        variant: 'error',
        autoHideDuration: 5000,
      });

      return Promise.reject(error);
    }
  );
}

/**
 * Retry failed requests with exponential backoff
 */
export function setupRetryLogic(axiosInstance: any, maxRetries = 3) {
  axiosInstance.interceptors.response.use(
    (response: any) => response,
    async (error: AxiosError) => {
      const config: any = error.config;

      // Don't retry if max retries reached
      if (!config || !config.retry || config.__retryCount >= maxRetries) {
        return Promise.reject(error);
      }

      // Only retry on network errors or 5xx errors
      const shouldRetry =
        !error.response ||
        (error.response.status >= 500 && error.response.status < 600) ||
        error.code === 'ECONNABORTED';

      if (!shouldRetry) {
        return Promise.reject(error);
      }

      config.__retryCount = config.__retryCount || 0;
      config.__retryCount += 1;

      // Exponential backoff: 1s, 2s, 4s
      const delay = Math.pow(2, config.__retryCount - 1) * 1000;

      console.log(`[API Retry] Attempt ${config.__retryCount}/${maxRetries} after ${delay}ms`);

      await new Promise((resolve) => setTimeout(resolve, delay));

      return axiosInstance(config);
    }
  );
}

export default {
  setupAxiosInterceptors,
  setupRetryLogic,
};
