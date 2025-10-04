import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { FileVideo, Upload, X } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';

interface TimelineUploadZoneProps {
  drtFile: File | null;
  onFileSelected: (file: File | null) => void;
}

export default function TimelineUploadZone({ drtFile, onFileSelected }: TimelineUploadZoneProps) {
  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0];
      const extension = file.name.split('.').pop()?.toLowerCase();

      if (['drt', 'xml'].includes(extension || '')) {
        onFileSelected(file);
      }
    }
  }, [onFileSelected]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/xml': ['.drt', '.xml']
    },
    multiple: false
  });

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation();
    onFileSelected(null);
  };

  return (
    <Card className="border-2 border-dashed transition-colors duration-200 hover:border-secondary">
      <CardContent className="p-6">
        <div
          {...getRootProps()}
          className={`
            flex flex-col items-center justify-center p-8 rounded-lg cursor-pointer
            transition-all duration-200
            ${isDragActive
              ? 'bg-secondary/10 border-2 border-secondary'
              : 'bg-muted/30 hover:bg-muted/50'
            }
          `}
        >
          <input {...getInputProps()} />

          {drtFile ? (
            <div className="flex flex-col items-center gap-4 w-full">
              <div className="flex items-center justify-between w-full max-w-md p-4 bg-background rounded-lg border">
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <div className="flex-shrink-0">
                    <FileVideo className="h-8 w-8 text-secondary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{drtFile.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {(drtFile.size / 1024).toFixed(2)} KB
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
              <div className="p-4 rounded-full bg-secondary/10">
                <Upload className="h-10 w-10 text-secondary" />
              </div>
              <div>
                <p className="text-lg font-semibold mb-1">
                  {isDragActive ? 'Drop timeline file here' : 'Upload Timeline File'}
                </p>
                <p className="text-sm text-muted-foreground">
                  Drag & drop or click to browse
                </p>
                <p className="text-xs text-muted-foreground mt-2">
                  Supports: DRT, XML (DaVinci Resolve Timeline)
                </p>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
