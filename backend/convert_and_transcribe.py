"""
Convert 24-bit/stereo WAV to 16-bit/mono and transcribe with Google Cloud STT
Fixes: "Timeline 1 (2).wav" is 24-bit stereo, Google needs 16-bit
"""
import os
import sys
import time
import wave
import subprocess
import tempfile
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import storage

# Fix Unicode console output
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Configuration
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'C:/Users/Tomso/Documents/easyedit-v2/backend/gcp-credentials/easyedit-stt-key.json'
bucket_name = 'easyedit-v2-audio-staging'

# Get input file
if len(sys.argv) < 2:
    print("Usage: python convert_and_transcribe.py <path_to_wav_file> [language_choice]")
    sys.exit(1)

audio_file = sys.argv[1].strip().strip('"')

if not os.path.exists(audio_file):
    print(f"❌ File not found: {audio_file}")
    sys.exit(1)

file_size_mb = os.path.getsize(audio_file) / (1024 * 1024)

print("=" * 80)
print("CONVERT & TRANSCRIBE WORKFLOW")
print("Converts 24-bit/stereo → 16-bit/mono → Transcribe")
print("=" * 80)
print(f"\n📁 Original file: {os.path.basename(audio_file)}")
print(f"📊 Size: {file_size_mb:.2f} MB")

# Read original WAV metadata
print(f"\n[1/6] Analyzing original audio...")
try:
    with wave.open(audio_file, 'rb') as wav_file:
        orig_channels = wav_file.getnchannels()
        orig_sampwidth = wav_file.getsampwidth()
        orig_framerate = wav_file.getframerate()
        orig_frames = wav_file.getnframes()
        duration = orig_frames / orig_framerate

        print(f"   Original format:")
        print(f"   - Channels: {orig_channels} ({'stereo' if orig_channels == 2 else 'mono'})")
        print(f"   - Sample width: {orig_sampwidth} bytes ({orig_sampwidth * 8}-bit)")
        print(f"   - Sample rate: {orig_framerate} Hz")
        print(f"   - Duration: {duration:.1f}s ({duration/60:.1f} min)")

        needs_conversion = (orig_sampwidth != 2 or orig_channels != 1)

        if needs_conversion:
            print(f"\n   ⚠️  Conversion needed:")
            if orig_sampwidth != 2:
                print(f"   - {orig_sampwidth * 8}-bit → 16-bit (required by Google)")
            if orig_channels != 1:
                print(f"   - Stereo → Mono (better transcription)")

except Exception as e:
    print(f"   ❌ Could not read WAV: {e}")
    sys.exit(1)

# Convert using ffmpeg
print(f"\n[2/6] Converting to 16-bit mono WAV...")

# Create temporary converted file
converted_file = tempfile.NamedTemporaryFile(suffix='_converted.wav', delete=False).name

try:
    # Check ffmpeg availability
    result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
    if result.returncode != 0:
        print("   ❌ ffmpeg not found")
        print("   Please install ffmpeg from: https://ffmpeg.org/download.html")
        sys.exit(1)

    # Convert: 16-bit, mono, keep original sample rate
    cmd = [
        'ffmpeg',
        '-i', audio_file,
        '-ar', str(orig_framerate),  # Keep original sample rate
        '-ac', '1',  # Mono
        '-sample_fmt', 's16',  # 16-bit signed integer
        '-y',  # Overwrite
        converted_file
    ]

    start_convert = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    if result.returncode != 0:
        print(f"   ❌ Conversion failed:")
        print(f"   {result.stderr[:500]}")
        os.unlink(converted_file)
        sys.exit(1)

    convert_time = time.time() - start_convert
    converted_size = os.path.getsize(converted_file) / (1024 * 1024)

    print(f"   ✅ Converted in {convert_time:.1f}s")
    print(f"   ✅ New size: {converted_size:.2f} MB")

    # Verify conversion
    with wave.open(converted_file, 'rb') as wav:
        print(f"   ✅ Format: {wav.getsampwidth() * 8}-bit, {wav.getnchannels()} channel, {wav.getframerate()} Hz")

except FileNotFoundError:
    print("   ❌ ffmpeg not found in PATH")
    print("   Install from: https://ffmpeg.org/download.html")
    if os.path.exists(converted_file):
        os.unlink(converted_file)
    sys.exit(1)
except subprocess.TimeoutExpired:
    print("   ❌ Conversion timed out")
    if os.path.exists(converted_file):
        os.unlink(converted_file)
    sys.exit(1)

# Upload to GCS
print(f"\n[3/6] Uploading to Google Cloud Storage...")

try:
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    timestamp = int(time.time())
    blob_name = f"temp/converted_{timestamp}.wav"
    blob = bucket.blob(blob_name)

    start_upload = time.time()
    blob.upload_from_filename(converted_file)
    upload_time = time.time() - start_upload

    gcs_uri = f"gs://{bucket_name}/{blob_name}"

    print(f"   ✅ Uploaded in {upload_time:.1f}s")
    print(f"   📍 GCS URI: {gcs_uri}")

except Exception as e:
    print(f"   ❌ Upload failed: {e}")
    os.unlink(converted_file)
    sys.exit(1)

# Configure transcription
print(f"\n[4/6] Configuring transcription...")

lang_choice = sys.argv[2] if len(sys.argv) >= 3 else "1"

if lang_choice == "2":
    primary_lang = "ml-IN"
    alt_langs = ["en-IN", "en-US"]
    print(f"   🌐 Malayalam primary + English alternatives")
else:
    primary_lang = "en-IN"
    alt_langs = ["ml-IN", "en-US"]
    print(f"   🌐 English (India) primary + Malayalam, English (US) alternatives")

