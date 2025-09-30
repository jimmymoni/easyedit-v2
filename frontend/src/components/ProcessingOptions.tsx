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
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <h3 className="text-lg font-medium text-gray-900 mb-4">Processing Options</h3>

      <div className="space-y-4">
        {/* Transcription Options */}
        <div className="border-b border-gray-200 pb-4">
          <h4 className="text-sm font-medium text-gray-700 mb-3">Transcription & Analysis</h4>

          <div className="space-y-3">
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={options.enable_transcription ?? true}
                onChange={(e) => handleOptionChange('enable_transcription', e.target.checked)}
                disabled={disabled}
                className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded disabled:opacity-50"
              />
              <span className="ml-2 text-sm text-gray-700">
                Enable AI transcription
                <span className="block text-xs text-gray-500">
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
                className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded disabled:opacity-50"
              />
              <span className="ml-2 text-sm text-gray-700">
                Speaker diarization
                <span className="block text-xs text-gray-500">
                  Identify and separate different speakers
                </span>
              </span>
            </label>
          </div>
        </div>

        {/* Editing Rules */}
        <div className="border-b border-gray-200 pb-4">
          <h4 className="text-sm font-medium text-gray-700 mb-3">Editing Rules</h4>

          <div className="space-y-3">
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={options.remove_silence ?? true}
                onChange={(e) => handleOptionChange('remove_silence', e.target.checked)}
                disabled={disabled}
                className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded disabled:opacity-50"
              />
              <span className="ml-2 text-sm text-gray-700">
                Remove silence segments
                <span className="block text-xs text-gray-500">
                  Automatically detect and remove long pauses
                </span>
              </span>
            </label>
          </div>
        </div>

        {/* Advanced Settings */}
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-3">Advanced Settings</h4>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-700 mb-1">
                Minimum clip length (seconds)
              </label>
              <input
                type="number"
                value={options.min_clip_length ?? 5}
                onChange={(e) => handleOptionChange('min_clip_length', Number(e.target.value))}
                disabled={disabled}
                min="1"
                max="60"
                className="w-24 px-3 py-1 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:opacity-50"
              />
              <p className="text-xs text-gray-500 mt-1">
                Clips shorter than this will be merged or removed
              </p>
            </div>

            <div>
              <label className="block text-sm text-gray-700 mb-1">
                Silence threshold (dB)
              </label>
              <input
                type="number"
                value={options.silence_threshold_db ?? -40}
                onChange={(e) => handleOptionChange('silence_threshold_db', Number(e.target.value))}
                disabled={disabled}
                min="-60"
                max="-10"
                className="w-24 px-3 py-1 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:opacity-50"
              />
              <p className="text-xs text-gray-500 mt-1">
                Audio below this level is considered silence
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Processing Summary */}
      <div className="mt-6 p-3 bg-blue-50 rounded-md">
        <p className="text-sm text-blue-800">
          <strong>Selected options:</strong>
          {options.enable_transcription && ' AI Transcription'}
          {options.enable_speaker_diarization && ' + Speaker Detection'}
          {options.remove_silence && ' + Silence Removal'}
        </p>
        <p className="text-xs text-blue-600 mt-1">
          Processing time varies based on audio length and selected options
        </p>
      </div>
    </div>
  );
};

export default ProcessingOptions;