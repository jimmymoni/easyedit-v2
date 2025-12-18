import React from 'react';
import { Play, Pause, ZoomIn, ZoomOut, Grid3x3, SkipBack, SkipForward } from 'lucide-react';

interface TimelineControlsProps {
  isPlaying: boolean;
  onPlayPause: () => void;
  zoom: number;
  onZoomChange: (zoom: number) => void;
  snapToGrid: boolean;
  onSnapToggle: () => void;
  onSkipToPrevious?: () => void;
  onSkipToNext?: () => void;
  duration: number;
  currentTime: number;
}

export default function TimelineControls({
  isPlaying,
  onPlayPause,
  zoom,
  onZoomChange,
  snapToGrid,
  onSnapToggle,
  onSkipToPrevious,
  onSkipToNext,
  duration,
  currentTime
}: TimelineControlsProps) {

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 100);
    return `${mins}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
  };

  const handleZoomIn = () => {
    onZoomChange(Math.min(zoom * 1.5, 200)); // Max 200 pixels per second
  };

  const handleZoomOut = () => {
    onZoomChange(Math.max(zoom / 1.5, 10)); // Min 10 pixels per second
  };

  return (
    <div className="flex items-center justify-between bg-[#181818] border-t border-border px-4 py-3">
      {/* Left: Playback Controls */}
      <div className="flex items-center space-x-2">
        {onSkipToPrevious && (
          <button
            onClick={onSkipToPrevious}
            className="p-2 rounded-lg hover:bg-accent transition-colors"
            title="Previous clip"
          >
            <SkipBack className="h-4 w-4 text-foreground" />
          </button>
        )}

        <button
          onClick={onPlayPause}
          className="p-3 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          title={isPlaying ? 'Pause (Space)' : 'Play (Space)'}
        >
          {isPlaying ? (
            <Pause className="h-5 w-5" />
          ) : (
            <Play className="h-5 w-5 ml-0.5" />
          )}
        </button>

        {onSkipToNext && (
          <button
            onClick={onSkipToNext}
            className="p-2 rounded-lg hover:bg-accent transition-colors"
            title="Next clip"
          >
            <SkipForward className="h-4 w-4 text-foreground" />
          </button>
        )}

        {/* Time Display */}
        <div className="ml-4 flex items-center space-x-2 text-sm font-mono">
          <span className="text-foreground">{formatTime(currentTime)}</span>
          <span className="text-muted-foreground">/</span>
          <span className="text-muted-foreground">{formatTime(duration)}</span>
        </div>
      </div>

      {/* Center: Zoom Controls */}
      <div className="flex items-center space-x-3">
        <span className="text-xs text-muted-foreground font-medium">Zoom:</span>

        <button
          onClick={handleZoomOut}
          className="p-2 rounded-lg hover:bg-accent transition-colors"
          title="Zoom out"
        >
          <ZoomOut className="h-4 w-4 text-foreground" />
        </button>

        <div className="flex items-center space-x-2">
          <input
            type="range"
            min="10"
            max="200"
            value={zoom}
            onChange={(e) => onZoomChange(Number(e.target.value))}
            className="w-32 h-1 bg-border rounded-lg appearance-none cursor-pointer"
            style={{
              background: `linear-gradient(to right, #FF6B35 0%, #FF6B35 ${((zoom - 10) / (200 - 10)) * 100}%, #3f3f46 ${((zoom - 10) / (200 - 10)) * 100}%, #3f3f46 100%)`
            }}
          />
          <span className="text-xs text-muted-foreground font-mono w-12 text-right">
            {Math.round(zoom)}px/s
          </span>
        </div>

        <button
          onClick={handleZoomIn}
          className="p-2 rounded-lg hover:bg-accent transition-colors"
          title="Zoom in"
        >
          <ZoomIn className="h-4 w-4 text-foreground" />
        </button>
      </div>

      {/* Right: Grid Toggle */}
      <div className="flex items-center space-x-2">
        <button
          onClick={onSnapToggle}
          className={`
            flex items-center space-x-2 px-3 py-2 rounded-lg transition-colors
            ${snapToGrid ? 'bg-primary/10 text-primary' : 'hover:bg-accent text-muted-foreground'}
          `}
          title={snapToGrid ? 'Snap to grid: ON' : 'Snap to grid: OFF'}
        >
          <Grid3x3 className="h-4 w-4" />
          <span className="text-xs font-medium">
            Snap {snapToGrid ? 'ON' : 'OFF'}
          </span>
        </button>
      </div>
    </div>
  );
}
