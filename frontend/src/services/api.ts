import axios from 'axios';
import { ProcessingJob, ProcessingOptions, UploadResponse, ProcessingResponse } from '../types';

const api = axios.create({
  baseURL: import.meta.env.DEV ? '/api' : 'http://localhost:5000',
  timeout: 300000, // 5 minutes for long processing jobs
});

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