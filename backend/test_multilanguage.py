"""
Test Google Cloud Speech-to-Text with Multi-Language Recognition
Fixes code-mixed Malayalam-English transcription by using alternative_language_codes
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

print("=" * 80)
print("MULTI-LANGUAGE TRANSCRIPTION TEST")
print("Code-Mixed Malayalam-English Recognition")
print("=" * 80)

# Step 1: Upload to GCS
print("\n[1/4] Uploading to Google Cloud Storage...")
try:
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    timestamp = int(time.time())
    blob_name = f"temp/multilang_test_{timestamp}.mp3"
    blob = bucket.blob(blob_name)

    blob.upload_from_filename(audio_file)
    gcs_uri = f"gs://{bucket_name}/{blob_name}"

    print(f"   Uploaded: {gcs_uri}")
    print(f"   File size: {os.path.getsize(audio_file) / (1024*1024):.2f} MB")
except Exception as e:
    print(f"   ERROR: Upload failed: {e}")
    exit(1)

# Step 2: Configure recognition with alternative languages
print("\n[2/4] Configuring multi-language recognition...")
try:
    speech_client = speech.SpeechClient()

    # KEY FIX: Add alternative_language_codes for code-mixed content
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.MP3,
        language_code='ml-IN',  # Primary language: Malayalam (India)
        alternative_language_codes=['en-US', 'en-IN'],  # Alternative: English (US & India)
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

    print(f"   Primary language: ml-IN (Malayalam)")
    print(f"   Alternative languages: en-US, en-IN (English)")
    print(f"   Diarization: enabled (2-6 speakers)")
    print(f"   Model: default")

except Exception as e:
    print(f"   ERROR: Configuration failed: {e}")
    exit(1)

# Step 3: Start transcription
print("\n[3/4] Starting transcription...")
print("   This may take 1-2 minutes for a 5-6 minute audio file...")
try:
    audio = speech.RecognitionAudio(uri=gcs_uri)

    start_time = time.time()
    operation = speech_client.long_running_recognize(config=config, audio=audio)

    print("   Waiting for operation to complete...")
    response = operation.result(timeout=600)

    elapsed = time.time() - start_time
    print(f"   ✓ Processing time: {elapsed:.1f} seconds")

except Exception as e:
    print(f"   ERROR: Transcription failed: {e}")

    # Cleanup
    print("\n[CLEANUP] Deleting temporary GCS file...")
    try:
        blob.delete()
        print("   Deleted successfully")
    except:
        pass

    exit(1)

# Step 4: Process ALL results
print(f"\n[4/4] Processing results...")
print(f"   Total result segments: {len(response.results)}")

full_transcript = []
all_segments = []
speakers = set()
total_words = 0
language_stats = {}

for i, result in enumerate(response.results):
    if not result.alternatives:
        continue

    alternative = result.alternatives[0]

    # Track which language was detected for this segment
    detected_lang = result.language_code if hasattr(result, 'language_code') else 'unknown'
    language_stats[detected_lang] = language_stats.get(detected_lang, 0) + 1

    if alternative.transcript.strip():
        full_transcript.append(alternative.transcript)

    # Extract speaker segments with language info
    if hasattr(alternative, 'words') and alternative.words:
        current_speaker = None
        current_segment = []
        segment_start = None
        segment_lang = detected_lang

        for word_info in alternative.words:
            speaker_tag = word_info.speaker_tag if hasattr(word_info, 'speaker_tag') else 0
            speaker = f"Speaker_{speaker_tag}"
            speakers.add(speaker)

            start_time = word_info.start_time.total_seconds() if hasattr(word_info, 'start_time') else 0.0
            end_time = word_info.end_time.total_seconds() if hasattr(word_info, 'end_time') else 0.0

            total_words += 1

            # New segment when speaker changes
            if speaker != current_speaker:
                if current_segment:
                    all_segments.append({
                        'speaker': current_speaker,
                        'text': ' '.join(current_segment),
                        'start_time': segment_start,
                        'end_time': end_time,
                        'confidence': alternative.confidence,
                        'language': segment_lang
                    })

                current_speaker = speaker
                current_segment = [word_info.word]
                segment_start = start_time
            else:
                current_segment.append(word_info.word)

        # Save last segment
        if current_segment:
            all_segments.append({
                'speaker': current_speaker,
                'text': ' '.join(current_segment),
                'start_time': segment_start,
                'end_time': end_time,
                'confidence': alternative.confidence,
                'language': segment_lang
            })

# Display results
print("\n" + "=" * 80)
print("TRANSCRIPTION RESULTS")
print("=" * 80)

complete_transcript = ' '.join(full_transcript)
print(f"\n📊 STATISTICS:")
print(f"   Total words transcribed: {total_words}")
print(f"   Total segments: {len(all_segments)}")
print(f"   Speakers detected: {len(speakers)}")
print(f"   Transcript length: {len(complete_transcript)} characters")

if language_stats:
    print(f"\n🌐 LANGUAGE DETECTION:")
    for lang, count in sorted(language_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"   {lang}: {count} segments")

print(f"\n📝 FULL TRANSCRIPT:")
print("-" * 80)

if complete_transcript:
    # Display transcript in readable chunks
    transcript_lines = [complete_transcript[i:i+76] for i in range(0, len(complete_transcript), 76)]
    for line in transcript_lines[:20]:  # Show first 20 lines
        print(f"   {line}")
    if len(transcript_lines) > 20:
        print(f"\n   ... ({len(transcript_lines) - 20} more lines)")
else:
    print("   (No transcript generated)")

print("-" * 80)

# Show speaker segments with language tags
print(f"\n👥 SPEAKER SEGMENTS (showing first 15 of {len(all_segments)}):")
print("-" * 80)

for i, segment in enumerate(all_segments[:15]):
    lang_tag = f"[{segment.get('language', 'unknown')}]"
    time_range = f"({segment['start_time']:.1f}s - {segment['end_time']:.1f}s)"

    print(f"{i+1}. [{segment['speaker']}] {lang_tag} {time_range}")

    # Show first 100 chars of text
    text = segment['text']
    if len(text) > 100:
        print(f"   {text[:100]}...")
    else:
        print(f"   {text}")
    print(f"   Confidence: {segment['confidence']:.1%}")
    print()

if len(all_segments) > 15:
    print(f"   ... and {len(all_segments) - 15} more segments")

# Cleanup
print("\n[CLEANUP] Deleting temporary GCS file...")
try:
    blob.delete()
    print("   ✓ Deleted successfully")
except Exception as e:
    print(f"   Warning: Could not delete: {e}")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)

# Summary
print(f"\n✅ SUCCESS INDICATORS:")
if total_words > 100:
    print(f"   ✓ Transcribed {total_words} words (expected hundreds for 5-6 min audio)")
else:
    print(f"   ⚠ Only {total_words} words (expected hundreds - may need audio quality check)")

if len(speakers) >= 1:
    print(f"   ✓ Detected {len(speakers)} speaker(s)")

if len(language_stats) > 1:
    print(f"   ✓ Multi-language detected: {', '.join(language_stats.keys())}")
elif 'ml-IN' in language_stats:
    print(f"   ℹ Only Malayalam detected (English portions may be minimal)")
elif 'en-US' in language_stats or 'en-IN' in language_stats:
    print(f"   ℹ Only English detected (Malayalam portions may be minimal)")

print()
