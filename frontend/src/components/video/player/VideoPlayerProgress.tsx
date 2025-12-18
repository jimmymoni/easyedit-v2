import React, { useRef } from 'react';
import { VideoPlayerProgressProps } from './VideoPlayer.types';

/**
 * VideoPlayerProgress Component
 *
 * Progress bar with:
 * - Click-to-seek functionality
 * - Buffered portion indicator (gray)
 * - Played portion indicator (orange)
 * - Hover to show scrubber handle
 */
const VideoPlayerProgress: React.FC<VideoPlayerProgressProps> = ({
  currentTime,
  duration,
  buffered,
  onSeek,
}) => {
  const progressBarRef = useRef<HTMLDivElement>(null);

  const handleProgressBarClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!progressBarRef.current || !duration || !isFinite(duration)) return;

    const rect = progressBarRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percentage = x / rect.width;
    const newTime = percentage * duration;

    // Clamp between 0 and duration
    const clampedTime = Math.max(0, Math.min(duration, newTime));
    onSeek(clampedTime);
  };

  // Calculate progress percentage
  const progressPercentage = duration && isFinite(duration)
    ? (currentTime / duration) * 100
    : 0;

  // Calculate buffered percentage
  const bufferedPercentage = duration && isFinite(duration)
    ? Math.min(buffered, 100)
    : 0;

  return (
    <div
      ref={progressBarRef}
      className="relative w-full h-1 bg-gray-600 rounded-full mb-3 cursor-pointer group/progress"
      onClick={handleProgressBarClick}
    >
      {/* Buffered bar (gray, behind played bar) */}
      <div
        className="absolute h-1 bg-gray-400 rounded-full transition-all duration-200"
        style={{ width: `${bufferedPercentage}%` }}
      ></div>

      {/* Played bar (orange, on top) */}
      <div
        className="absolute h-1 bg-primary rounded-full transition-all duration-100"
        style={{ width: `${progressPercentage}%` }}
      ></div>

      {/* Scrubber handle (appears on hover) */}
      <div
        className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-primary rounded-full opacity-0 group-hover/progress:opacity-100 transition-opacity"
        style={{ left: `${progressPercentage}%`, transform: 'translate(-50%, -50%)' }}
      ></div>
    </div>
  );
};

export default VideoPlayerProgress;
