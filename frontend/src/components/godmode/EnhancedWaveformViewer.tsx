import React, { useEffect, useRef, useState } from 'react';
import WaveSurfer from 'wavesurfer.js';
import { Play, Pause, Volume2, ZoomIn, ZoomOut, GitCompare, ArrowLeft, ArrowRight, Scissors, TrendingDown } from 'lucide-react';
import axios from 'axios';
import * as api from '../../services/api';

interface WaveformViewerProps {
  jobId: string;
  audioUrl: string;
  onSeekReady?: (seekFn: (time: number) => void) => void;
  onTimeUpdate?: (currentTime: number) => void;
  autoSwitchToEdited?: boolean; // Auto-switch after AI edit
}

const EnhancedWaveformViewer: React.FC<WaveformViewerProps> = ({
  jobId,
  audioUrl,
  onSeekReady,
  onTimeUpdate,
  autoSwitchToEdited = false
}) => {
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

  // Comparison data
  const [comparisonData, setComparisonData] = useState<any | null>(null);
  const [viewMode, setViewMode] = useState<'original' | 'edited'>('original');
  const [isLoadingComparison, setIsLoadingComparison] = useState(false);
  const [currentAudioUrl, setCurrentAudioUrl] = useState(audioUrl);

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

  // Load comparison data
  useEffect(() => {
    loadComparisonData();
  }, [jobId]);

  // Auto-switch to edited view when AI edit completes
  useEffect(() => {
    if (autoSwitchToEdited && comparisonData?.has_edits) {
      setViewMode('edited');
    }
  }, [autoSwitchToEdited, comparisonData]);

  const loadComparisonData = async () => {
    try {
      setIsLoadingComparison(true);
      const data = await api.getTimelineComparison(jobId);
      setComparisonData(data);
    } catch (err: any) {
      console.error('Error loading timeline comparison:', err);
      // Don't show error if comparison data not available yet
    } finally {
      setIsLoadingComparison(false);
    }
  };

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
        const tokens = localStorage.getItem('easyedit_tokens');
        if (!tokens) {
          throw new Error('No authentication token found');
        }

        const parsedTokens = JSON.parse(tokens);

        const response = await axios.get(currentAudioUrl, {
          headers: {
            Authorization: `Bearer ${parsedTokens.access_token}`,
          },
          responseType: 'blob',
        });

        const blob = response.data;
        const blobUrl = URL.createObjectURL(blob);

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
  }, [currentAudioUrl]);

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

  const toggleViewMode = () => {
    const newMode = viewMode === 'original' ? 'edited' : 'original';
    setViewMode(newMode);

    // Switch audio URL based on view mode
    if (newMode === 'edited') {
      setCurrentAudioUrl(`http://localhost:5000/audio/${jobId}/edited`);
    } else {
      setCurrentAudioUrl(audioUrl);
    }
  };

  // Render timeline regions bar showing what will be removed
  const renderRemovedRegionsBar = () => {
    if (!comparisonData?.has_edits || viewMode === 'edited') return null;

    const { diff, stats } = comparisonData;
    if (!diff.removed_regions || diff.removed_regions.length === 0) return null;

    const totalDuration = stats.original_duration;

    return (
      <div className="mt-4 mb-2">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-[#EAEAEA]/70">Timeline Overview</span>
          <span className="text-xs text-red-400">
            {diff.removed_regions.length} section{diff.removed_regions.length > 1 ? 's' : ''} will be removed
          </span>
        </div>
        <div className="relative h-8 bg-[#0A0A0A] rounded-lg border border-[#2A2A2A] overflow-hidden">
          {/* Full timeline background (kept regions in green) */}
          <div className="absolute inset-0 bg-green-500/20" />

          {/* Removed regions (in red) */}
          {diff.removed_regions.map((region: any, index: number) => (
            <div
              key={index}
              className="absolute top-0 bottom-0 bg-red-500 hover:bg-red-600 transition-colors cursor-help group"
              style={{
                left: `${(region.start / totalDuration) * 100}%`,
                width: `${(region.duration / totalDuration) * 100}%`
              }}
              title={`Removed: ${formatTime(region.start)} - ${formatTime(region.end)} (${formatTime(region.duration)})`}
            >
              <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                <Scissors className="h-3 w-3 text-white" />
              </div>
            </div>
          ))}

          {/* Time markers */}
          {[0, 0.25, 0.5, 0.75, 1].map((fraction, i) => (
            <div
              key={i}
              className="absolute top-0 bottom-0 border-l border-[#EAEAEA]/20"
              style={{ left: `${fraction * 100}%` }}
            >
              <span className="absolute -bottom-5 -translate-x-1/2 text-[10px] text-[#EAEAEA]/50 font-mono">
                {formatTime(totalDuration * fraction)}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  if (error) {
    return (
      <div className="bg-[#181818] border border-[#2A2A2A] rounded-xl p-8 text-center">
        <p className="text-red-400 mb-2">Error Loading Audio</p>
        <p className="text-[#EAEAEA]/70 text-sm">{error}</p>
      </div>
    );
  }

  const hasEdits = comparisonData?.has_edits;
  const stats = comparisonData?.stats;

  return (
    <div className="bg-[#181818] border border-[#2A2A2A] rounded-xl shadow-lg p-6">
      {/* Header with View Toggle */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          <h3 className="text-lg font-semibold text-[#EAEAEA]">
            {viewMode === 'original' ? 'Original' : 'Edited'} Waveform
          </h3>
          {hasEdits && viewMode === 'edited' && (
            <div className="flex items-center space-x-2 text-sm bg-[#FF6B35]/10 text-[#FF6B35] px-2 py-1 rounded">
              <TrendingDown className="h-3 w-3" />
              <span className="font-semibold">{stats.compression_percentage}% shorter</span>
            </div>
          )}
        </div>

        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <span className="text-sm text-[#EAEAEA]/70 font-mono">
              {currentTime} / {duration}
            </span>
          </div>

          {/* View Toggle Button */}
          {hasEdits && (
            <button
              onClick={toggleViewMode}
              className="flex items-center space-x-2 bg-[#2A2A2A] hover:bg-[#FF6B35] text-[#EAEAEA] px-3 py-2 rounded-lg text-sm transition-colors"
              title={`Switch to ${viewMode === 'original' ? 'edited' : 'original'} view`}
            >
              <GitCompare className="h-4 w-4" />
              <span>{viewMode === 'original' ? 'View Edited' : 'View Original'}</span>
              {viewMode === 'original' ? (
                <ArrowRight className="h-3 w-3" />
              ) : (
                <ArrowLeft className="h-3 w-3" />
              )}
            </button>
          )}
        </div>
      </div>

      {/* Stats Bar (when viewing edited) */}
      {hasEdits && viewMode === 'edited' && stats && (
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="bg-[#0A0A0A] border border-[#2A2A2A] rounded-lg p-3">
            <div className="text-xs text-[#EAEAEA]/70 mb-1">Time Saved</div>
            <div className="text-lg font-semibold text-[#FF6B35]">
              {formatTime(stats.time_saved)}
            </div>
          </div>
          <div className="bg-[#0A0A0A] border border-[#2A2A2A] rounded-lg p-3">
            <div className="text-xs text-[#EAEAEA]/70 mb-1">Clips Removed</div>
            <div className="text-lg font-semibold text-[#EAEAEA]">
              {stats.clips_removed}
            </div>
          </div>
          <div className="bg-[#0A0A0A] border border-[#2A2A2A] rounded-lg p-3">
            <div className="text-xs text-[#EAEAEA]/70 mb-1">Final Duration</div>
            <div className="text-lg font-semibold text-[#EAEAEA]">
              {formatTime(stats.edited_duration)}
            </div>
          </div>
        </div>
      )}

      {/* Waveform Container */}
      <div className="relative mb-4">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#181818] rounded-lg z-10">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#FF6B35]"></div>
            <span className="ml-3 text-[#EAEAEA]/70">Loading waveform...</span>
          </div>
        )}
        <div
          className="relative rounded-lg overflow-hidden waveform-container"
          style={{ minHeight: '120px' }}
        >
          <div ref={waveformRef} />
        </div>
        <style>{`
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
          .waveform-container * {
            scrollbar-width: thin;
            scrollbar-color: #FF6B35 #2A2A2A;
          }
        `}</style>
      </div>

      {/* Timeline Overview Bar - Shows removed regions */}
      {renderRemovedRegionsBar()}

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

      {/* Swipe Hint */}
      {hasEdits && (
        <div className="mt-4 text-center text-xs text-[#EAEAEA]/50">
          Click "View {viewMode === 'original' ? 'Edited' : 'Original'}" to toggle between versions
        </div>
      )}
    </div>
  );
};

export default EnhancedWaveformViewer;
