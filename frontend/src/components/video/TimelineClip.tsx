import React, { useState, useRef } from 'react';
import { useDrag } from '@use-gesture/react';
import { TimelineClip as TimelineClipType } from '../../types';
import { AlertCircle, User } from 'lucide-react';

interface TimelineClipProps {
  clip: TimelineClipType;
  zoom: number;
  isSelected: boolean;
  onSelect: () => void;
  onResize: (newStart: number, newEnd: number) => void;
  snapToGrid: boolean;
  gridSize: number;
}

export default function TimelineClip({
  clip,
  zoom,
  isSelected,
  onSelect,
  onResize,
  snapToGrid,
  gridSize
}: TimelineClipProps) {

  const clipRef = useRef<HTMLDivElement>(null);
  const [isResizing, setIsResizing] = useState<'left' | 'right' | null>(null);

  const pixelToTime = (pixels: number): number => pixels / zoom;
  const timeToPixel = (time: number): number => time * zoom;

  const snapTime = (time: number): number => {
    if (!snapToGrid) return time;
    return Math.round(time / gridSize) * gridSize;
  };

  // Calculate clip visual properties
  const clipWidth = timeToPixel(clip.duration);
  const clipLeft = timeToPixel(clip.startTime);

  // Determine clip color based on type and metadata
  const getClipColor = (): string => {
    if (clip.type === 'remove') return 'bg-red-500/20 border-red-500';
    if (clip.metadata?.hasRepetition) return 'bg-orange-500/20 border-orange-500';
    if (clip.metadata?.hasFalseStart) return 'bg-yellow-500/20 border-yellow-500';
    return 'bg-green-500/20 border-green-500';
  };

  // Left handle drag
  const bindLeftHandle = useDrag(({ movement: [mx], last }) => {
    if (!isResizing && !last) setIsResizing('left');

    const deltaTime = pixelToTime(mx);
    let newStart = clip.startTime + deltaTime;

    if (snapToGrid) {
      newStart = snapTime(newStart);
    }

    // Ensure minimum clip duration (0.1s)
    newStart = Math.max(newStart, clip.sourceStart);
    newStart = Math.min(newStart, clip.endTime - 0.1);

    if (last) {
      setIsResizing(null);
      onResize(newStart, clip.endTime);
    }
  }, {
    axis: 'x'
  });

  // Right handle drag
  const bindRightHandle = useDrag(({ movement: [mx], last }) => {
    if (!isResizing && !last) setIsResizing('right');

    const deltaTime = pixelToTime(mx);
    let newEnd = clip.endTime + deltaTime;

    if (snapToGrid) {
      newEnd = snapTime(newEnd);
    }

    // Ensure minimum clip duration (0.1s) and max (sourceEnd)
    newEnd = Math.max(newEnd, clip.startTime + 0.1);
    newEnd = Math.min(newEnd, clip.sourceEnd);

    if (last) {
      setIsResizing(null);
      onResize(clip.startTime, newEnd);
    }
  }, {
    axis: 'x'
  });

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = (seconds % 60).toFixed(1);
    return `${mins}:${secs.padStart(4, '0')}`;
  };

  return (
    <div
      ref={clipRef}
      onClick={onSelect}
      className={`
        absolute top-0 h-full border-2 rounded cursor-pointer transition-all
        ${getClipColor()}
        ${isSelected ? 'ring-2 ring-primary ring-offset-2 ring-offset-background z-10' : 'hover:brightness-110'}
        ${isResizing ? 'transition-none' : ''}
      `}
      style={{
        left: `${clipLeft}px`,
        width: `${clipWidth}px`,
        minWidth: '40px'
      }}
    >
      {/* Left Resize Handle */}
      <div
        {...bindLeftHandle()}
        className="absolute left-0 top-0 w-2 h-full cursor-ew-resize hover:bg-primary/50 transition-colors z-20"
        title="Drag to trim start"
      />

      {/* Clip Content */}
      <div className="px-2 py-1 h-full overflow-hidden flex flex-col justify-between">
        {/* Top: Clip info */}
        <div className="flex items-start justify-between text-xs">
          <div className="flex items-center space-x-1 min-w-0">
            {clip.speaker && (
              <div className="flex items-center space-x-1 text-foreground/70">
                <User className="h-3 w-3 flex-shrink-0" />
                <span className="font-medium truncate">{clip.speaker}</span>
              </div>
            )}
            {clip.metadata?.hasRepetition && (
              <AlertCircle className="h-3 w-3 text-orange-500 flex-shrink-0" title="Repetition detected" />
            )}
            {clip.metadata?.hasFalseStart && (
              <AlertCircle className="h-3 w-3 text-yellow-500 flex-shrink-0" title="False start detected" />
            )}
          </div>
        </div>

        {/* Middle: Transcript (if space available) */}
        {clipWidth > 100 && (
          <div className="text-xs text-foreground/60 line-clamp-2 leading-tight">
            {clip.text}
          </div>
        )}

        {/* Bottom: Time range */}
        <div className="text-xs text-foreground/50 font-mono">
          {formatTime(clip.sourceStart)} - {formatTime(clip.sourceEnd)}
        </div>
      </div>

      {/* Right Resize Handle */}
      <div
        {...bindRightHandle()}
        className="absolute right-0 top-0 w-2 h-full cursor-ew-resize hover:bg-primary/50 transition-colors z-20"
        title="Drag to trim end"
      />

      {/* Selection indicator */}
      {isSelected && (
        <div className="absolute inset-0 border-2 border-primary rounded pointer-events-none" />
      )}
    </div>
  );
}
