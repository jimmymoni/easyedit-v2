import axios from 'axios';
import { ProcessingJob, ProcessingOptions, UploadResponse, ProcessingResponse } from '../types';

// TEMPORARY: Testing minimal app on port 5000
const API_BASE_URL = 'http://localhost:5000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 600000, // 10 minutes for AI analysis and long processing jobs
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

    // If uploading FormData, DO NOT modify headers except Authorization.
    if (config.data instanceof FormData) {
      config.headers = config.headers || {};
      if (token) config.headers.Authorization = `Bearer ${token}`;
      return config; // DO NOT touch Content-Type, axios must set the boundary automatically.
    }

    // Normal behavior for non-FormData requests
    if (token) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => Promise.reject(error)
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

export interface UploadProgress {
  percentage: number;
  uploadedBytes: number;
  totalBytes: number;
  uploadSpeed: number; // MB/s
  estimatedTimeRemaining: number; // seconds
}

// Simple upload endpoint for speed testing (NO middleware, NO interceptors)
export const simpleUploadFiles = async (
  audioFile: File,
  timelineFile: File,
  onProgress?: (progress: UploadProgress) => void
): Promise<UploadResponse> => {
  // Validate files before upload
  if (!audioFile) {
    throw new Error('Audio file is required');
  }
  if (!timelineFile) {
    throw new Error('Timeline file is required');
  }

  console.log('[API] simpleUploadFiles called', {
    audioFile: audioFile?.name,
    audioSize: audioFile?.size,
    timelineFile: timelineFile?.name,
    timelineSize: timelineFile?.size
  });

  // Create a bare axios instance WITHOUT interceptors
  // CRITICAL: Use direct backend URL to bypass Vite proxy which strips FormData
  const directBackendURL = 'http://localhost:5000';  // Testing minimal app
  const simpleAxios = axios.create({
    baseURL: directBackendURL,
    timeout: 300000,
    // NO interceptors, NO auth headers
  });

  const formData = new FormData();
  formData.append('audio', audioFile);
  formData.append('timeline', timelineFile);

  console.log('[API] FormData created with keys:', Array.from(formData.keys()));
  console.log('[API] Using direct backend URL:', directBackendURL);

  let startTime = Date.now();
  let lastLoaded = 0;
  let lastTime = startTime;

  const response = await simpleAxios.post<UploadResponse>('/simple-upload', formData, {
    onUploadProgress: (progressEvent) => {
      if (progressEvent.total && onProgress) {
        const currentTime = Date.now();
        const timeElapsed = (currentTime - lastTime) / 1000; // seconds
        const bytesUploaded = progressEvent.loaded - lastLoaded;

        // Calculate upload speed (MB/s)
        const uploadSpeed = timeElapsed > 0
          ? (bytesUploaded / (1024 * 1024)) / timeElapsed
          : 0;

        // Calculate percentage
        const percentage = Math.round((progressEvent.loaded / progressEvent.total) * 100);

        // Calculate ETA
        const bytesRemaining = progressEvent.total - progressEvent.loaded;
        const estimatedTimeRemaining = uploadSpeed > 0
          ? Math.ceil(bytesRemaining / (uploadSpeed * 1024 * 1024))
          : 0;

        onProgress({
          percentage,
          uploadedBytes: progressEvent.loaded,
          totalBytes: progressEvent.total,
          uploadSpeed,
          estimatedTimeRemaining,
        });

        lastLoaded = progressEvent.loaded;
        lastTime = currentTime;
      }
    },
  });

  return response.data;
};

