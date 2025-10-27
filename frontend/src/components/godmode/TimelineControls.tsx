import React from 'react';
import { Undo, Redo, Play, Download } from 'lucide-react';

interface TimelineControlsProps {
  onUndo?: () => void;
  onRedo?: () => void;
  onPreview?: () => void;
  onExport: () => void;
  canUndo?: boolean;
  canRedo?: boolean;
  isExporting?: boolean;
}

const TimelineControls: React.FC<TimelineControlsProps> = ({
  onUndo,
  onRedo,
  onPreview,
  onExport,
  canUndo = false,
  canRedo = false,
  isExporting = false,
}) => {
  return (
    <div className="bg-[#181818] border border-[#2A2A2A] rounded-xl shadow-lg p-6">
      <h3 className="text-lg font-semibold text-[#EAEAEA] mb-4">
        Timeline Controls
      </h3>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {/* Undo */}
        <button
          onClick={onUndo}
          disabled={!canUndo}
          className="flex items-center justify-center space-x-2 bg-[#0A0A0A] border border-[#2A2A2A] hover:border-[#FF6B35] disabled:opacity-30 disabled:hover:border-[#2A2A2A] text-[#EAEAEA] px-4 py-3 rounded-lg font-medium transition-all"
        >
          <Undo className="h-4 w-4" />
          <span className="hidden sm:inline">Undo</span>
        </button>

        {/* Redo */}
        <button
          onClick={onRedo}
          disabled={!canRedo}
          className="flex items-center justify-center space-x-2 bg-[#0A0A0A] border border-[#2A2A2A] hover:border-[#FF6B35] disabled:opacity-30 disabled:hover:border-[#2A2A2A] text-[#EAEAEA] px-4 py-3 rounded-lg font-medium transition-all"
        >
          <Redo className="h-4 w-4" />
          <span className="hidden sm:inline">Redo</span>
        </button>

        {/* Preview */}
        <button
          onClick={onPreview}
          disabled={true} // Coming soon
          className="flex items-center justify-center space-x-2 bg-[#0A0A0A] border border-[#2A2A2A] hover:border-[#FF6B35] disabled:opacity-30 disabled:hover:border-[#2A2A2A] text-[#EAEAEA] px-4 py-3 rounded-lg font-medium transition-all"
        >
          <Play className="h-4 w-4" />
          <span className="hidden sm:inline">Preview</span>
        </button>

        {/* Export */}
        <button
          onClick={onExport}
          disabled={isExporting}
          className="flex items-center justify-center space-x-2 bg-[#FF6B35] hover:bg-[#FF6B35]/90 disabled:bg-[#2A2A2A] disabled:text-[#EAEAEA]/30 text-white px-4 py-3 rounded-lg font-medium transition-colors"
        >
          <Download className="h-4 w-4" />
          <span className="hidden sm:inline">
            {isExporting ? 'Exporting...' : 'Export DRT'}
          </span>
        </button>
      </div>
    </div>
  );
};

export default TimelineControls;
