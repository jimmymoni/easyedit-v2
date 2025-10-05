"""
Soniox Speech-to-Text REST API Client
Supports Malayalam, English, and 60+ languages with speaker diarization
Uses the new multilingual Soniox API (stt-async-preview model)
"""

import os
import time
import logging
import requests
from typing import Dict, Any, List, Optional

from config import Config

logger = logging.getLogger(__name__)


class SonioxClient:
    """Client for Soniox Speech-to-Text REST API with speaker diarization"""

    API_BASE_URL = "https://api.soniox.com"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.SONIOX_API_KEY

        # Initialize HTTP session with auth header
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {self.api_key}"
        self.session.headers["Content-Type"] = "application/json"

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

            # Step 1: Upload audio file
            file_id = self._upload_file(audio_file_path)
            logger.info(f"Audio uploaded, file_id: {file_id}")

            # Step 2: Create transcription job
            transcription_id = self._create_transcription(
                file_id=file_id,
                enable_speaker_diarization=enable_speaker_diarization
            )
            logger.info(f"Transcription created, transcription_id: {transcription_id}")

            # Step 3: Poll for completion
            self._wait_until_completed(transcription_id)
            logger.info("Transcription completed successfully")

            # Step 4: Get transcription result
            result = self._get_transcription_result(transcription_id)

            # Step 5: Clean up
            self._delete_transcription(transcription_id)
            self._delete_file(file_id)

            # Process and return structured result
            return self._process_transcription_result(result)

        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            raise

    def _upload_file(self, file_path: str) -> str:
        """Upload audio file and return file_id"""
        url = f"{self.API_BASE_URL}/v1/files"

        with open(file_path, 'rb') as f:
            files = {'file': f}
            # Remove Content-Type header for multipart upload
            headers = {k: v for k, v in self.session.headers.items() if k != 'Content-Type'}
            headers['Authorization'] = f"Bearer {self.api_key}"

            response = requests.post(url, files=files, headers=headers)
            response.raise_for_status()

        return response.json()['file_id']

    def _create_transcription(self, file_id: str, enable_speaker_diarization: bool) -> str:
        """Create transcription job and return transcription_id"""
        url = f"{self.API_BASE_URL}/v1/transcriptions"

        config = {
            "model": "stt-async-preview",  # Multilingual model
            "language_hints": ["en", "ml"],  # English and Malayalam
            "enable_language_identification": True,  # Auto-detect languages
            "enable_speaker_diarization": enable_speaker_diarization,
            "file_id": file_id
        }

        response = self.session.post(url, json=config)
        response.raise_for_status()

        return response.json()['transcription_id']

    def _wait_until_completed(self, transcription_id: str, timeout: int = 600) -> None:
        """Poll transcription status until completed or timeout"""
        url = f"{self.API_BASE_URL}/v1/transcriptions/{transcription_id}"

        start_time = time.time()
        while True:
            if time.time() - start_time > timeout:
                raise Exception(f"Transcription timed out after {timeout}s")

            response = self.session.get(url)
            response.raise_for_status()

            status_data = response.json()
            status = status_data.get('status')

            if status == 'completed':
                return
            elif status == 'failed':
                error = status_data.get('error', 'Unknown error')
                raise Exception(f"Transcription failed: {error}")

            logger.info(f"Transcription in progress... ({status})")
            time.sleep(2)

    def _get_transcription_result(self, transcription_id: str) -> Dict[str, Any]:
        """Get transcription result with tokens"""
        url = f"{self.API_BASE_URL}/v1/transcriptions/{transcription_id}/transcript"

        response = self.session.get(url)
        response.raise_for_status()

        return response.json()

    def _delete_transcription(self, transcription_id: str) -> None:
        """Delete transcription job"""
        try:
            url = f"{self.API_BASE_URL}/v1/transcriptions/{transcription_id}"
            self.session.delete(url)
        except Exception as e:
            logger.warning(f"Failed to delete transcription {transcription_id}: {e}")

    def _delete_file(self, file_id: str) -> None:
        """Delete uploaded file"""
        try:
            url = f"{self.API_BASE_URL}/v1/files/{file_id}"
            self.session.delete(url)
        except Exception as e:
            logger.warning(f"Failed to delete file {file_id}: {e}")

    def _process_transcription_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Process Soniox API result into structured format"""
        processed_result = {
            'transcript': '',
            'segments': [],
            'speakers': [],
            'duration': 0.0,
            'confidence': 0.0,
            'word_count': 0
        }

        try:
            tokens = result.get('tokens', [])
            if not tokens:
                logger.warning("No tokens in transcription result")
                return processed_result

            # Build full transcript and process tokens
            transcript_words = []
            current_segment = None
            current_speaker = None
            segment_words = []

            for token in tokens:
                text = token.get('text', '')
                speaker = token.get('speaker_id')
                start_ms = token.get('start_ms', 0)
                end_ms = start_ms + token.get('duration_ms', 0)
                confidence = token.get('confidence', 1.0)

                # Add to full transcript
                transcript_words.append(text)

                # Track unique speakers
                if speaker is not None and speaker not in processed_result['speakers']:
                    processed_result['speakers'].append(speaker)

                # Start new segment if speaker changes
                if speaker != current_speaker:
                    # Save previous segment
                    if current_segment:
                        current_segment['text'] = ' '.join(segment_words)
                        processed_result['segments'].append(current_segment)

                    # Start new segment
                    current_segment = {
                        'speaker': f"Speaker {speaker}" if speaker is not None else 'unknown',
                        'start_time': start_ms / 1000.0,
                        'end_time': end_ms / 1000.0,
                        'text': '',
                        'confidence': confidence,
                        'words': []
                    }
                    current_speaker = speaker
                    segment_words = []

                # Add token to current segment
                if current_segment:
                    current_segment['end_time'] = end_ms / 1000.0
                    current_segment['words'].append({
                        'text': text,
                        'start_time': start_ms / 1000.0,
                        'end_time': end_ms / 1000.0,
                        'confidence': confidence
                    })
                    segment_words.append(text)

            # Save final segment
            if current_segment:
                current_segment['text'] = ' '.join(segment_words)
                processed_result['segments'].append(current_segment)

            # Build final transcript
            processed_result['transcript'] = ' '.join(transcript_words)
            processed_result['word_count'] = len(transcript_words)

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
            # Try to access API base endpoint
            response = self.session.get(f"{self.API_BASE_URL}/v1/transcriptions", params={"limit": 1})
            return response.status_code in [200, 401]  # 200 OK or 401 means API is up
        except Exception as e:
            logger.error(f"Error checking Soniox API status: {str(e)}")
            return False
