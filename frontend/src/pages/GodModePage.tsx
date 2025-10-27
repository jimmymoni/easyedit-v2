import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Zap } from 'lucide-react';

const GodModePage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();

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
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="bg-[#181818] border border-[#2A2A2A] rounded-xl shadow-lg p-12 text-center">
          <div className="mb-6">
            <span className="text-6xl">⚡</span>
          </div>
          <h2 className="text-3xl font-bold text-[#EAEAEA] mb-4">
            God Mode - Coming Soon
          </h2>
          <p className="text-[#EAEAEA]/70 mb-2">
            Job ID: <span className="font-mono text-[#FF6B35]">{jobId}</span>
          </p>
          <p className="text-[#EAEAEA]/70 mb-8 max-w-2xl mx-auto">
            This powerful AI-driven timeline editor will let you make intelligent edits
            through natural language prompts. Stay tuned!
          </p>
          <button
            onClick={() => navigate('/')}
            className="bg-[#FF6B35] hover:bg-[#FF6B35]/90 text-white px-6 py-3 rounded-lg font-medium transition-colors"
          >
            Back to Main Page
          </button>
        </div>

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
