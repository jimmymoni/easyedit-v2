import axios from 'axios';
import { ProcessingJob, ProcessingOptions, UploadResponse, ProcessingResponse, VideoUploadResponse, VideoJob, VideoAnalysis, SegmentAdjustment, SystemCheckResponse, VideoProxyStatus, WaveformData } from '../types';

// Use environment variable for API base URL, default to localhost:5000 for development
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000';

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
  const directBackendURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000';
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

// ==========================================
// VIDEO EDITOR API METHODS
// ==========================================

export const uploadVideo = async (
  videoFile: File,
  onProgress?: (progress: UploadProgress) => void
): Promise<VideoUploadResponse> => {
  const formData = new FormData();
  formData.append('video', videoFile);

  // Phase 2: Use cloud-first upload endpoint (no FFmpeg required)
  const response = await api.post<VideoUploadResponse>('/upload-video', formData, {
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        const percentage = (progressEvent.loaded / progressEvent.total) * 100;
        const uploadSpeed = calculateUploadSpeed(progressEvent);
        const estimatedTimeRemaining = calculateETA(progressEvent);

        onProgress({
          percentage,
          uploadedBytes: progressEvent.loaded,
          totalBytes: progressEvent.total,
          uploadSpeed,
          estimatedTimeRemaining,
        });
      }
    },
  });

  return response.data;
};

export const analyzeVideo = async (jobId: string): Promise<any> => {
  const response = await api.post(`/analyze-video/${jobId}`, {}, {
    timeout: 900000, // 15 minutes for analysis
  });
  return response.data;
};

export const getVideoAnalysis = async (jobId: string): Promise<{
  job_id: string;
  status: string;
  progress: number;
  message: string;
  analysis: VideoAnalysis;
}> => {
  const response = await api.get(`/video-analysis/${jobId}`);
  return response.data;
};

export const applyVideoCuts = async (
  jobId: string,
  segmentAdjustments: SegmentAdjustment[],
  encodingMethod: 'reencode' | 'lossless' = 'reencode'
): Promise<any> => {
  const response = await api.post(`/apply-video-cuts/${jobId}`, {
    segment_adjustments: segmentAdjustments,
    encoding_method: encodingMethod,
  }, {
    timeout: 1800000, // 30 minutes for video cutting
  });
  return response.data;
};

export const downloadCutVideo = async (jobId: string): Promise<void> => {
  const response = await api.get(`/download-video/${jobId}`, {
    responseType: 'blob',
  });

  // Create download link
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `edited_video_${jobId}.mp4`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

/**
 * Check if video processing system is ready (FFmpeg installed)
 */
export const checkVideoSystem = async (): Promise<SystemCheckResponse> => {
  const response = await api.get<SystemCheckResponse>('/video/system-check');
  return response.data;
};

export const downloadVideoXML = async (jobId: string): Promise<void> => {
  const response = await api.get(`/download-video-xml/${jobId}`, {
    responseType: 'blob',
  });

  // Create download link
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `timeline_${jobId}.xml`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

// Helper functions for upload progress (reuse existing ones if available)
const calculateUploadSpeed = (progressEvent: any): number => {
  // Simple calculation: bytes per second
  const timeElapsed = (Date.now() - progressEvent.timeStamp) / 1000;
  return progressEvent.loaded / timeElapsed;
};

const calculateETA = (progressEvent: any): number => {
  const uploadSpeed = calculateUploadSpeed(progressEvent);
  const remaining = progressEvent.total! - progressEvent.loaded;
  return remaining / uploadSpeed;
};

// ==========================================
// VIDEO AI EDITOR API METHODS
// ==========================================

/**
 * Send a natural language message to the video AI editor
 */
export const sendVideoAIChat = async (
  jobId: string,
  message: string
): Promise<any> => {
  const response = await api.post('/video/ai-chat', {
    job_id: jobId,
    message: message,
  }, {
    timeout: 120000, // 2 minutes for AI processing
  });
  return response.data;
};

/**
 * Get a preview of AI-suggested edits without applying them
 */
export const previewVideoAIEdit = async (
  jobId: string,
  operation: string,
  params?: Record<string, any>
): Promise<any> => {
  const response = await api.post('/video/ai-preview', {
    job_id: jobId,
    operation: operation,
    params: params,
  });
  return response.data;
};

/**
 * Apply AI-suggested edits to the timeline
 */
export const applyVideoAIEdit = async (
  jobId: string,
  operation: string,
  params?: Record<string, any>
): Promise<any> => {
  const response = await api.post('/video/ai-apply', {
    job_id: jobId,
    operation: operation,
    params: params,
  });
  return response.data;
};

// ==========================================
// VIDEO PROXY API METHODS (Phase 2)
// ==========================================

/**
 * Get video job status including proxy transcoding progress
 */
export const getVideoJobStatus = async (jobId: string): Promise<VideoJob> => {
  const response = await api.get<VideoJob>(`/video-status/${jobId}`);
  return response.data;
};

/**
 * Get the proxy video URL for streaming (constructs the URL)
 * Note: The actual streaming happens via the /video-proxy/<job_id> endpoint
 */
export const getVideoProxyUrl = (jobId: string): string => {
  return `${API_BASE_URL}/video-proxy/${jobId}`;
};

/**
 * Check if video proxy is ready for streaming
 */
export const checkVideoProxyReady = async (jobId: string): Promise<boolean> => {
  try {
    const status = await getVideoJobStatus(jobId);
    return status.proxy_status === 'ready';
  } catch (error) {
    console.error('Error checking video proxy status:', error);
    return false;
  }
};

/**
 * Get waveform peak data for timeline visualization
 *
 * @param jobId - Video job identifier
 * @returns Waveform data with normalized peaks [0, 1]
 * @throws 404 - Video job not found
 * @throws 425 - Proxy not ready yet (waveform generation pending)
 * @throws 500 - Waveform generation failed
 */
export const getWaveformData = async (jobId: string): Promise<WaveformData> => {
  const response = await api.get<WaveformData>(`/waveform/${jobId}`);
  return response.data;
};