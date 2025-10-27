"""
Test Google Cloud Speech-to-Text with English as PRIMARY language
Correct approach for English-dominant audio with occasional Malayalam words
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
print("CORRECTED MULTI-LANGUAGE TEST")
print("English PRIMARY + Malayalam ALTERNATIVE (for English-dominant audio)")
print("=" * 80)

# Upload to GCS
print("\n[1/4] Uploading to Google Cloud Storage...")
storage_client = storage.Client()
bucket = storage_client.bucket(bucket_name)

timestamp = int(time.time())
blob_name = f"temp/english_primary_{timestamp}.mp3"
blob = bucket.blob(blob_name)

blob.upload_from_filename(audio_file)
gcs_uri = f"gs://{bucket_name}/{blob_name}"

print(f"   Uploaded: {gcs_uri}")
print(f"   File size: {os.path.getsize(audio_file) / (1024*1024):.2f} MB")

# Configure recognition - ENGLISH PRIMARY
print("\n[2/4] Configuring multi-language recognition...")
speech_client = speech.SpeechClient()

# CORRECTED: English as primary, Malayalam as alternative
config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.MP3,
    language_code='en-IN',  # PRIMARY: English (India) for Indian accent
    alternative_language_codes=['ml-IN', 'en-US'],  # ALTERNATIVES: Malayalam + US English
    enable_automatic_punctuation=True,
    enable_word_time_offsets=True,
    enable_word_confidence=True,
    model='default',
)

# Add diarization
diarization_config = speech.SpeakerDiarizationConfig(
    enable_speaker_diarization=True,
    min_speaker_count=1,  # Single speaker
    max_speaker_count=2,
)
config.diarization_config = diarization_config

print(f"   ✅ Primary language: en-IN (English - India)")
print(f"   ✅ Alternative languages: ml-IN (Malayalam), en-US (English - US)")
print(f"   ✅ Diarization: enabled (1-2 speakers)")
print(f"   ✅ Model: default")

# Start transcription
print("\n[3/4] Starting transcription...")
print("   This should now capture the full 2 minutes of English speech...")

audio = speech.RecognitionAudio(uri=gcs_uri)

start_time = time.time()
operation = speech_client.long_running_recognize(config=config, audio=audio)

print("   Waiting for operation to complete...")
response = operation.result(timeout=600)

elapsed = time.time() - start_time
print(f"   ✓ Processing time: {elapsed:.1f} seconds")

# Process results
print(f"\n[4/4] Processing results...")
print(f"   Total result segments: {len(response.results)}")

full_transcript = []
all_segments = []
total_words = 0
language_stats = {}

for i, result in enumerate(response.results):
    if not result.alternatives:
        continue

    alternative = result.alternatives[0]

    # Track language
    detected_lang = result.language_code if hasattr(result, 'language_code') else 'en-in'
    language_stats[detected_lang] = language_stats.get(detected_lang, 0) + 1

    if alternative.transcript.strip():
        full_transcript.append(alternative.transcript)

    # Count words
    if hasattr(alternative, 'words') and alternative.words:
        total_words += len(alternative.words)

        # Build segments
        for word_info in alternative.words:
            speaker_tag = word_info.speaker_tag if hasattr(word_info, 'speaker_tag') else 0
            speaker = f"Speaker_{speaker_tag}"

            start_time_sec = word_info.start_time.total_seconds() if hasattr(word_info, 'start_time') else 0.0
            end_time_sec = word_info.end_time.total_seconds() if hasattr(word_info, 'end_time') else 0.0

            all_segments.append({
                'speaker': speaker,
                'word': word_info.word,
                'start': start_time_sec,
                'end': end_time_sec,
                'language': detected_lang
            })

# Display results
print("\n" + "=" * 80)
print("TRANSCRIPTION RESULTS")
print("=" * 80)

complete_transcript = ' '.join(full_transcript)

print(f"\n📊 STATISTICS:")
print(f"   Total words transcribed: {total_words} ✅")
print(f"   Total segments: {len(all_segments)}")
print(f"   Transcript length: {len(complete_transcript)} characters")

if language_stats:
    print(f"\n🌐 LANGUAGE DETECTION:")
    for lang, count in sorted(language_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"   {lang}: {count} segments")

print(f"\n📝 FULL TRANSCRIPT:")
print("-" * 80)

if complete_transcript:
    # Display transcript with proper formatting
    words_list = complete_transcript.split()
    current_line = ""

    for word in words_list:
        if len(current_line) + len(word) + 1 <= 76:
            current_line += word + " "
        else:
            print(f"   {current_line}")
            current_line = word + " "

    if current_line:
        print(f"   {current_line}")
else:
    print("   (No transcript generated)")

print("-" * 80)

# Show timing for first 20 words
print(f"\n⏱️  WORD TIMING (first 20 words):")
print("-" * 80)
for i, seg in enumerate(all_segments[:20]):
    print(f"{i+1:3d}. [{seg['start']:6.1f}s - {seg['end']:6.1f}s] {seg['word']} ({seg['language']})")

if len(all_segments) > 20:
    print(f"     ... and {len(all_segments) - 20} more words")

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

# Verification
print(f"\n✅ VERIFICATION:")
if total_words > 200:
    print(f"   ✅ SUCCESS! Transcribed {total_words} words")
    print(f"   ✅ This matches expectation for 2 minutes of continuous speech")
    print(f"   ✅ Google Cloud STT is working correctly!")
elif total_words > 100:
    print(f"   ⚠️  Transcribed {total_words} words (expected ~200-300)")
    print(f"   ⚠️  May have some gaps but generally working")
else:
    print(f"   ❌ Only {total_words} words (expected 200-300 for 2 min speech)")
    print(f"   ❌ Still having issues - may need further investigation")

print()
