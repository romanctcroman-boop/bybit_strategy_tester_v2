import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { isLoggedIn, getCurrentUser, logout as authLogout, UserInfo } from '../services/auth';

interface AuthContextType {
  user: UserInfo | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const checkAuth = async () => {
    try {
      if (isLoggedIn()) {
        const userInfo = await getCurrentUser();
        setUser(userInfo);
        setIsAuthenticated(true);
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
    } catch (error) {
      console.error('[AuthContext] Failed to get user info:', error);
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setLoading(false);
    }
  };

  const login = async () => {
    // IMMEDIATELY set authenticated if tokens exist
    // This allows navigation to happen right away
    if (isLoggedIn()) {
      setIsAuthenticated(true);
      setLoading(false);

      // Fetch user info in background (non-blocking)
      getCurrentUser()
        .then((userInfo) => {
          setUser(userInfo);
        })
        .catch((error) => {
          console.error('[AuthContext] Failed to fetch user info:', error);
          // Keep authenticated (tokens are valid), just missing user details
        });
    } else {
      // No tokens found
      setUser(null);
      setIsAuthenticated(false);
      setLoading(false);
      throw new Error('No authentication tokens found');
    }
  };

  const logout = async () => {
    try {
      await authLogout();
    } catch (error) {
      console.error('[AuthContext] Logout error:', error);
    } finally {
      setUser(null);
      setIsAuthenticated(false);
    }
  };

  useEffect(() => {
    checkAuth();
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated,
        login,
        logout,
        checkAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
