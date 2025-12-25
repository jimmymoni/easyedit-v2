import { useState, useEffect, useRef } from 'react';
import { Sparkles } from 'lucide-react';
import { VideoAnalysis, VideoSegment, SegmentAdjustment } from '../../types';
import * as api from '../../services/api';
import AIPromptPanel from './AIPromptPanel';

interface TimelineEditorNewProps {
  analysis: VideoAnalysis;
  jobId: string;
  onApply: (adjustments: SegmentAdjustment[], encodingMethod: 'reencode' | 'lossless') => void;
  onCancel: () => void;
}

export default function TimelineEditorNew({
  analysis,
  jobId,
  onApply,
  onCancel
}: TimelineEditorNewProps) {
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [videoReady, setVideoReady] = useState(false);
  const [videoUrl, setVideoUrl] = useState<string>('');
  const [showAIPanel, setShowAIPanel] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const isPreview = jobId === 'preview-demo';

  // Fetch video URL on mount
  useEffect(() => {
    if (isPreview || !jobId) return;

    const fetchVideoUrl = async () => {
      try {
        const status = await api.getVideoJobStatus(jobId);
        console.log('[TimelineEditorNew] Video status response:', status);

        // Try multiple URL sources (fallback chain)
        const url = status.proxy_url         // Primary: S3 presigned URL
          || status.video_url                // Fallback 1: Direct video URL
          || status.s3_url                   // Fallback 2: Alternative S3 URL
          || status.url;                     // Fallback 3: Generic URL field

        if (url) {
          console.log('[TimelineEditorNew] Setting video URL:', url);
          setVideoUrl(url);
        } else {
          // Last resort: construct proxy endpoint URL
          const proxyUrl = `http://localhost:5000/video-proxy/${jobId}`;
          console.log('[TimelineEditorNew] No URL in response, trying proxy:', proxyUrl);
          setVideoUrl(proxyUrl);
        }
      } catch (err) {
        console.error('[TimelineEditorNew] Failed to fetch video URL:', err);
        // Fallback to proxy endpoint on error
        const proxyUrl = `http://localhost:5000/video-proxy/${jobId}`;
        console.log('[TimelineEditorNew] Error fallback, using proxy:', proxyUrl);
        setVideoUrl(proxyUrl);
      }
    };

    fetchVideoUrl();
  }, [jobId, isPreview]);

  // Debug logging - check what data we're receiving
  useEffect(() => {
    console.log('[TimelineEditorNew] Props received:', {
      jobId,
      analysisSegmentsCount: analysis?.segments?.length,
      totalDuration: analysis?.stats?.original_duration,
      firstSegment: analysis?.segments?.[0],
    });

    // Check for timestamp issues
    if (analysis?.segments?.length > 0) {
      const firstSeg = analysis.segments[0];
      console.log('[TimelineEditorNew] First segment detailed check:', {
        hasStartTime: 'start_time' in firstSeg,
        hasEndTime: 'end_time' in firstSeg,
        hasDuration: 'duration' in firstSeg,
        startTimeValue: firstSeg.start_time,
        endTimeValue: firstSeg.end_time,
        durationValue: firstSeg.duration,
        allKeys: Object.keys(firstSeg),
      });
    }
  }, [analysis, jobId]);

  // Filter segments with 'keep' action and validate timestamps
  const segments = analysis.segments
    .filter(seg => seg.action === 'keep')
    .map((seg, idx) => {
      // Log warning if timestamps are missing
      if ((seg.start_time === undefined || seg.start_time === 0) &&
          (seg.end_time === undefined || seg.end_time === 0)) {
        console.warn(`[TimelineEditorNew] Segment ${seg.id || idx} has invalid timestamps`, seg);
      }
      return seg;
    });

  // DIAGNOSTIC: Detailed segment structure analysis
  useEffect(() => {
    if (segments && segments.length > 0) {
      console.log('[DEBUG] ===== SEGMENT STRUCTURE ANALYSIS =====');
      console.log('[DEBUG] Full first segment:', JSON.stringify(segments[0], null, 2));
      console.log('[DEBUG] All keys in first segment:', Object.keys(segments[0]));

      // Check for various timestamp property names
      const seg = segments[0];
      console.log('[DEBUG] Possible timestamp values:', {
        start_time: seg.start_time,
        startTime: (seg as any).startTime,
        start: (seg as any).start,
        begin: (seg as any).begin,
        end_time: seg.end_time,
        endTime: (seg as any).endTime,
        end: (seg as any).end,
        timestamp: (seg as any).timestamp,
        timestamps: (seg as any).timestamps,
      });
    }
  }, [segments]);

  // Debug video URL
  useEffect(() => {
    if (!isPreview) {
      console.log('[TimelineEditorNew] Video URL:', videoUrl);
    }
  }, [videoUrl, isPreview]);

  // Sync currentTime with video playback
  useEffect(() => {
    const video = videoRef.current;

    // Only run when we have BOTH video element AND video URL
    if (!video || !videoUrl) {
      console.log('[TimelineEditorNew] Waiting for video element and URL...');
      return;
    }

    console.log('[TimelineEditorNew] Attaching event listeners, videoUrl:', videoUrl);

    // Reset videoReady when URL changes (new video loading)
    setVideoReady(false);

    const handleTimeUpdate = () => {
      setCurrentTime(video.currentTime);
    };

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleLoadedData = () => {
      console.log('[TimelineEditorNew] Video loaded successfully');
      setVideoReady(true);
    };
    const handleError = (e: Event) => {
      console.error('[TimelineEditorNew] Video loading error:', e);
      const videoEl = e.target as HTMLVideoElement;
      if (videoEl.error) {
        console.error('[TimelineEditorNew] Video error details:', {
          code: videoEl.error.code,
          message: videoEl.error.message,
        });
      }
    };

    video.addEventListener('timeupdate', handleTimeUpdate);
    video.addEventListener('play', handlePlay);
    video.addEventListener('pause', handlePause);
    video.addEventListener('loadeddata', handleLoadedData);
    video.addEventListener('error', handleError);

    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate);
      video.removeEventListener('play', handlePlay);
      video.removeEventListener('pause', handlePause);
      video.removeEventListener('loadeddata', handleLoadedData);
      video.removeEventListener('error', handleError);
    };
  }, [videoUrl]);

  // Debug logging for videoReady state changes
  useEffect(() => {
    console.log('[TimelineEditorNew] videoReady changed to:', videoReady);
  }, [videoReady]);

  // Debug logging for videoUrl state changes
  useEffect(() => {
    console.log('[TimelineEditorNew] videoUrl state changed to:', videoUrl);
  }, [videoUrl]);

  // Jump to segment when clicked
  const handleSegmentClick = (segment: VideoSegment) => {
    const startTime = segment.start_time ?? 0;
    if (isPreview) {
      // In preview mode, just update currentTime state
      setCurrentTime(startTime);
    } else if (videoRef.current) {
      videoRef.current.currentTime = startTime;
      setCurrentTime(startTime);
    }
  };

  // Handle Export XML
  const handleExport = () => {
    const adjustments: SegmentAdjustment[] = analysis.segments.map(seg => ({
      id: seg.id,
      action: seg.action,
      start_time: seg.start_time,
      end_time: seg.end_time
    }));
    onApply(adjustments, 'reencode');
  };

  // Calculate playhead position percentage
  const totalDuration = analysis.stats.original_duration;
  const playheadPercent = totalDuration > 0 ? (currentTime / totalDuration) * 100 : 0;

  return (
    <div className="h-screen w-full bg-black text-[#EAEAEA] flex flex-col font-inter">
      {/* Top Bar (Minimal) */}
      <div className="h-12 flex items-center justify-between px-6 border-b border-[#1F1F1F]">
        <div className="flex items-center space-x-4">
          <button
            onClick={onCancel}
            className="text-[#EAEAEA]/60 hover:text-[#EAEAEA] transition-colors text-xs"
          >
            ← Back
          </button>
          <h1 className="font-medium text-sm tracking-wide">EasyEdit</h1>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setShowAIPanel(true)}
            className="flex items-center gap-2 bg-blue-600/90 hover:bg-blue-600 text-white px-3 py-1 rounded-md text-xs transition-colors"
          >
            <Sparkles className="h-3 w-3" />
            AI Edit
          </button>
          <button
            onClick={handleExport}
            className="bg-orange-500/90 hover:bg-orange-500 text-white px-3 py-1 rounded-md text-xs"
          >
            Export XML
          </button>
        </div>
      </div>

      {/* Main Area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Transcript (Clean / Flat) */}
        <div className="w-[380px] border-r border-[#1F1F1F] overflow-y-auto px-5 py-4 space-y-2">
          {segments.map((seg) => {
            const active = currentTime >= (seg.start_time ?? 0) && currentTime < (seg.end_time ?? 0);
            return (
              <div
                key={seg.id}
                onClick={() => handleSegmentClick(seg)}
                className={`group cursor-pointer rounded-md px-3 py-2 transition-colors ${
                  active
                    ? "bg-orange-500/10 text-orange-400"
                    : "text-[#EAEAEA]/80 hover:bg-white/5"
                }`}
              >
                <div className="text-[11px] text-[#EAEAEA]/40 mb-0.5">
                  {(seg.start_time ?? 0).toFixed(1)}s – {(seg.end_time ?? 0).toFixed(1)}s
                </div>
                <div className="text-sm leading-snug">{seg.text}</div>
              </div>
            );
          })}
        </div>

        {/* Video Preview (Calm, No Card Feel) */}
        <div className="flex-1 flex items-center justify-center bg-[#080808]">
          <div className="w-[720px] aspect-video bg-[#111] rounded-lg flex items-center justify-center overflow-hidden">
            {isPreview ? (
              <div className="text-center p-8">
                <div className="text-[#EAEAEA]/30 text-sm mb-2">Video Preview</div>
                <div className="text-[#EAEAEA]/20 text-xs">Upload a real video to see playback</div>
              </div>
            ) : videoUrl ? (
              <video
                ref={videoRef}
                src={videoUrl}
                className="w-full h-full object-contain"
                controls
                onLoadStart={() => console.log('[Video] Load started')}
                onCanPlay={() => console.log('[Video] Can play')}
                onLoadedData={() => console.log('[Video] Data loaded')}
                onError={(e) => {
                  console.error('[Video] Playback error:', e.currentTarget.error?.message);
                  console.error('[Video] Error code:', e.currentTarget.error?.code);
                  console.error('[Video] Failed URL:', videoUrl);
                  // Could trigger retry or show user-friendly error message
                }}
              />
            ) : (
              <div className="text-[#EAEAEA]/30 text-sm">No video URL available (jobId: {jobId})</div>
            )}
          </div>
        </div>
      </div>

      {/* Timeline (Ultra Minimal) */}
      <div className="h-24 border-t border-[#1F1F1F] px-6 py-3">
        <div className="relative h-full">
          {/* Playhead */}
          <div
            className="absolute top-0 bottom-0 w-px bg-orange-500 z-10"
            style={{ left: `${playheadPercent}%` }}
          />

          {/* Split Button - Shows at playhead position */}
          {isPlaying && (
            <button
              className="absolute -top-5 -translate-x-1/2 bg-orange-500 text-white text-[11px] px-2.5 py-0.5 rounded-full z-20"
              style={{ left: `${playheadPercent}%` }}
            >
              Split
            </button>
          )}

          {/* Clip Lane - Visual representation of segments */}
          <div className="flex h-full gap-px">
            {segments.map((seg) => {
              // Safe division - avoid divide by zero
              const widthPercent = totalDuration > 0
                ? ((seg.duration ?? 0) / totalDuration) * 100
                : 0;
              return (
                <div
                  key={seg.id}
                  className="bg-[#1A1A1A] hover:bg-[#252525] transition-colors cursor-pointer"
                  style={{ width: `${Math.max(widthPercent, 0.5)}%` }}
                  onClick={() => handleSegmentClick(seg)}
                  title={`${seg.text.substring(0, 50)}...`}
                />
              );
            })}
          </div>
        </div>
      </div>

      {/* AI Prompt Panel (Slide-out) */}
      <AIPromptPanel
        isOpen={showAIPanel}
        onClose={() => setShowAIPanel(false)}
        jobId={jobId}
        onApplyChanges={(changes) => {
          // Convert AI changes to segment adjustments and apply
          if (changes && changes.segments) {
            const adjustments: SegmentAdjustment[] = changes.segments.map((seg: any) => ({
              id: seg.id,
              action: seg.action,
              start_time: seg.start_time,
              end_time: seg.end_time
            }));
            onApply(adjustments, 'reencode');
          }
          setShowAIPanel(false);
        }}
      />
    </div>
  );
}
