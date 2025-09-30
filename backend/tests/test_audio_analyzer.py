import pytest
import numpy as np
import tempfile
import os
from unittest.mock import patch, Mock

# Try to import AudioAnalyzer, fall back to SimpleAudioAnalyzer if not available
try:
    from services.audio_analyzer import AudioAnalyzer
    USING_SIMPLE_ANALYZER = False
except ImportError:
    from services.simple_audio_analyzer import SimpleAudioAnalyzer as AudioAnalyzer
    USING_SIMPLE_ANALYZER = True

class TestAudioAnalyzer:
    """Test cases for AudioAnalyzer service"""

    def test_load_audio_success(self, temp_dir, sample_audio_data):
        """Test successful audio loading"""
        # Create test audio file
        audio_data, sample_rate = sample_audio_data
        audio_file = os.path.join(temp_dir, 'test_audio.wav')

        if USING_SIMPLE_ANALYZER:
            # SimpleAudioAnalyzer uses scipy.io.wavfile
            from scipy.io import wavfile
            wavfile.write(audio_file, sample_rate, (audio_data * 32767).astype(np.int16))
        else:
            # AudioAnalyzer uses soundfile
            import soundfile as sf
            sf.write(audio_file, audio_data, sample_rate)

        analyzer = AudioAnalyzer()
        success = analyzer.load_audio(audio_file)

        assert success == True
        assert analyzer.audio_data is not None
        assert analyzer.sample_rate is not None
        assert analyzer.duration > 0
        assert len(analyzer.audio_data) > 0

    def test_load_nonexistent_audio(self):
        """Test loading non-existent audio file fails"""
        analyzer = AudioAnalyzer()
        success = analyzer.load_audio('/nonexistent/file.wav')

        assert success == False
        assert analyzer.audio_data is None

    @pytest.fixture
    def loaded_analyzer(self, temp_dir, sample_audio_data):
        """Fixture providing an AudioAnalyzer with loaded audio"""
        audio_data, sample_rate = sample_audio_data
        audio_file = os.path.join(temp_dir, 'test_audio.wav')

        if USING_SIMPLE_ANALYZER:
            # SimpleAudioAnalyzer uses scipy.io.wavfile
            from scipy.io import wavfile
            wavfile.write(audio_file, sample_rate, (audio_data * 32767).astype(np.int16))
        else:
            # AudioAnalyzer uses soundfile
            import soundfile as sf
            sf.write(audio_file, audio_data, sample_rate)

        analyzer = AudioAnalyzer()
        analyzer.load_audio(audio_file)
        return analyzer

    def test_detect_silence_default_params(self, loaded_analyzer):
        """Test silence detection with default parameters"""
        silence_segments = loaded_analyzer.detect_silence()

        assert isinstance(silence_segments, list)
        # Should detect some silence segments based on our test data
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

    def test_detect_silence_custom_params(self, loaded_analyzer):
        """Test silence detection with custom parameters"""
        # More sensitive threshold should detect more silence
        silence_segments_sensitive = loaded_analyzer.detect_silence(
            silence_threshold_db=-20,
            min_silence_duration=0.1
        )

        # Less sensitive threshold should detect less silence
        silence_segments_less_sensitive = loaded_analyzer.detect_silence(
            silence_threshold_db=-60,
            min_silence_duration=1.0
        )

        assert isinstance(silence_segments_sensitive, list)
        assert isinstance(silence_segments_less_sensitive, list)

        # More sensitive settings should find more segments
        assert len(silence_segments_sensitive) >= len(silence_segments_less_sensitive)

    def test_detect_silence_no_audio_loaded(self):
        """Test silence detection with no audio loaded raises error"""
        analyzer = AudioAnalyzer()

        with pytest.raises(ValueError, match="No audio data loaded"):
            analyzer.detect_silence()

    def test_detect_speech_segments(self, loaded_analyzer):
        """Test speech segment detection"""
        speech_segments = loaded_analyzer.detect_speech_segments()

        assert isinstance(speech_segments, list)
        assert len(speech_segments) >= 1

        # Check structure of speech segments
        for segment in speech_segments:
            assert 'start_time' in segment
            assert 'end_time' in segment
            assert 'duration' in segment
            assert 'type' in segment
            assert segment['type'] == 'speech'
            assert segment['end_time'] > segment['start_time']

    def test_analyze_audio_features(self, loaded_analyzer):
        """Test audio feature analysis"""
        features = loaded_analyzer.analyze_audio_features()

        assert isinstance(features, dict)

        # Check for expected feature keys
        expected_keys = [
            'duration', 'sample_rate', 'channels',
            'rms_mean', 'rms_std', 'rms_max',
            'spectral_centroid_mean', 'spectral_centroid_std',
            'zero_crossing_rate_mean', 'zero_crossing_rate_std',
            'mfcc_mean', 'mfcc_std',
            'tempo', 'beat_count',
            'dynamic_range_db', 'peak_db', 'avg_db'
        ]

        for key in expected_keys:
            assert key in features, f"Missing feature: {key}"

        # Check value types and ranges
        assert features['duration'] > 0
        assert features['sample_rate'] > 0
        assert features['channels'] >= 1
        assert features['rms_mean'] >= 0
        assert isinstance(features['mfcc_mean'], list)
        assert len(features['mfcc_mean']) == 13  # Standard MFCC count

    def test_find_optimal_cut_points(self, loaded_analyzer):
        """Test finding optimal cut points"""
        cut_points = loaded_analyzer.find_optimal_cut_points()

        assert isinstance(cut_points, list)

        # Check structure of cut points
        for point in cut_points:
            assert 'time' in point
            assert 'type' in point
            assert 'confidence' in point
            assert 'reason' in point
            assert point['time'] >= 0
            assert 0 <= point['confidence'] <= 1

    def test_find_optimal_cut_points_with_params(self, loaded_analyzer):
        """Test cut points with custom parameters"""
        cut_points_short = loaded_analyzer.find_optimal_cut_points(
            min_segment_duration=2.0,
            max_segment_duration=10.0
        )

        cut_points_long = loaded_analyzer.find_optimal_cut_points(
            min_segment_duration=1.0,
            max_segment_duration=30.0
        )

        assert isinstance(cut_points_short, list)
        assert isinstance(cut_points_long, list)

        # Different parameters should potentially yield different results
        # (though exact comparison depends on audio content)

    def test_get_audio_summary(self, loaded_analyzer):
        """Test getting comprehensive audio summary"""
        summary = loaded_analyzer.get_audio_summary()

        assert isinstance(summary, dict)

        # Check for expected summary sections
        expected_sections = ['basic_info', 'segments', 'features', 'cut_points', 'processing_recommendations']
        for section in expected_sections:
            assert section in summary, f"Missing summary section: {section}"

        # Check basic info
        basic_info = summary['basic_info']
        assert basic_info['duration'] > 0
        assert basic_info['sample_rate'] > 0

        # Check segments info
        segments = summary['segments']
        assert 'silence_segments' in segments
        assert 'speech_segments' in segments
        assert segments['silence_segments'] >= 0
        assert segments['speech_segments'] >= 0

    def test_get_audio_summary_no_audio(self):
        """Test audio summary with no audio loaded"""
        analyzer = AudioAnalyzer()
        summary = analyzer.get_audio_summary()

        assert "error" in summary
        assert summary["error"] == "No audio data loaded"

    def test_processing_recommendations(self, loaded_analyzer):
        """Test processing recommendations generation"""
        # This is tested through get_audio_summary, but let's test the internal method
        recommendations = loaded_analyzer._get_processing_recommendations()

        assert isinstance(recommendations, dict)
        assert 'silence_removal' in recommendations
        assert 'speaker_separation' in recommendations
        assert 'energy_based_cuts' in recommendations
        assert 'minimum_clip_length' in recommendations

        # Check for boolean values where expected
        assert isinstance(recommendations['silence_removal'], bool)
        assert isinstance(recommendations['speaker_separation'], bool)

    def test_intermediate_cuts_finding(self, loaded_analyzer):
        """Test finding intermediate cuts in long segments"""
        # Test the private method for finding cuts within long segments
        # Create mock RMS and frame times data
        rms = np.array([0.1, 0.05, 0.15, 0.02, 0.12, 0.08, 0.01, 0.11])  # Mock energy levels
        frame_times = np.linspace(0, 10, len(rms))  # 10 second segment

        cuts = loaded_analyzer._find_intermediate_cuts(
            start_time=0,
            end_time=10,
            max_duration=3,  # Force cuts every 3 seconds
            rms=rms,
            frame_times=frame_times
        )

        assert isinstance(cuts, list)
        # Should find some cut points for a 10-second segment with 3s max duration

    def test_silence_detection_edge_cases(self, loaded_analyzer):
        """Test silence detection edge cases"""
        # Test with very strict threshold (should find little/no silence)
        strict_silence = loaded_analyzer.detect_silence(silence_threshold_db=-80)

        # Test with very lenient threshold (should find lots of silence)
        lenient_silence = loaded_analyzer.detect_silence(silence_threshold_db=-10)

        assert isinstance(strict_silence, list)
        assert isinstance(lenient_silence, list)

        # Lenient threshold should typically find more silence
        assert len(lenient_silence) >= len(strict_silence)

    def test_speech_segments_complement_silence(self, loaded_analyzer):
        """Test that speech segments complement silence segments"""
        silence_segments = loaded_analyzer.detect_silence()
        speech_segments = loaded_analyzer.detect_speech_segments()

        # Combined segments should cover most of the audio duration
        total_silence_duration = sum(seg['duration'] for seg in silence_segments)
        total_speech_duration = sum(seg['duration'] for seg in speech_segments)
        total_covered = total_silence_duration + total_speech_duration

        # Should cover most of the audio (allowing for some gaps/overlaps in detection)
        assert total_covered >= loaded_analyzer.duration * 0.8

    @patch('services.audio_analyzer.librosa.load')
    def test_audio_loading_error_handling(self, mock_load):
        """Test error handling in audio loading"""
        mock_load.side_effect = Exception("Simulated load error")

        analyzer = AudioAnalyzer()
        success = analyzer.load_audio('fake_file.wav')

        assert success == False
        assert analyzer.audio_data is None

    def test_feature_analysis_robustness(self, loaded_analyzer):
        """Test feature analysis with edge case audio"""
        # Replace audio with very quiet audio
        loaded_analyzer.audio_data = np.random.random(loaded_analyzer.audio_data.shape) * 0.001

        features = loaded_analyzer.analyze_audio_features()

        # Should still return all expected features without crashing
        assert isinstance(features, dict)
        assert 'rms_mean' in features
        assert 'dynamic_range_db' in features

        # RMS should be very low
        assert features['rms_mean'] < 0.01

    def test_cut_points_empty_audio(self):
        """Test cut point detection with minimal audio"""
        analyzer = AudioAnalyzer()

        # Create very short audio
        short_audio = np.random.random(1000) * 0.1  # 1000 samples ≈ 0.045s at 22050Hz
        analyzer.audio_data = short_audio
        analyzer.sample_rate = 22050
        analyzer.duration = len(short_audio) / analyzer.sample_rate

        cut_points = analyzer.find_optimal_cut_points()

        # Should handle short audio gracefully
        assert isinstance(cut_points, list)
        # Might be empty for very short audio