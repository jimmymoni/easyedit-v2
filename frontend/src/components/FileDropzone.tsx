import React, { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, File, Music } from 'lucide-react';

interface FileDropzoneProps {
  onFilesSelected: (audioFile: File | null, drtFile: File | null) => void;
  audioFile: File | null;
  drtFile: File | null;
  isUploading: boolean;
}

const FileDropzone: React.FC<FileDropzoneProps> = ({
  onFilesSelected,
  audioFile,
  drtFile,
  isUploading,
}) => {
  const onDrop = useCallback((acceptedFiles: File[]) => {
    let newAudioFile = audioFile;
    let newDrtFile = drtFile;

    acceptedFiles.forEach((file) => {
      const extension = file.name.split('.').pop()?.toLowerCase();

      if (['wav', 'mp3', 'm4a', 'aac', 'flac'].includes(extension || '')) {
        newAudioFile = file;
      } else if (['drt', 'xml'].includes(extension || '')) {
        newDrtFile = file;
      }
    });

    onFilesSelected(newAudioFile, newDrtFile);
  }, [audioFile, drtFile, onFilesSelected]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'audio/*': ['.wav', '.mp3', '.m4a', '.aac', '.flac'],
      'application/xml': ['.drt', '.xml'],
      'text/xml': ['.drt', '.xml'],
    },
    multiple: true,
    disabled: isUploading,
  });

  const removeFile = (type: 'audio' | 'drt') => {
    if (type === 'audio') {
      onFilesSelected(null, drtFile);
    } else {
      onFilesSelected(audioFile, null);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="w-full">
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
          ${isDragActive ? 'border-primary-500 bg-primary-50' : 'border-gray-300'}
          ${isUploading ? 'opacity-50 cursor-not-allowed' : 'hover:border-primary-400'}
        `}
      >
        <input {...getInputProps()} />
        <Upload className="mx-auto h-12 w-12 text-gray-400 mb-4" />
        <p className="text-lg font-medium text-gray-900 mb-2">
          {isDragActive ? 'Drop files here...' : 'Drop files or click to upload'}
        </p>
        <p className="text-sm text-gray-500">
          Upload audio files (WAV, MP3, M4A) and DaVinci Resolve timeline files (.drt, .xml)
        </p>
      </div>

      {/* File Preview */}
      {(audioFile || drtFile) && (
        <div className="mt-6 space-y-3">
          <h3 className="text-sm font-medium text-gray-900">Selected Files:</h3>

          {audioFile && (
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center space-x-3">
                <Music className="h-5 w-5 text-primary-500" />
                <div>
                  <p className="text-sm font-medium text-gray-900">{audioFile.name}</p>
                  <p className="text-xs text-gray-500">
                    Audio • {formatFileSize(audioFile.size)}
                  </p>
                </div>
              </div>
              {!isUploading && (
                <button
                  onClick={() => removeFile('audio')}
                  className="text-red-500 hover:text-red-700 text-sm"
                >
                  Remove
                </button>
              )}
            </div>
          )}

          {drtFile && (
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center space-x-3">
                <File className="h-5 w-5 text-primary-500" />
                <div>
                  <p className="text-sm font-medium text-gray-900">{drtFile.name}</p>
                  <p className="text-xs text-gray-500">
                    Timeline • {formatFileSize(drtFile.size)}
                  </p>
                </div>
              </div>
              {!isUploading && (
                <button
                  onClick={() => removeFile('drt')}
                  className="text-red-500 hover:text-red-700 text-sm"
                >
                  Remove
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Upload Requirements */}
      {(!audioFile || !drtFile) && (
        <div className="mt-6 p-4 bg-blue-50 rounded-lg">
          <h4 className="text-sm font-medium text-blue-900 mb-2">Required Files:</h4>
          <ul className="text-sm text-blue-800 space-y-1">
            <li className={`flex items-center ${audioFile ? 'line-through opacity-60' : ''}`}>
              • Audio file (WAV, MP3, M4A, AAC, FLAC)
            </li>
            <li className={`flex items-center ${drtFile ? 'line-through opacity-60' : ''}`}>
              • DaVinci Resolve timeline file (.drt or .xml)
            </li>
          </ul>
        </div>
      )}
    </div>
  );
};

export default FileDropzone;