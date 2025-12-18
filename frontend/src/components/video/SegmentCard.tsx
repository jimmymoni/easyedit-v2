import { VideoSegment } from '../../types';
import { Badge } from '@/components/ui/badge';
import { Clock, User, MessageSquare } from 'lucide-react';

interface SegmentCardProps {
  segment: VideoSegment;
  onToggle: (segmentId: string, action: 'keep' | 'remove') => void;
}

export default function SegmentCard({ segment, onToggle }: SegmentCardProps) {
  const isKeep = segment.action === 'keep';

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 10);
    return `${mins}:${secs.toString().padStart(2, '0')}.${ms}`;
  };

  const getReasonColor = (reason: string): string => {
    switch (reason.toLowerCase()) {
      case 'best take':
        return 'bg-green-500/10 text-green-500 border-green-500/20';
      case 'duplicate':
      case 'repeated content':
        return 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20';
      case 'false start':
        return 'bg-orange-500/10 text-orange-500 border-orange-500/20';
      case 'filler heavy':
        return 'bg-red-500/10 text-red-500 border-red-500/20';
      default:
        return 'bg-muted-foreground/10 text-muted-foreground border-muted-foreground/20';
    }
  };

  const getConfidenceColor = (confidence: number): string => {
    if (confidence >= 0.8) return 'text-green-500';
    if (confidence >= 0.5) return 'text-yellow-500';
    return 'text-red-500';
  };

  return (
    <div
      className={`
        relative rounded-xl border transition-all duration-200
        ${isKeep
          ? 'border-green-500/30 bg-green-500/5'
          : 'border-red-500/30 bg-red-500/5'
        }
      `}
    >
      {/* Left Border Indicator */}
      <div
        className={`
          absolute left-0 top-0 bottom-0 w-1 rounded-l-xl
          ${isKeep ? 'bg-green-500' : 'bg-red-500'}
        `}
      ></div>

      <div className="pl-5 pr-4 py-4">
        {/* Header with Toggle */}
        <div className="flex items-start justify-between gap-4 mb-3">
          <div className="flex-1 min-w-0 space-y-2">
            {/* Time Range */}
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Clock className="h-4 w-4 flex-shrink-0" />
              <span className="font-mono">
                {formatTime(segment.start_time)} - {formatTime(segment.end_time)}
              </span>
              <span className="text-xs">
                ({segment.duration.toFixed(1)}s)
              </span>
            </div>

            {/* Reason and Confidence */}
            <div className="flex items-center gap-2 flex-wrap">
              <Badge
                variant="outline"
                className={`text-xs font-medium border ${getReasonColor(segment.reason)}`}
              >
                {segment.reason}
              </Badge>

              {segment.speaker && (
                <Badge variant="secondary" className="text-xs">
                  <User className="h-3 w-3 mr-1" />
                  {segment.speaker}
                </Badge>
              )}

              <span className={`text-xs font-medium ${getConfidenceColor(segment.confidence)}`}>
                {Math.round(segment.confidence * 100)}% confidence
              </span>
            </div>
          </div>

          {/* Toggle Switch */}
          <label className="flex items-center cursor-pointer">
            <div className="relative">
              <input
                type="checkbox"
                checked={isKeep}
                onChange={(e) => onToggle(segment.id, e.target.checked ? 'keep' : 'remove')}
                className="sr-only"
              />
              <div
                className={`
                  w-14 h-7 rounded-full transition-colors duration-200
                  ${isKeep ? 'bg-green-500' : 'bg-red-500'}
                `}
              ></div>
              <div
                className={`
                  absolute left-1 top-1 bg-white w-5 h-5 rounded-full transition-transform duration-200
                  ${isKeep ? 'translate-x-7' : 'translate-x-0'}
                `}
              ></div>
            </div>
            <span className={`ml-3 text-sm font-medium ${isKeep ? 'text-green-500' : 'text-red-500'}`}>
              {isKeep ? 'Keep' : 'Remove'}
            </span>
          </label>
        </div>

        {/* Transcript Text */}
        {segment.text && (
          <div className="mt-3 pt-3 border-t border-border/50">
            <div className="flex items-start gap-2">
              <MessageSquare className="h-4 w-4 text-muted-foreground flex-shrink-0 mt-0.5" />
              <p className="text-sm text-foreground leading-relaxed">
                "{segment.text}"
              </p>
            </div>
          </div>
        )}

        {/* Markers for special detections */}
        {segment.has_repetition_marker && (
          <div className="mt-2 inline-flex items-center text-xs text-orange-500">
            <span className="mr-1">🔄</span>
            <span>Contains repetition marker</span>
          </div>
        )}
        {segment.has_false_start && (
          <div className="mt-2 inline-flex items-center text-xs text-yellow-500 ml-3">
            <span className="mr-1">⚠️</span>
            <span>False start detected</span>
          </div>
        )}
        {segment.filler_density && segment.filler_density > 0.2 && (
          <div className="mt-2 inline-flex items-center text-xs text-red-500 ml-3">
            <span className="mr-1">💬</span>
            <span>High filler density ({Math.round(segment.filler_density * 100)}%)</span>
          </div>
        )}
      </div>
    </div>
  );
}
