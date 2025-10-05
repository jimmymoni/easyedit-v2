import requests
import json
import time
import os
from typing import Dict, Any, List, Optional
from config import Config
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

class SonioxClient:
    """Client for Soniox Speech-to-Text API with speaker diarization"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.SONIOX_API_KEY
        self.base_url = "https://api.soniox.com/transcribe-async"

        # Configure session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,  # 3 retries
            backoff_factor=2,  # 2s, 4s, 8s delays
            status_forcelist=[429, 500, 502, 503, 504],  # Retry on these HTTP codes
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # Set authorization header only - DO NOT set Content-Type
        # Content-Type must be set by requests for multipart/form-data uploads
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}'
        })

    def transcribe_audio(self, audio_file_path: str, enable_speaker_diarization: bool = True) -> Dict[str, Any]:
        """
        Transcribe audio file with optional speaker diarization
        Returns transcription with speaker labels and timestamps
        """
        try:
            # Start transcription job
            job_id = self._start_transcription_job(audio_file_path, enable_speaker_diarization)

            if not job_id:
                raise Exception("Failed to start transcription job")

            # Poll for completion
            result = self._poll_transcription_job(job_id)

            if not result:
                raise Exception("Failed to get transcription result")

            # Process and return structured result
            return self._process_transcription_result(result)

        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            raise

    def _start_transcription_job(self, audio_file_path: str, enable_speaker_diarization: bool) -> Optional[str]:
        """Start async transcription job"""
        try:
            # Check file size before upload
            file_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
            if file_size_mb > 500:  # Soniox limit
                raise Exception(f"Audio file too large: {file_size_mb:.1f}MB (max 500MB)")

            logger.info(f"Uploading audio file ({file_size_mb:.1f}MB) to Soniox API...")

            # Upload audio file
            with open(audio_file_path, 'rb') as audio_file:
                files = {'audio': audio_file}

                # Prepare transcription request
                request_data = {
                    'model': 'nova-2-general',
                    'language': ['en'],  # Can be expanded to include Malayalam
                    'include_speaker_diarization': enable_speaker_diarization,
                    'speaker_diarization_max_num_speakers': 10,
                    'include_profanity_filter': False,
                    'enable_global_speaker_diarization': True,
                    'enable_speaker_identification': False,
                    'profanity_filter': False
                }

                # Make request with timeout for large file uploads
                # timeout = (connect_timeout, read_timeout)
                # 30s to connect, 5 minutes (300s) to upload large files
                response = self.session.post(
                    self.base_url,
                    files=files,
                    data={'request': json.dumps(request_data)},
                    timeout=(30, 300)
                )

                if response.status_code == 200:
                    result = response.json()
                    job_id = result.get('id')
                    logger.info(f"Transcription job started successfully: {job_id}")
                    return job_id
                else:
                    error_msg = f"Soniox API error: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)

        except Exception as e:
            logger.error(f"Error starting transcription job: {str(e)}")
            raise  # Re-raise to propagate error details

    def _poll_transcription_job(self, job_id: str, max_wait_time: int = 600) -> Optional[Dict[str, Any]]:
        """Poll transcription job until completion"""
        status_url = f"https://api.soniox.com/transcribe-async/{job_id}"
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            try:
                response = self.session.get(status_url)

                if response.status_code == 200:
                    result = response.json()
                    status = result.get('status')

                    if status == 'COMPLETED':
                        return result
                    elif status == 'FAILED':
                        logger.error(f"Transcription job failed: {result.get('error', 'Unknown error')}")
                        return None
                    elif status in ['QUEUED', 'RUNNING']:
                        logger.info(f"Transcription job {job_id} status: {status}")
                        time.sleep(10)  # Wait 10 seconds before polling again
                    else:
                        logger.warning(f"Unknown job status: {status}")
                        time.sleep(10)
                else:
                    logger.error(f"Error polling job status: {response.status_code}")
                    time.sleep(10)

            except Exception as e:
                logger.error(f"Error polling transcription job: {str(e)}")
                time.sleep(10)

        logger.error(f"Transcription job {job_id} timed out after {max_wait_time} seconds")
        return None

    def _process_transcription_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Process raw transcription result into structured format"""
        processed_result = {
            'transcript': '',
            'segments': [],
            'speakers': [],
            'duration': 0.0,
            'confidence': 0.0,
            'word_count': 0
        }

        try:
            # Extract main transcript
            if 'transcript' in result:
                processed_result['transcript'] = result['transcript']

            # Extract segments with speaker information
            if 'words' in result:
                current_segment = None
                current_speaker = None
                segment_words = []

                for word in result['words']:
                    speaker = word.get('speaker')
                    start_time = word.get('start_ms', 0) / 1000.0  # Convert to seconds
                    end_time = word.get('end_ms', 0) / 1000.0
                    text = word.get('text', '')
                    confidence = word.get('confidence', 0.0)

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
                            'speaker': speaker,
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

                    processed_result['word_count'] += 1

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
            # Make a simple request to check API status
            response = self.session.get("https://api.soniox.com/transcribe-async")
            return response.status_code in [200, 401]  # 401 means API is accessible but auth issue
        except Exception as e:
            logger.error(f"Error checking Soniox API status: {str(e)}")
            return False