import React from 'react';
import { ProcessingJob, ProcessingStats } from '../types';
import { CheckCircle, AlertCircle, Clock, Download, BarChart3 } from 'lucide-react';

interface ProcessingStatusProps {
  job: ProcessingJob;
  onDownload: (jobId: string) => void;
}

const ProcessingStatus: React.FC<ProcessingStatusProps> = ({ job, onDownload }) => {
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
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          {getStatusIcon()}
          <div>
            <h3 className="text-lg font-medium text-gray-900">Processing Status</h3>
            <p className="text-sm text-gray-500">Job ID: {job.job_id}</p>
          </div>
        </div>
        <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor()}`}>
          {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
        </span>
      </div>

      {/* Progress Bar */}
      {job.status === 'processing' && (
        <div className="mb-4">
          <div className="flex justify-between text-sm text-gray-600 mb-1">
            <span>Progress</span>
            <span>{job.progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-primary-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Status Message */}
      <div className="mb-4">
        <p className="text-sm text-gray-700">{job.message}</p>
        <p className="text-xs text-gray-500 mt-1">
          Created: {new Date(job.created_at).toLocaleString()}
        </p>
      </div>

      {/* Processing Statistics */}
      {job.stats && (
        <div className="border-t border-gray-200 pt-4">
          <div className="flex items-center space-x-2 mb-3">
            <BarChart3 className="h-4 w-4 text-gray-600" />
            <h4 className="text-sm font-medium text-gray-900">Processing Results</h4>
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-600">Original Duration:</span>
                <span className="font-medium">{formatDuration(job.stats.original_duration)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Edited Duration:</span>
                <span className="font-medium">{formatDuration(job.stats.edited_duration)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Time Saved:</span>
                <span className="font-medium text-green-600">
                  {formatDuration(job.stats.duration_reduction)}
                </span>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-600">Original Clips:</span>
                <span className="font-medium">{job.stats.original_clips}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Edited Clips:</span>
                <span className="font-medium">{job.stats.edited_clips}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Compression:</span>
                <span className="font-medium text-blue-600">
                  {formatPercentage(job.stats.compression_ratio)}
                </span>
              </div>
            </div>
          </div>

          {/* Additional Stats */}
          <div className="mt-3 pt-3 border-t border-gray-100">
            <div className="flex justify-between items-center text-sm">
              <span className="text-gray-600">Tracks Processed:</span>
              <span className="font-medium">{job.stats.tracks_processed}</span>
            </div>
            {job.stats.markers_added > 0 && (
              <div className="flex justify-between items-center text-sm mt-1">
                <span className="text-gray-600">Markers Added:</span>
                <span className="font-medium">{job.stats.markers_added}</span>
              </div>
            )}
            {job.transcription_available && (
              <div className="flex items-center text-sm mt-2 text-green-600">
                <CheckCircle className="h-3 w-3 mr-1" />
                <span>AI transcription completed</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Download Button */}
      {job.status === 'completed' && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <button
            onClick={() => onDownload(job.job_id)}
            className="w-full flex items-center justify-center space-x-2 bg-primary-600 hover:bg-primary-700 text-white px-4 py-2 rounded-md transition-colors"
          >
            <Download className="h-4 w-4" />
            <span>Download Edited Timeline (.drt)</span>
          </button>
        </div>
      )}

      {/* Error Details */}
      {job.status === 'failed' && (
        <div className="mt-4 p-3 bg-red-50 rounded-md">
          <p className="text-sm text-red-800">
            Processing failed. Please check your files and try again.
          </p>
        </div>
      )}
    </div>
  );
};

export default ProcessingStatus;