/**
 * JWT Authentication Service
 * Phase 1 Security Integration - Frontend
 *
 * Handles JWT token storage, refresh, and API authentication
 */

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserInfo {
  user_id: string;
  user?: string | null; // Deprecated, use user_id
  scopes: string[];
  authenticated?: boolean;
}

const ACCESS_TOKEN_KEY = 'bybit_access_token';
const REFRESH_TOKEN_KEY = 'bybit_refresh_token';
const TOKEN_EXPIRY_KEY = 'bybit_token_expiry';

/**
 * Get access token from localStorage
 */
export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

/**
 * Get refresh token from localStorage
 */
export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

/**
 * Check if token is expired
 */
export function isTokenExpired(): boolean {
  const expiry = localStorage.getItem(TOKEN_EXPIRY_KEY);
  if (!expiry) return true;

  const expiryTime = parseInt(expiry, 10);
  const now = Date.now();

  // Consider expired if less than 5 minutes remaining
  return now >= expiryTime - 5 * 60 * 1000;
}

/**
 * Save tokens to localStorage
 */
export function saveTokens(response: TokenResponse): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, response.access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, response.refresh_token);

  // Calculate expiry timestamp
  const expiryTime = Date.now() + response.expires_in * 1000;
  localStorage.setItem(TOKEN_EXPIRY_KEY, expiryTime.toString());

  console.log('[Auth] Tokens saved, expires at:', new Date(expiryTime).toISOString());
}

/**
 * Clear all tokens from localStorage
 */
export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(TOKEN_EXPIRY_KEY);
  console.log('[Auth] Tokens cleared');
}

/**
 * Check if user is logged in (has valid token)
 */
export function isLoggedIn(): boolean {
  const token = getAccessToken();
  return token !== null && !isTokenExpired();
}

/**
 * Login with username and password
 */
export async function login(username: string, password: string): Promise<TokenResponse> {
  const baseURL = (import.meta as any).env?.VITE_API_URL || '/api/v1';

  const response = await fetch(`${baseURL}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ username, password }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Login failed' }));
    throw new Error(error.detail || 'Login failed');
  }

  const data: TokenResponse = await response.json();
  saveTokens(data);

  console.log('[Auth] Login successful for user:', username);
  return data;
}

/**
 * Refresh access token using refresh token
 */
export async function refreshAccessToken(): Promise<TokenResponse> {
  const refreshToken = getRefreshToken();

  if (!refreshToken) {
    throw new Error('No refresh token available');
  }

  const baseURL = (import.meta as any).env?.VITE_API_URL || '/api/v1';

  const response = await fetch(`${baseURL}/auth/refresh`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!response.ok) {
    // Refresh token expired or invalid - clear all tokens
    clearTokens();
    throw new Error('Session expired. Please login again.');
  }

  const data: TokenResponse = await response.json();
  saveTokens(data);

  console.log('[Auth] Token refreshed successfully');
  return data;
}

/**
 * Get current user info
 */
export async function getCurrentUser(): Promise<UserInfo> {
  const baseURL = (import.meta as any).env?.VITE_API_URL || '/api/v1';
  const token = getAccessToken();

  if (!token) {
    throw new Error('Not authenticated');
  }

  const response = await fetch(`${baseURL}/auth/me`, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error('Failed to get user info');
  }

  const data: UserInfo = await response.json();
  return data;
}

/**
 * Logout - clear tokens and call logout endpoint
 */
export async function logout(): Promise<void> {
  const baseURL = (import.meta as any).env?.VITE_API_URL || '/api/v1';
  const token = getAccessToken();

  if (token) {
    try {
      await fetch(`${baseURL}/auth/logout`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
    } catch (error) {
      console.warn('[Auth] Logout endpoint failed:', error);
    }
  }

  clearTokens();
  console.log('[Auth] Logged out');
}

/**
 * Get Authorization header for API requests
 */
export function getAuthHeader(): string | null {
  const token = getAccessToken();
  return token ? `Bearer ${token}` : null;
}
