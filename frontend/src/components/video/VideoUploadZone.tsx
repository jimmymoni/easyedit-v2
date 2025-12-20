import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Film, X, Upload } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import UploadProgress from '../UploadProgress';
import * as api from '../../services/api';

interface VideoUploadZoneProps {
  onUploadComplete: (jobId: string) => void;
}

export default function VideoUploadZone({ onUploadComplete }: VideoUploadZoneProps) {
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<api.UploadProgress | null>(null);
  const [uploadComplete, setUploadComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0];
      const extension = file.name.split('.').pop()?.toLowerCase();
      const maxSize = 3 * 1024 * 1024 * 1024; // 3GB in bytes

      if (!['mp4', 'mov', 'avi', 'mkv', 'm4v'].includes(extension || '')) {
        setError('Invalid file type. Please upload MP4, MOV, AVI, or MKV files.');
        return;
      }

      if (file.size > maxSize) {
        setError('File too large. Maximum size is 3GB.');
        return;
      }

      setVideoFile(file);
      setError(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'video/*': ['.mp4', '.mov', '.avi', '.mkv', '.m4v']
    },
    multiple: false,
    disabled: isUploading
  });

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation();
    setVideoFile(null);
    setError(null);
  };

  const handleUpload = async () => {
    if (!videoFile) return;

    setIsUploading(true);
    setUploadProgress(null);
    setUploadComplete(false);
    setError(null);

    try {
      const response = await api.uploadVideo(videoFile, (progress) => {
        setUploadProgress(progress);
      });

      setUploadComplete(true);
      await new Promise(resolve => setTimeout(resolve, 1000));

      // Analysis starts automatically in background, no need to call analyzeVideo
      onUploadComplete(response.job_id);
    } catch (err: any) {
      console.error('Upload failed:', err);
      setError(err.response?.data?.error || 'Upload failed. Please try again.');
    } finally {
      setIsUploading(false);
      setUploadProgress(null);
      setUploadComplete(false);
    }
  };

  const getFileExtension = (filename: string): string => {
    return filename.split('.').pop()?.toUpperCase() || '';
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(1)} KB`;
    } else if (bytes < 1024 * 1024 * 1024) {
      return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    } else {
      return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
    }
  };

  return (
    <div className="space-y-6">
      <Card
        {...getRootProps()}
        className={`
          relative cursor-pointer transition-all duration-200 border
          ${isUploading ? 'pointer-events-none opacity-60' : ''}
          ${isDragActive
            ? 'border-primary bg-primary/5 shadow-lg shadow-primary/20'
            : videoFile
            ? 'border-border bg-card hover:bg-accent/50 shadow-sm hover:shadow-md'
            : 'border-dashed border-muted-foreground/25 hover:border-muted-foreground/50 hover:bg-accent/30 hover:shadow-sm'
          }
        `}
      >
        <input {...getInputProps()} />

        {videoFile ? (
          <div className="p-6">
            <div className="flex items-center gap-4">
              <div className="flex-shrink-0">
                <Film className="h-8 w-8 text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-base font-semibold truncate mb-1">{videoFile.name}</p>
                <p className="text-sm text-muted-foreground">
                  {formatFileSize(videoFile.size)}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <Badge variant="secondary" className="text-sm font-medium">
                  {getFileExtension(videoFile.name)}
                </Badge>
                <button
                  onClick={handleRemove}
                  disabled={isUploading}
                  className="flex-shrink-0 p-2 hover:bg-destructive/10 rounded-md transition-colors disabled:opacity-50"
                >
                  <X className="h-5 w-5 text-muted-foreground hover:text-destructive" />
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="p-12 text-center min-h-[240px] flex flex-col items-center justify-center">
            <div className="bg-primary/10 rounded-full p-6 mb-6">
              <Film className="h-12 w-12 text-primary" />
            </div>
            <p className="text-lg font-semibold text-foreground mb-2">
              {isDragActive ? 'Drop video file here' : 'Upload Video File'}
            </p>
            <p className="text-sm text-muted-foreground leading-relaxed mb-1">
              Drag & drop or click to upload
            </p>
            <p className="text-xs text-muted-foreground/70">
              MP4, MOV, AVI, MKV (up to 3GB)
            </p>
          </div>
        )}
      </Card>

      {/* Error Display */}
      {error && (
        <div className="bg-destructive/10 border border-destructive/20 rounded-xl p-4">
          <div className="flex items-start space-x-3">
            <svg
              className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <div className="flex-1">
              <p className="text-destructive text-sm font-medium">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Upload Button */}
      {videoFile && !isUploading && !uploadProgress && (
        <button
          onClick={handleUpload}
          className="w-full flex items-center justify-center space-x-2 bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-3 rounded-lg font-medium transition-colors"
        >
          <Upload className="h-5 w-5" />
          <span>Upload & Analyze Video</span>
        </button>
      )}

      {/* Upload Progress */}
      {uploadProgress && (
        <UploadProgress
          progress={uploadProgress}
          isComplete={uploadComplete}
        />
      )}

      {/* Info Box */}
      <div className="bg-primary/5 border border-primary/10 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-foreground mb-2">What happens next?</h3>
        <ul className="text-xs text-muted-foreground space-y-1.5 leading-relaxed">
          <li>• Secure upload to cloud servers (5-15 min for large files)</li>
          <li>• AI automatically analyzes your video (no software required)</li>
          <li>• Repeated takes and mistakes detected instantly</li>
          <li>• Review suggested cuts and make adjustments</li>
          <li>• Download your edited video and timeline</li>
        </ul>
      </div>
    </div>
  );
}
