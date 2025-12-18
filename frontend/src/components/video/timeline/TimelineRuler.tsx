import React, { useMemo } from 'react';
import { timeToPixel, formatTime } from '../../../utils/video/timelineCalculator';

/**
 * TimelineRuler Component
 *
 * Displays time markers along the timeline with auto-adjusting density.
 *
 * Features:
 * - Major markers with time labels (0:00, 0:10, 0:20...)
 * - Minor tick marks (every 1s or 5s)
 * - Auto-adjusts marker density based on zoom level
 * - Renders only visible markers
 */

interface TimelineRulerProps {
  duration: number;           // Total duration (seconds)
  zoom: number;               // Pixels per second
  offset: number;             // Horizontal scroll offset (seconds)
  width: number;              // Ruler width (pixels)
  height?: number;            // Ruler height (default: 30px)
}

interface MarkerInterval {
  major: number;  // Major marker interval (seconds)
  minor: number;  // Minor marker interval (seconds)
}

const TimelineRuler: React.FC<TimelineRulerProps> = ({
  duration,
  zoom,
  offset,
  width,
  height = 30,
}) => {
  // Calculate marker intervals based on zoom level
  const intervals = useMemo((): MarkerInterval => {
    if (zoom < 20) {
      return { major: 60, minor: 10 };  // 1 minute major, 10 seconds minor
    } else if (zoom < 50) {
      return { major: 30, minor: 5 };   // 30 seconds major, 5 seconds minor
    } else if (zoom < 100) {
      return { major: 10, minor: 1 };   // 10 seconds major, 1 second minor
    } else {
      return { major: 5, minor: 1 };    // 5 seconds major, 1 second minor
    }
  }, [zoom]);

  // Calculate visible time range
  const visibleStart = offset;
  const visibleEnd = offset + (width / zoom);

  // Generate markers
  const markers = useMemo(() => {
    const result: Array<{ time: number; type: 'major' | 'minor' }> = [];

    // Start from first major marker before visible area
    const firstMajor = Math.floor(visibleStart / intervals.major) * intervals.major;

    // Generate major markers
    for (let time = firstMajor; time <= visibleEnd; time += intervals.major) {
      if (time >= 0 && time <= duration) {
        result.push({ time, type: 'major' });
      }
    }

    // Generate minor markers
    const firstMinor = Math.floor(visibleStart / intervals.minor) * intervals.minor;
    for (let time = firstMinor; time <= visibleEnd; time += intervals.minor) {
      if (time >= 0 && time <= duration) {
        // Don't add minor marker if it coincides with a major marker
        const isMajor = time % intervals.major === 0;
        if (!isMajor) {
          result.push({ time, type: 'minor' });
        }
      }
    }

    return result;
  }, [visibleStart, visibleEnd, duration, intervals]);

  return (
    <div
      className="relative bg-[#181818] border-b border-gray-800"
      style={{ width: `${width}px`, height: `${height}px` }}
    >
      {/* Markers */}
      {markers.map((marker, index) => {
        const pixelX = timeToPixel(marker.time, zoom, offset);
        const isMajor = marker.type === 'major';

        return (
          <div
            key={`${marker.time}-${index}`}
            className="absolute bottom-0 flex flex-col items-center"
            style={{ left: `${pixelX}px`, transform: 'translateX(-50%)' }}
          >
            {/* Tick mark */}
            <div
              className="bg-gray-500"
              style={{
                width: '1px',
                height: isMajor ? '12px' : '6px',
              }}
            />

            {/* Time label (major markers only) */}
            {isMajor && (
              <span className="text-xs text-gray-400 mt-1 font-mono">
                {formatTime(marker.time)}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default TimelineRuler;
