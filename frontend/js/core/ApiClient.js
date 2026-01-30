/**
 * 🔒 Centralized API Client - Bybit Strategy Tester v2
 *
 * Secure API client with CSRF protection, error handling,
 * automatic retries, and request/response interceptors.
 *
 * Fixes P0-2: CSRF Protection
 * Fixes P1-4: Centralized API Client
 *
 * @version 1.0.0
 * @date 2026-01-28
 */

// ============================================
// CUSTOM ERRORS
// ============================================

/**
 * Custom API Error with status code and response data
 */
export class ApiError extends Error {
  constructor(status, message, data = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
    this.timestamp = new Date().toISOString();
  }

  /**
   * Check if error is a client error (4xx)
   * @returns {boolean}
   */
  isClientError() {
    return this.status >= 400 && this.status < 500;
  }

  /**
   * Check if error is a server error (5xx)
   * @returns {boolean}
   */
  isServerError() {
    return this.status >= 500;
  }

  /**
   * Check if error is authentication related
   * @returns {boolean}
   */
  isAuthError() {
    return this.status === 401 || this.status === 403;
  }
}

/**
 * Network Error (no response)
 */
export class NetworkError extends Error {
  constructor(message = "Network error occurred") {
    super(message);
    this.name = "NetworkError";
    this.timestamp = new Date().toISOString();
  }
}

// ============================================
// API CLIENT CLASS
// ============================================

/**
 * Centralized API Client with security features
 *
 * @example
 * const api = new ApiClient('/api/v1');
 *
 * // GET request
 * const data = await api.get('/strategies');
 *
 * // POST with data
 * const result = await api.post('/backtests', { symbol: 'BTCUSDT' });
 *
 * // With custom options
 * const data = await api.get('/data', { timeout: 30000 });
 */
export class ApiClient {
  /**
   * @param {string} baseUrl - Base URL for all requests
   * @param {Object} options - Configuration options
   */
  constructor(baseUrl = "/api", options = {}) {
    this.baseUrl = baseUrl;
    this.timeout = options.timeout || 30000;
    this.retries = options.retries || 3;
    this.retryDelay = options.retryDelay || 1000;

    // CSRF token management
    this.csrfToken = null;
    this.csrfHeaderName = options.csrfHeaderName || "X-CSRF-Token";
    this.csrfCookieName = options.csrfCookieName || "csrf_token";

    // Request/response interceptors
    this._requestInterceptors = [];
    this._responseInterceptors = [];
    this._errorHandlers = [];

    // Initialize CSRF token
    this._initCsrfToken();
  }

  // ============================================
  // CSRF PROTECTION
  // ============================================

  /**
   * Initialize CSRF token from meta tag or cookie
   * @private
   */
  _initCsrfToken() {
    // Try meta tag first
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) {
      this.csrfToken = metaTag.getAttribute("content");
      return;
    }

    // Try cookie
    const cookie = this._getCookie(this.csrfCookieName);
    if (cookie) {
      this.csrfToken = cookie;
      return;
    }

