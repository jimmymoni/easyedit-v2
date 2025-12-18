import React from 'react';
import VideoPlayer from './VideoPlayer';

/**
 * Example component demonstrating VideoPlayer usage
 *
 * This example shows how to integrate the VideoPlayer component
 * with callback handlers for time synchronization.
 *
 * Usage:
 * ```tsx
 * import VideoPlayerExample from '@/components/video/player/VideoPlayerExample';
 *
 * function MyPage() {
 *   const jobId = "your-video-job-id";
 *   return <VideoPlayerExample jobId={jobId} />;
 * }
 * ```
 */
interface VideoPlayerExampleProps {
  jobId: string;
}

const VideoPlayerExample: React.FC<VideoPlayerExampleProps> = ({ jobId }) => {
  const handleTimeUpdate = (currentTime: number) => {
    console.log('Current time:', currentTime);
    // Use this callback to:
    // - Sync timeline playhead position
    // - Update waveform viewer
    // - Trigger time-based events
  };

  const handleDurationChange = (duration: number) => {
    console.log('Video duration:', duration);
    // Use this callback to:
    // - Set timeline total duration
    // - Initialize waveform length
    // - Calculate segment boundaries
  };

  return (
    <div className="max-w-5xl mx-auto p-6">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-foreground mb-2">Video Player - Phase 2.1</h2>
        <p className="text-muted-foreground">
          The video player automatically loads the H.264 proxy for smooth playback.
        </p>
      </div>

      {/* Video Player */}
      <VideoPlayer
        jobId={jobId}
        onTimeUpdate={handleTimeUpdate}
        onDurationChange={handleDurationChange}
        className="shadow-2xl"
      />

      {/* Features Documentation */}
      <div className="mt-6 bg-card rounded-lg border border-border p-6">
        <h3 className="font-semibold text-foreground mb-4 text-lg">✅ Implemented Features</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Column 1: Core Features */}
          <div>
            <h4 className="font-medium text-foreground mb-2">Core Functionality</h4>
            <ul className="space-y-1 text-sm text-muted-foreground">
              <li>✓ Automatic proxy status detection</li>
              <li>✓ Real-time transcoding progress</li>
              <li>✓ Play/Pause controls</li>
              <li>✓ Seek with progress bar</li>
              <li>✓ Volume controls</li>
              <li>✓ Fullscreen support</li>
              <li>✓ Buffering progress indicator</li>
              <li>✓ Time synchronization callbacks</li>
            </ul>
          </div>

          {/* Column 2: States & Shortcuts */}
          <div>
            <h4 className="font-medium text-foreground mb-2">States & Shortcuts</h4>
            <ul className="space-y-1 text-sm text-muted-foreground">
              <li>✓ Loading state (checking proxy)</li>
              <li>✓ Transcoding state (with progress)</li>
              <li>✓ Error handling (failed/not found)</li>
              <li>✓ Keyboard shortcuts (Space, ←/→, ↑/↓)</li>
              <li>✓ Home/End navigation</li>
              <li>✓ Mute toggle (M key)</li>
              <li>✓ Fullscreen toggle (F key)</li>
              <li>✓ Responsive design</li>
            </ul>
          </div>
        </div>

        {/* Keyboard Shortcuts Reference */}
        <div className="mt-6 pt-6 border-t border-border">
          <h4 className="font-medium text-foreground mb-3">⌨️ Keyboard Shortcuts</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div className="bg-[#181818] rounded px-3 py-2">
              <kbd className="bg-black px-2 py-1 rounded text-gray-300">Space</kbd>
              <p className="text-gray-400 mt-1">Play/Pause</p>
            </div>
            <div className="bg-[#181818] rounded px-3 py-2">
              <kbd className="bg-black px-2 py-1 rounded text-gray-300">← →</kbd>
              <p className="text-gray-400 mt-1">Seek ±5s</p>
            </div>
            <div className="bg-[#181818] rounded px-3 py-2">
              <kbd className="bg-black px-2 py-1 rounded text-gray-300">↑ ↓</kbd>
              <p className="text-gray-400 mt-1">Volume</p>
            </div>
            <div className="bg-[#181818] rounded px-3 py-2">
              <kbd className="bg-black px-2 py-1 rounded text-gray-300">M</kbd>
              <p className="text-gray-400 mt-1">Mute</p>
            </div>
            <div className="bg-[#181818] rounded px-3 py-2">
              <kbd className="bg-black px-2 py-1 rounded text-gray-300">F</kbd>
              <p className="text-gray-400 mt-1">Fullscreen</p>
            </div>
            <div className="bg-[#181818] rounded px-3 py-2">
              <kbd className="bg-black px-2 py-1 rounded text-gray-300">Home</kbd>
              <p className="text-gray-400 mt-1">Start</p>
            </div>
            <div className="bg-[#181818] rounded px-3 py-2">
              <kbd className="bg-black px-2 py-1 rounded text-gray-300">End</kbd>
              <p className="text-gray-400 mt-1">End</p>
            </div>
          </div>
        </div>

        {/* Integration Notes */}
        <div className="mt-6 pt-6 border-t border-border">
          <h4 className="font-medium text-foreground mb-2">🔗 Integration with Timeline (Phase 2.2+)</h4>
          <p className="text-sm text-muted-foreground">
            The <code className="bg-black px-1 py-0.5 rounded text-primary">onTimeUpdate</code> and{' '}
            <code className="bg-black px-1 py-0.5 rounded text-primary">onDurationChange</code> callbacks
            will be used to synchronize the timeline playhead, waveform viewer, and segment markers.
          </p>
        </div>
      </div>
    </div>
  );
};

export default VideoPlayerExample;
