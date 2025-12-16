import { useState, useEffect } from 'react';
import { Film, Mic, Brain, Clock } from 'lucide-react';
import { Card } from '@/components/ui/card';

interface VideoAnalysisProgressProps {
  jobId: string;
}

type AnalysisStage = 'extracting' | 'transcribing' | 'detecting' | 'complete';

export default function VideoAnalysisProgress({ jobId }: VideoAnalysisProgressProps) {
  const [stage, setStage] = useState<AnalysisStage>('extracting');
  const [elapsedTime, setElapsedTime] = useState(0);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const startTime = Date.now();
    const timer = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      setElapsedTime(elapsed);

      // Simulate stage progression based on typical timings
      if (elapsed < 30) {
        setStage('extracting');
        setProgress(Math.min((elapsed / 30) * 10, 10));
      } else if (elapsed < 180) {
        setStage('transcribing');
        setProgress(10 + Math.min(((elapsed - 30) / 150) * 60, 60));
      } else {
        setStage('detecting');
        setProgress(70 + Math.min(((elapsed - 180) / 60) * 30, 30));
      }
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getEstimatedTime = (): string => {
    switch (stage) {
      case 'extracting':
        return '~30 seconds';
      case 'transcribing':
        return '~2-3 minutes';
      case 'detecting':
        return '~1 minute';
      default:
        return 'Almost done...';
    }
  };

  const stages = [
    {
      id: 'extracting',
      icon: Film,
      label: 'Processing Audio',
      description: 'Analyzing audio in the cloud',
      progress: stage === 'extracting' ? progress : stage !== 'extracting' && progress > 10 ? 10 : 0,
      active: stage === 'extracting',
      complete: progress > 10
    },
    {
      id: 'transcribing',
      icon: Mic,
      label: 'Transcribing Speech',
      description: 'AI transcription with speaker identification',
      progress: stage === 'transcribing' ? progress - 10 : progress > 70 ? 60 : 0,
      active: stage === 'transcribing',
      complete: progress > 70
    },
    {
      id: 'detecting',
      icon: Brain,
      label: 'Detecting Repeated Takes',
      description: 'Analyzing for duplicates, false starts, and fillers',
      progress: stage === 'detecting' ? progress - 70 : 0,
      active: stage === 'detecting',
      complete: progress >= 100
    }
  ];

  return (
    <div className="space-y-6">
      <Card className="p-8">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary/10 mb-4">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary"></div>
          </div>
          <h3 className="text-2xl font-bold text-foreground mb-2">Processing in the Cloud</h3>
          <p className="text-muted-foreground mb-1">
            Cloud analysis usually takes 10-15 minutes.
          </p>
          <p className="text-sm text-muted-foreground/80">
            You can safely close this tab and come back later.
          </p>
        </div>

        {/* Overall Progress Bar */}
        <div className="mb-8">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium text-foreground">Overall Progress</span>
            <span className="text-sm text-muted-foreground">{Math.round(progress)}%</span>
          </div>
          <div className="w-full bg-muted rounded-full h-3">
            <div
              className="bg-primary h-3 rounded-full transition-all duration-500 ease-out"
              style={{ width: `${progress}%` }}
            ></div>
          </div>
        </div>

        {/* Stage Cards */}
        <div className="space-y-4">
          {stages.map((s, index) => {
            const Icon = s.icon;
            return (
              <div
                key={s.id}
                className={`
                  flex items-start gap-4 p-4 rounded-xl border transition-all duration-300
                  ${s.active
                    ? 'border-primary bg-primary/5'
                    : s.complete
                    ? 'border-green-500/20 bg-green-500/5'
                    : 'border-border bg-card/50'
                  }
                `}
              >
                <div className={`
                  flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center
                  ${s.active
                    ? 'bg-primary/20'
                    : s.complete
                    ? 'bg-green-500/20'
                    : 'bg-muted'
                  }
                `}>
                  {s.complete ? (
                    <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    <Icon className={`h-5 w-5 ${s.active ? 'text-primary' : 'text-muted-foreground'}`} />
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <h4 className={`text-sm font-semibold ${s.active ? 'text-foreground' : 'text-muted-foreground'}`}>
                      {s.label}
                    </h4>
                    {s.active && (
                      <span className="text-xs text-muted-foreground">
                        {getEstimatedTime()}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mb-2">{s.description}</p>
                  {s.active && (
                    <div className="w-full bg-muted/50 rounded-full h-1.5">
                      <div
                        className="bg-primary h-1.5 rounded-full transition-all duration-500"
                        style={{ width: `${(s.progress / [10, 60, 30][index]) * 100}%` }}
                      ></div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Time Elapsed */}
        <div className="mt-6 pt-6 border-t border-border">
          <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
            <Clock className="h-4 w-4" />
            <span>Time Elapsed: {formatTime(elapsedTime)}</span>
          </div>
        </div>
      </Card>

      {/* Info Box */}
      <div className="bg-primary/5 border border-primary/10 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-foreground mb-2">What's happening?</h3>
        <ul className="text-xs text-muted-foreground space-y-1.5 leading-relaxed">
          <li>• Cloud servers are processing your video (no local software required)</li>
          <li>• AI transcription identifies speakers and timestamps automatically</li>
          <li>• Repeated takes and mistakes are detected in real-time</li>
          <li>• Quality scoring helps you choose the best takes</li>
          <li>• You can close this tab and come back later</li>
        </ul>
      </div>
    </div>
  );
}
