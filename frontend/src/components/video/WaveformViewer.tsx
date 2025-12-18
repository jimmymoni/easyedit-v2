import React, { useEffect, useRef, useState } from 'react';
import WaveSurfer from 'wavesurfer.js';
import { Loader2 } from 'lucide-react';

interface WaveformViewerProps {
  audioUrl?: string;
  playhead: number;
  onSeek: (time: number) => void;
  zoom: number;
  isPlaying: boolean;
  onReady?: () => void;
}

export default function WaveformViewer({
  audioUrl,
  playhead,
  onSeek,
  zoom,
  isPlaying,
  onReady
}: WaveformViewerProps) {

  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Initialize WaveSurfer
  useEffect(() => {
    if (!containerRef.current || !audioUrl) return;

    setIsLoading(true);
    setError(null);

    try {
      // Create WaveSurfer instance
      const wavesurfer = WaveSurfer.create({
        container: containerRef.current,
        waveColor: '#FF6B35',
        progressColor: '#FF8C42',
        cursorColor: '#FF6B35',
        barWidth: 2,
        barRadius: 3,
        responsive: true,
        height: 80,
        normalize: true,
        backend: 'WebAudio',
        hideScrollbar: true,
        interact: false // Disable WaveSurfer's built-in interaction
      });

      wavesurferRef.current = wavesurfer;

      // Load audio
      wavesurfer.load(audioUrl);

      // Ready event
      wavesurfer.on('ready', () => {
        setIsLoading(false);
        onReady?.();
      });

      // Error event
      wavesurfer.on('error', (err) => {
        console.error('WaveSurfer error:', err);
        setError('Failed to load audio waveform');
        setIsLoading(false);
      });

      // Cleanup
      return () => {
        wavesurfer.destroy();
      };
    } catch (err) {
      console.error('WaveSurfer initialization error:', err);
      setError('Failed to initialize waveform viewer');
      setIsLoading(false);
    }
  }, [audioUrl, onReady]);

  // Update playhead position
  useEffect(() => {
    if (wavesurferRef.current && !isPlaying) {
      const duration = wavesurferRef.current.getDuration();
      if (duration > 0) {
        wavesurferRef.current.seekTo(playhead / duration);
      }
    }
  }, [playhead, isPlaying]);

  // Handle zoom changes
  useEffect(() => {
    if (wavesurferRef.current) {
      // Adjust waveform zoom (minPxPerSec)
      const minPxPerSec = Math.max(10, Math.min(zoom, 200));
      wavesurferRef.current.params.minPxPerSec = minPxPerSec;
      wavesurferRef.current.drawBuffer();
    }
  }, [zoom]);

  // Handle click to seek
  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!wavesurferRef.current) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const width = rect.width;
    const percentage = x / width;
    const duration = wavesurferRef.current.getDuration();
    const newTime = percentage * duration;

    onSeek(newTime);
  };

  if (!audioUrl) {
    return (
      <div className="h-20 bg-[#0a0a0a] border border-border rounded-lg flex items-center justify-center">
        <p className="text-sm text-muted-foreground">No audio available for waveform</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-20 bg-[#0a0a0a] border border-border rounded-lg flex items-center justify-center">
        <p className="text-sm text-red-500">{error}</p>
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Waveform container */}
      <div
        ref={containerRef}
        onClick={handleClick}
        className="h-20 bg-[#0a0a0a] border border-border rounded-lg cursor-pointer overflow-hidden"
      />

      {/* Loading overlay */}
      {isLoading && (
        <div className="absolute inset-0 bg-[#0a0a0a]/80 flex items-center justify-center rounded-lg">
          <div className="flex items-center space-x-2 text-primary">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span className="text-sm">Loading waveform...</span>
          </div>
        </div>
      )}

      {/* Label */}
      <div className="absolute left-2 top-2 text-xs text-muted-foreground font-medium">
        Audio Waveform
      </div>
    </div>
  );
}
