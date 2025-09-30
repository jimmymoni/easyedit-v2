import React from 'react';
import { ProcessingJob } from '../types';
import { CheckCircle, AlertCircle, Clock, Download, Trash2 } from 'lucide-react';

interface JobHistoryProps {
  jobs: ProcessingJob[];
  onDownload: (jobId: string) => void;
  onViewDetails: (job: ProcessingJob) => void;
}

const JobHistory: React.FC<JobHistoryProps> = ({ jobs, onDownload, onViewDetails }) => {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      case 'processing':
        return <Clock className="h-4 w-4 text-blue-500" />;
      default:
        return <Clock className="h-4 w-4 text-gray-500" />;
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = diffMs / (1000 * 60 * 60);

    if (diffHours < 24) {
      if (diffHours < 1) {
        const diffMinutes = Math.floor(diffMs / (1000 * 60));
        return `${diffMinutes} min ago`;
      }
      return `${Math.floor(diffHours)} hours ago`;
    } else if (diffHours < 168) { // Less than a week
      const diffDays = Math.floor(diffHours / 24);
      return `${diffDays} days ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  const formatDuration = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  if (jobs.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-2">Processing History</h3>
        <div className="text-center py-8">
          <Clock className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No jobs yet</h3>
          <p className="mt-1 text-sm text-gray-500">
            Upload and process your first timeline to get started.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      <div className="p-6 border-b border-gray-200">
        <h3 className="text-lg font-medium text-gray-900">Processing History</h3>
        <p className="text-sm text-gray-500">Recent timeline processing jobs</p>
      </div>

      <div className="divide-y divide-gray-200">
        {jobs.map((job) => (
          <div key={job.job_id} className="p-6 hover:bg-gray-50 transition-colors">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3 flex-1">
                {getStatusIcon(job.status)}
                <div className="flex-1">
                  <div className="flex items-center space-x-2">
                    <h4 className="text-sm font-medium text-gray-900">
                      Job #{job.job_id.slice(-8)}
                    </h4>
                    <span className={`
                      px-2 py-1 rounded-full text-xs font-medium
                      ${job.status === 'completed' ? 'bg-green-100 text-green-800' : ''}
                      ${job.status === 'failed' ? 'bg-red-100 text-red-800' : ''}
                      ${job.status === 'processing' ? 'bg-blue-100 text-blue-800' : ''}
                      ${job.status === 'uploaded' ? 'bg-gray-100 text-gray-800' : ''}
                    `}>
                      {job.status}
                    </span>
                  </div>

                  <p className="text-sm text-gray-500 mt-1">{job.message}</p>

                  <div className="flex items-center space-x-4 mt-2 text-xs text-gray-500">
                    <span>{formatDate(job.created_at)}</span>
                    {job.stats && (
                      <>
                        <span>•</span>
                        <span>
                          {formatDuration(job.stats.original_duration)} → {formatDuration(job.stats.edited_duration)}
                        </span>
                        <span>•</span>
                        <span>
                          {job.stats.clips_change > 0 ? '+' : ''}{job.stats.clips_change} clips
                        </span>
                      </>
                    )}
                    {job.transcription_available && (
                      <>
                        <span>•</span>
                        <span className="text-green-600">AI Transcribed</span>
                      </>
                    )}
                  </div>

                  {/* Progress Bar for Processing Jobs */}
                  {job.status === 'processing' && (
                    <div className="mt-2">
                      <div className="flex justify-between text-xs text-gray-500 mb-1">
                        <span>Progress</span>
                        <span>{job.progress}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-1">
                        <div
                          className="bg-blue-500 h-1 rounded-full transition-all duration-300"
                          style={{ width: `${job.progress}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <button
                  onClick={() => onViewDetails(job)}
                  className="text-gray-400 hover:text-gray-600 p-1"
                  title="View details"
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </button>

                {job.status === 'completed' && (
                  <button
                    onClick={() => onDownload(job.job_id)}
                    className="text-primary-600 hover:text-primary-700 p-1"
                    title="Download result"
                  >
                    <Download className="h-4 w-4" />
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {jobs.length > 5 && (
        <div className="p-4 border-t border-gray-200 text-center">
          <button className="text-sm text-primary-600 hover:text-primary-700">
            View all jobs
          </button>
        </div>
      )}
    </div>
  );
};

export default JobHistory;