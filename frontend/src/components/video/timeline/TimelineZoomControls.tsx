import React, { useEffect } from 'react';
import { ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';
import { formatTime } from '../../../utils/video/timelineCalculator';

/**
 * TimelineZoomControls Component
 *
 * UI controls for timeline zoom operations.
 *
 * Features:
 * - Zoom in button
 * - Zoom out button
 * - Zoom to fit button
 * - Current zoom level display
 * - Playhead time display
 * - Keyboard shortcuts (Ctrl + Plus/Minus/0)
 */

interface TimelineZoomControlsProps {
  zoom: number;               // Current zoom level (px/s)
  currentTime: number;        // Current playback time (seconds)
  duration: number;           // Total duration (seconds)
  onZoomIn: () => void;       // Increase zoom
  onZoomOut: () => void;      // Decrease zoom
  onZoomFit: () => void;      // Fit entire timeline in viewport
}

const TimelineZoomControls: React.FC<TimelineZoomControlsProps> = ({
  zoom,
  currentTime,
  duration,
  onZoomIn,
  onZoomOut,
  onZoomFit,
}) => {
  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Only handle if Ctrl/Cmd is pressed
      if (!e.ctrlKey && !e.metaKey) return;

      // Don't handle in input fields
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;

      switch (e.key) {
        case '+':
        case '=':
          e.preventDefault();
          onZoomIn();
          break;

        case '-':
        case '_':
          e.preventDefault();
          onZoomOut();
          break;

        case '0':
          e.preventDefault();
          onZoomFit();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onZoomIn, onZoomOut, onZoomFit]);

  return (
    <div className="flex items-center justify-between px-4 py-2 bg-[#181818] border-b border-gray-800">
      {/* Left: Zoom controls */}
      <div className="flex items-center space-x-2">
        {/* Zoom out button */}
        <button
          onClick={onZoomOut}
          className="p-2 rounded hover:bg-[#FF6B35] hover:text-white transition-colors text-gray-400"
          title="Zoom out (Ctrl + -)"
        >
          <ZoomOut className="w-4 h-4" />
        </button>

        {/* Zoom in button */}
        <button
          onClick={onZoomIn}
          className="p-2 rounded hover:bg-[#FF6B35] hover:text-white transition-colors text-gray-400"
          title="Zoom in (Ctrl + +)"
        >
          <ZoomIn className="w-4 h-4" />
        </button>

        {/* Zoom to fit button */}
        <button
          onClick={onZoomFit}
          className="p-2 rounded hover:bg-[#FF6B35] hover:text-white transition-colors text-gray-400"
          title="Zoom to fit (Ctrl + 0)"
        >
          <Maximize2 className="w-4 h-4" />
        </button>

        {/* Zoom level display */}
        <div className="ml-2 px-2 py-1 bg-black rounded text-xs text-gray-300 font-mono">
          {Math.round(zoom)} px/s
        </div>
      </div>

      {/* Right: Playhead time */}
      <div className="flex items-center space-x-2 text-gray-300">
        <span className="text-sm font-mono">
          {formatTime(currentTime)} / {formatTime(duration)}
        </span>
      </div>
    </div>
  );
};

export default TimelineZoomControls;
