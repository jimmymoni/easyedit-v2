import React, { useState, useEffect, useRef } from 'react';
import { timeToPixel, pixelToTime, clamp, formatTime } from '../../../utils/video/timelineCalculator';

/**
 * TimelinePlayhead Component
 *
 * Vertical line indicator showing current playback position with drag-to-seek.
 *
 * Features:
 * - Renders vertical orange line at current time
 * - Draggable to seek video
 * - Time tooltip during drag
 * - Hover state with cursor change
 * - Clamped to valid time range [0, duration]
 */

interface TimelinePlayheadProps {
  position: number;           // Current time (seconds)
  zoom: number;               // Pixels per second
  offset: number;             // Timeline scroll offset (seconds)
  duration: number;           // Total duration (seconds)
  height: number;             // Playhead height (matches timeline height)
  onDrag: (time: number) => void; // Drag callback (update video time)
  isDraggable?: boolean;      // Enable drag-to-seek (default: true)
}

const TimelinePlayhead: React.FC<TimelinePlayheadProps> = ({
  position,
  zoom,
  offset,
  duration,
  height,
  onDrag,
  isDraggable = true,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [dragTime, setDragTime] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Calculate pixel position from time
  const pixelX = timeToPixel(position, zoom, offset);

  // Handle mouse down on playhead
  const handleMouseDown = (e: React.MouseEvent) => {
    if (!isDraggable) return;

    setIsDragging(true);
    setDragTime(position);
    e.preventDefault();
    e.stopPropagation();
  };

  // Handle mouse move (dragging)
  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const container = containerRef.current;
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;

      // Convert pixel to time
      const newTime = pixelToTime(mouseX, zoom, offset);

      // Clamp to valid range
      const clampedTime = clamp(newTime, 0, duration);

      setDragTime(clampedTime);
    };

    const handleMouseUp = () => {
      if (dragTime !== null) {
        onDrag(dragTime);
      }
      setIsDragging(false);
      setDragTime(null);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, dragTime, zoom, offset, duration, onDrag]);

  // Display time (current or dragging)
  const displayTime = dragTime !== null ? dragTime : position;
  const displayPixelX = dragTime !== null ? timeToPixel(dragTime, zoom, offset) : pixelX;

  // Check if playhead is visible in viewport
  const isVisible = displayPixelX >= 0 && displayPixelX <= containerRef.current?.offsetWidth || 0;

  if (!isVisible && !isDragging) {
    return null; // Don't render if not visible
  }

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 pointer-events-none"
      style={{ height: `${height}px` }}
    >
      {/* Playhead line */}
      <div
        className={`absolute top-0 bottom-0 w-0.5 bg-[#FF6B35] pointer-events-auto ${
          isDraggable ? 'cursor-ew-resize' : ''
        }`}
        style={{
          left: `${displayPixelX}px`,
          transform: 'translateX(-50%)',
        }}
        onMouseDown={handleMouseDown}
      >
        {/* Top handle (circle) */}
        <div
          className={`absolute -top-1 left-1/2 -translate-x-1/2 w-3 h-3 bg-[#FF6B35] rounded-full border-2 border-black ${
            isDragging ? 'scale-125' : ''
          } transition-transform`}
        />
      </div>

      {/* Time tooltip (during drag) */}
      {isDragging && dragTime !== null && (
        <div
          className="absolute -top-8 bg-black text-white px-2 py-1 rounded text-xs font-mono whitespace-nowrap pointer-events-none border border-[#FF6B35]"
          style={{
            left: `${displayPixelX}px`,
            transform: 'translateX(-50%)',
          }}
        >
          {formatTime(dragTime)}
        </div>
      )}
    </div>
  );
};

export default TimelinePlayhead;
