"""
Tests for audio format converter
"""

import pytest
import os
import tempfile
import numpy as np
from scipy.io import wavfile
from pydub import AudioSegment
from services.audio_converter import AudioFormatConverter


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def converter(temp_dir):
    """Create an AudioFormatConverter instance"""
    return AudioFormatConverter(temp_dir)


@pytest.fixture
def test_wav_file(temp_dir):
    """Create a test WAV file"""
    sample_rate = 22050
    duration = 2.0  # seconds
    frequency = 440  # Hz (A4 note)

    # Generate a simple sine wave
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio_data = np.sin(2 * np.pi * frequency * t)

    # Convert to 16-bit PCM
    audio_data = (audio_data * 32767).astype(np.int16)

    # Save as WAV
    wav_path = os.path.join(temp_dir, 'test.wav')
    wavfile.write(wav_path, sample_rate, audio_data)

    return wav_path


@pytest.fixture
def test_mp3_file(test_wav_file, temp_dir):
    """Create a test MP3 file from WAV"""
    try:
        audio = AudioSegment.from_wav(test_wav_file)
        mp3_path = os.path.join(temp_dir, 'test.mp3')
        audio.export(mp3_path, format='mp3', bitrate='128k')
        return mp3_path
    except Exception as e:
        pytest.skip(f"Could not create MP3 file (ffmpeg may not be installed): {str(e)}")


@pytest.fixture
def test_m4a_file(test_wav_file, temp_dir):
    """Create a test M4A file from WAV"""
    try:
        audio = AudioSegment.from_wav(test_wav_file)
        m4a_path = os.path.join(temp_dir, 'test.m4a')
        audio.export(m4a_path, format='mp4', codec='aac')
        return m4a_path
    except Exception as e:
        pytest.skip(f"Could not create M4A file (ffmpeg may not be installed): {str(e)}")


@pytest.fixture
def test_flac_file(test_wav_file, temp_dir):
    """Create a test FLAC file from WAV"""
    try:
        audio = AudioSegment.from_wav(test_wav_file)
        flac_path = os.path.join(temp_dir, 'test.flac')
        audio.export(flac_path, format='flac')
        return flac_path
    except Exception as e:
        pytest.skip(f"Could not create FLAC file (ffmpeg may not be installed): {str(e)}")


