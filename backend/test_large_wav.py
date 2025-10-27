"""
Test Google Cloud Speech-to-Text with large WAV file (275MB)
Uses GCS upload (required for files > 10MB)
"""
import os
import sys
import time
import wave
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import storage

# Fix Unicode console output
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Configuration
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'C:/Users/Tomso/Documents/easyedit-v2/backend/gcp-credentials/easyedit-stt-key.json'
bucket_name = 'easyedit-v2-audio-staging'

# IMPORTANT: Pass WAV file path as command line argument
if len(sys.argv) < 2:
    print("Usage: python test_large_wav.py <path_to_wav_file>")
    print("\nExample:")
    print('  python test_large_wav.py "C:\\path\\to\\audio.wav"')
    sys.exit(1)

audio_file = sys.argv[1].strip().strip('"')

if not os.path.exists(audio_file):
    print(f"❌ File not found: {audio_file}")
    sys.exit(1)

file_size_mb = os.path.getsize(audio_file) / (1024 * 1024)

print("=" * 80)
print("LARGE WAV FILE TRANSCRIPTION TEST")
print("=" * 80)
print(f"\n📁 File: {os.path.basename(audio_file)}")
print(f"📊 Size: {file_size_mb:.2f} MB")

if file_size_mb > 1000:
    print(f"❌ File too large: {file_size_mb:.2f} MB (max 1000 MB)")
    sys.exit(1)

# Read WAV file metadata
print(f"\n[0/4] Reading WAV file metadata...")
try:
    with wave.open(audio_file, 'rb') as wav_file:
        n_channels = wav_file.getnchannels()
        sampwidth = wav_file.getsampwidth()
        framerate = wav_file.getframerate()
        n_frames = wav_file.getnframes()
        duration = n_frames / framerate

        print(f"   ✅ Channels: {n_channels}")
        print(f"   ✅ Sample width: {sampwidth} bytes")
        print(f"   ✅ Sample rate: {framerate} Hz")
        print(f"   ✅ Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")

        # Validate sample rate (Google supports specific rates)
        supported_rates = [8000, 16000, 32000, 44100, 48000]
        if framerate not in supported_rates:
            print(f"\n   ⚠️  WARNING: Sample rate {framerate} Hz may not be optimal")
            print(f"   ℹ️  Supported rates: {supported_rates}")
            print(f"   ℹ️  Will try to use {framerate} Hz anyway")

except Exception as e:
    print(f"   ❌ Could not read WAV metadata: {e}")
    print(f"   Will attempt transcription without sample rate specification")
    framerate = None
    n_channels = 1
    duration = 0

# Language configuration (can be passed as 2nd argument)
if len(sys.argv) >= 3:
    lang_choice = sys.argv[2]
else:
    lang_choice = "1"  # Default to English (India)

if lang_choice == "1":
    primary_lang = "en-IN"
    alt_langs = ["ml-IN", "en-US"]
    print(f"\n🌐 Language: English (India) primary + Malayalam, English (US) alternatives")
elif lang_choice == "2":
    primary_lang = "ml-IN"
    alt_langs = ["en-IN", "en-US"]
    print(f"\n🌐 Language: Malayalam (India) primary + English (India), English (US) alternatives")
else:
    primary_lang = "en-US"
    alt_langs = ["en-IN", "ml-IN"]
    print(f"\n🌐 Language: English (US) primary + English (India), Malayalam alternatives")

# Step 1: Upload to GCS
print(f"\n[1/4] Uploading {file_size_mb:.2f} MB to Google Cloud Storage...")
print(f"   This may take a few minutes for large files...")

try:
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    timestamp = int(time.time())
    blob_name = f"temp/large_wav_{timestamp}.wav"
    blob = bucket.blob(blob_name)

    # Upload with progress indication
    start_upload = time.time()
    blob.upload_from_filename(audio_file)
    upload_time = time.time() - start_upload

    gcs_uri = f"gs://{bucket_name}/{blob_name}"

    print(f"   ✅ Uploaded in {upload_time:.1f} seconds")
    print(f"   📍 GCS URI: {gcs_uri}")

except Exception as e:
    print(f"   ❌ Upload failed: {e}")
    sys.exit(1)

# Step 2: Configure recognition
print(f"\n[2/4] Configuring recognition...")

try:
    speech_client = speech.SpeechClient()

    # Build config with detected sample rate
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        language_code=primary_lang,
        alternative_language_codes=alt_langs,
        enable_automatic_punctuation=True,
        enable_word_time_offsets=True,
        enable_word_confidence=True,
        model='default',
        audio_channel_count=n_channels,
    )

    # Add sample rate if detected
    if framerate:
        config.sample_rate_hertz = framerate

    # Add diarization
    diarization_config = speech.SpeakerDiarizationConfig(
        enable_speaker_diarization=True,
        min_speaker_count=1,
        max_speaker_count=6,
    )
    config.diarization_config = diarization_config

    print(f"   ✅ Encoding: LINEAR16 (WAV)")
    print(f"   ✅ Primary language: {primary_lang}")
    print(f"   ✅ Alternative languages: {', '.join(alt_langs)}")
    print(f"   ✅ Diarization: enabled (1-6 speakers)")

except Exception as e:
    print(f"   ❌ Configuration failed: {e}")
    blob.delete()
    sys.exit(1)

