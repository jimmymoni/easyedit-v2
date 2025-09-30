import React, { createContext, useContext, useState, useEffect, ReactNode, useMemo, useCallback } from 'react';
import axios from 'axios';

interface AuthTokens {
  access_token: string;
  refresh_token: string;
  expires_at: string;
}

interface User {
  user_id: string;
  email: string;
  role: string;
  has_api_key: boolean;
}

interface AuthError {
  message: string;
  code?: string;
  details?: unknown;
}

interface ApiErrorResponse {
  response?: {
    data?: {
      error?: string;
    };
  };
  message?: string;
}

interface AuthContextType {
  isAuthenticated: boolean;
  user: User | null;
  tokens: AuthTokens | null;
  login: () => Promise<void>;
  logout: () => void;
  isLoading: boolean;
  error: string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const API_BASE_URL = import.meta.env.DEV ? 'http://localhost:5000' : 'http://localhost:5000';

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [tokens, setTokens] = useState<AuthTokens | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load tokens from localStorage on mount
  useEffect(() => {
    const savedTokens = localStorage.getItem('easyedit_tokens');
    const savedUser = localStorage.getItem('easyedit_user');

    if (savedTokens && savedUser) {
      try {
        const parsedTokens = JSON.parse(savedTokens);
        const parsedUser = JSON.parse(savedUser);

        // Check if token is expired
        if (new Date(parsedTokens.expires_at) > new Date()) {
          setTokens(parsedTokens);
          setUser(parsedUser);
        } else {
          // Token expired, clear storage
          localStorage.removeItem('easyedit_tokens');
          localStorage.removeItem('easyedit_user');
        }
      } catch (error) {
        console.error('Error parsing stored auth data:', error);
        localStorage.removeItem('easyedit_tokens');
        localStorage.removeItem('easyedit_user');
      }
    }

    setIsLoading(false);
  }, []);

  const login = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Get demo token
      const tokenResponse = await axios.get(`${API_BASE_URL}/auth/demo-token`);
      const newTokens: AuthTokens = {
        access_token: tokenResponse.data.access_token,
        refresh_token: tokenResponse.data.refresh_token,
        expires_at: tokenResponse.data.expires_at,
      };

      // Verify token and get user info
      const userResponse = await axios.get(`${API_BASE_URL}/auth/verify`, {
        headers: {
          Authorization: `Bearer ${newTokens.access_token}`,
        },
      });

      const userData: User = userResponse.data.user;

      // Save to state and localStorage
      setTokens(newTokens);
      setUser(userData);
      localStorage.setItem('easyedit_tokens', JSON.stringify(newTokens));
      localStorage.setItem('easyedit_user', JSON.stringify(userData));

    } catch (error: unknown) {
      const apiError = error as ApiErrorResponse;
      const errorMessage = apiError.response?.data?.error || apiError.message || 'Login failed';
      setError(errorMessage);
      console.error('Login error:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    setTokens(null);
    setUser(null);
    setError(null);
    localStorage.removeItem('easyedit_tokens');
    localStorage.removeItem('easyedit_user');
  }, []);

  const refreshToken = async () => {
    if (!tokens?.refresh_token) {
      logout();
      return null;
    }

    try {
      const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
        refresh_token: tokens.refresh_token,
      });

      const newTokens: AuthTokens = {
        access_token: response.data.access_token,
        refresh_token: response.data.refresh_token || tokens.refresh_token,
        expires_at: response.data.expires_at,
      };

      setTokens(newTokens);
      localStorage.setItem('easyedit_tokens', JSON.stringify(newTokens));

      return newTokens.access_token;
    } catch (error) {
      console.error('Token refresh failed:', error);
      logout();
      return null;
    }
  };

  const value: AuthContextType = useMemo(() => ({
    isAuthenticated: !!tokens && !!user,
    user,
    tokens,
    login,
    logout,
    isLoading,
    error,
  }), [tokens, user, login, logout, isLoading, error]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// Note: Removed getAuthRefreshFunction export as it's not needed
// The API client now handles token refresh independently