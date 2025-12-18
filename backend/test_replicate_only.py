"""
Test Replicate Audio Extraction (No MediaConvert Required)

This tests audio extraction using Replicate API - works without AWS MediaConvert setup.
Cost: ~$0.02 per test
"""

import sys
import time

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

from services.replicate_video_processor import ReplicateVideoProcessor
from config import Config

def test_audio_extraction():
    """Test Replicate audio extraction with public video"""
    print("\n" + "="*60)
    print("REPLICATE AUDIO EXTRACTION TEST")
    print("="*60)

    # Use public test video (15 seconds, has speech)
    test_video_url = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"

    print(f"\nTest Video: {test_video_url}")
    print("Duration: ~15 seconds")
    print("Expected Cost: ~$0.02")
    print("Expected Time: 10-30 seconds")

    user_input = input("\nRun audio extraction test? (y/n): ").lower().strip()

    if user_input != 'y':
        print("\nTest skipped by user")
        return

    try:
        # Create processor (skip MediaConvert by catching error)
        print("\nInitializing Replicate processor...")

        # Import and initialize just the Replicate parts we need
        import replicate
        import httpx

        # Initialize Replicate client
        custom_timeout = httpx.Timeout(
            connect=30.0,
            read=600.0,
            write=600.0,
            pool=30.0
        )

        client = replicate.Client(
            api_token=Config.REPLICATE_API_TOKEN,
            timeout=custom_timeout
        )

        audio_model = "lucataco/extract-audio"

        print(f"Replicate API Token: {Config.REPLICATE_API_TOKEN[:20]}...")
        print(f"Audio Model: {audio_model}")

        print("\nExtracting audio...")
        start_time = time.time()

        # Extract audio using Replicate
        input_params = {
            "video": test_video_url,
            "output_format": "wav",
            "audio_quality": "high",
            "normalize_audio": False
        }

        output = replicate.run(
            f"{audio_model}:latest",
            input=input_params
        )

        elapsed = time.time() - start_time
        audio_url = output if isinstance(output, str) else str(output)

        print("\n" + "="*60)
        print("SUCCESS! Audio Extraction Complete")
        print("="*60)
        print(f"Time: {elapsed:.1f} seconds")
        print(f"Audio URL: {audio_url}")
        print(f"Format: wav")
        print(f"Quality: high")

        # Verify audio is accessible
        import requests
        response = requests.head(audio_url, timeout=10)
        if response.status_code == 200:
            print(f"\nAudio file verified:")
            print(f"  Status: {response.status_code} OK")
            if 'content-length' in response.headers:
                size_mb = int(response.headers['content-length']) / (1024 * 1024)
                print(f"  Size: {size_mb:.2f} MB")

        print("\n" + "="*60)
        print("READY FOR WHISPER TRANSCRIPTION!")
        print("="*60)
        print("\nThis audio can be sent to Replicate Whisper for:")
        print("  - Speech-to-text transcription")
        print("  - Speaker diarization")
        print("  - Multi-language support")

        return True

    except Exception as e:
        print(f"\nERROR: Audio extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("REPLICATE AUDIO EXTRACTION TEST")
    print("No AWS MediaConvert Required")
    print("="*60)

    success = test_audio_extraction()

    if success:
        print("\n" + "="*60)
        print("SUCCESS! Replicate integration working!")
        print("="*60)
        print("\nNext steps:")
        print("1. Integrate with upload flow")
        print("2. Add Whisper transcription")
        print("3. (Optional) Enable AWS MediaConvert later for video transcoding")
    else:
        print("\nTest failed - check error above")
        sys.exit(1)
