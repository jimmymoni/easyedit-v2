import React, { useEffect, useRef, useState } from 'react';
import WaveSurfer from 'wavesurfer.js';
import { Play, Pause, Volume2, ZoomIn, ZoomOut } from 'lucide-react';
import axios from 'axios';

interface WaveformViewerProps {
  jobId: string;
  audioUrl: string;
  onSeekReady?: (seekFn: (time: number) => void) => void;
  onTimeUpdate?: (currentTime: number) => void; // NEW: Expose playback position
}

const WaveformViewer: React.FC<WaveformViewerProps> = ({ jobId, audioUrl, onSeekReady, onTimeUpdate }) => {
  const waveformRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const loadingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState('0:00');
  const [duration, setDuration] = useState('0:00');
  const [volume, setVolume] = useState(0.75);
  const [zoom, setZoom] = useState(50);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Expose seek function to parent via callback
  useEffect(() => {
    if (wavesurferRef.current && !isLoading && onSeekReady) {
      const seekFn = (time: number) => {
        if (wavesurferRef.current) {
          wavesurferRef.current.seekTo(time / wavesurferRef.current.getDuration());
        }
      };
      onSeekReady(seekFn);
    }
  }, [isLoading, onSeekReady]);

  useEffect(() => {
    if (!waveformRef.current) return;

    let wavesurfer: WaveSurfer | null = null;
    let isMounted = true;

    // Initialize WaveSurfer
    wavesurfer = WaveSurfer.create({
      container: waveformRef.current,
      waveColor: '#2A2A2A',
      progressColor: '#FF6B35',
      cursorColor: '#FF6B35',
      barWidth: 2,
      barRadius: 3,
      cursorWidth: 2,
      height: 120,
      barGap: 2,
      backgroundColor: '#181818',
    });

    wavesurferRef.current = wavesurfer;

    // Set loading timeout (15 seconds)
    loadingTimeoutRef.current = setTimeout(() => {
      if (isMounted && isLoading) {
        setError('Audio loading timed out. Please try refreshing the page.');
        setIsLoading(false);
      }
    }, 15000);

    // Fetch audio with authentication headers
    const loadAudioWithAuth = async () => {
      try {
        // Get token from localStorage
        const tokens = localStorage.getItem('easyedit_tokens');
        if (!tokens) {
          throw new Error('No authentication token found');
        }

        const parsedTokens = JSON.parse(tokens);

        // Fetch audio file with auth header
        const response = await axios.get(audioUrl, {
          headers: {
            Authorization: `Bearer ${parsedTokens.access_token}`,
          },
          responseType: 'blob',
        });

        // Create blob URL
        const blob = response.data;
        const blobUrl = URL.createObjectURL(blob);

        // Load blob into wavesurfer
        if (wavesurfer && isMounted) {
          wavesurfer.load(blobUrl);
        }
      } catch (err: any) {
        console.error('Error loading audio:', err);
        if (isMounted) {
          if (err.response?.status === 401) {
            setError('Authentication required. Please log in again.');
          } else if (err.response?.status === 404) {
            setError('Audio file not found for this job.');
          } else {
            setError(err.message || 'Failed to load audio file');
          }
          setIsLoading(false);
        }
      }
    };

    loadAudioWithAuth();

    // Event listeners
    wavesurfer.on('ready', () => {
      if (isMounted) {
        setIsLoading(false);
        setDuration(formatTime(wavesurfer!.getDuration()));
        wavesurfer!.setVolume(volume);
        if (loadingTimeoutRef.current) {
          clearTimeout(loadingTimeoutRef.current);
        }
      }
    });

    wavesurfer.on('audioprocess', () => {
      if (isMounted) {
        const currentTimeValue = wavesurfer!.getCurrentTime();
        setCurrentTime(formatTime(currentTimeValue));
        // Emit current playback position to parent for transcription highlighting
        if (onTimeUpdate) {
          onTimeUpdate(currentTimeValue);
        }
      }
    });

    wavesurfer.on('play', () => {
      if (isMounted) setIsPlaying(true);
    });

    wavesurfer.on('pause', () => {
      if (isMounted) setIsPlaying(false);
    });

    wavesurfer.on('finish', () => {
      if (isMounted) setIsPlaying(false);
    });

    wavesurfer.on('error', (err) => {
      console.error('WaveSurfer error:', err);
      if (isMounted) {
        setError('Failed to load audio file. The file may be corrupted or in an unsupported format.');
        setIsLoading(false);
      }
    });

    return () => {
      isMounted = false;
      if (loadingTimeoutRef.current) {
        clearTimeout(loadingTimeoutRef.current);
      }
      if (wavesurfer) {
        wavesurfer.destroy();
      }
    };
  }, [audioUrl]);

  useEffect(() => {
    if (wavesurferRef.current) {
      wavesurferRef.current.setVolume(volume);
    }
  }, [volume]);

  useEffect(() => {
    if (wavesurferRef.current && !isLoading) {
      try {
        wavesurferRef.current.zoom(zoom);
      } catch (err) {
        // Ignore zoom errors if audio isn't loaded yet
        console.debug('Zoom not available yet');
      }
    }
  }, [zoom, isLoading]);

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const togglePlayPause = () => {
    if (wavesurferRef.current) {
      wavesurferRef.current.playPause();
    }
  };

  const handleZoomIn = () => {
    setZoom(prev => Math.min(prev + 25, 200));
  };

  const handleZoomOut = () => {
    setZoom(prev => Math.max(prev - 25, 25));
  };

  if (error) {
    return (
      <div className="bg-[#181818] border border-[#2A2A2A] rounded-xl p-8 text-center">
        <p className="text-red-400 mb-2">Error Loading Audio</p>
        <p className="text-[#EAEAEA]/70 text-sm">{error}</p>
      </div>
    );
  }

  return (
    <div className="bg-[#181818] border border-[#2A2A2A] rounded-xl shadow-lg p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-[#EAEAEA]">Audio Waveform</h3>
        <div className="flex items-center space-x-2">
          <span className="text-sm text-[#EAEAEA]/70 font-mono">
            {currentTime} / {duration}
          </span>
        </div>
      </div>

      {/* Waveform Container */}
      <div className="relative mb-4">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#181818] rounded-lg z-10">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#FF6B35]"></div>
            <span className="ml-3 text-[#EAEAEA]/70">Loading waveform...</span>
          </div>
        )}
        <div
          ref={waveformRef}
          className="rounded-lg overflow-hidden waveform-container"
          style={{ minHeight: '120px' }}
        />
        <style>{`
          /* Style the WaveSurfer scrollbar */
          .waveform-container ::-webkit-scrollbar {
            height: 8px;
          }
          .waveform-container ::-webkit-scrollbar-track {
            background: #2A2A2A;
            border-radius: 4px;
          }
          .waveform-container ::-webkit-scrollbar-thumb {
            background: #FF6B35;
            border-radius: 4px;
          }
          .waveform-container ::-webkit-scrollbar-thumb:hover {
            background: #FF8555;
          }
          /* Firefox scrollbar styling */
          .waveform-container * {
            scrollbar-width: thin;
            scrollbar-color: #FF6B35 #2A2A2A;
          }
        `}</style>
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between">
        {/* Play/Pause */}
        <div className="flex items-center space-x-3">
          <button
            onClick={togglePlayPause}
            disabled={isLoading}
            className="bg-[#FF6B35] hover:bg-[#FF6B35]/90 disabled:bg-[#2A2A2A] disabled:text-[#EAEAEA]/30 text-white p-3 rounded-lg transition-colors"
          >
            {isPlaying ? (
              <Pause className="h-5 w-5" />
            ) : (
              <Play className="h-5 w-5" />
            )}
          </button>

          {/* Volume */}
          <div className="flex items-center space-x-2">
            <Volume2 className="h-4 w-4 text-[#EAEAEA]/70" />
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={volume}
              onChange={(e) => setVolume(parseFloat(e.target.value))}
              className="w-24 accent-[#FF6B35]"
            />
          </div>
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center space-x-2">
          <span className="text-xs text-[#EAEAEA]/70 mr-2">Zoom:</span>
          <button
            onClick={handleZoomOut}
            disabled={zoom <= 25}
            className="p-2 hover:bg-[#2A2A2A] disabled:opacity-30 rounded transition-colors"
          >
            <ZoomOut className="h-4 w-4 text-[#EAEAEA]" />
          </button>
          <span className="text-xs text-[#EAEAEA]/70 font-mono w-12 text-center">
            {Math.round((zoom / 50) * 100)}%
          </span>
          <button
            onClick={handleZoomIn}
            disabled={zoom >= 200}
            className="p-2 hover:bg-[#2A2A2A] disabled:opacity-30 rounded transition-colors"
          >
            <ZoomIn className="h-4 w-4 text-[#EAEAEA]" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default WaveformViewer;
