/**
 * Timeline Calculator Utilities
 *
 * Pure functions for timeline calculations:
 * - Pixel ↔ time conversions
 * - Zoom calculations
 * - Pan calculations
 * - Visible range calculations
 *
 * All functions are pure (no side effects) and can be easily tested.
 */

/**
 * Convert pixel position to time (seconds)
 *
 * @param pixelX - Pixel position on timeline (relative to left edge)
 * @param zoom - Pixels per second
 * @param offset - Timeline scroll offset (seconds)
 * @returns Time in seconds
 *
 * @example
 * pixelToTime(100, 50, 0) // 2 seconds (100px ÷ 50px/s + 0s offset)
 * pixelToTime(100, 50, 10) // 12 seconds (100px ÷ 50px/s + 10s offset)
 */
export const pixelToTime = (pixelX: number, zoom: number, offset: number): number => {
  return (pixelX / zoom) + offset;
};

/**
 * Convert time (seconds) to pixel position
 *
 * @param time - Time in seconds
 * @param zoom - Pixels per second
 * @param offset - Timeline scroll offset (seconds)
 * @returns Pixel position relative to timeline left edge
 *
 * @example
 * timeToPixel(5, 50, 0) // 250px (5s × 50px/s - 0s offset)
 * timeToPixel(15, 50, 10) // 250px (15s × 50px/s - 10s × 50px/s)
 */
export const timeToPixel = (time: number, zoom: number, offset: number): number => {
  return (time - offset) * zoom;
};

/**
 * Calculate visible time range for current viewport
 *
 * @param width - Viewport width in pixels
 * @param zoom - Pixels per second
 * @param offset - Timeline scroll offset (seconds)
 * @returns Object with start, end, and duration in seconds
 *
 * @example
 * getVisibleTimeRange(1000, 50, 0)
 * // { start: 0, end: 20, duration: 20 } (1000px ÷ 50px/s = 20 seconds)
 */
export const getVisibleTimeRange = (
  width: number,
  zoom: number,
  offset: number
): { start: number; end: number; duration: number } => {
  const start = offset;
  const duration = width / zoom;
  const end = start + duration;

  return { start, end, duration };
};

/**
 * Calculate zoom level to fit entire timeline in viewport
 *
 * @param duration - Total timeline duration (seconds)
 * @param width - Viewport width in pixels
 * @param minZoom - Minimum allowed zoom level
 * @param maxZoom - Maximum allowed zoom level
 * @returns Zoom level (pixels per second)
 *
 * @example
 * calculateFitZoom(300, 1000, 20, 500)
 * // 3.33 px/s (1000px ÷ 300s, clamped to [20, 500])
 */
export const calculateFitZoom = (
  duration: number,
  width: number,
  minZoom: number,
  maxZoom: number
): number => {
  if (duration === 0 || width === 0) return minZoom;

  const fitZoom = width / duration;
  return clamp(fitZoom, minZoom, maxZoom);
};

/**
 * Calculate new zoom level with multiplicative factor
 *
 * @param currentZoom - Current zoom level (pixels per second)
 * @param factor - Multiplicative factor (>1 = zoom in, <1 = zoom out)
 * @param minZoom - Minimum allowed zoom level
 * @param maxZoom - Maximum allowed zoom level
 * @returns New zoom level
 *
 * @example
 * calculateZoom(100, 1.2, 20, 500) // 120 px/s (zoom in)
 * calculateZoom(100, 0.8, 20, 500) // 80 px/s (zoom out)
 */
export const calculateZoom = (
  currentZoom: number,
  factor: number,
  minZoom: number,
  maxZoom: number
): number => {
  const newZoom = currentZoom * factor;
  return clamp(newZoom, minZoom, maxZoom);
};

/**
 * Calculate new offset when zooming to maintain cursor position
 *
 * This ensures that the time at the cursor position remains fixed
 * when zooming in/out.
 *
 * @param cursorPixelX - Cursor X position in pixels
 * @param currentZoom - Current zoom level
 * @param newZoom - New zoom level after zoom operation
 * @param currentOffset - Current timeline offset
 * @returns New offset to maintain cursor position
 *
 * @example
 * // Cursor at 500px, zoom from 50 to 100 px/s, offset 0
 * calculateZoomOffset(500, 50, 100, 0)
 * // Returns 5 (cursor stays at 10 seconds)
 */
