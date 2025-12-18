/**
 * Type definitions for VideoPlayer component
 * Modular types specific to the player module
 */

export interface VideoPlayerState {
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  isMuted: boolean;
  playbackRate: number;
  isFullscreen: boolean;
  buffered: number;
}

export type ProxyStatus = 'checking' | 'ready' | 'transcoding' | 'failed' | 'not_found';

export interface VideoPlayerProps {
  jobId: string;
  onTimeUpdate?: (currentTime: number) => void;
  onDurationChange?: (duration: number) => void;
  className?: string;
}

export interface VideoPlayerControlsProps {
  playerState: VideoPlayerState;
  onTogglePlay: () => void;
  onToggleMute: () => void;
  onVolumeChange: (delta: number) => void;
  onToggleFullscreen: () => void;
}

export interface VideoPlayerProgressProps {
  currentTime: number;
  duration: number;
  buffered: number;
  onSeek: (time: number) => void;
}

export interface VideoPlayerOverlayProps {
  proxyStatus: ProxyStatus;
  proxyProgress: number;
  proxyError: string | null;
  isPlaying: boolean;
  onTogglePlay: () => void;
}
