import pytest
import tempfile
import shutil
import os
from unittest.mock import Mock, patch
import numpy as np
from scipy.io import wavfile

# Import our application modules
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from models.timeline import Timeline, Track, Clip

# Try to import AudioAnalyzer, fall back to SimpleAudioAnalyzer if not available
try:
    from services.audio_analyzer import AudioAnalyzer
except ImportError:
    from services.simple_audio_analyzer import SimpleAudioAnalyzer as AudioAnalyzer

from services.edit_rules import EditRulesEngine
from parsers.drt_parser import DRTParser
from parsers.drt_writer import DRTWriter

@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    temp_directory = tempfile.mkdtemp()
    yield temp_directory
    shutil.rmtree(temp_directory)

@pytest.fixture
def sample_timeline():
    """Create a sample timeline for testing"""
    timeline = Timeline(name="Test Timeline", frame_rate=25.0, sample_rate=48000)

    # Add audio track with clips
    audio_track = Track(index=0, name="Audio Track", track_type="audio")

    # Add some test clips
    clip1 = Clip(
        name="Clip 1",
        start_time=0.0,
        end_time=10.0,
        duration=10.0,
        track_index=0,
        enabled=True
    )

    clip2 = Clip(
        name="Clip 2",
        start_time=15.0,
        end_time=25.0,
        duration=10.0,
        track_index=0,
        enabled=True
    )

    audio_track.add_clip(clip1)
    audio_track.add_clip(clip2)
    timeline.add_track(audio_track)

    # Add some markers
    timeline.add_marker(5.0, "Marker 1", "Red")
    timeline.add_marker(20.0, "Marker 2", "Blue")

    timeline.calculate_duration()
    return timeline

@pytest.fixture
def sample_audio_data():
    """Generate sample audio data for testing"""
    duration = 30.0  # 30 seconds
    sample_rate = 22050
    samples = int(duration * sample_rate)

    # Generate audio with speech-like patterns and silence
    t = np.linspace(0, duration, samples)

    # Create segments with different characteristics
    audio = np.zeros(samples)

    # Speech-like segment (0-10s)
    speech_mask = (t >= 0) & (t < 10)
    audio[speech_mask] = 0.3 * np.sin(2 * np.pi * 200 * t[speech_mask]) * np.random.random(np.sum(speech_mask))

    # Silence segment (10-12s)
    silence_mask = (t >= 10) & (t < 12)
    audio[silence_mask] = 0.01 * np.random.random(np.sum(silence_mask))

    # Another speech segment (12-25s)
    speech_mask2 = (t >= 12) & (t < 25)
    audio[speech_mask2] = 0.2 * np.sin(2 * np.pi * 300 * t[speech_mask2]) * np.random.random(np.sum(speech_mask2))

    # Final silence (25-30s)
    silence_mask2 = (t >= 25) & (t < 30)
    audio[silence_mask2] = 0.005 * np.random.random(np.sum(silence_mask2))

    return audio, sample_rate

@pytest.fixture
def sample_transcription_data():
    """Create sample transcription data for testing"""
    return {
        'transcript': 'Hello, this is a test transcription with multiple speakers.',
        'segments': [
            {
                'speaker': 'Speaker1',
                'start_time': 0.5,
                'end_time': 5.2,
                'text': 'Hello, this is a test',
                'confidence': 0.95,
                'words': [
                    {'text': 'Hello', 'start_time': 0.5, 'end_time': 1.0, 'confidence': 0.98},
                    {'text': 'this', 'start_time': 1.2, 'end_time': 1.5, 'confidence': 0.95},
                    {'text': 'is', 'start_time': 1.6, 'end_time': 1.8, 'confidence': 0.92},
                    {'text': 'a', 'start_time': 1.9, 'end_time': 2.0, 'confidence': 0.90},
                    {'text': 'test', 'start_time': 2.1, 'end_time': 2.8, 'confidence': 0.96}
                ]
            },
            {
                'speaker': 'Speaker2',
                'start_time': 6.0,
                'end_time': 12.5,
                'text': 'transcription with multiple speakers',
                'confidence': 0.87,
                'words': [
                    {'text': 'transcription', 'start_time': 6.0, 'end_time': 7.2, 'confidence': 0.88},
                    {'text': 'with', 'start_time': 7.5, 'end_time': 7.8, 'confidence': 0.85},
                    {'text': 'multiple', 'start_time': 8.0, 'end_time': 8.9, 'confidence': 0.89},
                    {'text': 'speakers', 'start_time': 9.2, 'end_time': 10.1, 'confidence': 0.86}
                ]
            }
        ],
        'speakers': ['Speaker1', 'Speaker2'],
        'duration': 12.5,
        'confidence': 0.91,
        'word_count': 9
    }

