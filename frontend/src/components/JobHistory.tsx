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
      <div className="bg-card rounded-xl border border-border p-6">
        <h3 className="text-lg font-semibold text-foreground mb-2 tracking-tight">Processing History</h3>
        <div className="text-center py-8">
          <Clock className="mx-auto h-12 w-12 text-muted-foreground/40" />
          <h3 className="mt-2 text-sm font-medium text-foreground">No jobs yet</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Upload and process your first timeline to get started.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-card rounded-xl border border-border/80 shadow-sm hover:shadow-md transition-shadow duration-200">
      <div className="p-6 border-b border-border">
        <h3 className="text-lg font-semibold text-foreground tracking-tight">Processing History</h3>
        <p className="text-sm text-muted-foreground">Recent timeline processing jobs</p>
      </div>

      <div className="divide-y divide-border">
        {jobs.map((job) => (
          <div key={job.job_id} className="p-6 hover:bg-accent/30 transition-colors">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3 flex-1">
                {getStatusIcon(job.status)}
                <div className="flex-1">
                  <div className="flex items-center space-x-2">
                    <h4 className="text-sm font-medium text-foreground">
                      Job #{job.job_id.slice(-8)}
                    </h4>
                    <span className={`
                      px-2 py-1 rounded-full text-xs font-medium
                      ${job.status === 'completed' ? 'bg-primary/10 text-primary' : ''}
                      ${job.status === 'failed' ? 'bg-destructive/10 text-destructive' : ''}
                      ${job.status === 'processing' ? 'bg-primary/10 text-primary' : ''}
                      ${job.status === 'uploaded' ? 'bg-muted text-muted-foreground' : ''}
                    `}>
                      {job.status}
                    </span>
                  </div>

                  <p className="text-sm text-muted-foreground mt-1">{job.message}</p>

                  <div className="flex items-center space-x-4 mt-2 text-xs text-muted-foreground">
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
                        <span className="text-primary">AI Transcribed</span>
                      </>
                    )}
                  </div>

                  {/* Progress Bar for Processing Jobs */}
                  {job.status === 'processing' && (
                    <div className="mt-2">
                      <div className="flex justify-between text-xs text-muted-foreground mb-1">
                        <span>Progress</span>
                        <span>{job.progress}%</span>
                      </div>
                      <div className="w-full bg-muted rounded-full h-1">
                        <div
                          className="bg-primary h-1 rounded-full transition-all duration-300"
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
                  className="text-muted-foreground hover:text-foreground p-1 transition-colors"
                  title="View details"
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </button>

                {job.status === 'completed' && (
                  <button
                    onClick={() => onDownload(job.job_id)}
                    className="text-primary hover:text-primary/80 p-1 transition-colors"
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
        <div className="p-4 border-t border-border text-center">
          <button className="text-sm text-primary hover:text-primary/80 font-medium transition-colors">
            View all jobs
          </button>
        </div>
      )}
    </div>
  );
};

export default JobHistory;