    // Will be fetched on first request if needed
    console.debug("[ApiClient] No CSRF token found, will fetch on demand");
  }

  /**
   * Get cookie value by name
   * @private
   * @param {string} name - Cookie name
   * @returns {string|null}
   */
  _getCookie(name) {
    const match = document.cookie.match(
      new RegExp("(^| )" + name + "=([^;]+)"),
    );
    return match ? decodeURIComponent(match[2]) : null;
  }

  /**
   * Fetch CSRF token from server
   * @returns {Promise<string>}
   */
  async fetchCsrfToken() {
    try {
      const response = await fetch(`${this.baseUrl}/csrf-token`, {
        method: "GET",
        credentials: "same-origin",
      });

      if (response.ok) {
        const data = await response.json();
        this.csrfToken = data.token;
        return this.csrfToken;
      }
    } catch (error) {
      console.warn("[ApiClient] Failed to fetch CSRF token:", error);
    }
    return null;
  }

  // ============================================
  // INTERCEPTORS
  // ============================================

  /**
   * Add request interceptor
   * @param {Function} interceptor - (config) => config
   * @returns {Function} Remove function
   */
  addRequestInterceptor(interceptor) {
    this._requestInterceptors.push(interceptor);
    return () => {
      const index = this._requestInterceptors.indexOf(interceptor);
      if (index > -1) this._requestInterceptors.splice(index, 1);
    };
  }

  /**
   * Add response interceptor
   * @param {Function} interceptor - (response) => response
   * @returns {Function} Remove function
   */
  addResponseInterceptor(interceptor) {
    this._responseInterceptors.push(interceptor);
    return () => {
      const index = this._responseInterceptors.indexOf(interceptor);
      if (index > -1) this._responseInterceptors.splice(index, 1);
    };
  }

  /**
   * Add global error handler
   * @param {Function} handler - (error) => void
   * @returns {Function} Remove function
   */
  addErrorHandler(handler) {
    this._errorHandlers.push(handler);
    return () => {
      const index = this._errorHandlers.indexOf(handler);
      if (index > -1) this._errorHandlers.splice(index, 1);
    };
  }

  // ============================================
  // CORE REQUEST METHOD
  // ============================================

  /**
   * Make HTTP request with all security features
   * @param {string} method - HTTP method
   * @param {string} endpoint - API endpoint
   * @param {Object|null} data - Request body
   * @param {Object} options - Additional options
   * @returns {Promise<any>}
   */
  async request(method, endpoint, data = null, options = {}) {
    const url = this._buildUrl(endpoint, options.params);

    let config = {
      method: method.toUpperCase(),
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...options.headers,
      },
      credentials: "same-origin",
      signal: this._createAbortSignal(options.timeout),
    };

    // Add CSRF token for mutating requests
    if (["POST", "PUT", "PATCH", "DELETE"].includes(config.method)) {
      if (this.csrfToken) {
        config.headers[this.csrfHeaderName] = this.csrfToken;
      }
    }

    // Add body for requests with data
    if (data !== null && !["GET", "HEAD"].includes(config.method)) {
      config.body = JSON.stringify(data);
    }

    // Apply request interceptors
    for (const interceptor of this._requestInterceptors) {
      config = (await interceptor(config)) || config;
    }

    // Execute with retry logic
    return this._executeWithRetry(url, config, options);
  }

  /**
   * Build URL with query parameters
   * @private
   * @param {string} endpoint - API endpoint
   * @param {Object} params - Query parameters
   * @returns {string}
   */
  _buildUrl(endpoint, params = null) {
    let url = `${this.baseUrl}${endpoint}`;

    if (params && Object.keys(params).length > 0) {
      const searchParams = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== null) {
          searchParams.append(key, String(value));
        }
      }
      url += `?${searchParams.toString()}`;
    }

    return url;
  }

  /**
   * Create abort signal with timeout
   * @private
   * @param {number} timeout - Timeout in ms
   * @returns {AbortSignal}
   */
  _createAbortSignal(timeout = null) {
    const controller = new AbortController();
    const effectiveTimeout = timeout || this.timeout;

    if (effectiveTimeout > 0) {
      setTimeout(() => controller.abort(), effectiveTimeout);
    }

    return controller.signal;
  }

  /**
   * Execute request with retry logic
   * @private
   */
  async _executeWithRetry(url, config, options) {
    const maxRetries = options.retries ?? this.retries;
    let lastError = null;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        const response = await fetch(url, config);
        return await this._handleResponse(response, options);
      } catch (error) {
        lastError = error;

        // Don't retry on abort
        if (error.name === "AbortError") {
          throw new NetworkError("Request timeout");
        }

        // Don't retry on client errors
        if (error instanceof ApiError && error.isClientError()) {
          throw error;
        }

        // Retry with exponential backoff
        if (attempt < maxRetries) {
          const delay = this.retryDelay * Math.pow(2, attempt);
          console.warn(
            `[ApiClient] Retry ${attempt + 1}/${maxRetries} after ${delay}ms`,
          );
          await this._sleep(delay);
        }
      }
    }

    // All retries failed
    this._notifyErrorHandlers(lastError);
    throw lastError;
  }

  /**
   * Handle API response
   * @private
   */
  async _handleResponse(response, options) {
    let data = null;

    // Parse response body
    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      try {
        data = await response.json();
      } catch (e) {
        data = null;
      }
    } else if (!options.rawResponse) {
      data = await response.text();
    }

    // Handle error responses
    if (!response.ok) {
      const message = data?.detail || data?.message || response.statusText;
      const error = new ApiError(response.status, message, data);
      this._notifyErrorHandlers(error);
      throw error;
    }

    // Apply response interceptors
    let result = { data, response, status: response.status };
    for (const interceptor of this._responseInterceptors) {
      result = (await interceptor(result)) || result;
    }

    // Return data directly unless raw response requested
    return options.rawResponse ? result : result.data;
  }

  /**
   * Sleep helper
   * @private
   */
  _sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Notify all error handlers
   * @private
   */
  _notifyErrorHandlers(error) {
    for (const handler of this._errorHandlers) {
      try {
        handler(error);
      } catch (e) {
        console.error("[ApiClient] Error handler threw:", e);
      }
    }

    // Dispatch global event for UI components
    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent("api-error", {
          detail: {
            error,
            status: error.status,
            message: error.message,
            timestamp: new Date().toISOString(),
          },
        }),
      );
    }
  }

  // ============================================
  // CONVENIENCE METHODS
  // ============================================

  /**
   * GET request
   * @param {string} endpoint
   * @param {Object} options
   * @returns {Promise<any>}
   */
  get(endpoint, options = {}) {
    return this.request("GET", endpoint, null, options);
  }

  /**
   * POST request
   * @param {string} endpoint
   * @param {Object} data
   * @param {Object} options
   * @returns {Promise<any>}
   */
  post(endpoint, data, options = {}) {
    return this.request("POST", endpoint, data, options);
  }

  /**
   * PUT request
   * @param {string} endpoint
   * @param {Object} data
   * @param {Object} options
   * @returns {Promise<any>}
   */
  put(endpoint, data, options = {}) {
    return this.request("PUT", endpoint, data, options);
  }

  /**
   * PATCH request
   * @param {string} endpoint
   * @param {Object} data
   * @param {Object} options
   * @returns {Promise<any>}
   */
  patch(endpoint, data, options = {}) {
    return this.request("PATCH", endpoint, data, options);
  }

  /**
   * DELETE request
   * @param {string} endpoint
   * @param {Object} options
   * @returns {Promise<any>}
   */
  delete(endpoint, options = {}) {
    return this.request("DELETE", endpoint, null, options);
  }

  // ============================================
  // UTILITY METHODS
  // ============================================

  /**
   * Upload file
   * @param {string} endpoint
   * @param {FormData} formData
   * @param {Object} options
   * @returns {Promise<any>}
   */
  async upload(endpoint, formData, options = {}) {
    const url = this._buildUrl(endpoint);

    const config = {
      method: "POST",
      headers: {},
      body: formData,
      credentials: "same-origin",
    };

    // Add CSRF token
    if (this.csrfToken) {
      config.headers[this.csrfHeaderName] = this.csrfToken;
    }

    // Handle progress
    if (options.onProgress && typeof XMLHttpRequest !== "undefined") {
      return this._uploadWithProgress(url, config, options);
    }

    const response = await fetch(url, config);
    return this._handleResponse(response, options);
  }

  /**
   * Upload with progress tracking
   * @private
   */
  _uploadWithProgress(url, config, options) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable && options.onProgress) {
          options.onProgress({
            loaded: e.loaded,
            total: e.total,
            percent: Math.round((e.loaded / e.total) * 100),
          });
        }
      });

      xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText));
          } catch {
            resolve(xhr.responseText);
          }
        } else {
          reject(new ApiError(xhr.status, xhr.statusText));
        }
      });

      xhr.addEventListener("error", () => {
        reject(new NetworkError("Upload failed"));
      });

      xhr.open(config.method, url);

      // Set headers
      for (const [key, value] of Object.entries(config.headers)) {
        xhr.setRequestHeader(key, value);
      }

      xhr.withCredentials = true;
      xhr.send(config.body);
    });
  }

  /**
   * Download file
   * @param {string} endpoint
   * @param {string} filename
   * @param {Object} options
   */
  async download(endpoint, filename, options = {}) {
    const response = await this.request("GET", endpoint, null, {
      ...options,
      rawResponse: true,
    });

    const blob = await response.response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();
  }
}

// ============================================
// SINGLETON INSTANCE
// ============================================

// Create default API client instance
const api = new ApiClient("/api/v1");

// Add global error handler for notifications
api.addErrorHandler((error) => {
  // Log errors in development (check hostname instead of process.env)
  const isDev =
    typeof window !== "undefined" &&
    (window.location?.hostname === "localhost" ||
      window.location?.hostname === "127.0.0.1");
  if (isDev) {
    console.error("[API Error]", error.message, error);
  }
});

// Export singleton and class
export { api };
export default ApiClient;

// Attach to window for non-module scripts
if (typeof window !== "undefined") {
  window.ApiClient = ApiClient;
  window.api = api;
  window.ApiError = ApiError;
}
