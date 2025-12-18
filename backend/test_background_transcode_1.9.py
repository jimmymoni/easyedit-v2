"""
Test script for Sub-Step 1.9: Background Transcoding Service

This script tests the background transcoding system by:
1. Creating a mock video file and VideoJob
2. Starting background transcoding
3. Monitoring progress updates
4. Verifying proxy file creation
5. Testing thread safety and duplicate prevention
"""

import os
import sys
import time
import logging
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_test_video():
    """Create a small test video file using FFmpeg"""
    try:
        import subprocess

        test_video_path = os.path.join('temp', 'test_transcode_input.mp4')
        os.makedirs('temp', exist_ok=True)

        # Create a 5-second test video (640x480, black screen with counter)
        command = [
            'ffmpeg',
            '-y',  # Overwrite without asking
            '-f', 'lavfi',
            '-i', 'color=c=black:s=640x480:d=5',  # 5 seconds of black
            '-f', 'lavfi',
            '-i', 'anullsrc=r=44100:cl=stereo',  # Silent audio
            '-shortest',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-c:a', 'aac',
            test_video_path
        ]

        logger.info("Creating test video file...")
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30
        )

        if result.returncode == 0 and os.path.exists(test_video_path):
            logger.info(f"✅ Test video created: {test_video_path}")
            return test_video_path
        else:
            logger.error(f"❌ Failed to create test video: {result.stderr.decode()}")
            return None

    except FileNotFoundError:
        logger.error("❌ FFmpeg not found. Please install FFmpeg to run this test.")
        return None
    except Exception as e:
        logger.error(f"❌ Error creating test video: {str(e)}")
        return None


