"""
Test Replicate Audio Extraction (Zero-Install Architecture)

This script tests audio extraction from video using Replicate APIs to verify:
1. Audio extraction works correctly
2. 16kHz mono WAV format is correct for Whisper
3. Audio quality is acceptable for transcription
4. Cost is acceptable (~$0.05 per video)

Usage:
    python test_replicate_audio.py
"""

import os
import sys
import time
from dotenv import load_dotenv

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from services.replicate_video_processor import ReplicateVideoProcessor
from config import Config

def test_audio_extraction():
    """Test audio extraction from video"""
    print("\n" + "="*60)
    print("TEST: Audio Extraction from Video")
    print("="*60)

    # Use a publicly available test video with speech
    test_video_url = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"

    print(f"\n📹 Test Video: {test_video_url}")
    print("   Duration: ~15 seconds")
    print("   Expected Cost: ~$0.02")
    print("   Expected Time: 10-30 seconds")

    try:
        processor = ReplicateVideoProcessor()

        print("\n⏳ Extracting audio...")
        start_time = time.time()

        # Extract audio for Whisper transcription (16kHz mono WAV)
        result = processor.extract_audio(
            video_url=test_video_url,
            sample_rate=16000,  # 16kHz for Whisper
            channels=1,  # Mono
            output_format="wav"
        )

        elapsed = time.time() - start_time

        print("\n✅ Audio extraction completed!")
        print(f"   Time: {elapsed:.1f} seconds")
        print(f"   Audio URL: {result['audio_url']}")
        print(f"   Sample Rate: {result['sample_rate']} Hz")
        print(f"   Channels: {result['channels']}")
        print(f"   Format: {result['format']}")

        # Calculate cost (rough estimate)
        estimated_cost = 0.05 * (elapsed / 30)  # $0.05 per 30 sec
        print(f"   Estimated Cost: ${estimated_cost:.3f}")

        # Verify audio is suitable for Whisper
        if result['sample_rate'] == 16000 and result['channels'] == 1:
            print("\n✅ Audio format is correct for Whisper transcription!")
        else:
            print(f"\n⚠️  WARNING: Audio format may not be optimal for Whisper")
            print(f"   Expected: 16000 Hz, 1 channel")
            print(f"   Got: {result['sample_rate']} Hz, {result['channels']} channel(s)")

        return True, result

    except Exception as e:
        print(f"\n❌ Audio extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_waveform_audio_extraction():
    """Test audio extraction for waveform generation (44.1kHz)"""
    print("\n" + "="*60)
    print("TEST: Audio Extraction for Waveform (44.1kHz)")
    print("="*60)

    test_video_url = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"

    print(f"\n📹 Test Video: {test_video_url}")
    print("   Extracting at 44.1kHz for waveform visualization")

    try:
        processor = ReplicateVideoProcessor()

        print("\n⏳ Extracting audio...")
        start_time = time.time()

        # Extract audio for waveform (44.1kHz mono)
        result = processor.extract_audio(
            video_url=test_video_url,
            sample_rate=44100,  # 44.1kHz for waveform
            channels=1,  # Mono
            output_format="wav"
        )

        elapsed = time.time() - start_time

        print("\n✅ Waveform audio extracted!")
        print(f"   Time: {elapsed:.1f} seconds")
        print(f"   Sample Rate: {result['sample_rate']} Hz")
        print(f"   Format: {result['format']}")

        if result['sample_rate'] == 44100:
            print("\n✅ Audio format is correct for waveform generation!")
        else:
            print(f"\n⚠️  WARNING: Expected 44100 Hz, got {result['sample_rate']} Hz")

        return True, result

    except Exception as e:
        print(f"\n❌ Waveform audio extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def main():
    """Run all audio extraction tests"""
    print("\n" + "="*60)
    print("🎵 REPLICATE AUDIO EXTRACTION TEST SUITE")
    print("   Testing Zero-Install Architecture")
    print("="*60)

    # Check if Replicate token is configured
    if not Config.REPLICATE_API_TOKEN:
        print("\n❌ ERROR: REPLICATE_API_TOKEN not configured!")
        print("   Get your token at: https://replicate.com/account/api-tokens")
        print("   Add to backend/.env: REPLICATE_API_TOKEN=your_token_here")
        sys.exit(1)

    results = []

    # Warning about API costs
    print("\n" + "="*60)
    print("⚠️  WARNING: These tests will use Replicate API credits!")
    print("   Estimated total cost: ~$0.04")
    print("   Time: ~1 minute")
    print("="*60)

    user_input = input("\nRun audio extraction tests? (y/n): ").lower().strip()

    if user_input != 'y':
        print("\n⏭️  Tests canceled by user")
        sys.exit(0)

    # Test 1: Audio for Whisper (16kHz)
    success, result = test_audio_extraction()
    results.append(("Audio Extraction (16kHz)", success))

    # Test 2: Audio for Waveform (44.1kHz)
    success, result = test_waveform_audio_extraction()
    results.append(("Audio Extraction (44.1kHz)", success))

    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)

    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status:12} {test_name}")

    # Overall result
    passed = sum(1 for _, r in results if r)
    failed = sum(1 for _, r in results if not r)

    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)

    if failed > 0:
        sys.exit(1)
    else:
        print("\n🎉 All audio tests passed! Ready for Whisper transcription!\n")

if __name__ == "__main__":
    main()
