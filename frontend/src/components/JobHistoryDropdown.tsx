import React from 'react';
import { ProcessingJob } from '../types';
import { History, CheckCircle, AlertCircle, Clock, Download } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';

interface JobHistoryDropdownProps {
  jobs: ProcessingJob[];
  onDownload: (jobId: string) => void;
  onViewDetails: (job: ProcessingJob) => void;
}

const JobHistoryDropdown: React.FC<JobHistoryDropdownProps> = ({ jobs, onDownload, onViewDetails }) => {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-3.5 w-3.5 text-primary" />;
      case 'failed':
        return <AlertCircle className="h-3.5 w-3.5 text-destructive" />;
      case 'processing':
        return <Clock className="h-3.5 w-3.5 text-primary animate-pulse" />;
      default:
        return <Clock className="h-3.5 w-3.5 text-muted-foreground" />;
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMinutes / 60);

    if (diffHours < 1) {
      return `${diffMinutes}m ago`;
    } else if (diffHours < 24) {
      return `${diffHours}h ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  const recentJobs = jobs.slice(0, 8);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="h-9 gap-2">
          <History className="h-4 w-4" />
          <span className="hidden md:inline">History</span>
          {jobs.length > 0 && (
            <span className="rounded-full bg-primary/20 px-2 py-0.5 text-xs font-medium text-primary">
              {jobs.length}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[380px]">
        <DropdownMenuLabel className="font-semibold">
          Processing History
        </DropdownMenuLabel>
        <DropdownMenuSeparator />

        {recentJobs.length === 0 ? (
          <div className="px-2 py-8 text-center text-sm text-muted-foreground">
            No processing history yet
          </div>
        ) : (
          <div className="max-h-[400px] overflow-y-auto">
            {recentJobs.map((job) => (
              <DropdownMenuItem
                key={job.job_id}
                className="flex items-start gap-3 p-3 cursor-pointer"
                onSelect={() => onViewDetails(job)}
              >
                <div className="mt-0.5">{getStatusIcon(job.status)}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-foreground truncate">
                      Job #{job.job_id.slice(-8)}
                    </span>
                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                      {formatDate(job.created_at)}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5 truncate">
                    {job.message}
                  </p>
                  {job.status === 'processing' && job.progress && (
                    <div className="mt-1.5 w-full bg-muted rounded-full h-1">
                      <div
                        className="bg-primary h-1 rounded-full transition-all duration-300"
                        style={{ width: `${job.progress}%` }}
                      />
                    </div>
                  )}
                </div>
                {job.status === 'completed' && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 flex-shrink-0"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDownload(job.job_id);
                    }}
                  >
                    <Download className="h-3.5 w-3.5" />
                  </Button>
                )}
              </DropdownMenuItem>
            ))}
          </div>
        )}

        {jobs.length > 8 && (
          <>
            <DropdownMenuSeparator />
            <div className="px-2 py-2 text-center">
              <button className="text-xs text-primary hover:underline font-medium">
                View all {jobs.length} jobs
              </button>
            </div>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export default JobHistoryDropdown;