# Step 3: Start transcription
print(f"\n[3/4] Starting transcription...")
print(f"   ⏱️  Large files may take several minutes to process")
print(f"   💡 Approximate time: {file_size_mb / 10:.0f}-{file_size_mb / 5:.0f} minutes")

try:
    audio = speech.RecognitionAudio(uri=gcs_uri)

    start_time = time.time()
    operation = speech_client.long_running_recognize(config=config, audio=audio)

    print(f"   ⏳ Waiting for operation to complete...")

    # Poll with progress indication
    last_progress_time = time.time()
    while not operation.done():
        if time.time() - last_progress_time > 30:
            elapsed = time.time() - start_time
            print(f"   ... still processing ({elapsed:.0f}s elapsed)")
            last_progress_time = time.time()
        time.sleep(5)

    response = operation.result(timeout=3600)  # 1 hour timeout for very large files

    elapsed = time.time() - start_time
    print(f"   ✅ Processing completed in {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")

except Exception as e:
    print(f"   ❌ Transcription failed: {e}")

    # Cleanup
    print(f"\n[CLEANUP] Deleting GCS file...")
    try:
        blob.delete()
    except:
        pass

    sys.exit(1)

# Step 4: Process results
print(f"\n[4/4] Processing results...")
print(f"   Total result segments: {len(response.results)}")

full_transcript = []
all_words = []
total_words = 0
language_stats = {}
speaker_stats = {}

for result in response.results:
    if not result.alternatives:
        continue

    alternative = result.alternatives[0]

    # Track language
    detected_lang = result.language_code if hasattr(result, 'language_code') else primary_lang
    language_stats[detected_lang] = language_stats.get(detected_lang, 0) + 1

    if alternative.transcript.strip():
        full_transcript.append(alternative.transcript)

    # Extract words with metadata
    if hasattr(alternative, 'words') and alternative.words:
        for word_info in alternative.words:
            speaker_tag = word_info.speaker_tag if hasattr(word_info, 'speaker_tag') else 0
            speaker = f"Speaker_{speaker_tag}"
            speaker_stats[speaker] = speaker_stats.get(speaker, 0) + 1

            start_time = word_info.start_time.total_seconds() if hasattr(word_info, 'start_time') else 0.0
            end_time = word_info.end_time.total_seconds() if hasattr(word_info, 'end_time') else 0.0
            confidence = word_info.confidence if hasattr(word_info, 'confidence') else 0.0

            all_words.append({
                'word': word_info.word,
                'speaker': speaker,
                'start': start_time,
                'end': end_time,
                'confidence': confidence,
                'language': detected_lang
            })

            total_words += 1

complete_transcript = ' '.join(full_transcript)

# Display results
print("\n" + "=" * 80)
print("TRANSCRIPTION RESULTS")
print("=" * 80)

print(f"\n📊 STATISTICS:")
print(f"   Total words: {total_words:,}")
print(f"   Total segments: {len(response.results)}")
print(f"   Transcript length: {len(complete_transcript):,} characters")
print(f"   Audio duration: {all_words[-1]['end']:.1f} seconds ({all_words[-1]['end']/60:.1f} minutes)" if all_words else "")

if speaker_stats:
    print(f"\n👥 SPEAKERS DETECTED:")
    for speaker, count in sorted(speaker_stats.items()):
        print(f"   {speaker}: {count:,} words")

if language_stats:
    print(f"\n🌐 LANGUAGE DISTRIBUTION:")
    for lang, count in sorted(language_stats.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / len(response.results)) * 100
        print(f"   {lang}: {count} segments ({percentage:.1f}%)")

# Calculate average confidence
if all_words:
    avg_confidence = sum(w['confidence'] for w in all_words) / len(all_words)
    print(f"\n📈 AVERAGE CONFIDENCE: {avg_confidence:.1%}")

print(f"\n📝 FULL TRANSCRIPT (first 1000 characters):")
print("-" * 80)
if complete_transcript:
    preview = complete_transcript[:1000]
    print(f"   {preview}")
    if len(complete_transcript) > 1000:
        print(f"\n   ... ({len(complete_transcript) - 1000:,} more characters)")
else:
    print("   (No transcript generated)")
print("-" * 80)

# Save to file
output_file = audio_file.replace('.wav', '_transcript.txt')
try:
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("FULL TRANSCRIPT\n")
        f.write("=" * 80 + "\n\n")
        f.write(complete_transcript + "\n\n")

        f.write("=" * 80 + "\n")
        f.write("DETAILED WORD LIST\n")
        f.write("=" * 80 + "\n\n")

        for i, word_data in enumerate(all_words, 1):
            f.write(f"{i:6d}. [{word_data['start']:7.2f}s] [{word_data['speaker']}] {word_data['word']}\n")

    print(f"\n💾 Transcript saved to: {output_file}")
except Exception as e:
    print(f"\n⚠️  Could not save transcript: {e}")

# Cleanup
print(f"\n[CLEANUP] Deleting temporary GCS file...")
try:
    blob.delete()
    print(f"   ✅ Deleted successfully")
except Exception as e:
    print(f"   ⚠️  Could not delete: {e}")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)

# Verification
print(f"\n✅ SUCCESS SUMMARY:")
print(f"   📊 Transcribed {total_words:,} words")
print(f"   👥 Detected {len(speaker_stats)} speaker(s)")
print(f"   🌐 Used {len(language_stats)} language(s)")
print(f"   ⏱️  Processing time: {elapsed:.1f}s")
print(f"   💾 Transcript saved to text file")
print()
