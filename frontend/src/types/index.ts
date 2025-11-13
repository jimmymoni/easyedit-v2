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
  drt_filename: string;
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