import React from 'react';
import { Loader2, AlertCircle, Play } from 'lucide-react';
import { VideoPlayerOverlayProps } from './VideoPlayer.types';

/**
 * VideoPlayerOverlay Component
 *
 * Handles all overlay states for the video player:
 * - Checking: Initial proxy status check
 * - Transcoding: Proxy generation in progress with progress bar
 * - Failed: Error state with message
 * - Not Found: Invalid job ID
 * - Center Play Button: Shows when video is paused
 */
const VideoPlayerOverlay: React.FC<VideoPlayerOverlayProps> = ({
  proxyStatus,
  proxyProgress,
  proxyError,
  isPlaying,
  onTogglePlay,
}) => {
  // Checking state - Initial load
  if (proxyStatus === 'checking') {
    return (
      <div className="absolute inset-0 flex items-center justify-center bg-black">
        <div className="text-center">
          <Loader2 className="h-12 w-12 text-primary animate-spin mx-auto mb-4" />
          <p className="text-white text-sm">Checking video status...</p>
        </div>
      </div>
    );
  }

  // Transcoding state - Proxy generation in progress
  if (proxyStatus === 'transcoding') {
    return (
      <div className="absolute inset-0 flex items-center justify-center bg-black">
        <div className="text-center max-w-md px-6">
          <Loader2 className="h-12 w-12 text-primary animate-spin mx-auto mb-4" />
          <p className="text-white text-lg font-semibold mb-2">Optimizing Video for Web</p>
          <p className="text-gray-400 text-sm mb-4">
            Creating a web-optimized proxy for smooth playback...
          </p>
          <div className="w-full bg-gray-700 rounded-full h-2 mb-2">
            <div
              className="bg-primary h-2 rounded-full transition-all duration-300"
              style={{ width: `${proxyProgress}%` }}
            ></div>
          </div>
          <p className="text-gray-400 text-xs">{proxyProgress.toFixed(0)}% complete</p>
        </div>
      </div>
    );
  }

  // Error states - Failed or Not Found
  if (proxyStatus === 'failed' || proxyStatus === 'not_found') {
    return (
      <div className="absolute inset-0 flex items-center justify-center bg-black border border-red-500/50">
        <div className="text-center max-w-md px-6">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <p className="text-white text-lg font-semibold mb-2">Video Not Available</p>
          <p className="text-gray-400 text-sm">{proxyError || 'Failed to load video.'}</p>
        </div>
      </div>
    );
  }

  // Center play button - Shows when paused (ready state only)
  if (proxyStatus === 'ready' && !isPlaying) {
    return (
      <div
        className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
        onClick={onTogglePlay}
      >
        <div className="bg-primary/90 rounded-full p-6 hover:bg-primary transition-colors">
          <Play className="h-12 w-12 text-white" />
        </div>
      </div>
    );
  }

  // No overlay (video is playing)
  return null;
};

export default VideoPlayerOverlay;
