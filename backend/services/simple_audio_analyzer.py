import numpy as np
from scipy.io import wavfile
from scipy import signal
from typing import List, Dict, Any, Optional
import logging
import os
import threading

logger = logging.getLogger(__name__)

class SimpleAudioAnalyzer:
    """
    SECURITY HARDENED: Simplified audio analysis module using scipy and numpy

    Supports context manager pattern for guaranteed cleanup:
        with SimpleAudioAnalyzer() as analyzer:
            analyzer.load_audio('file.mp3')
            # ... analysis code ...
        # Automatic cleanup happens here
    """

    # SECURITY: Global tracking of converted files with thread safety
    _all_converted_files = set()
    _converted_files_lock = threading.Lock()

    def __init__(self):
        self.audio_data = None
        self.duration = 0.0
        self.file_path = None
        self.sample_rate = 22050
        self.original_sample_rate = None
        self.converted_file_path = None  # Track converted files for cleanup
        self._memory_usage_mb = 0

    def load_audio(self, file_path: str, target_sr: int = 22050) -> bool:
        """Load audio file for analysis using scipy (supports WAV, MP3, M4A, AAC, FLAC via conversion)"""
        try:
            self.file_path = file_path
            working_file_path = file_path

            # Check if format conversion is needed
            if not file_path.lower().endswith('.wav'):
                logger.info(f"Non-WAV format detected, converting to WAV: {file_path}")

                from services.audio_converter import get_converter
                converter = get_converter()

                # Convert to WAV
                success, wav_path, error_msg = converter.convert_to_wav(file_path)

                if not success:
                    logger.error(f"Failed to convert audio file: {error_msg}")
                    return False

                # Use the converted WAV file for analysis
                working_file_path = wav_path
                self.converted_file_path = wav_path

                # SECURITY: Track globally for emergency cleanup
                with self._converted_files_lock:
                    self._all_converted_files.add(wav_path)

                logger.info(f"Audio converted successfully: {wav_path}")

            # Load audio using scipy.io.wavfile
            self.original_sample_rate, audio_data = wavfile.read(working_file_path)

            # Convert to float and normalize
            if audio_data.dtype == np.int16:
                audio_data = audio_data.astype(np.float32) / 32768.0
            elif audio_data.dtype == np.int32:
                audio_data = audio_data.astype(np.float32) / 2147483648.0
            elif audio_data.dtype == np.uint8:
                audio_data = (audio_data.astype(np.float32) - 128) / 128.0

            # Convert stereo to mono if needed
            if len(audio_data.shape) > 1:
                audio_data = np.mean(audio_data, axis=1)

            # Resample if needed
            if self.original_sample_rate != target_sr:
                # Calculate number of samples after resampling
                num_samples = int(len(audio_data) * target_sr / self.original_sample_rate)
                audio_data = signal.resample(audio_data, num_samples)
                self.sample_rate = target_sr
            else:
                self.sample_rate = self.original_sample_rate

            self.audio_data = audio_data
            self.duration = len(self.audio_data) / self.sample_rate

            # Track memory usage
            self._memory_usage_mb = self.audio_data.nbytes / (1024 * 1024)

            logger.info(f"Audio loaded: {self.duration:.2f}s, {self.sample_rate}Hz, {self._memory_usage_mb:.1f}MB RAM")
            return True

        except Exception as e:
            logger.error(f"Error loading audio file {file_path}: {str(e)}")
            return False

    def detect_silence(self,
                      silence_threshold_db: float = -40,
                      min_silence_duration: float = 0.5) -> List[Dict[str, Any]]:
        """
        Detect silence segments in the audio using energy-based detection
        Returns list of silence segments with start/end times
        """
        try:
            if self.audio_data is None:
                logger.error("No audio loaded")
                return []

            # Convert dB threshold to linear amplitude
            # dBFS = 20 * log10(amplitude)
            # amplitude = 10^(dBFS / 20)
            amplitude_threshold = 10 ** (silence_threshold_db / 20.0)

            # Calculate frame size for analysis (50ms frames)
            frame_size = int(0.05 * self.sample_rate)
            hop_size = frame_size // 2

            # Calculate RMS energy for each frame
            num_frames = (len(self.audio_data) - frame_size) // hop_size + 1
            is_silent = np.zeros(num_frames, dtype=bool)

            for i in range(num_frames):
                start_idx = i * hop_size
                end_idx = start_idx + frame_size
                frame = self.audio_data[start_idx:end_idx]
                rms = np.sqrt(np.mean(frame ** 2))
                is_silent[i] = rms < amplitude_threshold

            # Find continuous silence segments
            silence_segments = []
            in_silence = False
            silence_start_frame = 0

            for i, silent in enumerate(is_silent):
                if silent and not in_silence:
                    # Start of silence
                    in_silence = True
                    silence_start_frame = i
                elif not silent and in_silence:
                    # End of silence
                    in_silence = False
                    silence_duration_frames = i - silence_start_frame
                    silence_duration_sec = (silence_duration_frames * hop_size) / self.sample_rate

                    if silence_duration_sec >= min_silence_duration:
                        start_time = (silence_start_frame * hop_size) / self.sample_rate
                        end_time = (i * hop_size) / self.sample_rate
                        silence_segments.append({
                            'start_time': start_time,
                            'end_time': end_time,
                            'duration': end_time - start_time,
                            'type': 'silence'
                        })

            # Handle case where audio ends in silence
            if in_silence:
                silence_duration_frames = num_frames - silence_start_frame
                silence_duration_sec = (silence_duration_frames * hop_size) / self.sample_rate
                if silence_duration_sec >= min_silence_duration:
                    start_time = (silence_start_frame * hop_size) / self.sample_rate
                    end_time = self.duration
                    silence_segments.append({
                        'start_time': start_time,
                        'end_time': end_time,
                        'duration': end_time - start_time,
                        'type': 'silence'
                    })

            logger.info(f"Detected {len(silence_segments)} silence segments")
            return silence_segments

        except Exception as e:
            logger.error(f"Error detecting silence: {str(e)}")
            return []

    def detect_speech_segments(self,
                              silence_threshold_db: float = -40,
                              min_segment_duration: float = 1.0) -> List[Dict[str, Any]]:
        """
        Detect speech segments (non-silence) in the audio
        Returns list of speech segments with start/end times
        """
        silence_segments = self.detect_silence(silence_threshold_db=silence_threshold_db)

        if not silence_segments:
            # No silence detected, entire audio is speech
            return [{
                'start_time': 0.0,
                'end_time': self.duration,
                'duration': self.duration,
                'type': 'speech'
            }]

        speech_segments = []
        current_time = 0.0

        for silence in silence_segments:
            # Add speech segment before this silence
            if silence['start_time'] > current_time:
                duration = silence['start_time'] - current_time
                if duration >= min_segment_duration:
                    speech_segments.append({
                        'start_time': current_time,
                        'end_time': silence['start_time'],
                        'duration': duration,
                        'type': 'speech'
                    })

            current_time = silence['end_time']

        # Add final speech segment after last silence
        if current_time < self.duration:
            duration = self.duration - current_time
            if duration >= min_segment_duration:
                speech_segments.append({
                    'start_time': current_time,
                    'end_time': self.duration,
                    'duration': duration,
                    'type': 'speech'
                })

        logger.info(f"Detected {len(speech_segments)} speech segments")
        return speech_segments

    def analyze_audio_features(self) -> Dict[str, Any]:
        """
        Basic audio feature analysis using numpy
        """
        if self.audio_data is None:
            return {}

        try:
            # Calculate RMS (Root Mean Square) energy
            rms = np.sqrt(np.mean(self.audio_data ** 2))

            # Calculate dBFS (dB relative to full scale)
            # Assuming full scale is 1.0 (since we normalized)
            if rms > 0:
                dBFS = 20 * np.log10(rms)
            else:
                dBFS = -np.inf

            # Calculate max dBFS
            max_amplitude = np.max(np.abs(self.audio_data))
            if max_amplitude > 0:
                max_dBFS = 20 * np.log10(max_amplitude)
            else:
                max_dBFS = -np.inf

            features = {
                'duration': self.duration,
                'sample_rate': self.sample_rate,
                'channels': 1,  # We convert to mono
                'frame_rate': self.sample_rate,
                'rms': float(rms),
                'dBFS': float(dBFS),
                'max_dBFS': float(max_dBFS),
                'max_amplitude': float(max_amplitude),
                'mean_amplitude': float(np.mean(np.abs(self.audio_data)))
            }

            return features

        except Exception as e:
            logger.error(f"Error analyzing audio features: {str(e)}")
            return {}

    def find_optimal_cut_points(self,
                               min_segment_duration: float = 5.0,
                               max_segment_duration: float = 300.0) -> List[Dict[str, Any]]:
        """
        Find optimal cut points based on silence detection
        """
        try:
            cut_points = []
            silence_segments = self.detect_silence(min_silence_duration=0.3)

            current_segment_start = 0.0

            for silence in silence_segments:
                segment_duration = silence['start_time'] - current_segment_start

                # If segment is long enough, add cut point at silence
                if segment_duration >= min_segment_duration:
                    cut_points.append({
                        'time': silence['start_time'],
                        'type': 'silence_cut',
                        'confidence': 0.9,
                        'reason': 'Natural silence break',
                        'duration_before': segment_duration
                    })
                    current_segment_start = silence['end_time']

            logger.info(f"Found {len(cut_points)} optimal cut points")
            return cut_points

        except Exception as e:
            logger.error(f"Error finding optimal cut points: {str(e)}")
            return []

    def get_audio_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary of the audio analysis"""
        if self.audio_data is None:
            return {"error": "No audio data loaded"}

        try:
            summary = {
                'basic_info': {
                    'duration': self.duration,
                    'sample_rate': self.sample_rate,
                    'file_size_mb': os.path.getsize(self.file_path) / (1024 * 1024) if self.file_path else 0
                },
                'segments': {
                    'silence_segments': len(self.detect_silence()),
                    'speech_segments': len(self.detect_speech_segments())
                },
                'features': self.analyze_audio_features(),
                'cut_points': len(self.find_optimal_cut_points()),
                'processing_recommendations': self._get_processing_recommendations()
            }

            return summary

        except Exception as e:
            logger.error(f"Error generating audio summary: {str(e)}")
            return {"error": str(e)}

    def _get_processing_recommendations(self) -> Dict[str, Any]:
        """Generate processing recommendations based on audio analysis"""
        recommendations = {
            'silence_removal': True,
            'energy_based_cuts': True,
            'minimum_clip_length': 5.0
        }

        try:
            features = self.analyze_audio_features()

            if features.get('dBFS', 0) < -20:
                recommendations['amplify'] = True
                recommendations['note'] = 'Low volume detected, amplification recommended'

            silence_segments = self.detect_silence()
            if len(silence_segments) > 20:
                recommendations['aggressive_silence_removal'] = True
                recommendations['note'] = 'Many silence segments detected, aggressive removal recommended'

            return recommendations

        except Exception as e:
            logger.warning(f"Error generating processing recommendations: {str(e)}")
            return recommendations

    def release_audio_data(self) -> None:
        """SECURITY: Explicitly release audio data from memory"""
        if self.audio_data is not None:
            logger.info(f"Releasing {self._memory_usage_mb:.1f}MB audio data from memory")
            self.audio_data = None
            self._memory_usage_mb = 0
            import gc
            gc.collect()  # Force garbage collection

    def cleanup(self) -> None:
        """SECURITY: Clean up resources (converted files and memory)"""
        # Release audio data from memory
        self.release_audio_data()

        # Clean up converted files
        if self.converted_file_path:
            try:
                from services.audio_converter import get_converter
                converter = get_converter()

                # SECURITY: Use lock to prevent race conditions
                with self._converted_files_lock:
                    if self.converted_file_path in self._all_converted_files:
                        converter.cleanup_converted_file(self.converted_file_path)
                        self._all_converted_files.discard(self.converted_file_path)

                self.converted_file_path = None
            except Exception as e:
                logger.warning(f"Error during cleanup: {str(e)}")

    def __enter__(self):
        """SECURITY: Context manager entry - guaranteed cleanup"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """SECURITY: Context manager exit - guaranteed cleanup on any exit"""
        self.cleanup()
        return False  # Don't suppress exceptions

    @classmethod
    def cleanup_all_orphaned_files(cls):
        """SECURITY: Emergency cleanup of all tracked converted files"""
        with cls._converted_files_lock:
            orphaned_count = len(cls._all_converted_files)
            if orphaned_count > 0:
                logger.warning(f"Emergency cleanup: {orphaned_count} orphaned converted files")

            for file_path in list(cls._all_converted_files):
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"Emergency cleanup: {file_path}")
                except Exception as e:
                    logger.error(f"Emergency cleanup failed for {file_path}: {e}")

            cls._all_converted_files.clear()