def test_background_transcode():
    """Test background transcoding with a real video file"""
    print("\n" + "="*60)
    print("TEST 1: Background Transcoding - Basic Flow")
    print("="*60)

    from models import VideoJob, VideoJobStatus
    from services.video_background_processor import start_background_transcode, is_job_transcoding
    from services.video_metadata_extractor import extract_video_metadata
    from config import Config
    import uuid

    try:
        # Step 1: Create test video
        test_video_path = create_test_video()
        if not test_video_path:
            print("⚠️  Skipping test - could not create test video")
            return False

        # Step 2: Extract metadata
        logger.info("Extracting video metadata...")
        metadata = extract_video_metadata(test_video_path)

        if not metadata:
            logger.error("❌ Could not extract video metadata")
            return False

        logger.info(f"✅ Metadata extracted: {metadata['duration']:.1f}s, {metadata['resolution']}")

        # Step 3: Create VideoJob
        job_id = str(uuid.uuid4())
        video_jobs = {}

        # Ensure directories exist
        os.makedirs(Config.VIDEO_UPLOAD_DIR, exist_ok=True)
        os.makedirs(Config.VIDEO_PROXY_DIR, exist_ok=True)

        # Copy test video to upload directory
        import shutil
        original_filename = "test_video.mp4"
        permanent_path = os.path.join(Config.VIDEO_UPLOAD_DIR, f"{job_id}_{original_filename}")
        shutil.copy(test_video_path, permanent_path)

        video_job = VideoJob(
            job_id=job_id,
            user_id="test_user",
            original_filename=original_filename,
            original_path=permanent_path,
            original_size_bytes=os.path.getsize(permanent_path),
            original_format=metadata['format'],
            duration_seconds=metadata['duration'],
            width=metadata['width'],
            height=metadata['height'],
            fps=metadata['fps'],
            codec=metadata['codec'],
            bitrate=metadata['bitrate'],
            has_audio=metadata['has_audio']
        )

        video_job.update_status(VideoJobStatus.UPLOADED)
        video_jobs[job_id] = video_job

        logger.info(f"✅ VideoJob created: {job_id}")

        # Step 4: Start background transcoding
        logger.info("Starting background transcode...")
        success = start_background_transcode(job_id, video_jobs)

        if not success:
            logger.error("❌ Failed to start background transcode")
            return False

        logger.info("✅ Background transcode started")

        # Step 5: Check if job is transcoding
        if not is_job_transcoding(job_id):
            logger.error("❌ Job not marked as transcoding")
            return False

        logger.info("✅ Job marked as transcoding")

        # Step 6: Monitor progress
        logger.info("Monitoring progress...")
        start_time = time.time()
        last_progress = -1

        while True:
            job = video_jobs[job_id]
            current_progress = job.transcode_progress_percent

            # Log progress changes
            if current_progress != last_progress:
                logger.info(f"Progress: {current_progress}%")
                last_progress = current_progress

            # Check if completed
            if job.status == VideoJobStatus.READY:
                logger.info("✅ Transcoding completed successfully")
                break

            # Check if failed
            if job.status == VideoJobStatus.FAILED:
                logger.error(f"❌ Transcoding failed: {job.transcode_error}")
                return False

            # Timeout after 60 seconds
            if time.time() - start_time > 60:
                logger.error("❌ Transcoding timeout (>60s)")
                return False

            time.sleep(0.5)

        # Step 7: Verify proxy file
        if not job.proxy_path or not os.path.exists(job.proxy_path):
            logger.error(f"❌ Proxy file not found: {job.proxy_path}")
            return False

        proxy_size = os.path.getsize(job.proxy_path)
        logger.info(f"✅ Proxy file created: {job.proxy_path} ({proxy_size} bytes)")

        # Step 8: Verify proxy_ready flag
        if not job.proxy_ready:
            logger.error("❌ proxy_ready flag is False")
            return False

        logger.info("✅ proxy_ready flag is True")

        # Step 9: Verify proxy_url
        if not job.proxy_url:
            logger.error("❌ proxy_url not set")
            return False

        logger.info(f"✅ proxy_url set: {job.proxy_url}")

        # Step 10: Verify timestamps
        if not job.transcode_started_at:
            logger.error("❌ transcode_started_at not set")
            return False

        if not job.transcode_completed_at:
            logger.error("❌ transcode_completed_at not set")
            return False

        elapsed = (job.transcode_completed_at - job.transcode_started_at).total_seconds()
        logger.info(f"✅ Timestamps set (elapsed: {elapsed:.1f}s)")

        # Cleanup
        try:
            os.remove(test_video_path)
            os.remove(permanent_path)
            os.remove(job.proxy_path)
            logger.info("✅ Cleanup completed")
        except Exception as e:
            logger.warning(f"⚠️  Cleanup warning: {str(e)}")

        print("\n✅ Background Transcoding test PASSED")
        return True

    except Exception as e:
        logger.error(f"❌ Test error: {str(e)}", exc_info=True)
        return False


def test_duplicate_prevention():
    """Test that duplicate transcoding is prevented"""
    print("\n" + "="*60)
    print("TEST 2: Duplicate Transcoding Prevention")
    print("="*60)

    from models import VideoJob, VideoJobStatus
    from services.video_background_processor import start_background_transcode, is_job_transcoding
    from config import Config
    import uuid

    try:
        # Create a minimal VideoJob
        job_id = str(uuid.uuid4())
        video_jobs = {}

        # Create a fake original file
        os.makedirs(Config.VIDEO_UPLOAD_DIR, exist_ok=True)
        test_file = os.path.join(Config.VIDEO_UPLOAD_DIR, f"{job_id}_test.mp4")
        with open(test_file, 'wb') as f:
            f.write(b'fake video data')

        video_job = VideoJob(
            job_id=job_id,
            user_id="test_user",
            original_filename="test.mp4",
            original_path=test_file,
            original_size_bytes=100,
            original_format="mp4",
            duration_seconds=5.0,
            width=640,
            height=480,
            fps=30.0,
            codec="h264",
            bitrate=1000000,
            has_audio=True
        )

        video_job.update_status(VideoJobStatus.UPLOADED)
        video_jobs[job_id] = video_job

        # Start first transcode
        logger.info("Starting first transcode...")
        success1 = start_background_transcode(job_id, video_jobs)

        if not success1:
            logger.error("❌ First transcode failed to start")
            return False

        logger.info("✅ First transcode started")

        # Wait a moment for thread to initialize
        time.sleep(0.5)

        # Try to start duplicate transcode
        logger.info("Attempting duplicate transcode...")
        success2 = start_background_transcode(job_id, video_jobs)

        if success2:
            logger.error("❌ Duplicate transcode was allowed (should be prevented)")
            return False

        logger.info("✅ Duplicate transcode correctly prevented")

        # Wait for completion or timeout
        start_time = time.time()
        while is_job_transcoding(job_id):
            if time.time() - start_time > 30:
                logger.warning("⚠️  Transcode timeout (expected for fake file)")
                break
            time.sleep(0.5)

        # Cleanup
        try:
            os.remove(test_file)
        except:
            pass

        print("\n✅ Duplicate Prevention test PASSED")
        return True

    except Exception as e:
        logger.error(f"❌ Test error: {str(e)}", exc_info=True)
        return False