// Regular upload endpoint (WITH middleware)
export const uploadFiles = async (
  audioFile: File,
  timelineFile: File,
  onProgress?: (progress: UploadProgress) => void
): Promise<UploadResponse> => {
  // Validate files before upload
  if (!audioFile) {
    throw new Error('Audio file is required');
  }
  if (!timelineFile) {
    throw new Error('Timeline file is required');
  }

  console.log('[API] uploadFiles called', {
    audioFile: audioFile?.name,
    audioSize: audioFile?.size,
    timelineFile: timelineFile?.name,
    timelineSize: timelineFile?.size
  });

  const formData = new FormData();
  formData.append('audio', audioFile);
  formData.append('timeline', timelineFile);

  console.log('[API] Debug FormData:', {
    hasAudio: formData.has('audio'),
    hasTimeline: formData.has('timeline'),
    audioName: (() => { const f = formData.get('audio'); return f instanceof File ? f.name : null; })(),
    timelineName: (() => { const f = formData.get('timeline'); return f instanceof File ? f.name : null; })(),
    audioSize: (() => { const f = formData.get('audio'); return f instanceof File ? f.size : null; })(),
    timelineSize: (() => { const f = formData.get('timeline'); return f instanceof File ? f.size : null; })(),
  });

  console.log('[API] FormData created with keys:', Array.from(formData.keys()));

  let startTime = Date.now();
  let lastLoaded = 0;
  let lastTime = startTime;

  const response = await api.post<UploadResponse>('/upload', formData, {
    onUploadProgress: (progressEvent) => {
      if (progressEvent.total && onProgress) {
        const currentTime = Date.now();
        const timeElapsed = (currentTime - lastTime) / 1000; // seconds
        const bytesUploaded = progressEvent.loaded - lastLoaded;

        // Calculate upload speed (MB/s)
        const uploadSpeed = timeElapsed > 0
          ? (bytesUploaded / (1024 * 1024)) / timeElapsed
          : 0;

        // Calculate percentage
        const percentage = Math.round((progressEvent.loaded / progressEvent.total) * 100);

        // Calculate ETA
        const bytesRemaining = progressEvent.total - progressEvent.loaded;
        const estimatedTimeRemaining = uploadSpeed > 0
          ? Math.ceil(bytesRemaining / (uploadSpeed * 1024 * 1024))
          : 0;

        onProgress({
          percentage,
          uploadedBytes: progressEvent.loaded,
          totalBytes: progressEvent.total,
          uploadSpeed,
          estimatedTimeRemaining,
        });

        lastLoaded = progressEvent.loaded;
        lastTime = currentTime;
      }
    },
  });

  return response.data;
};

export const processTimeline = async (
  jobId: string,
  options: ProcessingOptions = {}
): Promise<ProcessingResponse> => {
  const response = await api.post<ProcessingResponse>(`/process/${jobId}`, options, {
    timeout: 600000, // 10 minutes for AI transcription and analysis
  });
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

// God Mode - AI Edit API
export const submitAIEdit = async (jobId: string, prompt: string, params?: Record<string, any>): Promise<any> => {
  const response = await api.post('/ai-edit', {
    job_id: jobId,
    prompt: prompt,
    params: params,
  });
  return response.data;
};

// God Mode - Transcription API
export const getTranscription = async (jobId: string): Promise<any> => {
  const response = await api.get(`/transcription/${jobId}`);
  return response.data;
};

// God Mode - Timeline Comparison API
export const getTimelineComparison = async (jobId: string): Promise<any> => {
  const response = await api.get(`/timeline-comparison/${jobId}`);
  return response.data;
};

// God Mode - AI Chat API
export const sendChatMessage = async (jobId: string, message: string): Promise<any> => {
  const response = await api.post('/ai-chat', {
    job_id: jobId,
    message: message,
  }, {
    timeout: 120000, // 2 minutes for GPT-4-Turbo transcript analysis (optimized from 10min)
  });
  return response.data;
};

// God Mode - Intelligent Greeting API
export const getIntelligentGreeting = async (jobId: string): Promise<any> => {
  const response = await api.get(`/ai-greeting/${jobId}`);
  return response.data;
};

// God Mode - Knowledge Base API
export const getKnowledgeBase = async (jobId: string): Promise<any> => {
  const response = await api.get(`/knowledge-base/${jobId}`);
  return response.data;
};

export const updateKnowledgeBase = async (jobId: string, contentAnalysis: any): Promise<any> => {
  const response = await api.put(`/knowledge-base/${jobId}`, {
    content_analysis: contentAnalysis,
  });
  return response.data;
};

// God Mode - AI Preview API
export const getAIPreview = async (jobId: string, params: Record<string, any>): Promise<any> => {
  const response = await api.post('/ai-preview', {
    job_id: jobId,
    params: params,
  });
  return response.data;
};