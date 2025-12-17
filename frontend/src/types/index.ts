export interface ProcessingJob {
  job_id: string;
  status: 'uploaded' | 'processing' | 'completed' | 'failed';
  progress: number;
  message: string;
  created_at: string;
  stats?: ProcessingStats;
  transcription_available?: boolean;
}

export interface ProcessingStats {
  original_duration: number;
  edited_duration: number;
  duration_reduction: number;
  compression_ratio: number;
  original_clips: number;
  edited_clips: number;
  clips_change: number;
  tracks_processed: number;
  markers_added: number;
}

export interface ProcessingOptions {
  enable_transcription?: boolean;
  enable_speaker_diarization?: boolean;
  remove_silence?: boolean;
  min_clip_length?: number;
  silence_threshold_db?: number;
}

export interface UploadResponse {
  job_id: string;
  message: string;
  audio_filename: string;
  timeline_filename: string;
}

export interface ProcessingResponse {
  job_id: string;
  status: string;
  stats: ProcessingStats;
  transcription_available: boolean;
  message: string;
}

export interface FileWithPreview extends File {
  preview?: string;
}

export interface TimelineInsights {
  audio_quality: {
    dynamic_range: number;
    average_volume: number;
    speech_to_silence_ratio: number;
  };
  editing_effectiveness: {
    silence_removed_count: number;
    cuts_applied: number;
    clips_created: number;
    time_saved_minutes: number;
  };
  transcription?: {
    speakers_detected: number;
    words_transcribed: number;
    confidence_score: number;
    speaker_changes: number;
  };
}

// God Mode - AI Edit Types
export interface AIEditRequest {
  job_id: string;
  prompt: string;
}

export interface AIEditResponse {
  job_id: string;
  success: boolean;
  operation: string;
  message: string;
  changes_made: Record<string, any>;
  prompt: string;
}

// God Mode - Knowledge Base Types
export interface Feature {
  id: string;
  name: string;
  description: string;
  start_time: number;
  end_time: number;
  duration: number;
  key_points?: string[];
  confidence?: number;
  user_edited: boolean;
}

export interface Chapter {
  title: string;
  start: number;
  end: number;
}

export interface KeyMoment {
  description: string;
  timestamp: number;
  engagement: 'high' | 'medium' | 'low';
}

export interface ContentAnalysis {
  content_type: string;
  main_topic: string;
  features_discussed: Feature[];
  chapters: Chapter[];
  key_moments: KeyMoment[];
  metadata: {
    analyzed_at: string;
    analyzer_version: string;
    user_modified: boolean;
    last_edited?: string;
    llm_model?: string;
    analysis_method?: string;
    analysis_error?: string;
  };
}

export interface KnowledgeBaseResponse {
  job_id: string;
  content_analysis: ContentAnalysis;
}

export interface KnowledgeBaseUpdateRequest {
  content_analysis: ContentAnalysis;
}

// Video Editor Types
export interface VideoInfo {
  duration: number;
  size_mb: number;
  width: number;
  height: number;
  fps: number;
  codec: string;
}

export interface VideoSegment {
  id: string;
  start_time: number;
  end_time: number;
  duration: number;
  text: string;
  speaker?: string;
  action: 'keep' | 'remove';
  reason: string;
  confidence: number;
  has_repetition_marker?: boolean;
  has_false_start?: boolean;
  filler_density?: number;
}

export interface VideoAnalysisStats {
  total_segments: number;
  segments_to_keep: number;
  segments_to_remove: number;
  original_duration: number;
  edited_duration: number;
  time_saved: number;
  compression_ratio: number;
}

export interface DetectedPatterns {
  repetition_markers: number;
  false_starts: number;
  filler_heavy: number;
}

export interface VideoAnalysis {
  segments: VideoSegment[];
  stats: VideoAnalysisStats;
  detected_patterns: DetectedPatterns;
}

export interface VideoUploadResponse {
  job_id: string;
  message: string;
  video_filename: string;
  video_info: VideoInfo;
}

export interface VideoJob {
  job_id: string;
  type: 'video_editing';
  status: 'uploaded' | 'analyzing' | 'analyzed' | 'processing' | 'completed' | 'failed' | 'transcoding';
  progress: number;
  message: string;
  created_at: number;
  video_file?: string;
  audio_file?: string;
  output_video_file?: string;
  output_xml_file?: string;
  video_info?: VideoInfo;
  transcription?: any;
  analysis?: VideoAnalysis;
  proxy_status?: 'pending' | 'transcoding' | 'ready' | 'failed';
  proxy_url?: string;
  proxy_progress?: number;
  estimated_time_remaining?: number;
}

