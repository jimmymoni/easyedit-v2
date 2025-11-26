/**
 * WebSocket hook for real-time upload status updates
 *
 * Subscribes to job-specific WebSocket events to receive async upload
 * progress updates (validating, saving, ready, validation_failed).
 *
 * Features:
 * - Automatic connection/disconnection management
 * - Job-specific room subscription
 * - Real-time status, progress, and message updates
 * - Cleanup on unmount
 *
 * Usage:
 * ```tsx
 * const { uploadStatus, uploadProgress, uploadMessage } = useUploadWebSocket(jobId);
 * ```
 */

import { useEffect, useState } from 'react';
import { io, Socket } from 'socket.io-client';

interface UploadWebSocketResult {
  uploadStatus: string;
  uploadProgress: number;
  uploadMessage: string;
  isConnected: boolean;
}

export const useUploadWebSocket = (jobId: string | null): UploadWebSocketResult => {
  const [uploadStatus, setUploadStatus] = useState<string>('created');
  const [uploadProgress, setUploadProgress] = useState<number>(5);
  const [uploadMessage, setUploadMessage] = useState<string>('');
  const [isConnected, setIsConnected] = useState<boolean>(false);

  useEffect(() => {
    if (!jobId) return;

    let socket: Socket | null = null;

    const connectWebSocket = () => {
      // Get API base URL from environment
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? '/api' : 'http://localhost:5000');

      // Get JWT token from localStorage
      const token = localStorage.getItem('token');

      // Connect to backend WebSocket server
      socket = io(API_BASE_URL, {
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionAttempts: 5,
        auth: {
          token: token // Include JWT for authentication
        }
      });

      // Handle connection events
      socket.on('connect', () => {
        console.log(`[WebSocket] Connected, subscribing to job ${jobId}`);
        setIsConnected(true);

        // Subscribe to job-specific updates
        socket!.emit('subscribe_job', { job_id: jobId });
      });

      socket.on('disconnect', () => {
        console.log('[WebSocket] Disconnected');
        setIsConnected(false);
      });

      socket.on('connect_error', (error) => {
        console.error('[WebSocket] Connection error:', error);
        setIsConnected(false);
      });

      // Handle subscription confirmation
      socket.on('subscribed', (data) => {
        console.log(`[WebSocket] Subscribed to job ${data.job_id}`);
      });

      // Handle job status updates (main event)
      socket.on('job_update', (data) => {
        console.log('[WebSocket] Job update received:', data);

        if (data.status) {
          setUploadStatus(data.status);
        }

        if (data.progress !== undefined) {
          setUploadProgress(data.progress);
        }

        if (data.message) {
          setUploadMessage(data.message);
        }
      });

      // Handle errors
      socket.on('error', (data) => {
        console.error('[WebSocket] Error:', data.message);
        setUploadMessage(`Error: ${data.message}`);
      });

      // Handle ping/pong for connection keepalive
      socket.on('pong', (data) => {
        console.log('[WebSocket] Pong received:', data.timestamp);
      });
    };

    // Connect WebSocket
    connectWebSocket();

    // Cleanup on unmount
    return () => {
      if (socket) {
        console.log(`[WebSocket] Unsubscribing from job ${jobId}`);

        // Unsubscribe from job updates
        socket.emit('unsubscribe_job', { job_id: jobId });

        // Disconnect socket
        socket.disconnect();
        socket = null;
      }
    };
  }, [jobId]);

  return {
    uploadStatus,
    uploadProgress,
    uploadMessage,
    isConnected
  };
};
