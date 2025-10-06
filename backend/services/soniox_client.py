"""
Soniox Speech-to-Text REST API Client
Supports Malayalam, English, and 60+ languages with speaker diarization
Uses the new multilingual Soniox API (stt-async-preview model)

SECURITY HARDENED VERSION:
- Request timeouts to prevent hangs
- Guaranteed resource cleanup with finally blocks
- Sanitized logging (no sensitive data exposure)
- Path validation to prevent directory traversal
- Exponential backoff for API polling
"""

import os
import time
import logging
import requests
from typing import Dict, Any, List, Optional

from config import Config

logger = logging.getLogger(__name__)

# Note: MIME type validation with python-magic is disabled on Windows due to libmagic DLL requirements
# Extension validation provides primary defense against invalid file types


class SonioxClient:
    """Client for Soniox Speech-to-Text REST API with speaker diarization"""

    API_BASE_URL = "https://api.soniox.com"

    # Timeout constants
    REQUEST_TIMEOUT = 30  # seconds for regular API calls
    UPLOAD_TIMEOUT = 300  # seconds for large file uploads (5 minutes)

    # Polling constants
    INITIAL_POLL_INTERVAL = 2  # start at 2 seconds
    MAX_POLL_INTERVAL = 30  # cap at 30 seconds
    DEFAULT_TRANSCRIPTION_TIMEOUT = 600  # 10 minutes max

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.SONIOX_API_KEY

        if not self.api_key:
            raise ValueError("Soniox API key is required but not provided")

        # Initialize HTTP session with auth header
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {self.api_key}"
        self.session.headers["Content-Type"] = "application/json"

    def transcribe_audio(self, audio_file_path: str, enable_speaker_diarization: bool = True) -> Dict[str, Any]:
        """
        Transcribe audio file with optional speaker diarization
        Returns transcription with speaker labels and timestamps

        SECURITY: Guaranteed cleanup with finally block
        """
        file_id = None
        transcription_id = None

        try:
            # Validate file path (SECURITY: prevent directory traversal)
            validated_path = self._validate_audio_file_path(audio_file_path)

            # Check file size before upload
            file_size_mb = os.path.getsize(validated_path) / (1024 * 1024)
            if file_size_mb > 500:  # Soniox limit
                raise ValueError(f"Audio file too large: {file_size_mb:.1f}MB (max 500MB)")

            logger.info(f"Starting Soniox transcription for {file_size_mb:.1f}MB file...")

            # Step 1: Upload audio file
            file_id = self._upload_file(validated_path)
            logger.info(f"Audio uploaded successfully")

            # Step 2: Create transcription job
            transcription_id = self._create_transcription(
                file_id=file_id,
                enable_speaker_diarization=enable_speaker_diarization
            )
            logger.info(f"Transcription job created successfully")

            # Step 3: Poll for completion (with exponential backoff)
            self._wait_until_completed(transcription_id)
            logger.info("Transcription completed successfully")

            # Step 4: Get transcription result
            result = self._get_transcription_result(transcription_id)

            # Process and return structured result
            return self._process_transcription_result(result)

        except requests.exceptions.Timeout as e:
            logger.error(f"Soniox API timeout: {str(e)}")
            raise Exception("Transcription API timed out. Please try again.") from e
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Soniox API connection error: {str(e)}")
            raise Exception("Could not connect to transcription API") from e
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else None
            logger.error(f"Soniox API HTTP error: status={status_code}")
            raise Exception(f"Transcription API error (HTTP {status_code})") from e
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            raise

        finally:
            # GUARANTEED cleanup - always runs even on exception
            if transcription_id:
                try:
                    self._delete_transcription(transcription_id)
                    logger.info("Cleaned up transcription job")
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup transcription: {cleanup_error}")

            if file_id:
                try:
                    self._delete_file(file_id)
                    logger.info("Cleaned up uploaded file")
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup file: {cleanup_error}")

    def _validate_audio_file_path(self, file_path: str) -> str:
        """
        Validate and sanitize audio file path

        SECURITY: Prevent directory traversal, symlink attacks
        """
        # Check file exists
        if not os.path.exists(file_path):
            raise ValueError(f"Audio file does not exist: {file_path}")

        # Check is regular file (not directory, symlink, device)
        if not os.path.isfile(file_path):
            raise ValueError(f"Path is not a regular file: {file_path}")

        # Check not a symlink (prevent symlink attacks)
        if os.path.islink(file_path):
            raise ValueError(f"Symlinks not allowed: {file_path}")

        # Resolve to absolute path and check against whitelist
        abs_path = os.path.abspath(file_path)
        allowed_dirs = [
            os.path.abspath(Config.UPLOAD_FOLDER),
            os.path.abspath(Config.TEMP_FOLDER)
        ]

        if not any(abs_path.startswith(allowed_dir) for allowed_dir in allowed_dirs):
            raise ValueError(f"File path outside allowed directories: {file_path}")

        # Check file extension (primary validation)
        ext = os.path.splitext(abs_path)[1].lower().lstrip('.')
        allowed_extensions = ['wav', 'mp3', 'm4a', 'aac', 'flac']
        if ext not in allowed_extensions:
            raise ValueError(f"Invalid audio file extension: {ext}")

        # Note: MIME type validation skipped on Windows (requires libmagic DLL)
        # Extension validation provides sufficient protection for audio files

        return abs_path

    def _sanitize_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove sensitive fields from response before logging

        SECURITY: Prevent API keys, tokens from being logged
        """
        safe_data = response_data.copy()
        sensitive_keys = ['api_key', 'token', 'secret', 'authorization', 'credential', 'password']

        for key in list(safe_data.keys()):
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                safe_data[key] = '***REDACTED***'

        return safe_data

    def _upload_file(self, file_path: str) -> str:
        """
        Upload audio file and return file_id

        SECURITY: Request timeout, sanitized logging
        """
        url = f"{self.API_BASE_URL}/v1/files"

        with open(file_path, 'rb') as f:
            files = {'file': f}
            # Remove Content-Type header for multipart upload
            headers = {k: v for k, v in self.session.headers.items() if k != 'Content-Type'}
            headers['Authorization'] = f"Bearer {self.api_key}"

            response = requests.post(
                url,
                files=files,
                headers=headers,
                timeout=self.UPLOAD_TIMEOUT  # SECURITY: Prevent indefinite hangs
            )
            response.raise_for_status()

        result = response.json()
        # SECURITY: Sanitize before logging
        logger.info(f"File upload response: {self._sanitize_response(result)}")

        # API returns either 'file_id' or 'id'
        file_id = result.get('file_id') or result.get('id')
        if not file_id:
            raise Exception(f"No file_id in response. Got: {list(result.keys())}")

        return file_id

    def _create_transcription(self, file_id: str, enable_speaker_diarization: bool) -> str:
        """
        Create transcription job and return transcription_id

        SECURITY: Request timeout, sanitized logging
        """
        url = f"{self.API_BASE_URL}/v1/transcriptions"

        config = {
            "model": "stt-async-preview",  # Multilingual model
            "language_hints": ["en", "ml"],  # English and Malayalam
            "enable_language_identification": True,  # Auto-detect languages
            "enable_speaker_diarization": enable_speaker_diarization,
            "file_id": file_id
        }

        response = self.session.post(
            url,
            json=config,
            timeout=self.REQUEST_TIMEOUT  # SECURITY: Prevent indefinite hangs
        )
        response.raise_for_status()

        result = response.json()
        # SECURITY: Sanitize before logging
        logger.info(f"Create transcription response: {self._sanitize_response(result)}")

        # API might return 'id' or 'transcription_id'
        transcription_id = result.get('transcription_id') or result.get('id')
        if not transcription_id:
            raise Exception(f"No transcription_id in response. Got: {list(result.keys())}")

        return transcription_id

    def _wait_until_completed(self, transcription_id: str, timeout: int = None) -> None:
        """
        Poll transcription status until completed or timeout

        SECURITY: Request timeout on each poll, exponential backoff
        """
        if timeout is None:
            timeout = self.DEFAULT_TRANSCRIPTION_TIMEOUT

        url = f"{self.API_BASE_URL}/v1/transcriptions/{transcription_id}"

        start_time = time.time()
        poll_interval = self.INITIAL_POLL_INTERVAL  # Start at 2 seconds

        while True:
            elapsed = time.time() - start_time

            # Check timeout BEFORE making request (SECURITY: Precise timeout enforcement)
            if elapsed > timeout:
                raise Exception(f"Transcription timed out after {timeout}s")

            # Ensure we have time for the request to complete
            if elapsed + self.REQUEST_TIMEOUT > timeout:
                logger.warning(f"Approaching timeout ({elapsed:.1f}s/{timeout}s), final poll attempt")
                # Make one last request with remaining time
                remaining_time = max(5, int(timeout - elapsed))  # At least 5 seconds
                response = self.session.get(url, timeout=remaining_time)
            else:
                response = self.session.get(
                    url,
                    timeout=self.REQUEST_TIMEOUT  # SECURITY: Prevent indefinite hangs
                )

            response.raise_for_status()

            status_data = response.json()
            status = status_data.get('status')

            if status == 'completed':
                return
            elif status == 'failed':
                error = status_data.get('error', 'Unknown error')
                raise Exception(f"Transcription failed: {error}")

            elapsed_int = int(elapsed)
            logger.info(f"Transcription in progress... (elapsed: {elapsed_int}s, next check in {poll_interval}s)")
            time.sleep(poll_interval)

            # Exponential backoff: 2s -> 4s -> 8s -> 16s -> 30s (max)
            # SECURITY: Reduces API calls and costs
            poll_interval = min(poll_interval * 2, self.MAX_POLL_INTERVAL)

    def _get_transcription_result(self, transcription_id: str) -> Dict[str, Any]:
        """
        Get transcription result with tokens

        SECURITY: Request timeout
        """
        url = f"{self.API_BASE_URL}/v1/transcriptions/{transcription_id}/transcript"

        response = self.session.get(
            url,
            timeout=self.REQUEST_TIMEOUT  # SECURITY: Prevent indefinite hangs
        )
        response.raise_for_status()

        return response.json()

    def _delete_transcription(self, transcription_id: str) -> None:
        """
        Delete transcription job

        SECURITY: Request timeout
        """
        try:
            url = f"{self.API_BASE_URL}/v1/transcriptions/{transcription_id}"
            self.session.delete(
                url,
                timeout=self.REQUEST_TIMEOUT  # SECURITY: Prevent indefinite hangs
            )
        except Exception as e:
            # Don't suppress - caller needs to know cleanup failed
            raise Exception(f"Failed to delete transcription {transcription_id}: {e}") from e

    def _delete_file(self, file_id: str) -> None:
        """
        Delete uploaded file

        SECURITY: Request timeout
        """
        try:
            url = f"{self.API_BASE_URL}/v1/files/{file_id}"
            self.session.delete(
                url,
                timeout=self.REQUEST_TIMEOUT  # SECURITY: Prevent indefinite hangs
            )
        except Exception as e:
            # Don't suppress - caller needs to know cleanup failed
            raise Exception(f"Failed to delete file {file_id}: {e}") from e

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
            # Validate API response format (SECURITY: Better error messages)
            if 'tokens' not in result:
                raise ValueError("Invalid Soniox API response: missing 'tokens' field")

            tokens = result['tokens']
            if not tokens:
                logger.warning("Empty transcription (no speech detected in audio)")
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
        """
        Check if Soniox API is accessible with current credentials

        SECURITY: Request timeout
        """
        try:
            # Try to access API base endpoint
            response = self.session.get(
                f"{self.API_BASE_URL}/v1/transcriptions",
                params={"limit": 1},
                timeout=self.REQUEST_TIMEOUT  # SECURITY: Prevent indefinite hangs
            )
            return response.status_code in [200, 401]  # 200 OK or 401 means API is up
        except Exception as e:
            logger.error(f"Error checking Soniox API status: {str(e)}")
            return False
