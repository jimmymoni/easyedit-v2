import React from 'react';
import { AlertTriangle, ExternalLink, RefreshCw } from 'lucide-react';
import { SystemCheckResponse } from '../../types';

interface FFmpegWarningBannerProps {
  systemCheck: SystemCheckResponse;
  onRetry: () => void;
  isRetrying: boolean;
}

const FFmpegWarningBanner: React.FC<FFmpegWarningBannerProps> = ({
  systemCheck,
  onRetry,
  isRetrying
}) => {
  // Show success banner if cloud processing is enabled
  if (systemCheck.cloud_processing && systemCheck.replicate_configured) {
    return (
      <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-6 mb-8">
        <div className="flex items-start space-x-4">
          <div className="flex-shrink-0">
            <div className="bg-green-500/10 rounded-full p-3">
              <svg className="h-6 w-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
          </div>

          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-green-500 mb-2">
              Ready to Process Videos ✓
            </h3>

            <p className="text-sm text-muted-foreground mb-4 leading-relaxed">
              Cloud processing is enabled. Upload your video to get started.
            </p>

            <div className="bg-card rounded-lg border border-border p-4">
              <h4 className="text-sm font-semibold text-foreground mb-2">
                Benefits:
              </h4>
              <ul className="text-xs text-muted-foreground space-y-1.5 leading-relaxed">
                <li>• No software installation required</li>
                <li>• Fast GPU-accelerated cloud processing</li>
                <li>• Zero local resource usage</li>
                <li>• Works on any device or platform</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Don't show banner if FFmpeg is available (local mode)
  if (systemCheck.status === 'ready') {
    return null;
  }

  // Get platform-specific instructions
  const getInstructions = () => {
    const platform = systemCheck.platform;
    if (platform === 'win32' || platform === 'windows') {
      return systemCheck.install_instructions.windows;
    } else if (platform === 'darwin') {
      return systemCheck.install_instructions.macos;
    } else {
      return systemCheck.install_instructions.linux;
    }
  };

  return (
    <div className="bg-primary/5 border border-primary/20 rounded-xl p-6 mb-8">
      {/* Header */}
      <div className="flex items-start space-x-4">
        <div className="flex-shrink-0">
          <div className="bg-primary/10 rounded-full p-3">
            <AlertTriangle className="h-6 w-6 text-primary" />
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <h3 className="text-lg font-semibold text-foreground mb-2">
            FFmpeg Installation Required
          </h3>

          <p className="text-sm text-muted-foreground mb-4 leading-relaxed">
            {systemCheck.message} Video upload and processing features will not work until FFmpeg is installed on your system.
          </p>

          {/* Installation Instructions */}
          <div className="bg-card rounded-lg border border-border p-4 mb-4">
            <h4 className="text-sm font-semibold text-foreground mb-2">
              Installation Instructions:
            </h4>
            <pre className="text-xs text-muted-foreground font-mono whitespace-pre-wrap leading-relaxed">
              {getInstructions()}
            </pre>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap gap-3">
            <button
              onClick={onRetry}
              disabled={isRetrying}
              className="
                flex items-center space-x-2
                bg-primary text-primary-foreground
                hover:bg-primary/90
                disabled:opacity-50 disabled:cursor-not-allowed
                px-4 py-2 rounded-lg
                font-medium text-sm
                transition-colors
              "
            >
              <RefreshCw className={`h-4 w-4 ${isRetrying ? 'animate-spin' : ''}`} />
              <span>{isRetrying ? 'Checking...' : 'Retry Check'}</span>
            </button>

            <a
              href={systemCheck.install_url}
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
          </div>
        </div>
      </div>
    </div>
  );
};

export default FFmpegWarningBanner;
