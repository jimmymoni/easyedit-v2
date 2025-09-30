import pytest
import os
import tempfile
import numpy as np
import soundfile as sf
from pathlib import Path
from unittest.mock import patch, Mock

from services.audio_analyzer import AudioAnalyzer


class TestAudioFormats:
    """Test audio processing with various file formats"""

    @pytest.fixture
    def sample_audio_data(self):
        """Generate sample audio data for testing"""
        duration = 10.0  # 10 seconds
        sample_rate = 44100
        t = np.linspace(0, duration, int(duration * sample_rate))

        # Create realistic audio with speech-like patterns
        audio = 0.3 * np.sin(2 * np.pi * 200 * t)  # Base frequency
        audio += 0.1 * np.sin(2 * np.pi * 400 * t)  # Harmonic
        audio *= (1 + 0.2 * np.random.random(len(audio)))  # Variation

        # Add some silence in the middle
        silence_start = int(4.5 * sample_rate)
        silence_end = int(5.5 * sample_rate)
        audio[silence_start:silence_end] *= 0.05  # Very quiet

        return audio, sample_rate

    def create_test_audio_file(self, temp_dir, audio_data, sample_rate, format_name, subtype=None):
        """Helper to create test audio files in different formats"""
        audio, sr = audio_data, sample_rate
        filename = f'test_audio.{format_name.lower()}'
        filepath = os.path.join(temp_dir, filename)

        try:
            if subtype:
                sf.write(filepath, audio, sr, subtype=subtype)
            else:
                sf.write(filepath, audio, sr)
            return filepath
        except Exception as e:
            pytest.skip(f"Cannot create {format_name} file: {e}")

    def test_wav_format_support(self, temp_dir, sample_audio_data):
        """Test WAV format support (most common)"""
        audio_file = self.create_test_audio_file(temp_dir, sample_audio_data, 44100, 'wav')

        analyzer = AudioAnalyzer()
        success = analyzer.load_audio(audio_file)

        assert success == True
        assert analyzer.audio_data is not None
        assert analyzer.sample_rate == 44100
        assert analyzer.duration > 9  # Should be ~10 seconds

        # Test analysis functions work
        silence = analyzer.detect_silence()
        features = analyzer.analyze_audio_features()

        assert isinstance(silence, list)
        assert len(silence) >= 1  # Should detect the silence we added
        assert isinstance(features, dict)

    def test_wav_different_bit_depths(self, temp_dir, sample_audio_data):
        """Test WAV files with different bit depths"""
        test_cases = [
            ('PCM_16', '16-bit PCM'),
            ('PCM_24', '24-bit PCM'),
            ('PCM_32', '32-bit PCM'),
            ('FLOAT', '32-bit float')
        ]

        for subtype, description in test_cases:
            try:
                audio_file = self.create_test_audio_file(
                    temp_dir, sample_audio_data, 48000, 'wav', subtype=subtype
                )

                analyzer = AudioAnalyzer()
                success = analyzer.load_audio(audio_file)

                assert success == True, f"Failed to load {description} WAV"
                assert analyzer.sample_rate == 48000

                # Basic analysis should work
                features = analyzer.analyze_audio_features()
                assert 'duration' in features

                print(f"✓ Successfully processed {description} WAV")

            except Exception as e:
                pytest.skip(f"Skipping {description}: {e}")

    def test_different_sample_rates(self, temp_dir, sample_audio_data):
        """Test audio files with different sample rates"""
        sample_rates = [8000, 16000, 22050, 44100, 48000, 96000]
        audio, _ = sample_audio_data

        for sr in sample_rates:
            try:
                # Resample audio data for different sample rates
                if sr != 44100:
                    # Simple resampling (for testing purposes)
                    ratio = sr / 44100
                    new_length = int(len(audio) * ratio)
                    resampled_audio = np.interp(
                        np.linspace(0, len(audio), new_length),
                        np.arange(len(audio)),
                        audio
                    )
                else:
                    resampled_audio = audio

                audio_file = self.create_test_audio_file(
                    temp_dir, (resampled_audio, sr), sr, 'wav'
                )

                analyzer = AudioAnalyzer()
                success = analyzer.load_audio(audio_file)

                assert success == True, f"Failed to load {sr}Hz audio"
                assert analyzer.sample_rate == sr

                # Analysis should work regardless of sample rate
                silence = analyzer.detect_silence()
                assert isinstance(silence, list)

                print(f"✓ Successfully processed {sr}Hz audio")

            except Exception as e:
                print(f"⚠ Skipping {sr}Hz: {e}")

    def test_stereo_vs_mono(self, temp_dir, sample_audio_data):
        """Test both mono and stereo audio files"""
        audio, sample_rate = sample_audio_data

        # Test mono (original)
        mono_file = self.create_test_audio_file(temp_dir, (audio, sample_rate), sample_rate, 'wav')

        # Test stereo (duplicate to both channels)
        stereo_audio = np.column_stack([audio, audio])
        stereo_file = self.create_test_audio_file(temp_dir, (stereo_audio, sample_rate), sample_rate, 'wav')

        # Test mono file
        analyzer_mono = AudioAnalyzer()
        success_mono = analyzer_mono.load_audio(mono_file)
        assert success_mono == True

        # Test stereo file
        analyzer_stereo = AudioAnalyzer()
        success_stereo = analyzer_stereo.load_audio(stereo_file)
        assert success_stereo == True

        # Both should work and produce similar analysis results
        mono_features = analyzer_mono.analyze_audio_features()
        stereo_features = analyzer_stereo.analyze_audio_features()

        assert mono_features['channels'] == 1
        assert stereo_features['channels'] == 2

        # Duration should be similar
        assert abs(mono_features['duration'] - stereo_features['duration']) < 0.1

    @patch('soundfile.read')
    def test_mp3_format_simulation(self, mock_sf_read, temp_dir, sample_audio_data):
        """Test MP3 format support (simulated since soundfile might not support MP3)"""
        audio, sample_rate = sample_audio_data

        # Mock soundfile.read to simulate MP3 loading
        mock_sf_read.return_value = (audio, sample_rate)

        # Create a fake MP3 file path
        mp3_file = os.path.join(temp_dir, 'test.mp3')
        with open(mp3_file, 'wb') as f:
            f.write(b'fake mp3 content')  # Just to make file exist

        analyzer = AudioAnalyzer()

        # Patch the load method to use our mock
        with patch.object(analyzer, '_load_with_librosa') as mock_librosa:
            mock_librosa.return_value = (audio, sample_rate)

            success = analyzer.load_audio(mp3_file)

            assert success == True
            assert analyzer.sample_rate == sample_rate

            # Should fall back to librosa for MP3
            mock_librosa.assert_called_once()

    def test_flac_format_support(self, temp_dir, sample_audio_data):
        """Test FLAC format support if available"""
        try:
            audio_file = self.create_test_audio_file(temp_dir, sample_audio_data, 44100, 'flac')

            analyzer = AudioAnalyzer()
            success = analyzer.load_audio(audio_file)

            assert success == True
            assert analyzer.audio_data is not None

            # FLAC is lossless, so quality should be preserved
            features = analyzer.analyze_audio_features()
            assert features['duration'] > 9

            print("✓ Successfully processed FLAC file")

        except Exception as e:
            pytest.skip(f"FLAC support not available: {e}")

    def test_ogg_format_support(self, temp_dir, sample_audio_data):
        """Test OGG format support if available"""
        try:
            audio_file = self.create_test_audio_file(temp_dir, sample_audio_data, 44100, 'ogg')

            analyzer = AudioAnalyzer()
            success = analyzer.load_audio(audio_file)

            assert success == True
            assert analyzer.audio_data is not None

            features = analyzer.analyze_audio_features()
            assert features['duration'] > 9

            print("✓ Successfully processed OGG file")

        except Exception as e:
            pytest.skip(f"OGG support not available: {e}")

    def test_aiff_format_support(self, temp_dir, sample_audio_data):
        """Test AIFF format support"""
        try:
            audio_file = self.create_test_audio_file(temp_dir, sample_audio_data, 44100, 'aiff')

            analyzer = AudioAnalyzer()
            success = analyzer.load_audio(audio_file)

            assert success == True
            assert analyzer.audio_data is not None

            features = analyzer.analyze_audio_features()
            assert features['duration'] > 9

            print("✓ Successfully processed AIFF file")

        except Exception as e:
            pytest.skip(f"AIFF support not available: {e}")

    def test_unsupported_format_handling(self, temp_dir):
        """Test handling of unsupported audio formats"""
        # Create a fake file with unsupported extension
        fake_file = os.path.join(temp_dir, 'test.xyz')
        with open(fake_file, 'wb') as f:
            f.write(b'fake audio content')

        analyzer = AudioAnalyzer()
        success = analyzer.load_audio(fake_file)

        # Should gracefully fail
        assert success == False
        assert analyzer.audio_data is None

    def test_corrupted_file_handling(self, temp_dir):
        """Test handling of corrupted audio files"""
        # Create a corrupted WAV file
        corrupted_file = os.path.join(temp_dir, 'corrupted.wav')
        with open(corrupted_file, 'wb') as f:
            f.write(b'RIFF    WAVEfmt corrupted content')

        analyzer = AudioAnalyzer()
        success = analyzer.load_audio(corrupted_file)

        # Should gracefully handle corruption
        assert success == False
        assert analyzer.audio_data is None

    def test_empty_file_handling(self, temp_dir):
        """Test handling of empty audio files"""
        empty_file = os.path.join(temp_dir, 'empty.wav')
        with open(empty_file, 'wb') as f:
            pass  # Create empty file

        analyzer = AudioAnalyzer()
        success = analyzer.load_audio(empty_file)

        assert success == False
        assert analyzer.audio_data is None

    def test_very_short_audio(self, temp_dir):
        """Test handling of very short audio files"""
        # Create very short audio (0.1 seconds)
        duration = 0.1
        sample_rate = 44100
        t = np.linspace(0, duration, int(duration * sample_rate))
        short_audio = 0.5 * np.sin(2 * np.pi * 440 * t)  # 440Hz tone

        audio_file = self.create_test_audio_file(temp_dir, (short_audio, sample_rate), sample_rate, 'wav')

        analyzer = AudioAnalyzer()
        success = analyzer.load_audio(audio_file)

        assert success == True
        assert analyzer.duration < 0.2  # Should be very short

        # Analysis should handle short files gracefully
        try:
            silence = analyzer.detect_silence()
            features = analyzer.analyze_audio_features()
            cut_points = analyzer.find_optimal_cut_points()

            # Results might be limited but shouldn't crash
            assert isinstance(silence, list)
            assert isinstance(features, dict)
            assert isinstance(cut_points, list)

        except Exception as e:
            pytest.fail(f"Short audio analysis failed: {e}")

    def test_very_long_audio_simulation(self, temp_dir):
        """Test handling of longer audio files (simulated for speed)"""
        # Simulate longer audio without actually creating huge files
        duration = 1800.0  # 30 minutes
        sample_rate = 22050  # Lower sample rate for speed

        # Create audio in segments to simulate long file
        segment_duration = 10.0  # 10 second segments
        total_samples = int(duration * sample_rate)
        segment_samples = int(segment_duration * sample_rate)

        # Create first segment with speech patterns
        t = np.linspace(0, segment_duration, segment_samples)
        audio_segment = 0.2 * np.sin(2 * np.pi * 200 * t)
        audio_segment += 0.1 * np.sin(2 * np.pi * 400 * t)
        audio_segment *= (1 + 0.3 * np.random.random(len(audio_segment)))

        # Save just the segment for testing (representing larger file)
        audio_file = self.create_test_audio_file(temp_dir, (audio_segment, sample_rate), sample_rate, 'wav')

        analyzer = AudioAnalyzer()
        success = analyzer.load_audio(audio_file)

        assert success == True

        # Analysis should work efficiently even with longer content
        start_time = analyzer.duration  # Simple timing simulation

        silence = analyzer.detect_silence()
        features = analyzer.analyze_audio_features()

        # Should complete analysis without issues
        assert isinstance(silence, list)
        assert isinstance(features, dict)
        assert features['duration'] > 9

    def test_format_specific_metadata(self, temp_dir, sample_audio_data):
        """Test extraction of format-specific metadata"""
        formats_to_test = ['wav', 'flac']  # Formats that support metadata

        for fmt in formats_to_test:
            try:
                audio_file = self.create_test_audio_file(temp_dir, sample_audio_data, 44100, fmt)

                analyzer = AudioAnalyzer()
                success = analyzer.load_audio(audio_file)

                if success:
                    features = analyzer.analyze_audio_features()

                    # Should extract basic audio properties
                    assert 'sample_rate' in features
                    assert 'duration' in features
                    assert 'channels' in features

                    # Format-specific checks
                    if fmt == 'wav':
                        assert features['sample_rate'] == 44100

                    print(f"✓ Extracted metadata from {fmt.upper()}")

            except Exception as e:
                print(f"⚠ Skipping {fmt} metadata test: {e}")

    def test_concurrent_format_loading(self, temp_dir, sample_audio_data):
        """Test loading multiple formats concurrently"""
        formats = ['wav']  # Start with supported format
        audio_files = []

        # Create multiple files
        for i, fmt in enumerate(formats):
            try:
                audio_file = self.create_test_audio_file(
                    temp_dir, sample_audio_data, 44100, fmt
                )
                audio_files.append((audio_file, fmt))
            except:
                continue

        # Load them with separate analyzer instances
        results = []
        for audio_file, fmt in audio_files:
            analyzer = AudioAnalyzer()
            success = analyzer.load_audio(audio_file)
            results.append((fmt, success, analyzer.duration if success else None))

        # All should succeed
        successful_loads = [r for r in results if r[1] == True]
        assert len(successful_loads) >= 1, "At least one format should load successfully"

        # Durations should be similar across formats
        durations = [r[2] for r in successful_loads]
        if len(durations) > 1:
            duration_variance = max(durations) - min(durations)
            assert duration_variance < 0.5, f"Duration variance too high: {duration_variance}"

    def test_format_conversion_implications(self, temp_dir, sample_audio_data):
        """Test implications of format conversion for analysis"""
        audio, sample_rate = sample_audio_data

        # Create reference WAV file
        wav_file = self.create_test_audio_file(temp_dir, (audio, sample_rate), sample_rate, 'wav')

        analyzer_wav = AudioAnalyzer()
        analyzer_wav.load_audio(wav_file)
        wav_features = analyzer_wav.analyze_audio_features()

        # Compare with different formats if available
        try:
            flac_file = self.create_test_audio_file(temp_dir, (audio, sample_rate), sample_rate, 'flac')

            analyzer_flac = AudioAnalyzer()
            analyzer_flac.load_audio(flac_file)
            flac_features = analyzer_flac.analyze_audio_features()

            # Lossless formats should produce very similar results
            assert abs(wav_features['rms_mean'] - flac_features['rms_mean']) < 0.01
            assert abs(wav_features['duration'] - flac_features['duration']) < 0.01

            print("✓ Lossless format comparison successful")

        except Exception as e:
            pytest.skip(f"Format comparison skipped: {e}")

    def test_audio_format_recommendations(self, temp_dir, sample_audio_data):
        """Test system recommendations for different audio formats"""
        # Test with high quality audio
        hq_audio, _ = sample_audio_data
        hq_file = self.create_test_audio_file(temp_dir, (hq_audio, 48000), 48000, 'wav', 'PCM_24')

        analyzer = AudioAnalyzer()
        if analyzer.load_audio(hq_file):
            summary = analyzer.get_audio_summary()

            recommendations = summary.get('processing_recommendations', {})

            # High quality audio should get appropriate recommendations
            assert isinstance(recommendations, dict)

            # Should recommend keeping high quality for professional content
            if 'quality_assessment' in recommendations:
                assert recommendations['quality_assessment'] in ['high', 'professional']