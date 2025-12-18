/**
 * Status Mapping Utility
 *
 * Maps backend WebSocket status updates to frontend ProcessingJob status types.
 *
 * Backend statuses: created, validating, saving, ready, validation_failed, failed
 * Frontend statuses: uploaded, processing, completed, failed
 */

interface BackendStatus {
  status: string;
  progress: number;
  message: string;
}

interface MappedStatus {
  status: 'uploaded' | 'processing' | 'completed' | 'failed';
  progress: number;
  message: string;
  phase?: 'created' | 'validating' | 'saving' | 'ready';
}

/**
 * Maps backend WebSocket status to frontend ProcessingJob status
 *
 * @param backendStatus - Status update from WebSocket
 * @returns Mapped status compatible with frontend types
 */
export const mapBackendToFrontendStatus = (backendStatus: BackendStatus): MappedStatus => {
  switch (backendStatus.status) {
    case 'created':
      return {
        status: 'uploaded',
        progress: backendStatus.progress,
        message: backendStatus.message || 'Upload received',
        phase: 'created'
      };

    case 'validating':
      return {
        status: 'uploaded',
        progress: backendStatus.progress,
        message: backendStatus.message || 'Validating files...',
        phase: 'validating'
      };

    case 'saving':
      return {
        status: 'uploaded',
        progress: backendStatus.progress,
        message: backendStatus.message || 'Saving files to disk...',
        phase: 'saving'
      };

    case 'ready':
      return {
        status: 'uploaded',
        progress: 100,
        message: backendStatus.message || 'Ready for processing',
        phase: 'ready'
      };

    case 'validation_failed':
      return {
        status: 'failed',
        progress: 0,
        message: backendStatus.message || 'File validation failed'
      };

    case 'failed':
      return {
        status: 'failed',
        progress: 0,
        message: backendStatus.message || 'Upload failed'
      };

    default:
      // Fallback: return as-is with uploaded status
      return {
        status: 'uploaded',
        progress: backendStatus.progress || 0,
        message: backendStatus.message || 'Processing...'
      };
  }
};

/**
 * Checks if the upload phase is complete (files validated and saved)
 *
 * @param status - Backend status string
 * @returns True if upload is ready for processing
 */
export const isUploadPhaseComplete = (status: string): boolean => {
  return status === 'ready';
};

/**
 * Checks if the upload failed during validation or saving
 *
 * @param status - Backend status string
 * @returns True if upload failed
 */
export const isUploadPhaseFailed = (status: string): boolean => {
  return status === 'validation_failed' || status === 'failed';
};
