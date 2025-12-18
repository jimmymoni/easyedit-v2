import { useState, useEffect, useRef } from 'react';
import * as api from '../../services/api';
import { WaveformData, WaveformState } from '../../types';

/**
 * useWaveform Hook
 *
 * Fetches and caches waveform peak data for timeline visualization.
 *
 * Features:
 * - Automatic fetching on mount
 * - In-memory caching (prevents refetching on remount)
 * - Retry logic for 425 Too Early responses
 * - Error handling for 404, 500, and network errors
 *
 * @param jobId - Video job identifier
 * @returns Waveform state { data, loading, error }
 *
 * @example
 * ```tsx
 * const { waveformData, loading, error } = useWaveform('abc-123');
 *
 * if (loading) return <div>Loading waveform...</div>;
 * if (error) return <div>Error: {error}</div>;
 * if (!waveformData) return null;
 *
 * // Use waveformData.peaks to render waveform
 * ```
 */

// In-memory cache for waveform data (persists across component remounts)
const waveformCache = new Map<string, WaveformData>();

const useWaveform = (jobId: string): WaveformState => {
  const [data, setData] = useState<WaveformData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Track retry timeout to clean up on unmount
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Check cache first
    const cached = waveformCache.get(jobId);
    if (cached) {
      setData(cached);
      setLoading(false);
      setError(null);
      return;
    }

    // Fetch waveform data from API
    const fetchWaveform = async () => {
      try {
        setLoading(true);
        setError(null);

        const waveformData = await api.getWaveformData(jobId);

        // Cache the data
        waveformCache.set(jobId, waveformData);

        setData(waveformData);
        setError(null);
      } catch (err: any) {
        const status = err.response?.status;
        const errorCode = err.response?.data?.code;
        const errorMessage = err.response?.data?.error;

        if (status === 425) {
          // Proxy not ready or waveform generating - retry after 2 seconds
          setError('Waveform not ready yet. Waiting for proxy...');

          retryTimeoutRef.current = setTimeout(() => {
            fetchWaveform(); // Retry
          }, 2000);
        } else if (status === 404) {
          setError('Video job not found.');
        } else if (errorCode === 'WAVEFORM_GENERATION_FAILED') {
          setError('This video has no audio track.');
        } else if (errorMessage) {
          setError(errorMessage);
        } else {
          setError('Failed to load waveform. Please try again.');
        }

        console.error('Error fetching waveform:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchWaveform();

    // Cleanup: Clear retry timeout on unmount
    return () => {
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
      }
    };
  }, [jobId]);

  return { data, loading, error };
};

export default useWaveform;
