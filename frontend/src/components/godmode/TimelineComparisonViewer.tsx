import React, { useState, useEffect, useRef } from 'react';
import { GitCompare, Clock, Scissors, TrendingDown, Loader2 } from 'lucide-react';
import * as api from '../../services/api';

interface TimelineClip {
  name: string;
  start: number;
  end: number;
  duration: number;
  track: number;
  track_name: string;
  enabled: boolean;
}

interface TimelineData {
  clips: TimelineClip[];
  duration: number;
  total_clips: number;
}

interface ComparisonDiff {
  removed_regions: Array<{
    start: number;
    end: number;
    duration: number;
    name: string;
  }>;
  kept_regions: TimelineClip[];
  total_removed_duration: number;
  compression_ratio: number;
}

interface ComparisonStats {
  original_duration: number;
  edited_duration: number;
  time_saved: number;
  clips_removed: number;
  compression_percentage: number;
}

interface TimelineComparisonViewerProps {
  jobId: string;
  audioUrl: string;
  onRefresh?: () => void;
}

const TimelineComparisonViewer: React.FC<TimelineComparisonViewerProps> = ({
  jobId,
  audioUrl,
  onRefresh
}) => {
  const [comparisonData, setComparisonData] = useState<any | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scrollPosition, setScrollPosition] = useState(0);

  const originalScrollRef = useRef<HTMLDivElement>(null);
  const editedScrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadComparisonData();
  }, [jobId]);

  const loadComparisonData = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const data = await api.getTimelineComparison(jobId);
      setComparisonData(data);
    } catch (err: any) {
      console.error('Error loading timeline comparison:', err);
      setError(err.response?.data?.error || 'Failed to load timeline comparison');
    } finally {
      setIsLoading(false);
    }
  };

  const formatTime = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
      return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Synchronized scrolling
  const handleScroll = (source: 'original' | 'edited', event: React.UIEvent<HTMLDivElement>) => {
    const scrollLeft = event.currentTarget.scrollLeft;
    setScrollPosition(scrollLeft);

    // Sync the other timeline
    if (source === 'original' && editedScrollRef.current) {
      editedScrollRef.current.scrollLeft = scrollLeft;
    } else if (source === 'edited' && originalScrollRef.current) {
      originalScrollRef.current.scrollLeft = scrollLeft;
    }
  };

  // Render timeline visualization
  const renderTimeline = (data: TimelineData, type: 'original' | 'edited', diff?: ComparisonDiff) => {
    const pixelsPerSecond = 20; // Scale factor for visualization
    const timelineWidth = data.duration * pixelsPerSecond;

    return (
      <div
        ref={type === 'original' ? originalScrollRef : editedScrollRef}
        className="overflow-x-auto overflow-y-hidden pb-2"
        style={{ maxWidth: '100%' }}
        onScroll={(e) => handleScroll(type, e)}
      >
        <div
          className="relative bg-[#0A0A0A] rounded-lg border border-[#2A2A2A]"
          style={{
            width: `${timelineWidth}px`,
            height: '120px',
            minWidth: '100%'
          }}
        >
          {/* Timeline ruler */}
          <div className="absolute top-0 left-0 right-0 h-6 border-b border-[#2A2A2A] flex items-center px-2">
            {Array.from({ length: Math.ceil(data.duration / 10) }).map((_, i) => (
              <div
                key={i}
                className="absolute text-xs text-[#EAEAEA]/50 font-mono"
                style={{ left: `${i * 10 * pixelsPerSecond}px` }}
              >
                {formatTime(i * 10)}
              </div>
            ))}
          </div>

          {/* Clips */}
          <div className="absolute top-6 left-0 right-0 bottom-0">
            {data.clips.map((clip, index) => (
              <div
                key={index}
                className="absolute bg-[#FF6B35] hover:bg-[#FF8555] border border-[#EAEAEA]/20 rounded transition-colors cursor-pointer group"
                style={{
                  left: `${clip.start * pixelsPerSecond}px`,
                  width: `${clip.duration * pixelsPerSecond}px`,
                  top: '10px',
                  height: '90px'
                }}
                title={`${clip.name}\n${formatTime(clip.start)} - ${formatTime(clip.end)}\nDuration: ${formatTime(clip.duration)}`}
              >
                <div className="p-1 text-xs text-white truncate">
                  {clip.name}
                </div>
              </div>
            ))}

            {/* Show removed regions for original timeline */}
            {type === 'original' && diff && diff.removed_regions.map((region, index) => (
              <div
                key={`removed-${index}`}
                className="absolute bg-red-500/30 border border-red-500/50 rounded"
                style={{
                  left: `${region.start * pixelsPerSecond}px`,
                  width: `${region.duration * pixelsPerSecond}px`,
                  top: '10px',
                  height: '90px',
                  pointerEvents: 'none'
                }}
                title={`REMOVED: ${formatTime(region.start)} - ${formatTime(region.end)}`}
              >
                <div className="flex items-center justify-center h-full">
                  <Scissors className="h-6 w-6 text-red-500" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  if (isLoading) {
    return (
      <div className="bg-[#181818] border border-[#2A2A2A] rounded-xl shadow-lg p-8 flex items-center justify-center min-h-[400px]">
        <div className="flex items-center space-x-3">
          <Loader2 className="animate-spin h-8 w-8 text-[#FF6B35]" />
          <span className="text-[#EAEAEA]/70">Loading timeline comparison...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-[#181818] border border-[#2A2A2A] rounded-xl shadow-lg p-8">
        <div className="text-center">
          <GitCompare className="h-12 w-12 text-[#EAEAEA]/30 mx-auto mb-3" />
          <p className="text-red-400 mb-2">Error Loading Comparison</p>
          <p className="text-[#EAEAEA]/70 text-sm">{error}</p>
          <button
            onClick={loadComparisonData}
            className="mt-4 bg-[#FF6B35] hover:bg-[#FF8555] text-white px-4 py-2 rounded-lg text-sm transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!comparisonData) {
    return null;
  }

  const { original, edited, diff, stats, has_edits } = comparisonData;

  return (
    <div className="bg-[#181818] border border-[#2A2A2A] rounded-xl shadow-lg p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <GitCompare className="h-6 w-6 text-[#FF6B35]" />
          <h3 className="text-lg font-semibold text-[#EAEAEA]">Timeline Comparison</h3>
        </div>
        {has_edits && (
          <div className="flex items-center space-x-2 text-sm text-[#FF6B35]">
            <TrendingDown className="h-4 w-4" />
            <span className="font-semibold">{stats.compression_percentage}% compression</span>
          </div>
        )}
      </div>

      {/* Statistics */}
      {has_edits && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-[#0A0A0A] border border-[#2A2A2A] rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-1">
              <Clock className="h-4 w-4 text-[#EAEAEA]/70" />
              <span className="text-xs text-[#EAEAEA]/70">Original</span>
            </div>
            <p className="text-lg font-semibold text-[#EAEAEA]">
              {formatTime(stats.original_duration)}
            </p>
          </div>

          <div className="bg-[#0A0A0A] border border-[#2A2A2A] rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-1">
              <Clock className="h-4 w-4 text-[#FF6B35]" />
              <span className="text-xs text-[#EAEAEA]/70">Edited</span>
            </div>
            <p className="text-lg font-semibold text-[#FF6B35]">
              {formatTime(stats.edited_duration)}
            </p>
          </div>

          <div className="bg-[#0A0A0A] border border-[#2A2A2A] rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-1">
              <Scissors className="h-4 w-4 text-[#EAEAEA]/70" />
              <span className="text-xs text-[#EAEAEA]/70">Time Saved</span>
            </div>
            <p className="text-lg font-semibold text-[#EAEAEA]">
              {formatTime(stats.time_saved)}
            </p>
          </div>

          <div className="bg-[#0A0A0A] border border-[#2A2A2A] rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-1">
              <GitCompare className="h-4 w-4 text-[#EAEAEA]/70" />
              <span className="text-xs text-[#EAEAEA]/70">Clips Removed</span>
            </div>
            <p className="text-lg font-semibold text-[#EAEAEA]">
              {stats.clips_removed}
            </p>
          </div>
        </div>
      )}

      {/* Original Timeline */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-semibold text-[#EAEAEA]">Original Timeline</h4>
          <span className="text-xs text-[#EAEAEA]/70">
            {original.total_clips} clips • {formatTime(original.duration)}
          </span>
        </div>
        {renderTimeline(original, 'original', has_edits ? diff : undefined)}
      </div>

      {/* Edited Timeline */}
      {has_edits && edited && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-semibold text-[#FF6B35]">Edited Timeline</h4>
            <span className="text-xs text-[#EAEAEA]/70">
              {edited.total_clips} clips • {formatTime(edited.duration)}
            </span>
          </div>
          {renderTimeline(edited, 'edited')}
        </div>
      )}

      {/* No edits message */}
      {!has_edits && (
        <div className="bg-[#0A0A0A] border border-[#2A2A2A] rounded-lg p-8 text-center">
          <p className="text-[#EAEAEA]/70 mb-4">
            No AI edits have been applied yet. Use the prompt below to make timeline edits.
          </p>
          <p className="text-sm text-[#EAEAEA]/50">
            Try commands like "cut all the ums" or "remove long pauses"
          </p>
        </div>
      )}

      {/* Scroll hint */}
      <div className="flex items-center justify-center text-xs text-[#EAEAEA]/50">
        <span>← Scroll horizontally to navigate timeline →</span>
      </div>
    </div>
  );
};

export default TimelineComparisonViewer;
