"""
Test script for Replicate Whisper integration

Usage:
    1. Set REPLICATE_API_TOKEN in your .env file
    2. Run: python test_replicate_whisper.py <path_to_audio_file>

Example:
    python test_replicate_whisper.py test_audio.wav
"""

import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from services.replicate_whisper_client import ReplicateWhisperClient
from services.transcription_service import TranscriptionServiceFactory
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def test_direct_client(audio_file: str):
    """Test ReplicateWhisperClient directly"""
    print("\n" + "="*80)
    print("TEST 1: Direct ReplicateWhisperClient")
    print("="*80)

    try:
        # Initialize client
        print("\n1. Initializing Replicate Whisper client...")
        client = ReplicateWhisperClient()
        print("   ✓ Client initialized successfully")

        # Check API status
        print("\n2. Checking API status...")
        if client.check_api_status():
            print("   ✓ API is accessible")
        else:
            print("   ✗ API check failed")
            return False

        # Get provider info
        print("\n3. Provider information:")
        info = client.get_provider_info()
        print(f"   Provider: {info['provider']}")
        print(f"   Model: {info['model_name']}")
        print(f"   GPU Cost: ${info['pricing']['cost_per_second']}/second")
        print(f"   Typical Cost: ${info['pricing']['typical_cost_per_hour_audio']}/hour")
        print(f"   Capabilities: {', '.join([k for k, v in info['capabilities'].items() if v])}")

        # Transcribe audio
        print(f"\n4. Transcribing audio file: {audio_file}")
        print("   This may take 30-60 seconds...")
        result = client.transcribe_audio(
            audio_file_path=audio_file,
            enable_speaker_diarization=True,
            language='en'
        )

        # Display results
        print("\n5. Transcription Results:")
        print(f"   ✓ Processing Time: {result['processing_time_seconds']:.1f} seconds")
        print(f"   ✓ Estimated Cost: ${result['cost_usd']:.4f}")
        print(f"   ✓ Audio Duration: {result['duration']:.1f} seconds")
        print(f"   ✓ Word Count: {result['word_count']} words")
        print(f"   ✓ Number of Speakers: {result['num_speakers']}")
        print(f"   ✓ Average Confidence: {result['confidence']:.2%}")
        print(f"   ✓ Language: {result['language']}")

        print("\n6. Full Transcript:")
        print("   " + "-"*76)
        print(f"   {result['transcript'][:500]}...")
        print("   " + "-"*76)

        print("\n7. Speaker Segments (first 5):")
        for i, seg in enumerate(result['segments'][:5]):
            print(f"   [{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['speaker']}: {seg['text'][:60]}...")

        print("\n✅ Direct client test PASSED\n")
        return True

    except Exception as e:
        print(f"\n❌ Direct client test FAILED: {str(e)}\n")
        import traceback
        traceback.print_exc()
        return False


def test_via_factory(audio_file: str):
    """Test via TranscriptionServiceFactory"""
    print("\n" + "="*80)
    print("TEST 2: TranscriptionServiceFactory")
    print("="*80)

    try:
        # Create service via factory
        print("\n1. Creating transcription service via factory...")
        service = TranscriptionServiceFactory.create()  # Should use Replicate by default
        print(f"   ✓ Service created: {service.provider_name}")

        # Check API status
        print("\n2. Checking API status...")
        if service.check_api_status():
            print("   ✓ API is accessible")
        else:
            print("   ✗ API check failed")
            return False

        # Transcribe audio
        print(f"\n3. Transcribing audio file: {audio_file}")
        print("   This may take 30-60 seconds...")
        result = service.transcribe_audio(
            audio_file_path=audio_file,
            enable_speaker_diarization=True,
            language_code='en'
        )

        # Display results
        print("\n4. Transcription Results:")
        print(f"   ✓ Provider: {result['provider']}")
        print(f"   ✓ Processing Time: {result['processing_time_seconds']:.1f} seconds")
        print(f"   ✓ Estimated Cost: ${result['cost_usd']:.4f}")
        print(f"   ✓ Word Count: {result['word_count']} words")
        print(f"   ✓ Number of Speakers: {len(result['speakers'])}")

        print("\n✅ Factory test PASSED\n")
        return True

    except Exception as e:
        print(f"\n❌ Factory test FAILED: {str(e)}\n")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function"""
    print("\n" + "="*80)
    print("REPLICATE WHISPER INTEGRATION TEST")
    print("="*80)

    # Check for audio file argument
    if len(sys.argv) < 2:
        print("\n❌ Error: No audio file provided")
        print("\nUsage: python test_replicate_whisper.py <path_to_audio_file>")
        print("\nExample: python test_replicate_whisper.py test_audio.wav")
        sys.exit(1)

    audio_file = sys.argv[1]

    # Check if file exists
    if not os.path.exists(audio_file):
        print(f"\n❌ Error: Audio file not found: {audio_file}")
        sys.exit(1)

    # Check for API token
    if not os.getenv('REPLICATE_API_TOKEN'):
        print("\n❌ Error: REPLICATE_API_TOKEN not set in environment")
        print("\nPlease:")
        print("1. Get your token from https://replicate.com/account")
        print("2. Add to .env file: REPLICATE_API_TOKEN=your_token_here")
        print("3. Or set environment variable: export REPLICATE_API_TOKEN=your_token_here")
        sys.exit(1)

    print(f"\nAudio file: {audio_file}")
    print(f"File size: {os.path.getsize(audio_file) / 1024 / 1024:.2f} MB")

    # Run tests
    test1_passed = test_direct_client(audio_file)
    test2_passed = test_via_factory(audio_file)

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Test 1 (Direct Client): {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Test 2 (Factory): {'✅ PASSED' if test2_passed else '❌ FAILED'}")

    if test1_passed and test2_passed:
        print("\n🎉 ALL TESTS PASSED! Replicate Whisper integration is working!")
        print("\nNext steps:")
        print("1. Integration is complete and ready for production use")
        print("2. Update frontend to use new transcription provider")
        print("3. Test with real-world audio files")
        print("4. Monitor costs in Replicate dashboard: https://replicate.com/account/billing")
    else:
        print("\n❌ SOME TESTS FAILED. Please check the errors above.")
        sys.exit(1)


if __name__ == '__main__':
    main()
