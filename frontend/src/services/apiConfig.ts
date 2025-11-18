/**
 * API Configuration - Initialize Axios instance with interceptors
 *
 * This file sets up:
 * - Global error handling via interceptors
 * - Retry logic for transient failures
 * - Request/response logging (dev mode)
 *
 * Import this once in main.tsx before rendering the app.
 */

import api from './api';
import { setupAxiosInterceptors, setupRetryLogic } from './apiInterceptor';

// Setup global interceptors
setupAxiosInterceptors(api);

// Setup retry logic (3 retries with exponential backoff)
setupRetryLogic(api, 3);

export default api;
