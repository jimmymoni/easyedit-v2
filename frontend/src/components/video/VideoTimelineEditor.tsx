import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { create } from 'zustand';
import { VideoAnalysis, TimelineClip, TimelineState, SegmentAdjustment } from '../../types';
import TimelineControls from './TimelineControls';
import TimelineTrack from './TimelineTrack';
import WaveformViewer from './WaveformViewer';
import { Card } from '@/components/ui/card';
import { BarChart3, Scissors, Info } from 'lucide-react';

interface VideoTimelineEditorProps {
  analysis: VideoAnalysis;
  audioUrl?: string;
  jobId: string;
  onApply: (adjustments: SegmentAdjustment[], encodingMethod: 'reencode' | 'lossless') => void;
  onCancel: () => void;
}

// Zustand store for timeline state
interface TimelineStore extends TimelineState {
  setClips: (clips: TimelineClip[]) => void;
  setPlayhead: (playhead: number) => void;
  setZoom: (zoom: number) => void;
  setSelectedClipId: (id: string | null) => void;
  setIsPlaying: (isPlaying: boolean) => void;
  setSnapToGrid: (snap: boolean) => void;
  updateClip: (clipId: string, updates: Partial<TimelineClip>) => void;
}

const useTimelineStore = create<TimelineStore>((set) => ({
  clips: [],
  playhead: 0,
  zoom: 50,  // Default 50 pixels per second
  selectedClipId: null,
  isPlaying: false,
  totalDuration: 0,
  snapToGrid: true,
  gridSize: 1.0,  // 1 second grid

  setClips: (clips) => set({ clips }),
  setPlayhead: (playhead) => set({ playhead }),
  setZoom: (zoom) => set({ zoom }),
  setSelectedClipId: (selectedClipId) => set({ selectedClipId }),
  setIsPlaying: (isPlaying) => set({ isPlaying }),
  setSnapToGrid: (snapToGrid) => set((state) => ({ snapToGrid })),
  updateClip: (clipId, updates) => set((state) => ({
    clips: state.clips.map(clip =>
      clip.id === clipId ? { ...clip, ...updates } : clip
    )
  }))
}));

