import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ProcessingJob, ProcessingStats } from '../types';
import { CheckCircle, AlertCircle, Clock, Download, BarChart3 } from 'lucide-react';
import ProcessingTimer from './ProcessingTimer';

interface ProcessingStatusProps {
  job: ProcessingJob;
  onDownload: (jobId: string) => void;
}

const ProcessingStatus: React.FC<ProcessingStatusProps> = ({ job, onDownload }) => {
  const navigate = useNavigate();

  const getStatusIcon = () => {
    switch (job.status) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'failed':
        return <AlertCircle className="h-5 w-5 text-red-500" />;
      case 'processing':
        return <Clock className="h-5 w-5 text-blue-500 animate-spin" />;
      default:
        return <Clock className="h-5 w-5 text-gray-500" />;
    }
  };

  const getStatusColor = () => {
    switch (job.status) {
      case 'completed':
        return 'text-green-700 bg-green-100';
      case 'failed':
        return 'text-red-700 bg-red-100';
      case 'processing':
        return 'text-blue-700 bg-blue-100';
      default:
        return 'text-gray-700 bg-gray-100';
    }
  };

  const formatDuration = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  const formatPercentage = (value: number): string => {
    return `${(value * 100).toFixed(1)}%`;
  };

  return (
    <div className="bg-card rounded-xl border border-border/80 shadow-sm hover:shadow-md transition-shadow duration-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          {getStatusIcon()}
          <div>
            <h3 className="text-lg font-semibold text-foreground tracking-tight">Processing Status</h3>
            <p className="text-sm text-muted-foreground font-mono">Job ID: {job.job_id}</p>
          </div>
        </div>
        <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor()}`}>
          {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
        </span>
      </div>

      {/* Processing Timer */}
      {job.status === 'processing' && (
        <div className="mb-4">
          <ProcessingTimer
            startTime={new Date(job.created_at).getTime()}
            estimatedDuration={60} // 60 seconds estimate, adjust based on file size
            isProcessing={true}
          />
        </div>
      )}

      {/* Status Message */}
      <div className="mb-4">
        <p className="text-sm text-foreground">{job.message}</p>
        <p className="text-xs text-muted-foreground mt-1">
          Created: {new Date(job.created_at).toLocaleString()}
        </p>
      </div>

      {/* Processing Statistics */}
      {job.stats && (
        <div className="border-t border-border pt-4">
          <div className="flex items-center space-x-2 mb-3">
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
            <h4 className="text-sm font-semibold text-foreground">Processing Results</h4>
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Original Duration:</span>
                <span className="font-medium text-foreground">{formatDuration(job.stats.original_duration)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Edited Duration:</span>
                <span className="font-medium text-foreground">{formatDuration(job.stats.edited_duration)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Time Saved:</span>
                <span className="font-medium text-primary">
                  {formatDuration(job.stats.duration_reduction)}
                </span>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Original Clips:</span>
                <span className="font-medium text-foreground">{job.stats.original_clips}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Edited Clips:</span>
                <span className="font-medium text-foreground">{job.stats.edited_clips}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Compression:</span>
                <span className="font-medium text-primary">
                  {formatPercentage(job.stats.compression_ratio)}
                </span>
              </div>
            </div>
          </div>

          {/* Additional Stats */}
          <div className="mt-3 pt-3 border-t border-border">
            <div className="flex justify-between items-center text-sm">
              <span className="text-muted-foreground">Tracks Processed:</span>
              <span className="font-medium text-foreground">{job.stats.tracks_processed}</span>
            </div>
            {job.stats.markers_added > 0 && (
              <div className="flex justify-between items-center text-sm mt-1">
                <span className="text-muted-foreground">Markers Added:</span>
                <span className="font-medium text-foreground">{job.stats.markers_added}</span>
              </div>
            )}
            {job.transcription_available && (
              <div className="flex items-center text-sm mt-2 text-primary">
                <CheckCircle className="h-3 w-3 mr-1" />
                <span>AI transcription completed</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Download Button */}
      {job.status === 'completed' && (
        <div className="mt-4 pt-4 border-t border-border space-y-3">
          <button
            onClick={() => onDownload(job.job_id)}
            className="w-full flex items-center justify-center space-x-2 bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2.5 rounded-lg font-medium transition-colors"
          >
            <Download className="h-4 w-4" />
            <span>Download Edited Timeline (.drt)</span>
          </button>

          {/* Enter God Mode Button */}
          <button
            onClick={() => navigate(`/godmode/${job.job_id}`)}
            className="w-full flex items-center justify-center space-x-2 bg-[#181818] border border-[#2A2A2A] text-[#EAEAEA] hover:bg-[#FF6B35] hover:text-white transition-all duration-300 px-4 py-2.5 rounded-lg font-medium"
          >
            <span className="text-lg">⚡</span>
            <span>Enter God Mode</span>
          </button>
        </div>
      )}

      {/* Error Details */}
      {job.status === 'failed' && (
        <div className="mt-4 p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
          <p className="text-sm text-destructive">
            Processing failed. Please check your files and try again.
          </p>
        </div>
      )}
    </div>
  );
};

export default ProcessingStatus;