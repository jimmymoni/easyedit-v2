import React, { useState, useEffect } from 'react';
import { Search, Download, FileText, Clock } from 'lucide-react';
import * as api from '../../services/api';

interface TranscriptionSegment {
  timestamp: number;
  speaker: string;
  text: string;
  confidence?: number;
}

interface TranscriptionViewerProps {
  jobId: string;
  onSeekAudio?: (timestamp: number) => void;
}

const TranscriptionViewer: React.FC<TranscriptionViewerProps> = ({ jobId, onSeekAudio }) => {
  const [transcription, setTranscription] = useState<TranscriptionSegment[]>([]);
  const [filteredTranscription, setFilteredTranscription] = useState<TranscriptionSegment[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [speakerLabels, setSpeakerLabels] = useState<Record<string, string>>({});
  const [editingSpeaker, setEditingSpeaker] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadTranscription();
  }, [jobId]);

  useEffect(() => {
    // Filter transcription based on search query
    if (searchQuery.trim() === '') {
      setFilteredTranscription(transcription);
    } else {
      const query = searchQuery.toLowerCase();
      const filtered = transcription.filter(
        segment =>
          segment.text.toLowerCase().includes(query) ||
          getSpeakerLabel(segment.speaker).toLowerCase().includes(query)
      );
      setFilteredTranscription(filtered);
    }
  }, [searchQuery, transcription, speakerLabels]);

  const loadTranscription = async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Fetch transcription from backend
      const response = await api.getTranscription(jobId);

      if (response.transcription && response.transcription.length > 0) {
        setTranscription(response.transcription);
        setFilteredTranscription(response.transcription);
      } else {
        setError('No transcription available for this job. Make sure transcription was enabled during processing.');
      }
    } catch (err: any) {
      console.error('Error loading transcription:', err);
      setError(err.response?.data?.error || 'Failed to load transcription');
    } finally {
      setIsLoading(false);
    }
  };

  const formatTimestamp = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
      return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getSpeakerLabel = (speaker: string): string => {
    return speakerLabels[speaker] || speaker;
  };

  const handleSpeakerEdit = (speaker: string, newLabel: string) => {
    setSpeakerLabels(prev => ({
      ...prev,
      [speaker]: newLabel
    }));
    setEditingSpeaker(null);
  };

  const handleTimestampClick = (timestamp: number) => {
    if (onSeekAudio) {
      onSeekAudio(timestamp);
    }
  };

  const exportAsText = () => {
    const text = filteredTranscription
      .map(seg => `[${formatTimestamp(seg.timestamp)}] ${getSpeakerLabel(seg.speaker)}: ${seg.text}`)
      .join('\n\n');

    downloadFile(text, `transcription_${jobId.slice(-8)}.txt`, 'text/plain');
  };

  const exportAsSRT = () => {
    let srt = '';
    filteredTranscription.forEach((seg, index) => {
      const start = formatSRTTimestamp(seg.timestamp);
      const end = formatSRTTimestamp(seg.timestamp + 5); // Assume 5 second duration
      srt += `${index + 1}\n${start} --> ${end}\n${getSpeakerLabel(seg.speaker)}: ${seg.text}\n\n`;
    });

    downloadFile(srt, `transcription_${jobId.slice(-8)}.srt`, 'text/srt');
  };

  const exportAsVTT = () => {
    let vtt = 'WEBVTT\n\n';
    filteredTranscription.forEach((seg, index) => {
      const start = formatVTTTimestamp(seg.timestamp);
      const end = formatVTTTimestamp(seg.timestamp + 5);
      vtt += `${index + 1}\n${start} --> ${end}\n${getSpeakerLabel(seg.speaker)}: ${seg.text}\n\n`;
    });

    downloadFile(vtt, `transcription_${jobId.slice(-8)}.vtt`, 'text/vtt');
  };

  const formatSRTTimestamp = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 1000);
    return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')},${ms.toString().padStart(3, '0')}`;
  };

  const formatVTTTimestamp = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 1000);
    return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(3, '0')}`;
  };

  const downloadFile = (content: string, filename: string, mimeType: string) => {
    const blob = new Blob([content], { type: mimeType });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  };

  if (isLoading) {
    return (
      <div className="bg-[#181818] border border-[#2A2A2A] rounded-xl shadow-lg p-8 flex items-center justify-center min-h-[400px]">
        <div className="flex items-center space-x-3">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#FF6B35]"></div>
          <span className="text-[#EAEAEA]/70">Loading transcription...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-[#181818] border border-[#2A2A2A] rounded-xl shadow-lg p-8">
        <div className="text-center">
          <FileText className="h-12 w-12 text-[#EAEAEA]/30 mx-auto mb-3" />
          <p className="text-red-400 mb-2">Error Loading Transcription</p>
          <p className="text-[#EAEAEA]/70 text-sm">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-[#181818] border border-[#2A2A2A] rounded-xl shadow-lg p-6">
      {/* Header with Search and Export */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <FileText className="h-6 w-6 text-[#FF6B35]" />
          <h3 className="text-lg font-semibold text-[#EAEAEA]">Transcription</h3>
          <span className="text-sm text-[#EAEAEA]/50">
            {filteredTranscription.length} segments
          </span>
        </div>

        <div className="flex items-center space-x-3">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-[#EAEAEA]/50" />
            <input
              type="text"
              placeholder="Search transcription..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-[#0A0A0A] border border-[#2A2A2A] rounded-lg pl-10 pr-4 py-2 text-sm text-[#EAEAEA] placeholder-[#EAEAEA]/30 focus:outline-none focus:border-[#FF6B35] w-64"
            />
          </div>

          {/* Export Buttons */}
          <div className="flex items-center space-x-2">
            <button
              onClick={exportAsText}
              className="flex items-center space-x-1 bg-[#2A2A2A] hover:bg-[#FF6B35] text-[#EAEAEA] px-3 py-2 rounded-lg text-sm transition-colors"
              title="Export as TXT"
            >
              <Download className="h-4 w-4" />
              <span>TXT</span>
            </button>
            <button
              onClick={exportAsSRT}
              className="flex items-center space-x-1 bg-[#2A2A2A] hover:bg-[#FF6B35] text-[#EAEAEA] px-3 py-2 rounded-lg text-sm transition-colors"
              title="Export as SRT (subtitles)"
            >
              <Download className="h-4 w-4" />
              <span>SRT</span>
            </button>
            <button
              onClick={exportAsVTT}
              className="flex items-center space-x-1 bg-[#2A2A2A] hover:bg-[#FF6B35] text-[#EAEAEA] px-3 py-2 rounded-lg text-sm transition-colors"
              title="Export as WebVTT"
            >
              <Download className="h-4 w-4" />
              <span>VTT</span>
            </button>
          </div>
        </div>
      </div>

      {/* Transcription Segments */}
      <div className="space-y-4 max-h-[600px] overflow-y-auto pr-2">
        {filteredTranscription.map((segment, index) => (
          <div
            key={index}
            className="bg-[#0A0A0A] border border-[#2A2A2A] rounded-lg p-4 hover:border-[#FF6B35]/30 transition-colors"
          >
            <div className="flex items-start space-x-3">
              {/* Timestamp */}
              <button
                onClick={() => handleTimestampClick(segment.timestamp)}
                className="flex items-center space-x-1 bg-[#FF6B35] hover:bg-[#FF8555] text-white px-2 py-1 rounded text-xs font-mono transition-colors flex-shrink-0"
                title="Click to seek audio"
              >
                <Clock className="h-3 w-3" />
                <span>{formatTimestamp(segment.timestamp)}</span>
              </button>

              {/* Speaker */}
              <div className="flex-shrink-0">
                {editingSpeaker === segment.speaker ? (
                  <input
                    type="text"
                    defaultValue={getSpeakerLabel(segment.speaker)}
                    autoFocus
                    onBlur={(e) => handleSpeakerEdit(segment.speaker, e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        handleSpeakerEdit(segment.speaker, e.currentTarget.value);
                      }
                      if (e.key === 'Escape') {
                        setEditingSpeaker(null);
                      }
                    }}
                    className="bg-[#181818] border border-[#FF6B35] rounded px-2 py-1 text-sm text-[#FF6B35] font-semibold w-24"
                  />
                ) : (
                  <button
                    onClick={() => setEditingSpeaker(segment.speaker)}
                    className="text-[#FF6B35] font-semibold text-sm hover:text-[#FF8555] transition-colors"
                    title="Click to edit speaker label"
                  >
                    {getSpeakerLabel(segment.speaker)}:
                  </button>
                )}
              </div>

              {/* Text */}
              <p className="text-[#EAEAEA] text-sm leading-relaxed flex-1">
                {segment.text}
              </p>
            </div>
          </div>
        ))}

        {filteredTranscription.length === 0 && searchQuery && (
          <div className="text-center py-12">
            <Search className="h-12 w-12 text-[#EAEAEA]/30 mx-auto mb-3" />
            <p className="text-[#EAEAEA]/70">No results found for "{searchQuery}"</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default TranscriptionViewer;