@pytest.fixture
def sample_drt_xml():
    """Sample DRT XML content for testing"""
    return """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="5">
    <project>
        <name>Test Project</name>
        <children>
            <sequence id="sequence-1">
                <name>Test Timeline</name>
                <duration>750</duration>
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
                            <depth>16</depth>
                        </audio>
                    </samplecharacteristics>
                </format>
                <media>
                    <audio>
                        <format>
                            <samplecharacteristics>
                                <depth>16</depth>
                                <samplerate>48000</samplerate>
                            </samplecharacteristics>
                        </format>
                        <track>
                            <clipitem id="clipitem-1">
                                <name>Test Clip 1</name>
                                <enabled>TRUE</enabled>
                                <duration>250</duration>
                                <rate>
                                    <timebase>25</timebase>
                                    <ntsc>FALSE</ntsc>
                                </rate>
                                <start>0</start>
                                <end>250</end>
                                <in>0</in>
                                <out>250</out>
                                <file id="file-1">
                                    <name>test_audio.wav</name>
                                    <pathurl>file://localhost/test_audio.wav</pathurl>
                                    <rate>
                                        <timebase>25</timebase>
                                        <ntsc>FALSE</ntsc>
                                    </rate>
                                    <duration>250</duration>
                                </file>
                            </clipitem>
                            <clipitem id="clipitem-2">
                                <name>Test Clip 2</name>
                                <enabled>TRUE</enabled>
                                <duration>375</duration>
                                <rate>
                                    <timebase>25</timebase>
                                    <ntsc>FALSE</ntsc>
                                </rate>
                                <start>375</start>
                                <end>750</end>
                                <in>0</in>
                                <out>375</out>
                                <file id="file-2">
                                    <name>test_audio2.wav</name>
                                    <pathurl>file://localhost/test_audio2.wav</pathurl>
                                    <rate>
                                        <timebase>25</timebase>
                                        <ntsc>FALSE</ntsc>
                                    </rate>
                                    <duration>375</duration>
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
</xmeml>"""

@pytest.fixture
def mock_soniox_response():
    """Mock response from Soniox API"""
    return {
        'id': 'test-job-123',
        'status': 'COMPLETED',
        'transcript': 'This is a test transcript from Soniox API.',
        'words': [
            {
                'text': 'This',
                'start_ms': 500,
                'end_ms': 800,
                'confidence': 0.95,
                'speaker': 'Speaker1'
            },
            {
                'text': 'is',
                'start_ms': 850,
                'end_ms': 1000,
                'confidence': 0.92,
                'speaker': 'Speaker1'
            },
            {
                'text': 'a',
                'start_ms': 1050,
                'end_ms': 1150,
                'confidence': 0.88,
                'speaker': 'Speaker1'
            },
            {
                'text': 'test',
                'start_ms': 1200,
                'end_ms': 1600,
                'confidence': 0.96,
                'speaker': 'Speaker1'
            }
        ]
    }

@pytest.fixture
def mock_openai_response():
    """Mock response from OpenAI API"""
    return {
        'choices': [{
            'message': {
                'content': 'This is an enhanced transcript with proper punctuation and grammar.'
            }
        }]
    }

# Helper functions for testing
def create_test_audio_file(temp_dir, filename='test_audio.wav', duration=10.0, sample_rate=22050):
    """Create a test audio file"""
    # Generate simple audio data
    t = np.linspace(0, duration, int(duration * sample_rate))
    audio_data = 0.3 * np.sin(2 * np.pi * 440 * t)
    file_path = os.path.join(temp_dir, filename)

    # Convert to int16 and write using scipy
    audio_int16 = (audio_data * 32767).astype(np.int16)
    wavfile.write(file_path, sample_rate, audio_int16)

    return file_path

def create_test_drt_file(temp_dir, filename='test_timeline.drt', xml_content=None):
    """Create a test DRT file"""
    if xml_content is None:
        xml_content = sample_drt_xml()

    file_path = os.path.join(temp_dir, filename)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(xml_content)

    return file_path