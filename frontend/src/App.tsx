import React, { useState, useEffect } from 'react';
import { Zap, Github, ExternalLink, Shield } from 'lucide-react';
import FileDropzone from './components/FileDropzone';
import ProcessingOptions from './components/ProcessingOptions';
import ProcessingStatus from './components/ProcessingStatus';
import JobHistory from './components/JobHistory';
import AuthButton from './components/AuthButton';
import { useAuth } from './contexts/AuthContext';
import * as api from './services/api';
import { ProcessingJob, ProcessingOptions as ProcessingOptionsType } from './types';

function App() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  // State for file upload
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [drtFile, setDrtFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);

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

  const handleFilesSelected = (audio: File | null, drt: File | null) => {
    setAudioFile(audio);
    setDrtFile(drt);
  };

  const handleUploadAndProcess = async () => {
    if (!audioFile || !drtFile) return;

    setIsUploading(true);
    try {
      // Upload files
      const uploadResponse = await api.uploadFiles(audioFile, drtFile);
      console.log('Upload successful:', uploadResponse);

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
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-3">
              <Zap className="h-8 w-8 text-primary-600" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900">EasyEdit v2</h1>
                <p className="text-sm text-gray-500">AI-Powered Timeline Editor for DaVinci Resolve</p>
              </div>
            </div>

            <div className="flex items-center space-x-4">
              <AuthButton />
              <div className="border-l border-gray-300 h-6"></div>
              <a
                href="https://github.com/yourusername/easyedit-v2"
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-500 hover:text-gray-700"
              >
                <Github className="h-5 w-5" />
              </a>
              <a
                href="https://www.blackmagicdesign.com/products/davinciresolve"
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-500 hover:text-gray-700"
              >
                <ExternalLink className="h-5 w-5" />
              </a>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {authLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
            <span className="ml-3 text-lg text-gray-600">Loading...</span>
          </div>
        ) : !isAuthenticated ? (
          <div className="text-center py-12">
            <Shield className="h-24 w-24 text-gray-400 mx-auto mb-6" />
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">Authentication Required</h2>
            <p className="text-gray-600 mb-6 max-w-md mx-auto">
              Please click "Get Demo Token" in the header to authenticate and start using the application.
            </p>
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 max-w-lg mx-auto">
              <p className="text-yellow-800 text-sm">
                <strong>For Demo:</strong> This uses a demo token for testing. In production, you would have proper user registration and login.
              </p>
            </div>
          </div>
        ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left Column - Upload and Options */}
          <div className="space-y-6">
            {/* File Upload */}
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">Upload Files</h2>
              <FileDropzone
                onFilesSelected={handleFilesSelected}
                audioFile={audioFile}
                drtFile={drtFile}
                isUploading={isUploading}
              />
            </div>

            {/* Processing Options */}
            <ProcessingOptions
              options={processingOptions}
              onOptionsChange={setProcessingOptions}
              disabled={isUploading || isPolling}
            />

            {/* Process Button */}
            <button
              onClick={handleUploadAndProcess}
              disabled={!canStartProcessing}
              className={`
                w-full py-3 px-4 rounded-lg font-medium text-white transition-colors
                ${canStartProcessing
                  ? 'bg-primary-600 hover:bg-primary-700'
                  : 'bg-gray-400 cursor-not-allowed'
                }
              `}
            >
              {isUploading ? 'Uploading...' : 'Upload & Process Timeline'}
            </button>
          </div>

          {/* Right Column - Status and History */}
          <div className="space-y-6">
            {/* Current Job Status */}
            {currentJob && (
              <ProcessingStatus
                job={selectedJob || currentJob}
                onDownload={handleDownload}
              />
            )}

            {/* Job History */}
            <JobHistory
              jobs={jobHistory}
              onDownload={handleDownload}
              onViewDetails={setSelectedJob}
            />
          </div>
        </div>
        )}

        {/* How it Works Section */}
        <div className="mt-12 bg-white rounded-lg border border-gray-200 p-8">
          <h2 className="text-2xl font-semibold text-gray-900 mb-6">How It Works</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center">
              <div className="bg-primary-100 rounded-full w-16 h-16 flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl font-bold text-primary-600">1</span>
              </div>
              <h3 className="font-semibold text-gray-900 mb-2">Upload Files</h3>
              <p className="text-gray-600 text-sm">
                Upload your audio file and DaVinci Resolve timeline (.drt) file. We support various audio formats including WAV, MP3, and M4A.
              </p>
            </div>

            <div className="text-center">
              <div className="bg-primary-100 rounded-full w-16 h-16 flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl font-bold text-primary-600">2</span>
              </div>
              <h3 className="font-semibold text-gray-900 mb-2">AI Processing</h3>
              <p className="text-gray-600 text-sm">
                Our AI analyzes your audio using Soniox API for transcription, detects speakers, removes silence, and applies intelligent editing rules.
              </p>
            </div>

            <div className="text-center">
              <div className="bg-primary-100 rounded-full w-16 h-16 flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl font-bold text-primary-600">3</span>
              </div>
              <h3 className="font-semibold text-gray-900 mb-2">Download & Import</h3>
              <p className="text-gray-600 text-sm">
                Download your optimized .drt timeline file and import it directly into DaVinci Resolve to continue editing with pre-cut segments.
              </p>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="mt-12 bg-white border-t border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="text-center text-gray-500 text-sm">
            <p>© 2024 EasyEdit v2. Built for video editors, powered by AI.</p>
            <p className="mt-2">
              Uses Soniox API for transcription and OpenAI for enhancement features.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;