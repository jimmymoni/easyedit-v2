import React, { useState, useEffect } from 'react';
import { Film, Github, ExternalLink, Shield, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import AuthButton from '../components/AuthButton';
import { useAuth } from '../contexts/AuthContext';
import * as api from '../services/api';
import { VideoJob, VideoAnalysis, SystemCheckResponse } from '../types';

// Import video components
import VideoUploadZone from '../components/video/VideoUploadZone';
import VideoAnalysisProgress from '../components/video/VideoAnalysisProgress';
import VideoSegmentPreview from '../components/video/VideoSegmentPreview';
import FFmpegWarningBanner from '../components/video/FFmpegWarningBanner';
import FFmpegErrorDisplay from '../components/video/FFmpegErrorDisplay';

type WorkflowStep = 'upload' | 'analyzing' | 'preview' | 'processing' | 'complete';

const VideoEditorPage: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  // Workflow state
  const [step, setStep] = useState<WorkflowStep>('upload');
  const [jobId, setJobId] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<VideoAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Job polling
  const [isPolling, setIsPolling] = useState(false);
  const [currentJob, setCurrentJob] = useState<VideoJob | null>(null);

  // System check state
  const [systemCheck, setSystemCheck] = useState<SystemCheckResponse | null>(null);
  const [isCheckingSystem, setIsCheckingSystem] = useState(false);
  const [showFFmpegWarning, setShowFFmpegWarning] = useState(false);

  // Poll job status when in analyzing or processing state
  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    if (jobId && (step === 'analyzing' || step === 'processing')) {
      setIsPolling(true);

      // Immediate check
      checkJobStatus();

      // Then poll every 2 seconds
      intervalId = setInterval(checkJobStatus, 2000);
    }

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
      setIsPolling(false);
    };
  }, [jobId, step]);

  const checkJobStatus = async () => {
    if (!jobId) return;

    try {
      if (step === 'analyzing') {
        // Check video analysis status
        const response = await api.getVideoAnalysis(jobId);

        if (response.status === 'analyzed') {
          // Analysis complete, move to preview
          setAnalysis(response.analysis);
          setStep('preview');
          setIsPolling(false);
        } else if (response.status === 'failed') {
          setError(response.message || 'Video analysis failed');
          setStep('upload');
          setIsPolling(false);
        }
      } else if (step === 'processing') {
        // Check video cutting status
        const job = await api.getJobStatus(jobId) as unknown as VideoJob;
        setCurrentJob(job);

        if (job.status === 'completed') {
          setStep('complete');
          setIsPolling(false);
        } else if (job.status === 'failed') {
          setError(job.message || 'Video processing failed');
          setStep('preview');
          setIsPolling(false);
        }
      }
    } catch (err: any) {
      console.error('Error checking job status:', err);
      setError(err.response?.data?.error || 'Failed to check job status');
    }
  };

  const handleUploadComplete = (uploadJobId: string) => {
    setJobId(uploadJobId);
    setStep('analyzing');
    setError(null);
  };

  const handleApplyCuts = async (adjustments: any[], encodingMethod: 'reencode' | 'lossless') => {
    if (!jobId) return;

    try {
      setStep('processing');
      await api.applyVideoCuts(jobId, adjustments, encodingMethod);
    } catch (err: any) {
      console.error('Error applying cuts:', err);
      setError(err.response?.data?.error || 'Failed to apply cuts');
      setStep('preview');
    }
  };

  const handleDownloadVideo = async () => {
    if (!jobId) return;
    try {
      await api.downloadCutVideo(jobId);
    } catch (err) {
      console.error('Error downloading video:', err);
      alert('Download failed. Please try again.');
    }
  };

  const handleDownloadXML = async () => {
    if (!jobId) return;
    try {
      await api.downloadVideoXML(jobId);
    } catch (err) {
      console.error('Error downloading XML:', err);
      alert('XML download failed. Please try again.');
    }
  };

  const handleReset = () => {
    setStep('upload');
    setJobId(null);
    setAnalysis(null);
    setError(null);
    setCurrentJob(null);
  };

  // Check FFmpeg availability on mount
  useEffect(() => {
    if (isAuthenticated && !authLoading) {
      performSystemCheck();
    }
  }, [isAuthenticated, authLoading]);

  const performSystemCheck = async () => {
    setIsCheckingSystem(true);
    try {
      const check = await api.checkVideoSystem();
      setSystemCheck(check);
      setShowFFmpegWarning(check.status !== 'ready');
    } catch (err) {
      console.error('System check failed:', err);
      // If system check fails, assume FFmpeg might be missing
      setShowFFmpegWarning(true);
    } finally {
      setIsCheckingSystem(false);
    }
  };

  const handleRetrySystemCheck = async () => {
    await performSystemCheck();
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-card shadow-sm border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-3">
              <button
                onClick={() => navigate('/')}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                <ArrowLeft className="h-5 w-5" />
              </button>
              <Film className="h-7 w-7 text-primary" />
              <div>
                <h1 className="text-xl font-semibold text-foreground tracking-tight">Video Editor</h1>
                <p className="text-xs text-muted-foreground font-medium">AI-Powered Repeated Take Detection</p>
              </div>
            </div>

            <div className="flex items-center space-x-4">
              <AuthButton />
              <div className="border-l border-border h-6"></div>
              <a
                href="https://github.com/yourusername/easyedit-v2"
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                <Github className="h-5 w-5" />
              </a>
              <a
                href="https://www.blackmagicdesign.com/products/davinciresolve"
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                <ExternalLink className="h-5 w-5" />
              </a>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-[1280px] mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {authLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
            <span className="ml-3 text-lg text-muted-foreground">Loading...</span>
          </div>
        ) : !isAuthenticated ? (
          <div className="text-center py-16">
            <Shield className="h-16 w-16 text-muted-foreground/40 mx-auto mb-6" />
            <h2 className="text-3xl font-bold text-foreground mb-3 tracking-tight">Authentication Required</h2>
            <p className="text-muted-foreground text-base mb-8 max-w-md mx-auto leading-relaxed">
              Please click "Get Demo Token" in the header to authenticate and start using the video editor.
            </p>
          </div>
        ) : (
          <div className="max-w-5xl mx-auto space-y-8">
            {/* Error Display */}
            {error && (
              <FFmpegErrorDisplay
                error={error}
                platform={systemCheck?.platform}
                installUrl={systemCheck?.install_url}
                onRetry={handleRetrySystemCheck}
                onDismiss={() => setError(null)}
              />
            )}

            {/* FFmpeg Warning Banner */}
            {showFFmpegWarning && systemCheck && !error && (
              <FFmpegWarningBanner
                systemCheck={systemCheck}
                onRetry={handleRetrySystemCheck}
                isRetrying={isCheckingSystem}
              />
            )}

            {/* Step 1: Upload */}
            {step === 'upload' && (
              <>
                {isCheckingSystem && (
                  <div className="bg-card rounded-xl border border-border p-8 text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
                    <p className="text-muted-foreground">Checking system requirements...</p>
                  </div>
                )}

                {!isCheckingSystem && (
                  <VideoUploadZone onUploadComplete={handleUploadComplete} />
                )}
              </>
            )}

            {/* Step 2: Analyzing */}
            {step === 'analyzing' && jobId && (
              <VideoAnalysisProgress jobId={jobId} />
            )}

            {/* Step 3: Preview Segments */}
            {step === 'preview' && analysis && (
              <VideoSegmentPreview
                analysis={analysis}
                onApply={handleApplyCuts}
                onCancel={handleReset}
              />
            )}

            {/* Step 4: Processing */}
            {step === 'processing' && (
              <div className="bg-card rounded-xl border border-border p-8 text-center">
                <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-primary mx-auto mb-4"></div>
                <h3 className="text-xl font-semibold text-foreground mb-2">Processing Video</h3>
                <p className="text-muted-foreground">
                  Cutting and encoding your video. This may take 5-10 minutes...
                </p>
                {currentJob && (
                  <div className="mt-4">
                    <div className="w-full bg-muted rounded-full h-2 mb-2">
                      <div
                        className="bg-primary h-2 rounded-full transition-all duration-300"
                        style={{ width: `${currentJob.progress}%` }}
                      ></div>
                    </div>
                    <p className="text-sm text-muted-foreground">{currentJob.message}</p>
                  </div>
                )}
              </div>
            )}

            {/* Step 5: Complete */}
            {step === 'complete' && (
              <div className="bg-card rounded-xl border border-border p-8">
                <div className="text-center mb-6">
                  <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-500/10 mb-4">
                    <svg className="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <h3 className="text-2xl font-bold text-foreground mb-2">Video Processing Complete!</h3>
                  <p className="text-muted-foreground">
                    Your edited video and XML timeline are ready to download.
                  </p>
                </div>

                <div className="space-y-3">
                  <button
                    onClick={handleDownloadVideo}
                    className="w-full flex items-center justify-center space-x-2 bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-3 rounded-lg font-medium transition-colors"
                  >
                    <Film className="h-5 w-5" />
                    <span>Download Edited Video (.mp4)</span>
                  </button>

                  <button
                    onClick={handleDownloadXML}
                    className="w-full flex items-center justify-center space-x-2 bg-[#181818] border border-border text-foreground hover:bg-accent px-4 py-3 rounded-lg font-medium transition-colors"
                  >
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <span>Download XML Timeline (.xml)</span>
                  </button>

                  <button
                    onClick={handleReset}
                    className="w-full flex items-center justify-center space-x-2 bg-muted text-foreground hover:bg-muted/80 px-4 py-2.5 rounded-lg font-medium transition-colors mt-6"
                  >
                    <span>Process Another Video</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* How it Works Section */}
        <div className="mt-20 max-w-5xl mx-auto bg-gradient-to-br from-card via-card to-accent/5 rounded-2xl border border-border/80 shadow-lg p-8 lg:p-12">
          <h2 className="text-3xl font-bold text-foreground mb-3 tracking-tight text-center">
            How Video Editor Works
          </h2>
          <p className="text-center text-muted-foreground mb-10 max-w-2xl mx-auto">
            Four simple steps to detect and remove repeated takes automatically
          </p>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 lg:gap-8">
            <div className="text-center">
              <div className="bg-primary/10 rounded-full w-14 h-14 flex items-center justify-center mx-auto mb-5">
                <span className="text-xl font-bold text-primary">1</span>
              </div>
              <h3 className="font-semibold text-foreground mb-2.5 text-base">Upload Video</h3>
              <p className="text-muted-foreground text-sm leading-relaxed">
                Upload your video file (up to 3GB). Supports MP4, MOV, AVI, and MKV formats.
              </p>
            </div>

            <div className="text-center">
              <div className="bg-primary/10 rounded-full w-14 h-14 flex items-center justify-center mx-auto mb-5">
                <span className="text-xl font-bold text-primary">2</span>
              </div>
              <h3 className="font-semibold text-foreground mb-2.5 text-base">AI Analysis</h3>
              <p className="text-muted-foreground text-sm leading-relaxed">
                AI transcribes your video and detects repeated takes, false starts, and filler-heavy sections.
              </p>
            </div>

            <div className="text-center">
              <div className="bg-primary/10 rounded-full w-14 h-14 flex items-center justify-center mx-auto mb-5">
                <span className="text-xl font-bold text-primary">3</span>
              </div>
              <h3 className="font-semibold text-foreground mb-2.5 text-base">Review & Adjust</h3>
              <p className="text-muted-foreground text-sm leading-relaxed">
                Preview detected segments with keep/remove toggles. Adjust AI decisions before processing.
              </p>
            </div>

            <div className="text-center">
              <div className="bg-primary/10 rounded-full w-14 h-14 flex items-center justify-center mx-auto mb-5">
                <span className="text-xl font-bold text-primary">4</span>
              </div>
              <h3 className="font-semibold text-foreground mb-2.5 text-base">Download Results</h3>
              <p className="text-muted-foreground text-sm leading-relaxed">
                Download your edited MP4 video and DaVinci Resolve XML timeline for further editing.
              </p>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="mt-20 bg-card border-t border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center text-muted-foreground text-sm">
            <p className="font-medium">© 2024 EasyEdit v2 - Video Editor. Built for content creators, powered by AI.</p>
            <p className="mt-2.5 text-xs">
              Uses Replicate Whisper for transcription and pattern-based detection for repeated takes.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default VideoEditorPage;
