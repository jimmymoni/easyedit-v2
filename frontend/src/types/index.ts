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
  status: 'uploaded' | 'analyzing' | 'analyzed' | 'processing' | 'completed' | 'failed';
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
}

export interface SegmentAdjustment {
  id: string;
  action: 'keep' | 'remove';
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
}