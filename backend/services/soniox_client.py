"""
Soniox Speech-to-Text API Client using Official SDK
Supports Malayalam, English, and code-switching with speaker diarization
"""

import os
import time
import logging
from typing import Dict, Any, List, Optional

from soniox.speech_service import SpeechClient
from soniox.transcribe_file_async import transcribe_file_async, FileSource
from config import Config

logger = logging.getLogger(__name__)


class SonioxClient:
    """Client for Soniox Speech-to-Text API with speaker diarization using official SDK"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.SONIOX_API_KEY

        # Initialize official Soniox client
        self.client = SpeechClient(api_key=self.api_key)

    def transcribe_audio(self, audio_file_path: str, enable_speaker_diarization: bool = True) -> Dict[str, Any]:
        """
        Transcribe audio file with optional speaker diarization
        Returns transcription with speaker labels and timestamps
        """
        try:
            # Check file size before upload
            file_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
            if file_size_mb > 500:  # Soniox limit
                raise Exception(f"Audio file too large: {file_size_mb:.1f}MB (max 500MB)")

            logger.info(f"Starting Soniox transcription for {file_size_mb:.1f}MB file...")

            # Create file source
            file_source = FileSource(path=audio_file_path)

            # Transcribe using official SDK
            # This handles upload, processing, and polling automatically
            result = transcribe_file_async(
                file_source=file_source,
                api_key=self.api_key,
                model="nova-2-general",  # Best multilingual model
                enable_speaker_diarization=enable_speaker_diarization,
                max_num_speakers=10,
                enable_global_speaker_diarization=True,
                language=["en", "ml"],  # English and Malayalam
                enable_profanity_filter=False,
            )

            logger.info(f"Transcription completed successfully")

            # Process and return structured result
            return self._process_transcription_result(result)

        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            raise

    def _process_transcription_result(self, result) -> Dict[str, Any]:
        """Process Soniox SDK result into structured format"""
        processed_result = {
            'transcript': '',
            'segments': [],
            'speakers': [],
            'duration': 0.0,
            'confidence': 0.0,
            'word_count': 0
        }

        try:
            # Extract full transcript
            if hasattr(result, 'words') and result.words:
                # Build full transcript from words
                transcript_words = [word.text for word in result.words]
                processed_result['transcript'] = ' '.join(transcript_words)
                processed_result['word_count'] = len(result.words)

                # Process words into speaker segments
                current_segment = None
                current_speaker = None
                segment_words = []

                for word in result.words:
                    speaker = word.speaker if hasattr(word, 'speaker') else None
                    start_time = word.start_ms / 1000.0 if hasattr(word, 'start_ms') else 0.0
                    end_time = word.end_ms / 1000.0 if hasattr(word, 'end_ms') else 0.0
                    text = word.text
                    confidence = word.confidence if hasattr(word, 'confidence') else 1.0

                    # Track unique speakers
                    if speaker and speaker not in processed_result['speakers']:
                        processed_result['speakers'].append(speaker)

                    # Start new segment if speaker changes
                    if speaker != current_speaker:
                        # Save previous segment
                        if current_segment:
                            current_segment['text'] = ' '.join(segment_words)
                            processed_result['segments'].append(current_segment)

                        # Start new segment
                        current_segment = {
                            'speaker': speaker or 'unknown',
                            'start_time': start_time,
                            'end_time': end_time,
                            'text': '',
                            'confidence': confidence,
                            'words': []
                        }
                        current_speaker = speaker
                        segment_words = []

                    # Add word to current segment
                    if current_segment:
                        current_segment['end_time'] = end_time
                        current_segment['words'].append({
                            'text': text,
                            'start_time': start_time,
                            'end_time': end_time,
                            'confidence': confidence
                        })
                        segment_words.append(text)

                # Save final segment
                if current_segment:
                    current_segment['text'] = ' '.join(segment_words)
                    processed_result['segments'].append(current_segment)

            # Calculate overall statistics
            if processed_result['segments']:
                last_segment = processed_result['segments'][-1]
                processed_result['duration'] = last_segment['end_time']

                # Average confidence
                total_confidence = sum(seg['confidence'] for seg in processed_result['segments'])
                processed_result['confidence'] = total_confidence / len(processed_result['segments'])

            logger.info(
                f"Processed transcription: {processed_result['word_count']} words, "
                f"{len(processed_result['speakers'])} speakers, "
                f"{processed_result['duration']:.1f}s duration"
            )

            return processed_result

        except Exception as e:
            logger.error(f"Error processing transcription result: {str(e)}")
            return processed_result

    def get_speaker_segments(self, transcription_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract speaker change points from transcription result"""
        speaker_segments = []

        for segment in transcription_result.get('segments', []):
            speaker_segments.append({
                'speaker': segment['speaker'],
                'start_time': segment['start_time'],
                'end_time': segment['end_time'],
                'duration': segment['end_time'] - segment['start_time'],
                'text': segment['text'],
                'word_count': len(segment['words']),
                'confidence': segment['confidence']
            })

        return speaker_segments

    def get_silence_detection_hints(self, transcription_result: Dict[str, Any], min_gap_seconds: float = 2.0) -> List[Dict[str, Any]]:
        """Identify potential silence gaps from transcription timing"""
        silence_gaps = []
        segments = transcription_result.get('segments', [])

        for i in range(len(segments) - 1):
            current_end = segments[i]['end_time']
            next_start = segments[i + 1]['start_time']
            gap_duration = next_start - current_end

            if gap_duration >= min_gap_seconds:
                silence_gaps.append({
                    'start_time': current_end,
                    'end_time': next_start,
                    'duration': gap_duration,
                    'type': 'speech_gap'
                })

        return silence_gaps

    def check_api_status(self) -> bool:
        """Check if Soniox API is accessible with current credentials"""
        try:
            # Try to initialize client - if API key is valid, this should work
            test_client = SpeechClient(api_key=self.api_key)
            return True
        except Exception as e:
            logger.error(f"Error checking Soniox API status: {str(e)}")
            return False
