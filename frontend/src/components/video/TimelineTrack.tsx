import React, { useMemo } from 'react';
import TimelineClip from './TimelineClip';
import { TimelineClip as TimelineClipType } from '../../types';

interface TimelineTrackProps {
  clips: TimelineClipType[];
  zoom: number;
  playhead: number;
  selectedClipId: string | null;
  onClipSelect: (clipId: string) => void;
  onClipResize: (clipId: string, newStart: number, newEnd: number) => void;
  snapToGrid: boolean;
  gridSize: number;
  totalDuration: number;
}

export default function TimelineTrack({
  clips,
  zoom,
  playhead,
  selectedClipId,
  onClipSelect,
  onClipResize,
  snapToGrid,
  gridSize,
  totalDuration
}: TimelineTrackProps) {

  // Sort clips by start time for proper rendering
  const sortedClips = useMemo(() => {
    return [...clips].sort((a, b) => a.startTime - b.startTime);
  }, [clips]);

  const timeToPixel = (time: number): number => time * zoom;
  const trackWidth = timeToPixel(totalDuration);

  // Generate grid lines based on zoom level
  const generateGridLines = (): number[] => {
    const lines: number[] = [];
    const interval = gridSize; // Grid interval in seconds
    const numLines = Math.ceil(totalDuration / interval);

    for (let i = 0; i <= numLines; i++) {
      lines.push(i * interval);
    }

    return lines;
  };

  const gridLines = useMemo(() => generateGridLines(), [totalDuration, gridSize]);

  return (
    <div className="relative bg-[#0a0a0a] border border-border rounded-lg overflow-hidden">
      {/* Time ruler */}
      <div className="h-6 bg-[#181818] border-b border-border relative">
        {gridLines.map((time, index) => {
          const left = timeToPixel(time);
          return (
            <div
              key={index}
              className="absolute top-0 h-full flex items-center"
              style={{ left: `${left}px` }}
            >
              <div className="h-2 w-px bg-border" />
              <span className="text-xs text-muted-foreground ml-1 font-mono">
                {Math.floor(time)}s
              </span>
            </div>
          );
        })}
      </div>

      {/* Track content */}
      <div
        className="relative h-24"
        style={{ width: `${Math.max(trackWidth, 800)}px` }}
      >
        {/* Grid lines */}
        {gridLines.map((time, index) => {
          const left = timeToPixel(time);
          return (
            <div
              key={`grid-${index}`}
              className="absolute top-0 h-full w-px bg-border/30"
              style={{ left: `${left}px` }}
            />
          );
        })}

        {/* Clips */}
        {sortedClips.map((clip) => (
          <TimelineClip
            key={clip.id}
            clip={clip}
            zoom={zoom}
            isSelected={clip.id === selectedClipId}
            onSelect={() => onClipSelect(clip.id)}
            onResize={(newStart, newEnd) => onClipResize(clip.id, newStart, newEnd)}
            snapToGrid={snapToGrid}
            gridSize={gridSize}
          />
        ))}

        {/* Playhead */}
        <div
          className="absolute top-0 h-full w-0.5 bg-primary z-30 pointer-events-none"
          style={{ left: `${timeToPixel(playhead)}px` }}
        >
          <div className="absolute -top-1 -left-2 w-4 h-4 bg-primary rounded-full" />
        </div>
      </div>

      {/* Track label */}
      <div className="absolute left-2 top-8 text-xs text-muted-foreground font-medium">
        Video Track
      </div>

      {/* Clip count */}
      <div className="absolute right-2 top-2 text-xs text-muted-foreground">
        {clips.filter(c => c.type === 'keep').length} clips
      </div>
    </div>
  );
}
