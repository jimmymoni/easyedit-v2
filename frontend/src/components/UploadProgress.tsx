import React from 'react';
import { Upload, CheckCircle2 } from 'lucide-react';
import { UploadProgress as UploadProgressType } from '../services/api';

interface UploadProgressProps {
  progress: UploadProgressType;
  isComplete?: boolean;
}

const UploadProgress: React.FC<UploadProgressProps> = ({ progress, isComplete = false }) => {
  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatTime = (seconds: number): string => {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  return (
    <div className="w-full bg-[#181818] border border-[#2A2A2A] rounded-xl shadow-lg p-6 animate-fade-in transition-all duration-300">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          {isComplete ? (
            <CheckCircle2 className="h-6 w-6 text-orange-500 animate-scale-in" />
          ) : (
            <Upload className="h-6 w-6 text-orange-500 animate-pulse" />
          )}
          <div>
            <h3 className="text-lg font-semibold text-[#EAEAEA]">
              {isComplete ? 'Upload Complete!' : 'Uploading Files...'}
            </h3>
            <p className="text-sm text-[#EAEAEA]/70">
              {isComplete
                ? 'Files uploaded successfully'
                : `${formatBytes(progress.uploadedBytes)} / ${formatBytes(progress.totalBytes)}`}
            </p>
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-[#EAEAEA]">{progress.percentage}%</div>
          {!isComplete && progress.uploadSpeed > 0 && (
            <div className="text-sm text-[#EAEAEA]/70">{progress.uploadSpeed.toFixed(1)} MB/s</div>
          )}
        </div>
      </div>

      {/* Progress Bar */}
      <div className="relative">
        <div className="w-full h-3 bg-muted/20 rounded-full overflow-hidden border border-[#2A2A2A]">
          <div
            className={`h-full transition-all duration-300 ease-out ${
              isComplete
                ? 'shadow-[0_0_6px_rgba(255,107,53,0.5)]'
                : ''
            }`}
            style={{
              width: `${progress.percentage}%`,
              background: isComplete
                ? 'linear-gradient(90deg, #FF6B35, #FF884F)'
                : '#FF6B35'
            }}
          >
            {/* Animated shimmer effect */}
            <div className="h-full w-full bg-gradient-to-r from-transparent via-white to-transparent opacity-20 animate-shimmer" />
          </div>
        </div>
      </div>

      {/* Time Remaining */}
      {!isComplete && progress.estimatedTimeRemaining > 0 && (
        <div className="mt-3 text-center">
          <p className="text-sm text-[#EAEAEA]/70">
            Estimated time remaining:{' '}
            <span className="font-medium text-[#EAEAEA]">
              {formatTime(progress.estimatedTimeRemaining)}
            </span>
          </p>
        </div>
      )}

      {isComplete && (
        <div className="mt-3 text-center text-sm text-orange-500 font-medium">
          Processing will begin shortly...
        </div>
      )}
    </div>
  );
};

export default UploadProgress;
