"""
Global pytest configuration and fixtures for backend tests.
This file is automatically loaded by pytest and provides shared fixtures
across all test modules.
"""

import pytest
import tempfile
import os
import shutil
import numpy as np
from scipy.io import wavfile
from pathlib import Path

from models.timeline import Timeline, Track, Clip


@pytest.fixture(scope="session")
def temp_dir():
    """Create a temporary directory for the test session"""
    temp_dir = tempfile.mkdtemp(prefix="easyedit_tests_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_timeline():
    """Create a sample timeline for testing"""
    timeline = Timeline("Test Timeline", duration=60.0, frame_rate=25, sample_rate=48000)

    # Add audio track with clips
    audio_track = Track(0, "Audio Track", "audio")

    clip1 = Clip("Clip 1", 0.0, 25.0, 25.0, 0)
    clip2 = Clip("Clip 2", 25.0, 50.0, 25.0, 0)
    clip3 = Clip("Clip 3", 50.0, 60.0, 10.0, 0)

    audio_track.add_clip(clip1)
    audio_track.add_clip(clip2)
    audio_track.add_clip(clip3)

    timeline.add_track(audio_track)

    # Add some markers (if marker support exists)
    if hasattr(timeline, 'add_marker'):
        timeline.add_marker({"name": "Start", "time": 0.0, "comment": "Beginning of timeline"})
        timeline.add_marker({"name": "Middle", "time": 30.0, "comment": "Midpoint"})
        timeline.add_marker({"name": "End", "time": 60.0, "comment": "End of timeline"})

    return timeline


@pytest.fixture
def sample_audio_data():
    """Generate sample audio data for testing"""
    duration = 30.0  # 30 seconds
    sample_rate = 48000
    t = np.linspace(0, duration, int(duration * sample_rate))

    # Create realistic audio with speech-like characteristics
    audio = np.zeros_like(t)

    # Speech segment 1 (0-10s) - Higher energy
    mask1 = (t >= 0) & (t < 10)
    speech1 = 0.3 * np.sin(2 * np.pi * 200 * t[mask1])  # Fundamental frequency
    speech1 += 0.1 * np.sin(2 * np.pi * 400 * t[mask1])  # First harmonic
    speech1 += 0.05 * np.sin(2 * np.pi * 600 * t[mask1])  # Second harmonic
    speech1 *= (1 + 0.3 * np.random.random(len(speech1)))  # Natural variation
    audio[mask1] = speech1

    # Silence segment (10-13s)
    mask2 = (t >= 10) & (t < 13)
    audio[mask2] = 0.01 * np.random.random(np.sum(mask2))  # Very quiet background

    # Speech segment 2 (13-25s) - Different speaker characteristics
    mask3 = (t >= 13) & (t < 25)
    speech2 = 0.25 * np.sin(2 * np.pi * 150 * t[mask3])  # Lower fundamental
    speech2 += 0.08 * np.sin(2 * np.pi * 300 * t[mask3])  # Harmonics
    speech2 += 0.04 * np.sin(2 * np.pi * 450 * t[mask3])
    speech2 *= (1 + 0.4 * np.random.random(len(speech2)))
    audio[mask3] = speech2

    # Final silence (25-30s)
    mask4 = (t >= 25) & (t < 30)
    audio[mask4] = 0.005 * np.random.random(np.sum(mask4))

    return audio, sample_rate


@pytest.fixture
def sample_transcription_data():
    """Sample transcription data for testing"""
    return {
        'transcript': 'This is a sample transcription for testing purposes. The speaker changes here. Welcome to our test.',
        'segments': [
            {
                'speaker': 'Speaker1',
                'start_time': 0.5,
                'end_time': 8.5,
                'text': 'This is a sample transcription for testing purposes.',
                'confidence': 0.95,
                'words': [
                    {'text': 'This', 'start_time': 0.5, 'end_time': 0.8, 'confidence': 0.98},
                    {'text': 'is', 'start_time': 0.9, 'end_time': 1.1, 'confidence': 0.96},
                    {'text': 'a', 'start_time': 1.2, 'end_time': 1.3, 'confidence': 0.94},
                    {'text': 'sample', 'start_time': 1.4, 'end_time': 1.9, 'confidence': 0.97},
                    {'text': 'transcription', 'start_time': 2.0, 'end_time': 2.8, 'confidence': 0.93},
                    {'text': 'for', 'start_time': 2.9, 'end_time': 3.1, 'confidence': 0.95},
                    {'text': 'testing', 'start_time': 3.2, 'end_time': 3.7, 'confidence': 0.96},
                    {'text': 'purposes', 'start_time': 3.8, 'end_time': 4.4, 'confidence': 0.94},
                ]
            },
            {
                'speaker': 'Speaker1',
                'start_time': 9.0,
                'end_time': 10.5,
                'text': 'The speaker changes here.',
                'confidence': 0.88,
                'words': [
                    {'text': 'The', 'start_time': 9.0, 'end_time': 9.2, 'confidence': 0.92},
                    {'text': 'speaker', 'start_time': 9.3, 'end_time': 9.7, 'confidence': 0.89},
                    {'text': 'changes', 'start_time': 9.8, 'end_time': 10.2, 'confidence': 0.85},
                    {'text': 'here', 'start_time': 10.3, 'end_time': 10.5, 'confidence': 0.87},
                ]
            },
            {
                'speaker': 'Speaker2',
                'start_time': 15.0,
                'end_time': 18.5,
                'text': 'Welcome to our test.',
                'confidence': 0.91,
                'words': [
                    {'text': 'Welcome', 'start_time': 15.0, 'end_time': 15.6, 'confidence': 0.93},
                    {'text': 'to', 'start_time': 15.7, 'end_time': 15.9, 'confidence': 0.95},
                    {'text': 'our', 'start_time': 16.0, 'end_time': 16.3, 'confidence': 0.89},
                    {'text': 'test', 'start_time': 16.4, 'end_time': 16.8, 'confidence': 0.88},
                ]
            }
        ],
        'speakers': ['Speaker1', 'Speaker2'],
        'duration': 18.5,
        'confidence': 0.913,
        'word_count': 16
    }


@pytest.fixture
def mock_soniox_response():
    """Mock response from Soniox API"""
    return {
        'transcript': 'This is a mock transcription from Soniox API for testing.',
        'segments': [
            {
                'speaker': 'Speaker1',
                'start_time': 1.0,
                'end_time': 5.0,
                'text': 'This is a mock transcription from Soniox API for testing.',
                'confidence': 0.92,
            }
        ],
        'speakers': ['Speaker1'],
        'duration': 5.0,
        'confidence': 0.92,
        'processing_time': 2.5
    }


@pytest.fixture
def mock_openai_response():
    """Mock response from OpenAI API"""
    return {
        'enhanced_transcript': 'This is an enhanced transcription with better punctuation and formatting.',
        'summary': 'The audio contains a mock transcription for testing purposes.',
        'key_topics': ['testing', 'transcription', 'API'],
        'sentiment': 'neutral',
        'confidence': 0.89,
        'processing_time': 1.2
    }


@pytest.fixture
def sample_drt_content():
    """Sample DRT XML content for testing"""
    return '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="5">
    <project>
        <name>Test Project</name>
        <children>
            <sequence id="sequence-1">
                <name>Test Sequence</name>
                <duration>1500</duration>
                <rate>
                    <timebase>25</timebase>
                    <ntsc>FALSE</ntsc>
                </rate>
                <format>
                    <samplecharacteristics>
                        <rate>
                            <timebase>25</timebase>
                            <ntsc>FALSE</ntsc>
                        </rate>
                        <audio>
                            <samplerate>48000</samplerate>
                            <depth>24</depth>
                        </audio>
                    </samplecharacteristics>
                </format>
                <media>
                    <audio>
                        <format>
                            <samplecharacteristics>
                                <depth>24</depth>
                                <samplerate>48000</samplerate>
                            </samplecharacteristics>
                        </format>
                        <track>
                            <clipitem id="clipitem-1">
                                <name>Test Audio</name>
                                <enabled>TRUE</enabled>
                                <duration>1500</duration>
                                <rate>
                                    <timebase>25</timebase>
                                    <ntsc>FALSE</ntsc>
                                </rate>
                                <start>0</start>
                                <end>1500</end>
                                <in>0</in>
                                <out>1500</out>
                                <file id="file-1">
                                    <name>test_audio.wav</name>
                                    <pathurl>file://localhost/test_audio.wav</pathurl>
                                </file>
                            </clipitem>
                        </track>
                    </audio>
                </media>
                <timecode>
                    <rate>
                        <timebase>25</timebase>
                        <ntsc>FALSE</ntsc>
                    </rate>
                    <string>01:00:00:00</string>
                    <frame>90000</frame>
                </timecode>
            </sequence>
        </children>
    </project>
</xmeml>'''


@pytest.fixture
def create_audio_file(temp_dir):
    """Factory fixture to create audio files for testing"""
    def _create_file(filename, audio_data, sample_rate, format='wav'):
        filepath = os.path.join(temp_dir, filename)
        # Convert float audio to int16 for WAV files
        if audio_data.dtype == np.float32 or audio_data.dtype == np.float64:
            audio_int16 = (audio_data * 32767).astype(np.int16)
        else:
            audio_int16 = audio_data
        wavfile.write(filepath, sample_rate, audio_int16)
        return filepath

    return _create_file


@pytest.fixture
def create_drt_file(temp_dir):
    """Factory fixture to create DRT files for testing"""
    def _create_file(filename, content):
        filepath = os.path.join(temp_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return filepath

    return _create_file


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Set up test environment variables"""
    monkeypatch.setenv("EASYEDIT_TEST_MODE", "true")
    monkeypatch.setenv("EASYEDIT_LOG_LEVEL", "DEBUG")

    # Disable external API calls in tests by default
    monkeypatch.setenv("DISABLE_EXTERNAL_APIS", "true")


@pytest.fixture
def mock_flask_app():
    """Create a mock Flask app for testing"""
    from app import app
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    with app.test_client() as client:
        with app.app_context():
            yield client


# Performance testing fixtures
@pytest.fixture
def large_audio_data():
    """Generate large audio data for performance testing"""
    duration = 600.0  # 10 minutes
    sample_rate = 44100
    t = np.linspace(0, duration, int(duration * sample_rate))

    # Generate segments to simulate realistic audio
    segments = []
    segment_length = 30.0  # 30 seconds each
    num_segments = int(duration / segment_length)

    for i in range(num_segments):
        start_time = i * segment_length
        end_time = start_time + segment_length - 2  # Leave 2s gap

        start_idx = int(start_time * sample_rate)
        end_idx = int(end_time * sample_rate)

        if end_idx > len(t):
            end_idx = len(t)

        # Vary frequency and amplitude per segment
        freq = 150 + (i * 20)
        amp = 0.2 + (i * 0.01)

        segment_t = t[start_idx:end_idx]
        segment_audio = amp * np.sin(2 * np.pi * freq * segment_t)
        segment_audio *= (1 + 0.3 * np.random.random(len(segment_audio)))

        segments.append((start_idx, end_idx, segment_audio))

    # Combine segments
    audio = np.zeros_like(t)
    for start_idx, end_idx, segment_audio in segments:
        audio[start_idx:end_idx] = segment_audio

    return audio, sample_rate


@pytest.fixture(scope="session")
def test_data_dir():
    """Path to test data directory"""
    return Path(__file__).parent / "tests" / "sample_data"


# Parametrized fixtures for testing multiple scenarios
@pytest.fixture(params=['wav', 'flac'])
def audio_format(request):
    """Parametrized fixture for different audio formats"""
    return request.param


@pytest.fixture(params=[22050, 44100, 48000])
def sample_rate_variant(request):
    """Parametrized fixture for different sample rates"""
    return request.param


@pytest.fixture(params=[1, 2])
def channel_count(request):
    """Parametrized fixture for mono and stereo audio"""
    return request.param


# Cleanup fixtures
@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """Clean up temporary files after each test"""
    yield

    # Clean up any temp files created during tests
    temp_patterns = [
        "test_*.wav",
        "test_*.drt",
        "temp_*.xml",
        "*_temp.*"
    ]

    for pattern in temp_patterns:
        for file in Path.cwd().glob(pattern):
            try:
                file.unlink()
            except:
                pass  # Ignore cleanup errors