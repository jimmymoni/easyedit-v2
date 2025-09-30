import pytest
import os
import numpy as np
from scipy.io import wavfile

from services.simple_audio_analyzer import SimpleAudioAnalyzer


class TestSimpleAudioAnalyzer:
    """Test cases for SimpleAudioAnalyzer service"""

    @pytest.fixture
    def temp_audio_file(self, tmp_path):
        """Create a temporary audio file with known characteristics"""
        # Generate a 5-second audio file with some silence
        sample_rate = 22050

        # Create segments: 1s speech, 0.5s silence, 2s speech, 0.5s silence, 1s speech
        freq = 440  # Hz

        # Speech segment (1s)
        t1 = np.linspace(0, 1.0, int(sample_rate * 1.0))
        speech1 = 0.3 * np.sin(2 * np.pi * freq * t1)

        # Silence (0.5s)
        silence1 = np.zeros(int(sample_rate * 0.5))

        # Speech segment (2s)
        t2 = np.linspace(0, 2.0, int(sample_rate * 2.0))
        speech2 = 0.3 * np.sin(2 * np.pi * freq * t2)

        # Silence (0.5s)
        silence2 = np.zeros(int(sample_rate * 0.5))

        # Speech segment (1s)
        t3 = np.linspace(0, 1.0, int(sample_rate * 1.0))
        speech3 = 0.3 * np.sin(2 * np.pi * freq * t3)

        # Concatenate all segments
        audio = np.concatenate([speech1, silence1, speech2, silence2, speech3])

        # Convert to int16 for WAV file
        audio_int16 = (audio * 32767).astype(np.int16)

        # Export to file
        audio_path = tmp_path / "test_audio.wav"
        wavfile.write(str(audio_path), sample_rate, audio_int16)

        return str(audio_path)

    @pytest.fixture
    def real_audio_file(self):
        """Use the actual test_audio.wav file if it exists"""
        audio_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'test_audio.wav')
        if os.path.exists(audio_path):
            return audio_path
        return None

    def test_load_audio_success(self, temp_audio_file):
        """Test successful audio loading"""
        analyzer = SimpleAudioAnalyzer()
        success = analyzer.load_audio(temp_audio_file)

        assert success is True
        assert analyzer.audio_data is not None
        assert analyzer.duration > 0
        assert analyzer.sample_rate == 22050

    def test_load_audio_wav(self, real_audio_file):
        """Test loading real WAV file if available"""
        if real_audio_file is None:
            pytest.skip("Real audio file not available")

        analyzer = SimpleAudioAnalyzer()
        success = analyzer.load_audio(real_audio_file)

        assert success is True
        assert analyzer.audio_data is not None
        assert analyzer.duration > 0

    def test_load_nonexistent_audio(self):
        """Test loading non-existent audio file fails gracefully"""
        analyzer = SimpleAudioAnalyzer()
        success = analyzer.load_audio('/nonexistent/file.wav')

        assert success is False
        assert analyzer.audio_data is None

    def test_detect_silence(self, temp_audio_file):
        """Test silence detection"""
        analyzer = SimpleAudioAnalyzer()
        analyzer.load_audio(temp_audio_file)

        silence_segments = analyzer.detect_silence(
            silence_threshold_db=-40,
            min_silence_duration=0.3
        )

        assert isinstance(silence_segments, list)
        # Should detect at least one silence segment (we created two 0.5s silences)
        assert len(silence_segments) >= 1

        # Check structure of silence segments
        for segment in silence_segments:
            assert 'start_time' in segment
            assert 'end_time' in segment
            assert 'duration' in segment
            assert 'type' in segment
            assert segment['type'] == 'silence'
            assert segment['end_time'] > segment['start_time']
            assert segment['duration'] == segment['end_time'] - segment['start_time']

    def test_detect_silence_no_audio_loaded(self):
        """Test silence detection without loaded audio"""
        analyzer = SimpleAudioAnalyzer()
        silence_segments = analyzer.detect_silence()

        assert isinstance(silence_segments, list)
        assert len(silence_segments) == 0

    def test_detect_speech_segments(self, temp_audio_file):
        """Test speech segment detection"""
        analyzer = SimpleAudioAnalyzer()
        analyzer.load_audio(temp_audio_file)

        speech_segments = analyzer.detect_speech_segments(
            silence_threshold_db=-40,
            min_segment_duration=0.5
        )

        assert isinstance(speech_segments, list)
        # Should detect multiple speech segments (we created three speech segments)
        assert len(speech_segments) >= 1

        # Check structure of speech segments
        for segment in speech_segments:
            assert 'start_time' in segment
            assert 'end_time' in segment
            assert 'duration' in segment
            assert 'type' in segment
            assert segment['type'] == 'speech'
            assert segment['end_time'] > segment['start_time']
            assert segment['duration'] >= 0.5  # Minimum duration

    def test_detect_speech_segments_no_silence(self, tmp_path):
        """Test speech detection when there's no silence"""
        # Create audio with no silence
        sample_rate = 22050
        duration = 3.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        continuous_speech = 0.3 * np.sin(2 * np.pi * 440 * t)
        audio_int16 = (continuous_speech * 32767).astype(np.int16)

        audio_path = tmp_path / "continuous.wav"
        wavfile.write(str(audio_path), sample_rate, audio_int16)

        analyzer = SimpleAudioAnalyzer()
        analyzer.load_audio(str(audio_path))
        speech_segments = analyzer.detect_speech_segments()

        # Should detect one continuous speech segment
        assert len(speech_segments) >= 1
        assert speech_segments[0]['duration'] > 2.5  # Approximately 3 seconds

    def test_analyze_audio_features(self, temp_audio_file):
        """Test audio feature analysis"""
        analyzer = SimpleAudioAnalyzer()
        analyzer.load_audio(temp_audio_file)

        features = analyzer.analyze_audio_features()

        assert isinstance(features, dict)
        assert 'duration' in features
        assert 'sample_rate' in features
        assert 'channels' in features
        assert 'frame_rate' in features
        assert 'rms' in features
        assert 'dBFS' in features

        # Validate feature values
        assert features['duration'] > 0
        assert features['sample_rate'] > 0
        assert features['channels'] >= 1

    def test_analyze_audio_features_no_audio(self):
        """Test feature analysis without loaded audio"""
        analyzer = SimpleAudioAnalyzer()
        features = analyzer.analyze_audio_features()

        assert isinstance(features, dict)
        assert len(features) == 0

    def test_find_optimal_cut_points(self, temp_audio_file):
        """Test finding optimal cut points"""
        analyzer = SimpleAudioAnalyzer()
        analyzer.load_audio(temp_audio_file)

        cut_points = analyzer.find_optimal_cut_points(
            min_segment_duration=1.0,
            max_segment_duration=300.0
        )

        assert isinstance(cut_points, list)
        # Should find some cut points based on silence

        # Check structure of cut points
        for cut_point in cut_points:
            assert 'time' in cut_point
            assert 'type' in cut_point
            assert 'confidence' in cut_point
            assert 'reason' in cut_point
            assert cut_point['time'] >= 0

    def test_get_audio_summary(self, temp_audio_file):
        """Test comprehensive audio summary generation"""
        analyzer = SimpleAudioAnalyzer()
        analyzer.load_audio(temp_audio_file)

        summary = analyzer.get_audio_summary()

        assert isinstance(summary, dict)
        assert 'basic_info' in summary
        assert 'segments' in summary
        assert 'features' in summary
        assert 'cut_points' in summary
        assert 'processing_recommendations' in summary

        # Validate basic info
        basic_info = summary['basic_info']
        assert 'duration' in basic_info
        assert 'sample_rate' in basic_info
        assert basic_info['duration'] > 0

        # Validate segments info
        segments = summary['segments']
        assert 'silence_segments' in segments
        assert 'speech_segments' in segments
        assert isinstance(segments['silence_segments'], int)
        assert isinstance(segments['speech_segments'], int)

    def test_get_audio_summary_no_audio(self):
        """Test audio summary without loaded audio"""
        analyzer = SimpleAudioAnalyzer()
        summary = analyzer.get_audio_summary()

        assert isinstance(summary, dict)
        assert 'error' in summary

    def test_processing_recommendations_low_volume(self, tmp_path):
        """Test that low volume triggers amplification recommendation"""
        # Create a very quiet audio segment (amplitude 0.01 = -40dB)
        sample_rate = 22050
        duration = 2.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        quiet_tone = 0.01 * np.sin(2 * np.pi * 440 * t)  # Very low amplitude
        audio_int16 = (quiet_tone * 32767).astype(np.int16)

        audio_path = tmp_path / "quiet.wav"
        wavfile.write(str(audio_path), sample_rate, audio_int16)

        analyzer = SimpleAudioAnalyzer()
        analyzer.load_audio(str(audio_path))
        summary = analyzer.get_audio_summary()

        recommendations = summary['processing_recommendations']
        # Low volume should trigger amplification recommendation
        assert 'amplify' in recommendations or 'silence_removal' in recommendations

    def test_multiple_loads(self, temp_audio_file, tmp_path):
        """Test loading multiple audio files sequentially"""
        # Create second audio file
        sample_rate = 22050
        duration = 2.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio2 = 0.3 * np.sin(2 * np.pi * 220 * t)
        audio2_int16 = (audio2 * 32767).astype(np.int16)

        audio2_path = tmp_path / "audio2.wav"
        wavfile.write(str(audio2_path), sample_rate, audio2_int16)

        analyzer = SimpleAudioAnalyzer()

        # Load first audio
        success1 = analyzer.load_audio(temp_audio_file)
        duration1 = analyzer.duration

        # Load second audio (should replace first)
        success2 = analyzer.load_audio(str(audio2_path))
        duration2 = analyzer.duration

        assert success1 is True
        assert success2 is True
        assert duration1 != duration2  # Different durations

    def test_silence_detection_threshold_sensitivity(self, temp_audio_file):
        """Test that different thresholds affect silence detection"""
        analyzer = SimpleAudioAnalyzer()
        analyzer.load_audio(temp_audio_file)

        # Aggressive threshold (more sensitive)
        silence_aggressive = analyzer.detect_silence(silence_threshold_db=-20)

        # Conservative threshold (less sensitive)
        silence_conservative = analyzer.detect_silence(silence_threshold_db=-60)

        assert isinstance(silence_aggressive, list)
        assert isinstance(silence_conservative, list)
        # Aggressive should detect more or equal silence
        assert len(silence_aggressive) >= len(silence_conservative)
