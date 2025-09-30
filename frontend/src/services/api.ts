import axios from 'axios';
import { ProcessingJob, ProcessingOptions, UploadResponse, ProcessingResponse } from '../types';

const API_BASE_URL = import.meta.env.DEV ? 'http://localhost:5000' : 'http://localhost:5000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000, // 5 minutes for long processing jobs
});

// Global variable to prevent race conditions in token refresh
let refreshPromise: Promise<string | null> | null = null;

// Helper function to check if token is expired
const isTokenExpired = (token: { expires_at?: string }): boolean => {
  if (!token?.expires_at) return true;
  return new Date(token.expires_at) <= new Date();
};

// Helper function to get valid token from storage
const getValidToken = (): string | null => {
  try {
    const tokens = localStorage.getItem('easyedit_tokens');
    if (!tokens) return null;

    const parsedTokens = JSON.parse(tokens);
    if (!parsedTokens.access_token) return null;

    // Check if token is expired
    if (isTokenExpired(parsedTokens)) {
      return null;
    }

    return parsedTokens.access_token;
  } catch (error) {
    console.error('Error parsing stored tokens:', error);
    return null;
  }
};

// Token refresh function with race condition protection
const performTokenRefresh = async (): Promise<string | null> => {
  try {
    const tokens = localStorage.getItem('easyedit_tokens');
    if (!tokens) return null;

    const parsedTokens = JSON.parse(tokens);
    if (!parsedTokens.refresh_token) return null;

    const refreshResponse = await axios.post(`${API_BASE_URL}/auth/refresh`, {
      refresh_token: parsedTokens.refresh_token,
    });

    const newTokens = {
      access_token: refreshResponse.data.access_token,
      refresh_token: refreshResponse.data.refresh_token || parsedTokens.refresh_token,
      expires_at: refreshResponse.data.expires_at,
    };

    localStorage.setItem('easyedit_tokens', JSON.stringify(newTokens));
    return newTokens.access_token;
  } catch (error) {
    // Refresh failed, clear tokens
    localStorage.removeItem('easyedit_tokens');
    localStorage.removeItem('easyedit_user');
    throw error;
  }
};

// Add request interceptor to include JWT token with expiration check
api.interceptors.request.use(
  (config) => {
    const token = getValidToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor to handle 401 errors with race condition protection
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        // Use shared refresh promise to prevent race conditions
        if (!refreshPromise) {
          refreshPromise = performTokenRefresh();
        }

        const newToken = await refreshPromise;
        refreshPromise = null; // Reset promise after completion

        if (newToken) {
          // Retry original request with new token
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return api(originalRequest);
        } else {
          // No valid token, redirect to login
          window.location.reload();
        }
      } catch (refreshError) {
        refreshPromise = null; // Reset promise on error
        console.error('Token refresh failed:', refreshError);
        window.location.reload();
      }
    }

    return Promise.reject(error);
  }
);

export const uploadFiles = async (
  audioFile: File,
  drtFile: File
): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('audio', audioFile);
  formData.append('drt', drtFile);

  const response = await api.post<UploadResponse>('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
};

export const processTimeline = async (
  jobId: string,
  options: ProcessingOptions = {}
): Promise<ProcessingResponse> => {
  const response = await api.post<ProcessingResponse>(`/process/${jobId}`, options);
  return response.data;
};

export const getJobStatus = async (jobId: string): Promise<ProcessingJob> => {
  const response = await api.get<ProcessingJob>(`/status/${jobId}`);
  return response.data;
};

export const downloadResult = async (jobId: string): Promise<Blob> => {
  const response = await api.get(`/download/${jobId}`, {
    responseType: 'blob',
  });
  return response.data;
};

export const getAllJobs = async (): Promise<{ jobs: ProcessingJob[] }> => {
  const response = await api.get<{ jobs: ProcessingJob[] }>('/jobs');
  return response.data;
};

export const healthCheck = async (): Promise<{ status: string }> => {
  const response = await api.get<{ status: string }>('/health');
  return response.data;
};

export const triggerCleanup = async (): Promise<{ message: string }> => {
  const response = await api.post<{ message: string }>('/cleanup');
  return response.data;
};