"""
Video AI Operations Service
Implements AI-powered video editing operations for natural language interface
"""
import logging
import json
from typing import Dict, List, Any, Optional
from openai import OpenAI
from config import Config
from services.repeated_take_detector import RepeatedTakeDetector
from services.simple_audio_analyzer import SimpleAudioAnalyzer

logger = logging.getLogger(__name__)


class VideoAIOperations:
    """AI-powered video editing operations for conversational interface"""

    def __init__(self, job_data: Dict, transcription_data: Optional[Dict] = None):
        """
        Initialize Video AI Operations

        Args:
            job_data: Job data with video info and analysis results
            transcription_data: Transcription data with timestamps and speakers
        """
        self.job_data = job_data
        self.transcription = transcription_data or {}
        self.video_info = job_data.get('video_info', {})
        self.analysis = job_data.get('analysis', {})

        # Initialize OpenAI client for AI operations
        self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY) if Config.OPENAI_API_KEY else None

        if not self.openai_client:
            logger.warning("OpenAI API key not configured - some AI operations will be limited")

    # ==========================================
    # OPERATION 1: REMOVE REPEATED TAKES
    # ==========================================

    def remove_repeated_takes(self) -> Dict[str, Any]:
        """
        Remove repeated takes and false starts using RepeatedTakeDetector

        Returns:
            {
                'operation': 'remove_repeated_takes',
                'description': 'Found X repeated takes to remove',
                'segments': List of segments to keep,
                'segments_affected': Count of removed segments,
                'time_saved': Time saved in seconds,
                'new_duration': New video duration
            }
        """
        try:
            logger.info("Starting remove repeated takes operation")

            # Use RepeatedTakeDetector service
            detector = RepeatedTakeDetector()
            result = detector.detect_repeated_takes(
                self.transcription,
                self.video_info
            )

            # Extract keep segments
            segments_to_keep = [
                s for s in result['segments']
                if s['action'] == 'keep'
            ]

            segments_removed = len(result['segments']) - len(segments_to_keep)

            return {
                'operation': 'remove_repeated_takes',
                'description': f"Found {segments_removed} repeated takes and false starts to remove",
                'segments': segments_to_keep,
                'segments_affected': segments_removed,
                'time_saved': result['stats'].get('time_saved', 0),
                'new_duration': result['stats'].get('edited_duration', 0),
                'stats': result['stats'],
                'detected_patterns': result['detected_patterns']
            }

        except Exception as e:
            logger.error(f"Error in remove_repeated_takes: {e}")
            return {
                'operation': 'remove_repeated_takes',
                'description': f'Error: {str(e)}',
                'segments': [],
                'segments_affected': 0,
                'time_saved': 0,
                'new_duration': 0,
                'error': str(e)
            }

    # ==========================================
    # OPERATION 2: CREATE HIGHLIGHT REEL
    # ==========================================

    def create_highlight_reel(self, target_duration: int = 60) -> Dict[str, Any]:
        """
        Create highlight reel using GPT-4 to identify engaging segments

        Args:
            target_duration: Target duration in seconds (default 60s)

        Returns:
            {
                'operation': 'create_highlight',
                'description': 'Created 60s highlight reel',
                'segments': List of selected segments,
                'segments_affected': Number of segments,
                'time_saved': Time removed,
                'new_duration': New duration
            }
        """
        try:
            logger.info(f"Creating {target_duration}s highlight reel")

            if not self.openai_client:
                return {
                    'operation': 'create_highlight',
                    'description': 'OpenAI API key required for highlight reel creation',
                    'segments': [],
                    'segments_affected': 0,
                    'time_saved': 0,
                    'new_duration': 0,
                    'error': 'OpenAI API key not configured'
                }

            if not self.transcription:
                return {
                    'operation': 'create_highlight',
                    'description': 'Transcription required for highlight reel',
                    'segments': [],
                    'segments_affected': 0,
                    'time_saved': 0,
                    'new_duration': 0,
                    'error': 'No transcription available'
                }

            # Build transcript for analysis
            transcript = self._build_transcript(self.transcription)

            # Use GPT-4 to analyze and extract best segments
            selected_segments = self._analyze_for_highlights(
                transcript,
                target_duration,
                self.transcription
            )

            if not selected_segments:
                return {
                    'operation': 'create_highlight',
                    'description': f"Couldn't identify engaging segments for {target_duration}s reel",
                    'segments': [],
                    'segments_affected': 0,
                    'time_saved': 0,
                    'new_duration': 0
                }

            # Calculate stats
            total_duration = sum(seg['duration'] for seg in selected_segments)
            original_duration = self.video_info.get('duration', 0)

            return {
                'operation': 'create_highlight',
                'description': f"Created {target_duration}s highlight reel with {len(selected_segments)} segments",
                'segments': selected_segments,
                'segments_affected': len(selected_segments),
                'time_saved': original_duration - total_duration,
                'new_duration': total_duration,
                'target_duration': target_duration
            }

        except Exception as e:
            logger.error(f"Error in create_highlight_reel: {e}")
            return {
                'operation': 'create_highlight',
                'description': f'Error: {str(e)}',
                'segments': [],
                'segments_affected': 0,
                'time_saved': 0,
                'new_duration': 0,
                'error': str(e)
            }

    # ==========================================
    # OPERATION 3: REMOVE SILENCE
    # ==========================================

    def remove_silence(self, threshold_seconds: float = 2.0) -> Dict[str, Any]:
        """
        Remove silence longer than threshold using audio analysis

        Args:
            threshold_seconds: Minimum silence duration to remove (default 2.0s)

        Returns:
            {
                'operation': 'remove_silence',
                'description': 'Removed X silence gaps',
                'segments': List of segments to keep (silence removed),
                'segments_affected': Number of silence gaps removed,
                'time_saved': Time saved,
                'new_duration': New duration
            }
        """
        try:
            logger.info(f"Removing silence longer than {threshold_seconds}s")

            # Get audio file path from job_data
            audio_file = self.job_data.get('audio_file')

            if not audio_file:
                return {
                    'operation': 'remove_silence',
                    'description': 'Audio file required for silence removal',
                    'segments': [],
                    'segments_affected': 0,
                    'time_saved': 0,
                    'new_duration': 0,
                    'error': 'No audio file available'
                }

            # Use SimpleAudioAnalyzer to detect silence
            analyzer = SimpleAudioAnalyzer(audio_file)
            analysis = analyzer.analyze()

            # Extract speech segments (non-silence)
            speech_segments = analysis.get('speech_segments', [])

            if not speech_segments:
                return {
                    'operation': 'remove_silence',
                    'description': 'No speech segments detected',
                    'segments': [],
                    'segments_affected': 0,
                    'time_saved': 0,
                    'new_duration': 0
                }

            # Filter out segments separated by silence > threshold
            segments_to_keep = []
            silence_gaps_removed = 0
            time_saved = 0

            for i, segment in enumerate(speech_segments):
                # Check gap to next segment
                if i < len(speech_segments) - 1:
                    next_segment = speech_segments[i + 1]
                    gap_duration = next_segment['start'] - segment['end']

                    # If gap is longer than threshold, we're removing it
                    if gap_duration > threshold_seconds:
                        silence_gaps_removed += 1
                        time_saved += gap_duration

                # Add segment to keep list
                segments_to_keep.append({
                    'id': f"seg_{i}",
                    'start_time': segment['start'],
                    'end_time': segment['end'],
                    'duration': segment['end'] - segment['start'],
                    'text': '',  # No text for silence removal
                    'action': 'keep',
                    'reason': 'Speech detected'
                })

            # Calculate new duration
            new_duration = sum(seg['duration'] for seg in segments_to_keep)

            return {
                'operation': 'remove_silence',
                'description': f"Removed {silence_gaps_removed} silence gaps longer than {threshold_seconds}s",
                'segments': segments_to_keep,
                'segments_affected': silence_gaps_removed,
                'time_saved': round(time_saved, 2),
                'new_duration': round(new_duration, 2),
                'threshold': threshold_seconds
            }

        except Exception as e:
            logger.error(f"Error in remove_silence: {e}")
            return {
                'operation': 'remove_silence',
                'description': f'Error: {str(e)}',
                'segments': [],
                'segments_affected': 0,
                'time_saved': 0,
                'new_duration': 0,
                'error': str(e)
            }

    # ==========================================
    # OPERATION 4: FILTER BY SPEAKER
    # ==========================================

    def filter_by_speaker(self, speaker_id: str) -> Dict[str, Any]:
        """
        Keep only segments where specified speaker is talking

        Args:
            speaker_id: Speaker identifier (e.g., "Speaker 1", "1")

        Returns:
            {
                'operation': 'filter_speaker',
                'description': 'Kept only Speaker X',
                'segments': List of segments from that speaker,
                'segments_affected': Number of segments removed,
                'time_saved': Time from other speakers,
                'new_duration': New duration
            }
        """
        try:
            logger.info(f"Filtering for speaker: {speaker_id}")

            if not self.transcription:
                return {
                    'operation': 'filter_speaker',
                    'description': 'Transcription with speaker diarization required',
                    'segments': [],
                    'segments_affected': 0,
                    'time_saved': 0,
                    'new_duration': 0,
                    'error': 'No transcription available'
                }

            # Get transcript segments
            all_segments = self.transcription.get('segments', [])

            if not all_segments:
                return {
                    'operation': 'filter_speaker',
                    'description': 'No segments in transcription',
                    'segments': [],
                    'segments_affected': 0,
                    'time_saved': 0,
                    'new_duration': 0
                }

            # Normalize speaker ID (handle "Speaker 1" or just "1")
            speaker_id_normalized = speaker_id.lower().strip()
            if not speaker_id_normalized.startswith('speaker'):
                speaker_id_normalized = f"speaker {speaker_id_normalized}"

            # Filter segments by speaker
            speaker_segments = []
            for seg in all_segments:
                seg_speaker = seg.get('speaker', '').lower().strip()

                if seg_speaker == speaker_id_normalized or speaker_id_normalized in seg_speaker:
                    speaker_segments.append({
                        'id': f"seg_{len(speaker_segments)}",
                        'start_time': seg.get('start', 0),
                        'end_time': seg.get('end', 0),
                        'duration': seg.get('end', 0) - seg.get('start', 0),
                        'text': seg.get('text', ''),
                        'speaker': seg.get('speaker', ''),
                        'action': 'keep',
                        'reason': f'Speaker {speaker_id}'
                    })

            if not speaker_segments:
                return {
                    'operation': 'filter_speaker',
                    'description': f'No segments found for {speaker_id}',
                    'segments': [],
                    'segments_affected': 0,
                    'time_saved': 0,
                    'new_duration': 0
                }

            # Calculate stats
            original_duration = sum(seg.get('end', 0) - seg.get('start', 0) for seg in all_segments)
            new_duration = sum(seg['duration'] for seg in speaker_segments)
            segments_removed = len(all_segments) - len(speaker_segments)

            return {
                'operation': 'filter_speaker',
                'description': f"Kept only {speaker_id} - {len(speaker_segments)} segments",
                'segments': speaker_segments,
                'segments_affected': segments_removed,
                'time_saved': round(original_duration - new_duration, 2),
                'new_duration': round(new_duration, 2),
                'speaker': speaker_id
            }

        except Exception as e:
            logger.error(f"Error in filter_by_speaker: {e}")
            return {
                'operation': 'filter_speaker',
                'description': f'Error: {str(e)}',
                'segments': [],
                'segments_affected': 0,
                'time_saved': 0,
                'new_duration': 0,
                'error': str(e)
            }

    # ==========================================
    # OPERATION 5: SUGGEST CUT POINTS
    # ==========================================

    def suggest_cut_points(self) -> Dict[str, Any]:
        """
        Analyze pacing and suggest stylish cut points using GPT-4

        Returns:
            {
                'operation': 'suggest_cut_points',
                'description': 'Suggested X cut points',
                'cut_points': List of suggested cuts with timestamps and reasons,
                'segments_affected': Number of suggested cuts,
                'preview_data': Additional data for visualization
            }
        """
        try:
            logger.info("Analyzing pacing for cut point suggestions")

            if not self.openai_client:
                return {
                    'operation': 'suggest_cut_points',
                    'description': 'OpenAI API key required for cut point suggestions',
                    'cut_points': [],
                    'segments_affected': 0,
                    'error': 'OpenAI API key not configured'
                }

            if not self.transcription:
                return {
                    'operation': 'suggest_cut_points',
                    'description': 'Transcription required for pacing analysis',
                    'cut_points': [],
                    'segments_affected': 0,
                    'error': 'No transcription available'
                }

            # Build transcript for analysis
            transcript = self._build_transcript(self.transcription)

            # Use GPT-4 to analyze pacing
            cut_points = self._analyze_for_cut_points(transcript, self.transcription)

            return {
                'operation': 'suggest_cut_points',
                'description': f"Suggested {len(cut_points)} cut points for better pacing",
                'cut_points': cut_points,
                'segments_affected': len(cut_points),
                'preview_data': {
                    'cut_points': cut_points
                }
            }

        except Exception as e:
            logger.error(f"Error in suggest_cut_points: {e}")
            return {
                'operation': 'suggest_cut_points',
                'description': f'Error: {str(e)}',
                'cut_points': [],
                'segments_affected': 0,
                'error': str(e)
            }

    # ==========================================
    # HELPER METHODS
    # ==========================================

    def _build_transcript(self, transcription_data: Dict) -> str:
        """Build formatted transcript from transcription data"""
        segments = transcription_data.get('segments', [])
        if not segments:
            return transcription_data.get('transcript', '')

        transcript_parts = []
        for segment in segments:
            start = segment.get('start', 0)
            text = segment.get('text', '')
            speaker = segment.get('speaker', 'SPEAKER')
            transcript_parts.append(f"[{start:.1f}s] {speaker}: {text}")

        return "\n".join(transcript_parts)

    def _analyze_for_highlights(
        self,
        transcript: str,
        target_duration: int,
        transcription_data: Dict
    ) -> List[Dict]:
        """Use GPT-4 to analyze transcript and extract best segments"""
        try:
            # Calculate total duration
            segments = transcription_data.get('segments', [])
            total_duration = max(s.get('end', 0) for s in segments) if segments else 60

            # Truncate transcript if too long (keep first 10000 chars)
            transcript_for_analysis = transcript[:10000] if len(transcript) > 10000 else transcript

            prompt = f"""Analyze this video transcript and identify the BEST segments for a {target_duration}-second highlight reel.

TRANSCRIPT (Total duration: {total_duration:.1f}s):
{transcript_for_analysis}

Select 3-5 segments that are:
- Engaging and high-energy
- Self-contained (make sense without context)
- Emotionally impactful or valuable
- Total duration around {target_duration} seconds

Respond with ONLY a JSON array (no markdown):
[
  {{
    "start": 12.5,
    "end": 28.3,
    "text": "segment text",
    "reason": "Strong hook - curiosity builder",
    "engagement_score": 0.95
  }}
]"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You are an expert video editor. Respond ONLY with valid JSON array."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2048,
                temperature=0.1,
                timeout=90
            )

            response_text = response.choices[0].message.content.strip()

            # Remove markdown if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            segments = json.loads(response_text)

            # Add duration to each segment
            for seg in segments:
                seg['duration'] = seg['end'] - seg['start']
                seg['start_time'] = seg['start']
                seg['end_time'] = seg['end']
                seg['action'] = 'keep'

            return segments

        except Exception as e:
            logger.error(f"Error analyzing for highlights: {e}")
            return []

    def _analyze_for_cut_points(self, transcript: str, transcription_data: Dict) -> List[Dict]:
        """Use GPT-4 to analyze pacing and suggest cut points"""
        try:
            # Truncate transcript if too long
            transcript_for_analysis = transcript[:8000] if len(transcript) > 8000 else transcript

            prompt = f"""Analyze this video transcript for pacing and rhythm. Suggest optimal cut points for dynamic, engaging flow.

TRANSCRIPT:
{transcript_for_analysis}

Consider:
- Natural pauses (breath points)
- Topic transitions
- Energy shifts
- Sentence boundaries
- Beat/rhythm

Suggest 5-10 cut points with timestamps and reasons.

Respond with ONLY a JSON array (no markdown):
[
  {{
    "timestamp": 45.2,
    "reason": "Natural breath point after sentence",
    "confidence": 0.9
  }}
]"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You are an expert video editor. Respond ONLY with valid JSON array."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1024,
                temperature=0.2,
                timeout=60
            )

            response_text = response.choices[0].message.content.strip()

            # Remove markdown if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            cut_points = json.loads(response_text)

            return cut_points

        except Exception as e:
            logger.error(f"Error analyzing for cut points: {e}")
            return []
