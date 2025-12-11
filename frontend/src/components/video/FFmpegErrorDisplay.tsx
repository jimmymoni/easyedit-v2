import React from 'react';
import { AlertCircle, ExternalLink, RefreshCw } from 'lucide-react';

interface FFmpegErrorDisplayProps {
  error: string;
  platform?: string;
  installUrl?: string;
  onRetry?: () => void;
  onDismiss?: () => void;
}

const FFmpegErrorDisplay: React.FC<FFmpegErrorDisplayProps> = ({
  error,
  platform,
  installUrl,
  onRetry,
  onDismiss
}) => {
  // Check if error is FFmpeg-related
  const isFFmpegError = error.toLowerCase().includes('ffmpeg');

  // Get platform-specific quick help
  const getQuickHelp = () => {
    if (!platform) return null;

    if (platform === 'win32' || platform === 'windows') {
      return 'Windows: Download from link below and add to PATH';
    } else if (platform === 'darwin') {
      return 'macOS: Run "brew install ffmpeg" in terminal';
    } else {
      return 'Linux: Run "sudo apt-get install ffmpeg" in terminal';
    }
  };

  return (
    <div className="bg-destructive/10 border border-destructive/20 rounded-xl p-6 mb-6">
      {/* Header */}
      <div className="flex items-start space-x-3 mb-4">
        <AlertCircle className="h-6 w-6 text-destructive flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <h3 className="text-base font-semibold text-destructive mb-1">
            {isFFmpegError ? 'FFmpeg Not Available' : 'Upload Failed'}
          </h3>
          <p className="text-sm text-destructive/80 leading-relaxed">
            {error}
          </p>
        </div>
      </div>

      {/* FFmpeg-specific help */}
      {isFFmpegError && (
        <div className="bg-card rounded-lg border border-border p-4 mb-4">
          <h4 className="text-sm font-semibold text-foreground mb-2">
            Quick Fix:
          </h4>
          <p className="text-sm text-muted-foreground mb-3">
            {getQuickHelp() || 'FFmpeg is required for video processing.'}
          </p>
          <p className="text-xs text-muted-foreground">
            After installing FFmpeg, click "Retry Check" or try uploading again.
          </p>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-3">
        {onRetry && (
          <button
            onClick={onRetry}
            className="
              flex items-center space-x-2
              bg-primary text-primary-foreground
              hover:bg-primary/90
              px-4 py-2 rounded-lg
              font-medium text-sm
              transition-colors
            "
          >
            <RefreshCw className="h-4 w-4" />
            <span>Retry Check</span>
          </button>
        )}

        {installUrl && (
          <a
            href={installUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="
              flex items-center space-x-2
              bg-card border border-border
              text-foreground hover:bg-accent
              px-4 py-2 rounded-lg
              font-medium text-sm
              transition-colors
            "
          >
            <ExternalLink className="h-4 w-4" />
            <span>Download FFmpeg</span>
          </a>
        )}

        {onDismiss && (
          <button
            onClick={onDismiss}
            className="
              text-sm text-muted-foreground
              hover:text-foreground
              underline
              px-2 py-2
              transition-colors
            "
          >
            Dismiss
          </button>
        )}
      </div>
    </div>
  );
};

export default FFmpegErrorDisplay;