export default function VideoTimelineEditor({
  analysis,
  audioUrl,
  jobId,
  onApply,
  onCancel
}: VideoTimelineEditorProps) {

  const [encodingMethod, setEncodingMethod] = useState<'reencode' | 'lossless'>('reencode');
  const [waveformReady, setWaveformReady] = useState(false);

  const {
    clips,
    playhead,
    zoom,
    selectedClipId,
    isPlaying,
    snapToGrid,
    gridSize,
    totalDuration,
    setClips,
    setPlayhead,
    setZoom,
    setSelectedClipId,
    setIsPlaying,
    setSnapToGrid,
    updateClip
  } = useTimelineStore();

  // Initialize clips from analysis
  useEffect(() => {
    const initialClips: TimelineClip[] = analysis.segments.map((segment, index) => {
      let timelineStart = 0;
      // Calculate timeline position based on previous clips
      for (let i = 0; i < index; i++) {
        if (analysis.segments[i].action === 'keep') {
          timelineStart += analysis.segments[i].duration;
        }
      }

      return {
        id: segment.id,
        startTime: timelineStart,
        endTime: timelineStart + segment.duration,
        duration: segment.duration,
        sourceStart: segment.start_time,
        sourceEnd: segment.end_time,
        text: segment.text,
        speaker: segment.speaker,
        type: segment.action,
        metadata: {
          hasRepetition: segment.has_repetition_marker,
          hasFalseStart: segment.has_false_start,
          fillerDensity: segment.filler_density,
          confidence: segment.confidence
        }
      };
    });

    setClips(initialClips);
  }, [analysis, setClips]);

  // Calculate total duration
  const calculatedDuration = useMemo(() => {
    const keptClips = clips.filter(c => c.type === 'keep');
    if (keptClips.length === 0) return 0;
    return Math.max(...keptClips.map(c => c.endTime));
  }, [clips]);

  // Handle clip selection
  const handleClipSelect = useCallback((clipId: string) => {
    setSelectedClipId(clipId);
  }, [setSelectedClipId]);

  // Handle clip resize
  const handleClipResize = useCallback((clipId: string, newStart: number, newEnd: number) => {
    const clip = clips.find(c => c.id === clipId);
    if (!clip) return;

    const newDuration = newEnd - newStart;

    // Update the clip
    updateClip(clipId, {
      startTime: newStart,
      endTime: newEnd,
      duration: newDuration
    });

    // Recalculate positions of subsequent clips
    const clipIndex = clips.findIndex(c => c.id === clipId);
    let currentTime = newEnd;

    for (let i = clipIndex + 1; i < clips.length; i++) {
      if (clips[i].type === 'keep') {
        updateClip(clips[i].id, {
          startTime: currentTime,
          endTime: currentTime + clips[i].duration
        });
        currentTime += clips[i].duration;
      }
    }
  }, [clips, updateClip]);

  // Handle play/pause
  const handlePlayPause = useCallback(() => {
    setIsPlaying(!isPlaying);
    // TODO: Implement actual video playback
  }, [isPlaying, setIsPlaying]);

  // Handle seek
  const handleSeek = useCallback((time: number) => {
    setPlayhead(time);
    setIsPlaying(false);
  }, [setPlayhead, setIsPlaying]);

  // Handle skip to previous clip
  const handleSkipToPrevious = useCallback(() => {
    const keptClips = clips.filter(c => c.type === 'keep').sort((a, b) => a.startTime - b.startTime);
    const currentIndex = keptClips.findIndex(c => c.startTime >= playhead);

    if (currentIndex > 0) {
      setPlayhead(keptClips[currentIndex - 1].startTime);
    } else if (keptClips.length > 0) {
      setPlayhead(0);
    }
  }, [clips, playhead, setPlayhead]);

  // Handle skip to next clip
  const handleSkipToNext = useCallback(() => {
    const keptClips = clips.filter(c => c.type === 'keep').sort((a, b) => a.startTime - b.startTime);
    const currentIndex = keptClips.findIndex(c => c.startTime > playhead);

    if (currentIndex !== -1 && currentIndex < keptClips.length) {
      setPlayhead(keptClips[currentIndex].startTime);
    }
  }, [clips, playhead, setPlayhead]);

  // Calculate updated stats
  const updatedStats = useMemo(() => {
    const keptClips = clips.filter(c => c.type === 'keep');
    const removedClips = clips.filter(c => c.type === 'remove');
    const editedDuration = keptClips.reduce((sum, c) => sum + c.duration, 0);
    const timeSaved = analysis.stats.original_duration - editedDuration;
    const compressionRatio = editedDuration / analysis.stats.original_duration;

    return {
      segmentsToKeep: keptClips.length,
      segmentsToRemove: removedClips.length,
      editedDuration,
      timeSaved,
      compressionRatio
    };
  }, [clips, analysis.stats.original_duration]);

  // Handle apply
  const handleApply = useCallback(() => {
    const adjustments: SegmentAdjustment[] = clips
      .filter(clip => clip.type === 'keep')
      .map(clip => ({
        id: clip.id,
        action: 'keep' as const,
        start_time: clip.sourceStart,
        end_time: clip.sourceEnd
      }));

    onApply(adjustments, encodingMethod);
  }, [clips, encodingMethod, onApply]);

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatPercentage = (value: number): string => {
    return `${(value * 100).toFixed(1)}%`;
  };

  return (
    <div className="space-y-6">
      {/* Stats Summary */}
      <Card className="p-6">
        <div className="flex items-center space-x-2 mb-4">
          <BarChart3 className="h-5 w-5 text-primary" />
          <h3 className="text-lg font-semibold text-foreground">Timeline Editor</h3>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Original Duration</p>
            <p className="text-lg font-semibold text-foreground">
              {formatDuration(analysis.stats.original_duration)}
            </p>
          </div>

          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Edited Duration</p>
            <p className="text-lg font-semibold text-primary">
              {formatDuration(updatedStats.editedDuration)}
            </p>
          </div>

          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Time Saved</p>
            <p className="text-lg font-semibold text-green-500">
              {formatDuration(updatedStats.timeSaved)}
            </p>
          </div>

          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Compression</p>
            <p className="text-lg font-semibold text-foreground">
              {formatPercentage(updatedStats.compressionRatio)}
            </p>
          </div>
        </div>

        <div className="mt-4 pt-4 border-t border-border flex items-center justify-between">
          <div className="flex items-center space-x-4 text-sm">
            <div className="flex items-center gap-2">
              <Scissors className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">Segments:</span>
              <span className="font-medium text-green-500">{updatedStats.segmentsToKeep} keep</span>
              <span className="text-muted-foreground">/</span>
              <span className="font-medium text-red-500">{updatedStats.segmentsToRemove} remove</span>
            </div>
          </div>

          {/* Encoding Method */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Method:</span>
            <select
              value={encodingMethod}
              onChange={(e) => setEncodingMethod(e.target.value as 'reencode' | 'lossless')}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-card border border-border text-foreground"
            >
              <option value="reencode">Re-encode (Reliable)</option>
              <option value="lossless">Lossless (Fast)</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Waveform */}
      <WaveformViewer
        audioUrl={audioUrl}
        playhead={playhead}
        onSeek={handleSeek}
        zoom={zoom}
        isPlaying={isPlaying}
        onReady={() => setWaveformReady(true)}
      />

      {/* Timeline Track */}
      <TimelineTrack
        clips={clips}
        zoom={zoom}
        playhead={playhead}
        selectedClipId={selectedClipId}
        onClipSelect={handleClipSelect}
        onClipResize={handleClipResize}
        snapToGrid={snapToGrid}
        gridSize={gridSize}
        totalDuration={calculatedDuration || analysis.stats.original_duration}
      />

      {/* Timeline Controls */}
      <TimelineControls
        isPlaying={isPlaying}
        onPlayPause={handlePlayPause}
        zoom={zoom}
        onZoomChange={setZoom}
        snapToGrid={snapToGrid}
        onSnapToggle={() => setSnapToGrid(!snapToGrid)}
        onSkipToPrevious={handleSkipToPrevious}
        onSkipToNext={handleSkipToNext}
        duration={calculatedDuration || analysis.stats.original_duration}
        currentTime={playhead}
      />

      {/* Info Box */}
      <div className="bg-primary/5 border border-primary/10 rounded-xl p-5">
        <div className="flex items-start space-x-3">
          <Info className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
          <div className="text-sm text-muted-foreground space-y-2">
            <p><strong className="text-foreground">How to use:</strong> Drag the edges of clips to trim them. Click clips to select. Use zoom controls to see more detail.</p>
            <p><strong className="text-foreground">Snap to grid:</strong> When enabled, clips snap to 1-second intervals for easier alignment.</p>
            <p><strong className="text-foreground">Colors:</strong> Green = keep, Red = remove, Orange = repetition detected, Yellow = false start detected.</p>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleApply}
          className="flex-1 flex items-center justify-center space-x-2 bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-3 rounded-lg font-medium transition-colors"
        >
          <Scissors className="h-5 w-5" />
          <span>Apply Edits & Process Video</span>
        </button>

        <button
          onClick={onCancel}
          className="px-6 py-3 rounded-lg font-medium bg-muted text-foreground hover:bg-muted/80 transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
