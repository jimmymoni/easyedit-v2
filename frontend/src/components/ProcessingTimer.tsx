import { useEffect, useState } from 'react';
import { Clock, Timer, Calendar } from 'lucide-react';

interface ProcessingTimerProps {
  startTime: number;
  estimatedDuration?: number; // in seconds
  isProcessing: boolean;
}

export default function ProcessingTimer({ startTime, estimatedDuration, isProcessing }: ProcessingTimerProps) {
  const [elapsedTime, setElapsedTime] = useState(0);

  useEffect(() => {
    if (!isProcessing) {
      setElapsedTime(0);
      return;
    }

    const interval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      setElapsedTime(elapsed);
    }, 1000);

    return () => clearInterval(interval);
  }, [startTime, isProcessing]);

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const formatCompletionTime = (): string => {
    if (!estimatedDuration) return 'Calculating...';

    const remainingSeconds = Math.max(0, estimatedDuration - elapsedTime);
    const completionTime = new Date(Date.now() + (remainingSeconds * 1000));

    return completionTime.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  };

  const getRemainingTime = (): string => {
    if (!estimatedDuration) return '~';

    const remainingSeconds = Math.max(0, estimatedDuration - elapsedTime);
    return formatTime(remainingSeconds);
  };

  const getProgress = (): number => {
    if (!estimatedDuration) return 0;
    return Math.min(100, (elapsedTime / estimatedDuration) * 100);
  };

  if (!isProcessing) return null;

  return (
    <div className="space-y-3 p-4 bg-muted/30 rounded-lg border">
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2">
          <Timer className="h-4 w-4 text-primary" />
          <span className="font-medium">Elapsed</span>
        </div>
        <span className="font-mono text-lg">{formatTime(elapsedTime)}</span>
      </div>

      {estimatedDuration && (
        <>
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium">Remaining</span>
            </div>
            <span className="font-mono text-lg text-muted-foreground">{getRemainingTime()}</span>
          </div>

          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium">ETA</span>
            </div>
            <span className="font-medium">{formatCompletionTime()}</span>
          </div>

          <div className="space-y-1">
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Progress</span>
              <span>{Math.round(getProgress())}%</span>
            </div>
            <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary transition-all duration-500 ease-out"
                style={{ width: `${getProgress()}%` }}
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
