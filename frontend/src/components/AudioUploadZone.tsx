import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Music, Upload, X } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';

interface AudioUploadZoneProps {
  audioFile: File | null;
  onFileSelected: (file: File | null) => void;
}

export default function AudioUploadZone({ audioFile, onFileSelected }: AudioUploadZoneProps) {
  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0];
      const extension = file.name.split('.').pop()?.toLowerCase();

      if (['wav', 'mp3', 'm4a', 'aac', 'flac'].includes(extension || '')) {
        onFileSelected(file);
      }
    }
  }, [onFileSelected]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'audio/*': ['.wav', '.mp3', '.m4a', '.aac', '.flac']
    },
    multiple: false
  });

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation();
    onFileSelected(null);
  };

  return (
    <Card className="border-2 border-dashed transition-colors duration-200 hover:border-primary">
      <CardContent className="p-6">
        <div
          {...getRootProps()}
          className={`
            flex flex-col items-center justify-center p-8 rounded-lg cursor-pointer
            transition-all duration-200
            ${isDragActive
              ? 'bg-primary/10 border-2 border-primary'
              : 'bg-muted/30 hover:bg-muted/50'
            }
          `}
        >
          <input {...getInputProps()} />

          {audioFile ? (
            <div className="flex flex-col items-center gap-4 w-full">
              <div className="flex items-center justify-between w-full max-w-md p-4 bg-background rounded-lg border">
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <div className="flex-shrink-0">
                    <Music className="h-8 w-8 text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{audioFile.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {(audioFile.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                </div>
                <button
                  onClick={handleRemove}
                  className="flex-shrink-0 ml-3 p-1 hover:bg-destructive/10 rounded-full transition-colors"
                >
                  <X className="h-5 w-5 text-destructive" />
                </button>
              </div>
              <p className="text-sm text-muted-foreground">
                Click or drag to replace
              </p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-4 text-center">
              <div className="p-4 rounded-full bg-primary/10">
                <Upload className="h-10 w-10 text-primary" />
              </div>
              <div>
                <p className="text-lg font-semibold mb-1">
                  {isDragActive ? 'Drop audio file here' : 'Upload Audio File'}
                </p>
                <p className="text-sm text-muted-foreground">
                  Drag & drop or click to browse
                </p>
                <p className="text-xs text-muted-foreground mt-2">
                  Supports: WAV, MP3, M4A, AAC, FLAC
                </p>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
