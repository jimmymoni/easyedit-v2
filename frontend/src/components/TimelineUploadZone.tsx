import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { FileVideo, X } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface TimelineUploadZoneProps {
  timelineFile: File | null;
  onFileSelected: (file: File | null) => void;
}

export default function TimelineUploadZone({ timelineFile, onFileSelected }: TimelineUploadZoneProps) {
  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0];
      const extension = file.name.split('.').pop()?.toLowerCase();

      if (extension === 'xml') {
        onFileSelected(file);
      }
    }
  }, [onFileSelected]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/xml': ['.xml']
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
          : timelineFile
          ? 'border-border bg-card hover:bg-accent/50 shadow-sm hover:shadow-md'
          : 'border-dashed border-muted-foreground/25 hover:border-muted-foreground/50 hover:bg-accent/30 hover:shadow-sm'
        }
      `}
    >
      <input {...getInputProps()} />

      {timelineFile ? (
        <div className="p-4">
          <div className="flex items-center gap-3">
            <div className="flex-shrink-0">
              <FileVideo className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{timelineFile.name}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {(timelineFile.size / 1024).toFixed(1)} KB
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="secondary" className="text-xs">
                {getFileExtension(timelineFile.name)}
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
          <FileVideo className="h-10 w-10 mx-auto text-muted-foreground/50 mb-3" />
          <p className="text-sm font-medium text-foreground mb-1.5">
            {isDragActive ? 'Drop timeline file' : 'Timeline File'}
          </p>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Drag & drop or click to upload<br />
            <span className="text-muted-foreground/70">FCP7 XML (.xml)</span>
          </p>
        </div>
      )}
    </Card>
  );
}
