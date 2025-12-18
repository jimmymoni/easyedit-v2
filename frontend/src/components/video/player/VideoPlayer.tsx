import React, { useState, useRef, useEffect } from 'react';
import * as api from '../../../services/api';
import { VideoJob } from '../../../types';
import { VideoPlayerProps, VideoPlayerState, ProxyStatus } from './VideoPlayer.types';
import VideoPlayerOverlay from './VideoPlayerOverlay';
import VideoPlayerProgress from './VideoPlayerProgress';
import VideoPlayerControls from './VideoPlayerControls';

/**
 * VideoPlayer Component
 *
 * Main video player component that orchestrates:
 * - Proxy status checking and polling
 * - Video playback state management
 * - Keyboard shortcuts
 * - Sub-component coordination
 *
 * Usage:
 * ```tsx
 * <VideoPlayer
 *   jobId="video-job-123"
 *   onTimeUpdate={(time) => console.log('Current time:', time)}
 *   onDurationChange={(duration) => console.log('Duration:', duration)}
 * />
 * ```
 */
const VideoPlayer: React.FC<VideoPlayerProps> = ({
  jobId,
  onTimeUpdate,
  onDurationChange,
  className = '',
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Player state
  const [playerState, setPlayerState] = useState<VideoPlayerState>({
    isPlaying: false,
    currentTime: 0,
    duration: 0,
    volume: 1,
    isMuted: false,
    playbackRate: 1,
    isFullscreen: false,
    buffered: 0,
  });

  // Proxy status
  const [proxyStatus, setProxyStatus] = useState<ProxyStatus>('checking');
  const [proxyProgress, setProxyProgress] = useState(0);
  const [proxyError, setProxyError] = useState<string | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);

  // Check proxy status and poll if transcoding
  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    const checkProxyStatus = async () => {
      try {
        const status: VideoJob = await api.getVideoJobStatus(jobId);

        if (status.proxy_status === 'ready') {
          setProxyStatus('ready');
          const url = api.getVideoProxyUrl(jobId);
          setVideoUrl(url);
        } else if (status.proxy_status === 'transcoding') {
          setProxyStatus('transcoding');
          setProxyProgress(status.proxy_progress || 0);
          // Continue polling
          if (!intervalId) {
            intervalId = setInterval(checkProxyStatus, 2000);
          }
        } else if (status.proxy_status === 'failed') {
          setProxyStatus('failed');
          setProxyError('Proxy transcoding failed. Please try re-uploading the video.');
        } else if (status.proxy_status === 'pending') {
          setProxyStatus('transcoding');
          setProxyProgress(0);
          // Start polling
          if (!intervalId) {
            intervalId = setInterval(checkProxyStatus, 2000);
          }
        }
      } catch (error: any) {
        console.error('Error checking proxy status:', error);
        if (error.response?.status === 404) {
          setProxyStatus('not_found');
          setProxyError('Video job not found.');
        } else {
          setProxyStatus('failed');
          setProxyError('Failed to load video. Please try again.');
        }
      }
    };

    checkProxyStatus();

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [jobId]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Only handle if video is ready
      if (!videoRef.current || proxyStatus !== 'ready') return;

      // Don't handle shortcuts in input fields
      const targetElement = e.target as HTMLElement;
      const isInputField = targetElement.tagName === 'INPUT' || targetElement.tagName === 'TEXTAREA';
      if (isInputField) return;

      switch (e.code) {
        case 'Space':
          e.preventDefault();
          togglePlayPause();
          break;
        case 'ArrowLeft':
          e.preventDefault();
          seekRelative(-5);
          break;
        case 'ArrowRight':
          e.preventDefault();
          seekRelative(5);
          break;
        case 'ArrowUp':
          e.preventDefault();
          changeVolume(0.1);
          break;
        case 'ArrowDown':
          e.preventDefault();
          changeVolume(-0.1);
          break;
        case 'KeyM':
          e.preventDefault();
          toggleMute();
          break;
        case 'KeyF':
          e.preventDefault();
          toggleFullscreen();
          break;
        case 'Home':
          e.preventDefault();
          seekTo(0);
          break;
        case 'End':
          e.preventDefault();
          if (isFinite(playerState.duration)) {
            seekTo(playerState.duration);
          }
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [proxyStatus, playerState.volume, playerState.duration]);

  // Video event handlers
  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    const currentTime = videoRef.current.currentTime;
    setPlayerState((prev) => ({ ...prev, currentTime }));
    if (onTimeUpdate) onTimeUpdate(currentTime);
  };

  const handleDurationChange = () => {
    if (!videoRef.current) return;
    const duration = videoRef.current.duration;
    setPlayerState((prev) => ({ ...prev, duration }));
    if (onDurationChange) onDurationChange(duration);
  };

  const handleProgress = () => {
    if (!videoRef.current) return;
    const buffered = videoRef.current.buffered;
    if (buffered.length > 0) {
      const bufferedEnd = buffered.end(buffered.length - 1);
      const duration = videoRef.current.duration;
      if (isFinite(duration) && duration > 0) {
        const bufferedPercent = (bufferedEnd / duration) * 100;
        setPlayerState((prev) => ({ ...prev, buffered: bufferedPercent }));
      }
    }
  };

  const handleEnded = () => {
    setPlayerState((prev) => ({ ...prev, isPlaying: false }));
  };

  // Control functions
  const togglePlayPause = () => {
    if (!videoRef.current) return;
    if (playerState.isPlaying) {
      videoRef.current.pause();
      setPlayerState((prev) => ({ ...prev, isPlaying: false }));
    } else {
      videoRef.current.play();
      setPlayerState((prev) => ({ ...prev, isPlaying: true }));
    }
  };

  const seekTo = (time: number) => {
    if (!videoRef.current) return;
    videoRef.current.currentTime = time;
    setPlayerState((prev) => ({ ...prev, currentTime: time }));
  };

  const seekRelative = (seconds: number) => {
    if (!videoRef.current) return;
    const newTime = Math.max(0, Math.min(playerState.duration, videoRef.current.currentTime + seconds));
    seekTo(newTime);
  };

  const changeVolume = (delta: number) => {
    if (!videoRef.current) return;
    const newVolume = Math.max(0, Math.min(1, playerState.volume + delta));
    videoRef.current.volume = newVolume;
    setPlayerState((prev) => ({ ...prev, volume: newVolume, isMuted: newVolume === 0 }));
  };

  const toggleMute = () => {
    if (!videoRef.current) return;
    const newMuted = !playerState.isMuted;
    videoRef.current.muted = newMuted;
    setPlayerState((prev) => ({ ...prev, isMuted: newMuted }));
  };

  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen();
      setPlayerState((prev) => ({ ...prev, isFullscreen: true }));
    } else {
      document.exitFullscreen();
      setPlayerState((prev) => ({ ...prev, isFullscreen: false }));
    }
  };

  // Render video player or loading/error states
  return (
    <div ref={containerRef} className={`bg-black rounded-xl overflow-hidden ${className}`}>
      {/* Show overlay states (checking, transcoding, error) or video player */}
      {proxyStatus !== 'ready' ? (
        // Full-screen overlay for non-ready states
        <div className="aspect-video relative">
          <VideoPlayerOverlay
            proxyStatus={proxyStatus}
            proxyProgress={proxyProgress}
            proxyError={proxyError}
            isPlaying={playerState.isPlaying}
            onTogglePlay={togglePlayPause}
          />
        </div>
      ) : (
        // Video player (ready state)
        <div className="relative group">
          {/* Video element */}
          <video
            ref={videoRef}
            src={videoUrl || ''}
            className="w-full aspect-video"
            onTimeUpdate={handleTimeUpdate}
            onDurationChange={handleDurationChange}
            onProgress={handleProgress}
            onEnded={handleEnded}
            onClick={togglePlayPause}
          />

          {/* Overlay (center play button when paused) */}
          <VideoPlayerOverlay
            proxyStatus={proxyStatus}
            proxyProgress={proxyProgress}
            proxyError={proxyError}
            isPlaying={playerState.isPlaying}
            onTogglePlay={togglePlayPause}
          />

          {/* Controls overlay */}
          <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 via-black/50 to-transparent p-4 opacity-0 group-hover:opacity-100 transition-opacity">
            {/* Progress bar */}
            <VideoPlayerProgress
              currentTime={playerState.currentTime}
              duration={playerState.duration}
              buffered={playerState.buffered}
              onSeek={seekTo}
            />

            {/* Control buttons */}
            <VideoPlayerControls
              playerState={playerState}
              onTogglePlay={togglePlayPause}
              onToggleMute={toggleMute}
              onVolumeChange={changeVolume}
              onToggleFullscreen={toggleFullscreen}
            />
          </div>
        </div>
      )}

      {/* Keyboard shortcuts hint (always visible) */}
      {proxyStatus === 'ready' && (
        <div className="bg-[#181818] px-4 py-2 text-xs text-gray-400 flex items-center justify-between">
          <div className="flex space-x-4">
            <span><kbd className="bg-black px-1.5 py-0.5 rounded text-gray-300">Space</kbd> Play/Pause</span>
            <span><kbd className="bg-black px-1.5 py-0.5 rounded text-gray-300">←/→</kbd> Seek</span>
            <span><kbd className="bg-black px-1.5 py-0.5 rounded text-gray-300">↑/↓</kbd> Volume</span>
          </div>
          <div className="flex space-x-4">
            <span><kbd className="bg-black px-1.5 py-0.5 rounded text-gray-300">M</kbd> Mute</span>
            <span><kbd className="bg-black px-1.5 py-0.5 rounded text-gray-300">F</kbd> Fullscreen</span>
            <span><kbd className="bg-black px-1.5 py-0.5 rounded text-gray-300">Home/End</kbd> Start/End</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default VideoPlayer;
