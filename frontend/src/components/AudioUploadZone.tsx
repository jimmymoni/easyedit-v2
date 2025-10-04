import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Music, X } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

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

  const getFileExtension = (filename: string): string => {
    return filename.split('.').pop()?.toUpperCase() || '';
  };

  return (
    <Card
      {...getRootProps()}
      className={`
        relative cursor-pointer transition-all duration-200 border
        ${isDragActive
          ? 'border-primary bg-primary/5 shadow-lg shadow-primary/20'
          : audioFile
          ? 'border-border bg-card hover:bg-accent/50 shadow-sm hover:shadow-md'
          : 'border-dashed border-muted-foreground/25 hover:border-muted-foreground/50 hover:bg-accent/30 hover:shadow-sm'
        }
      `}
    >
      <input {...getInputProps()} />

      {audioFile ? (
        <div className="p-4">
          <div className="flex items-center gap-3">
            <div className="flex-shrink-0">
              <Music className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{audioFile.name}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {(audioFile.size / 1024 / 1024).toFixed(1)} MB
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="secondary" className="text-xs">
                {getFileExtension(audioFile.name)}
              </Badge>
              <button
                onClick={handleRemove}
                className="flex-shrink-0 p-1 hover:bg-destructive/10 rounded-md transition-colors"
              >
                <X className="h-4 w-4 text-muted-foreground hover:text-destructive" />
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-8 text-center min-h-[180px] flex flex-col items-center justify-center">
          <Music className="h-10 w-10 mx-auto text-muted-foreground/50 mb-3" />
          <p className="text-sm font-medium text-foreground mb-1.5">
            {isDragActive ? 'Drop audio file' : 'Audio File'}
          </p>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Drag & drop or click to upload<br />
            <span className="text-muted-foreground/70">WAV, MP3, M4A, AAC, FLAC</span>
          </p>
        </div>
      )}
    </Card>
  );
}
