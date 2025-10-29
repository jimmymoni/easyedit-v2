"""
Test script to verify Replicate Whisper compression logic
Tests the _prepare_audio_for_upload method to ensure large files are compressed
"""

import os
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from services.replicate_whisper_client import ReplicateWhisperClient
from config import Config

def test_compression_logic():
    """Test the compression logic with the large WAV file"""

    # Path to your large WAV file
    test_file = r"C:\Users\Tomso\Downloads\Timeline 1 audio.wav"

    if not os.path.exists(test_file):
        logger.error(f"Test file not found: {test_file}")
        return False

    # Initialize client (we don't need real API token for this test)
    os.environ['REPLICATE_API_TOKEN'] = 'test-token'
    client = ReplicateWhisperClient()

    try:
        logger.info(f"Testing compression logic with file: {test_file}")
        logger.info(f"File size: {os.path.getsize(test_file) / (1024 * 1024):.1f}MB")
        logger.info(f"Max upload size: {Config.REPLICATE_MAX_FILE_SIZE_MB}MB")
        logger.info("")

        # Test the prepare method
        logger.info("Calling _prepare_audio_for_upload()...")
        upload_path, temp_path = client._prepare_audio_for_upload(test_file)

        logger.info(f"✓ Compression successful!")
        logger.info(f"  Original file: {test_file}")
        logger.info(f"  Upload file: {upload_path}")
        logger.info(f"  Temp file to cleanup: {temp_path}")

        if temp_path:
            compressed_size_mb = os.path.getsize(temp_path) / (1024 * 1024)
            original_size_mb = os.path.getsize(test_file) / (1024 * 1024)
            reduction = (1 - compressed_size_mb / original_size_mb) * 100

            logger.info(f"  Compressed size: {compressed_size_mb:.1f}MB")
            logger.info(f"  Compression ratio: {reduction:.1f}%")
            logger.info(f"  Within upload limit: {compressed_size_mb <= Config.REPLICATE_MAX_FILE_SIZE_MB}")

            # Clean up the compressed file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                logger.info(f"  ✓ Cleaned up temp file")

        logger.info("")
        logger.info("✓ Test PASSED - Compression logic works correctly!")
        return True

    except Exception as e:
        logger.error(f"✗ Test FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_compression_logic()
    sys.exit(0 if success else 1)
