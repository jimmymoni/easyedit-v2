import React from 'react';
import { ProcessingOptions as ProcessingOptionsType } from '../types';

interface ProcessingOptionsProps {
  options: ProcessingOptionsType;
  onOptionsChange: (options: ProcessingOptionsType) => void;
  disabled?: boolean;
}

const ProcessingOptions: React.FC<ProcessingOptionsProps> = ({
  options,
  onOptionsChange,
  disabled = false,
}) => {
  const handleOptionChange = (key: keyof ProcessingOptionsType, value: any) => {
    onOptionsChange({
      ...options,
      [key]: value,
    });
  };

  return (
    <div className="bg-card rounded-xl border border-border/80 shadow-sm hover:shadow-md transition-shadow duration-200 p-6 lg:p-8">
      <h3 className="text-lg font-semibold text-foreground mb-4 tracking-tight">Processing Options</h3>

      <div className="space-y-4">
        {/* Transcription Options */}
        <div className="border-b border-border pb-4">
          <h4 className="text-sm font-medium text-foreground mb-3">Transcription & Analysis</h4>

          <div className="space-y-3">
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={options.enable_transcription ?? true}
                onChange={(e) => handleOptionChange('enable_transcription', e.target.checked)}
                disabled={disabled}
                className="h-4 w-4 text-primary focus:ring-primary border-border rounded disabled:opacity-50"
              />
              <span className="ml-2 text-sm text-foreground">
                Enable AI transcription
                <span className="block text-xs text-muted-foreground">
                  Uses Soniox API for speech-to-text analysis
                </span>
              </span>
            </label>

            <label className="flex items-center">
              <input
                type="checkbox"
                checked={options.enable_speaker_diarization ?? true}
                onChange={(e) => handleOptionChange('enable_speaker_diarization', e.target.checked)}
                disabled={disabled || !options.enable_transcription}
                className="h-4 w-4 text-primary focus:ring-primary border-border rounded disabled:opacity-50"
              />
              <span className="ml-2 text-sm text-foreground">
                Speaker diarization
                <span className="block text-xs text-muted-foreground">
                  Identify and separate different speakers
                </span>
              </span>
            </label>
          </div>
        </div>

        {/* Editing Rules */}
        <div className="border-b border-border pb-4">
          <h4 className="text-sm font-medium text-foreground mb-3">Editing Rules</h4>

          <div className="space-y-3">
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={options.remove_silence ?? true}
                onChange={(e) => handleOptionChange('remove_silence', e.target.checked)}
                disabled={disabled}
                className="h-4 w-4 text-primary focus:ring-primary border-border rounded disabled:opacity-50"
              />
              <span className="ml-2 text-sm text-foreground">
                Remove silence segments
                <span className="block text-xs text-muted-foreground">
                  Automatically detect and remove long pauses
                </span>
              </span>
            </label>
          </div>
        </div>

        {/* Advanced Settings */}
        <div>
          <h4 className="text-sm font-medium text-foreground mb-3">Advanced Settings</h4>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-foreground mb-1">
                Minimum clip length (seconds)
              </label>
              <input
                type="number"
                value={options.min_clip_length ?? 5}
                onChange={(e) => handleOptionChange('min_clip_length', Number(e.target.value))}
                disabled={disabled}
                min="1"
                max="60"
                className="w-24 px-3 py-1.5 bg-background border border-border rounded-md text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Clips shorter than this will be merged or removed
              </p>
            </div>

            <div>
              <label className="block text-sm text-foreground mb-1">
                Silence threshold (dB)
              </label>
              <input
                type="number"
                value={options.silence_threshold_db ?? -40}
                onChange={(e) => handleOptionChange('silence_threshold_db', Number(e.target.value))}
                disabled={disabled}
                min="-60"
                max="-10"
                className="w-24 px-3 py-1.5 bg-background border border-border rounded-md text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Audio below this level is considered silence
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Processing Summary */}
      <div className="mt-6 p-4 bg-primary/5 border border-primary/10 rounded-lg">
        <p className="text-sm text-foreground">
          <strong className="font-semibold">Selected options:</strong>
          {options.enable_transcription && ' AI Transcription'}
          {options.enable_speaker_diarization && ' + Speaker Detection'}
          {options.remove_silence && ' + Silence Removal'}
        </p>
        <p className="text-xs text-muted-foreground mt-1.5">
          Processing time varies based on audio length and selected options
        </p>
      </div>
    </div>
  );
};

export default ProcessingOptions;