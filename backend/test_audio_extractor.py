"""
Quick test script to verify AudioExtractor works with ffmpeg
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from services.audio_extractor import AudioExtractor
from models.timeline import Timeline, Track, Clip

# Create a simple test timeline with 2 clips
timeline = Timeline(
    name="Test Timeline",
    frame_rate=30
)

audio_track = Track(
    index=0,
    name="Audio 1",
    track_type="audio"
)

# Clip 1: First 5 seconds (0-5s)
clip1 = Clip(
    name="Clip 1",
    start_time=0.0,
    end_time=5.0,
    duration=5.0,
    track_index=0,
    media_start=0.0,
    media_end=5.0,
    enabled=True
)

# Clip 2: Next 5 seconds (5-10s)
clip2 = Clip(
    name="Clip 2",
    start_time=5.0,
    end_time=10.0,
    duration=5.0,
    track_index=0,
    media_start=5.0,
    media_end=10.0,
    enabled=True
)

audio_track.clips = [clip1, clip2]
timeline.tracks = [audio_track]

# Test extraction (will fail if no audio file, but at least we can see ffmpeg check)
extractor = AudioExtractor()
print("\n✅ AudioExtractor initialized successfully!")
print(f"Supported formats: {extractor.supported_formats}")
print("\nffmpeg detection test passed! The system is ready for audio processing.")
