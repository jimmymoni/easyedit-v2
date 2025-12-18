/**
 * VideoPlayer Module Exports
 *
 * Main entry point for the video player component and its sub-components.
 *
 * Usage:
 * ```tsx
 * // Import main component
 * import VideoPlayer from '@/components/video/player';
 *
 * // Or import specific sub-components
 * import { VideoPlayerControls, VideoPlayerProgress } from '@/components/video/player';
 * ```
 */

// Main component (default export)
export { default } from './VideoPlayer';

// Sub-components (named exports)
export { default as VideoPlayerControls } from './VideoPlayerControls';
export { default as VideoPlayerProgress } from './VideoPlayerProgress';
export { default as VideoPlayerOverlay } from './VideoPlayerOverlay';

// Types (for external use)
export type {
  VideoPlayerProps,
  VideoPlayerState,
  VideoPlayerControlsProps,
  VideoPlayerProgressProps,
  VideoPlayerOverlayProps,
  ProxyStatus,
} from './VideoPlayer.types';
