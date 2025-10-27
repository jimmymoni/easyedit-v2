"""
Test with WAV conversion first - eliminate MP3 encoding issues
"""
import os
import sys
import time
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
audio_file = r'C:\Users\Tomso\Downloads\for easy edit test.mp3'

print("=" * 80)
print("TEST WITH WAV CONVERSION")
print("Convert MP3 → WAV → Transcribe (eliminate encoding issues)")
print("=" * 80)

# Step 1: Convert MP3 to WAV
print("\n[1/5] Converting MP3 to WAV...")

# Check if ffmpeg exists by trying to run it
try:
    result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
    if result.returncode != 0:
        print("   ❌ ffmpeg not found - cannot convert")
        print("   Please install ffmpeg first")
        sys.exit(1)
except (FileNotFoundError, subprocess.TimeoutExpired):
    print("   ❌ ffmpeg not found in PATH")
    print("   Skipping WAV conversion test")
    print("   Install ffmpeg from: https://ffmpeg.org/download.html")
    sys.exit(1)

# Create temporary WAV file
with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_wav:
    temp_wav_path = tmp_wav.name

print(f"   Converting to: {temp_wav_path}")

# Convert with optimal settings for speech recognition
cmd = [
    'ffmpeg',
    '-i', audio_file,
    '-ar', '16000',  # 16kHz sample rate (optimal for speech)
    '-ac', '1',  # Mono (speech recognition works better with mono)
    '-sample_fmt', 's16',  # 16-bit PCM
    '-y',  # Overwrite output file
    temp_wav_path
]

try:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    if result.returncode != 0:
        print(f"   ❌ Conversion failed:")
        print(f"   {result.stderr}")
        os.unlink(temp_wav_path)
        sys.exit(1)

    wav_size = os.path.getsize(temp_wav_path) / (1024*1024)
    print(f"   ✅ Converted successfully ({wav_size:.2f} MB)")

except subprocess.TimeoutExpired:
    print(f"   ❌ Conversion timed out")
    if os.path.exists(temp_wav_path):
        os.unlink(temp_wav_path)
    sys.exit(1)

# Step 2: Upload WAV to GCS
print("\n[2/5] Uploading WAV to Google Cloud Storage...")

try:
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    timestamp = int(time.time())
    blob_name = f"temp/wav_test_{timestamp}.wav"
    blob = bucket.blob(blob_name)

    blob.upload_from_filename(temp_wav_path)
    gcs_uri = f"gs://{bucket_name}/{blob_name}"

    print(f"   ✅ Uploaded: {gcs_uri}")

except Exception as e:
    print(f"   ❌ Upload failed: {e}")
    os.unlink(temp_wav_path)
    sys.exit(1)

# Step 3: Configure recognition for WAV
print("\n[3/5] Configuring recognition for WAV...")

speech_client = speech.SpeechClient()

config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,  # WAV PCM
    sample_rate_hertz=16000,  # Match our conversion
    language_code='en-IN',  # English (India)
    alternative_language_codes=['ml-IN', 'en-US'],  # Malayalam + US English
    enable_automatic_punctuation=True,
    enable_word_time_offsets=True,
    enable_word_confidence=True,
    model='default',
    audio_channel_count=1,  # Mono
)

# Add diarization
diarization_config = speech.SpeakerDiarizationConfig(
    enable_speaker_diarization=True,
    min_speaker_count=1,
    max_speaker_count=2,
)
config.diarization_config = diarization_config

print(f"   ✅ Encoding: LINEAR16 (WAV PCM)")
print(f"   ✅ Sample rate: 16000 Hz")
print(f"   ✅ Channels: 1 (mono)")
print(f"   ✅ Primary language: en-IN")
print(f"   ✅ Alternative languages: ml-IN, en-US")

# Step 4: Start transcription
print("\n[4/5] Starting transcription...")
print("   If this works, we'll get the full transcript!")

audio = speech.RecognitionAudio(uri=gcs_uri)

start_time = time.time()
operation = speech_client.long_running_recognize(config=config, audio=audio)

print("   Waiting for operation to complete...")
response = operation.result(timeout=600)

elapsed = time.time() - start_time
print(f"   ✅ Processing time: {elapsed:.1f} seconds")

# Step 5: Process results
print(f"\n[5/5] Processing results...")
print(f"   Total result segments: {len(response.results)}")

full_transcript = []
total_words = 0

for result in response.results:
    if not result.alternatives:
        continue

    alternative = result.alternatives[0]

    if alternative.transcript.strip():
        full_transcript.append(alternative.transcript)

    if hasattr(alternative, 'words') and alternative.words:
        total_words += len(alternative.words)

complete_transcript = ' '.join(full_transcript)

print("\n" + "=" * 80)
print("TRANSCRIPTION RESULTS")
print("=" * 80)

print(f"\n📊 STATISTICS:")
print(f"   Total words transcribed: {total_words}")
print(f"   Transcript length: {len(complete_transcript)} characters")

print(f"\n📝 FULL TRANSCRIPT:")
print("-" * 80)

if complete_transcript:
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

# Cleanup
print("\n[CLEANUP] Deleting temporary files...")
try:
    blob.delete()
    print("   ✅ Deleted GCS file")
except Exception as e:
    print(f"   ⚠️  Could not delete GCS file: {e}")

try:
    os.unlink(temp_wav_path)
    print("   ✅ Deleted local WAV file")
except Exception as e:
    print(f"   ⚠️  Could not delete local WAV: {e}")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)

# Verification
print(f"\n✅ VERIFICATION:")
if total_words > 200:
    print(f"   ✅ SUCCESS! Transcribed {total_words} words")
    print(f"   ✅ WAV conversion SOLVED the problem!")
    print(f"   ✅ We should convert MP3→WAV before transcription in production")
elif total_words > 100:
    print(f"   ⚠️  Transcribed {total_words} words (expected ~200-300)")
    print(f"   ⚠️  Better than MP3 but still has gaps")
elif total_words > 50:
    print(f"   ⚠️  Transcribed {total_words} words (expected 200-300)")
    print(f"   ⚠️  WAV conversion helped but issue persists")
else:
    print(f"   ❌ Only {total_words} words (expected 200-300)")
    print(f"   ❌ WAV conversion did NOT solve the problem")
    print(f"   ❌ The issue may be with the audio content itself")

print()
