import React, { useState } from 'react';
import { VideoAnalysis, SegmentAdjustment } from '../../types';
import VideoTimelineEditor from './VideoTimelineEditor';
import AIPromptPanel from './AIPromptPanel';
import { MessageSquare } from 'lucide-react';

interface VideoEditorWorkspaceProps {
  analysis: VideoAnalysis;
  audioUrl?: string;
  jobId: string;
  onApply: (adjustments: SegmentAdjustment[], encodingMethod: 'reencode' | 'lossless') => void;
  onCancel: () => void;
}

export default function VideoEditorWorkspace({
  analysis,
  audioUrl,
  jobId,
  onApply,
  onCancel
}: VideoEditorWorkspaceProps) {

  const [aiPanelOpen, setAiPanelOpen] = useState(false);

  // Handle AI-suggested changes
  const handleApplyAIChanges = async (changes: any) => {
    // TODO: Convert AI changes to segment adjustments
    // For now, just log the changes
    console.log('AI changes:', changes);

    // In Phase 4, we'll implement the conversion logic:
    // const adjustments = convertAIChangesToAdjustments(changes);
    // onApply(adjustments, 'reencode');
  };

  return (
    <div className="relative">
      {/* Main Editor */}
      <div className="space-y-6">
        <VideoTimelineEditor
          analysis={analysis}
          audioUrl={audioUrl}
          jobId={jobId}
          onApply={onApply}
          onCancel={onCancel}
        />
      </div>

      {/* AI Prompt Button */}
      <button
        onClick={() => setAiPanelOpen(!aiPanelOpen)}
        className="fixed bottom-8 right-8 bg-primary text-primary-foreground px-4 py-3 rounded-full shadow-lg hover:bg-primary/90 transition-all flex items-center space-x-2 z-30 group"
        title="Open AI Editor"
      >
        <MessageSquare className="h-5 w-5 group-hover:scale-110 transition-transform" />
        <span className="font-medium">AI Editor</span>
        <span className="text-xs bg-primary-foreground/20 px-2 py-0.5 rounded-full">Beta</span>
      </button>

      {/* AI Prompt Panel */}
      <AIPromptPanel
        isOpen={aiPanelOpen}
        onClose={() => setAiPanelOpen(false)}
        jobId={jobId}
        onApplyChanges={handleApplyAIChanges}
      />
    </div>
  );
}
