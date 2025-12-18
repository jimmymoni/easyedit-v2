import React, { useRef, useEffect } from 'react';
import useTimeline from '../../../hooks/video/useTimeline';
import TimelineWaveform from './TimelineWaveform';
import TimelinePlayhead from './TimelinePlayhead';
import TimelineRuler from './TimelineRuler';
import TimelineZoomControls from './TimelineZoomControls';

/**
 * TimelineContainer Component
 *
 * Main timeline orchestrator that coordinates all timeline components.
 *
 * Features:
 * - Manages timeline state (zoom, pan, playhead)
 * - Coordinates all child components
 * - Handles mouse wheel zoom (Ctrl + Scroll)
 * - Handles click-to-seek delegation
 * - Auto-scrolls during playback
 *
 * Architecture:
 * - TimelineZoomControls (header)
 * - TimelineRuler (time markers)
 * - TimelineWaveform (canvas waveform)
 * - TimelinePlayhead (draggable indicator)
 */

interface TimelineContainerProps {
  jobId: string;              // Video job ID
  duration: number;           // Total video duration (seconds)
  currentTime: number;        // Current playback time (seconds)
  onSeek: (time: number) => void; // Seek callback (passes to VideoPlayer)
  height?: number;            // Timeline waveform height (default: 120px)
}

const TimelineContainer: React.FC<TimelineContainerProps> = ({
  jobId,
  duration,
  currentTime,
  onSeek,
  height = 120,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [viewportWidth, setViewportWidth] = React.useState(0);

  // Initialize timeline state
  const timeline = useTimeline(duration, currentTime, viewportWidth, {
    initialZoom: 100,
    minZoom: 20,
    maxZoom: 500,
    autoScroll: true,
    autoScrollThreshold: 0.8,
  });

  // Update viewport width on mount and resize
  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        setViewportWidth(containerRef.current.offsetWidth);
      }
    };

    updateWidth();
    window.addEventListener('resize', updateWidth);
    return () => window.removeEventListener('resize', updateWidth);
  }, []);

  // Handle mouse wheel zoom (Ctrl + Scroll)
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleWheel = (e: WheelEvent) => {
      // Only zoom if Ctrl/Cmd key is held
      if (!e.ctrlKey && !e.metaKey) return;

      e.preventDefault();

      // Calculate zoom direction
      const zoomOut = e.deltaY > 0;

      // Get cursor position relative to timeline
      const rect = container.getBoundingClientRect();
      const cursorX = e.clientX - rect.left;

      // Zoom to cursor position
      if (zoomOut) {
        timeline.zoomOut(cursorX);
      } else {
        timeline.zoomIn(cursorX);
      }
    };

    container.addEventListener('wheel', handleWheel, { passive: false });
    return () => container.removeEventListener('wheel', handleWheel);
  }, [timeline]);

  // Total height (controls + ruler + waveform)
  const totalHeight = 42 + 30 + height; // 42px controls, 30px ruler, {height}px waveform

  return (
    <div className="bg-black rounded-xl overflow-hidden">
      {/* Zoom controls header */}
      <TimelineZoomControls
        zoom={timeline.zoom}
        currentTime={currentTime}
        duration={duration}
        onZoomIn={() => timeline.zoomIn()}
        onZoomOut={() => timeline.zoomOut()}
        onZoomFit={timeline.zoomFit}
      />

      {/* Timeline viewport */}
      <div
        ref={containerRef}
        className="relative overflow-hidden"
        style={{ height: `${30 + height}px` }}
      >
        {/* Time ruler */}
        <TimelineRuler
          duration={duration}
          zoom={timeline.zoom}
          offset={timeline.offset}
          width={viewportWidth}
          height={30}
        />

        {/* Waveform */}
        <div className="relative">
          <TimelineWaveform
            jobId={jobId}
            zoom={timeline.zoom}
            offset={timeline.offset}
            playheadPosition={currentTime}
            width={viewportWidth}
            height={height}
            onClick={onSeek}
          />

          {/* Playhead (overlays waveform) */}
          <TimelinePlayhead
            position={currentTime}
            zoom={timeline.zoom}
            offset={timeline.offset}
            duration={duration}
            height={height}
            onDrag={onSeek}
            isDraggable={true}
          />
        </div>
      </div>

      {/* Keyboard shortcuts hint */}
      <div className="px-4 py-2 bg-[#181818] text-xs text-gray-400 border-t border-gray-800">
        <div className="flex items-center space-x-4">
          <span>
            <kbd className="bg-black px-1.5 py-0.5 rounded text-gray-300">Ctrl + Scroll</kbd> Zoom
          </span>
          <span>
            <kbd className="bg-black px-1.5 py-0.5 rounded text-gray-300">Ctrl + +/−</kbd> Zoom In/Out
          </span>
          <span>
            <kbd className="bg-black px-1.5 py-0.5 rounded text-gray-300">Ctrl + 0</kbd> Fit
          </span>
          <span>
            <kbd className="bg-black px-1.5 py-0.5 rounded text-gray-300">Click</kbd> Seek
          </span>
          <span>
            <kbd className="bg-black px-1.5 py-0.5 rounded text-gray-300">Drag</kbd> Playhead
          </span>
        </div>
      </div>
    </div>
  );
};

export default TimelineContainer;
