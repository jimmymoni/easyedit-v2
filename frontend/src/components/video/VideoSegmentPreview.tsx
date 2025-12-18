import { useState } from 'react';
import { VideoAnalysis, SegmentAdjustment } from '../../types';
import SegmentCard from './SegmentCard';
import { Card } from '@/components/ui/card';
import { BarChart3, Clock, Scissors, TrendingDown, CheckCircle, AlertCircle } from 'lucide-react';

interface VideoSegmentPreviewProps {
  analysis: VideoAnalysis;
  onApply: (adjustments: SegmentAdjustment[], encodingMethod: 'reencode' | 'lossless') => void;
  onCancel: () => void;
}

export default function VideoSegmentPreview({ analysis, onApply, onCancel }: VideoSegmentPreviewProps) {
  const [segments, setSegments] = useState(analysis.segments);
  const [encodingMethod, setEncodingMethod] = useState<'reencode' | 'lossless'>('reencode');

  const handleToggle = (segmentId: string, action: 'keep' | 'remove') => {
    setSegments(prev =>
      prev.map(seg =>
        seg.id === segmentId ? { ...seg, action } : seg
      )
    );
  };

  const handleSelectAll = (action: 'keep' | 'remove') => {
    setSegments(prev => prev.map(seg => ({ ...seg, action })));
  };

  const handleApply = () => {
    const adjustments: SegmentAdjustment[] = segments.map(seg => ({
      id: seg.id,
      action: seg.action
    }));
    onApply(adjustments, encodingMethod);
  };

  // Calculate updated stats based on current segment selections
  const updatedStats = segments.reduce((acc, seg) => {
    if (seg.action === 'keep') {
      acc.editedDuration += seg.duration;
      acc.segmentsToKeep++;
    } else {
      acc.segmentsToRemove++;
    }
    return acc;
  }, {
    editedDuration: 0,
    segmentsToKeep: 0,
    segmentsToRemove: 0
  });

  const timeSaved = analysis.stats.original_duration - updatedStats.editedDuration;
  const compressionRatio = updatedStats.editedDuration / analysis.stats.original_duration;

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
          <h3 className="text-lg font-semibold text-foreground">Analysis Summary</h3>
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
              {formatDuration(timeSaved)}
            </p>
          </div>

          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Compression</p>
            <p className="text-lg font-semibold text-foreground">
              {formatPercentage(compressionRatio)}
            </p>
          </div>
        </div>

        <div className="mt-4 pt-4 border-t border-border grid grid-cols-3 gap-4 text-sm">
          <div className="flex items-center gap-2">
            <Scissors className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">Total Segments:</span>
            <span className="font-medium text-foreground">{segments.length}</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-green-500" />
            <span className="text-muted-foreground">Keep:</span>
            <span className="font-medium text-foreground">{updatedStats.segmentsToKeep}</span>
          </div>
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 text-red-500" />
            <span className="text-muted-foreground">Remove:</span>
            <span className="font-medium text-foreground">{updatedStats.segmentsToRemove}</span>
          </div>
        </div>

        {/* Detected Patterns */}
        {analysis.detected_patterns && (
          <div className="mt-4 pt-4 border-t border-border">
            <p className="text-xs text-muted-foreground mb-2">Detected Patterns:</p>
            <div className="flex flex-wrap gap-2 text-xs">
              {analysis.detected_patterns.repetition_markers > 0 && (
                <span className="px-2 py-1 rounded-md bg-orange-500/10 text-orange-500">
                  🔄 {analysis.detected_patterns.repetition_markers} repetition markers
                </span>
              )}
              {analysis.detected_patterns.false_starts > 0 && (
                <span className="px-2 py-1 rounded-md bg-yellow-500/10 text-yellow-500">
                  ⚠️ {analysis.detected_patterns.false_starts} false starts
                </span>
              )}
              {analysis.detected_patterns.filler_heavy > 0 && (
                <span className="px-2 py-1 rounded-md bg-red-500/10 text-red-500">
                  💬 {analysis.detected_patterns.filler_heavy} filler-heavy sections
                </span>
              )}
            </div>
          </div>
        )}
      </Card>

      {/* Bulk Actions */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Bulk Actions:</span>
          <button
            onClick={() => handleSelectAll('keep')}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-green-500/10 text-green-500 hover:bg-green-500/20 transition-colors"
          >
            Keep All
          </button>
          <button
            onClick={() => handleSelectAll('remove')}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-red-500/10 text-red-500 hover:bg-red-500/20 transition-colors"
          >
            Remove All
          </button>
        </div>

        {/* Encoding Method Selection */}
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

      {/* Segment List */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-foreground">
          Detected Segments ({segments.length})
        </h3>
        <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2">
          {segments.map((segment) => (
            <SegmentCard
              key={segment.id}
              segment={segment}
              onToggle={handleToggle}
            />
          ))}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleApply}
          className="flex-1 flex items-center justify-center space-x-2 bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-3 rounded-lg font-medium transition-colors"
        >
          <Scissors className="h-5 w-5" />
          <span>Apply Cuts & Process Video</span>
        </button>

        <button
          onClick={onCancel}
          className="px-6 py-3 rounded-lg font-medium bg-muted text-foreground hover:bg-muted/80 transition-colors"
        >
          Cancel
        </button>
      </div>

      {/* Info Box */}
      <div className="bg-primary/5 border border-primary/10 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-foreground mb-2">Processing Options</h3>
        <div className="text-xs text-muted-foreground space-y-1.5 leading-relaxed">
          <p><strong className="text-foreground">Re-encode (Recommended):</strong> Cuts and re-encodes video for best compatibility. Takes 5-10 minutes but ensures clean cuts.</p>
          <p><strong className="text-foreground">Lossless:</strong> Fast cutting without re-encoding (1-2 min). May have keyframe issues at cut points.</p>
        </div>
      </div>
    </div>
  );
}
