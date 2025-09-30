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