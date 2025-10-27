import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Zap } from 'lucide-react';
import WaveformViewer from '../components/godmode/WaveformViewer';
import PromptInput from '../components/godmode/PromptInput';
import TimelineControls from '../components/godmode/TimelineControls';
import * as api from '../services/api';

const GodModePage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const [audioUrl] = useState(`http://localhost:5000/audio/${jobId}`);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [editMessage, setEditMessage] = useState<string | null>(null);
  const [editError, setEditError] = useState<string | null>(null);

  const handlePromptSubmit = async (prompt: string) => {
    if (!jobId) return;

    setIsProcessing(true);
    setEditMessage(null);
    setEditError(null);

    try {
      const result = await api.submitAIEdit(jobId, prompt);
      setEditMessage(result.message || 'Edit completed successfully!');
      console.log('AI Edit result:', result);
    } catch (error: any) {
      console.error('AI Edit failed:', error);
      setEditError(error?.response?.data?.error || 'AI edit failed. Please try again.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleExport = async () => {
    if (!jobId) return;

    setIsExporting(true);
    try {
      // Download the existing processed DRT file
      const blob = await api.downloadResult(jobId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = `godmode_timeline_${jobId.slice(-8)}.drt`;
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
    <div className="min-h-screen bg-background">
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
        {/* Waveform Visualization */}
        {jobId && <WaveformViewer jobId={jobId} audioUrl={audioUrl} />}

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

        {/* AI Prompt Input */}
        <PromptInput onSubmit={handlePromptSubmit} isProcessing={isProcessing} />

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
