import React, { useState, useRef, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Zap, AudioWaveform, FileText } from 'lucide-react';
import EnhancedWaveformViewer, { WaveformViewerHandle } from '../components/godmode/EnhancedWaveformViewer';
import TranscriptionViewer from '../components/godmode/TranscriptionViewer';
import ChatInterface from '../components/godmode/ChatInterface';
import TimelineControls from '../components/godmode/TimelineControls';
import KnowledgeBaseEditor from '../components/godmode/KnowledgeBaseEditor';
import { ContentAnalysis } from '../types';
import * as api from '../services/api';

type TabType = 'waveform' | 'transcription';

const GodModePage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const [audioUrl] = useState(`http://localhost:5000/audio/${jobId}`);
  const [activeTab, setActiveTab] = useState<TabType>('waveform');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [editMessage, setEditMessage] = useState<string | null>(null);
  const [editError, setEditError] = useState<string | null>(null);
  const [currentPlaybackTime, setCurrentPlaybackTime] = useState(0); // NEW: Track playback position for karaoke highlighting
  const [autoSwitchToEdited, setAutoSwitchToEdited] = useState(false); // Auto-switch waveform after AI edit
  const [isEditedMode, setIsEditedMode] = useState(false); // NEW: Track whether viewing edited audio
  const [contentAnalysis, setContentAnalysis] = useState<ContentAnalysis | null>(null);
  const [kbLoading, setKbLoading] = useState(true);
  const waveformSeekRef = useRef<((time: number) => void) | null>(null);
  const waveformViewerRef = useRef<WaveformViewerHandle>(null);

  // Load knowledge base on mount
  useEffect(() => {
    const loadKnowledgeBase = async () => {
      if (!jobId) return;

      try {
        setKbLoading(true);
        const response = await api.getKnowledgeBase(jobId);
        if (response.content_analysis) {
          setContentAnalysis(response.content_analysis);
        }
      } catch (error) {
        console.error('Failed to load knowledge base:', error);
        // Knowledge base is optional - don't show error to user
      } finally {
        setKbLoading(false);
      }
    };

    loadKnowledgeBase();
  }, [jobId]);

  const handleKnowledgeBaseUpdate = (updated: ContentAnalysis) => {
    setContentAnalysis(updated);
  };

  const handleEditExecuted = (result: any) => {
    setEditMessage(result.message || 'Edit completed successfully!');
    console.log('AI Edit result:', result);

    // Trigger auto-switch to edited view
    setAutoSwitchToEdited(true);

    // Force reload comparison data after AI edit completes
    setTimeout(() => {
      waveformViewerRef.current?.reloadComparison();
    }, 500);

    // Switch to waveform tab to see the changes
    setActiveTab('waveform');
  };

  const handleExport = async () => {
    if (!jobId) return;

    setIsExporting(true);
    try {
      // Download the existing processed XML file
      const blob = await api.downloadResult(jobId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = `godmode_timeline_${jobId.slice(-8)}.xml`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Export failed:', error);
      alert('Export failed. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#000000]">
      {/* Header */}
      <header className="bg-[#181818] border-b border-[#2A2A2A] shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-3">
              <button
                onClick={() => navigate('/')}
                className="text-[#EAEAEA] hover:text-[#FF6B35] transition-colors"
                aria-label="Back to main page"
              >
                <ArrowLeft className="h-6 w-6" />
              </button>
              <Zap className="h-7 w-7 text-[#FF6B35]" />
              <div>
                <h1 className="text-xl font-bold text-[#EAEAEA] tracking-tight">
                  EASYEDIT v2 : GOD MODE
                </h1>
                <p className="text-xs text-[#EAEAEA]/70 font-medium">
                  AI-Powered Interactive Timeline Editor
                </p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Tab Navigation */}
        <div className="flex items-center space-x-2 border-b border-[#2A2A2A]">
          <button
            onClick={() => setActiveTab('waveform')}
            className={`flex items-center space-x-2 px-4 py-3 font-medium transition-colors ${
              activeTab === 'waveform'
                ? 'text-[#FF6B35] border-b-2 border-[#FF6B35]'
                : 'text-[#EAEAEA]/70 hover:text-[#EAEAEA]'
            }`}
          >
            <AudioWaveform className="h-5 w-5" />
            <span>Waveform</span>
          </button>
          <button
            onClick={() => setActiveTab('transcription')}
            className={`flex items-center space-x-2 px-4 py-3 font-medium transition-colors ${
              activeTab === 'transcription'
                ? 'text-[#FF6B35] border-b-2 border-[#FF6B35]'
                : 'text-[#EAEAEA]/70 hover:text-[#EAEAEA]'
            }`}
          >
            <FileText className="h-5 w-5" />
            <span>Transcription</span>
          </button>
        </div>

        {/* Tab Content */}
        {jobId && (
          <>
            <div style={{ display: activeTab === 'waveform' ? 'block' : 'none' }}>
              <EnhancedWaveformViewer
                ref={waveformViewerRef}
                jobId={jobId}
                audioUrl={audioUrl}
                onSeekReady={(seekFn) => {
                  waveformSeekRef.current = seekFn;
                }}
                onTimeUpdate={(time) => {
                  setCurrentPlaybackTime(time);
                }}
                autoSwitchToEdited={autoSwitchToEdited}
                onViewModeChange={(mode) => {
                  setIsEditedMode(mode === 'edited');
                }}
              />
            </div>
            <div style={{ display: activeTab === 'transcription' ? 'block' : 'none' }}>
              <TranscriptionViewer
                jobId={jobId}
                currentPlaybackTime={currentPlaybackTime}
                isEditedMode={isEditedMode}
                onSeekAudio={(timestamp) => {
                  setActiveTab('waveform');
                  if (waveformSeekRef.current) {
                    waveformSeekRef.current(timestamp);
                  }
                }}
              />
            </div>
          </>
        )}

        {/* Edit Result Messages */}
        {editMessage && (
          <div className="bg-[#181818] border border-[#FF6B35] rounded-xl p-4">
            <p className="text-[#FF6B35] font-medium">✓ {editMessage}</p>
          </div>
        )}
        {editError && (
          <div className="bg-[#181818] border border-red-400 rounded-xl p-4">
            <p className="text-red-400 font-medium">✗ {editError}</p>
          </div>
        )}

        {/* Knowledge Base Editor */}
        {jobId && !kbLoading && contentAnalysis && (
          <KnowledgeBaseEditor
            jobId={jobId}
            contentAnalysis={contentAnalysis}
            onUpdate={handleKnowledgeBaseUpdate}
          />
        )}

        {/* Chat with God */}
        {jobId && <ChatInterface jobId={jobId} onEditExecuted={handleEditExecuted} contentAnalysis={contentAnalysis} />}

        {/* Timeline Controls */}
        <TimelineControls onExport={handleExport} isExporting={isExporting} />

        {/* Feature Preview */}
        <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-[#181818] border border-[#2A2A2A] rounded-xl p-6">
            <div className="text-3xl mb-3">🎵</div>
            <h3 className="text-lg font-semibold text-[#EAEAEA] mb-2">
              Waveform Visualization
            </h3>
            <p className="text-sm text-[#EAEAEA]/70">
              See your audio timeline with clip markers and speech segments
            </p>
          </div>

          <div className="bg-[#181818] border border-[#2A2A2A] rounded-xl p-6">
            <div className="text-3xl mb-3">💬</div>
            <h3 className="text-lg font-semibold text-[#EAEAEA] mb-2">
              Natural Language Editing
            </h3>
            <p className="text-sm text-[#EAEAEA]/70">
              Make edits by describing what you want in plain English
            </p>
          </div>

          <div className="bg-[#181818] border border-[#2A2A2A] rounded-xl p-6">
            <div className="text-3xl mb-3">🎬</div>
            <h3 className="text-lg font-semibold text-[#EAEAEA] mb-2">
              Instant Preview
            </h3>
            <p className="text-sm text-[#EAEAEA]/70">
              Preview and export your AI-edited timeline instantly
            </p>
          </div>
        </div>
      </main>
    </div>
  );
};

export default GodModePage;