def test_job_not_found():
    """Test behavior when job doesn't exist"""
    print("\n" + "="*60)
    print("TEST 3: Job Not Found Handling")
    print("="*60)

    from services.video_background_processor import start_background_transcode

    try:
        video_jobs = {}
        fake_job_id = "00000000-0000-0000-0000-000000000000"

        logger.info("Attempting to transcode non-existent job...")
        success = start_background_transcode(fake_job_id, video_jobs)

        if success:
            logger.error("❌ Transcode should fail for non-existent job")
            return False

        logger.info("✅ Correctly rejected non-existent job")

        print("\n✅ Job Not Found test PASSED")
        return True

    except Exception as e:
        logger.error(f"❌ Test error: {str(e)}", exc_info=True)
        return False


def test_stats_api():
    """Test the stats API functions"""
    print("\n" + "="*60)
    print("TEST 4: Stats API")
    print("="*60)

    from services.video_background_processor import (
        get_active_transcode_jobs,
        get_transcode_stats
    )

    try:
        # Get stats
        stats = get_transcode_stats()
        logger.info(f"Stats: {stats}")

        # Verify structure
        assert 'active_count' in stats, "Missing active_count"
        assert 'active_jobs' in stats, "Missing active_jobs"
        assert 'job_locks_count' in stats, "Missing job_locks_count"

        logger.info("✅ Stats API returned correct structure")

        # Get active jobs
        active = get_active_transcode_jobs()
        logger.info(f"Active jobs: {active}")

        assert isinstance(active, set), "active_jobs should be a set"
        logger.info("✅ Active jobs API returned correct type")

        print("\n✅ Stats API test PASSED")
        return True

    except Exception as e:
        logger.error(f"❌ Test error: {str(e)}", exc_info=True)
        return False


def main():
    """Run all tests"""
    print("="*60)
    print("Sub-Step 1.9 - Background Transcoding Service Tests")
    print("="*60)

    # Check FFmpeg availability
    try:
        import subprocess
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
        if result.returncode == 0:
            print("✅ FFmpeg is available")
        else:
            print("⚠️  FFmpeg check failed")
    except FileNotFoundError:
        print("❌ FFmpeg not found - some tests will be skipped")
    except Exception as e:
        print(f"⚠️  FFmpeg check error: {str(e)}")

    results = []

    # Test 1: Basic background transcoding (requires FFmpeg)
    results.append(("Background Transcoding", test_background_transcode()))

    # Test 2: Duplicate prevention
    results.append(("Duplicate Prevention", test_duplicate_prevention()))

    # Test 3: Job not found
    results.append(("Job Not Found", test_job_not_found()))

    # Test 4: Stats API
    results.append(("Stats API", test_stats_api()))

    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")

    total_tests = len(results)
    passed_tests = sum(1 for _, passed in results if passed)

    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total_tests - passed_tests} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