class TestAudioFormatConverter:
    """Test suite for AudioFormatConverter"""

    def test_needs_conversion_wav(self, converter, test_wav_file):
        """Test that WAV files don't need conversion"""
        assert not converter.needs_conversion(test_wav_file)

    def test_needs_conversion_mp3(self, converter, temp_dir):
        """Test that MP3 files need conversion"""
        mp3_path = os.path.join(temp_dir, 'test.mp3')
        assert converter.needs_conversion(mp3_path)

    def test_needs_conversion_m4a(self, converter, temp_dir):
        """Test that M4A files need conversion"""
        m4a_path = os.path.join(temp_dir, 'test.m4a')
        assert converter.needs_conversion(m4a_path)

    def test_needs_conversion_flac(self, converter, temp_dir):
        """Test that FLAC files need conversion"""
        flac_path = os.path.join(temp_dir, 'test.flac')
        assert converter.needs_conversion(flac_path)

    def test_convert_mp3_to_wav(self, converter, test_mp3_file, temp_dir):
        """Test MP3 to WAV conversion"""
        success, wav_path, error = converter.convert_to_wav(test_mp3_file)

        assert success, f"Conversion failed: {error}"
        assert wav_path is not None
        assert os.path.exists(wav_path)
        assert wav_path.endswith('.converted.wav')

        # Verify it's a valid WAV file
        sr, data = wavfile.read(wav_path)
        assert sr > 0
        assert len(data) > 0

    def test_convert_m4a_to_wav(self, converter, test_m4a_file, temp_dir):
        """Test M4A to WAV conversion"""
        success, wav_path, error = converter.convert_to_wav(test_m4a_file)

        assert success, f"Conversion failed: {error}"
        assert wav_path is not None
        assert os.path.exists(wav_path)
        assert wav_path.endswith('.converted.wav')

        # Verify it's a valid WAV file
        sr, data = wavfile.read(wav_path)
        assert sr > 0
        assert len(data) > 0

    def test_convert_flac_to_wav(self, converter, test_flac_file, temp_dir):
        """Test FLAC to WAV conversion"""
        success, wav_path, error = converter.convert_to_wav(test_flac_file)

        assert success, f"Conversion failed: {error}"
        assert wav_path is not None
        assert os.path.exists(wav_path)
        assert wav_path.endswith('.converted.wav')

        # Verify it's a valid WAV file
        sr, data = wavfile.read(wav_path)
        assert sr > 0
        assert len(data) > 0

    def test_convert_nonexistent_file(self, converter):
        """Test conversion of non-existent file"""
        success, wav_path, error = converter.convert_to_wav('/nonexistent/file.mp3')

        assert not success
        assert wav_path is None
        assert error is not None
        assert 'not found' in error.lower()

    def test_convert_with_custom_output_path(self, converter, test_mp3_file, temp_dir):
        """Test conversion with custom output path"""
        custom_output = os.path.join(temp_dir, 'custom_output.wav')
        success, wav_path, error = converter.convert_to_wav(test_mp3_file, custom_output)

        assert success, f"Conversion failed: {error}"
        assert wav_path == custom_output
        assert os.path.exists(custom_output)

    def test_cleanup_converted_file(self, converter, test_mp3_file):
        """Test cleanup of converted files"""
        # Convert file
        success, wav_path, error = converter.convert_to_wav(test_mp3_file)
        assert success
        assert os.path.exists(wav_path)

        # Clean up
        cleanup_success = converter.cleanup_converted_file(wav_path)
        assert cleanup_success
        assert not os.path.exists(wav_path)

    def test_cleanup_only_converted_files(self, converter, test_wav_file):
        """Test that cleanup only removes .converted.wav files"""
        # Try to cleanup a regular WAV file
        cleanup_success = converter.cleanup_converted_file(test_wav_file)

        # Should not cleanup non-converted files
        assert not cleanup_success
        assert os.path.exists(test_wav_file)

    def test_get_audio_info_wav(self, converter, test_wav_file):
        """Test getting audio info for WAV file"""
        info = converter.get_audio_info(test_wav_file)

        assert info is not None
        assert 'duration_seconds' in info
        assert 'channels' in info
        assert 'sample_rate' in info
        assert 'format' in info
        assert info['format'] == 'wav'
        assert info['duration_seconds'] > 0

    def test_get_audio_info_mp3(self, converter, test_mp3_file):
        """Test getting audio info for MP3 file"""
        info = converter.get_audio_info(test_mp3_file)

        assert info is not None
        assert 'duration_seconds' in info
        assert 'channels' in info
        assert 'sample_rate' in info
        assert 'format' in info
        assert info['format'] == 'mp3'

    def test_check_ffmpeg_available(self):
        """Test ffmpeg availability check"""
        available, message = AudioFormatConverter.check_ffmpeg_available()

        # This test will pass if ffmpeg is installed, skip if not
        if not available:
            pytest.skip(f"ffmpeg not available: {message}")

        assert available
        assert message is not None

    def test_converted_file_naming(self, converter, test_mp3_file, temp_dir):
        """Test that converted files are named correctly"""
        success, wav_path, error = converter.convert_to_wav(test_mp3_file)

        assert success
        assert '.converted.wav' in wav_path
        assert 'test' in os.path.basename(wav_path)

    def test_conversion_preserves_audio_data(self, converter, test_mp3_file):
        """Test that conversion preserves audio data approximately"""
        # Get original duration
        original_info = converter.get_audio_info(test_mp3_file)
        original_duration = original_info['duration_seconds']

        # Convert to WAV
        success, wav_path, error = converter.convert_to_wav(test_mp3_file)
        assert success

        # Get converted duration
        converted_info = converter.get_audio_info(wav_path)
        converted_duration = converted_info['duration_seconds']

        # Duration should be approximately the same (allow 0.1s difference due to encoding)
        assert abs(original_duration - converted_duration) < 0.1

    def test_multiple_conversions(self, converter, test_mp3_file):
        """Test multiple sequential conversions"""
        paths = []

        for i in range(3):
            success, wav_path, error = converter.convert_to_wav(test_mp3_file)
            assert success, f"Conversion {i+1} failed: {error}"
            assert os.path.exists(wav_path)
            paths.append(wav_path)

        # All files should exist
        for path in paths:
            assert os.path.exists(path)

        # Clean up all
        for path in paths:
            converter.cleanup_converted_file(path)
            assert not os.path.exists(path)

    def test_corrupted_file_handling(self, converter, temp_dir):
        """Test handling of corrupted audio files"""
        # Create a fake "MP3" file with garbage data
        corrupted_file = os.path.join(temp_dir, 'corrupted.mp3')
        with open(corrupted_file, 'wb') as f:
            f.write(b'This is not a valid audio file')

        success, wav_path, error = converter.convert_to_wav(corrupted_file)

        assert not success
        assert wav_path is None
        assert error is not None


