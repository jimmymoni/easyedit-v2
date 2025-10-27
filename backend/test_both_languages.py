"""
Test transcription with both English and Malayalam to determine actual language
"""
import os
import sys
import time
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import storage

# Fix Unicode console output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Configuration
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'C:/Users/Tomso/Documents/easyedit-v2/backend/gcp-credentials/easyedit-stt-key.json'
bucket_name = 'easyedit-v2-audio-staging'
audio_file = r'C:\Users\Tomso\Downloads\for easy edit test.mp3'

def test_with_language(language_code, language_name):
    """Test transcription with specific language"""
    print("\n" + "=" * 80)
    print(f"TESTING WITH {language_name} ({language_code})")
    print("=" * 80)

    # Upload to GCS
    print("\n[1/3] Uploading to GCS...")
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    timestamp = int(time.time())
    blob_name = f"temp/test_{language_code}_{timestamp}.mp3"
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(audio_file)
    gcs_uri = f"gs://{bucket_name}/{blob_name}"
    print(f"   Uploaded: {gcs_uri}")

    # Configure recognition
    print(f"\n[2/3] Starting transcription with {language_code}...")
    speech_client = speech.SpeechClient()

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.MP3,
        language_code=language_code,
        enable_automatic_punctuation=True,
        enable_word_time_offsets=True,
        enable_word_confidence=True,
        model='default',
    )

    # Add diarization
    diarization_config = speech.SpeakerDiarizationConfig(
        enable_speaker_diarization=True,
        min_speaker_count=2,
        max_speaker_count=6,
    )
    config.diarization_config = diarization_config

    audio = speech.RecognitionAudio(uri=gcs_uri)

    start_time = time.time()
    operation = speech_client.long_running_recognize(config=config, audio=audio)
    response = operation.result(timeout=600)
    elapsed = time.time() - start_time

    print(f"   Processing time: {elapsed:.1f} seconds")

    # Process results
    print(f"\n[3/3] Processing results...")
    print(f"   Total results: {len(response.results)}")

    full_transcript = []
    total_words = 0
    total_confidence = 0
    result_count = 0

    for result in response.results:
        if not result.alternatives:
            continue

        alternative = result.alternatives[0]
        if alternative.transcript.strip():
            full_transcript.append(alternative.transcript)
            total_confidence += alternative.confidence
            result_count += 1

            if hasattr(alternative, 'words') and alternative.words:
                total_words += len(alternative.words)

    # Display results
    complete_transcript = ' '.join(full_transcript)
    avg_confidence = (total_confidence / result_count * 100) if result_count > 0 else 0

    print(f"\n   Words transcribed: {total_words}")
    print(f"   Average confidence: {avg_confidence:.1f}%")
    print(f"\n   TRANSCRIPT:")
    print("   " + "-" * 76)

    # Show transcript in chunks of 80 chars
    if complete_transcript:
        transcript_lines = [complete_transcript[i:i+76] for i in range(0, len(complete_transcript), 76)]
        for line in transcript_lines[:10]:  # Show first 10 lines
            print(f"   {line}")
        if len(transcript_lines) > 10:
            print(f"   ... ({len(transcript_lines) - 10} more lines)")
    else:
        print("   (No transcript generated)")

    print("   " + "-" * 76)

    # Cleanup
    print(f"\n   Cleaning up GCS file...")
    try:
        blob.delete()
        print("   Deleted successfully")
    except Exception as e:
        print(f"   Warning: Could not delete: {e}")

    return {
        'words': total_words,
        'confidence': avg_confidence,
        'transcript': complete_transcript,
        'char_count': len(complete_transcript)
    }

# Test with both languages
print("=" * 80)
print("DUAL-LANGUAGE TRANSCRIPTION TEST")
print("Testing same audio with English and Malayalam to find best match")
print("=" * 80)

results = {}

# Test English
results['English'] = test_with_language('en-US', 'English (US)')

# Test Malayalam
results['Malayalam'] = test_with_language('ml-IN', 'Malayalam (India)')

# Compare results
print("\n" + "=" * 80)
print("COMPARISON")
print("=" * 80)

print(f"\n{'Language':<15} {'Words':<10} {'Confidence':<15} {'Characters':<15}")
print("-" * 60)

for lang, data in results.items():
    print(f"{lang:<15} {data['words']:<10} {data['confidence']:<14.1f}% {data['char_count']:<15}")

print("\n" + "=" * 80)

# Recommend best language
best_lang = max(results.items(), key=lambda x: (x[1]['words'], x[1]['confidence']))
print(f"\nRECOMMENDATION: Use {best_lang[0]}")
print(f"   - More words detected ({best_lang[1]['words']} vs {min(r['words'] for r in results.values())})")
print(f"   - Higher confidence ({best_lang[1]['confidence']:.1f}%)")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