export const calculateZoomOffset = (
  cursorPixelX: number,
  currentZoom: number,
  newZoom: number,
  currentOffset: number
): number => {
  // Calculate time at cursor position (before zoom)
  const cursorTime = pixelToTime(cursorPixelX, currentZoom, currentOffset);

  // Calculate new offset to keep cursor at same time
  const newOffset = cursorTime - (cursorPixelX / newZoom);

  return newOffset;
};

/**
 * Calculate valid offset range for panning
 *
 * @param duration - Total timeline duration (seconds)
 * @param width - Viewport width in pixels
 * @param zoom - Pixels per second
 * @returns Object with min and max valid offsets
 *
 * @example
 * getOffsetRange(300, 1000, 50)
 * // { min: 0, max: 280 } (can scroll from 0s to 280s)
 */
export const getOffsetRange = (
  duration: number,
  width: number,
  zoom: number
): { min: number; max: number } => {
  const viewportDuration = width / zoom;

  return {
    min: 0,
    max: Math.max(0, duration - viewportDuration),
  };
};

/**
 * Clamp offset to valid range
 *
 * @param offset - Offset to clamp (seconds)
 * @param duration - Total timeline duration (seconds)
 * @param width - Viewport width in pixels
 * @param zoom - Pixels per second
 * @returns Clamped offset
 */
export const clampOffset = (
  offset: number,
  duration: number,
  width: number,
  zoom: number
): number => {
  const range = getOffsetRange(duration, width, zoom);
  return clamp(offset, range.min, range.max);
};

/**
 * Calculate auto-scroll offset to keep playhead visible
 *
 * When playhead reaches threshold (e.g., 80%) of visible area,
 * this calculates a new offset to keep playhead in comfortable view.
 *
 * @param playheadTime - Current playhead time (seconds)
 * @param currentOffset - Current timeline offset (seconds)
 * @param width - Viewport width in pixels
 * @param zoom - Pixels per second
 * @param threshold - Percentage of viewport before scrolling (0-1)
 * @returns New offset if scrolling needed, or null if no scroll needed
 *
 * @example
 * calculateAutoScrollOffset(18, 0, 1000, 50, 0.8)
 * // Returns 2 (playhead at 18s, viewport shows 0-20s, 80% = 16s, scroll to keep at 20%)
 */
export const calculateAutoScrollOffset = (
  playheadTime: number,
  currentOffset: number,
  width: number,
  zoom: number,
  threshold: number = 0.8
): number | null => {
  const visibleDuration = width / zoom;
  const visibleEnd = currentOffset + visibleDuration;

  // If playhead is past threshold, scroll
  if (playheadTime > currentOffset + (visibleDuration * threshold)) {
    // Position playhead at 20% of viewport (after scrolling)
    return playheadTime - (visibleDuration * 0.2);
  }

  // If playhead is before visible area, scroll to it
  if (playheadTime < currentOffset) {
    return playheadTime;
  }

  // No scroll needed
  return null;
};

/**
 * Format time in seconds to MM:SS or HH:MM:SS format
 *
 * @param seconds - Time in seconds
 * @param forceHours - Force HH:MM:SS format even for short durations
 * @returns Formatted time string
 *
 * @example
 * formatTime(65) // "1:05"
 * formatTime(3665) // "1:01:05"
 * formatTime(65, true) // "0:01:05"
 */
export const formatTime = (seconds: number, forceHours: boolean = false): string => {
  if (!isFinite(seconds) || seconds < 0) {
    return '0:00';
  }

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0 || forceHours) {
    return `${hours}:${pad(minutes)}:${pad(secs)}`;
  } else {
    return `${minutes}:${pad(secs)}`;
  }
};

/**
 * Clamp value to range [min, max]
 *
 * @param value - Value to clamp
 * @param min - Minimum value
 * @param max - Maximum value
 * @returns Clamped value
 */
export const clamp = (value: number, min: number, max: number): number => {
  return Math.max(min, Math.min(max, value));
};

/**
 * Pad number with leading zero if < 10
 *
 * @param num - Number to pad
 * @returns Padded string
 */
const pad = (num: number): string => {
  return num.toString().padStart(2, '0');
};

/**
 * Calculate easing function for smooth animations
 *
 * @param t - Progress value [0, 1]
 * @returns Eased value [0, 1]
 */
export const easeInOutQuad = (t: number): number => {
  return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
};
