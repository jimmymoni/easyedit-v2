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
  // Don't show banner if FFmpeg is available
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