// Timeline Editor Types
export interface TimelineClip {
  id: string;
  startTime: number;  // Timeline position (seconds)
  endTime: number;    // Timeline position (seconds)
  duration: number;   // Clip duration (seconds)
  sourceStart: number; // Original video position (seconds)
  sourceEnd: number;   // Original video position (seconds)
  text: string;        // Transcript text
  speaker?: string;    // Speaker identifier
  type: 'keep' | 'remove' | 'transition';
  color?: string;      // Visual color for clip
  metadata?: {
    hasRepetition?: boolean;
    hasFalseStart?: boolean;
    fillerDensity?: number;
    confidence?: number;
  };
}

export interface TimelineState {
  clips: TimelineClip[];
  playhead: number;           // Current playback position (seconds)
  zoom: number;               // Pixels per second for timeline scale
  selectedClipId: string | null;
  isPlaying: boolean;
  totalDuration: number;      // Total timeline duration (seconds)
  snapToGrid: boolean;        // Enable snapping to grid
  gridSize: number;           // Grid size in seconds (0.5 or 1.0)
}

export interface TimelineTrackProps {
  clips: TimelineClip[];
  zoom: number;
  playhead: number;
  selectedClipId: string | null;
  onClipSelect: (clipId: string) => void;
  onClipResize: (clipId: string, newStart: number, newEnd: number) => void;
  onClipMove: (clipId: string, newPosition: number) => void;
}

export interface WaveformPeaks {
  data: number[];       // Waveform peak data
  length: number;       // Total samples
  bits: number;         // Bits per sample
  sample_rate: number;  // Audio sample rate
}

export interface SegmentAdjustment {
  id: string;
  action: 'keep' | 'remove';
  start_time?: number;
  end_time?: number;
}

export interface SystemCheckResponse {
  status: 'ready' | 'partial' | 'missing';
  ffmpeg_available: boolean;
  ffprobe_available: boolean;
  message: string;
  platform: string;
  install_instructions: {
    windows: string;
    macos: string;
    linux: string;
  };
  install_url: string;
  ffmpeg_version?: string;
  cloud_processing: boolean;
  replicate_configured: boolean;
  mode?: 'cloud' | 'local';
}

// Video AI Editor Types
export interface VideoAIChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  preview?: VideoAIPreviewResult;
  options?: VideoAIEditOption[];
}

export interface VideoAIPreviewResult {
  operation: string;
  description: string;
  segments_affected: number;
  time_saved: number;
  new_duration: number;
  preview_data?: any;
  segments?: VideoSegment[];
  cut_points?: Array<{ timestamp: number; reason: string }>;
}

export interface VideoAIEditOption {
  label: string;
  value: string;
  description?: string;
}

export interface VideoAIChatRequest {
  job_id: string;
  message: string;
}

export interface VideoAIChatResponse {
  intent: string;
  confidence: number;
  message: string;
  preview: VideoAIPreviewResult;
  needs_confirmation: boolean;
}

export interface VideoAIApplyRequest {
  job_id: string;
  operation: string;
  params?: Record<string, any>;
}

export interface VideoAIApplyResponse {
  success: boolean;
  updated_clips: TimelineClip[];
  stats: {
    segments_affected: number;
    time_saved: number;
    new_duration: number;
  };
}

// Video Player Types (Phase 2)
export interface VideoPlayerState {
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  isMuted: boolean;
  playbackRate: number;
  isFullscreen: boolean;
  buffered: number;
}

export interface VideoProxyStatus {
  job_id: string;
  proxy_status: 'pending' | 'transcoding' | 'ready' | 'failed';
  proxy_url?: string;
  proxy_progress?: number;
  estimated_time_remaining?: number;
  message?: string;
}

// Waveform & Timeline Types (Phase 2.2)

// Waveform Data (Backend API Response from GET /waveform/<job_id>)
export interface WaveformData {
  job_id: string;
  peaks: number[];          // Normalized peak values [0, 1]
  sample_rate: number;      // Audio sample rate (e.g., 44100)
  duration: number;         // Audio duration in seconds
  channels: number;         // Number of audio channels (1 or 2)
  samples: number;          // Number of peak samples (e.g., 1500)
  created_at: string;       // ISO 8601 timestamp
}

// Timeline Configuration
export interface TimelineConfig {
  zoom: number;             // Pixels per second (50-500)
  offset: number;           // Horizontal scroll offset (seconds)
  minZoom: number;          // Minimum zoom level (e.g., 20)
  maxZoom: number;          // Maximum zoom level (e.g., 500)
  gridSize: number;         // Grid snap size (seconds, e.g., 0.5)
  snapToGrid: boolean;      // Enable grid snapping
}

// Timeline State (for useTimeline hook)
export interface TimelineState extends TimelineConfig {
  playheadPosition: number; // Current playback time (seconds)
  duration: number;         // Total video duration (seconds)
  isDragging: boolean;      // Is playhead being dragged
  isScrolling: boolean;     // Is timeline being panned
}

// Waveform Fetch State (for useWaveform hook)
export interface WaveformState {
  data: WaveformData | null;
  loading: boolean;
  error: string | null;
}