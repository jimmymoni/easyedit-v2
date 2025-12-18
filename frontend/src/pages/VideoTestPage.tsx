import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import VideoPlayerWithTimelineExample from '../components/video/player/VideoPlayerWithTimelineExample';

/**
 * VideoTestPage - Simple test page to verify Video Player + Timeline
 *
 * Route: /video-test/:jobId
 * Purpose: Visual verification of Phase 2.1 + 2.2.2 integration
 */
const VideoTestPage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();

  if (!jobId) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl text-white mb-4">Missing Job ID</h1>
          <p className="text-gray-400 mb-4">
            Usage: /video-test/YOUR_JOB_ID
          </p>
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 bg-[#FF6B35] text-white rounded"
          >
            Go Home
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black">
      {/* Header */}
      <div className="border-b border-gray-800 bg-[#181818]">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center">
          <button
            onClick={() => navigate('/')}
            className="mr-4 p-2 hover:bg-gray-700 rounded transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-gray-400" />
          </button>
          <h1 className="text-xl font-bold text-white">
            Video Editor Test - Phase 2.1 + 2.2.2
          </h1>
          <div className="ml-auto">
            <span className="text-sm text-gray-400 font-mono">
              Job ID: {jobId}
            </span>
          </div>
        </div>
      </div>

      {/* Video Player + Timeline */}
      <VideoPlayerWithTimelineExample jobId={jobId} />
    </div>
  );
};

export default VideoTestPage;
