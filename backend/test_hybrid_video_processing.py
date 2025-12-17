"""
Test Hybrid Cloud Video Processing (AWS MediaConvert + Replicate)

This script tests the complete cloud-based video processing pipeline:
1. AWS MediaConvert for video transcoding (H.264 MP4)
2. Replicate for audio extraction (WAV for Whisper)

Prerequisites:
1. AWS credentials configured in backend/.env:
   - AWS_ACCESS_KEY_ID
   - AWS_SECRET_ACCESS_KEY
   - AWS_REGION
   - S3_VIDEO_BUCKET
   - AWS_MEDIACONVERT_ROLE_ARN (IAM role with MediaConvert + S3 permissions)

2. Replicate API token in backend/.env:
   - REPLICATE_API_TOKEN

3. Test video uploaded to S3:
   - Upload a small test video to s3://your-bucket/test/sample.mp4

Usage:
    python test_hybrid_video_processing.py

Cost Estimate:
    - MediaConvert: ~$0.05 for 5-min video
    - Replicate audio: ~$0.02
    - Total: ~$0.07 per test run
"""

import os
import sys
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
import time


def test_configuration():
    """Test 1: Verify all configuration is set up correctly"""
    print("\n" + "="*60)
    print("TEST 1: Configuration Verification")
    print("="*60)

    errors = []

    # Check AWS credentials
    if not Config.AWS_ACCESS_KEY_ID:
        errors.append("❌ AWS_ACCESS_KEY_ID not set")
    else:
        print(f"✅ AWS_ACCESS_KEY_ID: {Config.AWS_ACCESS_KEY_ID[:10]}...")

    if not Config.AWS_SECRET_ACCESS_KEY:
        errors.append("❌ AWS_SECRET_ACCESS_KEY not set")
    else:
        print(f"✅ AWS_SECRET_ACCESS_KEY: {Config.AWS_SECRET_ACCESS_KEY[:10]}...")

    if not Config.AWS_REGION:
        errors.append("❌ AWS_REGION not set")
    else:
        print(f"✅ AWS_REGION: {Config.AWS_REGION}")

    if not Config.S3_VIDEO_BUCKET:
        errors.append("❌ S3_VIDEO_BUCKET not set")
    else:
        print(f"✅ S3_VIDEO_BUCKET: {Config.S3_VIDEO_BUCKET}")

    if not Config.AWS_MEDIACONVERT_ROLE_ARN:
        errors.append("❌ AWS_MEDIACONVERT_ROLE_ARN not set")
    else:
        print(f"✅ AWS_MEDIACONVERT_ROLE_ARN: {Config.AWS_MEDIACONVERT_ROLE_ARN[:30]}...")

    # Check Replicate token
    if not Config.REPLICATE_API_TOKEN:
        errors.append("❌ REPLICATE_API_TOKEN not set")
    else:
        print(f"✅ REPLICATE_API_TOKEN: {Config.REPLICATE_API_TOKEN[:20]}...")

    if errors:
        print("\n❌ Configuration errors found:")
        for error in errors:
            print(f"   {error}")
        print("\nPlease update backend/.env with required credentials.")
        return False
    else:
        print("\n✅ All configuration verified!")
        return True


