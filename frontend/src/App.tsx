import React, { useState, useEffect } from 'react';
import { Zap, Github, ExternalLink, Shield } from 'lucide-react';
import AudioUploadZone from './components/AudioUploadZone';
import TimelineUploadZone from './components/TimelineUploadZone';
import ProcessingOptionsTable from './components/ProcessingOptionsTable';
import ProcessingStatus from './components/ProcessingStatus';
import JobHistoryDropdown from './components/JobHistoryDropdown';
import AuthButton from './components/AuthButton';
import UploadProgress from './components/UploadProgress';
import { useAuth } from './contexts/AuthContext';
import * as api from './services/api';
import { ProcessingJob, ProcessingOptions as ProcessingOptionsType } from './types';

function App() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  // State for file upload
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [drtFile, setDrtFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<api.UploadProgress | null>(null);
  const [uploadComplete, setUploadComplete] = useState(false);

  // State for processing
  const [processingOptions, setProcessingOptions] = useState<ProcessingOptionsType>({
    enable_transcription: true,
    enable_speaker_diarization: true,
    remove_silence: true,
    min_clip_length: 5,
    silence_threshold_db: -40,
  });

  // State for current job
  const [currentJob, setCurrentJob] = useState<ProcessingJob | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  // State for job history
  const [jobHistory, setJobHistory] = useState<ProcessingJob[]>([]);
  const [selectedJob, setSelectedJob] = useState<ProcessingJob | null>(null);

  // Load job history when authenticated
  useEffect(() => {
    if (isAuthenticated) {
      loadJobHistory();
      checkBackendHealth();
    }
  }, [isAuthenticated]);

  // Poll current job status
  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    if (currentJob && (currentJob.status === 'processing' || currentJob.status === 'uploaded')) {
      setIsPolling(true);
      intervalId = setInterval(async () => {
        try {
          const updatedJob = await api.getJobStatus(currentJob.job_id);
          setCurrentJob(updatedJob);

          if (updatedJob.status === 'completed' || updatedJob.status === 'failed') {
            setIsPolling(false);
            loadJobHistory(); // Refresh history
          }
        } catch (error) {
          console.error('Error polling job status:', error);
        }
      }, 2000);
    }

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
      setIsPolling(false);
    };
  }, [currentJob]);

  const checkBackendHealth = async () => {
    try {
      await api.healthCheck();
    } catch (error) {
      console.error('Backend health check failed:', error);
    }
  };

  const loadJobHistory = async () => {
    try {
      const response = await api.getAllJobs();
      setJobHistory(response.jobs.slice(0, 10)); // Show latest 10 jobs
    } catch (error) {
      console.error('Error loading job history:', error);
    }
  };

  const handleAudioSelected = (file: File | null) => {
    setAudioFile(file);
  };

  const handleDrtSelected = (file: File | null) => {
    setDrtFile(file);
  };

  const handleUploadAndProcess = async () => {
    if (!audioFile || !drtFile) return;

    setIsUploading(true);
    setUploadProgress(null);
    setUploadComplete(false);

    try {
      // Upload files with progress tracking
      const uploadResponse = await api.uploadFiles(
        audioFile,
        drtFile,
        (progress) => {
          setUploadProgress(progress);
        }
      );
      console.log('Upload successful:', uploadResponse);

      // Mark upload as complete
      setUploadComplete(true);

      // Wait a moment to show completion state
      await new Promise(resolve => setTimeout(resolve, 1000));

      // Set initial job status
      const initialJob: ProcessingJob = {
        job_id: uploadResponse.job_id,
        status: 'uploaded',
        progress: 10,
        message: 'Files uploaded successfully',
        created_at: new Date().toISOString(),
      };
      setCurrentJob(initialJob);

      // Start processing
      await api.processTimeline(uploadResponse.job_id, processingOptions);

      // Clear uploaded files
      setAudioFile(null);
      setDrtFile(null);

    } catch (error) {
      console.error('Upload or processing failed:', error);
      alert('Upload or processing failed. Please try again.');
    } finally {
      setIsUploading(false);
      setUploadProgress(null);
      setUploadComplete(false);
    }
  };

  const handleDownload = async (jobId: string) => {
    try {
      const blob = await api.downloadResult(jobId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = `edited_timeline_${jobId.slice(-8)}.drt`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Download failed:', error);
      alert('Download failed. Please try again.');
    }
  };

  const canStartProcessing = audioFile && drtFile && !isUploading && !isPolling;

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-card shadow-sm border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-3">
              <Zap className="h-7 w-7 text-primary" />
              <div>
                <h1 className="text-xl font-semibold text-foreground tracking-tight">EasyEdit v2</h1>
                <p className="text-xs text-muted-foreground font-medium">AI-Powered Timeline Editor</p>
              </div>
            </div>

            <div className="flex items-center space-x-4">
              {isAuthenticated && (
                <>
                  <JobHistoryDropdown
                    jobs={jobHistory}
                    onDownload={handleDownload}
                    onViewDetails={setSelectedJob}
                  />
                  <div className="border-l border-border h-6"></div>
                </>
              )}
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
              Please click "Get Demo Token" in the header to authenticate and start using the application.
            </p>
            <div className="bg-primary/5 border border-primary/10 rounded-xl p-5 max-w-lg mx-auto">
              <p className="text-foreground text-sm leading-relaxed">
                <strong className="font-semibold">For Demo:</strong> This uses a demo token for testing. In production, you would have proper user registration and login.
              </p>
            </div>
          </div>
        ) : (
        <div className="max-w-5xl mx-auto space-y-8">
          {/* File Upload - Side by Side */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <AudioUploadZone
              audioFile={audioFile}
              onFileSelected={handleAudioSelected}
            />
            <TimelineUploadZone
              drtFile={drtFile}
              onFileSelected={handleDrtSelected}
            />
          </div>

          {/* Processing Options */}
          <ProcessingOptionsTable
            options={processingOptions}
            onOptionsChange={setProcessingOptions}
            disabled={isUploading || isPolling}
          />

          {/* Process Button */}
          <button
            onClick={handleUploadAndProcess}
            disabled={!canStartProcessing}
            className={`
              w-full py-3 px-4 rounded-lg font-medium transition-colors
              ${canStartProcessing
                ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                : 'bg-muted text-muted-foreground cursor-not-allowed'
              }
            `}
          >
            {isUploading ? 'Uploading...' : 'Upload & Process Timeline'}
          </button>

          {/* Upload Progress */}
          {uploadProgress && (
            <UploadProgress
              progress={uploadProgress}
              isComplete={uploadComplete}
            />
          )}

          {/* Current Job Status */}
          {currentJob && !uploadProgress && (
            <ProcessingStatus
              job={selectedJob || currentJob}
              onDownload={handleDownload}
            />
          )}
        </div>
        )}

        {/* How it Works Section */}
        <div className="mt-20 max-w-5xl mx-auto bg-gradient-to-br from-card via-card to-accent/5 rounded-2xl border border-border/80 shadow-lg p-8 lg:p-12">
          <h2 className="text-3xl font-bold text-foreground mb-3 tracking-tight text-center">
            How It Works
          </h2>
          <p className="text-center text-muted-foreground mb-10 max-w-2xl mx-auto">
            Three simple steps to automated timeline editing
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8">
            <div className="text-center">
              <div className="bg-primary/10 rounded-full w-14 h-14 flex items-center justify-center mx-auto mb-5">
                <span className="text-xl font-bold text-primary">1</span>
              </div>
              <h3 className="font-semibold text-foreground mb-2.5 text-base">Upload Files</h3>
              <p className="text-muted-foreground text-sm leading-relaxed">
                Upload your audio file and DaVinci Resolve timeline (.drt) file. We support various audio formats including WAV, MP3, and M4A.
              </p>
            </div>

            <div className="text-center">
              <div className="bg-primary/10 rounded-full w-14 h-14 flex items-center justify-center mx-auto mb-5">
                <span className="text-xl font-bold text-primary">2</span>
              </div>
              <h3 className="font-semibold text-foreground mb-2.5 text-base">AI Processing</h3>
              <p className="text-muted-foreground text-sm leading-relaxed">
                Our AI analyzes your audio using Soniox API for transcription, detects speakers, removes silence, and applies intelligent editing rules.
              </p>
            </div>

            <div className="text-center">
              <div className="bg-primary/10 rounded-full w-14 h-14 flex items-center justify-center mx-auto mb-5">
                <span className="text-xl font-bold text-primary">3</span>
              </div>
              <h3 className="font-semibold text-foreground mb-2.5 text-base">Download & Import</h3>
              <p className="text-muted-foreground text-sm leading-relaxed">
                Download your optimized .drt timeline file and import it directly into DaVinci Resolve to continue editing with pre-cut segments.
              </p>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="mt-20 bg-card border-t border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center text-muted-foreground text-sm">
            <p className="font-medium">© 2024 EasyEdit v2. Built for video editors, powered by AI.</p>
            <p className="mt-2.5 text-xs">
              Uses Soniox API for transcription and OpenAI for enhancement features.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;