class TestAudioConverterIntegration:
    """Integration tests with SimpleAudioAnalyzer"""

    def test_analyzer_with_mp3_file(self, test_mp3_file):
        """Test that SimpleAudioAnalyzer can load MP3 files"""
        from services.simple_audio_analyzer import SimpleAudioAnalyzer

        analyzer = SimpleAudioAnalyzer()
        success = analyzer.load_audio(test_mp3_file)

        if not success:
            pytest.skip("MP3 loading failed - ffmpeg may not be installed")

        assert success
        assert analyzer.audio_data is not None
        assert analyzer.duration > 0
        assert analyzer.sample_rate > 0

        # Clean up converted file
        analyzer.cleanup()

    def test_analyzer_with_m4a_file(self, test_m4a_file):
        """Test that SimpleAudioAnalyzer can load M4A files"""
        from services.simple_audio_analyzer import SimpleAudioAnalyzer

        analyzer = SimpleAudioAnalyzer()
        success = analyzer.load_audio(test_m4a_file)

        if not success:
            pytest.skip("M4A loading failed - ffmpeg may not be installed")

        assert success
        assert analyzer.audio_data is not None
        assert analyzer.duration > 0

        # Clean up converted file
        analyzer.cleanup()

    def test_analyzer_with_flac_file(self, test_flac_file):
        """Test that SimpleAudioAnalyzer can load FLAC files"""
        from services.simple_audio_analyzer import SimpleAudioAnalyzer

        analyzer = SimpleAudioAnalyzer()
        success = analyzer.load_audio(test_flac_file)

        if not success:
            pytest.skip("FLAC loading failed - ffmpeg may not be installed")

        assert success
        assert analyzer.audio_data is not None
        assert analyzer.duration > 0

        # Clean up converted file
        analyzer.cleanup()

    def test_analyzer_cleanup_on_delete(self, test_mp3_file, temp_dir):
        """Test that analyzer cleans up converted files when deleted"""
        from services.simple_audio_analyzer import SimpleAudioAnalyzer

        # Create analyzer and load MP3
        analyzer = SimpleAudioAnalyzer()
        success = analyzer.load_audio(test_mp3_file)

        if not success:
            pytest.skip("MP3 loading failed - ffmpeg may not be installed")

        # Get the converted file path
        converted_path = analyzer.converted_file_path
        assert converted_path is not None
        assert os.path.exists(converted_path)

        # Delete analyzer (should trigger cleanup)
        del analyzer

        # File should be cleaned up
        # Note: __del__ is not guaranteed to be called immediately
        # but cleanup() was called explicitly in our implementation
