import librosa
import numpy as np
from scipy.signal import find_peaks
from typing import List, Dict, Any, Tuple, Optional
import soundfile as sf
from config import Config
import logging
import os

logger = logging.getLogger(__name__)

class AudioAnalyzer:
    """Audio analysis module for silence detection, segment extraction, and audio processing"""

    def __init__(self):
        self.sample_rate = None
        self.audio_data = None
        self.duration = 0.0
        self.file_path = None
        self.file_info = None
        self.use_streaming = False

        # Memory threshold for streaming (100MB of audio data)
        self.streaming_threshold_mb = 100

    def load_audio(self, file_path: str, target_sr: int = 22050) -> bool:
        """Load audio file for analysis with memory optimization"""
        try:
            self.file_path = file_path

            # Get file size to determine processing strategy
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

            # Get audio info without loading the full file
            self.file_info = sf.info(file_path)
            self.duration = self.file_info.duration
            self.sample_rate = target_sr

            logger.info(f"Audio file: {self.duration:.2f}s, {file_size_mb:.1f}MB")

            # Decide whether to use streaming based on file size
            if file_size_mb > self.streaming_threshold_mb:
                self.use_streaming = True
                logger.info(f"Large file detected ({file_size_mb:.1f}MB), using streaming processing")
                # For streaming, we don't load the entire file into memory
                self.audio_data = None
                return True
            else:
                # Load smaller files completely into memory
                self.use_streaming = False
                self.audio_data, self.sample_rate = librosa.load(file_path, sr=target_sr)
                logger.info(f"Loaded audio: {self.duration:.2f}s at {self.sample_rate}Hz")
                return True

        except Exception as e:
            logger.error(f"Error loading audio file {file_path}: {str(e)}")
            return False

    def _load_audio_chunk(self, start_time: float, duration: float) -> Optional[np.ndarray]:
        """Load a specific chunk of audio for streaming processing"""
        try:
            start_frame = int(start_time * self.file_info.samplerate)
            frames_to_read = int(duration * self.file_info.samplerate)

            with sf.SoundFile(self.file_path) as audio_file:
                audio_file.seek(start_frame)
                chunk = audio_file.read(frames_to_read)

                # Convert to mono if stereo
                if chunk.ndim > 1:
                    chunk = np.mean(chunk, axis=1)

                # Resample if needed
                if self.file_info.samplerate != self.sample_rate:
                    chunk = librosa.resample(chunk,
                                           orig_sr=self.file_info.samplerate,
                                           target_sr=self.sample_rate)

                return chunk

        except Exception as e:
            logger.error(f"Error loading audio chunk: {str(e)}")
            return None

    def detect_silence(self,
                      silence_threshold_db: float = -40,
                      min_silence_duration: float = 0.5,
                      frame_length: int = 2048,
                      hop_length: int = 512) -> List[Dict[str, Any]]:
        """
        Detect silence segments in the audio
        Returns list of silence segments with start/end times
        """
        try:
            if self.use_streaming:
                return self._detect_silence_streaming(silence_threshold_db, min_silence_duration, frame_length, hop_length)
            else:
                return self._detect_silence_memory(silence_threshold_db, min_silence_duration, frame_length, hop_length)

        except Exception as e:
            logger.error(f"Error detecting silence: {str(e)}")
            return []

    def _detect_silence_memory(self, silence_threshold_db: float, min_silence_duration: float, frame_length: int, hop_length: int) -> List[Dict[str, Any]]:
        """Detect silence for files loaded in memory"""
        if self.audio_data is None:
            raise ValueError("No audio data loaded")

        # Convert to dB scale
        rms = librosa.feature.rms(y=self.audio_data,
                                frame_length=frame_length,
                                hop_length=hop_length)[0]

        # Convert to dB (avoiding log(0) by adding small epsilon)
        db = librosa.amplitude_to_db(rms + 1e-10)

        # Find frames below threshold
        silent_frames = db < silence_threshold_db

        # Convert frame indices to time
        frame_times = librosa.frames_to_time(np.arange(len(silent_frames)),
                                            sr=self.sample_rate,
                                            hop_length=hop_length)

        return self._group_silence_frames(frame_times, silent_frames, min_silence_duration)

    def _detect_silence_streaming(self, silence_threshold_db: float, min_silence_duration: float, frame_length: int, hop_length: int) -> List[Dict[str, Any]]:
        """Detect silence for large files using streaming"""
        chunk_duration = 30.0  # Process 30-second chunks
        overlap = 2.0  # 2-second overlap to avoid boundary issues

        all_frame_times = []
        all_silent_frames = []

        current_time = 0.0
        while current_time < self.duration:
            # Calculate chunk boundaries
            chunk_end = min(current_time + chunk_duration, self.duration)
            actual_duration = chunk_end - current_time

            # Load audio chunk
            chunk = self._load_audio_chunk(current_time, actual_duration)
            if chunk is None:
                break

            # Analyze chunk
            rms = librosa.feature.rms(y=chunk,
                                    frame_length=frame_length,
                                    hop_length=hop_length)[0]

            db = librosa.amplitude_to_db(rms + 1e-10)
            silent_frames = db < silence_threshold_db

            # Convert frame indices to absolute time
            chunk_frame_times = librosa.frames_to_time(np.arange(len(silent_frames)),
                                                      sr=self.sample_rate,
                                                      hop_length=hop_length) + current_time

            all_frame_times.extend(chunk_frame_times)
            all_silent_frames.extend(silent_frames)

            # Move to next chunk (with overlap)
            current_time = max(current_time + chunk_duration - overlap, chunk_end)

        return self._group_silence_frames(np.array(all_frame_times), np.array(all_silent_frames), min_silence_duration)

    def _group_silence_frames(self, frame_times: np.ndarray, silent_frames: np.ndarray, min_silence_duration: float) -> List[Dict[str, Any]]:
        """Group consecutive silent frames into segments"""
        silence_segments = []
        start_time = None

        for i, (time, is_silent) in enumerate(zip(frame_times, silent_frames)):
            if is_silent and start_time is None:
                start_time = time
            elif not is_silent and start_time is not None:
                duration = time - start_time
                if duration >= min_silence_duration:
                    silence_segments.append({
                        'start_time': start_time,
                        'end_time': time,
                        'duration': duration,
                        'type': 'silence'
                    })
                start_time = None

        # Handle case where audio ends with silence
        if start_time is not None:
            duration = self.duration - start_time
            if duration >= min_silence_duration:
                silence_segments.append({
                    'start_time': start_time,
                    'end_time': self.duration,
                    'duration': duration,
                    'type': 'silence'
                })

        logger.info(f"Detected {len(silence_segments)} silence segments")
        return silence_segments

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
        Analyze various audio features for editing decisions
        """
        if self.audio_data is None:
            raise ValueError("No audio data loaded")

        try:
            features = {}

            # Basic audio properties
            features['duration'] = self.duration
            features['sample_rate'] = self.sample_rate
            features['channels'] = 1 if self.audio_data.ndim == 1 else self.audio_data.shape[0]

            # RMS Energy
            rms = librosa.feature.rms(y=self.audio_data)[0]
            features['rms_mean'] = float(np.mean(rms))
            features['rms_std'] = float(np.std(rms))
            features['rms_max'] = float(np.max(rms))

            # Spectral features
            spectral_centroids = librosa.feature.spectral_centroid(y=self.audio_data, sr=self.sample_rate)[0]
            features['spectral_centroid_mean'] = float(np.mean(spectral_centroids))
            features['spectral_centroid_std'] = float(np.std(spectral_centroids))

            # Zero crossing rate
            zcr = librosa.feature.zero_crossing_rate(self.audio_data)[0]
            features['zero_crossing_rate_mean'] = float(np.mean(zcr))
            features['zero_crossing_rate_std'] = float(np.std(zcr))

            # MFCC features (for speech characteristics)
            mfccs = librosa.feature.mfcc(y=self.audio_data, sr=self.sample_rate, n_mfcc=13)
            features['mfcc_mean'] = mfccs.mean(axis=1).tolist()
            features['mfcc_std'] = mfccs.std(axis=1).tolist()

            # Tempo and rhythm (if applicable)
            try:
                tempo, beats = librosa.beat.beat_track(y=self.audio_data, sr=self.sample_rate)
                features['tempo'] = float(tempo)
                features['beat_count'] = len(beats)
            except:
                features['tempo'] = 0.0
                features['beat_count'] = 0

            # Dynamic range
            db_values = librosa.amplitude_to_db(np.abs(self.audio_data) + 1e-10)
            features['dynamic_range_db'] = float(np.max(db_values) - np.min(db_values))
            features['peak_db'] = float(np.max(db_values))
            features['avg_db'] = float(np.mean(db_values))

            return features

        except Exception as e:
            logger.error(f"Error analyzing audio features: {str(e)}")
            return {}

    def find_optimal_cut_points(self,
                               min_segment_duration: float = 5.0,
                               max_segment_duration: float = 300.0) -> List[Dict[str, Any]]:
        """
        Find optimal cut points for editing based on audio analysis
        Considers silence, speech patterns, and energy levels
        """
        try:
            cut_points = []

            # Get silence and speech segments
            silence_segments = self.detect_silence(min_silence_duration=0.3)
            speech_segments = self.detect_speech_segments(min_segment_duration=1.0)

            # Analyze energy levels
            rms = librosa.feature.rms(y=self.audio_data, hop_length=512)[0]
            frame_times = librosa.frames_to_time(np.arange(len(rms)),
                                               sr=self.sample_rate,
                                               hop_length=512)

            # Find low energy points (potential cut points)
            energy_threshold = np.percentile(rms, 25)  # Bottom 25% of energy levels
            low_energy_indices = np.where(rms < energy_threshold)[0]

            current_segment_start = 0.0

            for silence in silence_segments:
                segment_duration = silence['start_time'] - current_segment_start

                # If segment is too long, find intermediate cut points
                if segment_duration > max_segment_duration:
                    # Find cut points within the long segment
                    intermediate_cuts = self._find_intermediate_cuts(
                        current_segment_start,
                        silence['start_time'],
                        max_segment_duration,
                        rms,
                        frame_times
                    )
                    cut_points.extend(intermediate_cuts)

                # Silence as potential cut point
                if segment_duration >= min_segment_duration:
                    cut_points.append({
                        'time': silence['start_time'],
                        'type': 'silence_cut',
                        'confidence': 0.9,
                        'reason': 'Natural silence break',
                        'duration_before': segment_duration
                    })
                    current_segment_start = silence['end_time']

            # Handle final segment
            final_duration = self.duration - current_segment_start
            if final_duration > max_segment_duration:
                intermediate_cuts = self._find_intermediate_cuts(
                    current_segment_start,
                    self.duration,
                    max_segment_duration,
                    rms,
                    frame_times
                )
                cut_points.extend(intermediate_cuts)

            # Sort cut points by time
            cut_points.sort(key=lambda x: x['time'])

            logger.info(f"Found {len(cut_points)} optimal cut points")
            return cut_points

        except Exception as e:
            logger.error(f"Error finding optimal cut points: {str(e)}")
            return []

    def _find_intermediate_cuts(self,
                               start_time: float,
                               end_time: float,
                               max_duration: float,
                               rms: np.ndarray,
                               frame_times: np.ndarray) -> List[Dict[str, Any]]:
        """Find intermediate cut points within a long segment"""
        cuts = []
        segment_duration = end_time - start_time
        num_cuts_needed = int(segment_duration / max_duration)

        if num_cuts_needed <= 0:
            return cuts

        # Find frames within this time range
        mask = (frame_times >= start_time) & (frame_times <= end_time)
        segment_times = frame_times[mask]
        segment_rms = rms[mask]

        if len(segment_times) == 0:
            return cuts

        # Find local minima in energy (good cut points)
        try:
            local_minima, _ = find_peaks(-segment_rms, distance=int(self.sample_rate/512))  # At least 1 second apart

            if len(local_minima) > 0:
                # Select the best cut points
                minima_times = segment_times[local_minima]
                minima_values = segment_rms[local_minima]

                # Sort by energy level (lowest first)
                sorted_indices = np.argsort(minima_values)

                # Select up to num_cuts_needed best points
                selected_cuts = sorted_indices[:num_cuts_needed]

                for cut_idx in selected_cuts:
                    cuts.append({
                        'time': minima_times[cut_idx],
                        'type': 'energy_cut',
                        'confidence': 0.6,
                        'reason': 'Low energy point in long segment',
                        'energy_level': float(minima_values[cut_idx])
                    })

        except Exception as e:
            logger.warning(f"Error finding intermediate cuts: {str(e)}")
            # Fallback: evenly spaced cuts
            for i in range(1, num_cuts_needed + 1):
                cut_time = start_time + (segment_duration * i / (num_cuts_needed + 1))
                cuts.append({
                    'time': cut_time,
                    'type': 'timed_cut',
                    'confidence': 0.3,
                    'reason': 'Evenly spaced cut in long segment'
                })

        return cuts

    def get_audio_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary of the audio analysis"""
        if self.audio_data is None:
            return {"error": "No audio data loaded"}

        try:
            summary = {
                'basic_info': {
                    'duration': self.duration,
                    'sample_rate': self.sample_rate,
                    'file_size_mb': len(self.audio_data) * 4 / (1024 * 1024)  # Rough estimate
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
            'speaker_separation': True,
            'energy_based_cuts': True,
            'minimum_clip_length': Config.MIN_CLIP_LENGTH_SECONDS
        }

        try:
            # Analyze audio characteristics for recommendations
            features = self.analyze_audio_features()

            # Adjust recommendations based on audio properties
            if features.get('dynamic_range_db', 0) < 20:
                recommendations['normalize_audio'] = True
                recommendations['note'] = 'Low dynamic range detected, normalization recommended'

            if features.get('rms_mean', 0) < 0.01:
                recommendations['amplify'] = True
                recommendations['note'] = 'Low volume detected, amplification recommended'

            silence_segments = self.detect_silence()
            if len(silence_segments) > 50:
                recommendations['aggressive_silence_removal'] = True
                recommendations['note'] = 'Many silence segments detected, aggressive removal recommended'

            return recommendations

        except Exception as e:
            logger.warning(f"Error generating processing recommendations: {str(e)}")
            return recommendations