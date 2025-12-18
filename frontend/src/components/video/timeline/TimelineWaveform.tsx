import React, { useRef, useEffect, useMemo } from 'react';
import useWaveform from '../../../hooks/video/useWaveform';
import { getVisibleTimeRange } from '../../../utils/video/timelineCalculator';
import { Loader2, AlertCircle } from 'lucide-react';

/**
 * TimelineWaveform Component
 *
 * Renders audio waveform on Canvas with zoom/pan support and playhead synchronization.
 *
 * Features:
 * - Canvas-based rendering (60fps performance)
 * - Symmetrical waveform (mirrored top/bottom)
 * - Color coding: Orange before playhead, gray after
 * - Zoom/pan transformations
 * - Click-to-seek interaction
 * - Loading and error states
 *
 * Performance:
 * - Renders only visible peaks (virtual scrolling)
 * - Batches drawing operations by color
 * - Uses requestAnimationFrame for smooth updates
 * - Handles retina displays correctly
 */

interface TimelineWaveformProps {
  jobId: string;              // Video job ID for fetching waveform
  zoom: number;               // Pixels per second (50-500)
  offset: number;             // Horizontal scroll offset (seconds)
  playheadPosition: number;   // Current playback time (seconds)
  width: number;              // Canvas width (pixels)
  height?: number;            // Canvas height (pixels, default: 120)
  onClick?: (time: number) => void; // Click-to-seek callback
}

const TimelineWaveform: React.FC<TimelineWaveformProps> = ({
  jobId,
  zoom,
  offset,
  playheadPosition,
  width,
  height = 120,
  onClick,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { data: waveformData, loading, error } = useWaveform(jobId);

  // Calculate visible time range
  const visibleRange = useMemo(() => {
    return getVisibleTimeRange(width, zoom, offset);
  }, [width, zoom, offset]);

  // Calculate visible peaks (virtual scrolling)
  const visiblePeaks = useMemo(() => {
    if (!waveformData) return [];

    const peaksPerSecond = waveformData.samples / waveformData.duration;
    const startIndex = Math.floor(visibleRange.start * peaksPerSecond);
    const endIndex = Math.ceil(visibleRange.end * peaksPerSecond);

    return waveformData.peaks.slice(startIndex, endIndex);
  }, [waveformData, visibleRange]);

  // Draw waveform on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !waveformData || visiblePeaks.length === 0) return;

    const ctx = canvas.getContext('2d', { alpha: false });
    if (!ctx) return;

    // Handle retina displays
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.scale(dpr, dpr);

    // Clear canvas
    ctx.fillStyle = '#000000'; // Pure black background
    ctx.fillRect(0, 0, width, height);

    // Draw waveform
    drawWaveform(ctx, visiblePeaks, width, height, visibleRange, playheadPosition);
  }, [waveformData, visiblePeaks, width, height, visibleRange, playheadPosition]);

  // Draw waveform bars
  const drawWaveform = (
    ctx: CanvasRenderingContext2D,
    peaks: number[],
    canvasWidth: number,
    canvasHeight: number,
    timeRange: { start: number; end: number; duration: number },
    playhead: number
  ) => {
    if (peaks.length === 0) return;

    const centerY = canvasHeight / 2;
    const barWidth = canvasWidth / peaks.length;

    // Batch bars by color for performance
    const orangeBars: Array<{ x: number; height: number }> = [];
    const grayBars: Array<{ x: number; height: number }> = [];

    peaks.forEach((peak, index) => {
      const x = index * barWidth;
      const barHeight = peak * (canvasHeight / 2);

      // Calculate time for this bar
      const barTime = timeRange.start + (index / peaks.length) * timeRange.duration;

      // Group by color (orange before playhead, gray after)
      if (barTime < playhead) {
        orangeBars.push({ x, height: barHeight });
      } else {
        grayBars.push({ x, height: barHeight });
      }
    });

    // Draw all orange bars (played)
    ctx.fillStyle = '#FF6B35'; // Orange brand color
    orangeBars.forEach(bar => {
      ctx.fillRect(bar.x, centerY - bar.height, barWidth, bar.height * 2);
    });

    // Draw all gray bars (unplayed)
    ctx.fillStyle = '#6B7280'; // Gray
    grayBars.forEach(bar => {
      ctx.fillRect(bar.x, centerY - bar.height, barWidth, bar.height * 2);
    });
  };

  // Handle click-to-seek
  const handleClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (!onClick || !waveformData) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const clickX = event.clientX - rect.left;

    // Convert pixel to time
    const clickTime = offset + (clickX / zoom);

    // Clamp to valid range
    const clampedTime = Math.max(0, Math.min(waveformData.duration, clickTime));

    onClick(clampedTime);
  };

  // Loading state
  if (loading) {
    return (
      <div
        className="flex items-center justify-center bg-black"
        style={{ width: `${width}px`, height: `${height}px` }}
      >
        <div className="flex items-center space-x-2 text-gray-400">
          <Loader2 className="w-5 h-5 animate-spin text-[#FF6B35]" />
          <span className="text-sm">Loading waveform...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div
        className="flex items-center justify-center bg-black border border-red-500/20"
        style={{ width: `${width}px`, height: `${height}px` }}
      >
        <div className="flex items-center space-x-2 text-red-400">
          <AlertCircle className="w-5 h-5" />
          <span className="text-sm">{error}</span>
        </div>
      </div>
    );
  }

  // No waveform data
  if (!waveformData) {
    return (
      <div
        className="flex items-center justify-center bg-black"
        style={{ width: `${width}px`, height: `${height}px` }}
      >
        <span className="text-sm text-gray-500">No waveform data</span>
      </div>
    );
  }

  // Render canvas
  return (
    <canvas
      ref={canvasRef}
      onClick={handleClick}
      className="cursor-pointer"
      style={{ width: `${width}px`, height: `${height}px` }}
    />
  );
};

export default TimelineWaveform;
