import { useState, useCallback, useEffect, useRef } from 'react';
import { TimelineState } from '../../types';
import {
  calculateZoom,
  calculateFitZoom,
  calculateZoomOffset,
  clampOffset,
  calculateAutoScrollOffset,
} from '../../utils/video/timelineCalculator';

/**
 * useTimeline Hook
 *
 * Manages timeline state including zoom, pan, and auto-scroll logic.
 *
 * Features:
 * - Zoom in/out/fit operations
 * - Pan (horizontal scroll)
 * - Auto-scroll during playback
 * - Zoom to cursor position
 * - State validation and clamping
 *
 * @param duration - Total video duration (seconds)
 * @param currentTime - Current playback time (seconds)
 * @param viewportWidth - Timeline viewport width (pixels)
 * @returns Timeline state and control functions
 *
 * @example
 * ```tsx
 * const timeline = useTimeline(300, currentTime, 1000);
 *
 * <TimelineZoomControls
 *   zoom={timeline.zoom}
 *   onZoomIn={timeline.zoomIn}
 *   onZoomOut={timeline.zoomOut}
 *   onZoomFit={timeline.zoomFit}
 * />
 * ```
 */

interface UseTimelineOptions {
  initialZoom?: number;     // Initial zoom level (default: 100 px/s)
  minZoom?: number;          // Minimum zoom level (default: 20 px/s)
  maxZoom?: number;          // Maximum zoom level (default: 500 px/s)
  zoomFactor?: number;       // Zoom in/out multiplier (default: 1.2)
  autoScroll?: boolean;      // Enable auto-scroll (default: true)
  autoScrollThreshold?: number; // Auto-scroll trigger (default: 0.8 = 80%)
}

interface UseTimelineReturn extends TimelineState {
  zoomIn: (cursorX?: number) => void;
  zoomOut: (cursorX?: number) => void;
  zoomFit: () => void;
  setZoom: (zoom: number, cursorX?: number) => void;
  pan: (deltaSeconds: number) => void;
  setOffset: (offset: number) => void;
}

const useTimeline = (
  duration: number,
  currentTime: number,
  viewportWidth: number,
  options: UseTimelineOptions = {}
): UseTimelineReturn => {
  const {
    initialZoom = 100,
    minZoom = 20,
    maxZoom = 500,
    zoomFactor = 1.2,
    autoScroll = true,
    autoScrollThreshold = 0.8,
  } = options;

  // Timeline state
  const [zoom, setZoomState] = useState<number>(initialZoom);
  const [offset, setOffsetState] = useState<number>(0);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [isScrolling, setIsScrolling] = useState<boolean>(false);

  // Track previous current time for auto-scroll
  const prevCurrentTimeRef = useRef<number>(currentTime);

  // Zoom in (multiply by zoomFactor)
  const zoomIn = useCallback((cursorX?: number) => {
    setZoomState(prevZoom => {
      const newZoom = calculateZoom(prevZoom, zoomFactor, minZoom, maxZoom);

      // If cursor position provided, zoom to cursor
      if (cursorX !== undefined) {
        const newOffset = calculateZoomOffset(cursorX, prevZoom, newZoom, offset);
        setOffsetState(clampOffset(newOffset, duration, viewportWidth, newZoom));
      }

      return newZoom;
    });
  }, [zoomFactor, minZoom, maxZoom, offset, duration, viewportWidth]);

  // Zoom out (divide by zoomFactor)
  const zoomOut = useCallback((cursorX?: number) => {
    setZoomState(prevZoom => {
      const newZoom = calculateZoom(prevZoom, 1 / zoomFactor, minZoom, maxZoom);

      // If cursor position provided, zoom to cursor
      if (cursorX !== undefined) {
        const newOffset = calculateZoomOffset(cursorX, prevZoom, newZoom, offset);
        setOffsetState(clampOffset(newOffset, duration, viewportWidth, newZoom));
      }

      return newZoom;
    });
  }, [zoomFactor, minZoom, maxZoom, offset, duration, viewportWidth]);

  // Zoom to fit entire timeline in viewport
  const zoomFit = useCallback(() => {
    const fitZoom = calculateFitZoom(duration, viewportWidth, minZoom, maxZoom);
    setZoomState(fitZoom);
    setOffsetState(0); // Reset to start
  }, [duration, viewportWidth, minZoom, maxZoom]);

  // Set custom zoom level
  const setZoom = useCallback((newZoom: number, cursorX?: number) => {
    setZoomState(prevZoom => {
      const clampedZoom = Math.max(minZoom, Math.min(maxZoom, newZoom));

      // If cursor position provided, zoom to cursor
      if (cursorX !== undefined) {
        const newOffset = calculateZoomOffset(cursorX, prevZoom, clampedZoom, offset);
        setOffsetState(clampOffset(newOffset, duration, viewportWidth, clampedZoom));
      }

      return clampedZoom;
    });
  }, [minZoom, maxZoom, offset, duration, viewportWidth]);

  // Pan timeline (horizontal scroll)
  const pan = useCallback((deltaSeconds: number) => {
    setOffsetState(prevOffset => {
      const newOffset = prevOffset + deltaSeconds;
      return clampOffset(newOffset, duration, viewportWidth, zoom);
    });
  }, [duration, viewportWidth, zoom]);

  // Set custom offset
  const setOffset = useCallback((newOffset: number) => {
    setOffsetState(clampOffset(newOffset, duration, viewportWidth, zoom));
  }, [duration, viewportWidth, zoom]);

  // Auto-scroll timeline during playback
  useEffect(() => {
    if (!autoScroll) return;

    // Only auto-scroll if time is moving forward (playing)
    if (currentTime <= prevCurrentTimeRef.current) {
      prevCurrentTimeRef.current = currentTime;
      return;
    }

    prevCurrentTimeRef.current = currentTime;

    const newOffset = calculateAutoScrollOffset(
      currentTime,
      offset,
      viewportWidth,
      zoom,
      autoScrollThreshold
    );

    if (newOffset !== null) {
      setOffsetState(clampOffset(newOffset, duration, viewportWidth, zoom));
    }
  }, [currentTime, offset, viewportWidth, zoom, autoScroll, autoScrollThreshold, duration]);

  // Return timeline state and controls
  return {
    // State
    zoom,
    offset,
    minZoom,
    maxZoom,
    gridSize: 1, // 1 second grid (can be made configurable)
    snapToGrid: false, // Disabled for now (can be enabled later)
    playheadPosition: currentTime,
    duration,
    isDragging,
    isScrolling,

    // Controls
    zoomIn,
    zoomOut,
    zoomFit,
    setZoom,
    pan,
    setOffset,
  };
};

export default useTimeline;