try:
    speech_client = speech.SpeechClient()

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=orig_framerate,
        audio_channel_count=1,
        language_code=primary_lang,
        alternative_language_codes=alt_langs,
        enable_automatic_punctuation=True,
        enable_word_time_offsets=True,
        enable_word_confidence=True,
        model='default',
    )

    diarization_config = speech.SpeakerDiarizationConfig(
        enable_speaker_diarization=True,
        min_speaker_count=1,
        max_speaker_count=6,
    )
    config.diarization_config = diarization_config

    print(f"   ✅ Sample rate: {orig_framerate} Hz")
    print(f"   ✅ Diarization: 1-6 speakers")

except Exception as e:
    print(f"   ❌ Configuration failed: {e}")
    blob.delete()
    os.unlink(converted_file)
    sys.exit(1)

# Transcribe
print(f"\n[5/6] Transcribing...")
print(f"   ⏱️  Estimated time: {duration/60:.0f}-{duration/30:.0f} minutes")

try:
    audio = speech.RecognitionAudio(uri=gcs_uri)

    start_time = time.time()
    operation = speech_client.long_running_recognize(config=config, audio=audio)

    print(f"   ⏳ Processing...")

    last_progress = time.time()
    while not operation.done():
        if time.time() - last_progress > 30:
            elapsed = time.time() - start_time
            print(f"   ... {elapsed:.0f}s elapsed")
            last_progress = time.time()
        time.sleep(5)

    response = operation.result(timeout=3600)

    elapsed = time.time() - start_time
    print(f"   ✅ Completed in {elapsed:.1f}s ({elapsed/60:.1f} min)")

except Exception as e:
    print(f"   ❌ Transcription failed: {e}")
    blob.delete()
    os.unlink(converted_file)
    sys.exit(1)

# Process results
print(f"\n[6/6] Processing results...")
print(f"   Result segments: {len(response.results)}")

full_transcript = []
all_words = []
speaker_stats = {}
language_stats = {}

for result in response.results:
    if not result.alternatives:
        continue

    alternative = result.alternatives[0]
    detected_lang = result.language_code if hasattr(result, 'language_code') else primary_lang
    language_stats[detected_lang] = language_stats.get(detected_lang, 0) + 1

    if alternative.transcript.strip():
        full_transcript.append(alternative.transcript)

    if hasattr(alternative, 'words') and alternative.words:
        for word_info in alternative.words:
            speaker_tag = word_info.speaker_tag if hasattr(word_info, 'speaker_tag') else 0
            speaker = f"Speaker_{speaker_tag}"
            speaker_stats[speaker] = speaker_stats.get(speaker, 0) + 1

            all_words.append({
                'word': word_info.word,
                'speaker': speaker,
                'start': word_info.start_time.total_seconds() if hasattr(word_info, 'start_time') else 0.0,
                'end': word_info.end_time.total_seconds() if hasattr(word_info, 'end_time') else 0.0,
                'confidence': word_info.confidence if hasattr(word_info, 'confidence') else 0.0,
                'language': detected_lang
            })

complete_transcript = ' '.join(full_transcript)

print("\n" + "=" * 80)
print("TRANSCRIPTION RESULTS")
print("=" * 80)

print(f"\n📊 STATISTICS:")
print(f"   Total words: {len(all_words):,}")
print(f"   Speakers: {len(speaker_stats)}")
print(f"   Languages: {len(language_stats)}")
print(f"   Duration: {duration:.1f}s ({duration/60:.1f} min)")

if speaker_stats:
    print(f"\n👥 SPEAKER BREAKDOWN:")
    for speaker, count in sorted(speaker_stats.items()):
        print(f"   {speaker}: {count:,} words")

if language_stats:
    print(f"\n🌐 LANGUAGE DISTRIBUTION:")
    for lang, count in language_stats.items():
        print(f"   {lang}: {count} segments")

if all_words:
    avg_conf = sum(w['confidence'] for w in all_words) / len(all_words)
    print(f"\n📈 Average confidence: {avg_conf:.1%}")

print(f"\n📝 TRANSCRIPT PREVIEW (first 500 chars):")
print("-" * 80)
if complete_transcript:
    print(f"   {complete_transcript[:500]}")
    if len(complete_transcript) > 500:
        print(f"\n   ... ({len(complete_transcript) - 500:,} more characters)")
else:
    print("   (No transcript)")
print("-" * 80)

# Save to file
output_file = audio_file.replace('.wav', '_transcript.txt')
try:
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("FULL TRANSCRIPT\n")
        f.write("=" * 80 + "\n\n")
        f.write(complete_transcript + "\n\n")

        f.write("=" * 80 + "\n")
        f.write("WORD-BY-WORD WITH TIMING\n")
        f.write("=" * 80 + "\n\n")

        for i, w in enumerate(all_words, 1):
            f.write(f"{i:6d}. [{w['start']:7.2f}s] [{w['speaker']}] {w['word']}\n")

    print(f"\n💾 Saved to: {output_file}")
except Exception as e:
    print(f"\n⚠️  Could not save: {e}")

# Cleanup
print(f"\n[CLEANUP]")
try:
    blob.delete()
    print(f"   ✅ Deleted GCS file")
except:
    print(f"   ⚠️  Could not delete GCS file")

try:
    os.unlink(converted_file)
    print(f"   ✅ Deleted temporary converted file")
except:
    print(f"   ⚠️  Could not delete temp file")

print("\n" + "=" * 80)
print("✅ TRANSCRIPTION COMPLETE")
print("=" * 80)
print(f"\n   Words: {len(all_words):,}")
print(f"   Speakers: {len(speaker_stats)}")
print(f"   Processing time: {elapsed:.1f}s")
print(f"   Transcript saved: {output_file}")
print()
