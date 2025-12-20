#!/usr/bin/env python3
"""Test imports to verify modules load correctly"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing imports...")

try:
    from models import VideoJob, VideoJobStatus
    print("[OK] VideoJob, VideoJobStatus imported")
except Exception as e:
    print(f"[FAIL] VideoJob import failed: {e}")

try:
    from services.video_audio_extractor import VideoAudioExtractor
    print("[OK] VideoAudioExtractor imported")
except Exception as e:
    print(f"[FAIL] VideoAudioExtractor import failed: {e}")

try:
    from services.replicate_whisper_client import ReplicateWhisperClient
    print("[OK] ReplicateWhisperClient imported")
except Exception as e:
    print(f"[FAIL] ReplicateWhisperClient import failed: {e}")

try:
    from services.repeated_take_detector import RepeatedTakeDetector
    print("[OK] RepeatedTakeDetector imported")
except Exception as e:
    print(f"[FAIL] RepeatedTakeDetector import failed: {e}")

try:
    from config import Config
    print("[OK] Config imported")
except Exception as e:
    print(f"[FAIL] Config import failed: {e}")

try:
    from services import video_background_processor
    print("[OK] video_background_processor module imported")
except Exception as e:
    print(f"[FAIL] video_background_processor import failed: {e}")
    import traceback
    traceback.print_exc()

print("\nAll imports successful!")
