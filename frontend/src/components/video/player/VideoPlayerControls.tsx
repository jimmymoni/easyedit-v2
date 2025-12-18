import React from 'react';
import { Play, Pause, Volume2, VolumeX, Maximize } from 'lucide-react';
import { VideoPlayerControlsProps } from './VideoPlayer.types';

/**
 * VideoPlayerControls Component
 *
 * Control buttons for the video player:
 * - Play/Pause toggle
 * - Time display (current / duration)
 * - Volume mute toggle
 * - Fullscreen toggle
 */
const VideoPlayerControls: React.FC<VideoPlayerControlsProps> = ({
  playerState,
  onTogglePlay,
  onToggleMute,
  onVolumeChange,
  onToggleFullscreen,
}) => {
  // Format time as MM:SS or H:MM:SS for longer videos
  const formatTime = (seconds: number): string => {
    if (!isFinite(seconds)) return '0:00';

    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
      return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="flex items-center justify-between text-white">
      {/* Left group: Play/Pause + Time display */}
      <div className="flex items-center space-x-3">
        {/* Play/Pause button */}
        <button
          onClick={onTogglePlay}
          className="hover:text-primary transition-colors"
          aria-label={playerState.isPlaying ? 'Pause' : 'Play'}
        >
          {playerState.isPlaying ? (
            <Pause className="h-6 w-6" />
          ) : (
            <Play className="h-6 w-6" />
          )}
        </button>

        {/* Time display */}
        <span className="text-sm font-medium">
          {formatTime(playerState.currentTime)} / {formatTime(playerState.duration)}
        </span>
      </div>

      {/* Right group: Volume + Fullscreen */}
      <div className="flex items-center space-x-3">
        {/* Volume mute toggle */}
        <button
          onClick={onToggleMute}
          className="hover:text-primary transition-colors"
          aria-label={playerState.isMuted ? 'Unmute' : 'Mute'}
        >
          {playerState.isMuted || playerState.volume === 0 ? (
            <VolumeX className="h-5 w-5" />
          ) : (
            <Volume2 className="h-5 w-5" />
          )}
        </button>

        {/* Fullscreen button */}
        <button
          onClick={onToggleFullscreen}
          className="hover:text-primary transition-colors"
          aria-label="Fullscreen"
        >
          <Maximize className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
};

export default VideoPlayerControls;
