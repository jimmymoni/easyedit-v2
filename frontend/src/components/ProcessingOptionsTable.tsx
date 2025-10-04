import React from 'react';
import { ProcessingOptions as ProcessingOptionsType } from '../types';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Switch } from '@/components/ui/switch';
import { Slider } from '@/components/ui/slider';
import { Label } from '@/components/ui/label';

interface ProcessingOptionsProps {
  options: ProcessingOptionsType;
  onOptionsChange: (options: ProcessingOptionsType) => void;
  disabled?: boolean;
}

const ProcessingOptionsTable: React.FC<ProcessingOptionsProps> = ({
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
    <div className="bg-card rounded-xl border border-border/80 shadow-sm hover:shadow-md transition-shadow duration-200 overflow-hidden">
      <div className="px-6 py-4 border-b border-border/60">
        <h3 className="text-lg font-semibold text-foreground tracking-tight">Processing Options</h3>
        <p className="text-sm text-muted-foreground mt-1">Configure AI-powered editing settings</p>
      </div>

      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent border-border/60">
              <TableHead className="w-[40%] font-semibold">Feature</TableHead>
              <TableHead className="w-[15%] text-center font-semibold">Enable</TableHead>
              <TableHead className="w-[45%] font-semibold">Configuration</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {/* AI Transcription Row */}
            <TableRow className="hover:bg-accent/30">
              <TableCell>
                <div>
                  <div className="font-medium text-foreground">AI Transcription</div>
                  <div className="text-sm text-muted-foreground mt-0.5">
                    Speech-to-text analysis using Soniox API
                  </div>
                </div>
              </TableCell>
              <TableCell className="text-center">
                <div className="flex justify-center">
                  <Switch
                    checked={options.enable_transcription ?? true}
                    onCheckedChange={(checked) => handleOptionChange('enable_transcription', checked)}
                    disabled={disabled}
                  />
                </div>
              </TableCell>
              <TableCell className="text-sm text-muted-foreground">
                Required for speaker detection and filler word removal
              </TableCell>
            </TableRow>

            {/* Speaker Diarization Row */}
            <TableRow className="hover:bg-accent/30">
              <TableCell>
                <div>
                  <div className="font-medium text-foreground">Speaker Diarization</div>
                  <div className="text-sm text-muted-foreground mt-0.5">
                    Identify and separate different speakers
                  </div>
                </div>
              </TableCell>
              <TableCell className="text-center">
                <div className="flex justify-center">
                  <Switch
                    checked={options.enable_speaker_diarization ?? true}
                    onCheckedChange={(checked) => handleOptionChange('enable_speaker_diarization', checked)}
                    disabled={disabled || !options.enable_transcription}
                  />
                </div>
              </TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {!options.enable_transcription ? 'Requires AI Transcription' : 'Automatically detect speaker changes'}
              </TableCell>
            </TableRow>

            {/* Silence Removal Row */}
            <TableRow className="hover:bg-accent/30">
              <TableCell>
                <div>
                  <div className="font-medium text-foreground">Silence Removal</div>
                  <div className="text-sm text-muted-foreground mt-0.5">
                    Automatically detect and remove long pauses
                  </div>
                </div>
              </TableCell>
              <TableCell className="text-center">
                <div className="flex justify-center">
                  <Switch
                    checked={options.remove_silence ?? true}
                    onCheckedChange={(checked) => handleOptionChange('remove_silence', checked)}
                    disabled={disabled}
                  />
                </div>
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-4">
                  <Label htmlFor="silence-threshold" className="text-sm text-muted-foreground whitespace-nowrap min-w-[140px]">
                    Threshold: {options.silence_threshold_db ?? -40} dB
                  </Label>
                  <Slider
                    id="silence-threshold"
                    value={[options.silence_threshold_db ?? -40]}
                    onValueChange={(value) => handleOptionChange('silence_threshold_db', value[0])}
                    min={-60}
                    max={-10}
                    step={1}
                    disabled={disabled || !options.remove_silence}
                    className="flex-1 max-w-[200px]"
                  />
                </div>
              </TableCell>
            </TableRow>

            {/* Minimum Clip Length Row */}
            <TableRow className="hover:bg-accent/30 border-0">
              <TableCell>
                <div>
                  <div className="font-medium text-foreground">Minimum Clip Length</div>
                  <div className="text-sm text-muted-foreground mt-0.5">
                    Merge or remove clips shorter than threshold
                  </div>
                </div>
              </TableCell>
              <TableCell className="text-center">
                <div className="text-sm font-mono text-muted-foreground">
                  {options.min_clip_length ?? 5}s
                </div>
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-4">
                  <Label htmlFor="min-clip-length" className="text-sm text-muted-foreground whitespace-nowrap min-w-[140px]">
                    Length: {options.min_clip_length ?? 5} seconds
                  </Label>
                  <Slider
                    id="min-clip-length"
                    value={[options.min_clip_length ?? 5]}
                    onValueChange={(value) => handleOptionChange('min_clip_length', value[0])}
                    min={1}
                    max={60}
                    step={1}
                    disabled={disabled}
                    className="flex-1 max-w-[200px]"
                  />
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>

      {/* Processing Summary Footer */}
      <div className="px-6 py-4 bg-primary/5 border-t border-border/60">
        <div className="flex items-start gap-3">
          <div className="flex-1">
            <p className="text-sm font-medium text-foreground">
              Active Features:
              <span className="ml-2 text-primary">
                {[
                  options.enable_transcription && 'AI Transcription',
                  options.enable_speaker_diarization && 'Speaker Detection',
                  options.remove_silence && 'Silence Removal'
                ].filter(Boolean).join(' • ')}
              </span>
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Processing time varies based on audio length and selected features
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProcessingOptionsTable;
