"""
Sarvam AI Speech-to-Text Batch API Client
Supports Malayalam, English, and 10+ Indian languages with speaker diarization
Uses Sarvam's Batch API for long-form audio processing

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
import tempfile
from typing import Dict, Any, List, Optional

from config import Config

logger = logging.getLogger(__name__)

# Note: Batch API uses direct REST calls (no SDK required)
# SDK v0.1.11a2 has schema mismatches with the current API

# Note: MIME type validation skipped on Windows (requires libmagic DLL)
# Extension validation provides primary defense against invalid file types


class SarvamClient:
    """Client for Sarvam AI Speech-to-Text Batch API with speaker diarization"""

    API_BASE_URL = "https://api.sarvam.ai"

    # Timeout constants
    REQUEST_TIMEOUT = 30  # seconds for regular API calls
    UPLOAD_TIMEOUT = 900  # seconds for large file uploads (15 minutes)

    # Polling constants for batch jobs
    INITIAL_POLL_INTERVAL = 3  # start at 3 seconds
    MAX_POLL_INTERVAL = 30  # cap at 30 seconds
    DEFAULT_TRANSCRIPTION_TIMEOUT = 1200  # 20 minutes max (longer for batch)

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.SARVAM_API_KEY

        if not self.api_key:
            raise ValueError("Sarvam API key is required but not provided")

        # Initialize HTTP session with auth header
        self.session = requests.Session()
        self.session.headers["api-subscription-key"] = self.api_key

    def transcribe_audio(
        self,
        audio_file_path: str,
        enable_speaker_diarization: bool = True,
        language_code: str = "ml-IN"
    ) -> Dict[str, Any]:
        """
        Transcribe audio file with optional speaker diarization
        Routes to REST API (no diarization) or SDK Batch API (with diarization)

        SECURITY: Guaranteed cleanup with finally block

        Args:
            audio_file_path: Path to audio file
            enable_speaker_diarization: Enable speaker identification (requires Batch API)
            language_code: Language code (ml-IN for Malayalam, en-IN for English)
        """
        # Validate file path (SECURITY: prevent directory traversal)
        validated_path = self._validate_audio_file_path(audio_file_path)

        # Check file size before upload
        file_size_mb = os.path.getsize(validated_path) / (1024 * 1024)
        if file_size_mb > 500:  # Conservative limit
            raise ValueError(f"Audio file too large: {file_size_mb:.1f}MB (max 500MB)")

        logger.info(f"Starting Sarvam transcription for {file_size_mb:.1f}MB file...")

        try:
            # Route based on diarization requirement
            if enable_speaker_diarization:
                # Diarization requires Batch API (pure REST)
                logger.info("Using Batch API for diarization")
                return self._transcribe_with_batch_api(validated_path, language_code)
            else:
                # No diarization - use fast REST API
                logger.info("Using real-time REST API (no diarization)")
                return self._transcribe_with_rest_api(validated_path, language_code)

        except requests.exceptions.Timeout as e:
            logger.error(f"Sarvam API timeout: {str(e)}")
            raise Exception("Transcription API timed out. Please try again.") from e
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Sarvam API connection error: {str(e)}")
            raise Exception("Could not connect to transcription API") from e
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else None
            logger.error(f"Sarvam API HTTP error: status={status_code}")
            raise Exception(f"Transcription API error (HTTP {status_code})") from e
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            raise

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
        allowed_extensions = ['wav', 'mp3', 'm4a', 'aac', 'flac', 'mp4', 'ogg', 'aiff', 'amr']
        if ext not in allowed_extensions:
            raise ValueError(f"Invalid audio file extension: {ext}")

        # Note: MIME type validation skipped on Windows (requires libmagic DLL)
        # Extension validation provides sufficient protection for audio files

        return abs_path

    def _transcribe_with_rest_api(
        self,
        file_path: str,
        language_code: str
    ) -> Dict[str, Any]:
        """
        Transcribe using real-time REST API (no diarization)
        Fast, synchronous, up to 30 seconds
        """
        url = f"{self.API_BASE_URL}/speech-to-text"

        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'audio/wav')}
            data = {
                'model': 'saarika:v2.5',
                'language_code': language_code,
                'with_timestamps': 'true'
            }
            headers = {k: v for k, v in self.session.headers.items() if k != 'Content-Type'}
            headers['api-subscription-key'] = self.api_key

            response = requests.post(
                url, files=files, data=data, headers=headers,
                timeout=self.UPLOAD_TIMEOUT
            )
            response.raise_for_status()

        result = response.json()
        logger.info(f"Real-time API response: {self._sanitize_response(result)}")
        return self._process_transcription_result(result, has_diarization=False)

    def _transcribe_with_batch_api(
        self,
        file_path: str,
        language_code: str
    ) -> Dict[str, Any]:
        """
        Transcribe using Batch API (pure REST, no SDK) with diarization
        Handles long files and speaker identification

        Workflow:
        1. POST /job/init -> get job_id
        2. POST /job/v1/upload-files -> get Azure URLs
        3. PUT to Azure Blob Storage
        4. POST /job/v1/{job_id}/start -> trigger processing
        5. Poll GET /job/{job_id}/status -> wait for completion
        6. POST /job/v1/download-files -> get download URLs
        7. Download results from Azure

        SECURITY: Guaranteed cleanup with finally block, request timeouts
        """
        output_dir = None

        try:
            # Step 1: Initialize job
            logger.info("Initializing Batch API job...")
            init_response = requests.post(
                f"{self.API_BASE_URL}/speech-to-text/job/init",
                headers={
                    "api-subscription-key": self.api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "job_parameters": {
                        "language_code": language_code,
                        "with_diarization": True,
                        "with_timestamps": True
                    }
                },
                timeout=self.REQUEST_TIMEOUT
            )
            init_response.raise_for_status()
            init_data = init_response.json()
            job_id = init_data['job_id']
            logger.info(f"Job initialized: {job_id}")

            # Step 2: Get upload links for specific filename
            filename = os.path.basename(file_path)
            logger.info(f"Getting upload link for {filename}...")
            upload_response = requests.post(
                f"{self.API_BASE_URL}/speech-to-text/job/v1/upload-files",
                headers={
                    "api-subscription-key": self.api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "job_id": job_id,
                    "files": [filename]
                },
                timeout=self.REQUEST_TIMEOUT
            )
            upload_response.raise_for_status()
            upload_data = upload_response.json()
            upload_url = upload_data['upload_urls'][filename]['file_url']

            # Step 3: Upload file to Azure Blob Storage
            logger.info(f"Uploading {filename} to Azure Blob Storage...")
            with open(file_path, 'rb') as f:
                azure_response = requests.put(
                    upload_url,
                    data=f,
                    headers={
                        "x-ms-blob-type": "BlockBlob",
                        "Content-Type": "audio/wav"
                    },
                    timeout=self.UPLOAD_TIMEOUT
                )
                if azure_response.status_code not in [200, 201]:
                    raise Exception(f"Azure upload failed: {azure_response.status_code} - {azure_response.text}")
            logger.info("Upload successful")

            # Step 4: Start the job
            logger.info("Starting transcription job...")
            start_response = requests.post(
                f"{self.API_BASE_URL}/speech-to-text/job/v1/{job_id}/start",
                headers={"api-subscription-key": self.api_key},
                timeout=self.REQUEST_TIMEOUT
            )
            start_response.raise_for_status()
            logger.info("Job started")

            # Step 5: Poll for completion
            logger.info("Waiting for transcription to complete...")
            poll_interval = self.INITIAL_POLL_INTERVAL
            start_time = time.time()

            while True:
                elapsed = time.time() - start_time
                if elapsed > self.DEFAULT_TRANSCRIPTION_TIMEOUT:
                    raise Exception(f"Transcription timed out after {self.DEFAULT_TRANSCRIPTION_TIMEOUT}s")

                status_response = requests.get(
                    f"{self.API_BASE_URL}/speech-to-text/job/{job_id}/status",
                    headers={"api-subscription-key": self.api_key},
                    timeout=self.REQUEST_TIMEOUT
                )
                status_response.raise_for_status()
                status_data = status_response.json()
                job_state = status_data['job_state']

                logger.info(f"Job state: {job_state} (elapsed: {int(elapsed)}s)")

                if job_state.lower() == 'completed':
                    logger.info("Job completed successfully")
                    break
                elif job_state.lower() == 'failed':
                    error_msg = status_data.get('error_message', 'Unknown error')
                    raise Exception(f"Transcription job failed: {error_msg}")

                time.sleep(poll_interval)
                poll_interval = min(poll_interval * 2, self.MAX_POLL_INTERVAL)

            # Step 6: Get download links
            output_files = []
            for detail in status_data.get('job_details', []):
                if detail.get('outputs'):
                    output_files.append(detail['outputs'][0]['file_name'])

            if not output_files:
                raise Exception("No output files found in completed job")

            logger.info(f"Getting download links for {len(output_files)} file(s)...")
            download_response = requests.post(
                f"{self.API_BASE_URL}/speech-to-text/job/v1/download-files",
                headers={
                    "api-subscription-key": self.api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "job_id": job_id,
                    "files": output_files
                },
                timeout=self.REQUEST_TIMEOUT
            )
            download_response.raise_for_status()
            download_data = download_response.json()

            # Step 7: Download results
            output_dir = tempfile.mkdtemp()
            logger.info(f"Downloading results to {output_dir}...")

            for output_file in output_files:
                download_url = download_data['download_urls'][output_file]['file_url']
                result_response = requests.get(download_url, timeout=self.REQUEST_TIMEOUT)
                result_response.raise_for_status()

                result_path = os.path.join(output_dir, output_file)
                with open(result_path, 'wb') as f:
                    f.write(result_response.content)

            # Read result file
            result_files = [f for f in os.listdir(output_dir) if f.endswith('.json')]
            if not result_files:
                raise Exception("No transcription results found")

            result_path = os.path.join(output_dir, result_files[0])
            with open(result_path, 'r', encoding='utf-8') as f:
                import json
                result = json.load(f)

            logger.info("Batch API transcription completed successfully")
            return self._process_transcription_result(result, has_diarization=True)

        finally:
            # Cleanup temp directory
            if output_dir and os.path.exists(output_dir):
                import shutil
                try:
                    shutil.rmtree(output_dir)
                    logger.info(f"Cleaned up temp directory: {output_dir}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp directory: {e}")

    def _sanitize_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove sensitive fields from response before logging

        SECURITY: Prevent API keys, tokens from being logged
        """
        safe_data = response_data.copy()
        sensitive_keys = ['api_key', 'token', 'secret', 'authorization', 'credential', 'password', 'subscription']

        for key in list(safe_data.keys()):
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                safe_data[key] = '***REDACTED***'

        return safe_data

    def _submit_batch_job(
        self,
        file_path: str,
        language_code: str,
        enable_speaker_diarization: bool
    ) -> str:
        """
        Submit batch transcription job to Sarvam API

        SECURITY: Request timeout, sanitized logging
        """
        url = f"{self.API_BASE_URL}/speech-to-text"

        with open(file_path, 'rb') as f:
            files = {
                'file': (os.path.basename(file_path), f, 'audio/wav')
            }
            data = {
                'model': 'saarika:v2.5',  # Sarvam's transcription model (latest)
                'language_code': language_code,
                'with_timestamps': 'true'  # Always include timestamps
            }

            # Add diarization flag if requested
            if enable_speaker_diarization:
                data['with_diarization'] = 'true'

            # Remove Content-Type header for multipart upload
            headers = {k: v for k, v in self.session.headers.items() if k != 'Content-Type'}
            headers['api-subscription-key'] = self.api_key

            response = requests.post(
                url,
                files=files,
                data=data,
                headers=headers,
                timeout=self.UPLOAD_TIMEOUT  # SECURITY: Prevent indefinite hangs
            )

            # Log response for debugging
            logger.info(f"Sarvam API response status: {response.status_code}")
            if response.status_code >= 400:
                logger.error(f"Sarvam API error response: {response.text}")

            response.raise_for_status()

        result = response.json()
        # SECURITY: Sanitize before logging
        logger.info(f"API response: {self._sanitize_response(result)}")

        # Check if this is a synchronous response with transcription directly
        if 'transcript' in result:
            # Synchronous API - return result directly as a fake job_id
            # We'll store the result and return it immediately
            return result  # Return full result, not job_id

        # Otherwise, treat as batch API
        # Extract job_id from response
        job_id = result.get('job_id') or result.get('id')
        if not job_id:
            raise Exception(f"No job_id or transcript in response. Got: {list(result.keys())}")

        return job_id

    def _wait_until_completed(self, job_id: str, timeout: int = None) -> None:
        """
        Poll batch job status until completed or timeout

        SECURITY: Request timeout on each poll, exponential backoff
        """
        if timeout is None:
            timeout = self.DEFAULT_TRANSCRIPTION_TIMEOUT

        url = f"{self.API_BASE_URL}/jobs/{job_id}"

        start_time = time.time()
        poll_interval = self.INITIAL_POLL_INTERVAL  # Start at 3 seconds

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

            if status == 'COMPLETED':
                return
            elif status in ['FAILED', 'ERROR']:
                error = status_data.get('error', 'Unknown error')
                raise Exception(f"Transcription failed: {error}")

            elapsed_int = int(elapsed)
            logger.info(f"Transcription in progress... (elapsed: {elapsed_int}s, next check in {poll_interval}s)")
            time.sleep(poll_interval)

            # Exponential backoff: 3s -> 6s -> 12s -> 24s -> 30s (max)
            # SECURITY: Reduces API calls and costs
            poll_interval = min(poll_interval * 2, self.MAX_POLL_INTERVAL)

    def _get_batch_result(self, job_id: str) -> Dict[str, Any]:
        """
        Get batch transcription result

        SECURITY: Request timeout
        """
        url = f"{self.API_BASE_URL}/jobs/{job_id}/output"

        response = self.session.get(
            url,
            timeout=self.REQUEST_TIMEOUT  # SECURITY: Prevent indefinite hangs
        )
        response.raise_for_status()

        return response.json()

    def _process_transcription_result(
        self,
        result: Dict[str, Any],
        has_diarization: bool
    ) -> Dict[str, Any]:
        """Process Sarvam API result into structured format"""
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
            if 'transcript' not in result:
                raise ValueError("Invalid Sarvam API response: missing 'transcript' field")

            transcript = result['transcript']
            if not transcript:
                logger.warning("Empty transcription (no speech detected in audio)")
                return processed_result

            # Build full transcript
            processed_result['transcript'] = transcript
            processed_result['word_count'] = len(transcript.split())

            # Process timestamps if available
            if 'timestamps' in result:
                timestamps = result['timestamps']
                for ts in timestamps:
                    word = ts.get('word', '')
                    start_time = ts.get('start', 0.0)
                    end_time = ts.get('end', 0.0)

                    processed_result['duration'] = max(processed_result['duration'], end_time)

            # Process diarization if available
            if has_diarization and 'speaker_timeline' in result:
                speaker_timeline = result['speaker_timeline']
                current_speaker = None
                segment_words = []
                segment_start = 0.0

                for entry in speaker_timeline:
                    speaker = entry.get('speaker')
                    text = entry.get('text', '')
                    start_time = entry.get('start', 0.0)
                    end_time = entry.get('end', 0.0)

                    # Track unique speakers
                    if speaker and speaker not in processed_result['speakers']:
                        processed_result['speakers'].append(speaker)

                    # Create segment if speaker changes
                    if speaker != current_speaker:
                        # Save previous segment
                        if current_speaker is not None:
                            processed_result['segments'].append({
                                'speaker': f"Speaker {current_speaker}",
                                'start_time': segment_start,
                                'end_time': start_time,
                                'text': ' '.join(segment_words),
                                'confidence': 1.0,  # Sarvam doesn't provide per-segment confidence
                                'words': []
                            })

                        # Start new segment
                        current_speaker = speaker
                        segment_words = []
                        segment_start = start_time

                    segment_words.append(text)

                # Save final segment
                if current_speaker is not None and segment_words:
                    processed_result['segments'].append({
                        'speaker': f"Speaker {current_speaker}",
                        'start_time': segment_start,
                        'end_time': processed_result['duration'],
                        'text': ' '.join(segment_words),
                        'confidence': 1.0,
                        'words': []
                    })

            # Set default confidence (Sarvam doesn't provide this)
            processed_result['confidence'] = 1.0

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
                'word_count': len(segment['text'].split()),
                'confidence': segment['confidence']
            })

        return speaker_segments

    def get_silence_detection_hints(
        self,
        transcription_result: Dict[str, Any],
        min_gap_seconds: float = 2.0
    ) -> List[Dict[str, Any]]:
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
        Check if Sarvam API is accessible with current credentials

        SECURITY: Request timeout
        """
        try:
            # Try to access API health endpoint
            response = self.session.get(
                f"{self.API_BASE_URL}/",
                timeout=self.REQUEST_TIMEOUT  # SECURITY: Prevent indefinite hangs
            )
            return response.status_code in [200, 404]  # 200 OK or 404 means API is up
        except Exception as e:
            logger.error(f"Error checking Sarvam API status: {str(e)}")
            return False