def test_processor_initialization():
    """Test 2: Initialize hybrid processor"""
    print("\n" + "="*60)
    print("TEST 2: Processor Initialization")
    print("="*60)

    try:
        processor = ReplicateVideoProcessor()
        print("✅ ReplicateVideoProcessor initialized successfully")
        print(f"   AWS MediaConvert endpoint: {processor.mediaconvert.endpoint_url}")
        print(f"   Replicate audio model: {processor.audio_extract_model}")
        print(f"   Replicate merge model: {processor.video_merge_model}")
        return True, processor
    except Exception as e:
        print(f"❌ Failed to initialize processor: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_mediaconvert_transcode(processor):
    """Test 3: AWS MediaConvert video transcoding"""
    print("\n" + "="*60)
    print("TEST 3: AWS MediaConvert Transcoding (DRY RUN)")
    print("="*60)

    print("\n⚠️  WARNING: This test requires a video uploaded to S3!")
    print(f"   Expected S3 URL: s3://{Config.S3_VIDEO_BUCKET}/test/sample.mp4")
    print("\n   To upload a test video:")
    print("   aws s3 cp your-video.mp4 s3://your-bucket/test/sample.mp4")

    user_input = input("\nDo you have a test video uploaded to S3? (y/n): ").lower().strip()

    if user_input != 'y':
        print("\n⏭️  Skipped transcoding test - no test video available")
        print("   Transcoding functionality exists but cannot be tested without S3 video")
        return "skipped"

    # Get S3 URL from user
    print(f"\nDefault S3 URL: s3://{Config.S3_VIDEO_BUCKET}/test/sample.mp4")
    custom_url = input("Enter custom S3 URL (or press Enter for default): ").strip()
    test_video_s3_url = custom_url if custom_url else f"s3://{Config.S3_VIDEO_BUCKET}/test/sample.mp4"

    print(f"\n📹 Test Video: {test_video_s3_url}")
    print("   Expected Cost: ~$0.05-0.10 (depends on video length)")
    print("   Expected Time: 1-5 minutes (depends on video length)")
    print("   Quality: GOOD preset (fast single-pass encoding)")

    confirm = input("\nProceed with transcoding? (y/n): ").lower().strip()

    if confirm != 'y':
        print("\n⏭️  Transcoding test canceled by user")
        return "skipped"

    try:
        print("\n⏳ Starting AWS MediaConvert transcode (async mode)...")
        start_time = time.time()

        # Test async mode (submit job and return immediately)
        result = processor.transcode_video(
            video_url=test_video_s3_url,
            output_prefix=None,  # Auto-generate: proxy/test/
            max_width=1280,  # Lower resolution for faster test
            max_height=720,
            preset="GOOD",  # Fast preset
            async_mode=True  # Don't wait for completion
        )

        elapsed = time.time() - start_time

        print(f"\n✅ MediaConvert job submitted successfully!")
        print(f"   Job ID: {result['job_id']}")
        print(f"   Status: {result['status']}")
        print(f"   Output will be at: {result['output_s3_key']}")
        print(f"   Submission time: {elapsed:.1f} seconds")

        print("\n📊 Job is now processing in the background")
        print("   You can check status in AWS MediaConvert console:")
        print(f"   https://console.aws.amazon.com/mediaconvert/home?region={Config.AWS_REGION}#/jobs/summary/{result['job_id']}")

        return True

    except Exception as e:
        print(f"\n❌ Transcoding failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_replicate_audio_extraction():
    """Test 4: Replicate audio extraction"""
    print("\n" + "="*60)
    print("TEST 4: Replicate Audio Extraction")
    print("="*60)

    # Use a publicly available test video
    test_video_url = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"

    print(f"\n📹 Test Video: {test_video_url}")
    print("   Duration: ~15 seconds")
    print("   Expected Cost: ~$0.02")
    print("   Expected Time: 10-30 seconds")

    user_input = input("\nRun audio extraction test? (y/n): ").lower().strip()

    if user_input != 'y':
        print("\n⏭️  Audio extraction test skipped")
        return "skipped"

    try:
        processor = ReplicateVideoProcessor()

        print("\n⏳ Extracting audio...")
        start_time = time.time()

        result = processor.extract_audio(
            video_url=test_video_url,
            output_format="wav",
            audio_quality="high",
            normalize_audio=False
        )

        elapsed = time.time() - start_time

        print("\n✅ Audio extraction completed!")
        print(f"   Time: {elapsed:.1f} seconds")
        print(f"   Audio URL: {result['audio_url']}")
        print(f"   Format: {result['format']}")
        print(f"   Quality: {result['quality']}")
        print(f"\n   Note: {result['note']}")

        # Verify audio is accessible
        import requests
        response = requests.head(result['audio_url'], timeout=10)
        if response.status_code == 200:
            print(f"\n✅ Audio file is accessible!")
            print(f"   Status: {response.status_code}")
            if 'content-length' in response.headers:
                size_mb = int(response.headers['content-length']) / (1024 * 1024)
                print(f"   Size: {size_mb:.2f} MB")
        else:
            print(f"\n⚠️  Audio URL returned status {response.status_code}")

        return True

    except Exception as e:
        print(f"\n❌ Audio extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("🚀 HYBRID CLOUD VIDEO PROCESSING TEST SUITE")
    print("   AWS MediaConvert + Replicate Integration")
    print("="*60)

    results = []

    # Test 1: Configuration
    config_ok = test_configuration()
    results.append(("Configuration", config_ok))

    if not config_ok:
        print("\n❌ Cannot proceed without proper configuration")
        print("   Please update backend/.env with required credentials")
        sys.exit(1)

    # Test 2: Initialization
    init_ok, processor = test_processor_initialization()
    results.append(("Initialization", init_ok))

    if not init_ok:
        print("\n❌ Cannot proceed without successful initialization")
        sys.exit(1)

    # Test 3: MediaConvert (optional - requires S3 video)
    transcode_result = test_mediaconvert_transcode(processor)
    results.append(("MediaConvert Transcode", transcode_result))

    # Test 4: Replicate Audio (uses public video)
    audio_result = test_replicate_audio_extraction()
    results.append(("Replicate Audio", audio_result))

    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)

    for test_name, result in results:
        if result == "skipped":
            status = "⏭️  SKIPPED"
        elif result:
            status = "✅ PASSED"
        else:
            status = "❌ FAILED"

        print(f"{status:12} {test_name}")

    # Overall result
    passed = sum(1 for _, r in results if r is True)
    failed = sum(1 for _, r in results if r is False)
    skipped = sum(1 for _, r in results if r == "skipped")

    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    print("="*60)

    if failed > 0:
        print("\n⚠️  Some tests failed - review errors above")
        sys.exit(1)
    else:
        print("\n🎉 All required tests passed!")
        print("\n📋 Next Steps:")
        print("   1. Set up AWS MediaConvert IAM role (see docs below)")
        print("   2. Upload test video to S3 for full integration test")
        print("   3. Run Whisper transcription on extracted audio")
        print("   4. Integrate with upload flow (background processor)")


if __name__ == "__main__":
    main()
